"""Shared constants, glob matching, hashing and finding output for FlowGuard Map."""

from __future__ import annotations

import errno
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize
import threading
from dataclasses import asdict, dataclass
from functools import lru_cache, wraps
from pathlib import Path

SCHEMA = "flowguard.map.v1"
MAP_RELPATH = Path(".flowguard") / "map.json"
MODELS_RELDIR = Path(".flowguard") / "models"
CACHE_RELDIR = Path(".flowguard") / "cache"
DEFAULT_TEST_COMMAND = "python -m pytest -q"
SOURCE_EXTS = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rs",
               ".java", ".kt", ".cs", ".rb", ".php", ".swift", ".c", ".h", ".cpp", ".hpp"}
JS_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
DEFAULT_IGNORE = [".flowguard/**", ".git/**", "**/__pycache__/**", "node_modules/**",
                  "dist/**", "build/**", ".venv/**", "venv/**", "**/*.min.js"]
LEVELS = ("error", "warn", "info")
ADVICE_IDS = frozenset({"tests", "design", "code", "promote", "confirm", "commit", "add",
                        "describe", "extend", "check", "models", "bind", "rule", "target", "test_command"})
STOPWORDS = {"a", "an", "the", "of", "to", "and", "or", "for", "in", "on", "by", "with",
             "from", "into", "per", "is", "are", "be", "its", "it", "that", "this", "as"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    """Replace a disposable cache atomically, leaving no partial shared file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


_CHILD_PACKAGE_LOCK = threading.Lock()
_CHILD_PACKAGE_DIRECTORY = None


def _child_package_import_root() -> str:
    """Expose just the engine package, sharing its lifetime with this command."""
    package = Path(__file__).resolve().parents[1]
    parent = package.parent
    if not (parent / "pyproject.toml").is_file():
        return str(parent)
    # A model child inherits the parent command's shim. Reuse it rather than
    # building one per subprocess; the waiting parent owns its cleanup.
    for value in os.environ.get("PYTHONPATH", "").split(os.pathsep):
        if not value:
            continue
        candidate = Path(value).resolve()
        try:
            if ((candidate / "flowguard").resolve() == package
                    and {entry.name for entry in candidate.iterdir()} == {"flowguard"}):
                return str(candidate)
        except OSError:
            continue
    global _CHILD_PACKAGE_DIRECTORY
    with _CHILD_PACKAGE_LOCK:
        if _CHILD_PACKAGE_DIRECTORY is None:
            temporary = tempfile.TemporaryDirectory(prefix="flowguard-package-")
            destination = Path(temporary.name) / "flowguard"
            try:
                destination.symlink_to(package, target_is_directory=True)
            except (OSError, NotImplementedError):
                shutil.copytree(package, destination,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            _CHILD_PACKAGE_DIRECTORY = temporary
        return _CHILD_PACKAGE_DIRECTORY.name


def child_import_path(root: Path, data: dict) -> list[str]:
    """Put project imports first without exposing an engine source checkout."""
    root = Path(root).resolve()
    package_parent = Path(__file__).resolve().parents[2]
    source_checkout = (package_parent / "pyproject.toml").is_file()
    candidates = [root, *(root / value for value in data.get("import_roots", ()))]
    source = root / "src"
    if source.is_dir() and any(
        (entry.is_file() and entry.suffix == ".py")
        or (entry.is_dir() and (entry / "__init__.py").is_file())
        for entry in source.iterdir()
    ):
        candidates.append(source)
    for value in os.environ.get("PYTHONPATH", "").split(os.pathsep):
        if value:
            candidate = Path(value)
            candidates.append(candidate if candidate.is_absolute() else root / candidate)
    candidates.append(Path(_child_package_import_root()))
    paths = []
    for candidate in candidates:
        resolved = Path(candidate).resolve()
        if source_checkout and resolved == package_parent and resolved != root:
            continue
        value = str(resolved)
        if value not in paths:
            paths.append(value)
    return paths


def child_pytest_environment(environment):
    """Give a new pytest owner its own control and receipt paths."""
    child = dict(environment)
    for name in ("FLOWGUARD_PYTEST_COLLECTION_NODEIDS", "FLOWGUARD_PYTEST_SHARD_NODEIDS",
                 "FLOWGUARD_PYTEST_SHARD_COLLECTION", "FLOWGUARD_PYTEST_NODEIDS"):
        child.pop(name, None)
    return child


def normalize_newlines(data: bytes) -> bytes:
    """Canonical physical source newlines for fingerprints and equivalence checks."""
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def parse_test_anchor(anchor: str) -> tuple[str, str, str]:
    """Split a TESTED_BY anchor's optional exact pytest parameter item suffix."""
    path, _, symbol = anchor.partition(":")
    if "[" not in symbol and "]" not in symbol:
        return path, symbol, ""
    base, opening, item = symbol.partition("[")
    if (not opening or not base or "]" in base or not item.endswith("]")
            or not item[:-1] or any(char in item[:-1] for char in "[]\r\n")):
        raise ValueError(f"TESTED_BY anchor {anchor!r} has a malformed parameter selector; use 'path.py:test_name[param-id]'")
    return path, base, opening + item


def content_digest(path: Path) -> str:
    """sha256 with physical newlines normalized, so platform checkouts agree."""
    return sha256_bytes(normalize_newlines(path.read_bytes()))


def read_source(path: Path, *, data: bytes | None = None) -> str:
    """Source text as Python reads it: UTF-8 BOM and PEP 263 coding cookie honored, LF newlines,
    undecodable bytes replaced (never raises UnicodeDecodeError). Raises OSError like read_text."""
    data = path.read_bytes() if data is None else data
    encoding = "utf-8-sig"
    if path.suffix == ".py":
        try:
            encoding = tokenize.detect_encoding(io.BytesIO(data).readline)[0]
        except SyntaxError:                       # unknown or conflicting coding cookie
            pass
    try:
        text = data.decode("utf-8-sig" if encoding == "utf-8" else encoding, errors="replace")
    except LookupError:
        text = data.decode("utf-8-sig", errors="replace")
    return text.replace("\r\n", "\n")


def git_paths(root: Path, *args: str) -> list[str]:
    """NUL-separated git output (run with -z) as file names; never quoted, never locale-decoded."""
    out = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True).stdout
    return [os.fsdecode(item) for item in out.split(b"\0") if item]


def safe_stdio() -> None:
    """Print text the console code page cannot encode as escapes instead of crashing (Windows cp1252/GBK)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass


class _PipeOutput:
    """Translate the Windows closed-pipe spelling only at stdout operations."""
    def __init__(self, stream):
        self.stream = stream

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def _output(self, operation, *args):
        try:
            return getattr(self.stream, operation)(*args)
        except OSError as exc:
            if sys.platform == "win32" and exc.errno == errno.EINVAL:
                raise BrokenPipeError("closed stdout pipe") from exc
            raise

    def write(self, text):
        return self._output("write", text)

    def flush(self):
        return self._output("flush")


def quiet_broken_pipe(command):
    """Exit quietly when a consumer closes stdout, including buffered final output."""
    @wraps(command)
    def run(*args, **kwargs):
        original = sys.stdout
        if sys.platform == "win32" and not isinstance(original, _PipeOutput):
            sys.stdout = _PipeOutput(original)
        output = sys.stdout
        try:
            try:
                try:
                    return command(*args, **kwargs)
                finally:
                    sys.stdout.flush()
            except BrokenPipeError:
                # Prevent another buffered write during interpreter shutdown.
                sys.stdout = open(os.devnull, "w")
                return 0
        finally:
            if sys.stdout is output:
                sys.stdout = original
    return run


def cache_dir(root: Path) -> Path:
    """Disposable cache ignores itself, including in newly adopted repositories."""
    directory = root / CACHE_RELDIR
    directory.mkdir(parents=True, exist_ok=True)
    ignore = directory / ".gitignore"
    if not ignore.exists():
        ignore.write_text("*\n", encoding="utf-8")
    return directory


def norm(path: str) -> str:
    path = path.replace("\\", "/")
    return path[2:] if path.startswith("./") else path


@lru_cache(maxsize=4096)
def _glob_regex(pattern: str) -> "re.Pattern[str]":
    regex, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            regex, i = regex + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            regex, i = regex + ".*", i + 2
        else:
            c = pattern[i]
            regex += "[^/]*" if c == "*" else "[^/]" if c == "?" else re.escape(c)
            i += 1
    return re.compile(regex)


def glob_match(path: str, pattern: str) -> bool:
    """Glob where '**' crosses directories and '*' stays inside one path segment."""
    return _glob_regex(pattern).fullmatch(path) is not None


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(glob_match(path, p) for p in patterns)


def is_test_file(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    parts = path.split("/")[:-1]
    return (name.startswith("test_") or name.endswith("_test.py") or ".test." in name
            or ".spec." in name or "tests" in parts or "test" in parts or "__tests__" in parts)


def is_collectable_test(path: str) -> bool:
    """Runnable test files, excluding support modules and conftest.py."""
    name = path.rsplit("/", 1)[-1]
    return (name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))
            or Path(path).suffix in JS_EXTS and (".test." in name or ".spec." in name))


def is_product_file(path: str, patterns: list[str]) -> bool:
    """An exact files declaration overrides the test-name heuristic."""
    return matches_any(path, patterns) and (not is_test_file(path) or any(
        norm(pattern) == path and not any(char in pattern for char in "*?[") for pattern in patterns))


def tokens(text: str) -> set[str]:
    """Lowercase word tokens without stopwords, plus CJK character bigrams."""
    text = text.lower()
    words = {w for w in re.findall(r"[a-z0-9]+", text) if w not in STOPWORDS and len(w) > 1}
    cjk = re.findall("[\u4e00-\u9fff]", text)          # CJK ideographs
    return words | {a + b for a, b in zip(cjk, cjk[1:])}


@dataclass
class Finding:
    level: str        # error | warn | info
    code: str         # stable machine code, e.g. file_unmapped
    component: str    # component id or "" when not attributable
    message: str

    def line(self) -> str:
        return f"{self.level.upper():5} {self.code:24} {self.component or '-':26} {self.message}"


def project_command(root: Path, *arguments: str) -> str:
    """One shell-quoted public command tied to its actual absolute project."""
    import shlex
    return shlex.join(['python', '-m', 'flowguard', *arguments, '--root', str(Path(root).resolve())])


def advice(identifier: str, command: str, *, note: str | None = None) -> dict[str, str]:
    if identifier not in ADVICE_IDS:
        raise ValueError(f"unknown advice id: {identifier}")
    item = {"id": identifier, "command": command}
    if note:
        item['note'] = note
    return item


def render_advice(item: dict[str, str]) -> str:
    return (f"note: {item['note']}\n" if item.get('note') else '') + f"next[{item['id']}]: {item['command']}"


def finding_codes(findings: list[Finding], *, include_info: bool = False) -> list[dict[str, str]]:
    return [{"level": item.level, "code": item.code, "subject": item.component or "-"}
            for item in findings if include_info or item.level != "info"]


def print_verdict(command: str, exit_code: int, codes=(), next_advice=None, **extra) -> None:
    verdict = "PASS" if exit_code == 0 else "OPEN" if command == "target check" and exit_code == 3 else "FAIL"
    print(json.dumps({"command": command, "verdict": verdict, "codes": list(codes),
                      "next": next_advice, **extra}, ensure_ascii=False))


def print_findings(
    findings: list[Finding], name: str, *, as_json: bool, limit: int, command: str | None = None
) -> dict[str, int]:
    order = {lvl: i for i, lvl in enumerate(LEVELS)}
    findings.sort(key=lambda f: (order[f.level], f.code, f.component, f.message))
    counts = {lvl: sum(f.level == lvl for f in findings) for lvl in LEVELS}
    if as_json:
        print_verdict(command or name, int(bool(counts["error"])),
                      finding_codes(findings, include_info=name == "lint"),
                      counts=counts, findings=[asdict(f) for f in findings])
    else:
        covered = 0
        visible = []
        for finding in findings:
            if finding.level == "info" and " (accepted debt: " in finding.message:
                covered += 1
            else:
                visible.append(finding)
        rows = []
        grouped = {}
        for finding in visible:
            if finding.level == "info":
                grouped.setdefault(finding.code, []).append(finding)
        emitted = set()
        for finding in visible:
            group = grouped.get(finding.code, []) if finding.level == "info" else []
            if len(group) >= 3:
                if finding.code in emitted:
                    continue
                emitted.add(finding.code)
                ids = ", ".join(item.component or "-" for item in group[:8])
                more = (
                    f" (+{len(group)-8} more; python -m flowguard map lint --json)"
                    if len(group) > 8
                    else ""
                )
                rows.append(f"INFO {finding.code} x{len(group)}: {ids}{more}")
            else:
                rows.append(finding.line())
        for row in rows[:limit]:
            print(row)
        hidden = len(rows) - min(len(rows), limit)
        if hidden:
            print(f"... {hidden} more (use --limit N or --json)")
        if covered:
            print(
                f"({covered} finding(s) covered by accepted debts not shown: python -m flowguard map lint --debts)"
            )
        print(
            f"{name}: {counts['error']} error(s), {counts['warn']} warning(s), {counts['info']} info"
        )
    return counts
