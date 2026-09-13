"""Shared filesystem-symlink capability probe for governed full validation.

Path-sensitive pytest nodes require a real filesystem symlink (and, on
Windows, a reparse point).  Keeping the probe in a small dependency-free
module lets the pytest child use one definition at its capability boundary;
ordinary core owners do not inherit this platform qualification requirement.
"""

from __future__ import annotations

import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping


SYMLINK_CAPABILITY_BLOCKER = "SYMLINK_CAPABILITY_BLOCKED"
CAPABILITY_PATH_ESCAPE_POSIX = "path_escape.posix_symlink"
CAPABILITY_PATH_ESCAPE_WINDOWS = "path_escape.windows_reparse"
SYMLINK_CAPABILITY_IDS = (
    CAPABILITY_PATH_ESCAPE_POSIX,
    CAPABILITY_PATH_ESCAPE_WINDOWS,
)


def capability_satisfies(
    probe: Mapping[str, Any],
    required_capability: str,
) -> bool:
    """Return whether one probe explicitly satisfies a path capability.

    A missing field is deliberately not inferred from the legacy ``ok`` bit.
    This keeps a POSIX symlink observation from being reused as a Windows
    reparse qualification and makes old or synthetic payloads fail closed.
    """

    capability = str(required_capability or "").strip()
    if capability == CAPABILITY_PATH_ESCAPE_POSIX:
        return bool(probe.get("supports_posix_symlink", False))
    if capability == CAPABILITY_PATH_ESCAPE_WINDOWS:
        return bool(
            probe.get("platform") in {"win32", "cygwin", "msys"}
            and probe.get("supports_windows_reparse", False)
            and probe.get("reparse_point", False)
        )
    return False


def probe_symlink_capability() -> dict[str, Any]:
    """Return an immutable, JSON-ready observation of symlink capability.

    A successful probe must create and read a real link.  On Windows the
    created path must also carry the reparse-point attribute; text links or
    other compatibility shims are deliberately not accepted.
    """

    result: dict[str, Any] = {
        "schema_version": "flowguard.symlink_capability_probe.v1",
        "probe_kind": "real-filesystem-symlink",
        "platform": sys.platform,
        "python": sys.executable,
        "status": "blocked",
        "ok": False,
        "blocker": SYMLINK_CAPABILITY_BLOCKER,
        "reparse_point": False if os.name == "nt" else None,
        "supports_posix_symlink": False,
        "supports_windows_reparse": False,
        "qualification_scope": "blocked",
        "failure_code": "SYMLINK_CAPABILITY_PROBE_INCOMPLETE",
        "reason": "symlink capability probe did not complete",
    }
    try:
        with tempfile.TemporaryDirectory(prefix="flowguard-symlink-probe-") as raw_root:
            probe_root = Path(raw_root)
            target = probe_root / "target.txt"
            link = probe_root / "link.txt"
            target.write_text("flowguard-symlink-probe\n", encoding="utf-8")
            link.symlink_to(target, target_is_directory=False)
            is_symlink = link.is_symlink()
            attributes = getattr(
                os.stat(link, follow_symlinks=False),
                "st_file_attributes",
                0,
            )
            reparse_point = bool(
                int(attributes)
                & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
            )
            result["reparse_point"] = reparse_point
            if not is_symlink:
                result["reason"] = "created path is not recognized as a symlink"
                result["failure_code"] = "SYMLINK_NOT_RECOGNIZED"
                return result
            if os.name == "nt" and not reparse_point:
                result["reason"] = "created path is not a Windows reparse-point symlink"
                result["failure_code"] = "WINDOWS_REPARSE_POINT_MISSING"
                return result
            if link.read_text(encoding="utf-8") != target.read_text(encoding="utf-8"):
                result["reason"] = "symlink target could not be read consistently"
                result["failure_code"] = "SYMLINK_READBACK_FAILED"
                return result
            result.update(
                {
                    "status": "pass",
                    "ok": True,
                    "blocker": "",
                    "supports_posix_symlink": os.name != "nt" or is_symlink,
                    "supports_windows_reparse": os.name == "nt" and reparse_point,
                    "qualification_scope": (
                        "windows_reparse" if os.name == "nt" else "posix_symlink"
                    ),
                    "failure_code": "",
                    "reason": "real filesystem symlink capability is available",
                }
            )
            return result
    except (NotImplementedError, OSError) as exc:
        winerror = getattr(exc, "winerror", None)
        result.update(
            {
                "reason": f"{type(exc).__name__}: {exc}",
                "error_type": type(exc).__name__,
                "errno": getattr(exc, "errno", None),
                "winerror": winerror,
                "failure_code": (
                    "WINDOWS_SYMLINK_PRIVILEGE_REQUIRED"
                    if winerror == 1314 or "WinError 1314" in str(exc)
                    else "SYMLINK_CREATION_FAILED"
                ),
            }
        )
        return result


__all__ = [
    "CAPABILITY_PATH_ESCAPE_POSIX",
    "CAPABILITY_PATH_ESCAPE_WINDOWS",
    "SYMLINK_CAPABILITY_BLOCKER",
    "SYMLINK_CAPABILITY_IDS",
    "capability_satisfies",
    "probe_symlink_capability",
]
