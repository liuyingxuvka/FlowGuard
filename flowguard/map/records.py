"""Write-once raw files and their independent first-write byte protection."""

from __future__ import annotations

from contextvars import ContextVar
import json
import os
import re
import shlex
from datetime import datetime
from pathlib import Path

from .common import (GitRun, atomic_write_text, git_blob, git_common_directory, git_head, git_run,
                     normalize_newlines, sha256_bytes)
from .common import MapError


NO_ORIGINAL_FACT = ("this checkout holds no first commit, first-write receipt or release snapshot of the original "
                    "bytes (a copy without .git, a moved folder, or a Git repository before the first commit)")


class Unverifiable(Exception):
    """No original-byte fact exists for this file here; that is not evidence of an edit."""

    def __init__(self, relative: str):
        self.relative = relative
        super().__init__(f"cannot verify {relative} here: {NO_ORIGINAL_FACT}")


def restore_advice(root, paths, common) -> str:
    """How to get original bytes back: Git only where this checkout is in Git, never a Git command elsewhere."""
    if common is None:
        return "restore its original bytes from the copy, archive or backup this folder came from"
    command = shlex.join(["git", "-C", str(root), "checkout", "--", *paths])
    return f"restore its original bytes ({command} when committed)"


def _paths(root, relative_path):
    root = Path(root).resolve()
    path = (root / relative_path).resolve()
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise MapError(f"immutable file must be inside the project: {relative_path}") from exc
    return root, path, relative


def _common_directory(root: Path):
    return git_common_directory(root)


def _canonical_path(path: Path):
    return Path(os.path.normcase(str(path.resolve()))).as_posix()


def _written_directory(root: Path, common):
    return (common / "flowguard" if common is not None else root / ".flowguard/cache") / "written"


def _written_directories(root: Path, common):
    """Receipt directories for path discovery and write refusal; only the current one supplies a digest."""
    current = _written_directory(root, common)
    previous = _written_directory(root, None)
    return (current,) if current == previous else (current, previous)


def _written_path(root: Path, path: Path, common):
    return _written_directory(root, common) / sha256_bytes(_canonical_path(path).encode("utf-8"))


def _written_paths(root: Path, path: Path, common):
    name = _written_path(root, path, common).name
    return tuple(directory / name for directory in _written_directories(root, common))


def _receipt(path: Path):
    try:
        value = json.loads(path.read_text(encoding="ascii"))
        if (not isinstance(value, dict) or not isinstance(value.get("path"), str)
                or not re.fullmatch("[0-9a-f]{64}", str(value.get("sha256", "")))):
            raise ValueError('expected {"path": ..., "sha256": ...}')
    except (OSError, ValueError) as error:
        raise MapError(f"receipt_unreadable: {path}: {error}") from error
    return value


RELEASE_DIR = Path('.flowguard/release-base')


def _release_records(root):
    path = root / RELEASE_DIR / 'records.json'
    if not path.exists():
        return None
    try:
        item = json.loads(path.read_bytes())
        files = item['files']
        moment = datetime.fromisoformat(item['captured'])
        if (not isinstance(files, dict) or moment.tzinfo is None or moment.utcoffset().total_seconds() != 0
                or any(not isinstance(name, str) or not name.startswith(('.flowguard/requests/', '.flowguard/changes/'))
                       or Path(name).is_absolute() or '..' in Path(name).parts
                       or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest)
                       for name, digest in files.items())):
            raise ValueError('invalid original-byte snapshot')
        return item
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        raise MapError(f'release_snapshot_invalid: {path}: {error}') from error


def _stored_digest(root, path, relative, common):
    """One original-byte source, chosen by the file's state; never hash current bytes to learn a baseline.

    Committed in Git: its first committed blob. No Git and in the release snapshot: the snapshot (an
    invalid snapshot raises release_snapshot_invalid). Otherwise: this checkout's first-write receipt for
    the current mode. None of these: Unverifiable."""
    if common is not None:
        first = _first_blob(root, relative, common)
        if first is not None:
            return sha256_bytes(first)
    else:
        snapshot = _release_records(root)
        if snapshot is not None and relative in snapshot['files']:
            return snapshot['files'][relative]
    written = _written_path(root, path, common)
    if written.is_file():
        return _receipt(written)['sha256']
    raise Unverifiable(relative)


def _attribute_problem(root: Path, relative: str, common):
    if common is None:
        return None
    names = ("text", "eol", "filter", "ident", "working-tree-encoding")
    fields = git_run(root, "check-attr", "-z", *names, "--", relative).stdout.split(b"\0")
    attributes = {os.fsdecode(fields[index + 1]): os.fsdecode(fields[index + 2])
                  for index in range(0, len(fields) - 1, 3)}
    conflicts = {name: value for name, value in attributes.items()
                 if (name == "text" and value != "unset")
                 or (name not in {"text", "eol"} and value not in {"unset", "unspecified"})}
    if conflicts:
        details = ", ".join(f"{name}={value}" for name, value in conflicts.items())
        return f"Git attributes transform immutable bytes in {relative}: {details}; use -text and disable other transforms"
    return None


def prepare_directory(root, relative_dir, extensions):
    """Create a narrow raw-byte guard, preserving an existing attributes file."""
    _, directory, _ = _paths(root, relative_dir)
    directory.mkdir(parents=True, exist_ok=True)
    guard = directory / ".gitattributes"
    if not guard.exists():
        lines = [f"*.{extension.lstrip('.')} -text\n" for extension in extensions]
        with guard.open("xb") as stream:
            stream.write("".join(lines).encode("utf-8"))


def _new_file(root, relative_path):
    root, path, relative = _paths(root, relative_path)
    common = _common_directory(root)
    problem = _attribute_problem(root, relative, common)
    if problem:
        raise MapError(problem)
    candidates = _written_paths(root, path, common)
    written = candidates[0]
    if path.exists() or any(candidate.exists() for candidate in candidates):
        raise MapError(f"immutable file already exists or was written before: {relative}")
    snapshot = _release_records(root)
    if snapshot is not None and relative in snapshot['files']:
        raise MapError(f"immutable file was written before: {relative}")
    if _first_blob(root, relative, common) is not None:
        raise MapError(f"immutable file was committed before: {relative}")
    return path, written


def validate_new_files(root, relative_paths):
    """Check a coupled set before writing its first file; persist no check state."""
    for path in relative_paths:
        _new_file(root, path)


# flowguard: event RECORD_WRITE(root: str | Path, relative_path: str | Path, raw: bytes, _created: list | None)
def write_once(root: str | Path, relative_path: str | Path, raw: bytes, *, _created: list | None = None):
    """Save exact bytes once and protect them outside editable sidecar metadata."""
    path, written = _new_file(root, relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        if _created is not None:
            _created.append(path)
        stream.write(raw)
    written.parent.mkdir(parents=True, exist_ok=True)
    with written.open("x", encoding="ascii") as stream:
        if _created is not None:
            _created.append(written)
        stream.write(json.dumps({"path": path.as_posix(), "sha256": sha256_bytes(raw)}) + "\n")


# flowguard: same ORIGINAL_BYTES(root: str | Path, relative_path: str | Path) -> body: bytes
def read_original_bytes(root: str | Path, relative_path: str | Path) -> bytes:
    """Read a contained original without decoding or changing its byte representation."""
    _, path, _ = _paths(root, relative_path)
    return path.read_bytes()


def _first_blob(root: Path, relative: str, common):
    """The bytes of the commit that first added this path; None outside Git, before the first commit or when
    no commit holds it. A failing Git raises with its own message. Inside `FirstListings` the listing of the
    commits that added it may be one begun ahead."""
    if common is None or git_head(root) is None:
        return None
    listings = FirstListings.current.get()
    started = listings.take(root, relative) if listings is not None else None
    history = (started.result() if started is not None else git_run(root, *_added(relative))).stdout.split()
    if not history:
        return None
    first = history[0].decode("ascii")
    blob = git_blob(root, first, relative)
    if blob is None:
        raise MapError(f"git log names {first} as the commit that added {relative}, but that commit does not hold it")
    return blob


def _added(relative):
    """The arguments of the listing of the commits that added `relative`, oldest first (`_first_blob`)."""
    return "log", "--format=%H", "--diff-filter=A", "--reverse", "--", relative


class FirstListings:
    """While the block runs, the listing `_first_blob` reads of each of `relative_paths` is begun ahead, for the
    integrity checks of these files in this order (`integrity_problem`), the next few beside the one a check reads.
    Only a file inside root that exists gets one, as only its check reads one, by its real path relative to root as
    the check names it; a run no check reads is never read, and leaving the block waits for every run begun.
    At most AHEAD begun runs wait unread (`waiting`): a check can end before it reads its listing (a transforming
    attribute), so when they are that many, the ones of files before the next to begin are waited for unread; a
    check that comes to such a file later runs Git itself, as for a file this block does not list."""
    AHEAD = 4
    current = ContextVar('flowguard_first_listings', default=None)      # the block that runs now

    def __init__(self, root, relative_paths, common):
        root = Path(root).resolve()
        self.root, self.runs, self.waiting, self.taken, self.token = root, {}, {}, set(), None
        found = []
        if common is not None:
            for relative_path in relative_paths:
                path = (root / relative_path).resolve()
                if path.is_relative_to(root) and path.is_file():
                    found.append(path.relative_to(root).as_posix())
        self.order = list(dict.fromkeys(found))
        self.position = {relative: index for index, relative in enumerate(self.order)}

    def _begin(self, first):
        """Begin the listings of the AHEAD files from `first` on that have none, while fewer than AHEAD wait."""
        for relative in self.order[first:first + self.AHEAD]:
            if relative in self.runs:
                continue
            if len(self.waiting) >= self.AHEAD:
                for passed in [other for other in self.waiting if self.position[other] < first]:
                    self.waiting.pop(passed).close()
                if len(self.waiting) >= self.AHEAD:
                    return
            self.runs[relative] = self.waiting[relative] = GitRun(self.root, *_added(relative))

    def take(self, root, relative):
        """The run of `relative`'s listing in `root`, once, begun now if it was not; None for any other, and for
        one already waited for unread."""
        if root != self.root or relative not in self.position or relative in self.taken:
            return None
        self.taken.add(relative)
        run = self.waiting.pop(relative, None)
        if run is None and relative not in self.runs:
            run = self.runs[relative] = GitRun(self.root, *_added(relative))
        self._begin(self.position[relative] + 1)
        return run

    def __enter__(self):
        self._begin(0)
        self.token = FirstListings.current.set(self)
        return self

    def __exit__(self, *exc):
        FirstListings.current.reset(self.token)
        for run in self.runs.values():
            run.close()


def integrity_problem(root, relative_path):
    """Return a byte-protection diagnostic; never learn a baseline from the file.

    Raises Unverifiable when no original-byte fact exists here, so callers never report it as an edit."""
    root, path, relative = _paths(root, relative_path)
    if not path.is_file():
        return f"immutable file is missing: {relative}"
    common = _common_directory(root)
    problem = _attribute_problem(root, relative, common)
    if problem:
        return problem
    raw = read_original_bytes(root, relative)
    expected = _stored_digest(root, path, relative, common)
    if sha256_bytes(raw) != expected:
        return f"immutable file bytes changed: {relative}"
    if common is not None:
        indexed = git_blob(root, ":", relative)
        if indexed is not None and sha256_bytes(indexed) != expected:
            return f"immutable file index bytes changed: {relative}"
    return None


def _named_paths(root: Path, *arguments):
    """Paths a Git listing names; a failing Git raises with its own message."""
    result = git_run(root, *arguments)
    return {os.fsdecode(value).lstrip("\n") for value in result.stdout.split(b"\0") if value.strip(b"\n")}


def _committed_digest(root: Path, relative: str, expected):
    history = git_run(root, "log", "--all", "--format=%H", "--", relative)
    for commit in history.stdout.split():
        blob = git_blob(root, commit.decode("ascii"), relative)  # None: the commit that deleted it
        if blob is not None and sha256_bytes(blob) == expected:
            return True
    return False


def protected_paths(root, relative_dir) -> set[str]:
    """Discover immutable paths, including files deleted before their first commit."""
    root, directory, relative = _paths(root, relative_dir)
    common = _common_directory(root)
    current = set()
    historical = None
    paths = set()
    snapshot = _release_records(root)
    if snapshot is not None:
        paths.update(name for name in snapshot['files'] if name.startswith(relative.rstrip('/') + '/'))
    log = ("log", "--relative", "--format=", "--name-only", "--diff-filter=A", "-z")
    if common is not None:
        paths.update(_named_paths(root, "ls-files", "-z", "--", relative))
        if git_head(root) is not None:  # Before the first commit there is no history to list.
            current = _named_paths(root, *log, "--", relative)
            paths.update(current)
    for receipt_directory in _written_directories(root, common):
        for written in receipt_directory.iterdir() if receipt_directory.is_dir() else ():
            if not written.is_file():
                continue
            receipt = _receipt(written)
            absolute = receipt["path"]
            if not Path(absolute).is_relative_to(directory):
                continue  # The receipt directory is shared: this receipt is for another directory's file.
            candidate = Path(absolute).relative_to(root).as_posix()
            if common is not None and not Path(absolute).exists() and candidate not in paths:
                if historical is None:
                    historical = _named_paths(root, *log, "--all", "--", relative)
                if candidate in historical and _committed_digest(root, candidate, receipt["sha256"]):
                    continue
            paths.add(candidate)
    return {path for path in paths if Path(path).name != ".gitattributes"}
