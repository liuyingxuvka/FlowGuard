"""Provider-neutral native reports for target-system qualification.

Adapters may observe any language, artifact, or non-code workflow.  They do
not decide readiness.  This module compares their exact frozen member
denominator with independently declared members, checks a portable
``Input x State -> Set(Output x State)`` refinement, and mechanically derives
the downstream layer results consumed by the target-system compiler.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from .evidence_receipts import (
    EvidenceReceipt,
    ReceiptFinding,
    ReceiptVerificationResult,
    fingerprint_value,
    verified_receipt_binding_gap_codes,
)
from .portable_checker import PortableCheckReport, check_portable_model, check_refinement
from .portable_model import (
    PortableModel,
    RefinementBinding,
    canonical_json_bytes,
)
from .target_system_blueprint import (
    NON_CODE_WORKFLOW_TARGET_PROFILE,
    SOFTWARE_TARGET_PROFILE,
    BlueprintGapRef,
    BlueprintLayerResult,
    BlueprintNativeReportRef,
    FrozenTargetSystemEvidence,
    TargetSystemBlueprintError,
    TargetSystemBlueprintReport,
    TargetSystemDescriptor,
    TargetSystemProviderResult,
    _assemble_target_system_blueprint,
)
from .validation_ownership import (
    ValidationOwnerContract,
    _assert_owner_receipt_integrity,
)


TARGET_NATIVE_QUALIFICATION_SCHEMA = "flowguard.target_native_qualification.v2"
TARGET_NATIVE_MEMBER_ROLES = ("observation", "authority")
TARGET_NATIVE_MEMBER_STATUSES = ("current", "stale", "blocked", "unavailable")
TARGET_NATIVE_INTENT_SOURCE_KINDS = (
    "user_objective",
    "openspec",
    "spark",
    "openspark",
    "changelog",
    "target_contract",
)
_TARGET_NATIVE_INTENT_CONTRIBUTION_STATUSES = (
    "current",
    "stale",
    "contradictory",
    "blocked",
)
_TARGET_NATIVE_TEST_EXECUTION_STATUSES = (
    "not_run",
    "passed",
    "failed",
    "blocked",
    "stale",
)
_TARGET_NATIVE_RESOURCE_LIFECYCLE_STATUSES = (
    "current",
    "stale",
    "blocked",
    "unavailable",
    "retired",
)
TARGET_NATIVE_MEMBER_KINDS = (
    "actor",
    "behavior",
    "boundary",
    "external_owner",
    "implementation",
    "input",
    "intent",
    "interface",
    "output",
    "resource",
    "state",
    "test",
    "topology",
    "transition",
    "verification",
)


def _text(value: Any, context: str) -> str:
    result = str(value).strip()
    if not result:
        raise TargetSystemBlueprintError(f"{context} is required")
    return result


def _strings(values: Iterable[str]) -> tuple[str, ...]:
    rows = tuple(_text(value, "native member identity") for value in values)
    if len(rows) != len(set(rows)):
        raise TargetSystemBlueprintError(
            "native member identity array contains duplicate values"
        )
    return tuple(sorted(rows))


def _json_text(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TargetSystemBlueprintError(f"{context} must be a non-empty JSON string")
    return value


def _strict(value: Any, fields: Sequence[str], context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != set(fields):
        observed = set(value) if isinstance(value, Mapping) else set()
        raise TargetSystemBlueprintError(
            f"{context} fields are not exact-current: "
            f"missing={sorted(set(fields) - observed)}, "
            f"unexpected={sorted(observed - set(fields))}"
        )
    return value


def _array(value: Any, context: str) -> tuple[Any, ...]:
    if not isinstance(value, list):
        raise TargetSystemBlueprintError(f"{context} must be an array")
    return tuple(value)


def _freeze_json(value: Any, context: str) -> Any:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) or not key for key in value):
            raise TargetSystemBlueprintError(
                f"{context} object keys must be non-empty strings"
            )
        frozen: dict[str, Any] = {}
        for key, item in sorted(value.items()):
            frozen[key] = _freeze_json(item, f"{context}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(
            _freeze_json(item, f"{context}[{index}]")
            for index, item in enumerate(value)
        )
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise TargetSystemBlueprintError(
        f"{context} must contain only finite JSON values"
    )


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _detail_strings(
    value: Any,
    context: str,
    *,
    required: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise TargetSystemBlueprintError(f"{context} must be an array")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise TargetSystemBlueprintError(
            f"{context} must contain non-empty JSON strings"
        )
    rows = tuple(sorted(item.strip() for item in value))
    if len(rows) != len(set(rows)):
        raise TargetSystemBlueprintError(f"{context} contains duplicate values")
    if required and not rows:
        raise TargetSystemBlueprintError(f"{context} cannot be empty")
    return rows


def _detail_text(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TargetSystemBlueprintError(f"{context} must be a non-empty JSON string")
    return value.strip()


def _detail_optional_text(value: Any, context: str) -> str:
    if not isinstance(value, str):
        raise TargetSystemBlueprintError(f"{context} must be a JSON string")
    return value.strip()


def target_native_test_obligation_id(
    *,
    target_system_id: str,
    target_profile: str,
    subject_revision: str,
    evidence_role: str,
    member_kind: str,
    member_id: str,
) -> str:
    """Return the exact revision-bound obligation owned by one native test row."""

    if evidence_role not in TARGET_NATIVE_MEMBER_ROLES:
        raise TargetSystemBlueprintError("native test obligation role is invalid")
    if member_kind not in {"test", "verification"}:
        raise TargetSystemBlueprintError("native test obligation kind is invalid")
    payload = {
        "schema_version": TARGET_NATIVE_QUALIFICATION_SCHEMA,
        "target_system_id": _text(target_system_id, "target_system_id"),
        "target_profile": _text(target_profile, "target_profile"),
        "subject_revision": _text(subject_revision, "subject_revision"),
        "evidence_role": evidence_role,
        "member_kind": member_kind,
        "member_id": _text(member_id, "member_id"),
    }
    return "target-native-test:" + fingerprint_value(payload).split(":", 1)[1]


def _detail_json_values(value: Any, context: str) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)):
        raise TargetSystemBlueprintError(f"{context} must be an array")
    rows_by_fingerprint: dict[str, Any] = {}
    for index, item in enumerate(value):
        frozen = _freeze_json(item, f"{context}[{index}]")
        thawed = _thaw_json(frozen)
        identity = fingerprint_value(thawed)
        if identity in rows_by_fingerprint:
            raise TargetSystemBlueprintError(
                f"{context} contains duplicate JSON values"
            )
        rows_by_fingerprint[identity] = frozen
    return tuple(rows_by_fingerprint[key] for key in sorted(rows_by_fingerprint))


def _detail_object(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise TargetSystemBlueprintError(f"{context} must be a non-empty object")
    return _freeze_json(value, context)


_DETAIL_FIELDS = {
    "actor": ("role_ids", "permission_ids"),
    "behavior": ("input_ids", "state_ids", "output_ids", "effect_ids", "error_ids"),
    "boundary": ("boundary_fingerprint", "scope_ids"),
    "external_owner": (
        "owner_id",
        "contract_id",
        "contract_fingerprint",
        "input_ids",
        "state_ids",
        "output_ids",
        "effect_ids",
        "error_ids",
    ),
    "implementation": (
        "path",
        "symbol",
        "content_fingerprint",
        "structure_fingerprint",
        "input_ids",
        "state_ids",
        "output_ids",
        "effect_ids",
        "error_ids",
    ),
    "input": ("value_schema", "model_input_values"),
    "intent": (
        "source_kind",
        "source_id",
        "authority_id",
        "authority_revision",
        "authority_fingerprint",
        "contribution_id",
        "contribution_fingerprint",
        "behavior_ids",
        "model_ids",
        "model_transition_ids",
        "contribution_status",
        "conflicts_with_contribution_ids",
    ),
    "interface": ("input_ids", "state_ids", "output_ids", "effect_ids", "error_ids"),
    "output": ("value_schema", "model_output_values"),
    "resource": (
        "resource_kind",
        "owner_id",
        "source_ref",
        "current_fingerprint",
        "lifecycle_status",
    ),
    "state": ("value_schema", "model_state_ids"),
    "test": (
        "validation_owner_id",
        "obligation_id",
        "checker_id",
        "oracle_id",
        "source_ref",
        "source_fingerprint",
        "receipt_id",
        "receipt_fingerprint",
        "execution_status",
    ),
    "topology": (
        "producer_output_ids",
        "consumer_input_ids",
        "relation_fingerprint",
    ),
    "transition": ("input_ids", "state_ids", "output_ids", "effect_ids", "error_ids"),
    "verification": (
        "validation_owner_id",
        "obligation_id",
        "checker_id",
        "oracle_id",
        "source_ref",
        "source_fingerprint",
        "receipt_id",
        "receipt_fingerprint",
        "execution_status",
    ),
}


def _typed_member_details(
    *,
    member_kind: str,
    member_id: str,
    behavior_ids: tuple[str, ...],
    model_transition_ids: tuple[str, ...],
    value: Any,
) -> Mapping[str, Any]:
    data = _strict(
        value,
        _DETAIL_FIELDS[member_kind],
        f"native member {member_kind}:{member_id} details",
    )
    normalized: dict[str, Any]
    if member_kind in {"behavior", "interface", "transition"}:
        normalized = {
            name: _detail_strings(data[name], f"native details.{name}")
            for name in _DETAIL_FIELDS[member_kind]
        }
    elif member_kind in {"implementation", "external_owner"}:
        text_fields = (
            ("path", "symbol", "content_fingerprint", "structure_fingerprint")
            if member_kind == "implementation"
            else ("owner_id", "contract_id", "contract_fingerprint")
        )
        normalized = {
            name: _detail_text(data[name], f"native details.{name}")
            for name in text_fields
        }
        normalized.update(
            {
                name: _detail_strings(data[name], f"native details.{name}")
                for name in (
                    "input_ids",
                    "state_ids",
                    "output_ids",
                    "effect_ids",
                    "error_ids",
                )
            }
        )
    elif member_kind in {"input", "output", "state"}:
        model_field = {
            "input": "model_input_values",
            "output": "model_output_values",
            "state": "model_state_ids",
        }[member_kind]
        normalized = {
            "value_schema": _detail_object(
                data["value_schema"], "native details.value_schema"
            ),
            model_field: (
                _detail_strings(
                    data[model_field],
                    f"native details.{model_field}",
                )
                if member_kind == "state"
                else _detail_json_values(
                    data[model_field],
                    f"native details.{model_field}",
                )
            ),
        }
    elif member_kind in {"test", "verification"}:
        normalized = {
            name: _detail_text(data[name], f"native details.{name}")
            for name in _DETAIL_FIELDS[member_kind]
            if name
            not in {
                "execution_status",
                "receipt_id",
                "receipt_fingerprint",
            }
        }
        normalized["receipt_id"] = _detail_optional_text(
            data["receipt_id"], "native details.receipt_id"
        )
        normalized["receipt_fingerprint"] = _detail_optional_text(
            data["receipt_fingerprint"],
            "native details.receipt_fingerprint",
        )
        execution_status = _detail_text(
            data["execution_status"], "native details.execution_status"
        )
        if execution_status not in _TARGET_NATIVE_TEST_EXECUTION_STATUSES:
            raise TargetSystemBlueprintError(
                "native test execution_status is not exact-current"
            )
        normalized["execution_status"] = execution_status
        has_receipt_id = bool(normalized["receipt_id"])
        has_receipt_fingerprint = bool(normalized["receipt_fingerprint"])
        if has_receipt_id != has_receipt_fingerprint:
            raise TargetSystemBlueprintError(
                "native test receipt id and fingerprint must be supplied together"
            )
        if execution_status == "passed" and not has_receipt_id:
            raise TargetSystemBlueprintError(
                "passed native test requires one exact typed receipt binding"
            )
        if execution_status != "passed" and has_receipt_id:
            raise TargetSystemBlueprintError(
                "non-passing native test must not project an execution receipt"
            )
    elif member_kind == "resource":
        normalized = {
            name: _detail_text(data[name], f"native details.{name}")
            for name in _DETAIL_FIELDS[member_kind]
        }
        if normalized["lifecycle_status"] not in _TARGET_NATIVE_RESOURCE_LIFECYCLE_STATUSES:
            raise TargetSystemBlueprintError(
                "native resource lifecycle_status is not exact-current"
            )
    elif member_kind == "intent":
        normalized = {
            name: _detail_text(data[name], f"native details.{name}")
            for name in (
                "source_kind",
                "source_id",
                "authority_id",
                "authority_revision",
                "authority_fingerprint",
                "contribution_id",
                "contribution_fingerprint",
                "contribution_status",
            )
        }
        normalized.update(
            {
                name: _detail_strings(
                    data[name],
                    f"native details.{name}",
                    required=(name == "model_ids"),
                )
                for name in (
                    "behavior_ids",
                    "model_ids",
                    "model_transition_ids",
                    "conflicts_with_contribution_ids",
                )
            }
        )
        if normalized["source_kind"] not in TARGET_NATIVE_INTENT_SOURCE_KINDS:
            raise TargetSystemBlueprintError(
                "native intent source_kind is not a direct current source kind"
            )
        if normalized["contribution_status"] not in _TARGET_NATIVE_INTENT_CONTRIBUTION_STATUSES:
            raise TargetSystemBlueprintError(
                "native intent contribution_status is not exact-current"
            )
        if normalized["behavior_ids"] != behavior_ids:
            raise TargetSystemBlueprintError(
                "native intent detail behavior_ids differ from the member relation"
            )
        if normalized["model_transition_ids"] != model_transition_ids:
            raise TargetSystemBlueprintError(
                "native intent detail model_transition_ids differ from the member binding"
            )
        if (
            normalized["contribution_status"] == "contradictory"
            and not normalized["conflicts_with_contribution_ids"]
        ):
            raise TargetSystemBlueprintError(
                "contradictory native intent must identify conflicting contributions"
            )
        authority_payload = {
            name: normalized[name]
            for name in (
                "source_kind",
                "source_id",
                "authority_id",
                "authority_revision",
            )
        }
        if normalized["authority_fingerprint"] != fingerprint_value(authority_payload):
            raise TargetSystemBlueprintError(
                "native intent authority fingerprint differs from its exact payload"
            )
        contribution_payload = {
            name: _thaw_json(normalized[name])
            for name in (
                "source_kind",
                "source_id",
                "authority_id",
                "authority_revision",
                "authority_fingerprint",
                "contribution_id",
                "behavior_ids",
                "contribution_status",
                "conflicts_with_contribution_ids",
            )
        }
        if normalized["contribution_fingerprint"] != fingerprint_value(
            contribution_payload
        ):
            raise TargetSystemBlueprintError(
                "native intent contribution fingerprint differs from its exact payload"
            )
    elif member_kind == "boundary":
        normalized = {
            "boundary_fingerprint": _detail_text(
                data["boundary_fingerprint"],
                "native details.boundary_fingerprint",
            ),
            "scope_ids": _detail_strings(
                data["scope_ids"], "native details.scope_ids"
            ),
        }
    elif member_kind == "actor":
        normalized = {
            "role_ids": _detail_strings(
                data["role_ids"], "native details.role_ids", required=True
            ),
            "permission_ids": _detail_strings(
                data["permission_ids"],
                "native details.permission_ids",
                required=True,
            ),
        }
    elif member_kind == "topology":
        normalized = {
            "producer_output_ids": _detail_strings(
                data["producer_output_ids"],
                "native details.producer_output_ids",
            ),
            "consumer_input_ids": _detail_strings(
                data["consumer_input_ids"],
                "native details.consumer_input_ids",
            ),
            "relation_fingerprint": _detail_text(
                data["relation_fingerprint"],
                "native details.relation_fingerprint",
            ),
        }
    else:  # pragma: no cover - member kind validation precedes this branch
        raise TargetSystemBlueprintError(
            f"native member details have no owner for kind {member_kind}"
        )
    return _freeze_json(normalized, f"native member {member_kind}:{member_id} details")


def _relation_details(member_kind: str, details: Mapping[str, Any]) -> dict[str, Any]:
    """Return role-independent contract fields; model bindings refine separately."""

    value = _thaw_json(details)
    for field_name in (
        "model_input_values",
        "model_state_ids",
        "model_output_values",
        "model_ids",
        "model_transition_ids",
    ):
        value.pop(field_name, None)
    if member_kind in {"test", "verification"}:
        for field_name in (
            "validation_owner_id",
            "obligation_id",
            "receipt_id",
            "receipt_fingerprint",
            "execution_status",
        ):
            value.pop(field_name, None)
    return value


@dataclass(frozen=True)
class TargetNativeModelRef:
    evidence_role: str
    provider_id: str
    capability_id: str
    payload_id: str
    payload_fingerprint: str
    model_id: str
    model_fingerprint: str

    def __post_init__(self) -> None:
        if self.evidence_role not in TARGET_NATIVE_MEMBER_ROLES:
            raise TargetSystemBlueprintError("native model evidence role is invalid")
        for name in (
            "provider_id",
            "capability_id",
            "payload_id",
            "payload_fingerprint",
            "model_id",
            "model_fingerprint",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))

    def to_dict(self) -> dict[str, str]:
        return {
            "evidence_role": self.evidence_role,
            "provider_id": self.provider_id,
            "capability_id": self.capability_id,
            "payload_id": self.payload_id,
            "payload_fingerprint": self.payload_fingerprint,
            "model_id": self.model_id,
            "model_fingerprint": self.model_fingerprint,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "TargetNativeModelRef":
        fields = (
            "evidence_role",
            "provider_id",
            "capability_id",
            "payload_id",
            "payload_fingerprint",
            "model_id",
            "model_fingerprint",
        )
        data = _strict(value, fields, "target native model ref")
        return cls(**{name: _json_text(data[name], name) for name in fields})


@dataclass(frozen=True)
class TargetNativeMember:
    member_id: str
    member_kind: str
    evidence_role: str
    subject_revision: str
    provider_id: str
    capability_id: str
    payload_id: str
    payload_fingerprint: str
    details: Mapping[str, Any]
    behavior_ids: tuple[str, ...] = ()
    model_transition_ids: tuple[str, ...] = ()
    status: str = "current"

    def __post_init__(self) -> None:
        if self.member_kind not in TARGET_NATIVE_MEMBER_KINDS:
            raise TargetSystemBlueprintError(
                f"unknown target native member kind: {self.member_kind}"
            )
        if self.evidence_role not in TARGET_NATIVE_MEMBER_ROLES:
            raise TargetSystemBlueprintError("native member evidence role is invalid")
        if self.status not in TARGET_NATIVE_MEMBER_STATUSES:
            raise TargetSystemBlueprintError("native member status is invalid")
        for name in (
            "member_id",
            "subject_revision",
            "provider_id",
            "capability_id",
            "payload_id",
            "payload_fingerprint",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "behavior_ids", _strings(self.behavior_ids))
        object.__setattr__(
            self,
            "model_transition_ids",
            _strings(self.model_transition_ids),
        )
        object.__setattr__(
            self,
            "details",
            _typed_member_details(
                member_kind=self.member_kind,
                member_id=self.member_id,
                behavior_ids=self.behavior_ids,
                model_transition_ids=self.model_transition_ids,
                value=self.details,
            ),
        )
        if self.payload_fingerprint != fingerprint_value(self.canonical_payload):
            raise TargetSystemBlueprintError(
                "native member differs from its canonical provider payload fingerprint"
            )

    @property
    def denominator_key(self) -> tuple[str, str]:
        return (self.member_kind, self.member_id)

    @property
    def canonical_payload(self) -> dict[str, Any]:
        return {
            "member_id": self.member_id,
            "member_kind": self.member_kind,
            "subject_revision": self.subject_revision,
            "behavior_ids": list(self.behavior_ids),
            "model_transition_ids": list(self.model_transition_ids),
            "details": _thaw_json(self.details),
            "status": self.status,
        }

    @property
    def relation_contract_payload(self) -> dict[str, Any]:
        """Cross-role member contract; model ids are compared through refinement."""

        return {
            "member_id": self.member_id,
            "member_kind": self.member_kind,
            "subject_revision": self.subject_revision,
            "behavior_ids": list(self.behavior_ids),
            "details": _relation_details(self.member_kind, self.details),
            "status": self.status,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "member_id": self.member_id,
            "member_kind": self.member_kind,
            "evidence_role": self.evidence_role,
            "subject_revision": self.subject_revision,
            "provider_id": self.provider_id,
            "capability_id": self.capability_id,
            "payload_id": self.payload_id,
            "payload_fingerprint": self.payload_fingerprint,
            "behavior_ids": list(self.behavior_ids),
            "model_transition_ids": list(self.model_transition_ids),
            "details": _thaw_json(self.details),
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "TargetNativeMember":
        fields = (
            "member_id",
            "member_kind",
            "evidence_role",
            "subject_revision",
            "provider_id",
            "capability_id",
            "payload_id",
            "payload_fingerprint",
            "behavior_ids",
            "model_transition_ids",
            "details",
            "status",
        )
        data = _strict(value, fields, "target native member")
        return cls(
            **{
                name: _json_text(data[name], f"native member.{name}")
                for name in fields
                if name not in {"behavior_ids", "model_transition_ids", "details"}
            },
            behavior_ids=tuple(
                _json_text(item, "native behavior id")
                for item in _array(data["behavior_ids"], "native behavior ids")
            ),
            model_transition_ids=tuple(
                _json_text(item, "native model transition id")
                for item in _array(
                    data["model_transition_ids"],
                    "native model transition ids",
                )
            ),
            details=data["details"],
        )


_VALIDATION_OWNER_CONTRACT_FIELDS = (
    "owner_id",
    "command",
    "input_patterns",
    "obligation_ids",
    "projected_inputs",
    "dependency_owner_ids",
    "resource_keys",
    "toolchain_selectors",
    "environment_selectors",
    "external_component_bindings",
    "work_context_artifact_roles",
    "timeout_seconds",
    "termination_policy",
    "required",
)
_COMPONENT_BINDING_FIELDS = ("component_id", "fingerprint")
_EVIDENCE_RECEIPT_FIELDS = (
    "schema_version",
    "receipt_id",
    "subject_id",
    "subject_kind",
    "producer_id",
    "producer_version",
    "claim_scope",
    "command",
    "working_directory_token",
    "started_at",
    "finished_at",
    "exit_code",
    "environment_fingerprint",
    "environment_metadata",
    "contract_hash",
    "check_manifest_hash",
    "suite_map_hash",
    "input_snapshots",
    "proof_artifact_id",
    "proof_artifact_fingerprint",
    "result_status",
    "result_fingerprint",
    "covered_obligations",
    "required_child_receipts",
    "consumed_child_receipts",
    "supersedes_receipt_ids",
    "skipped_checks",
    "blockers",
    "claim_boundary",
    "metadata",
)
_INPUT_SNAPSHOT_FIELDS = (
    "artifact_id",
    "path_token",
    "hash_policy",
    "raw_sha256",
    "semantic_sha256",
    "obligation_ids",
)
_CHILD_RECEIPT_REQUIREMENT_FIELDS = (
    "receipt_id",
    "subject_id",
    "obligation_ids",
    "eligible_claim_scopes",
    "expected_receipt_fingerprint",
)
_CONSUMED_CHILD_RECEIPT_FIELDS = ("receipt_id", "receipt_fingerprint")
_RECEIPT_VERIFICATION_FIELDS = (
    "receipt_id",
    "receipt_fingerprint",
    "current",
    "eligible",
    "status",
    "finding_codes",
    "findings",
    "satisfied_obligations",
    "minimum_revalidation",
)
_RECEIPT_FINDING_FIELDS = ("code", "message", "artifact_id", "details")


def _validation_owner_contract_from_dict(value: Any) -> ValidationOwnerContract:
    data = _strict(
        value,
        _VALIDATION_OWNER_CONTRACT_FIELDS,
        "target native validation owner contract",
    )
    for name in (
        "command",
        "input_patterns",
        "obligation_ids",
        "dependency_owner_ids",
        "resource_keys",
        "toolchain_selectors",
        "environment_selectors",
        "work_context_artifact_roles",
    ):
        _array(data[name], f"target native validation owner contract.{name}")
    for name in ("projected_inputs", "external_component_bindings"):
        for index, row in enumerate(
            _array(data[name], f"target native validation owner contract.{name}")
        ):
            _strict(
                row,
                _COMPONENT_BINDING_FIELDS,
                f"target native validation owner contract.{name}[{index}]",
            )
    if not isinstance(data["required"], bool):
        raise TargetSystemBlueprintError(
            "target native validation owner contract.required must be a JSON boolean"
        )
    try:
        return ValidationOwnerContract.from_dict(data)
    except (TypeError, ValueError) as exc:
        raise TargetSystemBlueprintError(
            f"invalid target native validation owner contract: {exc}"
        ) from exc


def _evidence_receipt_from_dict(value: Any) -> EvidenceReceipt:
    data = _strict(
        value,
        _EVIDENCE_RECEIPT_FIELDS,
        "target native evidence receipt",
    )
    for name in (
        "command",
        "input_snapshots",
        "covered_obligations",
        "required_child_receipts",
        "consumed_child_receipts",
        "supersedes_receipt_ids",
        "skipped_checks",
        "blockers",
    ):
        _array(data[name], f"target native evidence receipt.{name}")
    if not isinstance(data["environment_metadata"], Mapping) or not isinstance(
        data["metadata"], Mapping
    ):
        raise TargetSystemBlueprintError(
            "target native evidence receipt metadata fields must be JSON objects"
        )
    for index, row in enumerate(data["input_snapshots"]):
        snapshot = _strict(
            row,
            _INPUT_SNAPSHOT_FIELDS,
            f"target native evidence receipt.input_snapshots[{index}]",
        )
        _array(
            snapshot["obligation_ids"],
            f"target native evidence receipt.input_snapshots[{index}].obligation_ids",
        )
    for index, row in enumerate(data["required_child_receipts"]):
        requirement = _strict(
            row,
            _CHILD_RECEIPT_REQUIREMENT_FIELDS,
            f"target native evidence receipt.required_child_receipts[{index}]",
        )
        _array(
            requirement["obligation_ids"],
            f"target native evidence receipt.required_child_receipts[{index}].obligation_ids",
        )
        _array(
            requirement["eligible_claim_scopes"],
            f"target native evidence receipt.required_child_receipts[{index}].eligible_claim_scopes",
        )
    for index, row in enumerate(data["consumed_child_receipts"]):
        _strict(
            row,
            _CONSUMED_CHILD_RECEIPT_FIELDS,
            f"target native evidence receipt.consumed_child_receipts[{index}]",
        )
    try:
        return EvidenceReceipt.from_dict(data)
    except (TypeError, ValueError) as exc:
        raise TargetSystemBlueprintError(
            f"invalid target native evidence receipt: {exc}"
        ) from exc


def _receipt_verification_from_dict(value: Any) -> ReceiptVerificationResult:
    data = _strict(
        value,
        _RECEIPT_VERIFICATION_FIELDS,
        "target native receipt verification",
    )
    if not isinstance(data["current"], bool) or not isinstance(
        data["eligible"], bool
    ):
        raise TargetSystemBlueprintError(
            "target native receipt verification current and eligible must be booleans"
        )
    findings: list[ReceiptFinding] = []
    for index, value_row in enumerate(
        _array(data["findings"], "target native receipt verification.findings")
    ):
        row = _strict(
            value_row,
            _RECEIPT_FINDING_FIELDS,
            f"target native receipt verification.findings[{index}]",
        )
        if not isinstance(row["details"], Mapping):
            raise TargetSystemBlueprintError(
                "target native receipt finding details must be a JSON object"
            )
        findings.append(
            ReceiptFinding(
                code=_json_text(row["code"], "receipt finding.code"),
                message=_json_text(row["message"], "receipt finding.message"),
                artifact_id=str(row["artifact_id"]),
                details=row["details"],
            )
        )
    finding_codes = tuple(
        _json_text(item, "receipt finding code")
        for item in _array(
            data["finding_codes"],
            "target native receipt verification.finding_codes",
        )
    )
    if finding_codes != tuple(row.code for row in findings):
        raise TargetSystemBlueprintError(
            "target native receipt verification finding_codes differ from findings"
        )
    satisfied = tuple(
        _json_text(item, "satisfied obligation id")
        for item in _array(
            data["satisfied_obligations"],
            "target native receipt verification.satisfied_obligations",
        )
    )
    revalidation = tuple(
        _json_text(item, "minimum revalidation action")
        for item in _array(
            data["minimum_revalidation"],
            "target native receipt verification.minimum_revalidation",
        )
    )
    if len(satisfied) != len(set(satisfied)) or len(revalidation) != len(
        set(revalidation)
    ):
        raise TargetSystemBlueprintError(
            "target native receipt verification arrays contain duplicate values"
        )
    return ReceiptVerificationResult(
        receipt_id=_json_text(data["receipt_id"], "verification receipt_id"),
        receipt_fingerprint=_json_text(
            data["receipt_fingerprint"], "verification receipt_fingerprint"
        ),
        current=data["current"],
        eligible=data["eligible"],
        status=_json_text(data["status"], "verification status"),
        findings=tuple(findings),
        satisfied_obligations=satisfied,
        minimum_revalidation=revalidation,
    )


@dataclass(frozen=True)
class TargetBlueprintNativeReportSet:
    target_system_id: str
    target_profile: str
    subject_revision: str
    descriptor_fingerprint: str
    boundary_fingerprint: str
    frozen_evidence_fingerprint: str
    observed_model: PortableModel
    authority_model: PortableModel
    refinement_binding: RefinementBinding
    model_refs: tuple[TargetNativeModelRef, ...]
    members: tuple[TargetNativeMember, ...]
    claim_boundary: str
    validation_owner_contracts: tuple[ValidationOwnerContract, ...] = ()
    execution_receipts: tuple[EvidenceReceipt, ...] = ()
    receipt_verifications: tuple[ReceiptVerificationResult, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "target_system_id",
            "target_profile",
            "subject_revision",
            "descriptor_fingerprint",
            "boundary_fingerprint",
            "frozen_evidence_fingerprint",
            "claim_boundary",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        refs = tuple(
            sorted(
                self.model_refs,
                key=lambda row: TARGET_NATIVE_MEMBER_ROLES.index(
                    row.evidence_role
                ),
            )
        )
        if tuple(row.evidence_role for row in refs) != TARGET_NATIVE_MEMBER_ROLES:
            raise TargetSystemBlueprintError(
                "native report set requires one observation and one authority model ref"
            )
        object.__setattr__(self, "model_refs", refs)
        members = tuple(
            sorted(
                self.members,
                key=lambda row: (
                    row.evidence_role,
                    row.member_kind,
                    row.member_id,
                ),
            )
        )
        identities = tuple(
            (row.evidence_role, row.member_kind, row.member_id) for row in members
        )
        if len(identities) != len(set(identities)):
            raise TargetSystemBlueprintError(
                "native report set contains duplicate member identities"
        )
        object.__setattr__(self, "members", members)
        if any(
            not isinstance(row, ValidationOwnerContract)
            for row in self.validation_owner_contracts
        ):
            raise TargetSystemBlueprintError(
                "target native validation owner registry must contain typed contracts"
            )
        if any(not isinstance(row, EvidenceReceipt) for row in self.execution_receipts):
            raise TargetSystemBlueprintError(
                "target native receipt registry must contain typed evidence receipts"
            )
        if any(
            not isinstance(row, ReceiptVerificationResult)
            for row in self.receipt_verifications
        ):
            raise TargetSystemBlueprintError(
                "target native verification registry must contain typed results"
            )
        contracts = tuple(
            sorted(self.validation_owner_contracts, key=lambda row: row.owner_id)
        )
        receipts = tuple(sorted(self.execution_receipts, key=lambda row: row.receipt_id))
        verifications = tuple(
            sorted(self.receipt_verifications, key=lambda row: row.receipt_id)
        )
        object.__setattr__(self, "validation_owner_contracts", contracts)
        object.__setattr__(self, "execution_receipts", receipts)
        object.__setattr__(self, "receipt_verifications", verifications)
        self._validate_execution_evidence()

    def _validate_execution_evidence(self) -> None:
        contracts = {
            row.owner_id: row for row in self.validation_owner_contracts
        }
        receipts = {row.receipt_id: row for row in self.execution_receipts}
        verifications = {
            row.receipt_id: row for row in self.receipt_verifications
        }
        if len(contracts) != len(self.validation_owner_contracts):
            raise TargetSystemBlueprintError(
                "target native validation owner registry contains duplicate owners"
            )
        if len(receipts) != len(self.execution_receipts):
            raise TargetSystemBlueprintError(
                "target native receipt registry contains duplicate receipt ids"
            )
        if len(verifications) != len(self.receipt_verifications):
            raise TargetSystemBlueprintError(
                "target native verification registry contains duplicate receipt ids"
            )

        execution_rows = tuple(
            row
            for row in self.members
            if row.member_kind in {"test", "verification"}
        )
        passed_rows = tuple(
            row
            for row in execution_rows
            if row.details["execution_status"] == "passed"
        )
        for row in execution_rows:
            expected_obligation_id = target_native_test_obligation_id(
                target_system_id=self.target_system_id,
                target_profile=self.target_profile,
                subject_revision=self.subject_revision,
                evidence_role=row.evidence_role,
                member_kind=row.member_kind,
                member_id=row.member_id,
            )
            if row.details["obligation_id"] != expected_obligation_id:
                raise TargetSystemBlueprintError(
                    "native test obligation is not bound to the exact target, "
                    "revision, role, kind, and member identity"
                )
            expected_source_fingerprint = fingerprint_value(
                {
                    "source_ref": row.details["source_ref"],
                    "subject_revision": row.subject_revision,
                }
            )
            if row.details["source_fingerprint"] != expected_source_fingerprint:
                raise TargetSystemBlueprintError(
                    "native test source fingerprint differs from its exact revision binding"
                )

        referenced_owner_ids = tuple(
            row.details["validation_owner_id"] for row in passed_rows
        )
        referenced_receipt_ids = tuple(row.details["receipt_id"] for row in passed_rows)
        if len(referenced_receipt_ids) != len(set(referenced_receipt_ids)):
            raise TargetSystemBlueprintError(
                "one native execution receipt cannot be reused for multiple passed members"
            )
        if len(referenced_owner_ids) != len(set(referenced_owner_ids)):
            raise TargetSystemBlueprintError(
                "one native validation owner cannot be reused for multiple passed members"
            )
        if set(contracts) != set(referenced_owner_ids):
            raise TargetSystemBlueprintError(
                "target native validation owner registry is not the exact passed-member set"
            )
        if set(receipts) != set(referenced_receipt_ids):
            raise TargetSystemBlueprintError(
                "target native receipt registry is not the exact passed-member set"
            )
        if set(verifications) != set(referenced_receipt_ids):
            raise TargetSystemBlueprintError(
                "target native verification registry is not the exact receipt set"
            )

        for row in passed_rows:
            owner_id = row.details["validation_owner_id"]
            obligation_id = row.details["obligation_id"]
            contract = contracts[owner_id]
            receipt = receipts[row.details["receipt_id"]]
            verification = verifications[receipt.receipt_id]
            expected_subject = f"validation-owner:{owner_id}"
            expected_producer = expected_subject

            if not contract.required or contract.dependency_owner_ids:
                raise TargetSystemBlueprintError(
                    "passed native test requires one required leaf validation owner"
                )
            if contract.obligation_ids != (obligation_id,):
                raise TargetSystemBlueprintError(
                    "native validation owner does not own the exact member obligation"
                )
            if tuple(contract.command) != receipt.command:
                raise TargetSystemBlueprintError(
                    "native validation owner command differs from its receipt"
                )
            selected_environment = tuple(
                sorted(
                    set(
                        contract.toolchain_selectors
                        + contract.environment_selectors
                    )
                )
            )
            if (
                not contract.toolchain_selectors
                or not contract.environment_selectors
                or tuple(receipt.environment_metadata) != selected_environment
            ):
                raise TargetSystemBlueprintError(
                    "native receipt does not bind the exact owner toolchain and environment selectors"
                )
            if (
                "flowguard_version" in receipt.environment_metadata
                and receipt.environment_metadata["flowguard_version"]
                != receipt.producer_version
            ):
                raise TargetSystemBlueprintError(
                    "native receipt producer version differs from its toolchain binding"
                )
            expected_contract_hash = fingerprint_value(
                {
                    **contract.to_dict(),
                    "command": list(receipt.command),
                }
            )
            expected_manifest_hash = fingerprint_value(
                {
                    "owner_id": owner_id,
                    "command": list(receipt.command),
                    "obligations": [obligation_id],
                }
            )
            expected_suite_map_hash = fingerprint_value(
                {
                    "owner_id": owner_id,
                    "patterns": list(contract.input_patterns),
                    "projected_inputs": [
                        {
                            "component_id": component_id,
                            "fingerprint": fingerprint,
                        }
                        for component_id, fingerprint in contract.projected_inputs
                    ],
                    "obligations": [obligation_id],
                }
            )
            if (
                receipt.contract_hash != expected_contract_hash
                or receipt.check_manifest_hash != expected_manifest_hash
                or receipt.suite_map_hash != expected_suite_map_hash
            ):
                raise TargetSystemBlueprintError(
                    "native receipt contract, checker, or input-map binding is stale"
                )
            if (
                receipt.subject_kind != "validation_owner"
                or receipt.required_child_receipts
                or receipt.consumed_child_receipts
            ):
                raise TargetSystemBlueprintError(
                    "parent or aggregate receipt cannot satisfy a native member"
                )
            if (
                len(receipt.input_snapshots) != 1
                or receipt.input_snapshots[0].artifact_id
                != f"input:validation-owner:{owner_id}"
                or receipt.input_snapshots[0].obligation_ids != (obligation_id,)
                or receipt.input_snapshots[0].path_token
                != f"<WORKSPACE>/<OWNER_INPUT:{owner_id}>"
            ):
                raise TargetSystemBlueprintError(
                    "native receipt input snapshot is not the exact current owner input"
                )
            if receipt.proof_artifact_id != f"proof:validation-owner:{owner_id}":
                raise TargetSystemBlueprintError(
                    "native receipt proof artifact is relabeled from another owner"
                )
            try:
                _assert_owner_receipt_integrity(receipt)
            except ValueError as exc:
                raise TargetSystemBlueprintError(str(exc)) from exc
            gaps = verified_receipt_binding_gap_codes(
                receipt,
                verification,
                expected_subject_id=expected_subject,
                expected_producer_id=expected_producer,
                eligible_claim_scopes=("full",),
                expected_obligation_ids=(obligation_id,),
            )
            if row.details["receipt_fingerprint"] != receipt.fingerprint:
                gaps = (
                    *gaps,
                    (
                        "native_receipt_member_fingerprint_mismatch",
                        "native member receipt fingerprint differs from the loaded receipt",
                    ),
                )
            if verification.minimum_revalidation:
                gaps = (
                    *gaps,
                    (
                        "native_receipt_revalidation_open",
                        "current native receipt verification still requests revalidation",
                    ),
                )
            if gaps:
                raise TargetSystemBlueprintError(
                    "native passed receipt is not exact-current: "
                    + ", ".join(code for code, _message in gaps)
                )

    @property
    def refinement_report(self) -> PortableCheckReport:
        return check_refinement(
            self.authority_model,
            self.observed_model,
            self.refinement_binding,
        )

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": TARGET_NATIVE_QUALIFICATION_SCHEMA,
            "target_system_id": self.target_system_id,
            "target_profile": self.target_profile,
            "subject_revision": self.subject_revision,
            "descriptor_fingerprint": self.descriptor_fingerprint,
            "boundary_fingerprint": self.boundary_fingerprint,
            "frozen_evidence_fingerprint": self.frozen_evidence_fingerprint,
            "observed_model": self.observed_model.to_dict(),
            "authority_model": self.authority_model.to_dict(),
            "refinement_binding": self.refinement_binding.to_dict(),
            "model_refs": [row.to_dict() for row in self.model_refs],
            "members": [row.to_dict() for row in self.members],
            "validation_owner_contracts": [
                row.to_dict() for row in self.validation_owner_contracts
            ],
            "execution_receipts": [
                row.to_dict() for row in self.execution_receipts
            ],
            "receipt_verifications": [
                row.to_dict() for row in self.receipt_verifications
            ],
            "claim_boundary": self.claim_boundary,
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_dict(cls, value: Any) -> "TargetBlueprintNativeReportSet":
        fields = (
            "schema_version",
            "target_system_id",
            "target_profile",
            "subject_revision",
            "descriptor_fingerprint",
            "boundary_fingerprint",
            "frozen_evidence_fingerprint",
            "observed_model",
            "authority_model",
            "refinement_binding",
            "model_refs",
            "members",
            "validation_owner_contracts",
            "execution_receipts",
            "receipt_verifications",
            "claim_boundary",
            "fingerprint",
        )
        data = _strict(value, fields, "target native report set")
        if data["schema_version"] != TARGET_NATIVE_QUALIFICATION_SCHEMA:
            raise TargetSystemBlueprintError(
                "target native report set schema is not current"
            )
        result = cls(
            target_system_id=_json_text(data["target_system_id"], "target_system_id"),
            target_profile=_json_text(data["target_profile"], "target_profile"),
            subject_revision=_json_text(data["subject_revision"], "subject_revision"),
            descriptor_fingerprint=_json_text(
                data["descriptor_fingerprint"], "descriptor_fingerprint"
            ),
            boundary_fingerprint=_json_text(
                data["boundary_fingerprint"], "boundary_fingerprint"
            ),
            frozen_evidence_fingerprint=_json_text(
                data["frozen_evidence_fingerprint"],
                "frozen_evidence_fingerprint",
            ),
            observed_model=PortableModel.from_dict(data["observed_model"]),
            authority_model=PortableModel.from_dict(data["authority_model"]),
            refinement_binding=RefinementBinding.from_dict(
                data["refinement_binding"]
            ),
            model_refs=tuple(
                TargetNativeModelRef.from_dict(item)
                for item in _array(data["model_refs"], "target native model refs")
            ),
            members=tuple(
                TargetNativeMember.from_dict(item)
                for item in _array(data["members"], "target native members")
            ),
            validation_owner_contracts=tuple(
                _validation_owner_contract_from_dict(item)
                for item in _array(
                    data["validation_owner_contracts"],
                    "target native validation owner contracts",
                )
            ),
            execution_receipts=tuple(
                _evidence_receipt_from_dict(item)
                for item in _array(
                    data["execution_receipts"],
                    "target native execution receipts",
                )
            ),
            receipt_verifications=tuple(
                _receipt_verification_from_dict(item)
                for item in _array(
                    data["receipt_verifications"],
                    "target native receipt verifications",
                )
            ),
            claim_boundary=_json_text(data["claim_boundary"], "claim_boundary"),
        )
        if result.fingerprint != _json_text(data["fingerprint"], "fingerprint"):
            raise TargetSystemBlueprintError(
                "target native report set fingerprint mismatch"
            )
        return result


def serialize_target_blueprint_native_report_set(
    report_set: TargetBlueprintNativeReportSet,
) -> bytes:
    return canonical_json_bytes(report_set.to_dict())


def load_target_blueprint_native_report_set(
    path: str | Path,
) -> TargetBlueprintNativeReportSet:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TargetSystemBlueprintError(
            f"cannot load target native report set: {exc}"
        ) from exc
    return TargetBlueprintNativeReportSet.from_dict(value)


_SOFTWARE_KIND_LAYERS = {
    "implementation": "implementation_inventory",
    "external_owner": "implementation_inventory",
    "interface": "implementation_inventory",
    "input": "traceability",
    "state": "traceability",
    "output": "traceability",
    "topology": "traceability",
    "behavior": "independent_semantics",
    "test": "model_code_test",
    "verification": "model_code_test",
    "resource": "resource_oracle",
    "intent": "resource_oracle",
}
_WORKFLOW_KIND_LAYERS = {
    "boundary": "workflow_boundary",
    "actor": "workflow_actors",
    "input": "workflow_inputs",
    "state": "workflow_states",
    "behavior": "workflow_transitions",
    "transition": "workflow_transitions",
    "output": "workflow_outputs",
    "resource": "workflow_resources",
    "intent": "workflow_intent",
    "test": "workflow_verification",
    "verification": "workflow_verification",
}
_REQUIRED_KIND_GROUPS = {
    SOFTWARE_TARGET_PROFILE: (
        ("behavior",),
        ("implementation", "external_owner"),
        ("interface",),
        ("input",),
        ("state",),
        ("output",),
        ("test", "verification"),
        ("resource",),
        ("intent",),
    ),
    NON_CODE_WORKFLOW_TARGET_PROFILE: (
        ("boundary",),
        ("actor",),
        ("input",),
        ("state",),
        ("transition",),
        ("output",),
        ("resource",),
        ("intent",),
        ("test", "verification"),
    ),
}
_REQUIRED_KINDS = {
    profile: frozenset(kind for group in groups for kind in group)
    for profile, groups in _REQUIRED_KIND_GROUPS.items()
}


def _provider_by_id(
    frozen: FrozenTargetSystemEvidence,
) -> dict[str, TargetSystemProviderResult]:
    return {row.provider_id: row for row in frozen.provider_results}


def _provider_binding_gap(
    *,
    descriptor: TargetSystemDescriptor,
    frozen: FrozenTargetSystemEvidence,
    provider_id: str,
    evidence_role: str,
    capability_id: str,
    payload_id: str,
    payload_fingerprint: str,
    object_id: str,
) -> BlueprintGapRef | None:
    provider = _provider_by_id(frozen).get(provider_id)
    if provider is None:
        message = "native evidence provider is absent from the frozen result set"
    elif provider.provider_role != evidence_role:
        message = "native evidence provider role differs from the frozen result"
    elif provider.status != "current":
        message = "native evidence provider result is not current"
    elif capability_id not in provider.capability_ids:
        message = "native evidence capability is absent from its provider"
    else:
        binding = next(
            (
                row
                for row in provider.capability_bindings
                if row.capability_id == capability_id
            ),
            None,
        )
        if binding is None or payload_id not in binding.payload_ids:
            message = "native evidence payload is not bound to its capability"
        elif dict(provider.payload_fingerprints).get(payload_id) != payload_fingerprint:
            message = "native evidence payload fingerprint differs from its provider"
        elif not any(
            dict(provider.input_fingerprints).get(input_id)
            == descriptor.boundary_fingerprint
            for input_id in binding.input_ids
        ):
            message = (
                "native evidence capability is not bound to the exact target boundary input"
            )
        else:
            return None
    return BlueprintGapRef(
        layer="evidence_qualification",
        object_kind="native_provider_payload_binding",
        object_id=object_id,
        status="blocked",
        owner_id=provider_id,
        expected_fingerprint=payload_fingerprint,
        observed_fingerprint=(
            dict(provider.payload_fingerprints).get(payload_id, "")
            if provider is not None
            else ""
        ),
        message=message,
    )


def _layer_for_kind(profile: str, kind: str) -> str:
    mapping = (
        _SOFTWARE_KIND_LAYERS
        if profile == SOFTWARE_TARGET_PROFILE
        else _WORKFLOW_KIND_LAYERS
    )
    return mapping.get(kind, "evidence_qualification")


def _member_denominator_gaps(
    native: TargetBlueprintNativeReportSet,
) -> list[BlueprintGapRef]:
    gaps: list[BlueprintGapRef] = []
    observed = {
        row.denominator_key: row
        for row in native.members
        if row.evidence_role == "observation"
    }
    declared = {
        row.denominator_key: row
        for row in native.members
        if row.evidence_role == "authority"
    }
    for kind_group in _REQUIRED_KIND_GROUPS[native.target_profile]:
        group_id = "|".join(kind_group)
        layer = _layer_for_kind(native.target_profile, kind_group[0])
        if not any(key[0] in kind_group for key in observed):
            gaps.append(
                BlueprintGapRef(
                    layer=layer,
                    object_kind="observed_member_kind",
                    object_id=group_id,
                    status="missing",
                    message="required native observation member kind is empty",
                )
            )
        if not any(key[0] in kind_group for key in declared):
            gaps.append(
                BlueprintGapRef(
                    layer=layer,
                    object_kind="declared_member_kind",
                    object_id=group_id,
                    status="missing",
                    message="required native authority member kind is empty",
                )
            )
    for key in sorted(set(observed) - set(declared)):
        row = observed[key]
        gaps.append(
            BlueprintGapRef(
                layer=_layer_for_kind(native.target_profile, row.member_kind),
                object_kind="observed_member_undeclared",
                object_id=f"{row.member_kind}:{row.member_id}",
                status="blocked",
                owner_id=row.provider_id,
                evidence_ref=row.payload_fingerprint,
                message="observed native member has no independent declaration",
            )
        )
    for key in sorted(set(declared) - set(observed)):
        row = declared[key]
        gaps.append(
            BlueprintGapRef(
                layer=_layer_for_kind(native.target_profile, row.member_kind),
                object_kind="declared_member_unobserved",
                object_id=f"{row.member_kind}:{row.member_id}",
                status="missing",
                owner_id=row.provider_id,
                evidence_ref=row.payload_fingerprint,
                message="declared native member is absent from independent observation",
            )
        )
    for key in sorted(set(observed) & set(declared)):
        observed_row = observed[key]
        declared_row = declared[key]
        if (
            observed_row.relation_contract_payload
            != declared_row.relation_contract_payload
        ):
            gaps.append(
                BlueprintGapRef(
                    layer=_layer_for_kind(
                        native.target_profile, observed_row.member_kind
                    ),
                    object_kind="native_member_contract_mismatch",
                    object_id=f"{observed_row.member_kind}:{observed_row.member_id}",
                    status="blocked",
                    owner_id=observed_row.provider_id,
                    expected_fingerprint=declared_row.payload_fingerprint,
                    observed_fingerprint=observed_row.payload_fingerprint,
                    message=(
                        "observed native member differs from its independent "
                        "authority relation or currentness contract"
                    ),
                )
            )
    for row in native.members:
        if row.subject_revision != native.subject_revision or row.status != "current":
            gaps.append(
                BlueprintGapRef(
                    layer=_layer_for_kind(native.target_profile, row.member_kind),
                    object_kind="native_member_currentness",
                    object_id=f"{row.evidence_role}:{row.member_kind}:{row.member_id}",
                    status=("stale" if row.status == "stale" else "blocked"),
                    owner_id=row.provider_id,
                    evidence_ref=row.payload_fingerprint,
                    expected_fingerprint=native.subject_revision,
                    observed_fingerprint=row.subject_revision,
                    message="native member is not current for the exact subject revision",
                )
            )
    return gaps


def _relation_gaps(
    native: TargetBlueprintNativeReportSet,
) -> list[BlueprintGapRef]:
    gaps: list[BlueprintGapRef] = []
    observed = tuple(
        row for row in native.members if row.evidence_role == "observation"
    )
    behavior_kind = (
        "behavior"
        if native.target_profile == SOFTWARE_TARGET_PROFILE
        else "transition"
    )
    behavior_ids = {
        row.member_id for row in observed if row.member_kind == behavior_kind
    }
    behavior_ids_by_role = {
        role: {
            row.member_id
            for row in native.members
            if row.evidence_role == role and row.member_kind == behavior_kind
        }
        for role in TARGET_NATIVE_MEMBER_ROLES
    }
    for row in native.members:
        unknown_behavior_ids = sorted(
            set(row.behavior_ids) - behavior_ids_by_role[row.evidence_role]
        )
        if unknown_behavior_ids:
            gaps.append(
                BlueprintGapRef(
                    layer=_layer_for_kind(native.target_profile, row.member_kind),
                    object_kind="native_behavior_relation_unknown",
                    object_id=(
                        f"{row.evidence_role}:{row.member_kind}:{row.member_id}"
                    ),
                    status="blocked",
                    owner_id=row.provider_id,
                    evidence_ref=row.payload_fingerprint,
                    message=(
                        "native member references behavior identities absent from "
                        f"its own independent denominator: {unknown_behavior_ids}"
                    ),
                )
            )
    required_related = (
        (("implementation", "external_owner"), "traceability"),
        (("interface",), "traceability"),
        (("input",), "traceability"),
        (("state",), "traceability"),
        (("output",), "traceability"),
        (("test", "verification"), "model_code_test"),
        (("resource",), "resource_oracle"),
        (("intent",), "resource_oracle"),
    ) if native.target_profile == SOFTWARE_TARGET_PROFILE else (
        (("boundary",), "workflow_boundary"),
        (("actor",), "workflow_actors"),
        (("input",), "workflow_inputs"),
        (("state",), "workflow_states"),
        (("output",), "workflow_outputs"),
        (("test", "verification"), "workflow_verification"),
        (("resource",), "workflow_resources"),
        (("intent",), "workflow_intent"),
    )
    related_kinds = {
        kind
        for kinds, _layer in required_related
        for kind in kinds
    }
    for row in native.members:
        if row.member_kind == behavior_kind and set(row.behavior_ids) != {row.member_id}:
            gaps.append(
                BlueprintGapRef(
                    layer=_layer_for_kind(native.target_profile, row.member_kind),
                    object_kind="native_behavior_self_relation",
                    object_id=f"{row.evidence_role}:{row.member_id}",
                    status="blocked",
                    owner_id=row.provider_id,
                    evidence_ref=row.payload_fingerprint,
                    message="native behavior must identify itself as its exact behavior relation",
                )
            )
        if row.member_kind in related_kinds and not row.behavior_ids:
            gaps.append(
                BlueprintGapRef(
                    layer=_layer_for_kind(native.target_profile, row.member_kind),
                    object_kind="native_member_behavior_relation_missing",
                    object_id=f"{row.evidence_role}:{row.member_kind}:{row.member_id}",
                    status="missing",
                    owner_id=row.provider_id,
                    evidence_ref=row.payload_fingerprint,
                    message="native member is orphaned from every exact behavior relation",
                )
            )
    for behavior_id in sorted(behavior_ids):
        for kinds, layer in required_related:
            rows = tuple(row for row in observed if row.member_kind in kinds)
            if rows and any(behavior_id in row.behavior_ids for row in rows):
                continue
            gaps.append(
                BlueprintGapRef(
                    layer=layer,
                    object_kind="native_behavior_relation",
                    object_id=f"{behavior_id}:{'|'.join(kinds)}",
                    status="missing",
                    message="behavior lacks an exact observed native member relation",
                )
            )
    return gaps


def _member_rows_by_role_and_kind(
    native: TargetBlueprintNativeReportSet,
) -> dict[str, dict[str, dict[str, TargetNativeMember]]]:
    return {
        role: {
            kind: {
                row.member_id: row
                for row in native.members
                if row.evidence_role == role and row.member_kind == kind
            }
            for kind in TARGET_NATIVE_MEMBER_KINDS
        }
        for role in TARGET_NATIVE_MEMBER_ROLES
    }


def _typed_relation_gaps(
    native: TargetBlueprintNativeReportSet,
) -> list[BlueprintGapRef]:
    """Check exact bidirectional ports plus model input/state/output coverage."""

    gaps: list[BlueprintGapRef] = []
    rows = _member_rows_by_role_and_kind(native)
    behavior_kind = (
        "behavior"
        if native.target_profile == SOFTWARE_TARGET_PROFILE
        else "transition"
    )
    models = {
        "observation": native.observed_model,
        "authority": native.authority_model,
    }
    for role in TARGET_NATIVE_MEMBER_ROLES:
        model = models[role]
        transitions_by_id = {
            transition.transition_id: transition
            for transition in model.transitions
        }
        for behavior in rows[role][behavior_kind].values():
            for port_kind, detail_field in (
                ("input", "input_ids"),
                ("state", "state_ids"),
                ("output", "output_ids"),
            ):
                expected_member_ids = {
                    row.member_id
                    for row in rows[role][port_kind].values()
                    if behavior.member_id in row.behavior_ids
                }
                declared_member_ids = set(behavior.details[detail_field])
                if declared_member_ids != expected_member_ids:
                    gaps.append(
                        BlueprintGapRef(
                            layer=(
                                "traceability"
                                if native.target_profile == SOFTWARE_TARGET_PROFILE
                                else _layer_for_kind(native.target_profile, port_kind)
                            ),
                            object_kind="native_behavior_port_relation",
                            object_id=f"{role}:{behavior.member_id}:{port_kind}",
                            status="blocked",
                            owner_id=behavior.provider_id,
                            evidence_ref=behavior.payload_fingerprint,
                            message=(
                                "behavior port ids do not equal the bidirectional "
                                f"{port_kind} member relation"
                            ),
                        )
                    )

            selected_transitions = tuple(
                transitions_by_id[transition_id]
                for transition_id in behavior.model_transition_ids
                if transition_id in transitions_by_id
            )
            expected_model_values = {
                "input": {
                    fingerprint_value(transition.input_symbol)
                    for transition in selected_transitions
                },
                "state": {
                    state_id
                    for transition in selected_transitions
                    for state_id in (
                        transition.source_state,
                        transition.target_state,
                    )
                },
                "output": {
                    fingerprint_value(transition.output_symbol)
                    for transition in selected_transitions
                },
            }
            observed_model_values: dict[str, set[str]] = {
                "input": set(),
                "state": set(),
                "output": set(),
            }
            for member_id in behavior.details["input_ids"]:
                member = rows[role]["input"].get(member_id)
                if member is not None:
                    observed_model_values["input"].update(
                        fingerprint_value(_thaw_json(value))
                        for value in member.details["model_input_values"]
                    )
            for member_id in behavior.details["state_ids"]:
                member = rows[role]["state"].get(member_id)
                if member is not None:
                    observed_model_values["state"].update(
                        member.details["model_state_ids"]
                    )
            for member_id in behavior.details["output_ids"]:
                member = rows[role]["output"].get(member_id)
                if member is not None:
                    observed_model_values["output"].update(
                        fingerprint_value(_thaw_json(value))
                        for value in member.details["model_output_values"]
                    )
            for port_kind in ("input", "state", "output"):
                if observed_model_values[port_kind] == expected_model_values[port_kind]:
                    continue
                gaps.append(
                    BlueprintGapRef(
                        layer=(
                            "traceability"
                            if native.target_profile == SOFTWARE_TARGET_PROFILE
                            else _layer_for_kind(native.target_profile, port_kind)
                        ),
                        object_kind="native_model_port_coverage",
                        object_id=f"{role}:{behavior.member_id}:{port_kind}",
                        status="blocked",
                        owner_id=behavior.provider_id,
                        evidence_ref=behavior.payload_fingerprint,
                        message=(
                            "typed port model bindings do not exactly cover the "
                            f"behavior's portable transition {port_kind} values"
                        ),
                    )
                )

            effect_ids = set(behavior.details["effect_ids"])
            error_ids = set(behavior.details["error_ids"])
            if not effect_ids or not error_ids:
                gaps.append(
                    BlueprintGapRef(
                        layer=(
                            "independent_semantics"
                            if native.target_profile == SOFTWARE_TARGET_PROFILE
                            else "workflow_transitions"
                        ),
                        object_kind="native_effect_error_relation",
                        object_id=f"{role}:{behavior.member_id}",
                        status="missing",
                        owner_id=behavior.provider_id,
                        evidence_ref=behavior.payload_fingerprint,
                        message=(
                            "behavior must declare exact effect and error identities"
                        ),
                    )
                )
            if native.target_profile == SOFTWARE_TARGET_PROFILE:
                for related_kind in (
                    "interface",
                    "implementation",
                    "external_owner",
                ):
                    for related in rows[role][related_kind].values():
                        if behavior.member_id not in related.behavior_ids:
                            continue
                        port_mismatch = any(
                            set(related.details[field_name])
                            != set(behavior.details[field_name])
                            for field_name in (
                                "input_ids",
                                "state_ids",
                                "output_ids",
                            )
                        )
                        if port_mismatch:
                            gaps.append(
                                BlueprintGapRef(
                                    layer="traceability",
                                    object_kind="native_behavior_port_relation",
                                    object_id=(
                                        f"{role}:{behavior.member_id}:{related_kind}:ports"
                                    ),
                                    status="blocked",
                                    owner_id=related.provider_id,
                                    evidence_ref=related.payload_fingerprint,
                                    message=(
                                        "software owner/interface ports differ from "
                                        "the model-bound behavior ports"
                                    ),
                                )
                            )
                        if (
                            set(related.details["effect_ids"]) != effect_ids
                            or set(related.details["error_ids"]) != error_ids
                        ):
                            gaps.append(
                                BlueprintGapRef(
                                    layer="traceability",
                                    object_kind="native_effect_error_relation",
                                    object_id=(
                                        f"{role}:{behavior.member_id}:{related_kind}"
                                    ),
                                    status="blocked",
                                    owner_id=related.provider_id,
                                    evidence_ref=related.payload_fingerprint,
                                    message=(
                                        "software owner/interface effect or error ids "
                                        "differ from the model-bound behavior contract"
                                    ),
                                )
                            )
    return gaps


def _intent_contribution_gaps(
    native: TargetBlueprintNativeReportSet,
) -> list[BlueprintGapRef]:
    gaps: list[BlueprintGapRef] = []
    behavior_kind = (
        "behavior"
        if native.target_profile == SOFTWARE_TARGET_PROFILE
        else "transition"
    )
    models = {
        "observation": native.observed_model,
        "authority": native.authority_model,
    }
    rows = _member_rows_by_role_and_kind(native)
    for role in TARGET_NATIVE_MEMBER_ROLES:
        for intent in rows[role]["intent"].values():
            contribution_status = intent.details["contribution_status"]
            conflicts = intent.details["conflicts_with_contribution_ids"]
            if contribution_status != "current" or conflicts:
                gaps.append(
                    BlueprintGapRef(
                        layer=_layer_for_kind(native.target_profile, "intent"),
                        object_kind="native_intent_contribution_currentness",
                        object_id=f"{role}:{intent.member_id}",
                        status=(
                            "stale"
                            if contribution_status == "stale"
                            else "blocked"
                        ),
                        owner_id=intent.provider_id,
                        evidence_ref=intent.payload_fingerprint,
                        message=(
                            "intent contribution is stale, contradictory, blocked, "
                            "or declares an unresolved contribution conflict"
                        ),
                    )
                )
            if intent.details["authority_revision"] != native.subject_revision:
                gaps.append(
                    BlueprintGapRef(
                        layer=_layer_for_kind(native.target_profile, "intent"),
                        object_kind="native_intent_authority_currentness",
                        object_id=f"{role}:{intent.member_id}",
                        status="stale",
                        owner_id=intent.provider_id,
                        evidence_ref=intent.payload_fingerprint,
                        expected_fingerprint=native.subject_revision,
                        observed_fingerprint=intent.details["authority_revision"],
                        message=(
                            "intent authority revision differs from the exact target revision"
                        ),
                    )
                )
            if set(intent.details["model_ids"]) != {models[role].model_id}:
                gaps.append(
                    BlueprintGapRef(
                        layer=_layer_for_kind(native.target_profile, "intent"),
                        object_kind="native_intent_model_binding",
                        object_id=f"{role}:{intent.member_id}:model",
                        status="blocked",
                        owner_id=intent.provider_id,
                        evidence_ref=intent.payload_fingerprint,
                        message=(
                            "intent contribution does not name the exact role-owned model"
                        ),
                    )
                )
            expected_transition_ids: set[str] = set()
            for behavior_id in intent.behavior_ids:
                behavior = rows[role][behavior_kind].get(behavior_id)
                if behavior is not None:
                    expected_transition_ids.update(behavior.model_transition_ids)
            if set(intent.details["model_transition_ids"]) != expected_transition_ids:
                gaps.append(
                    BlueprintGapRef(
                        layer=_layer_for_kind(native.target_profile, "intent"),
                        object_kind="native_intent_model_binding",
                        object_id=f"{role}:{intent.member_id}:transitions",
                        status="blocked",
                        owner_id=intent.provider_id,
                        evidence_ref=intent.payload_fingerprint,
                        message=(
                            "intent contribution transition ids do not equal the exact "
                            "transitions of its bound behaviors"
                        ),
                    )
                )
    return gaps


def _native_lifecycle_gaps(
    native: TargetBlueprintNativeReportSet,
) -> list[BlueprintGapRef]:
    gaps: list[BlueprintGapRef] = []
    for row in native.members:
        if row.member_kind == "resource" and row.details["lifecycle_status"] != "current":
            gaps.append(
                BlueprintGapRef(
                    layer=_layer_for_kind(native.target_profile, "resource"),
                    object_kind="native_resource_currentness",
                    object_id=f"{row.evidence_role}:{row.member_id}",
                    status=(
                        "stale"
                        if row.details["lifecycle_status"] == "stale"
                        else "blocked"
                    ),
                    owner_id=row.provider_id,
                    evidence_ref=row.payload_fingerprint,
                    message="native resource lifecycle evidence is not current",
                )
            )
        if (
            row.member_kind in {"test", "verification"}
            and row.details["execution_status"] in {"failed", "blocked", "stale"}
        ):
            gaps.append(
                BlueprintGapRef(
                    layer=_layer_for_kind(native.target_profile, row.member_kind),
                    object_kind="native_test_execution",
                    object_id=f"{row.evidence_role}:{row.member_id}",
                    status=(
                        "stale"
                        if row.details["execution_status"] == "stale"
                        else "blocked"
                    ),
                    owner_id=row.provider_id,
                    evidence_ref=row.details["receipt_fingerprint"],
                    message="native test receipt reports failed, blocked, or stale evidence",
                )
            )
    return gaps


def _native_execution_status(native: TargetBlueprintNativeReportSet) -> str:
    statuses = {
        row.details["execution_status"]
        for row in native.members
        if row.evidence_role == "observation"
        and row.member_kind in {"test", "verification"}
    }
    if "failed" in statuses:
        return "failed"
    if "blocked" in statuses:
        return "blocked"
    if "stale" in statuses:
        return "stale"
    if statuses and statuses == {"passed"}:
        return "passed"
    return "not_run"


def _model_transition_binding_gaps(
    native: TargetBlueprintNativeReportSet,
) -> list[BlueprintGapRef]:
    gaps: list[BlueprintGapRef] = []
    member_kind = (
        "behavior"
        if native.target_profile == SOFTWARE_TARGET_PROFILE
        else "transition"
    )
    layer = (
        "independent_semantics"
        if native.target_profile == SOFTWARE_TARGET_PROFILE
        else "workflow_transitions"
    )
    models = {
        "observation": native.observed_model,
        "authority": native.authority_model,
    }
    rows_by_role = {
        role: {
            row.denominator_key: row
            for row in native.members
            if row.evidence_role == role and row.member_kind == member_kind
        }
        for role in TARGET_NATIVE_MEMBER_ROLES
    }
    for role, model in models.items():
        known_transition_ids = {row.transition_id for row in model.transitions}
        bound_transition_ids: set[str] = set()
        for row in rows_by_role[role].values():
            if not row.model_transition_ids:
                gaps.append(
                    BlueprintGapRef(
                        layer=layer,
                        object_kind="native_behavior_model_binding",
                        object_id=f"{role}:{row.member_id}",
                        status="missing",
                        owner_id=row.provider_id,
                        evidence_ref=row.payload_fingerprint,
                        message=(
                            "native behavior or workflow transition has no exact "
                            "portable-model transition binding"
                        ),
                    )
                )
                continue
            unknown = sorted(set(row.model_transition_ids) - known_transition_ids)
            if unknown:
                gaps.append(
                    BlueprintGapRef(
                        layer=layer,
                        object_kind="native_behavior_model_binding",
                        object_id=f"{role}:{row.member_id}",
                        status="blocked",
                        owner_id=row.provider_id,
                        evidence_ref=row.payload_fingerprint,
                        message=(
                            "native behavior names portable transitions absent from "
                            f"the {role} model: {unknown}"
                        ),
                    )
                )
            bound_transition_ids.update(row.model_transition_ids)
        for transition_id in sorted(known_transition_ids - bound_transition_ids):
            gaps.append(
                BlueprintGapRef(
                    layer=layer,
                    object_kind="portable_transition_unbound",
                    object_id=f"{role}:{transition_id}",
                    status="missing",
                    message=(
                        "portable-model transition is absent from the independently "
                        "enumerated native behavior denominator"
                    ),
                )
            )

    observed = rows_by_role["observation"]
    authority = rows_by_role["authority"]
    transition_mapping = dict(native.refinement_binding.transition_mapping)
    for key in sorted(set(observed) & set(authority)):
        observed_row = observed[key]
        authority_row = authority[key]
        mapped = {
            transition_mapping[transition_id]
            for transition_id in observed_row.model_transition_ids
            if transition_id in transition_mapping
        }
        missing_mapping = sorted(
            set(observed_row.model_transition_ids) - set(transition_mapping)
        )
        if missing_mapping or mapped != set(authority_row.model_transition_ids):
            gaps.append(
                BlueprintGapRef(
                    layer=layer,
                    object_kind="native_behavior_refinement_binding",
                    object_id=observed_row.member_id,
                    status="blocked",
                    owner_id=observed_row.provider_id,
                    expected_fingerprint=authority_row.payload_fingerprint,
                    observed_fingerprint=observed_row.payload_fingerprint,
                    message=(
                        "observed behavior transitions do not map exactly to the "
                        "independent authority behavior transitions"
                    ),
                )
            )
    return gaps


def qualify_target_system_from_native_reports(
    descriptor: TargetSystemDescriptor,
    frozen_evidence: FrozenTargetSystemEvidence,
    native: TargetBlueprintNativeReportSet,
) -> TargetSystemBlueprintReport:
    """Derive one whole-target qualification; affected reads have a separate owner."""

    if (
        native.target_system_id != descriptor.target_system_id
        or native.target_profile != descriptor.target_profile
        or native.subject_revision != descriptor.subject_revision
        or native.target_profile not in _REQUIRED_KINDS
    ):
        raise TargetSystemBlueprintError(
            "native report set identity differs from the target descriptor"
        )
    if frozen_evidence.layer_plan.target_profile != native.target_profile:
        raise TargetSystemBlueprintError(
            "native report set profile differs from the frozen layer plan"
        )

    gaps: list[BlueprintGapRef] = []
    for object_kind, expected, observed in (
        (
            "native_descriptor_identity",
            descriptor.fingerprint,
            native.descriptor_fingerprint,
        ),
        (
            "native_boundary_identity",
            descriptor.boundary_fingerprint,
            native.boundary_fingerprint,
        ),
        (
            "native_frozen_evidence_identity",
            frozen_evidence.fingerprint,
            native.frozen_evidence_fingerprint,
        ),
    ):
        if observed != expected:
            gaps.append(
                BlueprintGapRef(
                    layer="evidence_qualification",
                    object_kind=object_kind,
                    object_id=native.target_system_id,
                    status="stale",
                    expected_fingerprint=expected,
                    observed_fingerprint=observed,
                    message=(
                        "native report set is not bound to the exact current target "
                        "descriptor, boundary, and frozen provider evidence"
                    ),
                )
            )
    model_by_role = {
        "observation": native.observed_model,
        "authority": native.authority_model,
    }
    for ref in native.model_refs:
        model = model_by_role[ref.evidence_role]
        if ref.model_id != model.model_id or ref.model_fingerprint != model.fingerprint:
            gaps.append(
                BlueprintGapRef(
                    layer="evidence_qualification",
                    object_kind="native_model_identity",
                    object_id=f"{ref.evidence_role}:{ref.model_id}",
                    status="stale",
                    owner_id=ref.provider_id,
                    expected_fingerprint=model.fingerprint,
                    observed_fingerprint=ref.model_fingerprint,
                    message="native model ref differs from the supplied portable model",
                )
            )
        if ref.payload_fingerprint != model.fingerprint:
            gaps.append(
                BlueprintGapRef(
                    layer="evidence_qualification",
                    object_kind="native_model_payload_identity",
                    object_id=f"{ref.evidence_role}:{ref.payload_id}",
                    status="stale",
                    owner_id=ref.provider_id,
                    expected_fingerprint=model.fingerprint,
                    observed_fingerprint=ref.payload_fingerprint,
                    message="portable model content differs from its provider payload",
                )
            )
        binding_gap = _provider_binding_gap(
            descriptor=descriptor,
            frozen=frozen_evidence,
            provider_id=ref.provider_id,
            evidence_role=ref.evidence_role,
            capability_id=ref.capability_id,
            payload_id=ref.payload_id,
            payload_fingerprint=ref.payload_fingerprint,
            object_id=f"model:{ref.evidence_role}:{ref.model_id}",
        )
        if binding_gap is not None:
            gaps.append(binding_gap)
    for row in native.members:
        binding_gap = _provider_binding_gap(
            descriptor=descriptor,
            frozen=frozen_evidence,
            provider_id=row.provider_id,
            evidence_role=row.evidence_role,
            capability_id=row.capability_id,
            payload_id=row.payload_id,
            payload_fingerprint=row.payload_fingerprint,
            object_id=f"member:{row.evidence_role}:{row.member_kind}:{row.member_id}",
        )
        if binding_gap is not None:
            gaps.append(binding_gap)
    gaps.extend(_member_denominator_gaps(native))
    gaps.extend(_relation_gaps(native))
    gaps.extend(_typed_relation_gaps(native))
    gaps.extend(_intent_contribution_gaps(native))
    gaps.extend(_native_lifecycle_gaps(native))
    gaps.extend(_model_transition_binding_gaps(native))

    refinement_layer = (
        "independent_semantics"
        if native.target_profile == SOFTWARE_TARGET_PROFILE
        else "workflow_transitions"
    )
    binding = native.refinement_binding
    if (
        binding.parent_model_id != native.authority_model.model_id
        or binding.child_model_id != native.observed_model.model_id
        or binding.parent_model_fingerprint != native.authority_model.fingerprint
        or binding.child_model_fingerprint != native.observed_model.fingerprint
    ):
        gaps.append(
            BlueprintGapRef(
                layer=refinement_layer,
                object_kind="portable_refinement_binding_identity",
                object_id=f"{binding.child_model_id}->{binding.parent_model_id}",
                status="blocked",
                expected_fingerprint=fingerprint_value(
                    {
                        "parent_model_id": native.authority_model.model_id,
                        "parent_model_fingerprint": native.authority_model.fingerprint,
                        "child_model_id": native.observed_model.model_id,
                        "child_model_fingerprint": native.observed_model.fingerprint,
                    }
                ),
                observed_fingerprint=fingerprint_value(
                    {
                        "parent_model_id": binding.parent_model_id,
                        "parent_model_fingerprint": binding.parent_model_fingerprint,
                        "child_model_id": binding.child_model_id,
                        "child_model_fingerprint": binding.child_model_fingerprint,
                    }
                ),
                message=(
                    "portable refinement binding does not name the exact supplied "
                    "authority and observation model identities"
                ),
            )
        )

    portable_checks = {
        role: check_portable_model(model)
        for role, model in model_by_role.items()
    }
    for role, check in portable_checks.items():
        if check.ok:
            continue
        if check.findings:
            for finding in check.findings:
                gaps.append(
                    BlueprintGapRef(
                        layer=refinement_layer,
                        object_kind="portable_model_finding",
                        object_id=f"{role}:{finding.finding_id}",
                        status="blocked",
                        evidence_ref=check.model_fingerprint,
                        message=finding.message,
                    )
                )
        else:
            gaps.append(
                BlueprintGapRef(
                    layer=refinement_layer,
                    object_kind="portable_model_status",
                    object_id=f"{role}:{check.status}",
                    status="blocked",
                    evidence_ref=check.model_fingerprint,
                    message=(
                        "; ".join(check.blockers)
                        or "portable model did not pass its own safety and temporal checks"
                    ),
                )
            )

    refinement = native.refinement_report
    if not refinement.ok:
        for finding in refinement.findings or ():
            gaps.append(
                BlueprintGapRef(
                    layer=refinement_layer,
                    object_kind="portable_refinement_finding",
                    object_id=finding.finding_id,
                    status="blocked",
                    evidence_ref=refinement.model_fingerprint,
                    message=finding.message,
                )
            )
        if not refinement.findings:
            gaps.append(
                BlueprintGapRef(
                    layer=refinement_layer,
                    object_kind="portable_refinement_status",
                    object_id=refinement.status,
                    status="blocked",
                    evidence_ref=refinement.model_fingerprint,
                    message="portable target refinement did not pass",
                )
            )

    provider_fingerprints = tuple(
        row.fingerprint for row in frozen_evidence.provider_results
    )
    portable_check_fingerprints = tuple(
        fingerprint_value(portable_checks[role].to_dict())
        for role in TARGET_NATIVE_MEMBER_ROLES
    )
    downstream: list[BlueprintLayerResult] = []
    prior_layer_report_fingerprints: list[str] = []
    for layer in frozen_evidence.layer_plan.layer_ids[1:]:
        layer_gaps = tuple(row for row in gaps if row.layer == layer)
        member_ids = tuple(
            sorted(
                f"{row.evidence_role}:{row.member_kind}:{row.member_id}"
                for row in native.members
                if _layer_for_kind(native.target_profile, row.member_kind) == layer
            )
        )
        report_payload = {
            "schema_version": TARGET_NATIVE_QUALIFICATION_SCHEMA,
            "native_report_set_fingerprint": native.fingerprint,
            "layer": layer,
            "member_ids": list(member_ids),
            "member_payload_fingerprints": [
                row.payload_fingerprint
                for row in native.members
                if _layer_for_kind(native.target_profile, row.member_kind) == layer
            ],
            "prior_layer_report_fingerprints": list(
                prior_layer_report_fingerprints
            ),
            "refinement_report": (
                refinement.to_dict() if layer == refinement_layer else None
            ),
            "portable_model_checks": (
                {
                    role: portable_checks[role].to_dict()
                    for role in TARGET_NATIVE_MEMBER_ROLES
                }
                if layer == refinement_layer
                else None
            ),
            "gap_ids": [row.gap_id for row in layer_gaps],
        }
        report_fingerprint = fingerprint_value(report_payload)
        prior_layer_report_fingerprints.append(report_fingerprint)
        native_ref = BlueprintNativeReportRef(
            owner_id=f"target-native-aggregate:{native.target_profile}:{layer}",
            report_id=(
                f"target-native-aggregate-report:{native.target_system_id}:{layer}"
            ),
            report_fingerprint=report_fingerprint,
        )
        if layer_gaps:
            status = (
                "stale"
                if all(row.status == "stale" for row in layer_gaps)
                else "blocked"
            )
            gap_ids = tuple(row.gap_id for row in layer_gaps)
            pre_code_status = status
        else:
            status = "pass"
            gap_ids = ()
            pre_code_status = (
                "ready"
                if native.target_profile == SOFTWARE_TARGET_PROFILE
                else "not_applicable"
            )
        downstream.append(
            BlueprintLayerResult._derived(
                layer=layer,
                status=status,
                evidence_ids=(
                    native.fingerprint,
                    report_fingerprint,
                    refinement.model_fingerprint,
                    *portable_check_fingerprints,
                    *provider_fingerprints,
                ),
                gap_ids=gap_ids,
                native_reports=(native_ref,),
                pre_code_status=pre_code_status,
                executed_evidence_status=(
                    _native_execution_status(native)
                    if layer
                    in {
                        "model_code_test",
                        "workflow_verification",
                    }
                    else "not_applicable"
                ),
            )
        )
    return _assemble_target_system_blueprint(
        descriptor,
        frozen_evidence,
        downstream_layers=tuple(downstream),
        downstream_gaps=tuple(gaps),
        scope="whole",
    )


__all__ = [
    "TARGET_NATIVE_INTENT_SOURCE_KINDS",
    "TARGET_NATIVE_MEMBER_KINDS",
    "TARGET_NATIVE_MEMBER_ROLES",
    "TARGET_NATIVE_MEMBER_STATUSES",
    "TARGET_NATIVE_QUALIFICATION_SCHEMA",
    "TargetBlueprintNativeReportSet",
    "TargetNativeMember",
    "TargetNativeModelRef",
    "load_target_blueprint_native_report_set",
    "qualify_target_system_from_native_reports",
    "serialize_target_blueprint_native_report_set",
    "target_native_test_obligation_id",
]
