"""Physical input stamps shared below native execution and job orchestration."""
from __future__ import annotations

import hashlib
import importlib.machinery
import json
import os
from pathlib import Path
import stat


def file_stamp(value):
    path = Path(value)
    try:
        info = path.lstat()
        row = {"mode": stat.S_IMODE(info.st_mode), "resolved": str(path.resolve())}
        if path.is_symlink():
            row["link"] = os.readlink(path)
        if path.is_file():
            row["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
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


def footprint_identity(footprint):
    if not footprint.get("reusable", False):
        return None
    try:
        for path, previous in footprint["files"].items():
            if file_stamp(path) != previous:
                return None
        for path, previous in footprint["directories"].items():
            usage = footprint.get("directory_uses", {}).get(path)
            if usage and usage.get("kind") == "module-lookup" and usage.get("lookups"):
                if any(module_lookup_stamp(path, name) != stamp for name, stamp in usage["lookups"].items()):
                    return None
            elif directory_stamp(path) != previous:
                return None
    except (OSError, ValueError):
        return None
    return hashlib.sha256(json.dumps(footprint, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
