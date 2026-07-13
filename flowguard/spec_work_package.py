"""Provider-neutral specification work packages for development-process governance.

The objects in this module bridge a specification provider's native task list
to existing FlowGuard process, plan, and test owners.  They deliberately do not
replace OpenSpec, Spec Kit, or another provider's verification/archive state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Sequence

from .behavior_plane import BCL_PLANE_AGENT_OPERATION, BCL_PLANE_DEVELOPMENT_PROCESS
from .export import to_jsonable


SPEC_PROVIDER_OPEN_SPEC = "openspec"
SPEC_PROVIDER_SPEC_KIT = "speckit"
SPEC_PROVIDER_IDS = (SPEC_PROVIDER_OPEN_SPEC, SPEC_PROVIDER_SPEC_KIT)

SPEC_PROVIDER_MODE_NATIVE = "native"
SPEC_PROVIDER_MODE_ARTIFACT_ONLY = "artifact_only"
SPEC_PROVIDER_MODE_UNAVAILABLE = "unavailable"
SPEC_PROVIDER_MODES = (
    SPEC_PROVIDER_MODE_NATIVE,
    SPEC_PROVIDER_MODE_ARTIFACT_ONLY,
    SPEC_PROVIDER_MODE_UNAVAILABLE,
)

SPEC_BINDING_DIRECT = "direct"
SPEC_BINDING_INFRASTRUCTURE = "infrastructure"
SPEC_BINDING_SCOPED_OUT = "scoped_out"
SPEC_BINDING_KINDS = (
    SPEC_BINDING_DIRECT,
    SPEC_BINDING_INFRASTRUCTURE,
    SPEC_BINDING_SCOPED_OUT,
)

SPEC_REVIEW_READY = "ready"
SPEC_REVIEW_BLOCKED = "blocked"

SPEC_SNAPSHOT_LIVE_SCOPED = "live-scoped"
SPEC_SNAPSHOT_FROZEN_REQUIRED = "frozen-required"
SPEC_SNAPSHOT_POLICIES = (
    SPEC_SNAPSHOT_LIVE_SCOPED,
    SPEC_SNAPSHOT_FROZEN_REQUIRED,
)

SPEC_EXECUTION_DIRECT = "direct"
SPEC_EXECUTION_AGGREGATE_CHILD_RECEIPTS = "aggregate-child-receipts"
SPEC_EXECUTION_UNCOVERED_REMAINDER = "uncovered-remainder"
SPEC_EXECUTION_MODES = (
    SPEC_EXECUTION_DIRECT,
    SPEC_EXECUTION_AGGREGATE_CHILD_RECEIPTS,
    SPEC_EXECUTION_UNCOVERED_REMAINDER,
)


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,)
    return tuple(str(value) for value in values)


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


def _as_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


@dataclass(frozen=True)
class SpecProviderRef:
    """One bounded, read-only specification provider reference."""

    provider_id: str
    root_token: str
    mode: str = SPEC_PROVIDER_MODE_ARTIFACT_ONLY
    native_task_authority: bool = True
    native_verification_authority: bool = True
    native_archive_authority: bool = True
    adapter_version: str = "1.0"
    provider_version: str = ""
    schema_version: str = ""
    available: bool = True
    current: bool = True
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", str(self.provider_id))
        object.__setattr__(self, "root_token", str(self.root_token).replace("\\", "/"))
        object.__setattr__(self, "mode", str(self.mode))
        object.__setattr__(self, "adapter_version", str(self.adapter_version))
        object.__setattr__(self, "provider_version", str(self.provider_version))
        default_schema = "artifact-v1" if self.provider_id == SPEC_PROVIDER_SPEC_KIT else ""
        object.__setattr__(self, "schema_version", str(self.schema_version or default_schema))
        object.__setattr__(self, "available", bool(self.available))
        object.__setattr__(self, "current", bool(self.current))
        object.__setattr__(self, "diagnostics", _as_tuple(self.diagnostics))

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "root_token": self.root_token,
            "mode": self.mode,
            "native_task_authority": self.native_task_authority,
            "native_verification_authority": self.native_verification_authority,
            "native_archive_authority": self.native_archive_authority,
            "adapter_version": self.adapter_version,
            "provider_version": self.provider_version,
            "schema_version": self.schema_version,
            "available": self.available,
            "current": self.current,
            "diagnostics": list(self.diagnostics),
        }


@dataclass(frozen=True)
class SpecConsumerRef:
    """One stable consumer of a check receipt; consumers are not executions."""

    consumer_id: str
    task_ids: tuple[str, ...] = ()
    obligation_ids: tuple[str, ...] = ()
    check_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "consumer_id", str(self.consumer_id))
        object.__setattr__(self, "task_ids", _unique(_as_tuple(self.task_ids)))
        object.__setattr__(self, "obligation_ids", _unique(_as_tuple(self.obligation_ids)))
        object.__setattr__(self, "check_id", str(self.check_id))

    def to_dict(self) -> dict[str, Any]:
        return {
            "consumer_id": self.consumer_id,
            "task_ids": list(self.task_ids),
            "obligation_ids": list(self.obligation_ids),
            "check_id": self.check_id,
        }


@dataclass(frozen=True)
class SpecScopedOutReason:
    """Typed explanation for a provider task deliberately outside this package."""

    reason_id: str
    task_ids: tuple[str, ...]
    owner_id: str
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_id", str(self.reason_id))
        object.__setattr__(self, "task_ids", _unique(_as_tuple(self.task_ids)))
        object.__setattr__(self, "owner_id", str(self.owner_id))
        object.__setattr__(self, "reason", str(self.reason))

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason_id": self.reason_id,
            "task_ids": list(self.task_ids),
            "owner_id": self.owner_id,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SpecTask:
    """One provider-owned task; completion remains provider-native state."""

    task_id: str
    title: str
    completed: bool = False
    source_ref: str = ""
    in_scope: bool = True
    scoped_out_reason: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", str(self.task_id))
        object.__setattr__(self, "title", str(self.title))
        object.__setattr__(self, "source_ref", str(self.source_ref).replace("\\", "/"))
        object.__setattr__(self, "scoped_out_reason", str(self.scoped_out_reason))
        object.__setattr__(self, "metadata", _as_mapping(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "completed": self.completed,
            "task_definition_fingerprint": self.task_definition_fingerprint,
            "progress_state": "checked" if self.completed else "unchecked",
            "source_ref": self.source_ref,
            "in_scope": self.in_scope,
            "scoped_out_reason": self.scoped_out_reason,
            "metadata": to_jsonable(dict(self.metadata)),
        }

    @property
    def task_definition_fingerprint(self) -> str:
        """Fingerprint the task definition without treating checkbox progress as definition."""

        payload = {
            "task_id": self.task_id,
            "title": self.title,
            "source_ref": self.source_ref,
            "in_scope": self.in_scope,
            "scoped_out_reason": self.scoped_out_reason,
        }
        canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


@dataclass(frozen=True)
class SpecObligation:
    """One provider verification obligation, distinct from a provider task."""

    obligation_id: str
    source_ref: str = ""
    claim: str = ""
    required: bool = True
    check_ids: tuple[str, ...] = ()
    flowguard_obligation_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "obligation_id", str(self.obligation_id))
        object.__setattr__(self, "source_ref", str(self.source_ref).replace("\\", "/"))
        object.__setattr__(self, "claim", str(self.claim))
        object.__setattr__(self, "check_ids", _unique(_as_tuple(self.check_ids)))
        object.__setattr__(
            self,
            "flowguard_obligation_ids",
            _unique(_as_tuple(self.flowguard_obligation_ids)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "source_ref": self.source_ref,
            "claim": self.claim,
            "required": self.required,
            "check_ids": list(self.check_ids),
            "flowguard_obligation_ids": list(self.flowguard_obligation_ids),
        }


@dataclass(frozen=True)
class SpecCheckDefinition:
    """One provider-declared check and its stable validation identity."""

    check_id: str
    command: tuple[str, ...] = ()
    required: bool = True
    obligation_ids: tuple[str, ...] = ()
    validation_obligation_ids: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    timeout_seconds: int = 600
    cross_change_safe: bool = False
    expected_exit_code: int = 0
    semantic_check_id: str = ""
    execution_owner_id: str = "flowguard.spec_check_cache"
    input_paths: tuple[str, ...] = ()
    dependency_input_ids: tuple[str, ...] = ()
    snapshot_policy: str = SPEC_SNAPSHOT_LIVE_SCOPED
    execution_mode: str = SPEC_EXECUTION_DIRECT
    parent_check_id: str = ""
    child_check_ids: tuple[str, ...] = ()
    coverage_ids: tuple[str, ...] = ()
    kind: str = "command"
    declared_execution_id: str = ""
    receipt_owner_check_id: str = ""
    external_receipt_ref: Mapping[str, str] = field(default_factory=dict)
    consumer_ids: tuple[str, ...] = ()
    validation_scope: str = "full"
    toolchain_identity: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "check_id", str(self.check_id))
        object.__setattr__(self, "command", _as_tuple(self.command))
        object.__setattr__(self, "obligation_ids", _unique(_as_tuple(self.obligation_ids)))
        object.__setattr__(
            self,
            "validation_obligation_ids",
            _unique(_as_tuple(self.validation_obligation_ids)),
        )
        object.__setattr__(self, "depends_on", _unique(_as_tuple(self.depends_on)))
        object.__setattr__(self, "timeout_seconds", int(self.timeout_seconds))
        object.__setattr__(self, "expected_exit_code", int(self.expected_exit_code))
        object.__setattr__(self, "semantic_check_id", str(self.semantic_check_id or self.check_id))
        object.__setattr__(self, "execution_owner_id", str(self.execution_owner_id))
        object.__setattr__(
            self,
            "input_paths",
            _unique(tuple(str(value).replace("\\", "/") for value in _as_tuple(self.input_paths))),
        )
        object.__setattr__(self, "dependency_input_ids", _unique(_as_tuple(self.dependency_input_ids)))
        snapshot_aliases = {
            "live": SPEC_SNAPSHOT_LIVE_SCOPED,
            "frozen": SPEC_SNAPSHOT_FROZEN_REQUIRED,
        }
        object.__setattr__(
            self,
            "snapshot_policy",
            snapshot_aliases.get(str(self.snapshot_policy), str(self.snapshot_policy)),
        )
        object.__setattr__(self, "execution_mode", str(self.execution_mode))
        object.__setattr__(self, "parent_check_id", str(self.parent_check_id))
        object.__setattr__(self, "child_check_ids", _unique(_as_tuple(self.child_check_ids)))
        object.__setattr__(self, "coverage_ids", _unique(_as_tuple(self.coverage_ids)))
        object.__setattr__(self, "kind", str(self.kind))
        object.__setattr__(self, "declared_execution_id", str(self.declared_execution_id))
        object.__setattr__(self, "receipt_owner_check_id", str(self.receipt_owner_check_id))
        object.__setattr__(
            self,
            "external_receipt_ref",
            dict(sorted((str(k), str(v)) for k, v in self.external_receipt_ref.items())),
        )
        object.__setattr__(self, "consumer_ids", _unique(_as_tuple(self.consumer_ids)))
        object.__setattr__(self, "validation_scope", str(self.validation_scope))
        object.__setattr__(self, "toolchain_identity", str(self.toolchain_identity))

    def execution_definition_dict(self) -> dict[str, Any]:
        """Canonical semantic execution definition, excluding provider-local consumers."""

        return {
            "semantic_check_id": self.semantic_check_id,
            "execution_owner_id": self.execution_owner_id,
            "command": list(self.command),
            "validation_obligation_ids": sorted(self.validation_obligation_ids),
            "depends_on": sorted(self.depends_on),
            "dependency_input_ids": sorted(self.dependency_input_ids),
            "input_paths": sorted(self.input_paths),
            "snapshot_policy": self.snapshot_policy,
            "execution_mode": self.execution_mode,
            "parent_check_id": self.parent_check_id,
            "child_check_ids": sorted(self.child_check_ids),
            "coverage_ids": sorted(self.coverage_ids),
            "kind": self.kind,
            "receipt_owner_check_id": self.receipt_owner_check_id,
            "external_receipt_ref": dict(self.external_receipt_ref),
            "consumer_ids": sorted(self.consumer_ids),
            "validation_scope": self.validation_scope,
            "toolchain_identity": self.toolchain_identity,
            "timeout_seconds": self.timeout_seconds,
            "cross_change_safe": self.cross_change_safe,
            "expected_exit_code": self.expected_exit_code,
        }

    @property
    def execution_definition_id(self) -> str:
        canonical = json.dumps(
            self.execution_definition_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        return f"execution-definition:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"

    @property
    def execution_id(self) -> str:
        """Stable local declaration identity; distinct from the input-bound execution key."""

        return self.declared_execution_id or self.execution_definition_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "command": list(self.command),
            "required": self.required,
            "obligation_ids": list(self.obligation_ids),
            "validation_obligation_ids": list(self.validation_obligation_ids),
            "depends_on": list(self.depends_on),
            "timeout_seconds": self.timeout_seconds,
            "cross_change_safe": self.cross_change_safe,
            "expected_exit_code": self.expected_exit_code,
            "semantic_check_id": self.semantic_check_id,
            "execution_owner_id": self.execution_owner_id,
            "execution_definition_id": self.execution_definition_id,
            "execution_id": self.execution_id,
            "input_paths": list(self.input_paths),
            "dependency_input_ids": list(self.dependency_input_ids),
            "snapshot_policy": self.snapshot_policy,
            "execution_mode": self.execution_mode,
            "parent_check_id": self.parent_check_id,
            "child_check_ids": list(self.child_check_ids),
            "coverage_ids": list(self.coverage_ids),
            "kind": self.kind,
            "declared_execution_id": self.declared_execution_id,
            "receipt_owner_check_id": self.receipt_owner_check_id,
            "external_receipt_ref": dict(self.external_receipt_ref),
            "consumer_ids": list(self.consumer_ids),
            "validation_scope": self.validation_scope,
            "toolchain_identity": self.toolchain_identity,
        }


@dataclass(frozen=True)
class SpecTaskObligationBinding:
    """A typed bidirectional mapping row between tasks and governed evidence."""

    binding_id: str
    task_ids: tuple[str, ...] = ()
    obligation_ids: tuple[str, ...] = ()
    check_ids: tuple[str, ...] = ()
    binding_kind: str = SPEC_BINDING_DIRECT
    owner_id: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding_id", str(self.binding_id))
        object.__setattr__(self, "task_ids", _unique(_as_tuple(self.task_ids)))
        object.__setattr__(self, "obligation_ids", _unique(_as_tuple(self.obligation_ids)))
        object.__setattr__(self, "check_ids", _unique(_as_tuple(self.check_ids)))
        object.__setattr__(self, "binding_kind", str(self.binding_kind))
        object.__setattr__(self, "owner_id", str(self.owner_id))
        object.__setattr__(self, "reason", str(self.reason))

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "task_ids": list(self.task_ids),
            "obligation_ids": list(self.obligation_ids),
            "check_ids": list(self.check_ids),
            "binding_kind": self.binding_kind,
            "owner_id": self.owner_id,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SpecWorkPackage:
    """Provider-neutral projection of one native specification change."""

    provider: SpecProviderRef
    work_package_id: str
    change_id: str
    behavior_plane: str = BCL_PLANE_DEVELOPMENT_PROCESS
    tasks: tuple[SpecTask, ...] = ()
    obligations: tuple[SpecObligation, ...] = ()
    checks: tuple[SpecCheckDefinition, ...] = ()
    bindings: tuple[SpecTaskObligationBinding, ...] = ()
    artifact_refs: tuple[str, ...] = ()
    provider_status: str = "active"
    provider_verified: bool = False
    provider_archive_ready: bool = False
    target_commitment_ids: tuple[str, ...] = ()
    typed_relation_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "work_package_id", str(self.work_package_id))
        object.__setattr__(self, "change_id", str(self.change_id))
        object.__setattr__(self, "behavior_plane", str(self.behavior_plane))
        object.__setattr__(self, "tasks", tuple(self.tasks))
        object.__setattr__(self, "obligations", tuple(self.obligations))
        object.__setattr__(self, "checks", tuple(self.checks))
        object.__setattr__(self, "bindings", tuple(self.bindings))
        object.__setattr__(self, "artifact_refs", _unique(_as_tuple(self.artifact_refs)))
        object.__setattr__(self, "provider_status", str(self.provider_status))
        object.__setattr__(self, "target_commitment_ids", _unique(_as_tuple(self.target_commitment_ids)))
        object.__setattr__(self, "typed_relation_ids", _unique(_as_tuple(self.typed_relation_ids)))
        object.__setattr__(self, "metadata", _as_mapping(self.metadata))

    @property
    def package_key(self) -> str:
        return f"{self.provider.provider_id}:{self.work_package_id}"

    def consumer_refs(self) -> tuple[SpecConsumerRef, ...]:
        rows: list[SpecConsumerRef] = []
        for binding in self.bindings:
            for check_id in binding.check_ids:
                rows.append(
                    SpecConsumerRef(
                        consumer_id=(
                            f"consumer:{self.provider.provider_id}:{self.work_package_id}:"
                            f"{binding.binding_id}:{check_id}"
                        ),
                        task_ids=binding.task_ids,
                        obligation_ids=binding.obligation_ids,
                        check_id=check_id,
                    )
                )
        return tuple(rows)

    def scoped_out_reasons(self) -> tuple[SpecScopedOutReason, ...]:
        return tuple(
            SpecScopedOutReason(binding.binding_id, binding.task_ids, binding.owner_id, binding.reason)
            for binding in self.bindings
            if binding.binding_kind == SPEC_BINDING_SCOPED_OUT
        )

    def identity_dict(self) -> dict[str, Any]:
        """Language-neutral identity; prose and localized display text are excluded."""

        return {
            "spec_provider_id": self.provider.provider_id,
            "provider_version": self.provider.provider_version,
            "adapter_version": self.provider.adapter_version,
            "schema_version": self.provider.schema_version,
            "work_package_id": self.work_package_id,
            "change_id": self.change_id,
            "behavior_plane": self.behavior_plane,
            "task_ids": sorted(task.task_id for task in self.tasks),
            "obligation_ids": sorted(item.obligation_id for item in self.obligations),
            "check_definitions": [
                {
                    "check_id": check.check_id,
                    **check.execution_definition_dict(),
                    "obligation_ids": sorted(check.obligation_ids),
                    "execution_definition_id": check.execution_definition_id,
                    "execution_id": check.execution_id,
                }
                for check in sorted(self.checks, key=lambda item: item.check_id)
            ],
            "bindings": [
                {
                    "binding_id": binding.binding_id,
                    "task_ids": sorted(binding.task_ids),
                    "obligation_ids": sorted(binding.obligation_ids),
                    "check_ids": sorted(binding.check_ids),
                    "binding_kind": binding.binding_kind,
                    "owner_id": binding.owner_id,
                }
                for binding in sorted(self.bindings, key=lambda item: item.binding_id)
            ],
        }

    @property
    def identity_fingerprint(self) -> str:
        payload = json.dumps(self.identity_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider.to_dict(),
            "work_package_id": self.work_package_id,
            "change_id": self.change_id,
            "behavior_plane": self.behavior_plane,
            "tasks": [task.to_dict() for task in self.tasks],
            "obligations": [item.to_dict() for item in self.obligations],
            "checks": [check.to_dict() for check in self.checks],
            "bindings": [binding.to_dict() for binding in self.bindings],
            "consumers": [consumer.to_dict() for consumer in self.consumer_refs()],
            "scoped_out_reasons": [reason.to_dict() for reason in self.scoped_out_reasons()],
            "identity_fingerprint": self.identity_fingerprint,
            "artifact_refs": list(self.artifact_refs),
            "provider_status": self.provider_status,
            "provider_verified": self.provider_verified,
            "provider_archive_ready": self.provider_archive_ready,
            "target_commitment_ids": list(self.target_commitment_ids),
            "typed_relation_ids": list(self.typed_relation_ids),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class SpecWorkPackageFinding:
    code: str
    message: str
    subject_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "subject_ids", _unique(_as_tuple(self.subject_ids)))

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "subject_ids": list(self.subject_ids)}


@dataclass(frozen=True)
class SpecWorkPackageReview:
    provider_id: str
    work_package_id: str
    status: str
    findings: tuple[SpecWorkPackageFinding, ...]
    task_count: int
    completed_task_count: int
    obligation_count: int
    check_count: int
    mapped_task_ids: tuple[str, ...]
    mapped_obligation_ids: tuple[str, ...]
    mapped_check_ids: tuple[str, ...]
    archive_ready: bool
    claim_boundary: str = (
        "Development-process reconciliation only; the specification provider retains task, "
        "verification, and archive authority."
    )

    @property
    def reconciliation_report_id(self) -> str:
        return f"spec-reconciliation:{self.provider_id}:{self.work_package_id}"

    @property
    def reconciliation_fingerprint(self) -> str:
        payload = {
            "provider_id": self.provider_id,
            "work_package_id": self.work_package_id,
            "status": self.status,
            "finding_codes": sorted(self.finding_codes),
            "mapped_task_ids": sorted(self.mapped_task_ids),
            "mapped_obligation_ids": sorted(self.mapped_obligation_ids),
            "mapped_check_ids": sorted(self.mapped_check_ids),
        }
        canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"

    @property
    def ok(self) -> bool:
        return self.status == SPEC_REVIEW_READY and not self.findings

    @property
    def finding_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "work_package_id": self.work_package_id,
            "status": self.status,
            "ok": self.ok,
            "finding_codes": list(self.finding_codes),
            "findings": [finding.to_dict() for finding in self.findings],
            "task_count": self.task_count,
            "completed_task_count": self.completed_task_count,
            "obligation_count": self.obligation_count,
            "check_count": self.check_count,
            "mapped_task_ids": list(self.mapped_task_ids),
            "mapped_obligation_ids": list(self.mapped_obligation_ids),
            "mapped_check_ids": list(self.mapped_check_ids),
            "archive_ready": self.archive_ready,
            "reconciliation_report_id": self.reconciliation_report_id,
            "reconciliation_fingerprint": self.reconciliation_fingerprint,
            "claim_boundary": self.claim_boundary,
        }

    def format_text(self) -> str:
        lines = [
            f"Spec Work Package: {self.provider_id}:{self.work_package_id}",
            f"status: {self.status}",
            f"tasks: {self.completed_task_count}/{self.task_count}",
            f"obligations: {len(self.mapped_obligation_ids)}/{self.obligation_count}",
            f"checks: {len(self.mapped_check_ids)}/{self.check_count}",
            f"archive_ready: {str(self.archive_ready).lower()}",
        ]
        lines.extend(f"- {finding.code}: {finding.message}" for finding in self.findings)
        return "\n".join(lines)


def _duplicate_ids(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return tuple(duplicates)


def review_spec_work_package(package: SpecWorkPackage) -> SpecWorkPackageReview:
    """Check provider authority, plane separation, and bidirectional coverage."""

    findings: list[SpecWorkPackageFinding] = []
    if package.provider.provider_id not in SPEC_PROVIDER_IDS:
        findings.append(SpecWorkPackageFinding("unknown_spec_provider", "provider id is not supported"))
    if package.provider.mode not in SPEC_PROVIDER_MODES:
        findings.append(SpecWorkPackageFinding("unknown_provider_mode", "provider mode is not supported"))
    if not (
        package.provider.native_task_authority
        and package.provider.native_verification_authority
        and package.provider.native_archive_authority
    ):
        findings.append(
            SpecWorkPackageFinding(
                "provider_native_authority_missing",
                "the bridge cannot take over native task, verification, or archive authority",
            )
        )
    if not package.provider.available or package.provider.mode == SPEC_PROVIDER_MODE_UNAVAILABLE:
        findings.append(SpecWorkPackageFinding("spec_provider_unavailable", "provider artifacts are unavailable"))
    if package.provider.adapter_version != "1.0":
        findings.append(
            SpecWorkPackageFinding(
                "provider_adapter_version_unsupported",
                "the provider adapter version is unsupported",
                (package.provider.adapter_version,),
            )
        )
    supported_schemas = {SPEC_PROVIDER_OPEN_SPEC: {"3"}, SPEC_PROVIDER_SPEC_KIT: {"artifact-v1"}}
    if package.provider.schema_version not in supported_schemas.get(package.provider.provider_id, set()):
        findings.append(
            SpecWorkPackageFinding(
                "provider_schema_unsupported",
                "the provider artifact schema is unsupported",
                (package.provider.schema_version or "missing",),
            )
        )
    if not package.provider.current:
        findings.append(SpecWorkPackageFinding("provider_context_stale", "provider context is not current"))
    if package.behavior_plane != BCL_PLANE_DEVELOPMENT_PROCESS:
        findings.append(
            SpecWorkPackageFinding(
                "spec_work_package_wrong_plane",
                "specification work packages must remain in development_process",
                (package.behavior_plane,),
            )
        )
    if not package.work_package_id or not package.change_id:
        findings.append(
            SpecWorkPackageFinding(
                "spec_work_package_identity_missing",
                "work_package_id and change_id are both required and remain distinct fields",
            )
        )

    task_ids = tuple(task.task_id for task in package.tasks)
    obligation_ids = tuple(item.obligation_id for item in package.obligations)
    check_ids = tuple(item.check_id for item in package.checks)
    binding_ids = tuple(item.binding_id for item in package.bindings)
    for label, duplicates in (
        ("task", _duplicate_ids(task_ids)),
        ("obligation", _duplicate_ids(obligation_ids)),
        ("check", _duplicate_ids(check_ids)),
        ("binding", _duplicate_ids(binding_ids)),
    ):
        if duplicates:
            findings.append(
                SpecWorkPackageFinding(
                    f"duplicate_{label}_identity",
                    f"{label} identities must be unique",
                    duplicates,
                )
            )

    task_set = set(task_ids)
    obligation_set = set(obligation_ids)
    check_set = set(check_ids)
    semantic_owners: dict[str, set[str]] = {}
    semantic_definitions: dict[str, set[str]] = {}
    for check in package.checks:
        if check.kind == "receipt":
            continue
        semantic_owners.setdefault(check.semantic_check_id, set()).add(check.execution_owner_id)
        semantic_definitions.setdefault(check.semantic_check_id, set()).add(check.execution_definition_id)
    for semantic_check_id in sorted(semantic_owners):
        if not semantic_check_id:
            findings.append(
                SpecWorkPackageFinding("semantic_check_id_missing", "every check needs a semantic execution identity")
            )
        if "" in semantic_owners[semantic_check_id] or len(semantic_owners[semantic_check_id]) != 1:
            findings.append(
                SpecWorkPackageFinding(
                    "semantic_check_execution_owner_conflict",
                    "one semantic check must have exactly one execution owner",
                    (semantic_check_id,),
                )
            )
        if len(semantic_definitions[semantic_check_id]) != 1:
            findings.append(
                SpecWorkPackageFinding(
                    "semantic_check_definition_conflict",
                    "one semantic check cannot name several execution definitions",
                    (semantic_check_id,),
                )
            )
    mapped_tasks: set[str] = set()
    mapped_obligations: set[str] = set()
    mapped_checks: set[str] = set()
    primary_owners: dict[str, set[str]] = {}
    for binding in package.bindings:
        if binding.binding_kind not in SPEC_BINDING_KINDS:
            findings.append(
                SpecWorkPackageFinding(
                    "unknown_spec_binding_kind",
                    f"binding {binding.binding_id} has an unknown kind",
                    (binding.binding_id,),
                )
            )
        missing_tasks = tuple(sorted(set(binding.task_ids) - task_set))
        missing_obligations = tuple(sorted(set(binding.obligation_ids) - obligation_set))
        missing_checks = tuple(sorted(set(binding.check_ids) - check_set))
        if missing_tasks or missing_obligations or missing_checks:
            findings.append(
                SpecWorkPackageFinding(
                    "spec_binding_target_missing",
                    f"binding {binding.binding_id} references undeclared identities",
                    missing_tasks + missing_obligations + missing_checks,
                )
            )
        if binding.binding_kind in {SPEC_BINDING_INFRASTRUCTURE, SPEC_BINDING_SCOPED_OUT}:
            if not binding.owner_id or not binding.reason:
                findings.append(
                    SpecWorkPackageFinding(
                        "typed_binding_reason_missing",
                        f"binding {binding.binding_id} requires an owner and reason",
                        (binding.binding_id,),
                    )
                )
        elif not binding.obligation_ids and not binding.check_ids:
            findings.append(
                SpecWorkPackageFinding(
                    "direct_binding_evidence_missing",
                    f"binding {binding.binding_id} maps no obligation or check",
                    (binding.binding_id,),
                )
            )
        mapped_tasks.update(binding.task_ids)
        mapped_obligations.update(binding.obligation_ids)
        mapped_checks.update(binding.check_ids)
        if binding.owner_id:
            for identity in binding.obligation_ids + binding.check_ids:
                primary_owners.setdefault(identity, set()).add(binding.owner_id)

    conflicting_owners = tuple(
        sorted(identity for identity, owner_ids in primary_owners.items() if len(owner_ids) > 1)
    )
    if conflicting_owners:
        findings.append(
            SpecWorkPackageFinding(
                "conflicting_primary_owner",
                "an obligation or check cannot have several primary infrastructure owners",
                conflicting_owners,
            )
        )

    # Obligation-to-check edges are also reverse mappings.  Materialize them so
    # callers never have to infer coverage from a checkbox alone.
    for obligation in package.obligations:
        unknown_checks = tuple(sorted(set(obligation.check_ids) - check_set))
        if unknown_checks:
            findings.append(
                SpecWorkPackageFinding(
                    "obligation_check_missing",
                    f"obligation {obligation.obligation_id} references undeclared checks",
                    unknown_checks,
                )
            )

    for check in package.checks:
        unknown_obligations = tuple(sorted(set(check.obligation_ids) - obligation_set))
        unknown_dependencies = tuple(sorted(set(check.depends_on) - check_set))
        unknown_children = tuple(sorted(set(check.child_check_ids) - check_set))
        if unknown_obligations:
            findings.append(
                SpecWorkPackageFinding(
                    "check_obligation_missing",
                    f"check {check.check_id} references undeclared obligations",
                    unknown_obligations,
                )
            )
        if unknown_dependencies:
            findings.append(
                SpecWorkPackageFinding(
                    "check_dependency_missing",
                    f"check {check.check_id} depends on undeclared checks",
                    unknown_dependencies,
                )
            )
        if unknown_children or (check.parent_check_id and check.parent_check_id not in check_set):
            findings.append(
                SpecWorkPackageFinding(
                    "check_receipt_topology_missing",
                    f"check {check.check_id} references undeclared parent/child checks",
                    unknown_children + ((check.parent_check_id,) if check.parent_check_id not in check_set else ()),
                )
            )
        if check.snapshot_policy not in SPEC_SNAPSHOT_POLICIES:
            findings.append(
                SpecWorkPackageFinding(
                    "check_snapshot_policy_invalid",
                    f"check {check.check_id} has an unsupported snapshot policy",
                    (check.check_id,),
                )
            )
        if check.execution_mode not in SPEC_EXECUTION_MODES:
            findings.append(
                SpecWorkPackageFinding(
                    "check_execution_mode_invalid",
                    f"check {check.check_id} has an unsupported execution mode",
                    (check.check_id,),
                )
            )
        if check.kind not in {"command", "manual", "receipt"}:
            findings.append(
                SpecWorkPackageFinding(
                    "check_kind_invalid", f"check {check.check_id} has an unsupported kind", (check.check_id,)
                )
            )
        internal_receipt_consumer = bool(
            check.receipt_owner_check_id
            and check.receipt_owner_check_id in check_set
            and check.consumer_ids
        )
        external_receipt_consumer = set(check.external_receipt_ref) == {
            "provider_id", "work_package_id", "adapter", "ref_path"
        }
        if check.kind == "receipt" and (
            check.command
            or internal_receipt_consumer == external_receipt_consumer
        ):
            findings.append(
                SpecWorkPackageFinding(
                    "receipt_consumer_contract_invalid",
                    f"receipt check {check.check_id} must use exactly one internal owner or external receipt ref and cannot execute a command",
                    (check.check_id,),
                )
            )
        if external_receipt_consumer:
            expected_path = (
                f"<SPEC_EVIDENCE>/portable-refs/{package.provider.provider_id}/"
                f"{package.work_package_id}/{check.check_id}.json"
            )
            canonical_semantics = package.metadata.get("canonical_check_semantics", {})
            canonical_check_ids = set(package.metadata.get("canonical_check_ids", ()))
            if (
                check.check_id not in canonical_check_ids
                or check.external_receipt_ref.get("provider_id") != package.provider.provider_id
                or check.external_receipt_ref.get("work_package_id") != package.work_package_id
                or check.external_receipt_ref.get("adapter") != "portable-receipt.v1"
                or check.external_receipt_ref.get("ref_path") != expected_path
                or not isinstance(canonical_semantics, Mapping)
                or canonical_semantics.get(check.check_id) != check.semantic_check_id
            ):
                findings.append(
                    SpecWorkPackageFinding(
                        "external_receipt_ref_identity_mismatch",
                        f"external receipt {check.check_id} must match its canonical FlowGuard owner identity",
                        (check.check_id,),
                    )
                )
        if check.execution_mode == SPEC_EXECUTION_AGGREGATE_CHILD_RECEIPTS and not check.child_check_ids:
            findings.append(
                SpecWorkPackageFinding(
                    "aggregate_check_children_missing",
                    f"aggregate check {check.check_id} must consume child receipt owners",
                    (check.check_id,),
                )
            )
        forbidden_provider_commands = {
            "spec-check-run": "provider_reexecutes_flowguard_owner",
            "spec-receipt-consume": "provider_reexecutes_flowguard_owner",
            "spec-session-begin": "provider_execution_lifecycle_cycle",
            "spec-session-close": "provider_execution_lifecycle_cycle",
            "spec-provider-close-review": "provider_execution_lifecycle_cycle",
        }
        if package.provider.provider_id == SPEC_PROVIDER_OPEN_SPEC and check.command:
            for command_token, finding_code in forbidden_provider_commands.items():
                if command_token in check.command:
                    findings.append(
                        SpecWorkPackageFinding(
                            finding_code,
                            f"OpenSpec check {check.check_id} cannot invoke FlowGuard owner or close lifecycle commands",
                            (check.check_id,),
                        )
                    )
        if check.timeout_seconds <= 0:
            findings.append(
                SpecWorkPackageFinding(
                    "check_timeout_missing",
                    f"check {check.check_id} requires a positive timeout",
                    (check.check_id,),
                )
            )
    # Expand only from identities that already have a task or infrastructure
    # owner.  Obligation<->check declarations alone do not create an owner.
    changed = True
    while changed:
        before = (len(mapped_obligations), len(mapped_checks))
        for obligation in package.obligations:
            if obligation.obligation_id in mapped_obligations:
                mapped_checks.update(obligation.check_ids)
        for check in package.checks:
            if check.check_id in mapped_checks:
                mapped_obligations.update(check.obligation_ids)
            elif set(check.obligation_ids) & mapped_obligations:
                mapped_checks.add(check.check_id)
        changed = before != (len(mapped_obligations), len(mapped_checks))

    required_tasks = {task.task_id for task in package.tasks if task.in_scope}
    required_obligations = {item.obligation_id for item in package.obligations if item.required}
    required_checks = {item.check_id for item in package.checks if item.required}
    for code, message, missing in (
        ("unmapped_spec_task", "in-scope provider tasks need a direct or typed mapping", required_tasks - mapped_tasks),
        (
            "unmapped_spec_obligation",
            "required provider obligations need a task or infrastructure owner",
            required_obligations - mapped_obligations,
        ),
        (
            "unmapped_spec_check",
            "required provider checks need a task/obligation or infrastructure owner",
            required_checks - mapped_checks,
        ),
    ):
        if missing:
            findings.append(SpecWorkPackageFinding(code, message, tuple(sorted(missing))))

    completed = sum(1 for task in package.tasks if task.completed)
    status = SPEC_REVIEW_READY if not findings else SPEC_REVIEW_BLOCKED
    archive_ready = (
        not findings
        and completed == len(package.tasks)
        and package.provider_verified
        and package.provider_archive_ready
    )
    return SpecWorkPackageReview(
        provider_id=package.provider.provider_id,
        work_package_id=package.work_package_id,
        status=status,
        findings=tuple(findings),
        task_count=len(package.tasks),
        completed_task_count=completed,
        obligation_count=len(package.obligations),
        check_count=len(package.checks),
        mapped_task_ids=tuple(sorted(mapped_tasks & task_set)),
        mapped_obligation_ids=tuple(sorted(mapped_obligations & obligation_set)),
        mapped_check_ids=tuple(sorted(mapped_checks & check_set)),
        archive_ready=archive_ready,
    )


def spec_work_package_preflight_context(package: SpecWorkPackage) -> dict[str, Any]:
    """Return plane-safe context consumed after ExistingModelPreflight lookup."""

    review = review_spec_work_package(package)
    return {
        "spec_provider_id": package.provider.provider_id,
        "work_package_id": package.work_package_id,
        "change_id": package.change_id,
        "behavior_plane": package.behavior_plane,
        "task_ids": [task.task_id for task in package.tasks],
        "obligation_ids": [item.obligation_id for item in package.obligations],
        "check_ids": [item.check_id for item in package.checks],
        "target_commitment_ids": list(package.target_commitment_ids),
        "typed_relation_ids": list(package.typed_relation_ids),
        "provider_version": package.provider.provider_version,
        "provider_schema_version": package.provider.schema_version,
        "provider_current": package.provider.current,
        "package_identity_fingerprint": package.identity_fingerprint,
        "reconciliation_status": review.status,
        "reconciliation_report_id": review.reconciliation_report_id,
        "reconciliation_fingerprint": review.reconciliation_fingerprint,
        "reconciliation_current": review.ok and package.provider.current,
        "provider_owns_product_behavior": False,
        "claim_boundary": (
            "Provider context follows plane-first commitment lookup and cannot own a product-runtime commitment."
        ),
    }


def spec_work_package_to_plan_detail(package: SpecWorkPackage):
    """Project provider identities into the existing PlanDetail owner."""

    from .development_process_flow import ProcessArtifact
    from .plan_detailing import (
        PLAN_DETAIL_CLAIM_SCOPED,
        PlanDetail,
        PlanDetailFailureBranch,
        PlanDetailFreshnessRule,
        PlanDetailSource,
        PlanDetailStateSurface,
        PlanDetailStep,
        PlanDetailSurface,
        PlanDetailValidation,
    )

    sources = (
        PlanDetailSource(
            source_id=f"spec-provider:{package.provider.provider_id}:{package.change_id}",
            source_kind="spec_work_package",
            current=True,
            summary="Provider-native task and verification source",
            metadata=spec_work_package_preflight_context(package),
            spec_provider_id=package.provider.provider_id,
            work_package_id=package.work_package_id,
            change_id=package.change_id,
            spec_task_ids=tuple(task.task_id for task in package.tasks),
            spec_obligation_ids=tuple(item.obligation_id for item in package.obligations),
            spec_check_ids=tuple(item.check_id for item in package.checks),
            spec_binding_ids=tuple(item.binding_id for item in package.bindings),
        ),
    )
    surfaces = tuple(
        PlanDetailSurface(
            surface_id=f"spec-task:{task.task_id}",
            surface_kind="development_process_task",
            description=task.title,
            in_scope=task.in_scope,
            included=True,
            source_ids=(sources[0].source_id,),
            out_of_scope_reason=task.scoped_out_reason,
        )
        for task in package.tasks
    )
    steps = tuple(
        PlanDetailStep(
            step_id=f"provider-task:{task.task_id}",
            action=task.title,
            step_type="provider_task",
            order_after=((f"provider-task:{package.tasks[index - 1].task_id}",) if index else ()),
            behavior_plane=BCL_PLANE_AGENT_OPERATION,
            target_behavior_planes=(BCL_PLANE_DEVELOPMENT_PROCESS,),
            target_commitment_ids=("commitment:spec-work-package-reconciliation",) + package.target_commitment_ids,
            typed_commitment_relation_refs=("relation:plans-spec-work-package",) + package.typed_relation_ids,
            spec_provider_id=package.provider.provider_id,
            work_package_id=package.work_package_id,
            change_id=package.change_id,
            spec_task_ids=(task.task_id,),
            spec_obligation_ids=tuple(
                sorted({item for binding in package.bindings if task.task_id in binding.task_ids for item in binding.obligation_ids})
            ),
            spec_check_ids=tuple(
                sorted({item for binding in package.bindings if task.task_id in binding.task_ids for item in binding.check_ids})
            ),
            spec_binding_ids=tuple(
                binding.binding_id for binding in package.bindings if task.task_id in binding.task_ids
            ),
            description="Provider task identity is preserved; completion remains provider-owned.",
        )
        for index, task in enumerate(package.tasks)
    )
    validations = tuple(
        PlanDetailValidation(
            validation_id=check.check_id,
            required_evidence_kinds=("spec_check_receipt",),
            command=" ".join(check.command),
            spec_provider_id=package.provider.provider_id,
            work_package_id=package.work_package_id,
            change_id=package.change_id,
            spec_task_ids=tuple(
                sorted({task_id for binding in package.bindings if check.check_id in binding.check_ids for task_id in binding.task_ids})
            ),
            spec_obligation_ids=check.obligation_ids,
            spec_check_ids=(check.check_id,),
            spec_binding_ids=tuple(
                binding.binding_id for binding in package.bindings if check.check_id in binding.check_ids
            ),
            description=(
                f"provider={package.provider.provider_id}; work_package={package.work_package_id}; "
                f"obligations={','.join(check.obligation_ids)}"
            ),
        )
        for check in package.checks
    )
    return PlanDetail(
        plan_id=f"spec-work-package:{package.package_key}",
        task_summary=f"Reconcile and verify {package.change_id}",
        goal="Preserve provider-native authority while binding tasks to current FlowGuard evidence.",
        sources=sources,
        surfaces=surfaces,
        artifacts=(
            ProcessArtifact(
                artifact_id=f"spec-work-package:{package.package_key}",
                artifact_type="spec_work_package",
                current_version=package.identity_fingerprint,
                path=package.provider.root_token,
                owner=package.provider.provider_id,
                spec_provider_id=package.provider.provider_id,
                work_package_id=package.work_package_id,
                spec_task_ids=tuple(task.task_id for task in package.tasks),
                spec_obligation_ids=tuple(item.obligation_id for item in package.obligations),
                spec_check_ids=tuple(item.check_id for item in package.checks),
            ),
        ),
        state_surfaces=(
            PlanDetailStateSurface(
                "spec_session_state",
                owner="development_process_flow",
                read_by_step_ids=tuple(step.step_id for step in steps),
                written_by_step_ids=tuple(step.step_id for step in steps),
                description="Begin/post freshness and terminal receipt state.",
            ),
        ),
        steps=steps,
        validations=validations,
        failure_branches=(
            PlanDetailFailureBranch(
                "spec-session-stale",
                trigger="A governed input changes or required receipt is incomplete.",
                step_id=steps[-1].step_id if steps else "",
                rework_step_id=steps[0].step_id if steps else "",
                expected_resolution="Reconcile again and begin a fresh session without rolling back peer work.",
            ),
        ),
        freshness_rules=(
            PlanDetailFreshnessRule(
                "spec-source-invalidates-session",
                f"spec-work-package:{package.package_key}",
                invalidates_evidence_kinds=("spec_check_receipt",),
                description="Canonical provider/model/test changes stale the active session.",
            ),
        ),
        final_claim=PLAN_DETAIL_CLAIM_SCOPED,
        final_evidence_ids=(),
        require_behavior_plane_boundary=True,
        metadata={"spec_work_package": package.to_dict()},
    )


def spec_work_package_to_development_process(package: SpecWorkPackage):
    """Reuse PlanDetail's existing DevelopmentProcessFlow projection."""

    from .development_process_flow import ProcessAction
    from .plan_detailing import plan_detail_to_development_process

    projected = plan_detail_to_development_process(spec_work_package_to_plan_detail(package))
    common = {
        "behavior_plane": BCL_PLANE_DEVELOPMENT_PROCESS,
        "spec_provider_id": package.provider.provider_id,
        "spec_work_package_id": package.work_package_id,
        "spec_task_ids": tuple(task.task_id for task in package.tasks),
        "spec_obligation_ids": tuple(item.obligation_id for item in package.obligations),
        "spec_check_ids": tuple(item.check_id for item in package.checks),
        "spec_binding_ids": tuple(item.binding_id for item in package.bindings),
    }
    actions: list[ProcessAction] = []
    prior = ""
    for action_id, action_type in (
        ("spec-provider-read", "spec_provider_read"),
        ("spec-reconcile", "spec_reconcile"),
        ("spec-session-begin", "spec_session_begin"),
    ):
        actions.append(ProcessAction(action_id, action_type=action_type, order_after=(prior,) if prior else (), **common))
        prior = action_id
    for check in package.checks:
        action_id = f"spec-check:{check.check_id}"
        actions.append(
            ProcessAction(
                action_id,
                action_type="spec_check",
                order_after=(prior,),
                spec_check_ids=(check.check_id,),
                spec_obligation_ids=check.obligation_ids,
                behavior_plane=BCL_PLANE_DEVELOPMENT_PROCESS,
                spec_provider_id=package.provider.provider_id,
                spec_work_package_id=package.work_package_id,
                spec_task_ids=tuple(
                    sorted({task_id for binding in package.bindings if check.check_id in binding.check_ids for task_id in binding.task_ids})
                ),
                spec_binding_ids=tuple(
                    binding.binding_id for binding in package.bindings if check.check_id in binding.check_ids
                ),
            )
        )
        prior = action_id
    for action_id, action_type in (
        ("spec-post-snapshot", "spec_post_snapshot"),
        ("spec-provider-verify", "spec_provider_verify"),
        ("spec-sync", "spec_sync"),
        ("spec-archive-ready", "spec_archive_ready"),
    ):
        actions.append(ProcessAction(action_id, action_type=action_type, order_after=(prior,), **common))
        prior = action_id
    return replace(
        projected,
        actions=tuple(actions),
        spec_work_package_ids=(package.package_key,),
        require_spec_session_close=True,
        require_spec_provider_close=True,
    )


def spec_work_package_to_test_mesh(package: SpecWorkPackage):
    """Project provider checks into the existing TestMesh child-evidence shape."""

    from .testmesh import (
        EVIDENCE_ABSTRACT_GREEN,
        TEST_LAYER_CHILD,
        TEST_STATUS_NOT_RUN,
        TestMeshPlan,
        TestPartitionItem,
        TestSuiteEvidence,
    )

    partition_items = tuple(
        TestPartitionItem(
            item_id=obligation.obligation_id,
            item_type="spec_obligation",
            owner_suite_id=next(
                (check.check_id for check in package.checks if obligation.obligation_id in check.obligation_ids),
                "",
            ),
            description=obligation.claim,
            inventory_revision=package.change_id,
        )
        for obligation in package.obligations
    )
    child_suites = tuple(
        TestSuiteEvidence(
            suite_id=check.check_id,
            command=" ".join(check.command),
            layer=TEST_LAYER_CHILD,
            result_status=TEST_STATUS_NOT_RUN,
            evidence_tier=EVIDENCE_ABSTRACT_GREEN,
            timeout_seconds=check.timeout_seconds,
            owns_state=(),
            owns_side_effects=(),
            owned_inventory_item_ids=check.obligation_ids,
            not_run_reason="Awaiting provider-session execution or exact reusable receipt.",
            covered_obligation_ids=check.validation_obligation_ids,
            artifact_version=package.change_id,
            verifier_version=package.provider.adapter_version,
            spec_consumer_ids=tuple(
                consumer.consumer_id for consumer in package.consumer_refs() if consumer.check_id == check.check_id
            ),
            spec_execution_state="not-run",
            cross_change_safe=check.cross_change_safe,
            spec_work_package_id=package.work_package_id,
            spec_check_id=check.check_id,
            spec_provider_cross_change_authorized=check.cross_change_safe,
            semantic_check_id=check.semantic_check_id,
            execution_id=check.execution_id,
            execution_owner_id=check.execution_owner_id,
            input_scope_ids=check.input_paths,
            snapshot_policy=check.snapshot_policy,
            execution_mode=check.execution_mode,
            parent_check_id=check.parent_check_id,
            uncovered_coverage_ids=check.coverage_ids,
        )
        for check in package.checks
    )
    return TestMeshPlan(
        parent_suite_id=f"spec-work-package:{package.package_key}",
        partition_items=partition_items,
        child_suites=child_suites,
        required_evidence_tier=EVIDENCE_ABSTRACT_GREEN,
        inventory_revision=package.change_id,
        required_inventory_item_ids=tuple(item.obligation_id for item in package.obligations if item.required),
        require_complete_inventory=True,
        require_final_receipts=True,
        required_spec_consumer_ids=tuple(consumer.consumer_id for consumer in package.consumer_refs()),
        parent_execution_mode=(
            SPEC_EXECUTION_AGGREGATE_CHILD_RECEIPTS
            if any(check.execution_mode == SPEC_EXECUTION_AGGREGATE_CHILD_RECEIPTS for check in package.checks)
            else ""
        ),
        parent_uncovered_coverage_ids=tuple(
            item
            for check in package.checks
            if check.execution_mode == SPEC_EXECUTION_AGGREGATE_CHILD_RECEIPTS
            for item in check.coverage_ids
        ),
    )


__all__ = [
    "SPEC_BINDING_DIRECT",
    "SPEC_BINDING_INFRASTRUCTURE",
    "SPEC_BINDING_KINDS",
    "SPEC_BINDING_SCOPED_OUT",
    "SPEC_PROVIDER_IDS",
    "SPEC_PROVIDER_MODE_ARTIFACT_ONLY",
    "SPEC_PROVIDER_MODE_NATIVE",
    "SPEC_PROVIDER_MODE_UNAVAILABLE",
    "SPEC_PROVIDER_MODES",
    "SPEC_PROVIDER_OPEN_SPEC",
    "SPEC_PROVIDER_SPEC_KIT",
    "SPEC_REVIEW_BLOCKED",
    "SPEC_REVIEW_READY",
    "SPEC_EXECUTION_AGGREGATE_CHILD_RECEIPTS",
    "SPEC_EXECUTION_DIRECT",
    "SPEC_EXECUTION_MODES",
    "SPEC_EXECUTION_UNCOVERED_REMAINDER",
    "SPEC_SNAPSHOT_FROZEN_REQUIRED",
    "SPEC_SNAPSHOT_LIVE_SCOPED",
    "SPEC_SNAPSHOT_POLICIES",
    "SpecCheckDefinition",
    "SpecConsumerRef",
    "SpecObligation",
    "SpecProviderRef",
    "SpecTask",
    "SpecTaskObligationBinding",
    "SpecScopedOutReason",
    "SpecWorkPackage",
    "SpecWorkPackageFinding",
    "SpecWorkPackageReview",
    "review_spec_work_package",
    "spec_work_package_preflight_context",
    "spec_work_package_to_development_process",
    "spec_work_package_to_plan_detail",
    "spec_work_package_to_test_mesh",
]
