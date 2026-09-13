"""Stable repository-source identity across equivalent text checkouts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from pathlib import PurePosixPath
import re
import tomllib
from typing import Any, Mapping

from .runtime_artifacts import classify_runtime_artifact


CANONICAL_TEXT_SUFFIXES = frozenset(
    {
        ".json",
        ".md",
        ".py",
        ".toml",
        ".txt",
        ".yaml",
        ".yml",
    }
)

_PROJECT_MANIFEST_AUDIT_FIELDS = frozenset(
    {"last_verified_at", "last_verified_by"}
)
_EXECUTION_POLICY_TABLE = "flowguard_execution"
_REGRESSION_MANIFEST_PATH = ".flowguard/models/regression-manifest.json"


def _normalize_openspec_task_body(text: str) -> str:
    """Ignore only Markdown checkbox progress outside fenced code."""

    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines(keepends=True)
    normalized: list[str] = []
    fence_char = ""
    fence_length = 0
    for line in lines:
        stripped = line.lstrip(" ")
        if fence_char:
            normalized.append(line)
            if stripped.startswith(fence_char * fence_length):
                closing = stripped[: len(stripped) - len(stripped.lstrip(fence_char))]
                if len(closing) >= fence_length:
                    fence_char = ""
                    fence_length = 0
            continue
        if stripped.startswith(("```", "~~~")):
            char = stripped[0]
            run = len(stripped) - len(stripped.lstrip(char))
            if run >= 3:
                fence_char = char
                fence_length = run
            normalized.append(line)
            continue
        normalized.append(
            re.sub(r"^(\s*(?:[-+*]|\d+[.)])\s+)\[[xX ]\]", r"\1[ ]", line)
        )
    return "".join(normalized)


def _functional_project_manifest_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result.pop("model_authority", None)
    result.pop(_EXECUTION_POLICY_TABLE, None)
    flowguard = result.get("flowguard")
    if isinstance(flowguard, Mapping):
        result["flowguard"] = {
            key: value
            for key, value in flowguard.items()
            if key not in _PROJECT_MANIFEST_AUDIT_FIELDS
        }
    return result


def _functional_regression_manifest_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    models = result.get("models")
    if isinstance(models, list):
        normalized_models: list[Any] = []
        for item in models:
            if isinstance(item, Mapping):
                entry = dict(item)
                entry.pop("timeout_seconds", None)
                normalized_models.append(entry)
            else:
                normalized_models.append(item)
        result["models"] = normalized_models
    return result


def functional_source_payload(root: str | Path, relative_path: str) -> Any:
    """Return the one canonical functional projection for one source path.

    Raw ``source_file_fingerprint`` remains the integrity identity.  This
    helper is only for current functional-input joins, where control-plane
    pointers, audit display fields, task checkboxes, and supervisor budgets
    must not reopen a settled functional owner.
    """

    normalized = str(relative_path or "").replace("\\", "/")
    if not normalized or PurePosixPath(normalized).is_absolute() or ".." in PurePosixPath(normalized).parts:
        raise ValueError(f"functional source path must be repository-relative: {relative_path!r}")
    normalized = assert_current_source_path(normalized)
    path = Path(root).resolve() / normalized
    if not path.is_file():
        raise ValueError(f"functional source path is missing: {normalized}")
    if normalized == ".flowguard/project.toml":
        try:
            payload = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
            raise ValueError(f"cannot parse project manifest: {path}") from exc
        if not isinstance(payload, Mapping):
            raise ValueError("project manifest must be a TOML mapping")
        return _functional_project_manifest_payload(payload)
    if normalized == _REGRESSION_MANIFEST_PATH:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot parse model regression manifest: {path}") from exc
        if not isinstance(payload, Mapping):
            raise ValueError("model regression manifest must be an object")
        return _functional_regression_manifest_payload(payload)
    if normalized.startswith("openspec/changes/") and normalized.endswith("/tasks.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ValueError(f"cannot read OpenSpec task body: {path}") from exc
        return _normalize_openspec_task_body(text)
    return canonical_source_bytes(path)


def functional_source_fingerprint(root: str | Path, relative_path: str) -> str:
    """Hash the canonical functional projection for one repository-relative file."""

    payload = functional_source_payload(root, relative_path)
    if isinstance(payload, bytes):
        encoded = payload
    elif isinstance(payload, str):
        encoded = payload.encode("utf-8")
    else:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def canonical_source_bytes(path: str | Path) -> bytes:
    """Normalize text newlines while preserving non-text inputs byte-for-byte."""

    source = Path(path)
    payload = source.read_bytes()
    if source.suffix.casefold() not in CANONICAL_TEXT_SUFFIXES:
        return payload
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return payload
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def assert_current_source_path(relative: str) -> str:
    """Reject known working/non-authority paths before source fingerprinting.

    This is the source-identity boundary, not a cleanup policy.  The caller
    remains free to keep the bytes in its controlled work area; it simply may
    not promote those bytes into a current source identity.
    """

    normalized = str(relative or "").replace("\\", "/")
    try:
        classification = classify_runtime_artifact(normalized)
    except ValueError as exc:
        raise ValueError(f"unsafe current source path: {relative!r}") from exc
    if classification is None and not normalized.startswith(".flowguard/"):
        # Authority records in older typed inputs may omit the explicit
        # control-plane prefix.  Resolve that spelling against the same
        # canonical runtime boundary so staging/cache bytes cannot acquire a
        # source identity merely through path shorthand.
        try:
            classification = classify_runtime_artifact(
                f".flowguard/{normalized}"
            )
        except ValueError as exc:
            raise ValueError(f"unsafe current source path: {relative!r}") from exc
    if classification is not None:
        raise ValueError(
            "working/non-authority path cannot become a current source identity: "
            f"{classification.relative_path} ({classification.kind})"
        )
    return classification.relative_path if classification else normalized


def source_file_fingerprint(path: str | Path) -> str:
    return f"sha256:{hashlib.sha256(canonical_source_bytes(path)).hexdigest()}"


__all__ = [
    "CANONICAL_TEXT_SUFFIXES",
    "assert_current_source_path",
    "canonical_source_bytes",
    "functional_source_fingerprint",
    "functional_source_payload",
    "source_file_fingerprint",
]
