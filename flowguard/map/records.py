"""Write-once raw files and their independent first-write byte protection."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .common import sha256_bytes
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


def _written_path(root: Path, path: Path, common):
    return _written_directory(root, common) / sha256_bytes(_canonical_path(path).encode("utf-8"))


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
    written = _written_path(root, path, common)
    if path.exists() or written.exists():
        raise MapError(f"immutable file already exists or was written before: {relative}")
    if _first_blob(root, relative, common) is not None:
        raise MapError(f"immutable file was committed before: {relative}")
    return path, written


def validate_new_files(root, relative_paths):
    """Check a coupled set before writing its first file; persist no check state."""
    for path in relative_paths:
        _new_file(root, path)


def write_once(root, relative_path, raw):
    """Save exact bytes once and protect them outside editable sidecar metadata."""
    path, written = _new_file(root, relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
    written.parent.mkdir(parents=True, exist_ok=True)
    with written.open("x", encoding="ascii") as stream:
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
    written = _written_path(root, path, common)
    if written.is_file():
        expected = _receipt(written).get("sha256")
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
    receipt_directory = _written_directory(root, common)
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
