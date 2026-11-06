"""Write-once raw files and their independent first-write byte protection."""

from __future__ import annotations

import json
import os
import re
import shlex
from datetime import datetime, timezone
from pathlib import Path

from .common import (Finding, atomic_write_text, git_blob, git_common_directory, git_head, git_run,
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


# flowguard: sensor ORIGINAL_BYTES(root: str | Path, relative_path: str | Path) -> body: bytes
def read_original_bytes(root: str | Path, relative_path: str | Path) -> bytes:
    """Read a contained original without decoding or changing its byte representation."""
    _, path, _ = _paths(root, relative_path)
    return path.read_bytes()


def _first_blob(root: Path, relative: str, common):
    """The bytes of the commit that first added this path; None outside Git, before the first commit or when
    no commit holds it. A failing Git raises with its own message."""
    if common is None or git_head(root) is None:
        return None
    history = git_run(root, "log", "--format=%H", "--diff-filter=A", "--reverse", "--", relative).stdout.split()
    if not history:
        return None
    first = history[0].decode("ascii")
    blob = git_blob(root, first, relative)
    if blob is None:
        raise MapError(f"git log names {first} as the commit that added {relative}, but that commit does not hold it")
    return blob


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


CHANGE_DIR = Path(".flowguard/changes")
_RECORD_LISTS = ("requests", "plan", "rules", "acceptances", "existing_cleared",
                 "implemented_by", "new_actions", "corrections")


def _record_files(root):
    """Record files on disk or protected; a legacy .msg written by FlowGuard 0.71.x stays protected."""
    paths = {path.relative_to(root).as_posix() for pattern in ("*.json", "*.msg")
             for path in (root / CHANGE_DIR).glob(pattern)}
    paths.update(Path(path).as_posix() for path in protected_paths(root, CHANGE_DIR)
                 if Path(path).suffix in {".json", ".msg"})
    return paths


def _record_identifiers(files):
    return sorted({Path(path).stem for path in files})


def _change_record(root, identifier, files):
    if not re.fullmatch(r"[0-9]{8}-[0-9]{4}-[0-9a-f]{6}", identifier):
        raise ValueError("invalid change record name")
    for extension in ("msg", "json"):
        relative = CHANGE_DIR / (identifier + "." + extension)
        if extension == "msg" and relative.as_posix() not in files:
            continue
        problem = integrity_problem(root, relative)
        if problem:
            raise ValueError(problem)
    item = json.loads((root / CHANGE_DIR / (identifier + ".json")).read_bytes())
    if (not isinstance(item, dict) or item.get("kind") != "change"
            or not isinstance(item.get("goal"), str) or not item["goal"].strip()
            or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("tree", "")))
            or "base" not in item
            or item.get("base") is not None and not isinstance(item["base"], str)
            or not isinstance(item.get("checked"), str) or not item["checked"].strip()
            or not isinstance(item.get("promoted"), str)
            or any(not isinstance(item.get(key), list) for key in _RECORD_LISTS)):
        raise ValueError("invalid change record fields")
    moment = datetime.fromisoformat(item["promoted"])
    if moment.tzinfo is None or moment.utcoffset().total_seconds() != 0:
        raise ValueError("promoted must be UTC")
    seen = set()
    for link in item["requests"]:
        if (not isinstance(link, dict) or set(link) != {"id", "part"}
                or not isinstance(link["id"], str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", link["id"])
                or type(link["part"]) is not bool or link["id"] in seen):
            raise ValueError("invalid change request link")
        seen.add(link["id"])
    return item


def _record_restore(root, identifier, files, common):
    return restore_advice(root, sorted(path for path in files if Path(path).stem == identifier), common)


def change_records(root, *, unreadable=None):
    """Complete, schema-valid, byte-protected successful records; the others are never facts.

    An unreadable record is never dropped silently: it is appended to `unreadable` as (id, error) for a
    caller that shows it, and without that list it stops with MapError naming it. record_findings reports
    it as record_edited and an unverifiable one as immutable_unverified."""
    root = Path(root).resolve()
    records = []
    files = _record_files(root)
    for identifier in _record_identifiers(files):
        try:
            records.append((identifier, _change_record(root, identifier, files)))
        except Unverifiable:
            continue  # Not a fact here (DECISIONS FG-801); record_findings reports immutable_unverified.
        except (OSError, ValueError) as error:
            problem = f"{error}; {_record_restore(root, identifier, files, _common_directory(root))}"
            if unreadable is None:
                raise MapError(f"change record {identifier} unreadable: {problem}") from error
            unreadable.append((identifier, problem))
    return records


def save_release_snapshot(root):
    """After green gates, preserve original digests and the current release boundary."""
    root = Path(root).resolve()
    common = _common_directory(root)
    if common is not None:
        return
    files = {}
    for directory in (Path('.flowguard/requests'), CHANGE_DIR):
        for relative in sorted(protected_paths(root, directory)):
            try:
                files[relative] = _stored_digest(root, root / relative, relative, common)
            except Unverifiable:
                continue  # Never take a baseline from current bytes; check reports immutable_unverified.
    unreadable = []
    changes = [identifier for identifier, _ in change_records(root, unreadable=unreadable)]
    if unreadable:
        identifier, error = unreadable[0]
        raise MapError(f"change record {identifier} unreadable: {error}; the release boundary would leave it out "
                       f"({len(unreadable)} unreadable; python -m flowguard status)")
    captured = datetime.now(timezone.utc).isoformat()
    records = {'captured': captured, 'files': files}
    covered = {'captured': captured, 'changes': changes}
    directory = root / RELEASE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    atomic_write_text(directory / 'records.json', json.dumps(records, ensure_ascii=False, sort_keys=True) + '\n')
    atomic_write_text(directory / 'covered.json', json.dumps(covered, sort_keys=True) + '\n')


def since_release(root, records, read_git_paths):
    """Derive the change records and retire records made since a reachable version tag."""
    patterns = ('v[0-9]*', '[0-9]*')
    tag = None
    if (git_common_directory(root) is not None and git_head(root) is not None
            and git_run(root, 'tag', '--merged', 'HEAD', '--list', *patterns).stdout.strip()):
        matches = [part for pattern in patterns for part in ('--match', pattern)]
        tag = os.fsdecode(git_run(root, 'describe', '--tags', '--abbrev=0', *matches).stdout).strip()
    retired_dir = '.flowguard/requests/retired/'
    if not tag or not re.fullmatch(r'v?[0-9]+\.[0-9]+\.[0-9]+', tag):
        snapshot = _release_records(root)
        boundary = root / RELEASE_DIR / 'covered.json'
        unknown = {'release': None, 'changes': None, 'released_retired': None}
        if snapshot is None or not boundary.is_file():
            return {**unknown, 'known_from': 'unknown: no reachable version release tag or complete legacy release snapshot'}
        try:
            covered = json.loads(boundary.read_bytes())
            if (not isinstance(covered, dict) or covered.get('captured') != snapshot['captured']
                    or not isinstance(covered.get('changes'), list)
                    or any(not isinstance(identifier, str) or not re.fullmatch(r'[0-9]{8}-[0-9]{4}-[0-9a-f]{6}', identifier)
                           for identifier in covered['changes'])):
                raise ValueError('it does not name the change records of the snapshot captured ' + snapshot['captured'])
        except (OSError, ValueError) as error:
            return {**unknown, 'known_from': f'unknown: release boundary {boundary} is unreadable: {error}'}
        changes = [dict(id=identifier, goal=record['goal'], requests=record['requests'], promoted=record['promoted'])
                   for identifier, record in records if identifier not in covered['changes']]
        retired = sorted(Path(path).stem for path in snapshot['files']
                         if path.startswith(retired_dir) and path.endswith('.json'))
        return {'release': 'snapshot ' + snapshot['captured'],
                'known_from': 'nongit release snapshot ' + snapshot['captured'] + ' and current immutable records',
                'changes': changes, 'released_retired': retired}
    prior = read_git_paths(root, 'ls-tree', '-r', '--name-only', '-z', tag, '--',
                           '.flowguard/changes', '.flowguard/requests')
    covered = {Path(path).stem for path in prior if path.startswith('.flowguard/changes/') and path.endswith('.json')}
    retired = sorted(Path(path).stem for path in prior if path.startswith(retired_dir) and path.endswith('.json'))
    changes = [dict(id=identifier, goal=record['goal'], requests=record['requests'], promoted=record['promoted'])
               for identifier, record in records if identifier not in covered]
    return {'release': tag, 'known_from': f'release tag {tag} and current records',
            'changes': changes, 'released_retired': retired}


def record_findings(root):
    """Fresh pair integrity; missing, orphaned and edited records remain errors."""
    root = Path(root).resolve()
    findings = []
    unverified = []
    files = _record_files(root)
    common = _common_directory(root)
    for identifier in _record_identifiers(files):
        try:
            _change_record(root, identifier, files)
        except Unverifiable:
            unverified.append(identifier)
        except (OSError, ValueError) as error:
            findings.append(Finding("error", "record_edited", identifier,
                                    f"{root / CHANGE_DIR / identifier}: {error}; records are written once; "
                                    f"{_record_restore(root, identifier, files, common)}"))
    if unverified:
        findings.append(Finding("info", "immutable_unverified", "",
                                f"{len(unverified)} change record(s) not used here "
                                f"(first: {min(path for path in files if Path(path).stem == unverified[0])}): "
                                f"{NO_ORIGINAL_FACT}; check them in a checkout that holds one"))
    return findings
