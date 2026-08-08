"""Internal current-package identity lookup."""

from __future__ import annotations

from importlib import metadata


def flowguard_package_version() -> str:
    try:
        return metadata.version("flowguard")
    except metadata.PackageNotFoundError:
        return "0+local"


__all__ = ["flowguard_package_version"]
