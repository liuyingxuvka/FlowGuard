"""Content-addressed execution ownership for FlowGuard validation.

The module is deliberately independent from OpenSpec providers.  It freezes
native FlowGuard owner inputs, verifies immutable receipts against a freshly
derived current context, and exposes only three execution dispositions:
``execute``, ``reuse_current``, or ``blocked``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
<<<<<<< HEAD
import platform
=======
>>>>>>> agent/harden-currentness-validation
import re
import subprocess
import tempfile
import time
import tomllib
from typing import Any, Iterable, Mapping, Sequence

from ._hashing import sha256_bytes as _sha256_bytes
from .evidence_receipts import (
    ChildReceiptRequirement,
    ConsumedChildReceipt,
    EvidenceReceipt,
    InputSnapshot,
    RECEIPT_STATUS_PASS,
    ReceiptVerificationContext,
    ReceiptVerificationResult,
    build_environment_fingerprint,
    fingerprint_value,
    list_evidence_receipts,
    load_evidence_receipt,
    save_evidence_receipt,
    snapshot_bytes,
    tokenize_command,
    verify_evidence_receipt,
)
from .source_identity import source_file_fingerprint
from .validation_results import ValidationChildResult


OWNER_EXECUTE = "execute"
OWNER_REUSE_CURRENT = "reuse_current"
OWNER_BLOCKED = "blocked"
OWNER_DISPOSITIONS = (OWNER_EXECUTE, OWNER_REUSE_CURRENT, OWNER_BLOCKED)
OWNER_RECEIPT_SCOPE = "full"
OWNER_RECEIPT_KIND = "validation_owner"
OWNER_RECEIPT_SCHEMA = "flowguard.validation_owner_receipt.v2"
PARENT_CURRENT_SCHEMA = "flowguard.validation_parent_current.v1"
OWNER_PLAN_SCHEMA = "flowguard.validation_owner_plan.v1"
DEFAULT_TERMINATION_POLICY = "terminate_grace_force_kill_confirm_zero_descendants"

_OUTPUT_PREFIXES = (
    ".flowguard/evidence/",
    ".flowguard/model-mesh/snapshots/",
    ".flowguard/model-system/store/",
    "tmp/",
)
_OUTPUT_SUFFIXES = (
    "/verification-report.json",
    "/result.json",
    "/CURRENT.json",
    ".pyc",
)
_OUTPUT_BASENAMES = {
    ".DS_Store",
    "adoption_log.jsonl",
    "skillguard_progress_ledger.jsonl",
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _content_addressed_receipt_id(prefix: str, receipt: EvidenceReceipt) -> str:
    payload = receipt.to_dict()
    payload["receipt_id"] = "<CONTENT_ADDRESS>"
    digest = fingerprint_value(payload).split(":", 1)[1]
    return f"{prefix}:{digest[:32]}"


def assert_validation_owner_receipt_integrity(
    receipt: EvidenceReceipt,
) -> None:
    """Reject a validation-owner receipt whose id is not its exact content address."""

    expected = _content_addressed_receipt_id(
        f"receipt:validation-owner:{receipt.subject_id.removeprefix('validation-owner:')}",
        receipt,
    )
    if receipt.receipt_id != expected:
        raise ValueError(
            f"validation owner receipt content address mismatch: {receipt.receipt_id}"
        )


def _assert_owner_receipt_integrity(receipt: EvidenceReceipt) -> None:
    """Internal spelling retained for existing validation-owner consumers."""

    assert_validation_owner_receipt_integrity(receipt)


def _package_version() -> str:
    try:
        return importlib.metadata.version("flowguard")
    except importlib.metadata.PackageNotFoundError:
        return "source"


def _receipt_result_status(status: str) -> str:
    return {
        "pass": "pass",
        "fail": "fail",
        "blocked": "blocked",
        "partial": "scoped",
        "invalid_input": "error",
        "timeout": "error",
        "cancelled": "error",
        "internal_error": "error",
    }.get(status, "error")


def _is_evidence_output(relative: str) -> bool:
    normalized = relative.replace("\\", "/")
    if any(normalized.startswith(prefix) for prefix in _OUTPUT_PREFIXES):
        return True
    if any(normalized.endswith(suffix) for suffix in _OUTPUT_SUFFIXES):
        return True
    if Path(normalized).name in _OUTPUT_BASENAMES:
        return True
    if "/__pycache__/" in f"/{normalized}/":
        return True
    if "/reports/current_" in normalized or "/ai_judgments/current_" in normalized:
        return True
    return False


def _glob_pattern_variants(
    pattern: str,
    *,
    max_depth: int,
) -> tuple[str, ...]:
    """Return Path.glob-compatible recursive variants for candidate matching."""

    pending = [str(pattern).replace("\\", "/")]
    variants: set[str] = set()
    while pending:
        current = pending.pop()
        if current in variants:
            continue
        variants.add(current)
        marker = current.find("**/")
        if marker >= 0:
            prefix = current[:marker]
            suffix = current[marker + 3 :]
            pending.extend(
                prefix + ("*/" * depth) + suffix
                for depth in range(max_depth + 1)
            )
    return tuple(sorted(variants))


def _matches_declared_pattern(relative: str, pattern: str) -> bool:
<<<<<<< HEAD
    # ``PurePath.match`` right-anchors relative patterns, which would make
    # ``flowguard/**/*.py`` also match ``.agents/skills/flowguard/x.py``.
    # Validation manifests are repository-root relative, so anchor both sides
    # under a synthetic root before applying the expanded recursive variants.
    candidate = PurePosixPath("/__flowguard_manifest_root__") / relative
    return any(
        candidate.match(f"/__flowguard_manifest_root__/{variant}")
=======
    candidate = PurePosixPath(relative)
    return any(
        candidate.match(variant)
>>>>>>> agent/harden-currentness-validation
        for variant in _glob_pattern_variants(
            pattern,
            max_depth=len(candidate.parts),
        )
    )


def _git_candidate_paths(root: Path) -> tuple[str, ...] | None:
    """List tracked and non-ignored untracked candidates without walking ignored stores."""

    try:
        raw = _git_bytes(
            root,
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        )
    except ValueError:
        return None
    return tuple(
        sorted(
            {
                item.decode("utf-8").replace("\\", "/")
                for item in raw.split(b"\0")
                if item
            }
        )
    )


def resolve_input_manifest(
    root: str | Path,
    patterns: Sequence[str],
) -> tuple[dict[str, str], ...]:
    """Resolve declared patterns to a deterministic content manifest."""

    root_path = Path(root).resolve()
    rows: dict[str, str] = {}
    unique_patterns = tuple(
        dict.fromkeys(str(item) for item in patterns if str(item))
    )
    candidates = _git_candidate_paths(root_path)
    if candidates is not None:
<<<<<<< HEAD
        candidate_set = set(candidates)
        literal_patterns = tuple(
            pattern
            for pattern in unique_patterns
            if not any(token in pattern for token in ("*", "?", "["))
        )
        wildcard_patterns = tuple(
            pattern for pattern in unique_patterns if pattern not in literal_patterns
        )
        selected = {
            pattern.replace("\\", "/")
            for pattern in literal_patterns
            if pattern.replace("\\", "/") in candidate_set
        }
        if wildcard_patterns:
            selected.update(
                relative
                for relative in candidates
                if any(
                    _matches_declared_pattern(relative, pattern)
                    for pattern in wildcard_patterns
                )
            )
        for relative in sorted(selected):
            if _is_evidence_output(relative):
=======
        for relative in candidates:
            if _is_evidence_output(relative) or not any(
                _matches_declared_pattern(relative, pattern)
                for pattern in unique_patterns
            ):
>>>>>>> agent/harden-currentness-validation
                continue
            path = root_path / relative
            if path.is_file():
                rows[relative] = source_file_fingerprint(path)
        return tuple(
            {"path": path, "sha256": rows[path]}
            for path in sorted(rows)
        )

    for pattern in unique_patterns:
        for path in root_path.glob(pattern):
            if not path.is_file():
                continue
            resolved = path.resolve()
            try:
                relative = resolved.relative_to(root_path).as_posix()
            except ValueError as exc:
                raise ValueError(
                    f"validation input escapes repository: {path}"
                ) from exc
            if not _is_evidence_output(relative):
                rows[relative] = source_file_fingerprint(resolved)
    return tuple({"path": path, "sha256": rows[path]} for path in sorted(rows))


def filter_resolved_input_manifest(
    manifest: Sequence[Mapping[str, str]],
    patterns: Sequence[str],
) -> tuple[dict[str, str], ...]:
    """Filter one resolved repository manifest with canonical match semantics.

    The function performs no filesystem or Git access.  It is strictly an
    invocation-local projection of a current observation, not a cache or a
    validation result that can be reused by another invocation.
    """

    unique_patterns = tuple(
        dict.fromkeys(str(item) for item in patterns if str(item))
    )
    manifest_by_path: dict[str, str] = {}
    for item in manifest:
        relative = str(item.get("path", "")).replace("\\", "/")
        fingerprint = str(item.get("sha256", ""))
        if not relative or not fingerprint:
            raise ValueError("resolved input manifest row is incomplete")
        if relative in manifest_by_path and manifest_by_path[relative] != fingerprint:
            raise ValueError("resolved input manifest contains conflicting rows")
        manifest_by_path[relative] = fingerprint
    literal_patterns = tuple(
        pattern.replace("\\", "/")
        for pattern in unique_patterns
        if not any(token in pattern for token in ("*", "?", "["))
    )
    wildcard_patterns = tuple(
        pattern
        for pattern in unique_patterns
        if any(token in pattern for token in ("*", "?", "["))
    )
    rows = {
        relative: manifest_by_path[relative]
        for relative in literal_patterns
        if relative in manifest_by_path
    }
    if wildcard_patterns:
        for relative, fingerprint in manifest_by_path.items():
            if any(
                _matches_declared_pattern(relative, pattern)
                for pattern in wildcard_patterns
            ):
                rows[relative] = fingerprint
    return tuple(
        {"path": relative, "sha256": rows[relative]}
        for relative in sorted(rows)
    )


def validation_input_manifest(root: str | Path) -> tuple[dict[str, str], ...]:
    """Return validation-governed inputs, excluding runtime evidence output."""

    patterns = (
        "flowguard/**/*",
        "scripts/**/*",
        "tests/**/*",
        "docs/**/*",
        "openspec/**/*",
        ".agents/skills/**/*",
        ".skillguard/**/*",
        ".flowguard/**/*",
        "pyproject.toml",
        "README.md",
        "CHANGELOG.md",
        "ROADMAP.md",
        "AGENTS.md",
        "LICENSE",
    )
    rows = list(resolve_input_manifest(root, patterns))
    rows = [
        row
        for row in rows
        if not (
            row["path"].startswith("openspec/changes/")
            and (
                row["path"].endswith("/tasks.md")
                or row["path"].endswith("/verification-report.json")
            )
        )
    ]
    return tuple(rows)


def governed_source_manifest(root: str | Path) -> tuple[dict[str, str], ...]:
    """Deprecated-name-free internal alias for the validation input manifest."""

    return validation_input_manifest(root)


def _git_bytes(root: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=root,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"git {' '.join(arguments)} failed: {message}")
    return completed.stdout


def _git_blob_id(data: bytes, object_format: str) -> str:
    payload = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    if object_format == "sha256":
        return hashlib.sha256(payload).hexdigest()
    if object_format == "sha1":
        return hashlib.sha1(payload).hexdigest()
    raise ValueError(f"unsupported Git object format: {object_format}")


def _git_worktree_blob_id(
    root: Path,
    relative: str,
    *,
    mode: str,
    object_format: str,
) -> str:
    """Hash prospective content with the same clean filters Git will commit."""

    path = root / relative
    if mode == "120000":
        return _git_blob_id(
            os.readlink(path).encode("utf-8"),
            object_format,
        )
    return _git_bytes(
        root,
        "hash-object",
        f"--path={relative}",
        "--",
        relative,
    ).decode("ascii").strip()


def model_authority_release_paths(root: Path) -> tuple[str, ...]:
    """Return the public files needed to replay the current authority head."""

    manifest_path = root / ".flowguard" / "project.toml"
    if not manifest_path.is_file():
        return ()
    with manifest_path.open("rb") as handle:
        manifest = tomllib.load(handle)
    authority = manifest.get("model_authority")
    if authority is None:
        return ()
    if not isinstance(authority, Mapping):
        raise ValueError("model_authority must be a TOML table")

    observed_fingerprint = str(
        authority.get("observed_snapshot_fingerprint", "")
    )
    observed_path = str(authority.get("observed_snapshot_path", "")).replace(
        "\\", "/"
    )
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", observed_fingerprint):
        raise ValueError("model authority observed snapshot fingerprint is invalid")
    observed_digest = observed_fingerprint.split(":", 1)[1]
    expected_observed_path = (
        f".flowguard/model-mesh/snapshots/{observed_digest}.json"
    )
    if observed_path != expected_observed_path:
        raise ValueError(
            "model authority observed snapshot path is not content addressed"
        )

    try:
        generation = int(authority.get("generation", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("model authority generation is invalid") from exc
    accepted = str(
        authority.get("accepted_revision_set_fingerprint", "")
    )
    activation = str(
        authority.get("activation_receipt_fingerprint", "")
    )
    previous = str(authority.get("previous_snapshot_fingerprint", ""))
    for field_name, value in (
        ("accepted revision", accepted),
        ("activation receipt", activation),
    ):
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
            raise ValueError(f"model authority {field_name} fingerprint is invalid")
    if previous and not re.fullmatch(r"sha256:[0-9a-f]{64}", previous):
        raise ValueError("model authority previous snapshot fingerprint is invalid")

    snapshot_file = root / expected_observed_path
    try:
        snapshot_payload = json.loads(snapshot_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("model authority observed snapshot is unreadable") from exc
    if not isinstance(snapshot_payload, Mapping):
        raise ValueError("model authority observed snapshot must be a JSON object")
    model_instances = snapshot_payload.get("model_instances")
    if not isinstance(model_instances, list):
        raise ValueError(
            "model authority observed snapshot model_instances must be an array"
        )

    paths = [expected_observed_path]
    for model_index, model_instance in enumerate(model_instances):
        if not isinstance(model_instance, Mapping):
            raise ValueError(
                f"model authority model_instances[{model_index}] must be an object"
            )
        inputs = model_instance.get("inputs")
        if not isinstance(inputs, list):
            raise ValueError(
                "model authority input inventory must be an array: "
                f"model_instances[{model_index}]"
            )
        for input_index, input_row in enumerate(inputs):
            if not isinstance(input_row, Mapping):
                raise ValueError(
                    "model authority input row must be an object: "
                    f"model_instances[{model_index}].inputs[{input_index}]"
                )
            relative = str(input_row.get("path", "")).replace("\\", "/")
            relative_path = Path(relative)
            if (
                not relative
                or relative_path.is_absolute()
                or ".." in relative_path.parts
            ):
                raise ValueError(
                    "model authority input path is invalid: "
                    f"model_instances[{model_index}].inputs[{input_index}]"
                )
            paths.append(relative)
    if previous:
        paths.append(
            ".flowguard/model-mesh/snapshots/"
            + previous.split(":", 1)[1]
            + ".json"
        )
    if generation == 1:
        if accepted != activation:
            raise ValueError(
                "bootstrap model authority must bind one bootstrap fingerprint"
            )
        paths.append(
            ".flowguard/model-mesh/bootstraps/"
            + accepted.split(":", 1)[1]
            + ".json"
        )
    elif generation > 1:
        paths.extend(
            (
                ".flowguard/model-mesh/revisions/"
                + accepted.split(":", 1)[1]
                + ".json",
                ".flowguard/model-mesh/activations/"
                + activation.split(":", 1)[1]
                + ".json",
            )
        )
    else:
        raise ValueError("model authority generation must be positive")
    return tuple(dict.fromkeys(paths))


def release_tree_manifest(
    root: str | Path,
    *,
    revision: str | None = None,
) -> tuple[dict[str, str], ...]:
    """Return exact prospective-worktree or committed Git tree identities."""

    root_path = Path(root).resolve()
    if revision is not None:
        raw = _git_bytes(
            root_path,
            "ls-tree",
            "-r",
            "-z",
            "--full-tree",
            revision,
        )
        rows: list[dict[str, str]] = []
        for item in raw.split(b"\0"):
            if not item:
                continue
            header, encoded_path = item.split(b"\t", 1)
            mode, object_type, object_id = header.decode("ascii").split()
            if object_type not in {"blob", "commit"}:
                raise ValueError(
                    f"unsupported Git tree object type: {object_type}"
                )
            rows.append(
                {
                    "path": encoded_path.decode("utf-8"),
                    "mode": mode,
                    "blob_id": object_id,
                }
            )
        return tuple(sorted(rows, key=lambda item: item["path"]))

    object_format = _git_bytes(
        root_path,
        "rev-parse",
        "--show-object-format",
    ).decode("ascii").strip()
    index_rows: dict[str, tuple[str, str]] = {}
    for item in _git_bytes(root_path, "ls-files", "--stage", "-z").split(b"\0"):
        if not item:
            continue
        header, encoded_path = item.split(b"\t", 1)
        mode, object_id, stage = header.decode("ascii").split()
        path = encoded_path.decode("utf-8")
        if stage != "0":
            raise ValueError(f"release tree has an unresolved index stage: {path}")
        index_rows[path] = (mode, object_id)
    worktree_changed_paths = {
        item.decode("utf-8")
        for item in _git_bytes(
            root_path,
            "diff-files",
            "--name-only",
            "-z",
        ).split(b"\0")
        if item
    }
    required_authority_paths = model_authority_release_paths(root_path)
    missing_authority_paths = tuple(
        path for path in required_authority_paths if path not in index_rows
    )
    if missing_authority_paths:
        raise ValueError(
            "required public model authority paths are not tracked: "
            + ", ".join(missing_authority_paths)
        )
    candidates = tuple(
        item.decode("utf-8")
        for item in _git_bytes(
            root_path,
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ).split(b"\0")
        if item
    )
    rows = []
    for relative in sorted(set(candidates)):
        if relative not in index_rows and _is_evidence_output(relative):
            continue
        path = root_path / relative
        mode, index_object_id = index_rows.get(relative, ("100644", ""))
        if mode == "160000":
            if not index_object_id:
                raise ValueError(f"untracked submodule entry is unsupported: {relative}")
            blob_id = index_object_id
        elif relative in index_rows and relative not in worktree_changed_paths:
            blob_id = index_object_id
        else:
            if not path.exists():
                raise ValueError(f"release tree path is deleted or missing: {relative}")
            if mode != "120000" and not path.is_file():
                raise ValueError(f"release tree entry is not a file: {relative}")
            blob_id = _git_worktree_blob_id(
                root_path,
                relative,
                mode=mode,
                object_format=object_format,
            )
        rows.append({"path": relative, "mode": mode, "blob_id": blob_id})
    return tuple(rows)


def manifest_fingerprint(manifest: Sequence[Mapping[str, str]]) -> str:
    return _sha256_bytes(_canonical_bytes([dict(item) for item in manifest]))


@dataclass(frozen=True)
class ValidationOwnerContract:
    owner_id: str
    command: tuple[str, ...]
    input_patterns: tuple[str, ...]
    obligation_ids: tuple[str, ...]
    projected_inputs: tuple[tuple[str, str], ...] = ()
    dependency_owner_ids: tuple[str, ...] = ()
    resource_keys: tuple[str, ...] = ()
    toolchain_selectors: tuple[str, ...] = ("python_implementation", "python_version", "flowguard_version")
    environment_selectors: tuple[str, ...] = ("platform_system", "platform_machine")
    external_component_bindings: tuple[tuple[str, str], ...] = ()
    work_context_artifact_roles: tuple[str, ...] = ()
    timeout_seconds: float = 900.0
    termination_policy: str = DEFAULT_TERMINATION_POLICY
    required: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "dependency_owner_ids",
            "resource_keys",
            "toolchain_selectors",
            "environment_selectors",
            "work_context_artifact_roles",
        ):
            values = tuple(sorted({str(item).strip() for item in getattr(self, field_name) if str(item).strip()}))
            object.__setattr__(self, field_name, values)
        external = tuple(
            sorted(
                (str(component_id).strip(), str(fingerprint).strip())
                for component_id, fingerprint in self.external_component_bindings
            )
        )
        if len({item[0] for item in external}) != len(external):
            raise ValueError("external component ids must be unique within one owner")
        if any(
            not component_id
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", fingerprint)
            for component_id, fingerprint in external
        ):
            raise ValueError(
                "external component bindings require a component id and canonical sha256 fingerprint"
            )
        object.__setattr__(self, "external_component_bindings", external)
        projected = tuple(
            sorted(
                (str(component_id), str(fingerprint))
                for component_id, fingerprint in self.projected_inputs
            )
        )
        if len({item[0] for item in projected}) != len(projected):
            raise ValueError("projected input component ids must be unique")
        if any(
            not component_id
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", fingerprint)
            for component_id, fingerprint in projected
        ):
            raise ValueError(
                "projected inputs require a component id and canonical sha256 fingerprint"
            )
        object.__setattr__(self, "projected_inputs", projected)
        object.__setattr__(self, "timeout_seconds", float(self.timeout_seconds))
        object.__setattr__(self, "termination_policy", str(self.termination_policy).strip())
        if self.owner_id in self.dependency_owner_ids:
            raise ValueError("validation owner cannot depend on itself")
        if self.timeout_seconds <= 0:
            raise ValueError("validation owner timeout must be positive")
        if not self.termination_policy:
            raise ValueError("validation owner termination policy is required")
        if (
            not self.owner_id
            or not self.command
            or (not self.input_patterns and not projected)
            or not self.obligation_ids
        ):
            raise ValueError(
                "owner id, command, input patterns or projections, and obligations are required"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner_id": self.owner_id,
            "command": list(self.command),
            "input_patterns": list(self.input_patterns),
            "obligation_ids": list(self.obligation_ids),
            "projected_inputs": [
                {
                    "component_id": component_id,
                    "fingerprint": fingerprint,
                }
                for component_id, fingerprint in self.projected_inputs
            ],
            "dependency_owner_ids": list(self.dependency_owner_ids),
            "resource_keys": list(self.resource_keys),
            "toolchain_selectors": list(self.toolchain_selectors),
            "environment_selectors": list(self.environment_selectors),
            "external_component_bindings": [
                {
                    "component_id": component_id,
                    "fingerprint": fingerprint,
                }
                for component_id, fingerprint in self.external_component_bindings
            ],
            "work_context_artifact_roles": list(self.work_context_artifact_roles),
            "timeout_seconds": self.timeout_seconds,
            "termination_policy": self.termination_policy,
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ValidationOwnerContract":
        return cls(
            owner_id=str(value.get("owner_id", "")),
            command=tuple(str(item) for item in value.get("command", ())),
            input_patterns=tuple(str(item) for item in value.get("input_patterns", ())),
            obligation_ids=tuple(str(item) for item in value.get("obligation_ids", ())),
            projected_inputs=tuple(
                (
                    str(item.get("component_id", "")),
                    str(item.get("fingerprint", "")),
                )
                for item in value.get("projected_inputs", ())
                if isinstance(item, Mapping)
            ),
            dependency_owner_ids=tuple(
                str(item) for item in value.get("dependency_owner_ids", ())
            ),
            resource_keys=tuple(str(item) for item in value.get("resource_keys", ())),
            toolchain_selectors=tuple(
                str(item) for item in value.get(
                    "toolchain_selectors",
                    ("python_implementation", "python_version", "flowguard_version"),
                )
            ),
            environment_selectors=tuple(
                str(item) for item in value.get(
                    "environment_selectors",
                    ("platform_system", "platform_machine"),
                )
            ),
            external_component_bindings=tuple(
                (
                    str(item.get("component_id", "")),
                    str(item.get("fingerprint", "")),
                )
                for item in value.get("external_component_bindings", ())
                if isinstance(item, Mapping)
            ),
            work_context_artifact_roles=tuple(
                str(item) for item in value.get("work_context_artifact_roles", ())
            ),
            timeout_seconds=float(value.get("timeout_seconds", 900.0)),
            termination_policy=str(
                value.get("termination_policy", DEFAULT_TERMINATION_POLICY)
            ),
            required=bool(value.get("required", True)),
        )


@dataclass(frozen=True)
class ValidationOwnerCurrent:
    contract: ValidationOwnerContract
    input_manifest: tuple[Mapping[str, str], ...]
    input_snapshot: InputSnapshot
    contract_hash: str
    check_manifest_hash: str
    suite_map_hash: str
    environment_metadata: Mapping[str, str]
    environment_fingerprint: str
    command: tuple[str, ...]
    owner_identity: str


@dataclass(frozen=True)
class ValidationOwnerPlanRow:
    owner_id: str
    disposition: str
    owner_identity: str
    reason: str
    receipt_id: str = ""
    receipt_fingerprint: str = ""
    findings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.disposition not in OWNER_DISPOSITIONS:
            raise ValueError(f"unsupported owner disposition: {self.disposition}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner_id": self.owner_id,
            "disposition": self.disposition,
            "owner_identity": self.owner_identity,
            "reason": self.reason,
            "receipt_id": self.receipt_id,
            "receipt_fingerprint": self.receipt_fingerprint,
            "findings": list(self.findings),
        }


@dataclass(frozen=True)
class ValidationOwnerObservation:
    """One immutable, invocation-local view of owner inputs and evidence.

    The observation is deliberately not persisted.  It lets a bounded caller
    reuse one repository scan and one canonical receipt-store read while every
    owner keeps its own contract, current identity, receipt, and native
    verification result.
    """

    contracts: tuple[ValidationOwnerContract, ...]
    repository_input_manifest: tuple[Mapping[str, str], ...]
    receipt_inventory_identities: tuple[tuple[str, str, str], ...]
    rows: tuple[ValidationOwnerPlanRow, ...]
    owner_currents: tuple[ValidationOwnerCurrent, ...]
    reusable_receipts: tuple[EvidenceReceipt, ...]
    reusable_verifications: tuple[ReceiptVerificationResult, ...]
    observation_fingerprint: str
    observation_seconds: float = 0.0

    @property
    def current_by_owner(self) -> Mapping[str, ValidationOwnerCurrent]:
        return {item.contract.owner_id: item for item in self.owner_currents}

    @property
    def receipt_by_owner(self) -> Mapping[str, EvidenceReceipt]:
        return {
            item.subject_id.removeprefix("validation-owner:"): item
            for item in self.reusable_receipts
        }

    @property
    def verification_by_owner(self) -> Mapping[str, ReceiptVerificationResult]:
        receipts = self.receipt_by_owner
        results = {item.receipt_id: item for item in self.reusable_verifications}
        return {
            owner_id: results[receipt.receipt_id]
            for owner_id, receipt in receipts.items()
        }

    @property
    def repository_input_manifest_fingerprint(self) -> str:
        return manifest_fingerprint(
            _governed_owner_input_manifest(self.owner_currents)
        )


@dataclass(frozen=True)
class ValidationObservationFreshness:
    """Visible final freshness boundary for one transient observation."""

    status: str
    initial_observation_fingerprint: str
    final_observation_fingerprint: str = ""
    findings: tuple[str, ...] = ()
    observation_seconds: float = 0.0
    owner_currents: tuple[ValidationOwnerCurrent, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == "pass" and not self.findings

    @property
    def current_by_owner(self) -> Mapping[str, ValidationOwnerCurrent]:
        return {item.contract.owner_id: item for item in self.owner_currents}

    @classmethod
    def not_run(
        cls,
        observation: ValidationOwnerObservation,
    ) -> "ValidationObservationFreshness":
        return cls(
            status="not_run",
            initial_observation_fingerprint=(
                observation.observation_fingerprint
            ),
        )


def topological_owner_contracts(
    contracts: Sequence[ValidationOwnerContract],
) -> tuple[ValidationOwnerContract, ...]:
    """Validate and deterministically order one complete owner DAG."""

    by_id = {item.owner_id: item for item in contracts}
    if len(by_id) != len(contracts):
        raise ValueError("validation owner ids must be unique")
    if any(not owner_id for owner_id in by_id):
        raise ValueError("validation owner ids must be non-empty")
    for contract in contracts:
        unknown = sorted(set(contract.dependency_owner_ids) - set(by_id))
        if unknown:
            raise ValueError(
                f"validation owner {contract.owner_id} has unknown dependencies: "
                + ", ".join(unknown)
            )

    ordered: list[ValidationOwnerContract] = []
    pending = set(by_id)
    while pending:
        ready = sorted(
            owner_id
            for owner_id in pending
            if set(by_id[owner_id].dependency_owner_ids).isdisjoint(pending)
        )
        if not ready:
            raise ValueError(
                "validation owner dependency cycle: " + ", ".join(sorted(pending))
            )
        for owner_id in ready:
            ordered.append(by_id[owner_id])
            pending.remove(owner_id)

    ancestors: dict[str, set[str]] = {}
    for contract in ordered:
        closure = set(contract.dependency_owner_ids)
        for dependency_id in contract.dependency_owner_ids:
            closure.update(ancestors[dependency_id])
        ancestors[contract.owner_id] = closure
    resource_owners: dict[str, list[str]] = {}
    for contract in ordered:
        for resource_key in contract.resource_keys:
            resource_owners.setdefault(resource_key, []).append(contract.owner_id)
    for resource_key, owner_ids in sorted(resource_owners.items()):
        for index, left in enumerate(owner_ids):
            for right in owner_ids[index + 1 :]:
                if left not in ancestors[right] and right not in ancestors[left]:
                    raise ValueError(
                        "validation resource conflict is not dependency ordered: "
                        f"{resource_key} ({left}, {right})"
                    )
    return tuple(ordered)


@dataclass(frozen=True)
class ValidationOwnerPlan:
    contracts: tuple[ValidationOwnerContract, ...]
    rows: tuple[ValidationOwnerPlanRow, ...]
    owner_currents: Mapping[str, ValidationOwnerCurrent]
    reusable_receipts: Mapping[str, EvidenceReceipt]
    validation_input_manifest: tuple[Mapping[str, str], ...]
    validation_input_manifest_fingerprint: str
    release_tree_manifest: tuple[Mapping[str, str], ...]
    release_tree_manifest_fingerprint: str
    plan_fingerprint: str

    @property
    def blocked(self) -> bool:
        return any(item.disposition == OWNER_BLOCKED for item in self.rows)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": OWNER_PLAN_SCHEMA,
            "contracts": [item.to_dict() for item in self.contracts],
            "rows": [item.to_dict() for item in self.rows],
            "owner_identities": {
                owner_id: current.owner_identity
                for owner_id, current in sorted(self.owner_currents.items())
            },
            "validation_input_manifest_fingerprint": self.validation_input_manifest_fingerprint,
            "release_tree_manifest_fingerprint": self.release_tree_manifest_fingerprint,
            "plan_fingerprint": self.plan_fingerprint,
            "blocked": self.blocked,
        }


@dataclass(frozen=True)
class ValidationParentCurrent:
    owner_plan: ValidationOwnerPlan
    validation_snapshot: InputSnapshot
    release_tree_snapshot: InputSnapshot
    contract_hash: str
    check_manifest_hash: str
    suite_map_hash: str
    environment_metadata: Mapping[str, str]
    environment_fingerprint: str
    parent_identity: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PARENT_CURRENT_SCHEMA,
            "owner_plan": self.owner_plan.to_dict(),
            "validation_snapshot": self.validation_snapshot.to_dict(),
            "release_tree_snapshot": self.release_tree_snapshot.to_dict(),
            "contract_hash": self.contract_hash,
            "check_manifest_hash": self.check_manifest_hash,
            "suite_map_hash": self.suite_map_hash,
            "environment_metadata": dict(self.environment_metadata),
            "environment_fingerprint": self.environment_fingerprint,
            "parent_identity": self.parent_identity,
        }


def build_owner_current(
    root: str | Path,
    contract: ValidationOwnerContract,
    *,
    all_contracts: Sequence[ValidationOwnerContract],
) -> ValidationOwnerCurrent:
    return _build_owner_current(
        Path(root).resolve(),
        contract,
        all_contracts=all_contracts,
        resolved_input_manifest=None,
    )


def _build_owner_current(
    root: Path,
    contract: ValidationOwnerContract,
    *,
    all_contracts: Sequence[ValidationOwnerContract],
    resolved_input_manifest: Sequence[Mapping[str, str]] | None,
) -> ValidationOwnerCurrent:
    """Build one owner against a direct or invocation-local input observation."""

    root_path = Path(root).resolve()
    resolved_inputs = (
        resolve_input_manifest(root_path, contract.input_patterns)
        if resolved_input_manifest is None
        else filter_resolved_input_manifest(
            resolved_input_manifest,
            contract.input_patterns,
        )
    )
    manifest = tuple(
        sorted(
            (
                *resolved_inputs,
                *(
                    {
                        "path": f"<projection:{component_id}>",
                        "sha256": fingerprint,
                    }
                    for component_id, fingerprint in contract.projected_inputs
                ),
                *(
                    {
                        "path": f"<external:{component_id}>",
                        "sha256": fingerprint,
                    }
                    for component_id, fingerprint in contract.external_component_bindings
                ),
            ),
            key=lambda item: item["path"],
        )
    )
    tokenized_command = tokenize_command(contract.command, workspace_root=root_path)
    canonical_contract = {
        **contract.to_dict(),
        "command": list(tokenized_command),
    }
    contract_hash = fingerprint_value(canonical_contract)
    check_manifest_hash = fingerprint_value(
        {
            "owner_id": contract.owner_id,
            "command": list(tokenized_command),
            "obligations": list(contract.obligation_ids),
        }
    )
    suite_map_hash = fingerprint_value(
        {
            "owner_id": contract.owner_id,
            "patterns": list(contract.input_patterns),
            "projected_inputs": [
                {
                    "component_id": component_id,
                    "fingerprint": fingerprint,
                }
                for component_id, fingerprint in contract.projected_inputs
            ],
            "obligations": list(contract.obligation_ids),
        }
    )
    input_snapshot = snapshot_bytes(
        f"input:validation-owner:{contract.owner_id}",
        _canonical_bytes([dict(item) for item in manifest]),
        path_token=f"<WORKSPACE>/<OWNER_INPUT:{contract.owner_id}>",
        obligation_ids=contract.obligation_ids,
    )
    observed_environment = {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "platform_system": platform.system(),
        "platform_machine": platform.machine(),
        "flowguard_version": _package_version(),
    }
    selected_keys = tuple(
        sorted(set(contract.toolchain_selectors + contract.environment_selectors))
    )
    unknown_selectors = sorted(set(selected_keys) - set(observed_environment))
    if unknown_selectors:
        raise ValueError(
            f"validation owner {contract.owner_id} has unknown environment selectors: "
            + ", ".join(unknown_selectors)
        )
    environment = build_environment_fingerprint(
        {key: observed_environment[key] for key in selected_keys}
    )
    owner_identity = fingerprint_value(
        {
            "schema": OWNER_RECEIPT_SCHEMA,
            "owner_id": contract.owner_id,
            "command": tokenized_command,
            "input_snapshot": input_snapshot.to_dict(),
            "contract_hash": contract_hash,
            "check_manifest_hash": check_manifest_hash,
            "suite_map_hash": suite_map_hash,
            "environment_fingerprint": environment.fingerprint,
            "obligations": list(contract.obligation_ids),
            "dependencies": list(contract.dependency_owner_ids),
            "resources": list(contract.resource_keys),
            "timeout_seconds": contract.timeout_seconds,
            "termination_policy": contract.termination_policy,
        }
    )
    return ValidationOwnerCurrent(
        contract=contract,
        input_manifest=manifest,
        input_snapshot=input_snapshot,
        contract_hash=contract_hash,
        check_manifest_hash=check_manifest_hash,
        suite_map_hash=suite_map_hash,
        environment_metadata=environment.metadata,
        environment_fingerprint=environment.fingerprint,
        command=tokenized_command,
        owner_identity=owner_identity,
    )


def _proof_path(receipt_root: Path, receipt: EvidenceReceipt) -> Path | None:
    relative = str(receipt.metadata.get("proof_relpath", ""))
    if not relative:
        return None
    candidate = (receipt_root / relative).resolve()
    if receipt_root.resolve() not in candidate.parents:
        return None
    return candidate


def build_owner_receipt_context(
    current: ValidationOwnerCurrent,
    receipt: EvidenceReceipt,
    receipt_root: str | Path,
) -> ReceiptVerificationContext | None:
    proof_path = _proof_path(Path(receipt_root).resolve(), receipt)
    if proof_path is None or not proof_path.is_file():
        return None
    proof_fingerprint = _sha256_bytes(proof_path.read_bytes())
    return _owner_receipt_context_for_proof(
        current,
        receipt,
        proof_fingerprint,
    )


def _owner_receipt_context_for_proof(
    current: ValidationOwnerCurrent,
    receipt: EvidenceReceipt,
    proof_fingerprint: str,
) -> ReceiptVerificationContext:
    return ReceiptVerificationContext(
        input_snapshots={current.input_snapshot.artifact_id: current.input_snapshot},
        contract_hash=current.contract_hash,
        check_manifest_hash=current.check_manifest_hash,
        suite_map_hash=current.suite_map_hash,
        producer_id=f"validation-owner:{current.contract.owner_id}",
        producer_version=_package_version(),
        environment_fingerprint=current.environment_fingerprint,
        proof_artifact_fingerprint=proof_fingerprint,
        result_fingerprint=proof_fingerprint,
        command=current.command,
        working_directory_token="<WORKSPACE>",
        proof_artifact_id=f"proof:validation-owner:{current.contract.owner_id}",
        required_obligation_ids=current.contract.obligation_ids,
        eligible_claim_scopes=(OWNER_RECEIPT_SCOPE,),
    )


def find_reusable_owner_receipt(
    current: ValidationOwnerCurrent,
    root: str | Path,
    receipt_root: str | Path,
    *,
    receipt_inventory: Sequence[EvidenceReceipt] | None = None,
) -> tuple[EvidenceReceipt | None, ReceiptVerificationResult | None]:
    subject_id = f"validation-owner:{current.contract.owner_id}"
    inventory = (
        tuple(receipt_inventory)
        if receipt_inventory is not None
        else list_evidence_receipts(root, output_directory=receipt_root)
    )
    candidates = [
        item
        for item in inventory
        if item.subject_id == subject_id
    ]
    candidates.sort(key=lambda item: item.finished_at, reverse=True)
    last_result: ReceiptVerificationResult | None = None
    exact_current: list[EvidenceReceipt] = []
    for receipt in candidates:
        assert_validation_owner_receipt_integrity(receipt)
        context = build_owner_receipt_context(current, receipt, receipt_root)
        result = verify_evidence_receipt(receipt, context)
        last_result = result
        if result.ok:
            exact_current.append(receipt)
            continue
        finding_codes = {finding.code for finding in result.findings}
        if finding_codes & {
            "proof_artifact_fingerprint_mismatch",
            "result_fingerprint_mismatch",
            "invalid_receipt",
        }:
            raise ValueError(
                "validation owner receipt or proof failed integrity verification"
            )
    if len(exact_current) > 1:
        raise ValueError(
            f"ambiguous exact-current receipts for {current.contract.owner_id}"
        )
    if exact_current:
        selected = exact_current[0]
        context = build_owner_receipt_context(current, selected, receipt_root)
        return selected, verify_evidence_receipt(selected, context)
    return None, last_result


def _receipt_inventory_identities(
    receipts: Sequence[EvidenceReceipt],
) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        sorted(
            (
                item.subject_id,
                item.receipt_id,
                item.fingerprint,
            )
            for item in receipts
        )
    )


def _governed_owner_input_manifest(
    currents: Iterable[ValidationOwnerCurrent],
) -> tuple[Mapping[str, str], ...]:
    rows: dict[str, str] = {}
    for current in currents:
        for item in current.input_manifest:
            path = str(item["path"])
            if path.startswith("<projection:") or path.startswith("<external:"):
                continue
            fingerprint = str(item["sha256"])
            previous = rows.get(path)
            if previous is not None and previous != fingerprint:
                raise ValueError(
                    f"validation owners disagree on input identity: {path}"
                )
            rows[path] = fingerprint
    return tuple(
        {"path": path, "sha256": rows[path]}
        for path in sorted(rows)
    )


def _validation_owner_observation(
    root: Path,
    contracts: Sequence[ValidationOwnerContract],
    *,
    receipt_root: Path,
    repository_input_manifest: Sequence[Mapping[str, str]],
    receipt_inventory: Sequence[EvidenceReceipt],
    started_at: float,
) -> ValidationOwnerObservation:
    ordered_contracts = topological_owner_contracts(contracts)
    currents: dict[str, ValidationOwnerCurrent] = {}
    reusable: dict[str, EvidenceReceipt] = {}
    verifications: dict[str, ReceiptVerificationResult] = {}
    rows: list[ValidationOwnerPlanRow] = []
    for contract in ordered_contracts:
        try:
            current = _build_owner_current(
                root,
                contract,
                all_contracts=ordered_contracts,
                resolved_input_manifest=repository_input_manifest,
            )
            currents[contract.owner_id] = current
            receipt, result = find_reusable_owner_receipt(
                current,
                root,
                receipt_root,
                receipt_inventory=receipt_inventory,
            )
        except (OSError, ValueError) as exc:
            rows.append(
                ValidationOwnerPlanRow(
                    contract.owner_id,
                    OWNER_BLOCKED,
                    "",
                    str(exc),
                )
            )
            continue
        if receipt is not None:
            if result is None or not result.ok:
                raise ValueError(
                    "exact-current validation owner receipt lacks its native "
                    f"verification: {contract.owner_id}"
                )
            reusable[contract.owner_id] = receipt
            verifications[contract.owner_id] = result
            rows.append(
                ValidationOwnerPlanRow(
                    contract.owner_id,
                    OWNER_REUSE_CURRENT,
                    current.owner_identity,
                    "independently verified exact-current terminal receipt",
                    receipt.receipt_id,
                    receipt.fingerprint,
                )
            )
        else:
            findings = tuple(
                finding.code
                for finding in (result.findings if result is not None else ())
            )
            rows.append(
                ValidationOwnerPlanRow(
                    contract.owner_id,
                    OWNER_EXECUTE,
                    current.owner_identity,
                    "no exact-current terminal-success receipt",
                    findings=findings,
                )
            )
    receipt_identities = _receipt_inventory_identities(receipt_inventory)
    payload = {
        "schema": "flowguard.validation_owner_observation.v1",
        "contracts": [item.to_dict() for item in ordered_contracts],
        "repository_input_manifest_fingerprint": manifest_fingerprint(
            _governed_owner_input_manifest(currents.values())
        ),
        "receipt_inventory_identities": [list(item) for item in receipt_identities],
        "owner_identities": {
            owner_id: current.owner_identity
            for owner_id, current in sorted(currents.items())
        },
        "rows": [item.to_dict() for item in rows],
        "reusable_receipts": [
            {
                "owner_id": owner_id,
                "receipt_id": receipt.receipt_id,
                "receipt_fingerprint": receipt.fingerprint,
                "verification": verifications[owner_id].to_dict(),
            }
            for owner_id, receipt in sorted(reusable.items())
        ],
    }
    return ValidationOwnerObservation(
        contracts=ordered_contracts,
        repository_input_manifest=tuple(
            dict(item) for item in repository_input_manifest
        ),
        receipt_inventory_identities=receipt_identities,
        rows=tuple(rows),
        owner_currents=tuple(
            currents[contract.owner_id]
            for contract in ordered_contracts
            if contract.owner_id in currents
        ),
        reusable_receipts=tuple(
            reusable[owner_id] for owner_id in sorted(reusable)
        ),
        reusable_verifications=tuple(
            verifications[owner_id] for owner_id in sorted(verifications)
        ),
        observation_fingerprint=fingerprint_value(payload),
        observation_seconds=max(0.0, time.perf_counter() - started_at),
    )


def observe_validation_owners(
    root: str | Path,
    contracts: Sequence[ValidationOwnerContract],
    *,
    receipt_root: str | Path,
) -> ValidationOwnerObservation:
    """Capture one strict owner observation for a bounded invocation."""

    started_at = time.perf_counter()
    ordered_contracts = topological_owner_contracts(contracts)
    root_path = Path(root).resolve()
    # Resolve and fingerprint the repository once for this planning invocation,
    # then project each owner's exact patterns from that single observation.
    # This is deliberately invocation-local: another plan resolves again so
    # source drift remains visible instead of becoming a cross-run cache hit.
    repository_input_manifest = resolve_input_manifest(
        root_path,
        ("**/*", "*"),
    )
    # One planning pass observes one immutable receipt-store snapshot.  Loading
    # the complete store independently for every owner is both redundant and,
    # on long-lived repositories, quadratic in the owner count.  Final receipt
    # currentness is still verified per owner and later publication phases
    # re-read the store under their own freshness boundary.
    receipt_inventory = list_evidence_receipts(
        root,
        output_directory=receipt_root,
    )
    return _validation_owner_observation(
        root_path,
        ordered_contracts,
        receipt_root=Path(receipt_root).resolve(),
        repository_input_manifest=repository_input_manifest,
        receipt_inventory=receipt_inventory,
        started_at=started_at,
    )


def plan_validation_owners(
    root: str | Path,
    contracts: Sequence[ValidationOwnerContract],
    *,
    receipt_root: str | Path,
) -> tuple[
    tuple[ValidationOwnerPlanRow, ...],
    Mapping[str, ValidationOwnerCurrent],
    Mapping[str, EvidenceReceipt],
]:
    """Compatibility-free tuple projection of one explicit observation."""

    observation = observe_validation_owners(
        root,
        contracts,
        receipt_root=receipt_root,
    )
    return (
        observation.rows,
        observation.current_by_owner,
        observation.receipt_by_owner,
    )


def refresh_validation_owner_observation_receipts(
    observation: ValidationOwnerObservation,
    root: str | Path,
    receipt_root: str | Path,
    supplied_receipts: Sequence[EvidenceReceipt],
) -> ValidationOwnerObservation:
    """Reconcile expected producer outputs without rescanning repository source.

    A model run may publish receipts after its source observation was frozen.
    This bounded refresh reads the canonical receipt store once, reuses native
    verifications for unchanged subjects, and verifies only newly supplied
    owner receipts against the already frozen current contexts.
    """

    started_at = time.perf_counter()
    root_path = Path(root).resolve()
    receipt_root_path = Path(receipt_root).resolve()
    supplied_by_owner: dict[str, EvidenceReceipt] = {}
    for receipt in supplied_receipts:
        _assert_owner_receipt_integrity(receipt)
        owner_id = receipt.subject_id.removeprefix("validation-owner:")
        if owner_id in supplied_by_owner:
            raise ValueError("supplied validation owner receipts must be unique")
        supplied_by_owner[owner_id] = receipt
    expected_owners = tuple(item.owner_id for item in observation.contracts)
    if set(supplied_by_owner) != set(expected_owners):
        raise ValueError(
            "supplied receipts do not exactly cover the frozen owner observation"
        )

    inventory = list_evidence_receipts(
        root_path,
        output_directory=receipt_root_path,
    )
    inventory_by_subject: dict[str, tuple[EvidenceReceipt, ...]] = {}
    for receipt in inventory:
        inventory_by_subject.setdefault(receipt.subject_id, []).append(receipt)
    initial_receipts = observation.receipt_by_owner
    initial_results = observation.verification_by_owner
    currents = observation.current_by_owner
    rows: list[ValidationOwnerPlanRow] = []
    reusable: dict[str, EvidenceReceipt] = {}
    verifications: dict[str, ReceiptVerificationResult] = {}
    for contract in observation.contracts:
        owner_id = contract.owner_id
        supplied = supplied_by_owner[owner_id]
        subject_id = f"validation-owner:{owner_id}"
        subject_inventory = tuple(inventory_by_subject.get(subject_id, ()))
        canonical = tuple(
            item
            for item in subject_inventory
            if item.receipt_id == supplied.receipt_id
            and item.fingerprint == supplied.fingerprint
        )
        if len(canonical) != 1:
            raise ValueError(
                f"supplied owner receipt is not canonical current: {owner_id}"
            )
        initial = initial_receipts.get(owner_id)
        if initial is not None and (
            initial.receipt_id == supplied.receipt_id
            and initial.fingerprint == supplied.fingerprint
        ):
            result = initial_results[owner_id]
        else:
            selected, result = find_reusable_owner_receipt(
                currents[owner_id],
                root_path,
                receipt_root_path,
                receipt_inventory=inventory,
            )
            if (
                selected is None
                or result is None
                or not result.ok
                or selected.receipt_id != supplied.receipt_id
                or selected.fingerprint != supplied.fingerprint
            ):
                raise ValueError(
                    f"new owner receipt failed exact-current verification: {owner_id}"
                )
        reusable[owner_id] = supplied
        verifications[owner_id] = result
        rows.append(
            ValidationOwnerPlanRow(
                owner_id,
                OWNER_REUSE_CURRENT,
                currents[owner_id].owner_identity,
                "independently verified exact-current terminal receipt",
                supplied.receipt_id,
                supplied.fingerprint,
            )
        )

    receipt_identities = _receipt_inventory_identities(inventory)
    payload = {
        "schema": "flowguard.validation_owner_observation.v1",
        "contracts": [item.to_dict() for item in observation.contracts],
        "repository_input_manifest_fingerprint": (
            observation.repository_input_manifest_fingerprint
        ),
        "receipt_inventory_identities": [list(item) for item in receipt_identities],
        "owner_identities": {
            owner_id: current.owner_identity
            for owner_id, current in sorted(currents.items())
        },
        "rows": [item.to_dict() for item in rows],
        "reusable_receipts": [
            {
                "owner_id": owner_id,
                "receipt_id": receipt.receipt_id,
                "receipt_fingerprint": receipt.fingerprint,
                "verification": verifications[owner_id].to_dict(),
            }
            for owner_id, receipt in sorted(reusable.items())
        ],
    }
    return ValidationOwnerObservation(
        contracts=observation.contracts,
        repository_input_manifest=observation.repository_input_manifest,
        receipt_inventory_identities=receipt_identities,
        rows=tuple(rows),
        owner_currents=observation.owner_currents,
        reusable_receipts=tuple(
            reusable[owner_id] for owner_id in sorted(reusable)
        ),
        reusable_verifications=tuple(
            verifications[owner_id] for owner_id in sorted(verifications)
        ),
        observation_fingerprint=fingerprint_value(payload),
        observation_seconds=max(0.0, time.perf_counter() - started_at),
    )


def assert_validation_owner_observation_fresh(
    observation: ValidationOwnerObservation,
    root: str | Path,
    receipt_root: str | Path,
    *,
    additional_receipt_subject_ids: Sequence[str] = (),
) -> ValidationObservationFreshness:
    """Make one fresh identity comparison without repeating native verifiers."""

    started_at = time.perf_counter()
    root_path = Path(root).resolve()
    receipt_root_path = Path(receipt_root).resolve()
    current_manifest = resolve_input_manifest(root_path, ("**/*", "*"))
    findings: list[str] = []

    current_owner_ids: dict[str, str] = {}
    current_owner_rows: list[ValidationOwnerCurrent] = []
    for contract in observation.contracts:
        current = _build_owner_current(
            root_path,
            contract,
            all_contracts=observation.contracts,
            resolved_input_manifest=current_manifest,
        )
        current_owner_ids[contract.owner_id] = current.owner_identity
        current_owner_rows.append(current)
    current_governed_manifest = _governed_owner_input_manifest(
        current_owner_rows
    )
    if manifest_fingerprint(current_governed_manifest) != (
        observation.repository_input_manifest_fingerprint
    ):
        findings.append("repository_input_manifest_changed")
    expected_owner_ids = {
        owner_id: current.owner_identity
        for owner_id, current in observation.current_by_owner.items()
    }
    if current_owner_ids != expected_owner_ids:
        findings.append("validation_owner_context_changed")

    inventory = list_evidence_receipts(
        root_path,
        output_directory=receipt_root_path,
    )
    subject_ids = {
        f"validation-owner:{contract.owner_id}"
        for contract in observation.contracts
    }
    subject_ids.update(
        str(item).strip()
        for item in additional_receipt_subject_ids
        if str(item).strip()
    )
    expected_receipts = tuple(
        item
        for item in observation.receipt_inventory_identities
        if item[0] in subject_ids
    )
    current_receipts = tuple(
        item
        for item in _receipt_inventory_identities(inventory)
        if item[0] in subject_ids
    )
    if current_receipts != expected_receipts:
        findings.append("validation_receipt_inventory_changed")

    final_payload = {
        "schema": "flowguard.validation_owner_freshness.v1",
        "initial_observation_fingerprint": observation.observation_fingerprint,
        "repository_input_manifest_fingerprint": manifest_fingerprint(
            current_governed_manifest
        ),
        "owner_identities": current_owner_ids,
        "receipt_inventory_identities": [list(item) for item in current_receipts],
        "receipt_subject_ids": sorted(subject_ids),
        "findings": findings,
    }
    result = ValidationObservationFreshness(
        status="pass" if not findings else "blocked",
        initial_observation_fingerprint=observation.observation_fingerprint,
        final_observation_fingerprint=fingerprint_value(final_payload),
        findings=tuple(findings),
        observation_seconds=max(0.0, time.perf_counter() - started_at),
        owner_currents=tuple(current_owner_rows),
    )
    if not result.ok:
        raise ValueError(
            "frozen validation owner observation changed before publication: "
            + ", ".join(result.findings)
        )
    return result


def assert_validation_owner_observation_receipts_fresh(
    source_observation: ValidationOwnerObservation,
    publication_observation: ValidationOwnerObservation,
    source_freshness: ValidationObservationFreshness,
    root: str | Path,
    receipt_root: str | Path,
    *,
    additional_receipt_subject_ids: Sequence[str] = (),
) -> ValidationObservationFreshness:
    """Complete one final boundary after batched leaf publication.

    The source observation is made once after all native producers terminate
    and before any new validation-owner leaf is published.  Publication then
    consumes those exact fresh owner contexts.  This function performs only
    the receipt-store half of the final comparison, so adding N leaf receipts
    cannot trigger N source-current rebuilds or a third repository scan.
    """

    started_at = time.perf_counter()
    if (
        not source_freshness.ok
        or source_freshness.initial_observation_fingerprint
        != source_observation.observation_fingerprint
    ):
        raise ValueError(
            "receipt freshness requires the matching passed source observation"
        )
    if (
        publication_observation.contracts != source_observation.contracts
        or publication_observation.repository_input_manifest
        != source_observation.repository_input_manifest
        or publication_observation.owner_currents
        != source_observation.owner_currents
    ):
        raise ValueError(
            "publication observation changed the frozen source or owner contexts"
        )
    final_currents = source_freshness.current_by_owner
    expected_currents = publication_observation.current_by_owner
    if (
        set(final_currents) != set(expected_currents)
        or any(
            final_currents[owner_id].owner_identity
            != expected_currents[owner_id].owner_identity
            for owner_id in expected_currents
        )
    ):
        raise ValueError(
            "final source observation does not own the publication contexts"
        )

    inventory = list_evidence_receipts(
        Path(root).resolve(),
        output_directory=Path(receipt_root).resolve(),
    )
    subject_ids = {
        f"validation-owner:{contract.owner_id}"
        for contract in publication_observation.contracts
    }
    subject_ids.update(
        str(item).strip()
        for item in additional_receipt_subject_ids
        if str(item).strip()
    )
    expected_receipts = tuple(
        item
        for item in publication_observation.receipt_inventory_identities
        if item[0] in subject_ids
    )
    current_receipts = tuple(
        item
        for item in _receipt_inventory_identities(inventory)
        if item[0] in subject_ids
    )
    findings: list[str] = []
    if current_receipts != expected_receipts:
        findings.append("validation_receipt_inventory_changed")
    final_payload = {
        "schema": "flowguard.validation_owner_publication_freshness.v1",
        "source_observation_fingerprint": (
            source_observation.observation_fingerprint
        ),
        "source_freshness_fingerprint": (
            source_freshness.final_observation_fingerprint
        ),
        "publication_observation_fingerprint": (
            publication_observation.observation_fingerprint
        ),
        "receipt_inventory_identities": [list(item) for item in current_receipts],
        "receipt_subject_ids": sorted(subject_ids),
        "findings": findings,
    }
    result = ValidationObservationFreshness(
        status="pass" if not findings else "blocked",
        initial_observation_fingerprint=(
            publication_observation.observation_fingerprint
        ),
        final_observation_fingerprint=fingerprint_value(final_payload),
        findings=tuple(findings),
        observation_seconds=(
            source_freshness.observation_seconds
            + max(0.0, time.perf_counter() - started_at)
        ),
        owner_currents=source_freshness.owner_currents,
    )
    if not result.ok:
        raise ValueError(
            "validation receipt inventory changed before parent publication: "
            + ", ".join(result.findings)
        )
    return result


def build_owner_current_from_observation(
    root: str | Path,
    contract: ValidationOwnerContract,
    *,
    all_contracts: Sequence[ValidationOwnerContract],
    observation: ValidationOwnerObservation,
) -> ValidationOwnerCurrent:
    """Project another exact owner from the same frozen repository view."""

    return _build_owner_current(
        Path(root).resolve(),
        contract,
        all_contracts=all_contracts,
        resolved_input_manifest=observation.repository_input_manifest,
    )


def build_validation_owner_plan(
    root: str | Path,
    contracts: Sequence[ValidationOwnerContract],
    *,
    receipt_root: str | Path,
    required_external_components: Mapping[str, str] | None = None,
) -> ValidationOwnerPlan:
    """Freeze the full owner DAG and both broad input manifests before execution."""

    root_path = Path(root).resolve()
    ordered_contracts = topological_owner_contracts(contracts)
    component_owners: dict[str, list[tuple[str, str]]] = {}
    for contract in ordered_contracts:
        for component_id, fingerprint in contract.external_component_bindings:
            component_owners.setdefault(component_id, []).append(
                (contract.owner_id, fingerprint)
            )
    conflicting_components = sorted(
        component_id
        for component_id, bindings in component_owners.items()
        if len({fingerprint for _owner_id, fingerprint in bindings}) != 1
    )
    if conflicting_components:
        raise ValueError(
            "external component consumers disagree on identity: "
            + ", ".join(conflicting_components)
        )
    required_components = {
        str(component_id): str(fingerprint)
        for component_id, fingerprint in (required_external_components or {}).items()
    }
    missing_components = sorted(set(required_components) - set(component_owners))
    extra_components = sorted(set(component_owners) - set(required_components))
    mismatched_components = sorted(
        component_id
        for component_id in set(required_components) & set(component_owners)
        if required_components[component_id] != component_owners[component_id][0][1]
    )
    if required_external_components is not None and (
        missing_components or extra_components or mismatched_components
    ):
        raise ValueError(
            "external component mapping is not exact: "
            f"missing={missing_components}, extra={extra_components}, "
            f"mismatched={mismatched_components}"
        )
    rows, currents, reusable = plan_validation_owners(
        root_path,
        ordered_contracts,
        receipt_root=receipt_root,
    )
    validation_manifest = validation_input_manifest(root_path)
    tree_manifest = release_tree_manifest(root_path)
    payload = {
        "schema_version": OWNER_PLAN_SCHEMA,
        "contracts": [
            {
                **item.to_dict(),
                "command": list(tokenize_command(item.command, workspace_root=root_path)),
            }
            for item in ordered_contracts
        ],
        "owner_identities": {
            owner_id: current.owner_identity
            for owner_id, current in sorted(currents.items())
        },
        "validation_input_manifest_fingerprint": manifest_fingerprint(
            validation_manifest
        ),
        "release_tree_manifest_fingerprint": manifest_fingerprint(tree_manifest),
    }
    return ValidationOwnerPlan(
        contracts=ordered_contracts,
        rows=rows,
        owner_currents=currents,
        reusable_receipts=reusable,
        validation_input_manifest=validation_manifest,
        validation_input_manifest_fingerprint=payload[
            "validation_input_manifest_fingerprint"
        ],
        release_tree_manifest=tree_manifest,
        release_tree_manifest_fingerprint=payload[
            "release_tree_manifest_fingerprint"
        ],
        plan_fingerprint=fingerprint_value(payload),
    )


def build_validation_parent_current(
    root: str | Path,
    owner_plan: ValidationOwnerPlan,
) -> ValidationParentCurrent:
    """Derive one immutable parent identity from a previously frozen owner plan."""

    root_path = Path(root).resolve()
    if owner_plan.blocked:
        raise ValueError("blocked validation owner plan cannot become parent current")
    current_validation = validation_input_manifest(root_path)
    current_tree = release_tree_manifest(root_path)
    if (
        manifest_fingerprint(current_validation)
        != owner_plan.validation_input_manifest_fingerprint
        or manifest_fingerprint(current_tree)
        != owner_plan.release_tree_manifest_fingerprint
    ):
        raise ValueError("validation inputs changed after owner-plan freeze")
    obligations = tuple(
        obligation
        for contract in owner_plan.contracts
        for obligation in contract.obligation_ids
    )
    validation_snapshot = snapshot_bytes(
        "input:validation-parent:validation-input-manifest",
        _canonical_bytes([dict(item) for item in owner_plan.validation_input_manifest]),
        path_token="<WORKSPACE>/<VALIDATION_INPUT_MANIFEST>",
        obligation_ids=obligations,
    )
    tree_snapshot = snapshot_bytes(
        "input:validation-parent:release-tree-manifest",
        _canonical_bytes([dict(item) for item in owner_plan.release_tree_manifest]),
        path_token="<WORKSPACE>/<RELEASE_TREE_MANIFEST>",
        obligation_ids=obligations,
    )
    canonical_contracts = [
        {
            **item.to_dict(),
            "command": list(tokenize_command(item.command, workspace_root=root_path)),
        }
        for item in owner_plan.contracts
    ]
    contract_hash = fingerprint_value(
        {"schema": OWNER_RECEIPT_SCHEMA, "owner": "validation-parent:full"}
    )
    check_manifest_hash = fingerprint_value(canonical_contracts)
    suite_map_hash = fingerprint_value(
        {
            item.owner_id: list(item.obligation_ids)
            for item in owner_plan.contracts
        }
    )
    environment = build_environment_fingerprint(
        {
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "platform_system": platform.system(),
            "platform_machine": platform.machine(),
            "flowguard_version": _package_version(),
        }
    )
    parent_identity = fingerprint_value(
        {
            "schema_version": PARENT_CURRENT_SCHEMA,
            "plan_fingerprint": owner_plan.plan_fingerprint,
            "validation_snapshot": validation_snapshot.to_dict(),
            "release_tree_snapshot": tree_snapshot.to_dict(),
            "contract_hash": contract_hash,
            "check_manifest_hash": check_manifest_hash,
            "suite_map_hash": suite_map_hash,
            "environment_fingerprint": environment.fingerprint,
        }
    )
    return ValidationParentCurrent(
        owner_plan=owner_plan,
        validation_snapshot=validation_snapshot,
        release_tree_snapshot=tree_snapshot,
        contract_hash=contract_hash,
        check_manifest_hash=check_manifest_hash,
        suite_map_hash=suite_map_hash,
        environment_metadata=environment.metadata,
        environment_fingerprint=environment.fingerprint,
        parent_identity=parent_identity,
    )


@dataclass(frozen=True)
class _PreparedOwnerReceipt:
    receipt: EvidenceReceipt
    proof_path: Path
    proof_bytes: bytes


def _prepare_owner_receipt(
    current: ValidationOwnerCurrent,
    child: ValidationChildResult,
    receipt_root: str | Path,
    *,
    started_at: str,
    finished_at: str,
    publication_kind: str,
) -> _PreparedOwnerReceipt:
    if publication_kind not in {"supervised_producer", "nonpass_record"}:
        raise ValueError("unsupported validation owner publication kind")
    if child.status == RECEIPT_STATUS_PASS and publication_kind != "supervised_producer":
        raise ValueError(
            "passing validation owner receipts require the supervised producer"
        )
    if publication_kind == "supervised_producer" and child.status != RECEIPT_STATUS_PASS:
        raise ValueError("supervised pass publication requires a passing child result")
    receipt_root_path = Path(receipt_root).resolve()
    proof_payload = {
        "schema_version": OWNER_RECEIPT_SCHEMA,
        "publication_kind": publication_kind,
        "owner_id": current.contract.owner_id,
        "owner_identity": current.owner_identity,
        "child": {
            "child_id": child.child_id,
            "status": child.status,
            "summary": child.summary,
            "nested_receipt_id": child.receipt_id,
            "claim_boundary": child.claim_boundary,
            "payload": dict(child.payload),
        },
    }
    proof_bytes = _canonical_bytes(proof_payload)
    proof_fingerprint = _sha256_bytes(proof_bytes)
    proof_dir = receipt_root_path / "proofs"
    proof_name = proof_fingerprint.split(":", 1)[1] + ".json"
    proof_path = proof_dir / proof_name
    receipt = EvidenceReceipt(
        receipt_id=(
            f"receipt:validation-owner:{current.contract.owner_id}:"
            + "0" * 32
        ),
        subject_id=f"validation-owner:{current.contract.owner_id}",
        subject_kind=OWNER_RECEIPT_KIND,
        producer_id=f"validation-owner:{current.contract.owner_id}",
        producer_version=_package_version(),
        claim_scope=OWNER_RECEIPT_SCOPE,
        command=current.command,
        working_directory_token="<WORKSPACE>",
        started_at=started_at,
        finished_at=finished_at,
        exit_code=0 if child.status == RECEIPT_STATUS_PASS else 1,
        environment_fingerprint=current.environment_fingerprint,
        environment_metadata=current.environment_metadata,
        contract_hash=current.contract_hash,
        check_manifest_hash=current.check_manifest_hash,
        suite_map_hash=current.suite_map_hash,
        input_snapshots=(current.input_snapshot,),
        proof_artifact_id=f"proof:validation-owner:{current.contract.owner_id}",
        proof_artifact_fingerprint=proof_fingerprint,
        result_status=_receipt_result_status(child.status),
        result_fingerprint=proof_fingerprint,
        covered_obligations=current.contract.obligation_ids,
        blockers=() if child.status == RECEIPT_STATUS_PASS else (f"owner_status:{child.status}",),
        claim_boundary=child.claim_boundary or "One native validation owner result.",
        metadata={
            "owner_identity": current.owner_identity,
            "proof_relpath": proof_path.relative_to(receipt_root_path).as_posix(),
            "publication_kind": publication_kind,
        },
    )
    receipt = replace(
        receipt,
        receipt_id=_content_addressed_receipt_id(
            f"receipt:validation-owner:{current.contract.owner_id}",
            receipt,
        ),
    )
    return _PreparedOwnerReceipt(receipt, proof_path, proof_bytes)


def _verify_prepared_owner_receipt(
    current: ValidationOwnerCurrent,
    prepared: _PreparedOwnerReceipt,
) -> ReceiptVerificationResult:
    return verify_evidence_receipt(
        prepared.receipt,
        _owner_receipt_context_for_proof(
            current,
            prepared.receipt,
            _sha256_bytes(prepared.proof_bytes),
        ),
    )


def _publish_content_addressed_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError("content-addressed validation proof collision")
        return
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != content:
                raise ValueError("content-addressed validation proof collision")
    finally:
        temporary.unlink(missing_ok=True)


def _publish_prepared_owner_receipt(
    prepared: _PreparedOwnerReceipt,
    root: str | Path,
    receipt_root: str | Path,
) -> EvidenceReceipt:
    """Publish a fully prepared result; an interruption can leave only a proof."""

    _publish_content_addressed_bytes(prepared.proof_path, prepared.proof_bytes)
    save_evidence_receipt(
        prepared.receipt,
        root,
        output_directory=Path(receipt_root).resolve(),
    )
    return prepared.receipt


def record_validation_owner_nonpass(
    current: ValidationOwnerCurrent,
    child: ValidationChildResult,
    root: str | Path,
    receipt_root: str | Path,
    *,
    all_contracts: Sequence[ValidationOwnerContract],
    started_at: str,
    finished_at: str,
) -> EvidenceReceipt:
    """Record a fail/blocked/not-run owner result without a success path."""

    if child.status == RECEIPT_STATUS_PASS:
        raise ValueError(
            "record_validation_owner_nonpass cannot publish a passing receipt"
        )
    root_path = Path(root).resolve()
    refreshed = build_owner_current(
        root_path,
        current.contract,
        all_contracts=tuple(all_contracts),
    )
    if refreshed.owner_identity != current.owner_identity:
        raise ValueError("validation owner inputs changed before nonpass publication")
    prepared = _prepare_owner_receipt(
        refreshed,
        child,
        receipt_root,
        started_at=started_at,
        finished_at=finished_at,
        publication_kind="nonpass_record",
    )
    return _publish_prepared_owner_receipt(
        prepared,
        root_path,
        receipt_root,
    )


def build_child_bound_owner_receipt_context(
    current: ValidationOwnerCurrent,
    receipt: EvidenceReceipt,
    root: str | Path,
    receipt_root: str | Path,
    *,
    child_receipts: Sequence[EvidenceReceipt],
    child_verification_results: Sequence[ReceiptVerificationResult],
) -> ReceiptVerificationContext:
    """Build currentness context for an owner receipt that composes real children."""

    base = build_owner_receipt_context(current, receipt, receipt_root)
    if base is None:
        raise ValueError(
            f"owner proof is missing for child-bound receipt {receipt.receipt_id}"
        )
    children_by_id = {item.receipt_id: item for item in child_receipts}
    if len(children_by_id) != len(child_receipts):
        raise ValueError("child-bound owner receipt children must be unique")
    results_by_id = {item.receipt_id: item for item in child_verification_results}
    if len(results_by_id) != len(child_verification_results):
        raise ValueError(
            "child-bound owner receipt verification results must be unique"
        )
    if set(results_by_id) != set(children_by_id):
        raise ValueError(
            "child-bound owner receipt requires one verification per child"
        )
    return replace(
        base,
        child_receipts=children_by_id,
        child_verification_results=results_by_id,
        receipt_store_repository_root=str(Path(root).resolve()),
        receipt_store_output_directory=str(Path(receipt_root).resolve()),
    )


@dataclass(frozen=True)
class _DerivedExactChildReceipt:
    contract: ValidationOwnerContract
    current: ValidationOwnerCurrent
    receipt: EvidenceReceipt
    verification: ReceiptVerificationResult


def _refresh_child_bound_owner_current(
    current: ValidationOwnerCurrent,
    root: Path,
    all_contracts: Sequence[ValidationOwnerContract],
) -> ValidationOwnerCurrent:
    universe = topological_owner_contracts(all_contracts)
    matching = tuple(
        contract
        for contract in universe
        if contract.owner_id == current.contract.owner_id
    )
    if len(matching) != 1 or matching[0] != current.contract:
        raise ValueError(
            "child-bound owner contract universe does not exactly own the aggregate"
        )
    refreshed = build_owner_current(
        root,
        matching[0],
        all_contracts=universe,
    )
    if refreshed.owner_identity != current.owner_identity:
        raise ValueError("child-bound owner inputs changed before publication")
    return refreshed


def _derive_exact_current_child_receipts(
    root: Path,
    receipt_root: Path,
    child_receipts: Sequence[EvidenceReceipt],
    child_contracts: Sequence[ValidationOwnerContract],
) -> tuple[_DerivedExactChildReceipt, ...]:
    """Rebuild child currentness from exact contracts and the canonical store."""

    ordered_contracts = topological_owner_contracts(child_contracts)
    if not ordered_contracts:
        raise ValueError("child-bound owner receipt requires child contracts")
    supplied_by_subject: dict[str, EvidenceReceipt] = {}
    for child in child_receipts:
        assert_validation_owner_receipt_integrity(child)
        if child.subject_id in supplied_by_subject:
            raise ValueError(
                "child-bound owner receipt child subjects must be unique"
            )
        supplied_by_subject[child.subject_id] = child
    expected_subjects = {
        f"validation-owner:{contract.owner_id}" for contract in ordered_contracts
    }
    if set(supplied_by_subject) != expected_subjects:
        raise ValueError(
            "child-bound owner receipt subjects do not exactly match child contracts"
        )

    rows, currents, reusable = plan_validation_owners(
        root,
        ordered_contracts,
        receipt_root=receipt_root,
    )
    noncurrent = tuple(
        f"{row.owner_id} ({row.reason})"
        for row in rows
        if row.disposition != OWNER_REUSE_CURRENT
    )
    if noncurrent:
        raise ValueError(
            "child-bound owner child evidence is not exact-current: "
            + ", ".join(noncurrent)
        )

    derived: list[_DerivedExactChildReceipt] = []
    for contract in ordered_contracts:
        subject_id = f"validation-owner:{contract.owner_id}"
        supplied = supplied_by_subject[subject_id]
        canonical = reusable[contract.owner_id]
        current = currents[contract.owner_id]
        if (
            supplied.receipt_id != canonical.receipt_id
            or supplied.fingerprint != canonical.fingerprint
        ):
            raise ValueError(
                f"child-bound owner receipt is not canonical current: {contract.owner_id}"
            )
        assert_validation_owner_receipt_integrity(canonical)
        if canonical.required_child_receipts or canonical.consumed_child_receipts:
            raise ValueError(
                "child-bound owner composition accepts exact terminal leaf receipts only"
            )
        if (
            canonical.subject_id != subject_id
            or canonical.subject_kind != OWNER_RECEIPT_KIND
            or canonical.producer_id != subject_id
            or canonical.claim_scope != OWNER_RECEIPT_SCOPE
            or canonical.result_status != RECEIPT_STATUS_PASS
            or canonical.exit_code != 0
            or canonical.skipped_checks
            or canonical.blockers
            or canonical.covered_obligations != contract.obligation_ids
            or str(canonical.metadata.get("publication_kind", ""))
            != "supervised_producer"
            or str(canonical.metadata.get("owner_identity", ""))
            != current.owner_identity
        ):
            raise ValueError(
                f"child-bound owner child is not one exact supervised leaf: {contract.owner_id}"
            )
        context = build_owner_receipt_context(current, canonical, receipt_root)
        verification = verify_evidence_receipt(canonical, context)
        if not verification.ok:
            raise ValueError(
                f"child-bound owner child failed fresh verification: {contract.owner_id}"
            )
        if set(verification.satisfied_obligations) != set(contract.obligation_ids):
            raise ValueError(
                f"child-bound owner child obligation mismatch: {contract.owner_id}"
            )
        derived.append(
            _DerivedExactChildReceipt(
                contract=contract,
                current=current,
                receipt=canonical,
                verification=verification,
            )
        )
    return tuple(sorted(derived, key=lambda item: item.receipt.receipt_id))


def _derived_exact_child_identity(
    children: Sequence[_DerivedExactChildReceipt],
) -> tuple[tuple[str, str, str, str, Mapping[str, Any]], ...]:
    return tuple(
        (
            item.contract.owner_id,
            item.current.owner_identity,
            item.receipt.receipt_id,
            item.receipt.fingerprint,
            item.verification.to_dict(),
        )
        for item in children
    )


def _save_child_bound_owner_receipt_from_derived(
    publication_current: ValidationOwnerCurrent,
    publication_children: Sequence[_DerivedExactChildReceipt],
    root_path: Path,
    receipt_root_path: Path,
    *,
    started_at: str,
    finished_at: str,
    evidence_context: Mapping[str, Any],
    claim_boundary: str,
) -> tuple[EvidenceReceipt, ReceiptVerificationResult]:
    root_path = Path(root_path).resolve()
    receipt_root_path = Path(receipt_root_path).resolve()
    ordered_children = tuple(item.receipt for item in publication_children)
    child_ids = tuple(item.receipt_id for item in ordered_children)

    proof_payload = {
        "schema_version": "flowguard.child_bound_validation_owner_proof.v1",
        "owner_id": publication_current.contract.owner_id,
        "owner_identity": publication_current.owner_identity,
        "covered_obligations": list(publication_current.contract.obligation_ids),
        "children": [
            {
                "receipt_id": child.receipt_id,
                "receipt_fingerprint": child.fingerprint,
                "subject_id": child.subject_id,
                "covered_obligations": list(child.covered_obligations),
            }
            for child in ordered_children
        ],
        "evidence_context": dict(evidence_context),
    }
    proof_bytes = _canonical_bytes(proof_payload)
    proof_fingerprint = _sha256_bytes(proof_bytes)
    proof_dir = receipt_root_path / "proofs"
    proof_path = proof_dir / (
        "owner-aggregate-" + proof_fingerprint.split(":", 1)[1] + ".json"
    )

    receipt = EvidenceReceipt(
        receipt_id=(
            f"receipt:validation-owner:{publication_current.contract.owner_id}:"
            + "0" * 32
        ),
        subject_id=f"validation-owner:{publication_current.contract.owner_id}",
        subject_kind=OWNER_RECEIPT_KIND,
        producer_id=f"validation-owner:{publication_current.contract.owner_id}",
        producer_version=_package_version(),
        claim_scope=OWNER_RECEIPT_SCOPE,
        command=publication_current.command,
        working_directory_token="<WORKSPACE>",
        started_at=started_at,
        finished_at=finished_at,
        exit_code=0,
        environment_fingerprint=publication_current.environment_fingerprint,
        environment_metadata=publication_current.environment_metadata,
        contract_hash=publication_current.contract_hash,
        check_manifest_hash=publication_current.check_manifest_hash,
        suite_map_hash=publication_current.suite_map_hash,
        input_snapshots=(publication_current.input_snapshot,),
        proof_artifact_id=(
            f"proof:validation-owner:{publication_current.contract.owner_id}"
        ),
        proof_artifact_fingerprint=proof_fingerprint,
        result_status=RECEIPT_STATUS_PASS,
        result_fingerprint=proof_fingerprint,
        covered_obligations=publication_current.contract.obligation_ids,
        required_child_receipts=tuple(
            ChildReceiptRequirement(
                receipt_id=child.receipt_id,
                subject_id=child.subject_id,
                obligation_ids=child.covered_obligations,
                eligible_claim_scopes=(OWNER_RECEIPT_SCOPE,),
                expected_receipt_fingerprint=child.fingerprint,
            )
            for child in ordered_children
        ),
        consumed_child_receipts=tuple(
            ConsumedChildReceipt(child.receipt_id, child.fingerprint)
            for child in ordered_children
        ),
        claim_boundary=claim_boundary,
        metadata={
            "owner_identity": publication_current.owner_identity,
            "proof_relpath": proof_path.relative_to(receipt_root_path).as_posix(),
            "child_receipt_ids": list(child_ids),
        },
    )
    receipt = replace(
        receipt,
        receipt_id=_content_addressed_receipt_id(
            f"receipt:validation-owner:{publication_current.contract.owner_id}",
            receipt,
        ),
    )

    _publish_content_addressed_bytes(proof_path, proof_bytes)
    save_evidence_receipt(
        receipt,
        root_path,
        output_directory=receipt_root_path,
    )

    context = build_child_bound_owner_receipt_context(
        publication_current,
        receipt,
        root_path,
        receipt_root_path,
        child_receipts=tuple(item.receipt for item in publication_children),
        child_verification_results=tuple(
            item.verification for item in publication_children
        ),
    )
    verification = verify_evidence_receipt(receipt, context)
    if not verification.ok:
        raise ValueError(
            "saved child-bound validation owner failed immediate verification: "
            + ", ".join(item.code for item in verification.findings)
        )
    return receipt, verification


def save_child_bound_owner_receipt(
    current: ValidationOwnerCurrent,
    child_receipts: Sequence[EvidenceReceipt],
    root: str | Path,
    receipt_root: str | Path,
    *,
    all_contracts: Sequence[ValidationOwnerContract],
    child_contracts: Sequence[ValidationOwnerContract],
    started_at: str,
    finished_at: str,
    evidence_context: Mapping[str, Any],
    claim_boundary: str,
) -> tuple[EvidenceReceipt, ReceiptVerificationResult]:
    """Persist one aggregate through an independently fresh direct invocation."""

    root_path = Path(root).resolve()
    receipt_root_path = Path(receipt_root).resolve()
    publication_current = _refresh_child_bound_owner_current(
        current,
        root_path,
        all_contracts,
    )
    publication_children = _derive_exact_current_child_receipts(
        root_path,
        receipt_root_path,
        child_receipts,
        child_contracts,
    )
    receipt, verification = _save_child_bound_owner_receipt_from_derived(
        publication_current,
        publication_children,
        root_path,
        receipt_root_path,
        started_at=started_at,
        finished_at=finished_at,
        evidence_context=evidence_context,
        claim_boundary=claim_boundary,
    )
    final_current = _refresh_child_bound_owner_current(
        current,
        root_path,
        all_contracts,
    )
    final_children = _derive_exact_current_child_receipts(
        root_path,
        receipt_root_path,
        child_receipts,
        child_contracts,
    )
    if (
        final_current.owner_identity != publication_current.owner_identity
        or _derived_exact_child_identity(final_children)
        != _derived_exact_child_identity(publication_children)
    ):
        raise ValueError(
            "child-bound owner or children changed during atomic publication"
        )
    return receipt, verification


def save_child_bound_owner_receipt_from_observation(
    current: ValidationOwnerCurrent,
    child_owner_ids: Sequence[str],
    root: str | Path,
    receipt_root: str | Path,
    *,
    observation: ValidationOwnerObservation,
    freshness: ValidationObservationFreshness,
    started_at: str,
    finished_at: str,
    evidence_context: Mapping[str, Any],
    claim_boundary: str,
) -> tuple[EvidenceReceipt, ReceiptVerificationResult]:
    """Publish one aggregate from a passed invocation-local freshness boundary."""

    if (
        not freshness.ok
        or freshness.initial_observation_fingerprint
        != observation.observation_fingerprint
    ):
        raise ValueError(
            "child-bound observation publication requires a matching final freshness pass"
        )
    owner_ids = tuple(sorted({str(item) for item in child_owner_ids if str(item)}))
    if not owner_ids:
        raise ValueError("child-bound observation publication requires children")
    currents = observation.current_by_owner
    receipts = observation.receipt_by_owner
    verifications = observation.verification_by_owner
    if any(
        owner_id not in currents
        or owner_id not in receipts
        or owner_id not in verifications
        for owner_id in owner_ids
    ):
        raise ValueError(
            "child-bound observation does not contain every exact child owner"
        )
    derived: list[_DerivedExactChildReceipt] = []
    for owner_id in owner_ids:
        contract = currents[owner_id].contract
        receipt = receipts[owner_id]
        verification = verifications[owner_id]
        _assert_owner_receipt_integrity(receipt)
        if (
            not verification.ok
            or verification.receipt_id != receipt.receipt_id
            or receipt.subject_id != f"validation-owner:{owner_id}"
            or receipt.subject_kind != OWNER_RECEIPT_KIND
            or receipt.producer_id != receipt.subject_id
            or receipt.claim_scope != OWNER_RECEIPT_SCOPE
            or receipt.result_status != RECEIPT_STATUS_PASS
            or receipt.exit_code != 0
            or receipt.skipped_checks
            or receipt.blockers
            or receipt.covered_obligations != contract.obligation_ids
            or receipt.required_child_receipts
            or receipt.consumed_child_receipts
            or str(receipt.metadata.get("publication_kind", ""))
            != "supervised_producer"
            or str(receipt.metadata.get("owner_identity", ""))
            != currents[owner_id].owner_identity
        ):
            raise ValueError(
                f"observation child is not one exact supervised leaf: {owner_id}"
            )
        derived.append(
            _DerivedExactChildReceipt(
                contract=contract,
                current=currents[owner_id],
                receipt=receipt,
                verification=verification,
            )
        )
    return _save_child_bound_owner_receipt_from_derived(
        current,
        tuple(sorted(derived, key=lambda item: item.receipt.receipt_id)),
        Path(root).resolve(),
        Path(receipt_root).resolve(),
        started_at=started_at,
        finished_at=finished_at,
        evidence_context=evidence_context,
        claim_boundary=claim_boundary,
    )


def child_from_owner_receipt(
    receipt: EvidenceReceipt,
    receipt_root: str | Path,
) -> ValidationChildResult:
    proof_path = _proof_path(Path(receipt_root).resolve(), receipt)
    if proof_path is None or not proof_path.is_file():
        raise ValueError(f"owner proof is missing for {receipt.receipt_id}")
    payload = json.loads(proof_path.read_text(encoding="utf-8"))
    child = payload.get("child", {})
    if not isinstance(child, Mapping):
        raise ValueError("validation owner proof child is invalid")
    return ValidationChildResult(
        child_id=str(child.get("child_id", "")),
        status=str(child.get("status", "")),
        summary=str(child.get("summary", "")),
        receipt_id=receipt.receipt_id,
        artifact_paths=(str(proof_path),),
        claim_boundary=str(child.get("claim_boundary", "")),
        payload={
            **dict(child.get("payload", {})),
            "execution_disposition": OWNER_REUSE_CURRENT,
            "owner_receipt_fingerprint": receipt.fingerprint,
            "nested_receipt_id": str(child.get("nested_receipt_id", "")),
        },
    )


def save_parent_receipt(
    root: str | Path,
    receipt_root: str | Path,
    *,
    parent_current: ValidationParentCurrent,
    child_receipts: Sequence[EvidenceReceipt],
    status: str,
    started_at: str,
    finished_at: str,
) -> EvidenceReceipt:
    """Persist one parent composition over exact independently owned children."""

    root_path = Path(root).resolve()
    receipt_root_path = Path(receipt_root).resolve()
    owner_plan = parent_current.owner_plan
    contracts = owner_plan.contracts
    if build_validation_parent_current(root_path, owner_plan).parent_identity != parent_current.parent_identity:
        raise ValueError("validation parent current changed before composition")
    by_subject = {item.subject_id: item for item in child_receipts}
    if len(by_subject) != len(child_receipts):
        raise ValueError("parent child subjects must be unique")
    required_receipts: list[tuple[ValidationOwnerContract, EvidenceReceipt]] = []
    for contract in contracts:
        receipt = by_subject.get(f"validation-owner:{contract.owner_id}")
        if receipt is None:
            raise ValueError(f"parent receipt is missing owner receipt: {contract.owner_id}")
        current = owner_plan.owner_currents.get(contract.owner_id)
        if current is None:
            raise ValueError(f"parent owner current is missing: {contract.owner_id}")
        context = build_owner_receipt_context(current, receipt, receipt_root_path)
        verification = verify_evidence_receipt(receipt, context)
        if not verification.ok:
            raise ValueError(
                f"parent child receipt is not exact-current: {contract.owner_id}"
            )
        required_receipts.append((contract, receipt))
    validation_fingerprint = owner_plan.validation_input_manifest_fingerprint
    validation_snapshot = parent_current.validation_snapshot
    tree_fingerprint = owner_plan.release_tree_manifest_fingerprint
    tree_snapshot = parent_current.release_tree_snapshot
    canonical_contracts = [
        {
            **item.to_dict(),
            "command": list(
                tokenize_command(item.command, workspace_root=root_path)
            ),
        }
        for item in contracts
    ]
    proof_payload = {
        "schema_version": "flowguard.validation_parent_proof.v3",
        "parent_identity": parent_current.parent_identity,
        "owner_plan_fingerprint": owner_plan.plan_fingerprint,
        "validation_input_manifest_fingerprint": validation_fingerprint,
        "release_tree_manifest_fingerprint": tree_fingerprint,
        "contracts": canonical_contracts,
        "owner_plan": [item.to_dict() for item in owner_plan.rows],
        "children": [
            {
                "owner_id": contract.owner_id,
                "receipt_id": receipt.receipt_id,
                "receipt_fingerprint": receipt.fingerprint,
            }
            for contract, receipt in required_receipts
        ],
    }
    proof_bytes = _canonical_bytes(proof_payload)
    proof_fingerprint = _sha256_bytes(proof_bytes)
    proof_dir = receipt_root_path / "proofs"
    proof_dir.mkdir(parents=True, exist_ok=True)
    proof_path = proof_dir / (
        "parent-" + proof_fingerprint.split(":", 1)[1] + ".json"
    )
    if proof_path.exists() and proof_path.read_bytes() != proof_bytes:
        raise ValueError("content-addressed parent proof collision")
    if not proof_path.exists():
        proof_path.write_bytes(proof_bytes)
    receipt_id = (
        "receipt:validation-parent:full:"
        + fingerprint_value(
            {
                "proof_fingerprint": proof_fingerprint,
                "status": status,
                "finished_at": finished_at,
            }
        ).split(":", 1)[1][:24]
    )
    receipt = EvidenceReceipt(
        receipt_id=receipt_id,
        subject_id="validation-parent:full",
        subject_kind="validation_parent",
        producer_id="validation-parent:full",
        producer_version=_package_version(),
        claim_scope=OWNER_RECEIPT_SCOPE,
        command=("python", "scripts/check_flowguard_skill_suite.py", "--scope", "full"),
        working_directory_token="<WORKSPACE>",
        started_at=started_at,
        finished_at=finished_at,
        exit_code=0 if status == RECEIPT_STATUS_PASS else 1,
        environment_fingerprint=parent_current.environment_fingerprint,
        environment_metadata=parent_current.environment_metadata,
        contract_hash=parent_current.contract_hash,
        check_manifest_hash=parent_current.check_manifest_hash,
        suite_map_hash=parent_current.suite_map_hash,
        input_snapshots=(validation_snapshot, tree_snapshot),
        proof_artifact_id="proof:validation-parent:full",
        proof_artifact_fingerprint=proof_fingerprint,
        result_status=_receipt_result_status(status),
        result_fingerprint=proof_fingerprint,
        covered_obligations=tuple(
            obligation
            for contract in contracts
            for obligation in contract.obligation_ids
        ),
        required_child_receipts=tuple(
            ChildReceiptRequirement(
                receipt_id=receipt.receipt_id,
                subject_id=receipt.subject_id,
                obligation_ids=contract.obligation_ids,
                eligible_claim_scopes=(OWNER_RECEIPT_SCOPE,),
                expected_receipt_fingerprint=receipt.fingerprint,
            )
            for contract, receipt in required_receipts
        ),
        consumed_child_receipts=tuple(
            ConsumedChildReceipt(receipt.receipt_id, receipt.fingerprint)
            for _contract, receipt in required_receipts
        ),
        blockers=() if status == RECEIPT_STATUS_PASS else (f"parent_status:{status}",),
        claim_boundary=(
            "This parent composes exact-current native validation-owner receipts "
            "for one frozen validation-input manifest and one exact release-tree manifest."
        ),
        metadata={
            "proof_relpath": proof_path.relative_to(receipt_root_path).as_posix(),
            "parent_identity": parent_current.parent_identity,
            "owner_plan_fingerprint": owner_plan.plan_fingerprint,
            "validation_input_manifest_fingerprint": validation_fingerprint,
            "release_tree_manifest_fingerprint": tree_fingerprint,
        },
    )
    save_evidence_receipt(receipt, root_path, output_directory=receipt_root_path)
    verification = verify_parent_receipt(
        receipt,
        root_path,
        receipt_root_path,
    )
    if not verification.ok:
        raise ValueError(
            "saved validation parent failed immediate verification: "
            + ", ".join(item.code for item in verification.findings)
        )
    return receipt


def verify_parent_receipt(
    receipt: EvidenceReceipt | str,
    root: str | Path,
    receipt_root: str | Path,
) -> ReceiptVerificationResult:
    """Independently verify a parent plus every exact child receipt."""

    root_path = Path(root).resolve()
    receipt_root_path = Path(receipt_root).resolve()
    parent = (
        load_evidence_receipt(receipt, root_path, output_directory=receipt_root_path)
        if isinstance(receipt, str)
        else receipt
    )
    proof_path = _proof_path(receipt_root_path, parent)
    if proof_path is None or not proof_path.is_file():
        return verify_evidence_receipt(parent, None)
    try:
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        contracts = tuple(
            ValidationOwnerContract.from_dict(item)
            for item in proof.get("contracts", ())
        )
        contracts = topological_owner_contracts(contracts)
        plan_rows = tuple(
            ValidationOwnerPlanRow(
                owner_id=str(item.get("owner_id", "")),
                disposition=str(item.get("disposition", "")),
                owner_identity=str(item.get("owner_identity", "")),
                reason=str(item.get("reason", "")),
                receipt_id=str(item.get("receipt_id", "")),
                receipt_fingerprint=str(item.get("receipt_fingerprint", "")),
                findings=tuple(str(value) for value in item.get("findings", ())),
            )
            for item in proof.get("owner_plan", ())
            if isinstance(item, Mapping)
        )
    except (OSError, ValueError, json.JSONDecodeError, TypeError):
        return verify_evidence_receipt(parent, None)
    child_receipts: dict[str, EvidenceReceipt] = {}
    child_results: dict[str, ReceiptVerificationResult] = {}
    for requirement in parent.required_child_receipts:
        try:
            child = load_evidence_receipt(
                requirement.receipt_id,
                root_path,
                output_directory=receipt_root_path,
            )
        except (OSError, ValueError):
            continue
        contract = next(
            (
                item
                for item in contracts
                if f"validation-owner:{item.owner_id}" == child.subject_id
            ),
            None,
        )
        if contract is None:
            continue
        try:
            current = build_owner_current(
                root_path,
                contract,
                all_contracts=contracts,
            )
            child_context = build_owner_receipt_context(
                current,
                child,
                receipt_root_path,
            )
            child_result = verify_evidence_receipt(child, child_context)
        except (OSError, ValueError):
            continue
        child_receipts[child.receipt_id] = child
        child_results[child.receipt_id] = child_result
    validation_manifest = validation_input_manifest(root_path)
    validation_snapshot = snapshot_bytes(
        "input:validation-parent:validation-input-manifest",
        _canonical_bytes([dict(item) for item in validation_manifest]),
        path_token="<WORKSPACE>/<VALIDATION_INPUT_MANIFEST>",
        obligation_ids=parent.covered_obligations,
    )
    tree_manifest = release_tree_manifest(root_path)
    tree_snapshot = snapshot_bytes(
        "input:validation-parent:release-tree-manifest",
        _canonical_bytes([dict(item) for item in tree_manifest]),
        path_token="<WORKSPACE>/<RELEASE_TREE_MANIFEST>",
        obligation_ids=parent.covered_obligations,
    )
    try:
        currents = {
            contract.owner_id: build_owner_current(
                root_path,
                contract,
                all_contracts=contracts,
            )
            for contract in contracts
        }
        validation_fingerprint = manifest_fingerprint(validation_manifest)
        tree_fingerprint = manifest_fingerprint(tree_manifest)
        plan_payload = {
            "schema_version": OWNER_PLAN_SCHEMA,
            "contracts": [
                {
                    **item.to_dict(),
                    "command": list(
                        tokenize_command(item.command, workspace_root=root_path)
                    ),
                }
                for item in contracts
            ],
            "owner_identities": {
                owner_id: current.owner_identity
                for owner_id, current in sorted(currents.items())
            },
            "validation_input_manifest_fingerprint": validation_fingerprint,
            "release_tree_manifest_fingerprint": tree_fingerprint,
        }
        owner_plan = ValidationOwnerPlan(
            contracts=contracts,
            rows=plan_rows,
            owner_currents=currents,
            reusable_receipts={},
            validation_input_manifest=validation_manifest,
            validation_input_manifest_fingerprint=validation_fingerprint,
            release_tree_manifest=tree_manifest,
            release_tree_manifest_fingerprint=tree_fingerprint,
            plan_fingerprint=fingerprint_value(plan_payload),
        )
        parent_current = build_validation_parent_current(root_path, owner_plan)
    except (OSError, ValueError):
        return verify_evidence_receipt(parent, None)
    if (
        str(parent.metadata.get("parent_identity", ""))
        != parent_current.parent_identity
        or str(proof.get("parent_identity", "")) != parent_current.parent_identity
        or str(proof.get("owner_plan_fingerprint", ""))
        != owner_plan.plan_fingerprint
    ):
        return verify_evidence_receipt(parent, None)
    proof_fingerprint = _sha256_bytes(proof_path.read_bytes())
    context = ReceiptVerificationContext(
        input_snapshots={
            validation_snapshot.artifact_id: validation_snapshot,
            tree_snapshot.artifact_id: tree_snapshot,
        },
        contract_hash=parent_current.contract_hash,
        check_manifest_hash=parent_current.check_manifest_hash,
        suite_map_hash=parent_current.suite_map_hash,
        producer_id="validation-parent:full",
        producer_version=_package_version(),
        environment_fingerprint=parent_current.environment_fingerprint,
        proof_artifact_fingerprint=proof_fingerprint,
        result_fingerprint=proof_fingerprint,
        command=("python", "scripts/check_flowguard_skill_suite.py", "--scope", "full"),
        working_directory_token="<WORKSPACE>",
        proof_artifact_id="proof:validation-parent:full",
        required_obligation_ids=parent.covered_obligations,
        eligible_claim_scopes=(OWNER_RECEIPT_SCOPE,),
        child_receipts=child_receipts,
        child_verification_results=child_results,
        receipt_store_repository_root=str(root_path),
        receipt_store_output_directory=str(receipt_root_path),
    )
    return verify_evidence_receipt(parent, context)


def find_reusable_parent_receipt(
    parent_current: ValidationParentCurrent,
    root: str | Path,
    receipt_root: str | Path,
) -> tuple[EvidenceReceipt | None, ReceiptVerificationResult | None]:
    """Resolve an exact-current full parent before considering child execution."""

    candidates = [
        receipt
        for receipt in list_evidence_receipts(root, output_directory=receipt_root)
        if receipt.subject_id == "validation-parent:full"
        and str(receipt.metadata.get("parent_identity", ""))
        == parent_current.parent_identity
    ]
    candidates.sort(key=lambda item: item.finished_at, reverse=True)
    verified: list[tuple[EvidenceReceipt, ReceiptVerificationResult]] = []
    last_result: ReceiptVerificationResult | None = None
    for candidate in candidates:
        result = verify_parent_receipt(candidate, root, receipt_root)
        last_result = result
        if result.ok:
            verified.append((candidate, result))
    if len(verified) > 1:
        raise ValueError("ambiguous exact-current validation parent receipts")
    return verified[0] if verified else (None, last_result)


__all__ = [
    "OWNER_BLOCKED",
    "OWNER_DISPOSITIONS",
    "OWNER_EXECUTE",
    "OWNER_REUSE_CURRENT",
    "ValidationOwnerContract",
    "ValidationOwnerCurrent",
    "ValidationOwnerObservation",
    "ValidationObservationFreshness",
    "ValidationOwnerPlan",
    "ValidationOwnerPlanRow",
    "ValidationParentCurrent",
    "assert_validation_owner_receipt_integrity",
    "assert_validation_owner_observation_fresh",
    "assert_validation_owner_observation_receipts_fresh",
    "build_child_bound_owner_receipt_context",
    "build_owner_current",
    "build_owner_receipt_context",
    "build_validation_owner_plan",
    "build_validation_parent_current",
    "child_from_owner_receipt",
    "find_reusable_parent_receipt",
    "find_reusable_owner_receipt",
    "filter_resolved_input_manifest",
    "governed_source_manifest",
    "manifest_fingerprint",
    "model_authority_release_paths",
    "observe_validation_owners",
    "plan_validation_owners",
    "release_tree_manifest",
    "resolve_input_manifest",
    "record_validation_owner_nonpass",
    "refresh_validation_owner_observation_receipts",
    "save_child_bound_owner_receipt",
    "save_child_bound_owner_receipt_from_observation",
    "save_parent_receipt",
    "topological_owner_contracts",
    "validation_input_manifest",
    "verify_parent_receipt",
]
