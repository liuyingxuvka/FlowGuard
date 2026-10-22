"""Shared constants, glob matching, hashing and finding output for FlowGuard Map."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tokenize
from dataclasses import asdict, dataclass
from functools import lru_cache
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
STOPWORDS = {"a", "an", "the", "of", "to", "and", "or", "for", "in", "on", "by", "with",
             "from", "into", "per", "is", "are", "be", "its", "it", "that", "this", "as"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_newlines(data: bytes) -> bytes:
    """Canonical physical source newlines for fingerprints and equivalence checks."""
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def content_digest(path: Path) -> str:
    """sha256 with physical newlines normalized, so platform checkouts agree."""
    return sha256_bytes(normalize_newlines(path.read_bytes()))


def read_source(path: Path) -> str:
    """Source text as Python reads it: UTF-8 BOM and PEP 263 coding cookie honored, LF newlines,
    undecodable bytes replaced (never raises UnicodeDecodeError). Raises OSError like read_text."""
    data = path.read_bytes()
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


def print_findings(findings: list[Finding], name: str, *, as_json: bool, limit: int) -> dict[str, int]:
    order = {lvl: i for i, lvl in enumerate(LEVELS)}
    findings.sort(key=lambda f: (order[f.level], f.code, f.component, f.message))
    counts = {lvl: sum(f.level == lvl for f in findings) for lvl in LEVELS}
    if as_json:
        print(json.dumps({"command": name, "counts": counts, "findings": [asdict(f) for f in findings]}, indent=1))
    else:
        for f in findings[:limit]:
            print(f.line())
        hidden = len(findings) - min(len(findings), limit)
        if hidden:
            print(f"... {hidden} more (use --limit N or --json)")
        print(f"{name}: {counts['error']} error(s), {counts['warn']} warning(s), {counts['info']} info")
    return counts
