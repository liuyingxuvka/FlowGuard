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
from pathlib import Path
import re
import subprocess
import tomllib
from typing import Any, Iterable, Mapping, Sequence

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
OWNER_RECEIPT_SCHEMA = "flowguard.validation_owner_receipt.v1"
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


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _content_addressed_receipt_id(prefix: str, receipt: EvidenceReceipt) -> str:
    payload = receipt.to_dict()
    payload["receipt_id"] = "<CONTENT_ADDRESS>"
    digest = fingerprint_value(payload).split(":", 1)[1]
    return f"{prefix}:{digest[:32]}"


def _assert_owner_receipt_integrity(receipt: EvidenceReceipt) -> None:
    expected = _content_addressed_receipt_id(
        f"receipt:validation-owner:{receipt.subject_id.removeprefix('validation-owner:')}",
        receipt,
    )
    if receipt.receipt_id != expected:
        raise ValueError(
            f"validation owner receipt content address mismatch: {receipt.receipt_id}"
        )


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


def resolve_input_manifest(
    root: str | Path,
    patterns: Sequence[str],
) -> tuple[dict[str, str], ...]:
    """Resolve declared patterns to a deterministic content manifest."""

    root_path = Path(root).resolve()
    rows: dict[str, str] = {}
    for pattern in tuple(dict.fromkeys(str(item) for item in patterns if str(item))):
        for path in root_path.glob(pattern):
            if not path.is_file():
                continue
            resolved = path.resolve()
            try:
                relative = resolved.relative_to(root_path).as_posix()
            except ValueError as exc:
                raise ValueError(f"validation input escapes repository: {path}") from exc
            if _is_evidence_output(relative):
                continue
            rows[relative] = source_file_fingerprint(resolved)
    return tuple({"path": path, "sha256": rows[path]} for path in sorted(rows))


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
    root_path = Path(root).resolve()
    manifest = tuple(
        sorted(
            (
                *resolve_input_manifest(root_path, contract.input_patterns),
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
        "python_implementation": __import__("platform").python_implementation(),
        "python_version": __import__("platform").python_version(),
        "platform_system": __import__("platform").system(),
        "platform_machine": __import__("platform").machine(),
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
) -> tuple[EvidenceReceipt | None, ReceiptVerificationResult | None]:
    subject_id = f"validation-owner:{current.contract.owner_id}"
    candidates = [
        item
        for item in list_evidence_receipts(root, output_directory=receipt_root)
        if item.subject_id == subject_id
    ]
    candidates.sort(key=lambda item: item.finished_at, reverse=True)
    last_result: ReceiptVerificationResult | None = None
    exact_current: list[EvidenceReceipt] = []
    for receipt in candidates:
        _assert_owner_receipt_integrity(receipt)
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
    ordered_contracts = topological_owner_contracts(contracts)
    currents: dict[str, ValidationOwnerCurrent] = {}
    reusable: dict[str, EvidenceReceipt] = {}
    rows: list[ValidationOwnerPlanRow] = []
    for contract in ordered_contracts:
        try:
            current = build_owner_current(
                root,
                contract,
                all_contracts=ordered_contracts,
            )
            currents[contract.owner_id] = current
            receipt, result = find_reusable_owner_receipt(
                current,
                root,
                receipt_root,
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
            reusable[contract.owner_id] = receipt
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
                finding.code for finding in (result.findings if result is not None else ())
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
    return tuple(rows), currents, reusable


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
            "python_implementation": __import__("platform").python_implementation(),
            "python_version": __import__("platform").python_version(),
            "platform_system": __import__("platform").system(),
            "platform_machine": __import__("platform").machine(),
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


def save_owner_receipt(
    current: ValidationOwnerCurrent,
    child: ValidationChildResult,
    root: str | Path,
    receipt_root: str | Path,
    *,
    started_at: str,
    finished_at: str,
) -> EvidenceReceipt:
    receipt_root_path = Path(receipt_root).resolve()
    proof_payload = {
        "schema_version": OWNER_RECEIPT_SCHEMA,
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
    proof_dir.mkdir(parents=True, exist_ok=True)
    proof_name = proof_fingerprint.split(":", 1)[1] + ".json"
    proof_path = proof_dir / proof_name
    if proof_path.exists() and proof_path.read_bytes() != proof_bytes:
        raise ValueError("content-addressed validation proof collision")
    if not proof_path.exists():
        proof_path.write_bytes(proof_bytes)
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
        },
    )
    receipt = replace(
        receipt,
        receipt_id=_content_addressed_receipt_id(
            f"receipt:validation-owner:{current.contract.owner_id}",
            receipt,
        ),
    )
    save_evidence_receipt(receipt, root, output_directory=receipt_root_path)
    return receipt


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
    "ValidationOwnerPlan",
    "ValidationOwnerPlanRow",
    "ValidationParentCurrent",
    "build_owner_current",
    "build_owner_receipt_context",
    "build_validation_owner_plan",
    "build_validation_parent_current",
    "child_from_owner_receipt",
    "find_reusable_parent_receipt",
    "find_reusable_owner_receipt",
    "governed_source_manifest",
    "manifest_fingerprint",
    "model_authority_release_paths",
    "plan_validation_owners",
    "release_tree_manifest",
    "resolve_input_manifest",
    "save_owner_receipt",
    "save_parent_receipt",
    "topological_owner_contracts",
    "validation_input_manifest",
    "verify_parent_receipt",
]
