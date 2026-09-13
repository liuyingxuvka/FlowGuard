"""Shared classification for bounded working artifacts.

The project layout, source-identity, and release owners all need the same
small answer to one question: is this path a generated/working artifact that
may remain on disk but must not become current authority?  Keeping that
classification in one dependency-free module prevents one owner from silently
including a path another owner excludes.

This module only classifies repository-relative names.  Callers that have an
on-disk path must perform their own link/reparse and containment checks before
calling it; classification never follows a path or touches the filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath


RUNTIME_CACHE_KINDS = frozenset({"python_cache", "python_bytecode"})
NON_AUTHORITY_KINDS = frozenset(
    {
        "opaque_evidence",
        "opaque_history",
        "authority_staging",
        "temporary_workspace",
        *RUNTIME_CACHE_KINDS,
    }
)

# These are deliberately exact, controlled paths.  A name merely containing
# ``tmp``, ``temp``, ``work``, or ``stage`` is not a reason to hide a source.
_WORKSPACE_PREFIX = "work/flowguard"
_FLOWGUARD_WORKSPACE_PREFIX = ".flowguard/work/flowguard"
_STAGING_PREFIX = ".flowguard/models/authority/staging"
_EVIDENCE_PREFIX = ".flowguard/evidence"
_HISTORY_PREFIX = ".flowguard/history"
_RUN_ARTIFACTS_PREFIX = ".flowguard/run_artifacts"
_BYTECODE_SUFFIXES = frozenset({".pyc", ".pyo"})
_GOVERNED_SOURCE_SUFFIXES = frozenset({".py", ".json", ".toml"})


@dataclass(frozen=True)
class RuntimeArtifactClassification:
    """The stable class of one known non-authority repository path."""

    relative_path: str
    kind: str

    @property
    def non_authority(self) -> bool:
        return self.kind in NON_AUTHORITY_KINDS

    @property
    def release_excluded(self) -> bool:
        return self.non_authority


def normalize_relative_path(value: str) -> str:
    """Normalize a repository-relative path and reject unsafe spellings.

    The function intentionally does not resolve a filesystem path.  A caller
    must separately inspect every physical component for a symlink/reparse
    point before using the returned value for classification or consumption.
    """

    raw = str(value or "").strip()
    posix = PurePosixPath(raw.replace("\\", "/"))
    windows = PureWindowsPath(raw)
    if (
        not raw
        or raw.startswith(("/", "\\"))
        or posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or "." in posix.parts
        or ".." in posix.parts
    ):
        raise ValueError(f"path must be a safe repository-relative name: {value!r}")
    return posix.as_posix()


def _has_prefix(relative: str, prefix: str) -> bool:
    return relative == prefix or relative.startswith(prefix + "/")


def classify_runtime_artifact(
    relative: str,
) -> RuntimeArtifactClassification | None:
    """Classify one safe repository-relative working/artifact path.

    The order is intentional: evidence/history remain opaque even if a
    generated-looking child appears inside them, and the explicit staging and
    workspace roots are recognized before generic Python cache rules.
    """

    normalized = normalize_relative_path(relative)
    if _has_prefix(normalized, _EVIDENCE_PREFIX):
        kind = "opaque_evidence"
    elif _has_prefix(normalized, _HISTORY_PREFIX):
        kind = "opaque_history"
    elif _has_prefix(normalized, _STAGING_PREFIX):
        kind = "authority_staging"
    elif _has_prefix(normalized, _WORKSPACE_PREFIX) or _has_prefix(
        normalized, _FLOWGUARD_WORKSPACE_PREFIX
    ) or _has_prefix(normalized, _RUN_ARTIFACTS_PREFIX):
        kind = "temporary_workspace"
    elif "__pycache__" in PurePosixPath(normalized).parts:
        kind = "python_cache"
    elif PurePosixPath(normalized).suffix.casefold() in _BYTECODE_SUFFIXES:
        kind = "python_bytecode"
    else:
        return None
    return RuntimeArtifactClassification(relative_path=normalized, kind=kind)


def is_non_authority_path(relative: str) -> bool:
    """Return whether a safe path is known working/non-authority material."""

    classification = classify_runtime_artifact(relative)
    return classification is not None and classification.non_authority


def is_governed_source_in_runtime_cache(relative: str) -> bool:
    """Return whether a cache path contains a source-like governed file.

    A generated cache may be excluded, but a ``.py``, ``.json``, or ``.toml``
    file inside it cannot be hidden by the cache directory name.  The caller
    should report this as a blocking governance finding after physical path
    safety has been checked.
    """

    classification = classify_runtime_artifact(relative)
    if classification is None or classification.kind != "python_cache":
        return False
    return PurePosixPath(classification.relative_path).suffix.casefold() in (
        _GOVERNED_SOURCE_SUFFIXES
    )


def is_release_excluded_path(relative: str) -> bool:
    """Return whether a path must be absent from a consumer/release projection."""

    classification = classify_runtime_artifact(relative)
    return classification is not None and classification.release_excluded


__all__ = [
    "NON_AUTHORITY_KINDS",
    "RUNTIME_CACHE_KINDS",
    "RuntimeArtifactClassification",
    "classify_runtime_artifact",
    "is_governed_source_in_runtime_cache",
    "is_non_authority_path",
    "is_release_excluded_path",
    "normalize_relative_path",
]
