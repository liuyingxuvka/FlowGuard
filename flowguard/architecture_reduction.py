"""Model-backed architecture reduction review helpers.

Architecture reduction reviews whether a modeled flow can support simpler code
structure. Ordinary contraction must preserve declared observable behavior;
intentional retirement may change behavior only through one complete current
retirement proof. The review reports actions and handoff requirements; it does
not rewrite production code.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ._normalization import string_sequence as _as_tuple
from .code_structure import CodeStructureRecommendation, review_code_structure_recommendation
from .export import to_jsonable
from .canonical_relation import (
    CanonicalRelationHandoff,
    normalize_canonical_relation_handoff,
)


ARCHITECTURE_REDUCTION_ROUTE = "architecture_reduction"

CANDIDATE_MERGE_HANDLERS = "merge_handlers"
CANDIDATE_MERGE_MODULES = "merge_modules"
CANDIDATE_COLLAPSE_ADAPTER = "collapse_adapter"
CANDIDATE_REMOVE_BRANCH = "remove_branch"
CANDIDATE_REMOVE_STATE_FIELD = "remove_state_field"
CANDIDATE_MERGE_STATE_PHASE = "merge_state_phase"
CANDIDATE_REMOVE_DUPLICATE_VALIDATION = "remove_duplicate_validation"
CANDIDATE_KEEP_PUBLIC_FACADE = "keep_public_facade"
CANDIDATE_MANUAL_REVIEW = "manual_review"

ARCHITECTURE_REDUCTION_CANDIDATE_TYPES = {
    CANDIDATE_MERGE_HANDLERS,
    CANDIDATE_MERGE_MODULES,
    CANDIDATE_COLLAPSE_ADAPTER,
    CANDIDATE_REMOVE_BRANCH,
    CANDIDATE_REMOVE_STATE_FIELD,
    CANDIDATE_MERGE_STATE_PHASE,
    CANDIDATE_REMOVE_DUPLICATE_VALIDATION,
    CANDIDATE_KEEP_PUBLIC_FACADE,
    CANDIDATE_MANUAL_REVIEW,
}

PROOF_SAFE_BY_EQUIVALENCE = "safe_by_equivalence"
PROOF_SAFE_BY_PUBLIC_FACADE = "safe_by_public_facade"
PROOF_PROPERTY_ONLY_SAFE = "property_only_safe"
PROOF_NEEDS_CONFORMANCE_REPLAY = "needs_conformance_replay"
PROOF_RISKY_KEEP = "risky_keep"
PROOF_BLOCKED_BY_MISSING_EVIDENCE = "blocked_by_missing_evidence"
PROOF_AUTHORIZED_RETIREMENT = "authorized_retirement"

ARCHITECTURE_REDUCTION_PROOF_STATUSES = {
    PROOF_SAFE_BY_EQUIVALENCE,
    PROOF_SAFE_BY_PUBLIC_FACADE,
    PROOF_PROPERTY_ONLY_SAFE,
    PROOF_NEEDS_CONFORMANCE_REPLAY,
    PROOF_RISKY_KEEP,
    PROOF_BLOCKED_BY_MISSING_EVIDENCE,
    PROOF_AUTHORIZED_RETIREMENT,
}

READY_PROOF_STATUSES = {
    PROOF_SAFE_BY_EQUIVALENCE,
    PROOF_SAFE_BY_PUBLIC_FACADE,
}

CANDIDATE_DISPOSITION_ACTIVE = "active"
CANDIDATE_DISPOSITION_COMPLETED = "completed"
CANDIDATE_DISPOSITION_HISTORICAL = "historical"

ARCHITECTURE_REDUCTION_CANDIDATE_DISPOSITIONS = {
    CANDIDATE_DISPOSITION_ACTIVE,
    CANDIDATE_DISPOSITION_COMPLETED,
    CANDIDATE_DISPOSITION_HISTORICAL,
}

TARGET_ACTION_MERGE = "merge"
TARGET_ACTION_COLLAPSE = "collapse"
TARGET_ACTION_REMOVE = "remove"
TARGET_ACTION_KEEP_FACADE = "keep_facade"
TARGET_ACTION_MANUAL_REVIEW = "manual_review"
TARGET_ACTION_RETIRE_BEHAVIOR = "retire_behavior"

ARCHITECTURE_REDUCTION_TARGET_ACTIONS = {
    TARGET_ACTION_MERGE,
    TARGET_ACTION_COLLAPSE,
    TARGET_ACTION_REMOVE,
    TARGET_ACTION_KEEP_FACADE,
    TARGET_ACTION_MANUAL_REVIEW,
    TARGET_ACTION_RETIRE_BEHAVIOR,
}

ARCHITECTURE_REDUCTION_STEP_COST_SCHEMA = (
    "flowguard.architecture_reduction_step_cost.v1"
)
ARCHITECTURE_REDUCTION_STEP_ASSESSMENT_SCHEMA = (
    "flowguard.architecture_reduction_step_assessment.v1"
)

STEP_KIND_SCAN = "scan"
STEP_KIND_REFLECTION = "reflection"
STEP_KIND_EVIDENCE_PROJECTION = "evidence_projection"
STEP_KIND_SERIALIZATION = "serialization"
STEP_KIND_PAYLOAD_MATERIALIZATION = "payload_materialization"
STEP_KIND_VALIDATION = "validation"
STEP_KIND_BRANCH = "branch"
STEP_KIND_HELPER = "helper"
STEP_KIND_BUILDER = "builder"
STEP_KIND_ADAPTER = "adapter"
STEP_KIND_ROUTE_DISPATCH = "route_dispatch"
STEP_KIND_MODULE_BOUNDARY = "module_boundary"
STEP_KIND_OTHER = "other"

ARCHITECTURE_REDUCTION_STEP_KINDS = {
    STEP_KIND_SCAN,
    STEP_KIND_REFLECTION,
    STEP_KIND_EVIDENCE_PROJECTION,
    STEP_KIND_SERIALIZATION,
    STEP_KIND_PAYLOAD_MATERIALIZATION,
    STEP_KIND_VALIDATION,
    STEP_KIND_BRANCH,
    STEP_KIND_HELPER,
    STEP_KIND_BUILDER,
    STEP_KIND_ADAPTER,
    STEP_KIND_ROUTE_DISPATCH,
    STEP_KIND_MODULE_BOUNDARY,
    STEP_KIND_OTHER,
}

STEP_ACTION_RETAIN = "retain"
STEP_ACTION_MERGE = "merge"
STEP_ACTION_DELEGATE = "delegate"
STEP_ACTION_REMOVE = "remove"
STEP_ACTION_EXPLICIT_ON_DEMAND = "explicit_on_demand"
STEP_ACTION_UNRESOLVED = "unresolved"

ARCHITECTURE_REDUCTION_STEP_ACTIONS = {
    STEP_ACTION_RETAIN,
    STEP_ACTION_MERGE,
    STEP_ACTION_DELEGATE,
    STEP_ACTION_REMOVE,
    STEP_ACTION_EXPLICIT_ON_DEMAND,
    STEP_ACTION_UNRESOLVED,
}

_STEP_CONTRACTION_ACTIONS = {
    STEP_ACTION_MERGE,
    STEP_ACTION_DELEGATE,
    STEP_ACTION_REMOVE,
    STEP_ACTION_EXPLICIT_ON_DEMAND,
}

ARCHITECTURE_RETIREMENT_PROOF_SCHEMA = (
    "flowguard.architecture_retirement_proof.v1"
)
ARCHITECTURE_RETIREMENT_RESPONSIBILITY_DISPOSITION_SCHEMA = (
    "flowguard.architecture_retirement_responsibility_disposition.v1"
)

RETIREMENT_DISPOSITION_RETIRE = "retire"
RETIREMENT_DISPOSITION_REPLACE = "replace"
RETIREMENT_DISPOSITION_MIGRATE = "migrate"
RETIREMENT_DISPOSITION_RETAIN_HISTORY = "retain_history"
ARCHITECTURE_RETIREMENT_DISPOSITIONS = {
    RETIREMENT_DISPOSITION_RETIRE,
    RETIREMENT_DISPOSITION_REPLACE,
    RETIREMENT_DISPOSITION_MIGRATE,
    RETIREMENT_DISPOSITION_RETAIN_HISTORY,
}
FORBIDDEN_RETIREMENT_DISPOSITIONS = {
    "alias",
    "compatibility",
    "compatibility_reader",
    "fallback",
    "forwarder",
}

RETIREMENT_OWNER_STATUS_EXACT_CURRENT = "exact_current"
RETIREMENT_OWNER_STATUS_NOT_APPLICABLE = "not_applicable"
ARCHITECTURE_RETIREMENT_OWNER_STATUSES = {
    RETIREMENT_OWNER_STATUS_EXACT_CURRENT,
    RETIREMENT_OWNER_STATUS_NOT_APPLICABLE,
}

RETIREMENT_RESPONSIBILITY_COMMITMENT = "commitment"
RETIREMENT_RESPONSIBILITY_BEHAVIOR = "behavior"
RETIREMENT_RESPONSIBILITY_CODE = "code"
RETIREMENT_RESPONSIBILITY_TEST = "test"
RETIREMENT_RESPONSIBILITY_MODEL = "model"
RETIREMENT_RESPONSIBILITY_PUBLIC_SURFACE = "public_surface"
RETIREMENT_RESPONSIBILITY_CONSUMER = "consumer"
RETIREMENT_RESPONSIBILITY_NEGATIVE_CASE = "negative_case"
RETIREMENT_RESPONSIBILITY_ROUTE = "route"
RETIREMENT_RESPONSIBILITY_SKILL = "skill"
RETIREMENT_RESPONSIBILITY_PROMPT = "prompt"
RETIREMENT_RESPONSIBILITY_TOPOLOGY_RELATION = "topology_relation"
RETIREMENT_RESPONSIBILITY_RELEASE_CLAIM = "release_claim"

ARCHITECTURE_RETIREMENT_RESPONSIBILITY_KINDS = {
    RETIREMENT_RESPONSIBILITY_COMMITMENT,
    RETIREMENT_RESPONSIBILITY_BEHAVIOR,
    RETIREMENT_RESPONSIBILITY_CODE,
    RETIREMENT_RESPONSIBILITY_TEST,
    RETIREMENT_RESPONSIBILITY_MODEL,
    RETIREMENT_RESPONSIBILITY_PUBLIC_SURFACE,
    RETIREMENT_RESPONSIBILITY_CONSUMER,
    RETIREMENT_RESPONSIBILITY_NEGATIVE_CASE,
    RETIREMENT_RESPONSIBILITY_ROUTE,
    RETIREMENT_RESPONSIBILITY_SKILL,
    RETIREMENT_RESPONSIBILITY_PROMPT,
    RETIREMENT_RESPONSIBILITY_TOPOLOGY_RELATION,
    RETIREMENT_RESPONSIBILITY_RELEASE_CLAIM,
}

ARCHITECTURE_RETIREMENT_GOVERNED_IDENTITY_ROLES = {
    "retirement_inventory",
    "observed_model_system",
    "behavior_commitment_ledger",
    "software_blueprint",
    "code_bindings",
    "test_bindings",
    "public_surface_inventory",
    "consumer_inventory",
    "negative_case_inventory",
    "route_topology",
    "release_claim_inventory",
}

ROUTE_DEVELOPMENT_PROCESS_FLOW = "development_process_flow"
ROUTE_EXISTING_MODEL_PREFLIGHT = "existing_model_preflight"
ROUTE_CODE_STRUCTURE_RECOMMENDATION = "code_structure_recommendation"
ROUTE_STRUCTURE_MESH = "structure_mesh"
ROUTE_MODEL_MESH = "model_mesh"
ROUTE_MODEL_TEST_ALIGNMENT = "model_test_alignment"
ROUTE_UI_FLOW_STRUCTURE = "ui_flow_structure"
ROUTE_CONFORMANCE_REPLAY = "conformance_replay"
ROUTE_MANUAL_REVIEW = "manual_review"

ARCHITECTURE_REDUCTION_COMPANION_ROUTES = {
    ROUTE_DEVELOPMENT_PROCESS_FLOW,
    ROUTE_EXISTING_MODEL_PREFLIGHT,
    ROUTE_CODE_STRUCTURE_RECOMMENDATION,
    ROUTE_STRUCTURE_MESH,
    ROUTE_MODEL_MESH,
    ROUTE_MODEL_TEST_ALIGNMENT,
    ROUTE_UI_FLOW_STRUCTURE,
    ROUTE_CONFORMANCE_REPLAY,
    ROUTE_MANUAL_REVIEW,
}

ARCHITECTURE_RETIREMENT_REQUIRED_ROUTES = {
    ROUTE_DEVELOPMENT_PROCESS_FLOW,
    ROUTE_STRUCTURE_MESH,
    ROUTE_MODEL_MESH,
    ROUTE_MODEL_TEST_ALIGNMENT,
}

COMPATIBILITY_SURFACE_CURRENT_CONTRACT = "current_contract"
COMPATIBILITY_SURFACE_BOUNDARY_ADAPTER = "boundary_adapter"
COMPATIBILITY_SURFACE_NEGATIVE_LEGACY_TEST = "negative_legacy_test"
COMPATIBILITY_SURFACE_ARCHIVE_ONLY = "archive_only"
COMPATIBILITY_SURFACE_PRUNE_CANDIDATE = "prune_candidate"
COMPATIBILITY_SURFACE_EVIDENCE_NEEDED = "evidence_needed"

COMPATIBILITY_SURFACE_CLASSIFICATIONS = {
    COMPATIBILITY_SURFACE_CURRENT_CONTRACT,
    COMPATIBILITY_SURFACE_BOUNDARY_ADAPTER,
    COMPATIBILITY_SURFACE_NEGATIVE_LEGACY_TEST,
    COMPATIBILITY_SURFACE_ARCHIVE_ONLY,
    COMPATIBILITY_SURFACE_PRUNE_CANDIDATE,
    COMPATIBILITY_SURFACE_EVIDENCE_NEEDED,
}

COMPATIBILITY_ACTION_KEEP = "keep"
COMPATIBILITY_ACTION_ADAPT = "adapt"
COMPATIBILITY_ACTION_REJECT = "reject"
COMPATIBILITY_ACTION_ARCHIVE = "archive"
COMPATIBILITY_ACTION_PRUNE = "prune"
COMPATIBILITY_ACTION_COLLECT_EVIDENCE = "collect_evidence"

COMPATIBILITY_SURFACE_RECOMMENDED_ACTIONS = {
    COMPATIBILITY_ACTION_KEEP,
    COMPATIBILITY_ACTION_ADAPT,
    COMPATIBILITY_ACTION_REJECT,
    COMPATIBILITY_ACTION_ARCHIVE,
    COMPATIBILITY_ACTION_PRUNE,
    COMPATIBILITY_ACTION_COLLECT_EVIDENCE,
}


def _strict_current_mapping(
    value: Any,
    *,
    fields: set[str],
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    data = dict(value)
    actual = set(data)
    if actual != fields:
        missing = sorted(fields - actual)
        unknown = sorted(actual - fields)
        raise ValueError(
            f"{label} must use the current schema exactly; "
            f"missing={missing}, unknown={unknown}"
        )
    return data


def _strict_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value


def _strict_string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) for item in value
    ):
        raise ValueError(f"{field_name} must be an array of strings")
    return tuple(value)


def _strict_string_map(value: Any, field_name: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) or not isinstance(item, str)
        for key, item in value.items()
    ):
        raise ValueError(f"{field_name} must be a string-to-string object")
    return dict(value)


def _strict_non_negative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _fingerprint_payload(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        to_jsonable(dict(payload)),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ArchitectureReductionStepCost:
    """Current measured cost used only to prioritize a step review.

    These measurements never contribute to ``is_ready`` or substitute for
    observable-equivalence, facade-delegation, or safety-owner evidence.
    """

    measurement_id: str
    subject_revision: str
    source_ref: str
    measurement_mode: str
    operation_count: int = 0
    payload_bytes: int = 0
    estimated_token_count: int = 0
    invocation_count: int = 0
    current: bool = True
    rationale: str = ""
    schema_version: str = ARCHITECTURE_REDUCTION_STEP_COST_SCHEMA

    def __post_init__(self) -> None:
        for name in (
            "measurement_id",
            "subject_revision",
            "source_ref",
            "measurement_mode",
            "rationale",
            "schema_version",
        ):
            value = str(getattr(self, name))
            object.__setattr__(self, name, value)
            if not value.strip():
                raise ValueError(f"architecture reduction step cost requires {name}")
        if self.schema_version != ARCHITECTURE_REDUCTION_STEP_COST_SCHEMA:
            raise ValueError(
                "architecture reduction step cost requires the current schema"
            )
        for name in (
            "operation_count",
            "payload_bytes",
            "estimated_token_count",
            "invocation_count",
        ):
            _strict_non_negative_int(getattr(self, name), name)
        if not any(
            (
                self.operation_count,
                self.payload_bytes,
                self.estimated_token_count,
                self.invocation_count,
            )
        ):
            raise ValueError(
                "architecture reduction step cost requires at least one measured dimension"
            )
        if not isinstance(self.current, bool):
            raise ValueError("current must be a boolean")

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "measurement_id": self.measurement_id,
            "subject_revision": self.subject_revision,
            "source_ref": self.source_ref,
            "measurement_mode": self.measurement_mode,
            "operation_count": self.operation_count,
            "payload_bytes": self.payload_bytes,
            "estimated_token_count": self.estimated_token_count,
            "invocation_count": self.invocation_count,
            "current": self.current,
            "rationale": self.rationale,
        }

    @property
    def fingerprint(self) -> str:
        return _fingerprint_payload(self.identity_payload())

    @property
    def priority_key(self) -> tuple[int, int, int, int]:
        """Stable prioritization only; this tuple is never proof authority."""

        return (
            self.operation_count * max(1, self.invocation_count),
            self.payload_bytes,
            self.estimated_token_count,
            self.invocation_count,
        )

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: Any) -> "ArchitectureReductionStepCost":
        fields = {
            "schema_version",
            "measurement_id",
            "subject_revision",
            "source_ref",
            "measurement_mode",
            "operation_count",
            "payload_bytes",
            "estimated_token_count",
            "invocation_count",
            "current",
            "rationale",
            "fingerprint",
        }
        data = _strict_current_mapping(
            value,
            fields=fields,
            label="architecture reduction step cost",
        )
        for name in (
            "schema_version",
            "measurement_id",
            "subject_revision",
            "source_ref",
            "measurement_mode",
            "rationale",
            "fingerprint",
        ):
            _strict_string(data[name], name)
        for name in (
            "operation_count",
            "payload_bytes",
            "estimated_token_count",
            "invocation_count",
        ):
            _strict_non_negative_int(data[name], name)
        if not isinstance(data["current"], bool):
            raise ValueError("current must be a boolean")
        result = cls(
            measurement_id=data["measurement_id"],
            subject_revision=data["subject_revision"],
            source_ref=data["source_ref"],
            measurement_mode=data["measurement_mode"],
            operation_count=data["operation_count"],
            payload_bytes=data["payload_bytes"],
            estimated_token_count=data["estimated_token_count"],
            invocation_count=data["invocation_count"],
            current=data["current"],
            rationale=data["rationale"],
            schema_version=data["schema_version"],
        )
        if result.schema_version != ARCHITECTURE_REDUCTION_STEP_COST_SCHEMA:
            raise ValueError("architecture reduction step cost uses a non-current schema")
        if result.fingerprint != data["fingerprint"]:
            raise ValueError("architecture reduction step cost fingerprint is stale")
        return result


@dataclass(frozen=True)
class ArchitectureReductionStepAssessment:
    """One retained-route internal-step necessity and contraction decision."""

    assessment_id: str
    parent_route_id: str
    step_id: str
    step_kind: str
    action: str
    proof_status: str
    rationale: str
    candidate_id: str = ""
    current_owner_ids: tuple[str, ...] = ()
    necessity_evidence_refs: tuple[str, ...] = ()
    equivalence_evidence_refs: tuple[str, ...] = ()
    caller_ids: tuple[str, ...] = ()
    caller_inventory_complete: bool = False
    replacement_step_ids: tuple[str, ...] = ()
    on_demand_trigger_ids: tuple[str, ...] = ()
    cost_evidence: tuple[ArchitectureReductionStepCost, ...] = ()
    safety_inventory_complete: bool = False
    safety_responsibility_ids: tuple[str, ...] = ()
    safety_owner_bindings: Mapping[str, str] = field(default_factory=dict)
    safety_evidence_refs: tuple[str, ...] = ()
    unresolved_gap_ids: tuple[str, ...] = ()
    schema_version: str = ARCHITECTURE_REDUCTION_STEP_ASSESSMENT_SCHEMA

    def __post_init__(self) -> None:
        for name in (
            "assessment_id",
            "parent_route_id",
            "step_id",
            "step_kind",
            "action",
            "proof_status",
            "rationale",
            "candidate_id",
            "schema_version",
        ):
            object.__setattr__(self, name, str(getattr(self, name)))
        if self.schema_version != ARCHITECTURE_REDUCTION_STEP_ASSESSMENT_SCHEMA:
            raise ValueError(
                "architecture reduction step assessment requires the current schema"
            )
        for name in (
            "current_owner_ids",
            "necessity_evidence_refs",
            "equivalence_evidence_refs",
            "caller_ids",
            "replacement_step_ids",
            "on_demand_trigger_ids",
            "safety_responsibility_ids",
            "safety_evidence_refs",
            "unresolved_gap_ids",
        ):
            object.__setattr__(
                self,
                name,
                tuple(sorted({value for value in _as_tuple(getattr(self, name)) if value})),
            )
        object.__setattr__(self, "cost_evidence", tuple(self.cost_evidence))
        if any(
            not isinstance(item, ArchitectureReductionStepCost)
            for item in self.cost_evidence
        ):
            raise ValueError(
                "cost_evidence must contain current ArchitectureReductionStepCost rows"
            )
        object.__setattr__(
            self,
            "safety_owner_bindings",
            {
                str(key): str(value)
                for key, value in dict(self.safety_owner_bindings).items()
            },
        )
        if not isinstance(self.caller_inventory_complete, bool):
            raise ValueError("caller_inventory_complete must be a boolean")
        if not isinstance(self.safety_inventory_complete, bool):
            raise ValueError("safety_inventory_complete must be a boolean")

    @property
    def is_contraction_action(self) -> bool:
        return self.action in _STEP_CONTRACTION_ACTIONS

    @property
    def cost_priority_key(self) -> tuple[int, int, int, int]:
        return tuple(
            sum(values)
            for values in zip(
                *(row.priority_key for row in self.cost_evidence),
                strict=False,
            )
        ) if self.cost_evidence else (0, 0, 0, 0)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "assessment_id": self.assessment_id,
            "parent_route_id": self.parent_route_id,
            "step_id": self.step_id,
            "step_kind": self.step_kind,
            "action": self.action,
            "proof_status": self.proof_status,
            "rationale": self.rationale,
            "candidate_id": self.candidate_id,
            "current_owner_ids": list(self.current_owner_ids),
            "necessity_evidence_refs": list(self.necessity_evidence_refs),
            "equivalence_evidence_refs": list(self.equivalence_evidence_refs),
            "caller_ids": list(self.caller_ids),
            "caller_inventory_complete": self.caller_inventory_complete,
            "replacement_step_ids": list(self.replacement_step_ids),
            "on_demand_trigger_ids": list(self.on_demand_trigger_ids),
            "cost_evidence": [row.to_dict() for row in self.cost_evidence],
            "safety_inventory_complete": self.safety_inventory_complete,
            "safety_responsibility_ids": list(self.safety_responsibility_ids),
            "safety_owner_bindings": dict(self.safety_owner_bindings),
            "safety_evidence_refs": list(self.safety_evidence_refs),
            "unresolved_gap_ids": list(self.unresolved_gap_ids),
        }

    @property
    def fingerprint(self) -> str:
        return _fingerprint_payload(self.identity_payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: Any) -> "ArchitectureReductionStepAssessment":
        fields = {
            "schema_version",
            "assessment_id",
            "parent_route_id",
            "step_id",
            "step_kind",
            "action",
            "proof_status",
            "rationale",
            "candidate_id",
            "current_owner_ids",
            "necessity_evidence_refs",
            "equivalence_evidence_refs",
            "caller_ids",
            "caller_inventory_complete",
            "replacement_step_ids",
            "on_demand_trigger_ids",
            "cost_evidence",
            "safety_inventory_complete",
            "safety_responsibility_ids",
            "safety_owner_bindings",
            "safety_evidence_refs",
            "unresolved_gap_ids",
            "fingerprint",
        }
        data = _strict_current_mapping(
            value,
            fields=fields,
            label="architecture reduction step assessment",
        )
        for name in (
            "schema_version",
            "assessment_id",
            "parent_route_id",
            "step_id",
            "step_kind",
            "action",
            "proof_status",
            "rationale",
            "candidate_id",
            "fingerprint",
        ):
            _strict_string(data[name], name)
        for name in ("caller_inventory_complete", "safety_inventory_complete"):
            if not isinstance(data[name], bool):
                raise ValueError(f"{name} must be a boolean")
        if not isinstance(data["cost_evidence"], list):
            raise ValueError("cost_evidence must be an array")
        tuple_fields = {
            name: _strict_string_tuple(data[name], name)
            for name in (
                "current_owner_ids",
                "necessity_evidence_refs",
                "equivalence_evidence_refs",
                "caller_ids",
                "replacement_step_ids",
                "on_demand_trigger_ids",
                "safety_responsibility_ids",
                "safety_evidence_refs",
                "unresolved_gap_ids",
            )
        }
        result = cls(
            assessment_id=data["assessment_id"],
            parent_route_id=data["parent_route_id"],
            step_id=data["step_id"],
            step_kind=data["step_kind"],
            action=data["action"],
            proof_status=data["proof_status"],
            rationale=data["rationale"],
            candidate_id=data["candidate_id"],
            caller_inventory_complete=data["caller_inventory_complete"],
            cost_evidence=tuple(
                ArchitectureReductionStepCost.from_dict(item)
                for item in data["cost_evidence"]
            ),
            safety_inventory_complete=data["safety_inventory_complete"],
            safety_owner_bindings=_strict_string_map(
                data["safety_owner_bindings"],
                "safety_owner_bindings",
            ),
            schema_version=data["schema_version"],
            **tuple_fields,
        )
        if result.schema_version != ARCHITECTURE_REDUCTION_STEP_ASSESSMENT_SCHEMA:
            raise ValueError(
                "architecture reduction step assessment uses a non-current schema"
            )
        if result.fingerprint != data["fingerprint"]:
            raise ValueError("architecture reduction step assessment fingerprint is stale")
        return result


@dataclass(frozen=True)
class RetirementResponsibilityDisposition:
    """Current disposition for one responsibility carried by retired behavior."""

    responsibility_kind: str
    responsibility_id: str
    disposition: str
    rationale: str
    evidence_refs: tuple[str, ...] = ()
    replacement_owner_id: str = ""
    replacement_owner_status: str = RETIREMENT_OWNER_STATUS_NOT_APPLICABLE
    oracle_id: str = ""
    protection_required: bool = False
    current_reference_remaining: bool = False
    retained_runtime_authority: bool = False
    schema: str = ARCHITECTURE_RETIREMENT_RESPONSIBILITY_DISPOSITION_SCHEMA

    def __post_init__(self) -> None:
        for name in (
            "responsibility_kind",
            "responsibility_id",
            "disposition",
            "rationale",
            "replacement_owner_id",
            "replacement_owner_status",
            "oracle_id",
            "schema",
        ):
            object.__setattr__(self, name, str(getattr(self, name)))
        object.__setattr__(self, "evidence_refs", _as_tuple(self.evidence_refs))
        object.__setattr__(self, "protection_required", bool(self.protection_required))
        object.__setattr__(
            self,
            "current_reference_remaining",
            bool(self.current_reference_remaining),
        )
        object.__setattr__(
            self,
            "retained_runtime_authority",
            bool(self.retained_runtime_authority),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "responsibility_kind": self.responsibility_kind,
            "responsibility_id": self.responsibility_id,
            "disposition": self.disposition,
            "rationale": self.rationale,
            "evidence_refs": list(self.evidence_refs),
            "replacement_owner_id": self.replacement_owner_id,
            "replacement_owner_status": self.replacement_owner_status,
            "oracle_id": self.oracle_id,
            "protection_required": self.protection_required,
            "current_reference_remaining": self.current_reference_remaining,
            "retained_runtime_authority": self.retained_runtime_authority,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "RetirementResponsibilityDisposition":
        fields = {
            "schema",
            "responsibility_kind",
            "responsibility_id",
            "disposition",
            "rationale",
            "evidence_refs",
            "replacement_owner_id",
            "replacement_owner_status",
            "oracle_id",
            "protection_required",
            "current_reference_remaining",
            "retained_runtime_authority",
        }
        data = _strict_current_mapping(
            value,
            fields=fields,
            label="retirement responsibility disposition",
        )
        for name in (
            "schema",
            "responsibility_kind",
            "responsibility_id",
            "disposition",
            "rationale",
            "replacement_owner_id",
            "replacement_owner_status",
            "oracle_id",
        ):
            _strict_string(data[name], name)
        for name in (
            "protection_required",
            "current_reference_remaining",
            "retained_runtime_authority",
        ):
            if not isinstance(data[name], bool):
                raise ValueError(f"{name} must be a boolean")
        result = cls(
            responsibility_kind=data["responsibility_kind"],
            responsibility_id=data["responsibility_id"],
            disposition=data["disposition"],
            rationale=data["rationale"],
            evidence_refs=_strict_string_tuple(
                data["evidence_refs"],
                "evidence_refs",
            ),
            replacement_owner_id=data["replacement_owner_id"],
            replacement_owner_status=data["replacement_owner_status"],
            oracle_id=data["oracle_id"],
            protection_required=data["protection_required"],
            current_reference_remaining=data["current_reference_remaining"],
            retained_runtime_authority=data["retained_runtime_authority"],
            schema=data["schema"],
        )
        if result.schema != ARCHITECTURE_RETIREMENT_RESPONSIBILITY_DISPOSITION_SCHEMA:
            raise ValueError(
                "retirement responsibility disposition uses a non-current schema"
            )
        return result


@dataclass(frozen=True)
class ArchitectureRetirementProof:
    """Complete current responsibility inventory for intentional retirement."""

    retirement_id: str
    current_goal_rationale: str
    inventory_revision: str
    inventory_current: bool
    owner_resolution_status: str
    retired_commitment_ids: tuple[str, ...]
    retired_behavior_ids: tuple[str, ...]
    code_binding_ids: tuple[str, ...] = ()
    test_binding_ids: tuple[str, ...] = ()
    model_binding_ids: tuple[str, ...] = ()
    public_surface_ids: tuple[str, ...] = ()
    consumer_ids: tuple[str, ...] = ()
    negative_case_ids: tuple[str, ...] = ()
    route_ids: tuple[str, ...] = ()
    skill_ids: tuple[str, ...] = ()
    prompt_ids: tuple[str, ...] = ()
    topology_relation_ids: tuple[str, ...] = ()
    release_claim_ids: tuple[str, ...] = ()
    responsibility_dispositions: tuple[RetirementResponsibilityDisposition, ...] = ()
    not_applicable_responsibility_kinds: Mapping[str, str] = field(
        default_factory=dict
    )
    replacement_owner_ids: tuple[str, ...] = ()
    required_validation_routes: tuple[str, ...] = ()
    governed_identity_fingerprints: Mapping[str, str] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    schema: str = ARCHITECTURE_RETIREMENT_PROOF_SCHEMA

    def __post_init__(self) -> None:
        for name in (
            "retirement_id",
            "current_goal_rationale",
            "inventory_revision",
            "owner_resolution_status",
            "schema",
        ):
            object.__setattr__(self, name, str(getattr(self, name)))
        object.__setattr__(self, "inventory_current", bool(self.inventory_current))
        for name in (
            "retired_commitment_ids",
            "retired_behavior_ids",
            "code_binding_ids",
            "test_binding_ids",
            "model_binding_ids",
            "public_surface_ids",
            "consumer_ids",
            "negative_case_ids",
            "route_ids",
            "skill_ids",
            "prompt_ids",
            "topology_relation_ids",
            "release_claim_ids",
            "replacement_owner_ids",
            "required_validation_routes",
            "evidence_refs",
        ):
            object.__setattr__(self, name, _as_tuple(getattr(self, name)))
        object.__setattr__(
            self,
            "responsibility_dispositions",
            tuple(self.responsibility_dispositions),
        )
        if any(
            not isinstance(item, RetirementResponsibilityDisposition)
            for item in self.responsibility_dispositions
        ):
            raise ValueError(
                "responsibility_dispositions must contain only current typed dispositions"
            )
        object.__setattr__(
            self,
            "not_applicable_responsibility_kinds",
            {
                str(key): str(value)
                for key, value in dict(
                    self.not_applicable_responsibility_kinds
                ).items()
            },
        )
        object.__setattr__(
            self,
            "governed_identity_fingerprints",
            {
                str(key): str(value)
                for key, value in dict(self.governed_identity_fingerprints).items()
            },
        )

    def governed_responsibility_ids(self) -> dict[str, tuple[str, ...]]:
        return {
            RETIREMENT_RESPONSIBILITY_COMMITMENT: self.retired_commitment_ids,
            RETIREMENT_RESPONSIBILITY_BEHAVIOR: self.retired_behavior_ids,
            RETIREMENT_RESPONSIBILITY_CODE: self.code_binding_ids,
            RETIREMENT_RESPONSIBILITY_TEST: self.test_binding_ids,
            RETIREMENT_RESPONSIBILITY_MODEL: self.model_binding_ids,
            RETIREMENT_RESPONSIBILITY_PUBLIC_SURFACE: self.public_surface_ids,
            RETIREMENT_RESPONSIBILITY_CONSUMER: self.consumer_ids,
            RETIREMENT_RESPONSIBILITY_NEGATIVE_CASE: self.negative_case_ids,
            RETIREMENT_RESPONSIBILITY_ROUTE: self.route_ids,
            RETIREMENT_RESPONSIBILITY_SKILL: self.skill_ids,
            RETIREMENT_RESPONSIBILITY_PROMPT: self.prompt_ids,
            RETIREMENT_RESPONSIBILITY_TOPOLOGY_RELATION: self.topology_relation_ids,
            RETIREMENT_RESPONSIBILITY_RELEASE_CLAIM: self.release_claim_ids,
        }

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "retirement_id": self.retirement_id,
            "current_goal_rationale": self.current_goal_rationale,
            "inventory_revision": self.inventory_revision,
            "inventory_current": self.inventory_current,
            "owner_resolution_status": self.owner_resolution_status,
            "retired_commitment_ids": list(self.retired_commitment_ids),
            "retired_behavior_ids": list(self.retired_behavior_ids),
            "code_binding_ids": list(self.code_binding_ids),
            "test_binding_ids": list(self.test_binding_ids),
            "model_binding_ids": list(self.model_binding_ids),
            "public_surface_ids": list(self.public_surface_ids),
            "consumer_ids": list(self.consumer_ids),
            "negative_case_ids": list(self.negative_case_ids),
            "route_ids": list(self.route_ids),
            "skill_ids": list(self.skill_ids),
            "prompt_ids": list(self.prompt_ids),
            "topology_relation_ids": list(self.topology_relation_ids),
            "release_claim_ids": list(self.release_claim_ids),
            "responsibility_dispositions": [
                item.to_dict() for item in self.responsibility_dispositions
            ],
            "not_applicable_responsibility_kinds": dict(
                self.not_applicable_responsibility_kinds
            ),
            "replacement_owner_ids": list(self.replacement_owner_ids),
            "required_validation_routes": list(self.required_validation_routes),
            "governed_identity_fingerprints": dict(
                self.governed_identity_fingerprints
            ),
            "evidence_refs": list(self.evidence_refs),
        }

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(
            self.identity_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(encoded).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: Any) -> "ArchitectureRetirementProof":
        fields = {
            "schema",
            "retirement_id",
            "current_goal_rationale",
            "inventory_revision",
            "inventory_current",
            "owner_resolution_status",
            "retired_commitment_ids",
            "retired_behavior_ids",
            "code_binding_ids",
            "test_binding_ids",
            "model_binding_ids",
            "public_surface_ids",
            "consumer_ids",
            "negative_case_ids",
            "route_ids",
            "skill_ids",
            "prompt_ids",
            "topology_relation_ids",
            "release_claim_ids",
            "responsibility_dispositions",
            "not_applicable_responsibility_kinds",
            "replacement_owner_ids",
            "required_validation_routes",
            "governed_identity_fingerprints",
            "evidence_refs",
            "fingerprint",
        }
        data = _strict_current_mapping(
            value,
            fields=fields,
            label="architecture retirement proof",
        )
        for name in (
            "schema",
            "retirement_id",
            "current_goal_rationale",
            "inventory_revision",
            "owner_resolution_status",
            "fingerprint",
        ):
            _strict_string(data[name], name)
        if not isinstance(data["inventory_current"], bool):
            raise ValueError("inventory_current must be a boolean")
        tuple_fields = {
            name: _strict_string_tuple(data[name], name)
            for name in (
                "retired_commitment_ids",
                "retired_behavior_ids",
                "code_binding_ids",
                "test_binding_ids",
                "model_binding_ids",
                "public_surface_ids",
                "consumer_ids",
                "negative_case_ids",
                "route_ids",
                "skill_ids",
                "prompt_ids",
                "topology_relation_ids",
                "release_claim_ids",
                "replacement_owner_ids",
                "required_validation_routes",
                "evidence_refs",
            )
        }
        if not isinstance(data["responsibility_dispositions"], list):
            raise ValueError("responsibility_dispositions must be an array")
        result = cls(
            retirement_id=data["retirement_id"],
            current_goal_rationale=data["current_goal_rationale"],
            inventory_revision=data["inventory_revision"],
            inventory_current=data["inventory_current"],
            owner_resolution_status=data["owner_resolution_status"],
            responsibility_dispositions=tuple(
                RetirementResponsibilityDisposition.from_dict(item)
                for item in data["responsibility_dispositions"]
            ),
            not_applicable_responsibility_kinds=_strict_string_map(
                data["not_applicable_responsibility_kinds"],
                "not_applicable_responsibility_kinds",
            ),
            governed_identity_fingerprints=_strict_string_map(
                data["governed_identity_fingerprints"],
                "governed_identity_fingerprints",
            ),
            schema=data["schema"],
            **tuple_fields,
        )
        if result.schema != ARCHITECTURE_RETIREMENT_PROOF_SCHEMA:
            raise ValueError("architecture retirement proof uses a non-current schema")
        if result.fingerprint != data["fingerprint"]:
            raise ValueError("architecture retirement proof fingerprint is stale")
        return result


@dataclass(frozen=True)
class ObservableArchitectureContract:
    """Public behavior boundary that code contraction must preserve."""

    source_model_id: str
    source_code_boundary_id: str
    public_entrypoints: tuple[str, ...] = ()
    observable_outputs: tuple[str, ...] = ()
    observable_state: tuple[str, ...] = ()
    observable_side_effects: tuple[str, ...] = ()
    validation_boundaries: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_model_id", str(self.source_model_id))
        object.__setattr__(self, "source_code_boundary_id", str(self.source_code_boundary_id))
        object.__setattr__(self, "public_entrypoints", _as_tuple(self.public_entrypoints))
        object.__setattr__(self, "observable_outputs", _as_tuple(self.observable_outputs))
        object.__setattr__(self, "observable_state", _as_tuple(self.observable_state))
        object.__setattr__(self, "observable_side_effects", _as_tuple(self.observable_side_effects))
        object.__setattr__(self, "validation_boundaries", _as_tuple(self.validation_boundaries))
        object.__setattr__(self, "rationale", str(self.rationale))

    def missing_fields(self) -> tuple[str, ...]:
        missing: list[str] = []
        if not self.source_model_id:
            missing.append("source_model_id")
        if not self.source_code_boundary_id:
            missing.append("source_code_boundary_id")
        if not self.public_entrypoints:
            missing.append("public_entrypoints")
        if not self.observable_outputs:
            missing.append("observable_outputs")
        if not self.validation_boundaries:
            missing.append("validation_boundaries")
        if not self.rationale:
            missing.append("rationale")
        return tuple(missing)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_model_id": self.source_model_id,
            "source_code_boundary_id": self.source_code_boundary_id,
            "public_entrypoints": list(self.public_entrypoints),
            "observable_outputs": list(self.observable_outputs),
            "observable_state": list(self.observable_state),
            "observable_side_effects": list(self.observable_side_effects),
            "validation_boundaries": list(self.validation_boundaries),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class CompatibilitySurfaceClassification:
    """Pre-reduction classification for old or alternate compatibility surfaces."""

    surface_id: str
    classification: str
    recommended_action: str
    rationale: str
    code_node_ids: tuple[str, ...] = ()
    public_entrypoints: tuple[str, ...] = ()
    field_ids: tuple[str, ...] = ()
    replacement_field_ids: tuple[str, ...] = ()
    runtime_authority: bool = False
    owner_model_elements: tuple[str, ...] = ()
    candidate_ids: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "surface_id", str(self.surface_id))
        object.__setattr__(self, "classification", str(self.classification))
        object.__setattr__(self, "recommended_action", str(self.recommended_action))
        object.__setattr__(self, "rationale", str(self.rationale))
        object.__setattr__(self, "code_node_ids", _as_tuple(self.code_node_ids))
        object.__setattr__(self, "public_entrypoints", _as_tuple(self.public_entrypoints))
        object.__setattr__(self, "field_ids", _as_tuple(self.field_ids))
        object.__setattr__(self, "replacement_field_ids", _as_tuple(self.replacement_field_ids))
        object.__setattr__(self, "runtime_authority", bool(self.runtime_authority))
        object.__setattr__(self, "owner_model_elements", _as_tuple(self.owner_model_elements))
        object.__setattr__(self, "candidate_ids", _as_tuple(self.candidate_ids))
        object.__setattr__(self, "evidence_refs", _as_tuple(self.evidence_refs))
        object.__setattr__(self, "missing_evidence", _as_tuple(self.missing_evidence))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def missing_fields(self) -> tuple[str, ...]:
        missing: list[str] = []
        if not self.surface_id:
            missing.append("surface_id")
        if not self.classification:
            missing.append("classification")
        if not self.recommended_action:
            missing.append("recommended_action")
        if not self.rationale:
            missing.append("rationale")
        return tuple(missing)

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface_id": self.surface_id,
            "classification": self.classification,
            "recommended_action": self.recommended_action,
            "rationale": self.rationale,
            "code_node_ids": list(self.code_node_ids),
            "public_entrypoints": list(self.public_entrypoints),
            "field_ids": list(self.field_ids),
            "replacement_field_ids": list(self.replacement_field_ids),
            "runtime_authority": self.runtime_authority,
            "owner_model_elements": list(self.owner_model_elements),
            "candidate_ids": list(self.candidate_ids),
            "evidence_refs": list(self.evidence_refs),
            "missing_evidence": list(self.missing_evidence),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ArchitectureReductionCandidate:
    """One model-backed code contraction candidate."""

    candidate_id: str
    candidate_type: str
    code_node_id: str
    source_model_element: str
    target_action: str
    proof_status: str
    required_next_route: str
    rationale: str
    affected_public_entrypoints: tuple[str, ...] = ()
    affected_state: tuple[str, ...] = ()
    affected_side_effects: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    canonical_relation_handoff: CanonicalRelationHandoff | Mapping[str, Any] | None = None
    lifecycle_disposition: str = CANDIDATE_DISPOSITION_ACTIVE
    completion_evidence_refs: tuple[str, ...] = ()
    business_intent_id: str = ""
    behavior_commitment_id: str = ""
    primary_path_id: str = ""
    inventory_revision: str = ""
    materialized_relation_ids: tuple[str, ...] = ()
    materialized_relation_code_obligation_ids: tuple[str, ...] = ()
    owner_code_contract_id: str = ""
    delegates_to_code_contract_id: str = ""
    delegates_to_primary_path_id: str = ""
    delegation_evidence_id: str = ""
    delegation_evidence_current: bool = False
    delegation_only: bool = False
    independent_business_authority: bool = False
    retirement_proof: ArchitectureRetirementProof | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", str(self.candidate_id))
        object.__setattr__(self, "candidate_type", str(self.candidate_type))
        object.__setattr__(self, "code_node_id", str(self.code_node_id))
        object.__setattr__(self, "source_model_element", str(self.source_model_element))
        object.__setattr__(self, "target_action", str(self.target_action))
        object.__setattr__(self, "proof_status", str(self.proof_status))
        object.__setattr__(self, "required_next_route", str(self.required_next_route))
        object.__setattr__(self, "rationale", str(self.rationale))
        object.__setattr__(self, "affected_public_entrypoints", _as_tuple(self.affected_public_entrypoints))
        object.__setattr__(self, "affected_state", _as_tuple(self.affected_state))
        object.__setattr__(self, "affected_side_effects", _as_tuple(self.affected_side_effects))
        object.__setattr__(self, "evidence_refs", _as_tuple(self.evidence_refs))
        object.__setattr__(
            self,
            "canonical_relation_handoff",
            normalize_canonical_relation_handoff(self.canonical_relation_handoff),
        )
        object.__setattr__(self, "lifecycle_disposition", str(self.lifecycle_disposition))
        object.__setattr__(self, "completion_evidence_refs", _as_tuple(self.completion_evidence_refs))
        object.__setattr__(self, "business_intent_id", str(self.business_intent_id))
        object.__setattr__(self, "behavior_commitment_id", str(self.behavior_commitment_id))
        object.__setattr__(self, "primary_path_id", str(self.primary_path_id))
        object.__setattr__(self, "inventory_revision", str(self.inventory_revision))
        object.__setattr__(
            self,
            "materialized_relation_ids",
            _as_tuple(self.materialized_relation_ids),
        )
        object.__setattr__(
            self,
            "materialized_relation_code_obligation_ids",
            _as_tuple(self.materialized_relation_code_obligation_ids),
        )
        object.__setattr__(self, "owner_code_contract_id", str(self.owner_code_contract_id))
        object.__setattr__(self, "delegates_to_code_contract_id", str(self.delegates_to_code_contract_id))
        object.__setattr__(self, "delegates_to_primary_path_id", str(self.delegates_to_primary_path_id))
        object.__setattr__(self, "delegation_evidence_id", str(self.delegation_evidence_id))
        object.__setattr__(self, "delegation_evidence_current", bool(self.delegation_evidence_current))
        object.__setattr__(self, "delegation_only", bool(self.delegation_only))
        object.__setattr__(self, "independent_business_authority", bool(self.independent_business_authority))
        if self.retirement_proof is not None and not isinstance(
            self.retirement_proof,
            ArchitectureRetirementProof,
        ):
            raise ValueError(
                "retirement_proof must be one current ArchitectureRetirementProof"
            )
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def is_ready(self) -> bool:
        if self.lifecycle_disposition != CANDIDATE_DISPOSITION_ACTIVE:
            return False
        if self.target_action == TARGET_ACTION_RETIRE_BEHAVIOR:
            return self.proof_status == PROOF_AUTHORIZED_RETIREMENT
        return self.proof_status in READY_PROOF_STATUSES

    @property
    def is_closed(self) -> bool:
        return self.lifecycle_disposition in {
            CANDIDATE_DISPOSITION_COMPLETED,
            CANDIDATE_DISPOSITION_HISTORICAL,
        }

    def touches_public_entrypoint(self) -> bool:
        return bool(self.affected_public_entrypoints)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_type": self.candidate_type,
            "code_node_id": self.code_node_id,
            "source_model_element": self.source_model_element,
            "target_action": self.target_action,
            "proof_status": self.proof_status,
            "required_next_route": self.required_next_route,
            "rationale": self.rationale,
            "affected_public_entrypoints": list(self.affected_public_entrypoints),
            "affected_state": list(self.affected_state),
            "affected_side_effects": list(self.affected_side_effects),
            "evidence_refs": list(self.evidence_refs),
            "canonical_relation_handoff": self.canonical_relation_handoff.to_dict()
            if self.canonical_relation_handoff
            else None,
            "lifecycle_disposition": self.lifecycle_disposition,
            "completion_evidence_refs": list(self.completion_evidence_refs),
            "business_intent_id": self.business_intent_id,
            "behavior_commitment_id": self.behavior_commitment_id,
            "primary_path_id": self.primary_path_id,
            "inventory_revision": self.inventory_revision,
            "materialized_relation_ids": list(self.materialized_relation_ids),
            "materialized_relation_code_obligation_ids": list(self.materialized_relation_code_obligation_ids),
            "owner_code_contract_id": self.owner_code_contract_id,
            "delegates_to_code_contract_id": self.delegates_to_code_contract_id,
            "delegates_to_primary_path_id": self.delegates_to_primary_path_id,
            "delegation_evidence_id": self.delegation_evidence_id,
            "delegation_evidence_current": self.delegation_evidence_current,
            "delegation_only": self.delegation_only,
            "independent_business_authority": self.independent_business_authority,
            "retirement_proof": (
                self.retirement_proof.to_dict()
                if self.retirement_proof is not None
                else None
            ),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ArchitectureReductionTrigger:
    """Complexity-growth signal from a companion FlowGuard route."""

    route_id: str
    trigger_reason: str
    complexity_signal: str = ""
    recommended_timing: str = ""
    required: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "route_id", str(self.route_id))
        object.__setattr__(self, "trigger_reason", str(self.trigger_reason))
        object.__setattr__(self, "complexity_signal", str(self.complexity_signal))
        object.__setattr__(self, "recommended_timing", str(self.recommended_timing))
        object.__setattr__(self, "required", bool(self.required))

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "trigger_reason": self.trigger_reason,
            "complexity_signal": self.complexity_signal,
            "recommended_timing": self.recommended_timing,
            "required": self.required,
        }


@dataclass(frozen=True)
class TargetArchitectureAction:
    """One target code-structure action derived from a candidate."""

    candidate_id: str
    action: str
    code_node_id: str
    required_next_route: str
    rationale: str = ""
    retirement_proof: ArchitectureRetirementProof | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", str(self.candidate_id))
        object.__setattr__(self, "action", str(self.action))
        object.__setattr__(self, "code_node_id", str(self.code_node_id))
        object.__setattr__(self, "required_next_route", str(self.required_next_route))
        object.__setattr__(self, "rationale", str(self.rationale))
        if self.retirement_proof is not None and not isinstance(
            self.retirement_proof,
            ArchitectureRetirementProof,
        ):
            raise ValueError(
                "target action retirement_proof must use the current typed proof"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "action": self.action,
            "code_node_id": self.code_node_id,
            "required_next_route": self.required_next_route,
            "rationale": self.rationale,
            "retirement_proof": (
                self.retirement_proof.to_dict()
                if self.retirement_proof is not None
                else None
            ),
        }


@dataclass(frozen=True)
class ArchitectureReductionPlan:
    """Review input for model-backed code architecture reduction."""

    reduction_id: str
    observable_contract: ObservableArchitectureContract
    candidates: tuple[ArchitectureReductionCandidate, ...] = ()
    companion_route_triggers: tuple[ArchitectureReductionTrigger, ...] = ()
    target_structure: CodeStructureRecommendation | None = None
    rationale: str = ""
    compatibility_surfaces: tuple[CompatibilitySurfaceClassification, ...] = ()
    inventory_revision: str = ""
    inventory_source_ref: str = ""
    inventory_current: bool = True
    expected_candidate_ids: tuple[str, ...] = ()
    scoped_candidate_reasons: Mapping[str, str] = field(default_factory=dict)
    require_complete_inventory: bool = False
    canonical_relation_handoff: CanonicalRelationHandoff | Mapping[str, Any] | None = None
    scoped_relation_reasons: Mapping[str, str] = field(default_factory=dict)
    step_assessments: tuple[ArchitectureReductionStepAssessment, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "reduction_id", str(self.reduction_id))
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "companion_route_triggers", tuple(self.companion_route_triggers))
        object.__setattr__(self, "compatibility_surfaces", tuple(self.compatibility_surfaces))
        object.__setattr__(self, "rationale", str(self.rationale))
        object.__setattr__(self, "inventory_revision", str(self.inventory_revision))
        object.__setattr__(self, "inventory_source_ref", str(self.inventory_source_ref))
        object.__setattr__(self, "inventory_current", bool(self.inventory_current))
        object.__setattr__(self, "expected_candidate_ids", _as_tuple(self.expected_candidate_ids))
        object.__setattr__(
            self,
            "scoped_candidate_reasons",
            {str(key): str(value) for key, value in dict(self.scoped_candidate_reasons).items()},
        )
        object.__setattr__(self, "require_complete_inventory", bool(self.require_complete_inventory))
        object.__setattr__(
            self,
            "canonical_relation_handoff",
            normalize_canonical_relation_handoff(self.canonical_relation_handoff),
        )
        object.__setattr__(
            self,
            "scoped_relation_reasons",
            {str(key): str(value) for key, value in dict(self.scoped_relation_reasons).items()},
        )
        object.__setattr__(self, "step_assessments", tuple(self.step_assessments))
        if any(
            not isinstance(row, ArchitectureReductionStepAssessment)
            for row in self.step_assessments
        ):
            raise ValueError(
                "step_assessments must contain current ArchitectureReductionStepAssessment rows"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "reduction_id": self.reduction_id,
            "observable_contract": self.observable_contract.to_dict(),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "companion_route_triggers": [trigger.to_dict() for trigger in self.companion_route_triggers],
            "compatibility_surfaces": [surface.to_dict() for surface in self.compatibility_surfaces],
            "target_structure": self.target_structure.to_dict() if self.target_structure else None,
            "rationale": self.rationale,
            "inventory_revision": self.inventory_revision,
            "inventory_source_ref": self.inventory_source_ref,
            "inventory_current": self.inventory_current,
            "expected_candidate_ids": list(self.expected_candidate_ids),
            "scoped_candidate_reasons": to_jsonable(dict(self.scoped_candidate_reasons)),
            "require_complete_inventory": self.require_complete_inventory,
            "canonical_relation_handoff": self.canonical_relation_handoff.to_dict() if self.canonical_relation_handoff else None,
            "scoped_relation_reasons": to_jsonable(dict(self.scoped_relation_reasons)),
            "step_assessments": [row.to_dict() for row in self.step_assessments],
        }


@dataclass(frozen=True)
class ArchitectureReductionFinding:
    """One architecture reduction finding."""

    code: str
    message: str
    severity: str = "blocker"
    candidate_id: str = ""
    item_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "candidate_id", str(self.candidate_id))
        object.__setattr__(self, "item_id", str(self.item_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "candidate_id": self.candidate_id,
            "item_id": self.item_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ArchitectureReductionReport:
    """Structured architecture reduction review result."""

    ok: bool
    reduction_id: str
    decision: str
    findings: tuple[ArchitectureReductionFinding, ...] = ()
    ready_candidate_ids: tuple[str, ...] = ()
    completed_candidate_ids: tuple[str, ...] = ()
    target_actions: tuple[TargetArchitectureAction, ...] = ()
    required_next_routes: tuple[str, ...] = ()
    summary: str = ""
    compatibility_surfaces: tuple[CompatibilitySurfaceClassification, ...] = ()
    inventory_revision: str = ""
    covered_candidate_ids: tuple[str, ...] = ()
    scoped_candidate_ids: tuple[str, ...] = ()
    missing_candidate_ids: tuple[str, ...] = ()
    unexpected_candidate_ids: tuple[str, ...] = ()
    materialized_relation_ids: tuple[str, ...] = ()
    materialized_relation_code_obligation_ids: tuple[str, ...] = ()
    step_assessments: tuple[ArchitectureReductionStepAssessment, ...] = ()
    cost_priority_step_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "reduction_id", str(self.reduction_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "ready_candidate_ids", _as_tuple(self.ready_candidate_ids))
        object.__setattr__(self, "completed_candidate_ids", _as_tuple(self.completed_candidate_ids))
        object.__setattr__(self, "target_actions", tuple(self.target_actions))
        object.__setattr__(self, "required_next_routes", _as_tuple(self.required_next_routes))
        object.__setattr__(self, "compatibility_surfaces", tuple(self.compatibility_surfaces))
        object.__setattr__(self, "inventory_revision", str(self.inventory_revision))
        object.__setattr__(self, "covered_candidate_ids", _as_tuple(self.covered_candidate_ids))
        object.__setattr__(self, "scoped_candidate_ids", _as_tuple(self.scoped_candidate_ids))
        object.__setattr__(self, "missing_candidate_ids", _as_tuple(self.missing_candidate_ids))
        object.__setattr__(self, "unexpected_candidate_ids", _as_tuple(self.unexpected_candidate_ids))
        object.__setattr__(
            self,
            "materialized_relation_ids",
            _as_tuple(self.materialized_relation_ids),
        )
        object.__setattr__(
            self,
            "materialized_relation_code_obligation_ids",
            _as_tuple(self.materialized_relation_code_obligation_ids),
        )
        object.__setattr__(self, "step_assessments", tuple(self.step_assessments))
        object.__setattr__(
            self,
            "cost_priority_step_ids",
            _as_tuple(self.cost_priority_step_ids),
        )
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: reduction={self.reduction_id} decision={self.decision} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard architecture reduction review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"reduction: {self.reduction_id}",
            f"decision: {self.decision}",
            f"findings: {len(self.findings)}",
        ]
        if self.ready_candidate_ids:
            lines.append(f"ready_candidates: {', '.join(self.ready_candidate_ids)}")
        if self.completed_candidate_ids:
            lines.append(f"completed_candidates: {', '.join(self.completed_candidate_ids)}")
        if self.required_next_routes:
            lines.append(f"required_next_routes: {', '.join(self.required_next_routes)}")
        if self.compatibility_surfaces:
            lines.append("compatibility_surfaces:")
            for surface in self.compatibility_surfaces:
                lines.append(
                    f"  - {surface.surface_id}: {surface.classification} -> {surface.recommended_action}"
                )
        if self.target_actions:
            lines.append("target_actions:")
            for action in self.target_actions:
                lines.append(f"  - {action.action} {action.code_node_id} via {action.required_next_route}")
        if self.step_assessments:
            lines.append("internal_step_assessments:")
            for row in self.step_assessments:
                lines.append(
                    f"  - {row.step_id}: {row.step_kind} -> {row.action}"
                )
        if self.cost_priority_step_ids:
            lines.append(
                "cost_priority_steps: " + ", ".join(self.cost_priority_step_ids)
            )
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"candidate: {finding.candidate_id or '(none)'}",
                    f"item: {finding.item_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reduction_id": self.reduction_id,
            "decision": self.decision,
            "findings": [finding.to_dict() for finding in self.findings],
            "ready_candidate_ids": list(self.ready_candidate_ids),
            "completed_candidate_ids": list(self.completed_candidate_ids),
            "target_actions": [action.to_dict() for action in self.target_actions],
            "required_next_routes": list(self.required_next_routes),
            "compatibility_surfaces": [surface.to_dict() for surface in self.compatibility_surfaces],
            "inventory_revision": self.inventory_revision,
            "covered_candidate_ids": list(self.covered_candidate_ids),
            "scoped_candidate_ids": list(self.scoped_candidate_ids),
            "missing_candidate_ids": list(self.missing_candidate_ids),
            "unexpected_candidate_ids": list(self.unexpected_candidate_ids),
            "materialized_relation_ids": list(self.materialized_relation_ids),
            "materialized_relation_code_obligation_ids": list(self.materialized_relation_code_obligation_ids),
            "step_assessments": [row.to_dict() for row in self.step_assessments],
            "cost_priority_step_ids": list(self.cost_priority_step_ids),
            "summary": self.summary,
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(to_jsonable(self.to_dict()), indent=indent, sort_keys=True)


def _blockers(findings: Sequence[ArchitectureReductionFinding]) -> tuple[ArchitectureReductionFinding, ...]:
    return tuple(finding for finding in findings if finding.severity == "blocker")


def _decision_for_findings(
    findings: Sequence[ArchitectureReductionFinding],
    *,
    candidate_count: int,
    active_count: int,
    completed_count: int,
    ready_count: int,
) -> str:
    blockers = _blockers(findings)
    if blockers:
        priority = [
            ("candidate_inventory_revision_missing", "candidate_inventory_blocked"),
            ("candidate_inventory_provenance_missing", "candidate_inventory_blocked"),
            ("candidate_inventory_stale", "candidate_inventory_blocked"),
            ("expected_candidate_inventory_missing", "candidate_inventory_blocked"),
            ("expected_reduction_candidate_missing", "candidate_inventory_blocked"),
            ("unexpected_reduction_candidate", "candidate_inventory_blocked"),
            ("canonical_relation_candidate_inventory_empty", "candidate_inventory_blocked"),
            ("unmaterialized_reduction_relation", "candidate_inventory_blocked"),
            ("unmaterialized_reduction_code_obligation", "candidate_inventory_blocked"),
            ("facade_delegation_contract_incomplete", "facade_delegation_blocked"),
            ("facade_delegation_target_mismatch", "facade_delegation_blocked"),
            ("facade_delegation_evidence_stale", "facade_delegation_blocked"),
            ("facade_independent_business_authority", "facade_delegation_blocked"),
            ("missing_observable_contract", "missing_observable_contract"),
            ("incomplete_candidate", "candidate_blocked"),
            ("invalid_candidate_type", "candidate_blocked"),
            ("invalid_target_action", "candidate_blocked"),
            ("invalid_proof_status", "candidate_blocked"),
            ("invalid_lifecycle_disposition", "candidate_blocked"),
            ("duplicate_step_assessment", "step_assessment_blocked"),
            ("duplicate_step_action", "step_assessment_blocked"),
            ("incomplete_step_assessment", "step_assessment_blocked"),
            ("invalid_step_kind", "step_assessment_blocked"),
            ("invalid_step_action", "step_assessment_blocked"),
            ("invalid_step_proof_status", "step_assessment_blocked"),
            ("step_candidate_missing", "step_assessment_blocked"),
            ("step_candidate_action_mismatch", "step_assessment_blocked"),
            ("step_candidate_proof_mismatch", "step_assessment_blocked"),
            ("step_cost_evidence_missing", "step_assessment_blocked"),
            ("step_cost_evidence_stale", "step_assessment_blocked"),
            ("step_retain_authority_missing", "step_assessment_blocked"),
            ("step_contraction_equivalence_missing", "step_assessment_blocked"),
            ("step_caller_inventory_incomplete", "step_assessment_blocked"),
            ("step_replacement_missing", "step_assessment_blocked"),
            ("step_on_demand_trigger_missing", "step_assessment_blocked"),
            ("step_safety_inventory_incomplete", "step_assessment_blocked"),
            ("step_safety_owner_incomplete", "step_assessment_blocked"),
            ("step_safety_transfer_evidence_missing", "step_assessment_blocked"),
            ("step_unique_safety_owner_removed", "step_assessment_blocked"),
            ("step_unresolved_gap_missing", "step_assessment_blocked"),
            ("completed_candidate_missing_evidence", "completed_candidate_blocked"),
            ("missing_required_next_route", "candidate_blocked"),
            ("public_entrypoint_requires_structure_mesh", "structure_mesh_required"),
            ("compatibility_surface_current_contract_blocks_contraction", "compatibility_surface_blocked"),
            ("compatibility_surface_public_entrypoint_requires_structure_mesh", "structure_mesh_required"),
            ("compatibility_surface_negative_legacy_test_requires_evidence", "compatibility_surface_blocked"),
            ("compatibility_surface_archive_has_runtime_authority", "compatibility_surface_blocked"),
            ("compatibility_field_surface_missing_evidence", "compatibility_surface_blocked"),
            ("compatibility_surface_evidence_needed", "evidence_blocked"),
            ("invalid_compatibility_surface_classification", "compatibility_surface_blocked"),
            ("invalid_compatibility_surface_action", "compatibility_surface_blocked"),
            ("incomplete_compatibility_surface", "compatibility_surface_blocked"),
            ("removes_observable_state", "observable_contract_blocked"),
            ("observable_side_effect_without_equivalence", "observable_contract_blocked"),
            ("conformance_replay_required", "conformance_required"),
            ("blocked_by_missing_evidence", "evidence_blocked"),
            ("target_structure_blocked", "target_structure_blocked"),
        ]
        codes = {finding.code for finding in blockers}
        for code, decision in priority:
            if code in codes:
                return decision
        if any(
            code.startswith("retirement_")
            or code == "retained_protection_without_current_owner"
            for code in codes
        ):
            return "retirement_proof_blocked"
        return "architecture_reduction_blocked"
    if any(finding.code == "property_only_reduction" for finding in findings):
        return "property_only_review"
    if candidate_count == 0:
        return "no_reduction_candidates"
    if active_count == 0 and completed_count:
        return "completed_reduction_candidates"
    if ready_count == 0:
        return "no_ready_reduction_candidates"
    return "architecture_reduction_ready"


def _candidate_incomplete(candidate: ArchitectureReductionCandidate) -> tuple[str, ...]:
    missing: list[str] = []
    for field_name in (
        "candidate_id",
        "candidate_type",
        "code_node_id",
        "source_model_element",
        "target_action",
        "proof_status",
        "required_next_route",
        "rationale",
    ):
        if not getattr(candidate, field_name):
            missing.append(field_name)
    return tuple(missing)


def _target_action_from_candidate(candidate: ArchitectureReductionCandidate) -> TargetArchitectureAction:
    return TargetArchitectureAction(
        candidate_id=candidate.candidate_id,
        action=candidate.target_action,
        code_node_id=candidate.code_node_id,
        required_next_route=candidate.required_next_route,
        rationale=candidate.rationale,
        retirement_proof=candidate.retirement_proof,
    )


def _step_assessment_findings(
    plan: ArchitectureReductionPlan,
) -> list[ArchitectureReductionFinding]:
    """Validate internal-step decisions without allowing cost to prove safety."""

    findings: list[ArchitectureReductionFinding] = []
    candidate_by_id = {
        candidate.candidate_id: candidate
        for candidate in plan.candidates
        if candidate.candidate_id
    }
    assessment_ids: set[str] = set()
    step_ids: set[str] = set()
    compatible_target_actions = {
        STEP_ACTION_MERGE: {TARGET_ACTION_MERGE},
        STEP_ACTION_DELEGATE: {
            TARGET_ACTION_COLLAPSE,
            TARGET_ACTION_KEEP_FACADE,
        },
        STEP_ACTION_REMOVE: {TARGET_ACTION_REMOVE},
        STEP_ACTION_EXPLICIT_ON_DEMAND: {
            TARGET_ACTION_COLLAPSE,
            TARGET_ACTION_REMOVE,
        },
    }
    for row in plan.step_assessments:
        if row.assessment_id in assessment_ids:
            findings.append(
                ArchitectureReductionFinding(
                    "duplicate_step_assessment",
                    "one step assessment identity occurs more than once",
                    item_id=row.assessment_id,
                )
            )
        assessment_ids.add(row.assessment_id)
        if row.step_id in step_ids:
            findings.append(
                ArchitectureReductionFinding(
                    "duplicate_step_action",
                    "one retained-route step received more than one action",
                    item_id=row.step_id,
                )
            )
        step_ids.add(row.step_id)

        missing = tuple(
            name
            for name in (
                "assessment_id",
                "parent_route_id",
                "step_id",
                "step_kind",
                "action",
                "proof_status",
                "rationale",
            )
            if not str(getattr(row, name, "")).strip()
        )
        if missing:
            findings.append(
                ArchitectureReductionFinding(
                    "incomplete_step_assessment",
                    "internal-step assessment is incomplete",
                    item_id=row.step_id,
                    metadata={"missing_fields": missing},
                )
            )
        if row.step_kind not in ARCHITECTURE_REDUCTION_STEP_KINDS:
            findings.append(
                ArchitectureReductionFinding(
                    "invalid_step_kind",
                    f"internal-step kind {row.step_kind!r} is not supported",
                    item_id=row.step_id,
                )
            )
        if row.action not in ARCHITECTURE_REDUCTION_STEP_ACTIONS:
            findings.append(
                ArchitectureReductionFinding(
                    "invalid_step_action",
                    f"internal-step action {row.action!r} is not supported",
                    item_id=row.step_id,
                )
            )
        if row.proof_status not in ARCHITECTURE_REDUCTION_PROOF_STATUSES:
            findings.append(
                ArchitectureReductionFinding(
                    "invalid_step_proof_status",
                    f"internal-step proof status {row.proof_status!r} is not supported",
                    item_id=row.step_id,
                )
            )

        candidate = candidate_by_id.get(row.candidate_id) if row.candidate_id else None
        if row.candidate_id and candidate is None:
            findings.append(
                ArchitectureReductionFinding(
                    "step_candidate_missing",
                    "internal-step assessment references an unknown reduction candidate",
                    candidate_id=row.candidate_id,
                    item_id=row.step_id,
                )
            )
        if candidate is not None:
            allowed = compatible_target_actions.get(row.action)
            if allowed is not None and candidate.target_action not in allowed:
                findings.append(
                    ArchitectureReductionFinding(
                        "step_candidate_action_mismatch",
                        "internal-step action does not match its reduction candidate action",
                        candidate_id=candidate.candidate_id,
                        item_id=row.step_id,
                        metadata={
                            "step_action": row.action,
                            "candidate_action": candidate.target_action,
                        },
                    )
                )
            if row.proof_status != candidate.proof_status:
                findings.append(
                    ArchitectureReductionFinding(
                        "step_candidate_proof_mismatch",
                        "internal-step proof status differs from its candidate proof status",
                        candidate_id=candidate.candidate_id,
                        item_id=row.step_id,
                    )
                )

        if row.action != STEP_ACTION_UNRESOLVED and not row.cost_evidence:
            findings.append(
                ArchitectureReductionFinding(
                    "step_cost_evidence_missing",
                    "a decided internal step lacks current operation or payload cost evidence",
                    item_id=row.step_id,
                )
            )
        for cost in row.cost_evidence:
            if not cost.current:
                findings.append(
                    ArchitectureReductionFinding(
                        "step_cost_evidence_stale",
                        "internal-step cost evidence is stale",
                        item_id=row.step_id,
                        metadata={"measurement_id": cost.measurement_id},
                    )
                )

        if row.action == STEP_ACTION_UNRESOLVED:
            if not row.unresolved_gap_ids:
                findings.append(
                    ArchitectureReductionFinding(
                        "step_unresolved_gap_missing",
                        "an unresolved internal step must name the missing proof or ownership gap",
                        item_id=row.step_id,
                    )
                )
            else:
                findings.append(
                    ArchitectureReductionFinding(
                        "internal_step_unresolved",
                        "internal-step cost or duplication is visible, but evidence does not authorize a change",
                        severity="warning",
                        item_id=row.step_id,
                        metadata={"gap_ids": row.unresolved_gap_ids},
                    )
                )
            continue

        if not row.caller_inventory_complete and row.action in _STEP_CONTRACTION_ACTIONS:
            findings.append(
                ArchitectureReductionFinding(
                    "step_caller_inventory_incomplete",
                    "internal-step contraction lacks a complete current caller inventory",
                    item_id=row.step_id,
                )
            )
        if not row.safety_inventory_complete:
            findings.append(
                ArchitectureReductionFinding(
                    "step_safety_inventory_incomplete",
                    "internal-step decision lacks a complete safety and evidence-owner inventory",
                    item_id=row.step_id,
                )
            )

        safety_ids = set(row.safety_responsibility_ids)
        safety_binding_ids = set(row.safety_owner_bindings)
        if safety_ids != safety_binding_ids or any(
            not owner_id.strip() for owner_id in row.safety_owner_bindings.values()
        ):
            findings.append(
                ArchitectureReductionFinding(
                    "step_safety_owner_incomplete",
                    "every unique safety or evidence responsibility needs one exact post-action owner",
                    item_id=row.step_id,
                    metadata={
                        "responsibility_ids": tuple(sorted(safety_ids)),
                        "binding_ids": tuple(sorted(safety_binding_ids)),
                    },
                )
            )
        if safety_ids and not row.safety_evidence_refs:
            findings.append(
                ArchitectureReductionFinding(
                    "step_safety_transfer_evidence_missing",
                    "unique safety or evidence responsibilities lack current owner evidence",
                    item_id=row.step_id,
                )
            )
        if row.action in {
            STEP_ACTION_MERGE,
            STEP_ACTION_REMOVE,
            STEP_ACTION_EXPLICIT_ON_DEMAND,
        } and any(
            owner_id == row.step_id
            for owner_id in row.safety_owner_bindings.values()
        ):
            findings.append(
                ArchitectureReductionFinding(
                    "step_unique_safety_owner_removed",
                    "a changed or removed step still uniquely owns a required safety or evidence responsibility",
                    item_id=row.step_id,
                )
            )

        if row.action == STEP_ACTION_RETAIN:
            if not row.current_owner_ids or not row.necessity_evidence_refs:
                findings.append(
                    ArchitectureReductionFinding(
                        "step_retain_authority_missing",
                        "retaining an internal step requires a current needed owner and necessity evidence",
                        item_id=row.step_id,
                    )
                )
            continue

        if row.action in _STEP_CONTRACTION_ACTIONS and (
            row.proof_status not in READY_PROOF_STATUSES
            or not row.equivalence_evidence_refs
        ):
            findings.append(
                ArchitectureReductionFinding(
                    "step_contraction_equivalence_missing",
                    "operation or payload cost cannot replace current observable-equivalence or facade-delegation proof",
                    candidate_id=row.candidate_id,
                    item_id=row.step_id,
                )
            )
        if row.action in {STEP_ACTION_MERGE, STEP_ACTION_DELEGATE} and not row.replacement_step_ids:
            findings.append(
                ArchitectureReductionFinding(
                    "step_replacement_missing",
                    "merge or delegate needs one exact replacement step or owner",
                    candidate_id=row.candidate_id,
                    item_id=row.step_id,
                )
            )
        if row.action == STEP_ACTION_REMOVE and row.caller_ids and not row.replacement_step_ids:
            findings.append(
                ArchitectureReductionFinding(
                    "step_replacement_missing",
                    "a called step cannot be removed without one exact replacement target",
                    candidate_id=row.candidate_id,
                    item_id=row.step_id,
                )
            )
        if (
            row.action == STEP_ACTION_EXPLICIT_ON_DEMAND
            and not row.on_demand_trigger_ids
        ):
            findings.append(
                ArchitectureReductionFinding(
                    "step_on_demand_trigger_missing",
                    "an explicit-on-demand step must name its explicit trigger boundary",
                    candidate_id=row.candidate_id,
                    item_id=row.step_id,
                )
            )
    return findings


def _surfaces_by_candidate(
    surfaces: Sequence[CompatibilitySurfaceClassification],
) -> dict[str, tuple[CompatibilitySurfaceClassification, ...]]:
    grouped: dict[str, list[CompatibilitySurfaceClassification]] = {}
    for surface in surfaces:
        for candidate_id in surface.candidate_ids:
            grouped.setdefault(candidate_id, []).append(surface)
    return {candidate_id: tuple(items) for candidate_id, items in grouped.items()}


def _candidate_inventory_findings(
    plan: ArchitectureReductionPlan,
) -> tuple[
    list[ArchitectureReductionFinding],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    findings: list[ArchitectureReductionFinding] = []
    expected = set(plan.expected_candidate_ids)
    materialized = {candidate.candidate_id for candidate in plan.candidates if candidate.candidate_id}
    scoped = set(plan.scoped_candidate_reasons)
    inventory_claimed = bool(plan.require_complete_inventory or expected or plan.canonical_relation_handoff)
    if inventory_claimed and not plan.inventory_revision:
        findings.append(
            ArchitectureReductionFinding(
                "candidate_inventory_revision_missing",
                "architecture-reduction candidate completeness requires an inventory revision",
            )
        )
    if inventory_claimed and not plan.inventory_source_ref:
        findings.append(
            ArchitectureReductionFinding(
                "candidate_inventory_provenance_missing",
                "architecture-reduction expected inventory lacks source provenance",
            )
        )
    if inventory_claimed and not plan.inventory_current:
        findings.append(
            ArchitectureReductionFinding(
                "candidate_inventory_stale",
                "architecture-reduction candidate inventory is stale",
            )
        )
    if plan.require_complete_inventory and not expected:
        findings.append(
            ArchitectureReductionFinding(
                "expected_candidate_inventory_missing",
                "complete architecture-reduction review has no independently declared expected candidates",
            )
        )
    for candidate_id, reason in plan.scoped_candidate_reasons.items():
        if not reason:
            findings.append(
                ArchitectureReductionFinding(
                    "candidate_scoped_reason_missing",
                    "scoped candidate disposition requires a reason",
                    candidate_id=candidate_id,
                )
            )
    missing = expected - materialized - scoped
    for candidate_id in sorted(missing):
        findings.append(
            ArchitectureReductionFinding(
                "expected_reduction_candidate_missing",
                "expected architecture-reduction candidate is omitted without scoped disposition",
                candidate_id=candidate_id,
                metadata={"inventory_revision": plan.inventory_revision},
            )
        )
    unexpected = materialized - expected if plan.require_complete_inventory else set()
    for candidate_id in sorted(unexpected):
        findings.append(
            ArchitectureReductionFinding(
                "unexpected_reduction_candidate",
                "materialized architecture-reduction candidate is outside the complete expected inventory",
                candidate_id=candidate_id,
                metadata={"inventory_revision": plan.inventory_revision},
            )
        )
    for candidate in plan.candidates:
        if plan.inventory_revision and candidate.inventory_revision != plan.inventory_revision:
            findings.append(
                ArchitectureReductionFinding(
                    "candidate_inventory_revision_mismatch",
                    "candidate was derived from a different or missing inventory revision",
                    candidate_id=candidate.candidate_id,
                    metadata={"expected": plan.inventory_revision, "actual": candidate.inventory_revision},
                )
            )
    return (
        findings,
        tuple(sorted(expected & materialized)),
        tuple(sorted(expected & scoped)),
        tuple(sorted(missing)),
        tuple(sorted(unexpected)),
    )


def _plan_canonical_relation_findings(
    plan: ArchitectureReductionPlan,
) -> tuple[list[ArchitectureReductionFinding], tuple[str, ...], tuple[str, ...]]:
    handoff = plan.canonical_relation_handoff
    materialized_relations = {
        item_id
        for candidate in plan.candidates
        for item_id in (
            candidate.materialized_relation_ids
            + (candidate.canonical_relation_handoff.relation_ids if candidate.canonical_relation_handoff else ())
        )
    }
    materialized_code = {
        item_id
        for candidate in plan.candidates
        for item_id in (
            candidate.materialized_relation_code_obligation_ids
            + (candidate.canonical_relation_handoff.code_obligation_ids if candidate.canonical_relation_handoff else ())
        )
    }
    if handoff is None:
        return [], tuple(sorted(materialized_relations)), tuple(sorted(materialized_code))
    findings: list[ArchitectureReductionFinding] = []
    scoped = set(plan.scoped_relation_reasons)
    for item_id, reason in plan.scoped_relation_reasons.items():
        if not reason:
            findings.append(
                ArchitectureReductionFinding(
                    "relation_scoped_reason_missing",
                    "scoped canonical relation candidate disposition requires a reason",
                    item_id=item_id,
                )
            )
    if not handoff.evidence_current:
        findings.append(
            ArchitectureReductionFinding(
                "stale_canonical_relation_provenance",
                "architecture-reduction canonical relation handoff evidence is stale",
                metadata=handoff.to_dict(),
            )
        )
    for gap_id in handoff.gap_ids:
        findings.append(
            ArchitectureReductionFinding(
                "canonical_relation_gap_unresolved",
                "canonical relation handoff contains an unresolved affected-owner gap",
                item_id=gap_id,
                metadata=handoff.to_dict(),
            )
        )
    if (handoff.relation_ids or handoff.code_obligation_ids) and not plan.candidates:
        findings.append(
            ArchitectureReductionFinding(
                "canonical_relation_candidate_inventory_empty",
                "duplicate/same-intent canonical relation handoff produced no concrete reduction candidates",
                metadata=handoff.to_dict(),
            )
        )
    for relation_id in handoff.relation_ids:
        if relation_id in materialized_relations or relation_id in scoped:
            continue
        findings.append(
            ArchitectureReductionFinding(
                "unmaterialized_reduction_relation",
                "canonical relation id is not bound to a concrete reduction candidate",
                item_id=relation_id,
                metadata=handoff.to_dict(),
            )
        )
    for obligation_id in handoff.code_obligation_ids:
        if obligation_id in materialized_code or obligation_id in scoped:
            continue
        findings.append(
            ArchitectureReductionFinding(
                "unmaterialized_reduction_code_obligation",
                "canonical relation code-obligation id is not bound to a concrete reduction candidate",
                item_id=obligation_id,
                metadata=handoff.to_dict(),
            )
        )
    return findings, tuple(sorted(materialized_relations)), tuple(sorted(materialized_code))


def _is_sha256(value: str) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("sha256:")
        and len(value) == 71
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _retirement_proof_findings(
    plan: ArchitectureReductionPlan,
    candidate: ArchitectureReductionCandidate,
) -> tuple[list[ArchitectureReductionFinding], bool]:
    findings: list[ArchitectureReductionFinding] = []
    proof = candidate.retirement_proof
    if candidate.target_action != TARGET_ACTION_RETIRE_BEHAVIOR:
        if proof is not None:
            findings.append(
                ArchitectureReductionFinding(
                    "retirement_proof_on_contract_action",
                    "ordinary contraction cannot use a behavior-retirement proof",
                    candidate_id=candidate.candidate_id,
                )
            )
        if candidate.proof_status == PROOF_AUTHORIZED_RETIREMENT:
            findings.append(
                ArchitectureReductionFinding(
                    "retirement_status_on_contract_action",
                    "authorized-retirement status is valid only for retire_behavior",
                    candidate_id=candidate.candidate_id,
                )
            )
        return findings, False

    if candidate.proof_status != PROOF_AUTHORIZED_RETIREMENT:
        findings.append(
            ArchitectureReductionFinding(
                "retirement_proof_status_mismatch",
                "retire_behavior requires explicit authorized_retirement status",
                candidate_id=candidate.candidate_id,
                item_id=candidate.proof_status,
            )
        )
    if proof is None:
        findings.append(
            ArchitectureReductionFinding(
                "retirement_proof_missing",
                "retire_behavior requires one complete current typed retirement proof",
                candidate_id=candidate.candidate_id,
            )
        )
        return findings, False
    if proof.schema != ARCHITECTURE_RETIREMENT_PROOF_SCHEMA:
        findings.append(
            ArchitectureReductionFinding(
                "retirement_proof_schema_stale",
                "retirement proof does not use the sole current schema",
                candidate_id=candidate.candidate_id,
                item_id=proof.schema,
            )
        )
    if not proof.retirement_id.strip():
        findings.append(
            ArchitectureReductionFinding(
                "retirement_identity_missing",
                "retirement proof requires one stable retirement id",
                candidate_id=candidate.candidate_id,
            )
        )
    if len(proof.current_goal_rationale.strip()) < 20:
        findings.append(
            ArchitectureReductionFinding(
                "retirement_current_goal_rationale_missing",
                "retirement proof must explain why the current product goal no longer needs the behavior",
                candidate_id=candidate.candidate_id,
            )
        )
    if not plan.require_complete_inventory or not plan.expected_candidate_ids:
        findings.append(
            ArchitectureReductionFinding(
                "retirement_complete_inventory_missing",
                "behavior retirement requires an independently complete candidate inventory",
                candidate_id=candidate.candidate_id,
            )
        )
    if not plan.inventory_current or not proof.inventory_current:
        findings.append(
            ArchitectureReductionFinding(
                "retirement_inventory_stale",
                "behavior retirement inventory is not exact-current",
                candidate_id=candidate.candidate_id,
            )
        )
    if (
        not proof.inventory_revision
        or proof.inventory_revision != candidate.inventory_revision
        or proof.inventory_revision != plan.inventory_revision
    ):
        findings.append(
            ArchitectureReductionFinding(
                "retirement_inventory_revision_mismatch",
                "candidate, plan, and retirement proof do not share one inventory revision",
                candidate_id=candidate.candidate_id,
                metadata={
                    "candidate": candidate.inventory_revision,
                    "plan": plan.inventory_revision,
                    "proof": proof.inventory_revision,
                },
            )
        )
    if proof.owner_resolution_status != RETIREMENT_OWNER_STATUS_EXACT_CURRENT:
        findings.append(
            ArchitectureReductionFinding(
                "retirement_owner_resolution_not_current",
                "retirement owners are missing, stale, ambiguous, unknown, or guessed",
                candidate_id=candidate.candidate_id,
                item_id=proof.owner_resolution_status,
            )
        )
    for field_name in (
        "business_intent_id",
        "behavior_commitment_id",
        "primary_path_id",
    ):
        if not getattr(candidate, field_name).strip():
            findings.append(
                ArchitectureReductionFinding(
                    "retirement_candidate_authority_incomplete",
                    "retirement candidate lacks exact current intent, commitment, or path identity",
                    candidate_id=candidate.candidate_id,
                    item_id=field_name,
                )
            )
    if (
        candidate.behavior_commitment_id
        and candidate.behavior_commitment_id not in proof.retired_commitment_ids
    ):
        findings.append(
            ArchitectureReductionFinding(
                "retirement_commitment_not_governed",
                "candidate commitment is absent from the retirement responsibility inventory",
                candidate_id=candidate.candidate_id,
                item_id=candidate.behavior_commitment_id,
            )
        )

    identity_roles = set(proof.governed_identity_fingerprints)
    missing_identity_roles = tuple(
        sorted(ARCHITECTURE_RETIREMENT_GOVERNED_IDENTITY_ROLES - identity_roles)
    )
    unknown_identity_roles = tuple(
        sorted(identity_roles - ARCHITECTURE_RETIREMENT_GOVERNED_IDENTITY_ROLES)
    )
    stale_identity_roles = tuple(
        sorted(
            role
            for role, fingerprint in proof.governed_identity_fingerprints.items()
            if not _is_sha256(fingerprint)
        )
    )
    if missing_identity_roles or unknown_identity_roles or stale_identity_roles:
        findings.append(
            ArchitectureReductionFinding(
                "retirement_governed_identities_incomplete",
                "retirement proof lacks one exact current governed identity set",
                candidate_id=candidate.candidate_id,
                metadata={
                    "missing_roles": missing_identity_roles,
                    "unknown_roles": unknown_identity_roles,
                    "invalid_fingerprint_roles": stale_identity_roles,
                },
            )
        )

    required_routes = set(proof.required_validation_routes)
    missing_routes = tuple(
        sorted(ARCHITECTURE_RETIREMENT_REQUIRED_ROUTES - required_routes)
    )
    unknown_routes = tuple(
        sorted(required_routes - ARCHITECTURE_REDUCTION_COMPANION_ROUTES)
    )
    if missing_routes or unknown_routes:
        findings.append(
            ArchitectureReductionFinding(
                "retirement_validation_routes_incomplete",
                "retirement proof lacks the complete recognized validation route set",
                candidate_id=candidate.candidate_id,
                metadata={
                    "missing_routes": missing_routes,
                    "unknown_routes": unknown_routes,
                },
            )
        )
    if not proof.evidence_refs or any(
        not evidence_ref.strip() for evidence_ref in proof.evidence_refs
    ):
        findings.append(
            ArchitectureReductionFinding(
                "retirement_proof_evidence_missing",
                "retirement proof requires current evidence references",
                candidate_id=candidate.candidate_id,
            )
        )

    governed = proof.governed_responsibility_ids()
    not_applicable = dict(proof.not_applicable_responsibility_kinds)
    invalid_not_applicable = tuple(
        sorted(set(not_applicable) - ARCHITECTURE_RETIREMENT_RESPONSIBILITY_KINDS)
    )
    empty_not_applicable = tuple(
        sorted(kind for kind, reason in not_applicable.items() if not reason.strip())
    )
    if invalid_not_applicable or empty_not_applicable:
        findings.append(
            ArchitectureReductionFinding(
                "retirement_not_applicable_disposition_invalid",
                "not-applicable responsibility kinds require recognized kinds and concrete reasons",
                candidate_id=candidate.candidate_id,
                metadata={
                    "invalid_kinds": invalid_not_applicable,
                    "empty_reasons": empty_not_applicable,
                },
            )
        )
    for kind, responsibility_ids in governed.items():
        blank_ids = tuple(
            item_id for item_id in responsibility_ids if not item_id.strip()
        )
        if blank_ids:
            findings.append(
                ArchitectureReductionFinding(
                    "retirement_responsibility_identity_missing",
                    "retirement responsibility ids must be stable non-empty identities",
                    candidate_id=candidate.candidate_id,
                    item_id=kind,
                )
            )
        duplicate_ids = tuple(
            sorted(
                item_id
                for item_id in set(responsibility_ids)
                if responsibility_ids.count(item_id) > 1
            )
        )
        if duplicate_ids:
            findings.append(
                ArchitectureReductionFinding(
                    "retirement_responsibility_identity_duplicate",
                    "retirement responsibility identities must be unique per kind",
                    candidate_id=candidate.candidate_id,
                    item_id=kind,
                    metadata={"duplicate_ids": duplicate_ids},
                )
            )
        if responsibility_ids and kind in not_applicable:
            findings.append(
                ArchitectureReductionFinding(
                    "retirement_responsibility_scope_conflict",
                    "a responsibility kind cannot be both governed and not applicable",
                    candidate_id=candidate.candidate_id,
                    item_id=kind,
                )
            )
        if not responsibility_ids and kind not in not_applicable:
            findings.append(
                ArchitectureReductionFinding(
                    "retirement_responsibility_scope_missing",
                    "every responsibility kind needs governed ids or an explicit not-applicable reason",
                    candidate_id=candidate.candidate_id,
                    item_id=kind,
                )
            )
    for required_kind in (
        RETIREMENT_RESPONSIBILITY_COMMITMENT,
        RETIREMENT_RESPONSIBILITY_BEHAVIOR,
    ):
        if not governed[required_kind]:
            findings.append(
                ArchitectureReductionFinding(
                    "retirement_primary_identity_missing",
                    "retire_behavior requires explicit retired commitment and behavior ids",
                    candidate_id=candidate.candidate_id,
                    item_id=required_kind,
                )
            )

    expected_keys = {
        (kind, item_id)
        for kind, responsibility_ids in governed.items()
        for item_id in responsibility_ids
    }
    rows_by_key: dict[
        tuple[str, str],
        list[RetirementResponsibilityDisposition],
    ] = {}
    for row in proof.responsibility_dispositions:
        if not isinstance(row, RetirementResponsibilityDisposition):
            findings.append(
                ArchitectureReductionFinding(
                    "retirement_responsibility_disposition_untyped",
                    "retirement proof contains a non-current disposition row",
                    candidate_id=candidate.candidate_id,
                )
            )
            continue
        key = (row.responsibility_kind, row.responsibility_id)
        rows_by_key.setdefault(key, []).append(row)
        if row.schema != ARCHITECTURE_RETIREMENT_RESPONSIBILITY_DISPOSITION_SCHEMA:
            findings.append(
                ArchitectureReductionFinding(
                    "retirement_responsibility_schema_stale",
                    "retirement responsibility row does not use the current schema",
                    candidate_id=candidate.candidate_id,
                    item_id=row.responsibility_id,
                )
            )
        if row.responsibility_kind not in ARCHITECTURE_RETIREMENT_RESPONSIBILITY_KINDS:
            findings.append(
                ArchitectureReductionFinding(
                    "retirement_responsibility_kind_unknown",
                    "retirement responsibility kind is unknown",
                    candidate_id=candidate.candidate_id,
                    item_id=row.responsibility_kind,
                )
            )
        if row.disposition in FORBIDDEN_RETIREMENT_DISPOSITIONS:
            findings.append(
                ArchitectureReductionFinding(
                    "retirement_compatibility_or_fallback_forbidden",
                    "retired behavior cannot survive through alias, compatibility, forwarder, or fallback disposition",
                    candidate_id=candidate.candidate_id,
                    item_id=row.responsibility_id,
                )
            )
        elif row.disposition not in ARCHITECTURE_RETIREMENT_DISPOSITIONS:
            findings.append(
                ArchitectureReductionFinding(
                    "retirement_disposition_unknown",
                    "retirement responsibility disposition is unknown",
                    candidate_id=candidate.candidate_id,
                    item_id=row.disposition,
                )
            )
        if (
            not row.responsibility_kind.strip()
            or not row.responsibility_id.strip()
            or not row.rationale.strip()
            or not row.evidence_refs
            or any(not evidence_ref.strip() for evidence_ref in row.evidence_refs)
        ):
            findings.append(
                ArchitectureReductionFinding(
                    "retirement_responsibility_evidence_missing",
                    "every responsibility disposition requires rationale and current evidence",
                    candidate_id=candidate.candidate_id,
                    item_id=row.responsibility_id,
                )
            )
        if row.current_reference_remaining:
            findings.append(
                ArchitectureReductionFinding(
                    "retirement_dangling_current_reference",
                    "a current reference still reaches the retired responsibility",
                    candidate_id=candidate.candidate_id,
                    item_id=row.responsibility_id,
                )
            )
        if row.retained_runtime_authority:
            findings.append(
                ArchitectureReductionFinding(
                    "retirement_runtime_authority_retained",
                    "retired or historical responsibility retains runtime authority",
                    candidate_id=candidate.candidate_id,
                    item_id=row.responsibility_id,
                )
            )
        replacement_required = row.disposition in {
            RETIREMENT_DISPOSITION_REPLACE,
            RETIREMENT_DISPOSITION_MIGRATE,
        }
        if replacement_required:
            if (
                not row.replacement_owner_id
                or row.replacement_owner_status
                != RETIREMENT_OWNER_STATUS_EXACT_CURRENT
            ):
                findings.append(
                    ArchitectureReductionFinding(
                        "retirement_replacement_owner_not_current",
                        "replacement or migrated protection lacks one exact current owner",
                        candidate_id=candidate.candidate_id,
                        item_id=row.responsibility_id,
                    )
                )
        elif (
            row.replacement_owner_id
            or row.replacement_owner_status
            != RETIREMENT_OWNER_STATUS_NOT_APPLICABLE
        ):
            findings.append(
                ArchitectureReductionFinding(
                    "retirement_replacement_owner_ambiguous",
                    "retire/history disposition must not carry a guessed replacement owner",
                    candidate_id=candidate.candidate_id,
                    item_id=row.responsibility_id,
                )
            )
        if row.protection_required and not replacement_required:
            findings.append(
                ArchitectureReductionFinding(
                    "retained_protection_without_current_owner",
                    "a still-required protection is retired without migration to a current owner",
                    candidate_id=candidate.candidate_id,
                    item_id=row.responsibility_id,
                )
            )
        if (
            row.responsibility_kind == RETIREMENT_RESPONSIBILITY_NEGATIVE_CASE
            and row.protection_required
            and (not row.oracle_id or not replacement_required)
        ):
            findings.append(
                ArchitectureReductionFinding(
                    "retirement_negative_case_orphaned",
                    "a retained negative case lacks its oracle or exact replacement owner",
                    candidate_id=candidate.candidate_id,
                    item_id=row.responsibility_id,
                )
            )

    duplicate_keys = tuple(
        sorted(key for key, rows in rows_by_key.items() if len(rows) != 1)
    )
    missing_keys = tuple(sorted(expected_keys - set(rows_by_key)))
    unexpected_keys = tuple(sorted(set(rows_by_key) - expected_keys))
    if duplicate_keys or missing_keys or unexpected_keys:
        findings.append(
            ArchitectureReductionFinding(
                "retirement_responsibility_disposition_incomplete",
                "retirement proof does not disposition every governed responsibility exactly once",
                candidate_id=candidate.candidate_id,
                metadata={
                    "duplicate": duplicate_keys,
                    "missing": missing_keys,
                    "unexpected": unexpected_keys,
                },
            )
        )

    row_replacement_owners = {
        row.replacement_owner_id
        for rows in rows_by_key.values()
        for row in rows
        if row.replacement_owner_id
    }
    declared_replacement_owners = set(proof.replacement_owner_ids)
    if (
        len(proof.replacement_owner_ids)
        != len(declared_replacement_owners)
        or row_replacement_owners != declared_replacement_owners
    ):
        findings.append(
            ArchitectureReductionFinding(
                "retirement_replacement_owner_inventory_mismatch",
                "declared replacement-owner inventory does not exactly match responsibility dispositions",
                candidate_id=candidate.candidate_id,
                metadata={
                    "declared": tuple(sorted(declared_replacement_owners)),
                    "materialized": tuple(sorted(row_replacement_owners)),
                },
            )
        )

    return findings, not _blockers(findings)


def review_architecture_reduction(plan: ArchitectureReductionPlan) -> ArchitectureReductionReport:
    """Review whether modeled flow evidence supports code architecture contraction."""

    findings: list[ArchitectureReductionFinding] = []
    ready_candidates: list[str] = []
    completed_candidates: list[str] = []
    target_actions: list[TargetArchitectureAction] = []
    required_routes: set[str] = set()
    compatibility_blocked_candidate_ids: set[str] = set()
    retirement_blocked_candidate_ids: set[str] = set()
    step_blocked_candidate_ids: set[str] = set()
    surfaces_by_candidate = _surfaces_by_candidate(plan.compatibility_surfaces)
    inventory_values = _candidate_inventory_findings(plan)
    findings.extend(inventory_values[0])
    relation_values = _plan_canonical_relation_findings(plan)
    findings.extend(relation_values[0])
    step_findings = _step_assessment_findings(plan)
    findings.extend(step_findings)
    blocked_step_ids = {
        finding.item_id
        for finding in step_findings
        if finding.severity == "blocker" and finding.item_id
    }
    step_blocked_candidate_ids.update(
        row.candidate_id
        for row in plan.step_assessments
        if row.candidate_id
        and (
            row.step_id in blocked_step_ids
            or row.assessment_id in blocked_step_ids
            or any(
                finding.severity == "blocker"
                and finding.candidate_id == row.candidate_id
                for finding in step_findings
            )
        )
    )

    if not plan.reduction_id:
        findings.append(
            ArchitectureReductionFinding(
                "missing_reduction_id",
                "architecture reduction review has no reduction id",
            )
        )
    if not plan.rationale:
        findings.append(
            ArchitectureReductionFinding(
                "missing_reduction_rationale",
                "architecture reduction review has no route rationale",
                severity="warning",
            )
        )

    missing_contract_fields = plan.observable_contract.missing_fields()
    if missing_contract_fields:
        findings.append(
            ArchitectureReductionFinding(
                "missing_observable_contract",
                "observable architecture contract is incomplete",
                metadata={"missing_fields": missing_contract_fields},
            )
        )

    if not plan.companion_route_triggers:
        findings.append(
            ArchitectureReductionFinding(
                "missing_companion_route_triggers",
                "no companion FlowGuard route triggers are recorded",
                severity="warning",
            )
        )
    for trigger in plan.companion_route_triggers:
        if trigger.route_id not in ARCHITECTURE_REDUCTION_COMPANION_ROUTES:
            findings.append(
                ArchitectureReductionFinding(
                    "unknown_companion_route",
                    f"companion route {trigger.route_id!r} is not recognized",
                    severity="warning",
                    item_id=trigger.route_id,
                )
            )
        else:
            required_routes.add(trigger.route_id)
        if not trigger.trigger_reason:
            findings.append(
                ArchitectureReductionFinding(
                    "missing_companion_trigger_reason",
                    f"companion route {trigger.route_id!r} has no trigger reason",
                    severity="warning",
                    item_id=trigger.route_id,
                )
            )

    for surface in plan.compatibility_surfaces:
        missing_surface_fields = surface.missing_fields()
        if missing_surface_fields:
            findings.append(
                ArchitectureReductionFinding(
                    "incomplete_compatibility_surface",
                    "compatibility surface classification is incomplete",
                    item_id=surface.surface_id,
                    metadata={"missing_fields": missing_surface_fields, "surface": surface.to_dict()},
                )
            )
        if surface.classification not in COMPATIBILITY_SURFACE_CLASSIFICATIONS:
            findings.append(
                ArchitectureReductionFinding(
                    "invalid_compatibility_surface_classification",
                    f"compatibility surface classification {surface.classification!r} is not supported",
                    item_id=surface.surface_id,
                    metadata=surface.to_dict(),
                )
            )
        if surface.field_ids and not (surface.evidence_refs or surface.owner_model_elements):
            findings.append(
                ArchitectureReductionFinding(
                    "compatibility_field_surface_missing_evidence",
                    "compatibility surface names old fields but lacks model owner or disposition evidence",
                    item_id=surface.surface_id,
                    metadata=surface.to_dict(),
                )
            )
        if surface.recommended_action not in COMPATIBILITY_SURFACE_RECOMMENDED_ACTIONS:
            findings.append(
                ArchitectureReductionFinding(
                    "invalid_compatibility_surface_action",
                    f"compatibility surface action {surface.recommended_action!r} is not supported",
                    item_id=surface.surface_id,
                    metadata=surface.to_dict(),
                )
            )
        if surface.classification == COMPATIBILITY_SURFACE_ARCHIVE_ONLY and surface.runtime_authority:
            compatibility_blocked_candidate_ids.update(surface.candidate_ids)
            findings.append(
                ArchitectureReductionFinding(
                    "compatibility_surface_archive_has_runtime_authority",
                    "archive-only compatibility surface still has runtime authority",
                    item_id=surface.surface_id,
                    metadata=surface.to_dict(),
                )
            )
        if surface.classification == COMPATIBILITY_SURFACE_EVIDENCE_NEEDED:
            compatibility_blocked_candidate_ids.update(surface.candidate_ids)
            findings.append(
                ArchitectureReductionFinding(
                    "compatibility_surface_evidence_needed",
                    "compatibility surface needs more evidence before linked candidates can be ready",
                    item_id=surface.surface_id,
                    metadata=surface.to_dict(),
                )
            )

    observable_state = set(plan.observable_contract.observable_state)
    observable_side_effects = set(plan.observable_contract.observable_side_effects)
    pre_candidate_blocked = bool(_blockers(findings))

    for candidate in plan.candidates:
        candidate_finding_start = len(findings)
        linked_surfaces = surfaces_by_candidate.get(candidate.candidate_id, ())
        retirement_findings, retirement_authorized = _retirement_proof_findings(
            plan,
            candidate,
        )
        findings.extend(retirement_findings)
        if _blockers(retirement_findings):
            retirement_blocked_candidate_ids.add(candidate.candidate_id)
        if candidate.target_action == TARGET_ACTION_RETIRE_BEHAVIOR:
            if candidate.retirement_proof is not None:
                required_routes.update(
                    set(candidate.retirement_proof.required_validation_routes)
                    & ARCHITECTURE_REDUCTION_COMPANION_ROUTES
                )
        missing_candidate_fields = _candidate_incomplete(candidate)
        if missing_candidate_fields:
            findings.append(
                ArchitectureReductionFinding(
                    "incomplete_candidate",
                    "architecture reduction candidate is incomplete",
                    candidate_id=candidate.candidate_id,
                    metadata={"missing_fields": missing_candidate_fields},
                )
            )
        if candidate.candidate_type not in ARCHITECTURE_REDUCTION_CANDIDATE_TYPES:
            findings.append(
                ArchitectureReductionFinding(
                    "invalid_candidate_type",
                    f"candidate type {candidate.candidate_type!r} is not supported",
                    candidate_id=candidate.candidate_id,
                    item_id=candidate.candidate_type,
                )
            )
        if candidate.target_action not in ARCHITECTURE_REDUCTION_TARGET_ACTIONS:
            findings.append(
                ArchitectureReductionFinding(
                    "invalid_target_action",
                    f"target action {candidate.target_action!r} is not supported",
                    candidate_id=candidate.candidate_id,
                    item_id=candidate.target_action,
                )
            )
        if candidate.proof_status not in ARCHITECTURE_REDUCTION_PROOF_STATUSES:
            findings.append(
                ArchitectureReductionFinding(
                    "invalid_proof_status",
                    f"proof status {candidate.proof_status!r} is not supported",
                    candidate_id=candidate.candidate_id,
                    item_id=candidate.proof_status,
                )
            )
        if candidate.lifecycle_disposition not in ARCHITECTURE_REDUCTION_CANDIDATE_DISPOSITIONS:
            findings.append(
                ArchitectureReductionFinding(
                    "invalid_lifecycle_disposition",
                    f"candidate lifecycle disposition {candidate.lifecycle_disposition!r} is not supported",
                    candidate_id=candidate.candidate_id,
                    item_id=candidate.lifecycle_disposition,
                )
            )
        if candidate.is_closed and not candidate.completion_evidence_refs:
            findings.append(
                ArchitectureReductionFinding(
                    "completed_candidate_missing_evidence",
                    "completed or historical candidates must cite completion evidence before leaving the active queue",
                    candidate_id=candidate.candidate_id,
                )
            )
        if candidate.required_next_route not in ARCHITECTURE_REDUCTION_COMPANION_ROUTES:
            findings.append(
                ArchitectureReductionFinding(
                    "missing_required_next_route",
                    "candidate does not name a recognized next route",
                    candidate_id=candidate.candidate_id,
                    item_id=candidate.required_next_route,
                )
            )
        elif candidate.lifecycle_disposition == CANDIDATE_DISPOSITION_ACTIVE:
            required_routes.add(candidate.required_next_route)

        canonical_relation_handoff = candidate.canonical_relation_handoff
        relation_ids = canonical_relation_handoff.relation_ids if canonical_relation_handoff else ()
        relation_code_obligation_ids = canonical_relation_handoff.code_obligation_ids if canonical_relation_handoff else ()
        if relation_ids and candidate.is_ready and not candidate.evidence_refs:
            findings.append(
                ArchitectureReductionFinding(
                    "canonical_relation_without_candidate_evidence",
                    "canonical relation provenance does not prove architecture contraction without candidate evidence refs",
                    candidate_id=candidate.candidate_id,
                    metadata={"relation_ids": list(relation_ids)},
                )
            )
        if relation_ids and not relation_code_obligation_ids:
            findings.append(
                ArchitectureReductionFinding(
                    "missing_relation_code_obligation",
                    "canonical-relation-derived contraction should cite the code maintenance obligation that identified the duplicate boundary or adapter-only flow",
                    severity="warning",
                    candidate_id=candidate.candidate_id,
                    metadata={"relation_ids": list(relation_ids)},
                )
            )
        if canonical_relation_handoff is not None and not canonical_relation_handoff.evidence_current:
            findings.append(
                ArchitectureReductionFinding(
                    "candidate_relation_evidence_stale",
                    "candidate canonical relation provenance is stale",
                    candidate_id=candidate.candidate_id,
                    metadata=canonical_relation_handoff.to_dict(),
                )
            )
        for gap_id in canonical_relation_handoff.gap_ids if canonical_relation_handoff else ():
            findings.append(
                ArchitectureReductionFinding(
                    "candidate_canonical_relation_gap_unresolved",
                    "candidate relation provenance contains an unresolved gap",
                    candidate_id=candidate.candidate_id,
                    item_id=gap_id,
                    metadata=canonical_relation_handoff.to_dict(),
                )
            )
        retained_facade = (
            candidate.candidate_type == CANDIDATE_KEEP_PUBLIC_FACADE
            or candidate.target_action == TARGET_ACTION_KEEP_FACADE
            or candidate.proof_status == PROOF_SAFE_BY_PUBLIC_FACADE
        )
        if retained_facade:
            missing_authority = tuple(
                field_name
                for field_name in (
                    "business_intent_id",
                    "behavior_commitment_id",
                    "primary_path_id",
                    "owner_code_contract_id",
                    "delegates_to_code_contract_id",
                    "delegates_to_primary_path_id",
                    "delegation_evidence_id",
                )
                if not getattr(candidate, field_name)
            )
            if missing_authority:
                findings.append(
                    ArchitectureReductionFinding(
                        "facade_delegation_contract_incomplete",
                        "retained facade lacks stable authority or delegation fields",
                        candidate_id=candidate.candidate_id,
                        metadata={"missing_fields": missing_authority},
                    )
                )
            if (
                candidate.delegates_to_code_contract_id != candidate.owner_code_contract_id
                or candidate.delegates_to_primary_path_id != candidate.primary_path_id
            ):
                findings.append(
                    ArchitectureReductionFinding(
                        "facade_delegation_target_mismatch",
                        "retained facade does not delegate to the selected owner contract and primary path",
                        candidate_id=candidate.candidate_id,
                        metadata=candidate.to_dict(),
                    )
                )
            if not candidate.delegation_evidence_current:
                findings.append(
                    ArchitectureReductionFinding(
                        "facade_delegation_evidence_stale",
                        "retained facade delegation evidence is missing or stale",
                        candidate_id=candidate.candidate_id,
                        metadata=candidate.to_dict(),
                    )
                )
            if not candidate.delegation_only or candidate.independent_business_authority:
                findings.append(
                    ArchitectureReductionFinding(
                        "facade_independent_business_authority",
                        "retained facade owns independent success or primary side-effect authority",
                        candidate_id=candidate.candidate_id,
                        metadata=candidate.to_dict(),
                    )
                )

        if (
            candidate.lifecycle_disposition == CANDIDATE_DISPOSITION_ACTIVE
            and candidate.touches_public_entrypoint()
            and candidate.required_next_route != ROUTE_STRUCTURE_MESH
        ):
            findings.append(
                ArchitectureReductionFinding(
                    "public_entrypoint_requires_structure_mesh",
                    "candidate affects public entrypoints and must route through StructureMesh",
                    candidate_id=candidate.candidate_id,
                    metadata={"affected_public_entrypoints": candidate.affected_public_entrypoints},
                )
            )

        for surface in linked_surfaces:
            if candidate.lifecycle_disposition != CANDIDATE_DISPOSITION_ACTIVE:
                continue
            if (
                candidate.target_action == TARGET_ACTION_RETIRE_BEHAVIOR
                and (
                    surface.classification
                    in {
                        COMPATIBILITY_SURFACE_CURRENT_CONTRACT,
                        COMPATIBILITY_SURFACE_BOUNDARY_ADAPTER,
                    }
                    or surface.recommended_action
                    in {COMPATIBILITY_ACTION_KEEP, COMPATIBILITY_ACTION_ADAPT}
                )
            ):
                compatibility_blocked_candidate_ids.add(candidate.candidate_id)
                findings.append(
                    ArchitectureReductionFinding(
                        "retirement_compatibility_surface_retained",
                        "retired behavior remains reachable through a current contract, boundary adapter, keep action, or adapt action",
                        candidate_id=candidate.candidate_id,
                        item_id=surface.surface_id,
                        metadata=surface.to_dict(),
                    )
                )
            if (
                surface.classification == COMPATIBILITY_SURFACE_CURRENT_CONTRACT
                and candidate.target_action in {TARGET_ACTION_REMOVE, TARGET_ACTION_COLLAPSE}
            ):
                compatibility_blocked_candidate_ids.add(candidate.candidate_id)
                findings.append(
                    ArchitectureReductionFinding(
                        "compatibility_surface_current_contract_blocks_contraction",
                        "candidate removes or collapses a surface classified as a current contract",
                        candidate_id=candidate.candidate_id,
                        item_id=surface.surface_id,
                        metadata=surface.to_dict(),
                    )
                )
            if surface.public_entrypoints and candidate.required_next_route != ROUTE_STRUCTURE_MESH:
                compatibility_blocked_candidate_ids.add(candidate.candidate_id)
                findings.append(
                    ArchitectureReductionFinding(
                        "compatibility_surface_public_entrypoint_requires_structure_mesh",
                        "linked compatibility surface affects public entrypoints and must route through StructureMesh",
                        candidate_id=candidate.candidate_id,
                        item_id=surface.surface_id,
                        metadata=surface.to_dict(),
                    )
                )
            if (
                surface.classification == COMPATIBILITY_SURFACE_NEGATIVE_LEGACY_TEST
                and candidate.target_action == TARGET_ACTION_REMOVE
                and not surface.evidence_refs
                and not candidate.evidence_refs
            ):
                compatibility_blocked_candidate_ids.add(candidate.candidate_id)
                findings.append(
                    ArchitectureReductionFinding(
                        "compatibility_surface_negative_legacy_test_requires_evidence",
                        "candidate removes negative legacy test evidence without replacement evidence refs",
                        candidate_id=candidate.candidate_id,
                        item_id=surface.surface_id,
                        metadata=surface.to_dict(),
                    )
                )

        removed_observable_state = tuple(sorted(observable_state.intersection(candidate.affected_state)))
        if (
            candidate.lifecycle_disposition == CANDIDATE_DISPOSITION_ACTIVE
            and candidate.target_action
            in {TARGET_ACTION_REMOVE, TARGET_ACTION_RETIRE_BEHAVIOR}
            and removed_observable_state
            and not (
                candidate.target_action == TARGET_ACTION_RETIRE_BEHAVIOR
                and retirement_authorized
            )
        ):
            findings.append(
                ArchitectureReductionFinding(
                    "removes_observable_state",
                    "candidate removes state declared observable by the contract",
                    candidate_id=candidate.candidate_id,
                    metadata={"observable_state": removed_observable_state},
                )
            )

        touched_observable_side_effects = tuple(sorted(observable_side_effects.intersection(candidate.affected_side_effects)))
        if (
            candidate.lifecycle_disposition == CANDIDATE_DISPOSITION_ACTIVE
            and
            candidate.target_action
            in {
                TARGET_ACTION_REMOVE,
                TARGET_ACTION_COLLAPSE,
                TARGET_ACTION_RETIRE_BEHAVIOR,
            }
            and touched_observable_side_effects
            and not (
                candidate.proof_status == PROOF_SAFE_BY_EQUIVALENCE
                or (
                    candidate.target_action == TARGET_ACTION_RETIRE_BEHAVIOR
                    and retirement_authorized
                )
            )
        ):
            findings.append(
                ArchitectureReductionFinding(
                    "observable_side_effect_without_equivalence",
                    "candidate changes observable side-effect structure without full equivalence proof",
                    candidate_id=candidate.candidate_id,
                    metadata={"observable_side_effects": touched_observable_side_effects},
                )
            )

        if candidate.lifecycle_disposition != CANDIDATE_DISPOSITION_ACTIVE:
            if candidate.is_closed:
                completed_candidates.append(candidate.candidate_id)
            continue

        if candidate.proof_status == PROOF_PROPERTY_ONLY_SAFE:
            findings.append(
                ArchitectureReductionFinding(
                    "property_only_reduction",
                    "candidate only preserves declared properties, not full observable behavior",
                    severity="warning",
                    candidate_id=candidate.candidate_id,
                )
            )
        elif candidate.proof_status == PROOF_NEEDS_CONFORMANCE_REPLAY:
            findings.append(
                ArchitectureReductionFinding(
                    "conformance_replay_required",
                    "candidate needs conformance replay before it can support code contraction",
                    candidate_id=candidate.candidate_id,
                )
            )
        elif candidate.proof_status == PROOF_RISKY_KEEP:
            findings.append(
                ArchitectureReductionFinding(
                    "risky_candidate_kept",
                    "candidate looks reducible but must be kept unless stronger evidence is added",
                    severity="warning",
                    candidate_id=candidate.candidate_id,
                )
            )
        elif candidate.proof_status == PROOF_BLOCKED_BY_MISSING_EVIDENCE:
            findings.append(
                ArchitectureReductionFinding(
                    "blocked_by_missing_evidence",
                    "candidate lacks enough evidence for architecture contraction",
                    candidate_id=candidate.candidate_id,
                )
            )

        if (
            candidate.target_action == TARGET_ACTION_RETIRE_BEHAVIOR
            and (
                pre_candidate_blocked
                or _blockers(findings[candidate_finding_start:])
            )
        ):
            retirement_blocked_candidate_ids.add(candidate.candidate_id)

        if (
            candidate.is_ready
            and candidate.candidate_id not in compatibility_blocked_candidate_ids
            and candidate.candidate_id not in retirement_blocked_candidate_ids
            and candidate.candidate_id not in step_blocked_candidate_ids
        ):
            ready_candidates.append(candidate.candidate_id)
            target_actions.append(_target_action_from_candidate(candidate))

    if plan.target_structure is not None:
        structure_report = review_code_structure_recommendation(plan.target_structure)
        if not structure_report.ok:
            for structure_finding in structure_report.findings:
                findings.append(
                    ArchitectureReductionFinding(
                        "target_structure_blocked",
                        f"target structure recommendation is blocked: {structure_finding.code}",
                        item_id=structure_finding.item_id,
                        metadata=structure_finding.to_dict(),
                    )
                )

    decision = _decision_for_findings(
        findings,
        candidate_count=len(plan.candidates),
        active_count=sum(
            1 for candidate in plan.candidates if candidate.lifecycle_disposition == CANDIDATE_DISPOSITION_ACTIVE
        ),
        completed_count=len(completed_candidates),
        ready_count=len(ready_candidates),
    )
    blockers = _blockers(findings)
    return ArchitectureReductionReport(
        ok=not blockers,
        reduction_id=plan.reduction_id,
        decision=decision,
        findings=tuple(findings),
        ready_candidate_ids=tuple(ready_candidates),
        completed_candidate_ids=tuple(completed_candidates),
        target_actions=tuple(target_actions),
        required_next_routes=tuple(sorted(required_routes)),
        compatibility_surfaces=plan.compatibility_surfaces,
        inventory_revision=plan.inventory_revision,
        covered_candidate_ids=inventory_values[1],
        scoped_candidate_ids=inventory_values[2],
        missing_candidate_ids=inventory_values[3],
        unexpected_candidate_ids=inventory_values[4],
        materialized_relation_ids=relation_values[1],
        materialized_relation_code_obligation_ids=relation_values[2],
        step_assessments=plan.step_assessments,
        cost_priority_step_ids=tuple(
            row.step_id
            for row in sorted(
                plan.step_assessments,
                key=lambda item: (item.cost_priority_key, item.step_id),
                reverse=True,
            )
            if row.cost_evidence
        ),
    )


__all__ = [
    "ARCHITECTURE_RETIREMENT_DISPOSITIONS",
    "ARCHITECTURE_RETIREMENT_GOVERNED_IDENTITY_ROLES",
    "ARCHITECTURE_RETIREMENT_OWNER_STATUSES",
    "ARCHITECTURE_RETIREMENT_PROOF_SCHEMA",
    "ARCHITECTURE_RETIREMENT_REQUIRED_ROUTES",
    "ARCHITECTURE_RETIREMENT_RESPONSIBILITY_DISPOSITION_SCHEMA",
    "ARCHITECTURE_RETIREMENT_RESPONSIBILITY_KINDS",
    "ARCHITECTURE_REDUCTION_CANDIDATE_TYPES",
    "ARCHITECTURE_REDUCTION_CANDIDATE_DISPOSITIONS",
    "ARCHITECTURE_REDUCTION_COMPANION_ROUTES",
    "ARCHITECTURE_REDUCTION_PROOF_STATUSES",
    "ARCHITECTURE_REDUCTION_ROUTE",
    "ARCHITECTURE_REDUCTION_TARGET_ACTIONS",
    "ARCHITECTURE_REDUCTION_STEP_ACTIONS",
    "ARCHITECTURE_REDUCTION_STEP_ASSESSMENT_SCHEMA",
    "ARCHITECTURE_REDUCTION_STEP_COST_SCHEMA",
    "ARCHITECTURE_REDUCTION_STEP_KINDS",
    "COMPATIBILITY_ACTION_ADAPT",
    "COMPATIBILITY_ACTION_ARCHIVE",
    "COMPATIBILITY_ACTION_COLLECT_EVIDENCE",
    "COMPATIBILITY_ACTION_KEEP",
    "COMPATIBILITY_ACTION_PRUNE",
    "COMPATIBILITY_ACTION_REJECT",
    "COMPATIBILITY_SURFACE_ARCHIVE_ONLY",
    "COMPATIBILITY_SURFACE_BOUNDARY_ADAPTER",
    "COMPATIBILITY_SURFACE_CLASSIFICATIONS",
    "COMPATIBILITY_SURFACE_CURRENT_CONTRACT",
    "COMPATIBILITY_SURFACE_EVIDENCE_NEEDED",
    "COMPATIBILITY_SURFACE_NEGATIVE_LEGACY_TEST",
    "COMPATIBILITY_SURFACE_PRUNE_CANDIDATE",
    "COMPATIBILITY_SURFACE_RECOMMENDED_ACTIONS",
    "CANDIDATE_COLLAPSE_ADAPTER",
    "CANDIDATE_DISPOSITION_ACTIVE",
    "CANDIDATE_DISPOSITION_COMPLETED",
    "CANDIDATE_DISPOSITION_HISTORICAL",
    "CANDIDATE_KEEP_PUBLIC_FACADE",
    "CANDIDATE_MANUAL_REVIEW",
    "CANDIDATE_MERGE_HANDLERS",
    "CANDIDATE_MERGE_MODULES",
    "CANDIDATE_MERGE_STATE_PHASE",
    "CANDIDATE_REMOVE_BRANCH",
    "CANDIDATE_REMOVE_DUPLICATE_VALIDATION",
    "CANDIDATE_REMOVE_STATE_FIELD",
    "FORBIDDEN_RETIREMENT_DISPOSITIONS",
    "PROOF_BLOCKED_BY_MISSING_EVIDENCE",
    "PROOF_AUTHORIZED_RETIREMENT",
    "PROOF_NEEDS_CONFORMANCE_REPLAY",
    "PROOF_PROPERTY_ONLY_SAFE",
    "PROOF_RISKY_KEEP",
    "PROOF_SAFE_BY_EQUIVALENCE",
    "PROOF_SAFE_BY_PUBLIC_FACADE",
    "READY_PROOF_STATUSES",
    "RETIREMENT_DISPOSITION_MIGRATE",
    "RETIREMENT_DISPOSITION_REPLACE",
    "RETIREMENT_DISPOSITION_RETAIN_HISTORY",
    "RETIREMENT_DISPOSITION_RETIRE",
    "RETIREMENT_OWNER_STATUS_EXACT_CURRENT",
    "RETIREMENT_OWNER_STATUS_NOT_APPLICABLE",
    "RETIREMENT_RESPONSIBILITY_BEHAVIOR",
    "RETIREMENT_RESPONSIBILITY_CODE",
    "RETIREMENT_RESPONSIBILITY_COMMITMENT",
    "RETIREMENT_RESPONSIBILITY_CONSUMER",
    "RETIREMENT_RESPONSIBILITY_MODEL",
    "RETIREMENT_RESPONSIBILITY_NEGATIVE_CASE",
    "RETIREMENT_RESPONSIBILITY_PROMPT",
    "RETIREMENT_RESPONSIBILITY_PUBLIC_SURFACE",
    "RETIREMENT_RESPONSIBILITY_RELEASE_CLAIM",
    "RETIREMENT_RESPONSIBILITY_ROUTE",
    "RETIREMENT_RESPONSIBILITY_SKILL",
    "RETIREMENT_RESPONSIBILITY_TEST",
    "RETIREMENT_RESPONSIBILITY_TOPOLOGY_RELATION",
    "ROUTE_CODE_STRUCTURE_RECOMMENDATION",
    "ROUTE_CONFORMANCE_REPLAY",
    "ROUTE_DEVELOPMENT_PROCESS_FLOW",
    "ROUTE_EXISTING_MODEL_PREFLIGHT",
    "ROUTE_MANUAL_REVIEW",
    "ROUTE_MODEL_MESH",
    "ROUTE_MODEL_TEST_ALIGNMENT",
    "ROUTE_STRUCTURE_MESH",
    "ROUTE_UI_FLOW_STRUCTURE",
    "TARGET_ACTION_COLLAPSE",
    "TARGET_ACTION_KEEP_FACADE",
    "TARGET_ACTION_MANUAL_REVIEW",
    "TARGET_ACTION_MERGE",
    "TARGET_ACTION_REMOVE",
    "TARGET_ACTION_RETIRE_BEHAVIOR",
    "STEP_ACTION_DELEGATE",
    "STEP_ACTION_EXPLICIT_ON_DEMAND",
    "STEP_ACTION_MERGE",
    "STEP_ACTION_REMOVE",
    "STEP_ACTION_RETAIN",
    "STEP_ACTION_UNRESOLVED",
    "STEP_KIND_ADAPTER",
    "STEP_KIND_BRANCH",
    "STEP_KIND_BUILDER",
    "STEP_KIND_EVIDENCE_PROJECTION",
    "STEP_KIND_HELPER",
    "STEP_KIND_MODULE_BOUNDARY",
    "STEP_KIND_OTHER",
    "STEP_KIND_PAYLOAD_MATERIALIZATION",
    "STEP_KIND_REFLECTION",
    "STEP_KIND_ROUTE_DISPATCH",
    "STEP_KIND_SCAN",
    "STEP_KIND_SERIALIZATION",
    "STEP_KIND_VALIDATION",
    "ArchitectureRetirementProof",
    "ArchitectureReductionCandidate",
    "ArchitectureReductionFinding",
    "ArchitectureReductionPlan",
    "ArchitectureReductionReport",
    "ArchitectureReductionStepAssessment",
    "ArchitectureReductionStepCost",
    "ArchitectureReductionTrigger",
    "CompatibilitySurfaceClassification",
    "ObservableArchitectureContract",
    "RetirementResponsibilityDisposition",
    "TargetArchitectureAction",
    "review_architecture_reduction",
]
