"""Shared source identity, Git reads and original-word boundaries."""
from __future__ import annotations

import errno
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize
from dataclasses import dataclass
from functools import lru_cache, wraps
from pathlib import Path

CACHE_RELDIR = Path('.flowguard') / 'cache'
SOURCE_EXTS = {'.py', '.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.go', '.rs',
               '.java', '.kt', '.cs', '.rb', '.php', '.swift', '.c', '.h', '.cpp', '.hpp'}
DEFAULT_IGNORE = ['.flowguard/**', '.git/**', '**/__pycache__/**', 'node_modules/**',
                  'dist/**', 'build/**', '.venv/**', 'venv/**', '**/*.min.js']




class MapError(Exception):
    """The map file is missing or invalid; the message says what to fix."""



def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()



def git_run(root, *arguments: str, allowed=(0,), input: bytes | None = None, env=None) -> subprocess.CompletedProcess:
    """Run git; a missing executable or an exit outside `allowed` is an error that carries Git's own message."""
    try:
        result = subprocess.run(["git", "-C", str(root), *arguments], capture_output=True, input=input, env=env)
    except FileNotFoundError as error:
        raise MapError("git executable not found: FlowGuard reads the project's Git state with it; "
                       "install Git or put it on PATH") from error
    if result.returncode not in allowed:
        reason = os.fsdecode(result.stderr).strip() or f"exit status {result.returncode}"
        raise MapError(f"git {arguments[0]} failed in {root}: {reason}")
    return result



def git_common_directory(root) -> Path | None:
    """Decide the Git mode once: the repository's shared Git directory, or None when root is in no Git repository.

    A .git in root or a parent, or GIT_DIR, means a repository. Git exits 128 both where there is none and for a
    repository it cannot open (one owned by another user, a damaged .git), so in a repository that exit raises; a
    folder in no repository needs no Git executable. A folder inside the Git directory itself (a cache under
    .git/) has no work tree, so Git says it is not inside one and it is read as a folder without Git. Any other
    folder outside a work tree (a checkout whose repository says core.bare=true) raises with Git's refusal."""
    place = Path(root).resolve()
    repository = "GIT_DIR" in os.environ or any((folder / ".git").exists() for folder in (place, *place.parents))
    if not repository and shutil.which("git") is None:
        return None
    result = git_run(root, "rev-parse", "--is-inside-work-tree", "--is-inside-git-dir", "--git-common-dir",
                     allowed=(0, 128))
    if result.returncode:
        if repository:
            reason = os.fsdecode(result.stderr).strip() or f"exit status {result.returncode}"
            raise MapError(f"git rev-parse failed in {root}: {reason}")
        return None
    inside, in_git_directory, directory = (os.fsdecode(result.stdout).strip().split("\n") + ["", ""])[:3]
    if inside.strip() != "true":
        if in_git_directory.strip() == "true":
            return None
        git_run(root, "rev-parse", "--show-toplevel")  # raises with Git's refusal ("must be run in a work tree")
        raise MapError(f"git rev-parse in {root} names a repository but no work tree")
    directory = Path(directory.strip())
    return (directory if directory.is_absolute() else Path(root) / directory).resolve()



def git_head(root) -> str | None:
    """The HEAD commit of a Git repository, or None on a branch that has no commit yet.

    A HEAD that names neither a commit nor a branch still to be born (a broken branch ref, a damaged detached
    HEAD) raises with Git's own diagnosis."""
    found = git_run(root, "rev-parse", "-q", "--verify", "HEAD", allowed=(0, 1))
    if not found.returncode:
        return os.fsdecode(found.stdout).strip()
    if git_run(root, "symbolic-ref", "-q", "HEAD", allowed=(0, 1, 128)).returncode == 0:
        return None  # HEAD names a branch with no commit yet; a broken branch ref makes symbolic-ref exit 128
    git_run(root, "log", "-1", "--format=%H")  # raises with Git's diagnosis ("your current branch appears to be broken")
    raise MapError(f"HEAD in {root} names no commit and no new branch")



def git_path_object(root, revision: str, relative: str) -> str | None:
    """The object id of `relative` at a tree-ish, or in the index (stage 0) when revision is ":".

    None only when Git lists no such path there. Git lists entries with ls-tree and ls-files, which exit 0 with
    no entry for an absent path and fail with Git's message for a tree or index it cannot read; rev-parse
    --verify exits 1 for both, so it never answers this question."""
    relative = Path(relative).as_posix()  # Git lists names with "/", relative to root
    if revision == ":":
        literal = {**os.environ, "GIT_LITERAL_PATHSPECS": "1"}  # the name is one file, never a glob pattern
        listing, field = git_run(root, "ls-files", "--stage", "-z", "--", relative, env=literal).stdout, 1
    else:
        listing, field = git_run(root, "ls-tree", "-z", revision, "--", relative).stdout, 2
    for row in listing.split(b"\0"):
        description, _, name = row.partition(b"\t")
        fields = description.split()
        if os.fsdecode(name) == relative and (revision != ":" or fields[2] == b"0"):
            return os.fsdecode(fields[field])
    return None



def git_blob(root, revision: str, relative: str) -> bytes | None:
    """The raw bytes of `relative` at a commit, or in the index when revision is ":", in a known Git repository.

    None only when that path is not there; a commit missing from this clone, a tree Git cannot read or a failing
    Git raises."""
    if revision != ":" and git_run(root, "rev-parse", "-q", "--verify", revision + "^{commit}", allowed=(0, 1)).returncode:
        raise MapError(f"commit {revision} is not in the Git repository at {root}")
    found = git_path_object(root, revision, relative)
    if found is None:
        return None
    return git_run(root, "cat-file", "blob", found).stdout


def git_renames(root, revision: str) -> dict[str, str]:
    """{path now: path at `revision`} of each file Git's rename detection (`diff -M`) finds moved since that
    commit, both paths relative to root (`--relative`: below the repository's top folder a move across root's edge
    is none). Git compares only the files it tracks, so a file moved without `git add` (an untracked one) is no
    rename. The one reader of renames: the map's `Change.renamed` and the comparisons read it."""
    parts = git_run(root, "diff", "-M", "--name-status", "-z", "--relative", "--diff-filter=R", revision, "--").stdout.split(b"\0")
    return {os.fsdecode(parts[index + 2]): os.fsdecode(parts[index + 1])
            for index in range(0, len(parts) - 2, 3) if parts[index].startswith(b"R")}


def git_files(root) -> frozenset[str]:
    """The files of the work tree under root that Git lists, tracked ones and untracked ones it does not ignore,
    relative to root; none outside Git. A run reads them once for its block, whose shortened paths may name no other
    of these files (`signals.render_block`)."""
    if git_common_directory(root) is None:
        return frozenset()
    listed = git_run(root, "ls-files", "-z").stdout + git_run(root, "ls-files", "--others", "--exclude-standard", "-z").stdout
    return frozenset(os.fsdecode(name) for name in listed.split(b"\0") if name)



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



def normalize_newlines(data: bytes) -> bytes:
    """Canonical physical source newlines for fingerprints and equivalence checks."""
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")



def literal_value(node, default=None):
    """The literal value of a Python syntax node or source text, or `default` when it is none: the one literal
    reader of the package (the map's JS/TS constants, the cache screen, the owners' constants, the dependency
    closure). A value too deep to read is not a literal either."""
    import ast
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return default


def content_digest(path: Path, *, data: bytes | None = None, source_only: bool = False) -> str:
    """Normalize source newlines; a checked non-source input keeps its real bytes.

    The default preserves the existing general content identity. Input receipts
    select source_only so binary/resources cannot alias different staged bytes.
    """
    raw = path.read_bytes() if data is None else data
    if not source_only or path.suffix in SOURCE_EXTS:
        raw = normalize_newlines(raw)
    return sha256_bytes(raw)



def read_source(path: Path, *, data: bytes | None = None) -> str:
    """Source text as Python reads it: UTF-8 BOM and PEP 263 coding cookie honored, LF newlines,
    undecodable bytes replaced (never raises UnicodeDecodeError). Raises OSError like read_text."""
    data = normalize_newlines(path.read_bytes() if data is None else data)
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
    return text



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



@dataclass
class Finding:
    level: str        # error | warn | info
    code: str         # stable machine code, e.g. file_unmapped
    component: str    # component id or "" when not attributable
    message: str

    def line(self) -> str:
        return f"{self.level.upper():5} {self.code:24} {self.component or '-':26} {self.message}"
