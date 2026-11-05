"""Physical input stamps shared below native execution and job orchestration."""
from __future__ import annotations

import hashlib
import importlib.machinery
import json
import os
from pathlib import Path
import stat
from dataclasses import dataclass

from flowguard.map.common import normalize_newlines

OWNED_ENVIRONMENT = {"HOME": "native-arena-home", "TMPDIR": "native-arena-temp", "TEMP": "native-arena-temp", "TMP": "native-arena-temp",
                     "PYTHONPATH": "native-import-path", "PYTHONDONTWRITEBYTECODE": "native-no-bytecode", "PYTHONHASHSEED": "native-hash-seed"}


def environment_stamp(key):
    """Identify one inherited input without publishing its value."""
    value = os.environ.get(key)
    return {"missing": True} if value is None else {"sha256": hashlib.sha256(value.encode("utf-8", "surrogatepass")).hexdigest()}


def file_stamp(value):
    path = Path(value)
    try:
        info = path.lstat()
        row = {"mode": stat.S_IMODE(info.st_mode), "resolved": str(path.resolve())}
        if path.is_symlink():
            row["link"] = os.readlink(path)
        if path.is_file():
            raw = path.read_bytes()
            row["sha256"] = hashlib.sha256(raw).hexdigest()
            if path.suffix.lower() in {".py", ".pyi", ".js"}:
                row["source_sha256"] = hashlib.sha256(normalize_newlines(raw)).hexdigest()
        elif path.is_dir():
            row["directory"] = True
        else:
            row["opaque"] = True
        return row
    except FileNotFoundError:
        return {"missing": True}


def directory_stamp(value):
    path = Path(value)
    if not path.is_dir():
        return {"missing": True}
    return {"entries": [[item.name, "link" if item.is_symlink() else "directory" if item.is_dir() else "file",
                          stat.S_IMODE(item.lstat().st_mode), os.readlink(item) if item.is_symlink() else None]
                         for item in path.iterdir()]}


def module_lookup_stamp(directory, name):
    """Only an actual FileFinder/import probe may declare this narrower use.

    Candidate absence and package-directory identity remain real dependencies.
    No application directory listing is represented by this function.
    """
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        raise ValueError("a module lookup needs its actual leaf name")
    path = Path(directory)
    slots = [name + suffix for suffix in importlib.machinery.all_suffixes()]
    slots += [str(Path(name) / ("__init__" + suffix)) for suffix in importlib.machinery.all_suffixes()]
    return {"directory": file_stamp(path), "package": file_stamp(path / name),
            "slots": {slot: file_stamp(path / slot) for slot in slots}}


@dataclass(frozen=True)
class FootprintEvidence:
    status: str
    identity: str | None = None
    reason: str = ""


def footprint_evidence(footprint):
    """Read the existing footprint without equating missing evidence with fresh evidence."""
    if not isinstance(footprint, dict) or not footprint.get("reusable", False):
        return FootprintEvidence("unknown", reason="no reusable native input footprint")
    try:
        for key, previous in footprint.get("environment", {}).items():
            if previous.get("owned") == OWNED_ENVIRONMENT.get(key) and key in OWNED_ENVIRONMENT:
                continue  # These values are supplied by the native world recipe.
            if environment_stamp(key) != previous:
                return FootprintEvidence("stale", reason="environment input changed: " + key)
        for path, previous in footprint["files"].items():
            current = file_stamp(path)
            if current != previous:
                return FootprintEvidence("missing" if current.get("missing") else "stale", reason=path)
        for path, previous in footprint["directories"].items():
            usage = footprint.get("directory_uses", {}).get(path)
            if usage and usage.get("kind") == "module-lookup" and usage.get("lookups"):
                if any(module_lookup_stamp(path, name) != stamp for name, stamp in usage["lookups"].items()):
                    return FootprintEvidence("stale", reason=path)
            else:
                current = directory_stamp(path)
                if current != previous:
                    return FootprintEvidence("missing" if current.get("missing") else "stale", reason=path)
    except OSError as exc:
        return FootprintEvidence("unreadable", reason=str(exc))
    except (KeyError, TypeError, ValueError) as exc:
        return FootprintEvidence("unknown", reason=str(exc))
    return FootprintEvidence("current", hashlib.sha256(json.dumps(footprint, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest())


def footprint_identity(footprint):
    return footprint_evidence(footprint).identity
