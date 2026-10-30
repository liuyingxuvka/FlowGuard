"""Write-once raw files and their independent first-write byte protection."""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .common import Finding, normalize_newlines, sha256_bytes
from .mapfile import MapError


def _git(root: Path, *arguments: str):
    try:
        return subprocess.run(["git", "-C", str(root), *arguments], capture_output=True)
    except FileNotFoundError:
        return None


def _paths(root, relative_path):
    root = Path(root).resolve()
    path = (root / relative_path).resolve()
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise MapError(f"immutable file must be inside the project: {relative_path}") from exc
    return root, path, relative


def _common_directory(root: Path):
    result = _git(root, "rev-parse", "--git-common-dir")
    if result is None or result.returncode:
        return None
    directory = Path(os.fsdecode(result.stdout).strip())
    return (directory if directory.is_absolute() else root / directory).resolve()


def _canonical_path(path: Path):
    return Path(os.path.normcase(str(path.resolve()))).as_posix()


def _written_directory(root: Path, common):
    return (common / "flowguard" if common is not None else root / ".flowguard/cache") / "written"


def _written_directories(root: Path, common):
    """Git initialization does not retire the original nongit receipts."""
    current = _written_directory(root, common)
    previous = _written_directory(root, None)
    return (current,) if current == previous else (current, previous)


def _written_path(root: Path, path: Path, common):
    return _written_directory(root, common) / sha256_bytes(_canonical_path(path).encode("utf-8"))


def _written_paths(root: Path, path: Path, common):
    name = _written_path(root, path, common).name
    return tuple(directory / name for directory in _written_directories(root, common))


def _receipt(path: Path):
    text = path.read_text(encoding="ascii").strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {"sha256": text}  # Earlier local receipts contained only the digest.
    return value if isinstance(value, dict) else {"sha256": text}


def _attribute_problem(root: Path, relative: str, common):
    if common is None:
        return None
    names = ("text", "eol", "filter", "ident", "working-tree-encoding")
    result = _git(root, "check-attr", "-z", *names, "--", relative)
    if result is None or result.returncode:
        return f"cannot check Git attributes for {relative}"
    fields = result.stdout.split(b"\0")
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
    if _first_blob(root, relative, common) is not None:
        raise MapError(f"immutable file was committed before: {relative}")
    return path, written


def validate_new_files(root, relative_paths):
    """Check a coupled set before writing its first file; persist no check state."""
    for path in relative_paths:
        _new_file(root, path)


def write_once(root, relative_path, raw, *, _created=None):
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


def _first_blob(root: Path, relative: str, common):
    if common is None:
        return None
    history = _git(root, "log", "--format=%H", "--diff-filter=A", "--reverse", "--", relative)
    if history is None or history.returncode or not history.stdout.strip():
        return None
    first = history.stdout.splitlines()[0].decode("ascii")
    blob = _git(root, "show", f"{first}:./{relative}")
    return blob.stdout if blob is not None and not blob.returncode else None


def integrity_problem(root, relative_path):
    """Return a byte-protection diagnostic; never learn a baseline from the file."""
    root, path, relative = _paths(root, relative_path)
    if not path.is_file():
        return f"immutable file is missing: {relative}"
    common = _common_directory(root)
    problem = _attribute_problem(root, relative, common)
    if problem:
        return problem
    raw = path.read_bytes()
    receipts = [_receipt(written).get("sha256") for written in _written_paths(root, path, common)
                if written.is_file()]
    if receipts:
        expected = receipts[0]
        if any(value != expected for value in receipts[1:]):
            return f"immutable file has conflicting first-write receipts: {relative}"
    else:
        first = _first_blob(root, relative, common)
        if first is None:
            return f"immutable file has no first-write or committed baseline: {relative}"
        expected = sha256_bytes(first)
    if sha256_bytes(raw) != expected:
        return f"immutable file bytes changed: {relative}"
    if common is not None:
        indexed = _git(root, "show", f":./{relative}")
        if indexed is not None and not indexed.returncode and sha256_bytes(indexed.stdout) != expected:
            return f"immutable file index bytes changed: {relative}"
    return None


def _named_paths(root: Path, *arguments):
    result = _git(root, *arguments)
    if result is None or result.returncode:
        return set()
    return {os.fsdecode(value).lstrip("\n") for value in result.stdout.split(b"\0") if value.strip(b"\n")}


def _committed_digest(root: Path, relative: str, expected):
    history = _git(root, "log", "--all", "--format=%H", "--", relative)
    if history is None or history.returncode:
        return False
    for commit in history.stdout.splitlines():
        blob = _git(root, "show", f"{commit.decode('ascii')}:./{relative}")
        if blob is not None and not blob.returncode and sha256_bytes(blob.stdout) == expected:
            return True
    return False


def protected_paths(root, relative_dir) -> set[str]:
    """Discover immutable paths, including files deleted before their first commit."""
    root, directory, relative = _paths(root, relative_dir)
    common = _common_directory(root)
    current = set()
    historical = None
    paths = set()
    if common is not None:
        paths = _named_paths(root, "ls-files", "-z", "--", relative)
        log = ("log", "--relative", "--format=", "--name-only", "--diff-filter=A", "-z")
        current = _named_paths(root, *log, "--", relative)
        paths.update(current)
    for receipt_directory in _written_directories(root, common):
        for written in receipt_directory.iterdir() if receipt_directory.is_dir() else ():
            if not written.is_file():
                continue
            receipt = _receipt(written)
            absolute = receipt.get("path")
            if not isinstance(absolute, str):
                continue
            try:
                Path(absolute).relative_to(directory)
                candidate = Path(absolute).relative_to(root).as_posix()
            except ValueError:
                continue
            if common is not None and not Path(absolute).exists() and candidate not in paths:
                if historical is None:
                    historical = _named_paths(root, *log, "--all", "--", relative)
                if candidate in historical and _committed_digest(root, candidate, receipt.get("sha256")):
                    continue
            paths.add(candidate)
    return {path for path in paths if Path(path).name != ".gitattributes"}


CHANGE_DIR = Path(".flowguard/changes")
_RECORD_LISTS = ("requests", "plan", "rules", "acceptances", "existing_cleared",
                 "implemented_by", "new_actions", "corrections")


def _diff_provenance(root, base, inputs, changed_paths):
    """Read actual base-to-worktree source changes, without an authored claim."""
    from difflib import SequenceMatcher
    from .inventory import function_digests

    commit = base.get("git")
    if not isinstance(commit, str):
        return [], [], "Exact changed functions and correction before-images are unavailable without a Git base."
    if changed_paths is None:
        return [], [], "The Git base diff is unavailable; implementation and correction provenance are unknown."
    paths = set(changed_paths)
    implemented, corrections = [], []
    for relative in sorted(paths):
        correction = relative == ".flowguard/skeleton.py" or Path(relative).name in {"world.py", "machine.py"}
        if not relative.endswith(".py") or relative.startswith(".flowguard/") and not correction:
            continue
        previous = _git(root, "show", f"{commit}:./{relative}")
        before = previous.stdout if previous is not None and not previous.returncode else b""
        path = root / relative
        after = path.read_bytes() if path.is_file() else b""
        try:
            old = normalize_newlines(before).decode("utf-8")
            new = normalize_newlines(after).decode("utf-8")
            left = function_digests(old)["functions"]
            right = function_digests(new)["functions"]
        except (UnicodeError, SyntaxError, ValueError):
            continue
        if not relative.startswith(".flowguard/"):
            implemented.extend(relative + ":" + name for name in sorted(left.keys() | right.keys())
                               if left.get(name) != right.get(name))
        if correction:
            old_lines, new_lines = old.splitlines(), new.splitlines()
            for operation, first, last, start, end in SequenceMatcher(None, old_lines, new_lines).get_opcodes():
                if operation != "equal":
                    corrections.append(dict(path=relative, old="\n".join(old_lines[first:last]),
                                            new="\n".join(new_lines[start:end])))
    return implemented, corrections, "Implementation provenance lists changed Python function definitions from the Git diff."


def prepare_change(root, *, goal, links, base, inputs, merged, model_bytes, deleted, checked,
                   changed_paths=None, owner_block=""):
    """Prepare a final immutable pair and the exact checked post-promotion view."""
    root = Path(root).resolve()
    prepare_directory(root, CHANGE_DIR, (".json", ".msg"))
    guard = (CHANGE_DIR / ".gitattributes").as_posix()
    guard_hash = sha256_bytes((root / guard).read_bytes())
    view = {path: digest for path, digest in inputs.items()
            if not path.startswith((".flowguard/target/", ".flowguard/cache/", ".git/"))}
    map_bytes = (json.dumps(merged, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    view[".flowguard/map.json"] = sha256_bytes(map_bytes)
    view[guard] = guard_hash
    for name, raw in model_bytes.items():
        view[".flowguard/models/" + name] = sha256_bytes(raw)
    for path in deleted:
        view.pop(path, None)
    tree = sha256_bytes(json.dumps(sorted(view.items()), ensure_ascii=False,
                                  separators=(",", ":")).encode("utf-8"))
    now = datetime.now(timezone.utc)
    identifier = now.strftime("%Y%m%d-%H%M-") + tree[:6]
    implemented, corrections, provenance = _diff_provenance(root, base, inputs, changed_paths)
    record = dict(kind="change", goal=goal, requests=links, base=base.get("git"), tree=tree,
                  promoted=now.isoformat(), plan=[], rules=[], acceptances=[], existing_cleared=[],
                  implemented_by=implemented, new_actions=[], corrections=corrections,
                  checked=checked + " " + provenance +
                  " PLAN lines, rule provenance, acceptances, existing-item clearance and new-action judgments are not assessed by this record producer; their lists are empty.")
    raw = (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    message = (goal + "\n\n" + record["checked"] +
               ("\n\n" + owner_block if owner_block else "") + "\n").encode("utf-8")
    validate_new_files(root, (CHANGE_DIR / (identifier + ".msg"), CHANGE_DIR / (identifier + ".json")))
    return dict(id=identifier, record=record, json=raw, msg=message, map_bytes=map_bytes,
                guard_path=guard, guard_sha256=guard_hash)


def publish_change(root, prepared):
    """Publish JSON last; a failed new pair never becomes a successful record."""
    created = []
    try:
        for extension in ("msg", "json"):
            write_once(root, CHANGE_DIR / (prepared["id"] + "." + extension),
                       prepared[extension], _created=created)
    except (OSError, MapError):
        for path in reversed(created):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass  # An incomplete pair remains an explicit record_edited finding.
        raise


def _record_identifiers(root):
    paths = {path for pattern in ("*.json", "*.msg") for path in (root / CHANGE_DIR).glob(pattern)}
    paths.update(Path(path) for path in protected_paths(root, CHANGE_DIR)
                 if Path(path).suffix in {".json", ".msg"})
    return sorted({path.stem for path in paths})


def _change_record(root, identifier):
    if not re.fullmatch(r"[0-9]{8}-[0-9]{4}-[0-9a-f]{6}", identifier):
        raise ValueError("invalid change record name")
    for extension in ("msg", "json"):
        problem = integrity_problem(root, CHANGE_DIR / (identifier + "." + extension))
        if problem:
            raise ValueError(problem)
    item = json.loads((root / CHANGE_DIR / (identifier + ".json")).read_bytes())
    if (not isinstance(item, dict) or item.get("kind") != "change"
            or not isinstance(item.get("goal"), str) or not item["goal"].strip()
            or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("tree", "")))
            or "base" not in item
            or item.get("base") is not None and not isinstance(item["base"], str)
            or not isinstance(item.get("checked"), str) or not item["checked"].strip()
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


def change_records(root):
    """Read only complete, schema-valid, byte-protected successful records."""
    root = Path(root).resolve()
    records = []
    for identifier in _record_identifiers(root):
        try:
            records.append((identifier, _change_record(root, identifier)))
        except (OSError, ValueError, KeyError, TypeError, OverflowError):
            continue
    return records


def since_release(root, records, read_git_paths):
    """Derive records and unrecorded code commits from a reachable version tag."""
    from .common import SOURCE_EXTS

    result = _git(root, 'describe', '--tags', '--abbrev=0', '--match', 'v[0-9]*', '--match', '[0-9]*')
    tag = result.stdout.decode().strip() if result is not None and result.returncode == 0 else None
    if not tag or not re.fullmatch(r'v?[0-9]+\.[0-9]+\.[0-9]+', tag):
        return {'release': None, 'known_from': 'unknown: no reachable version release tag; no legacy release snapshot is stored',
                'changes': None, 'code_commits_without_record': None, 'released_requests': None}
    prior = read_git_paths(root, 'ls-tree', '-r', '--name-only', '-z', tag, '--',
                           '.flowguard/changes', '.flowguard/requests')
    covered = {Path(path).stem for path in prior if path.startswith('.flowguard/changes/') and path.endswith('.json')}
    requests = sorted(Path(path).stem for path in prior
                      if path.startswith('.flowguard/requests/') and path.endswith('.json'))
    changes = [dict(id=identifier, goal=record['goal'], requests=record['requests'], promoted=record['promoted'])
               for identifier, record in records if identifier not in covered]
    commits = _git(root, 'log', '--format=%H %P', tag + '..HEAD')
    unrecorded = []
    for line in commits.stdout.decode().splitlines() if commits is not None and commits.returncode == 0 else ():
        commit, *parents = line.split()
        comparison = (parents[0], commit) if parents else (commit,)
        paths = read_git_paths(root, 'diff-tree', '--root', '--no-commit-id', '--name-only',
                               '--relative', '-r', '-z', *comparison, '--', '.')
        code = [path for path in paths if Path(path).suffix in SOURCE_EXTS and not path.startswith('.flowguard/')]
        added = read_git_paths(root, 'diff-tree', '--root', '--no-commit-id', '--name-only',
                               '--relative', '--diff-filter=A', '-r', '-z', *comparison, '--', '.flowguard/changes')
        if code and not any(path.endswith('.json') and Path(path).stem in {identifier for identifier, _ in records}
                            for path in added):
            unrecorded.append(dict(commit=commit, paths=code))
    return {'release': tag, 'known_from': f'release tag {tag}, current records and Git history (each commit against its first parent)',
            'changes': changes, 'code_commits_without_record': unrecorded, 'released_requests': requests}


def record_findings(root):
    """Fresh pair integrity; missing, orphaned and edited records remain errors."""
    import shlex

    root = Path(root).resolve()
    findings = []
    for identifier in _record_identifiers(root):
        try:
            _change_record(root, identifier)
        except (OSError, ValueError, KeyError, TypeError, OverflowError) as error:
            restore = shlex.join(["git", "-C", str(root), "checkout", "--",
                                  (CHANGE_DIR / (identifier + ".json")).as_posix(),
                                  (CHANGE_DIR / (identifier + ".msg")).as_posix()])
            findings.append(Finding("error", "record_edited", identifier,
                                    f"{root / CHANGE_DIR / identifier}: {error}; records are written once; "
                                    f"restore the original pair ({restore} when committed)"))
    return findings
