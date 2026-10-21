"""Model-backed architecture reduction review helpers.

Architecture reduction reviews whether a modeled flow can support simpler code
structure. Ordinary contraction must preserve declared observable behavior;
intentional retirement may change behavior only through one complete current
retirement proof. The review reports actions and handoff requirements; it does
not rewrite production code.
"""

from __future__ import annotations

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
    materialized_relation_ids: tuple[str, ...] = ()
    materialized_relation_code_obligation_ids: tuple[str, ...] = ()
    owner_code_contract_id: str = ""
    delegates_to_code_contract_id: str = ""
    delegates_to_primary_path_id: str = ""
    delegation_evidence_id: str = ""
    delegation_evidence_current: bool = False
    delegation_only: bool = False
    independent_business_authority: bool = False
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
            "materialized_relation_ids": list(self.materialized_relation_ids),
            "materialized_relation_code_obligation_ids": list(self.materialized_relation_code_obligation_ids),
            "owner_code_contract_id": self.owner_code_contract_id,
            "delegates_to_code_contract_id": self.delegates_to_code_contract_id,
            "delegates_to_primary_path_id": self.delegates_to_primary_path_id,
            "delegation_evidence_id": self.delegation_evidence_id,
            "delegation_evidence_current": self.delegation_evidence_current,
            "delegation_only": self.delegation_only,
            "independent_business_authority": self.independent_business_authority,
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

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", str(self.candidate_id))
        object.__setattr__(self, "action", str(self.action))
        object.__setattr__(self, "code_node_id", str(self.code_node_id))
        object.__setattr__(self, "required_next_route", str(self.required_next_route))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "action": self.action,
            "code_node_id": self.code_node_id,
            "required_next_route": self.required_next_route,
            "rationale": self.rationale,
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
    canonical_relation_handoff: CanonicalRelationHandoff | Mapping[str, Any] | None = None
    scoped_relation_reasons: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reduction_id", str(self.reduction_id))
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "companion_route_triggers", tuple(self.companion_route_triggers))
        object.__setattr__(self, "compatibility_surfaces", tuple(self.compatibility_surfaces))
        object.__setattr__(self, "rationale", str(self.rationale))
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "reduction_id": self.reduction_id,
            "observable_contract": self.observable_contract.to_dict(),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "companion_route_triggers": [trigger.to_dict() for trigger in self.companion_route_triggers],
            "compatibility_surfaces": [surface.to_dict() for surface in self.compatibility_surfaces],
            "target_structure": self.target_structure.to_dict() if self.target_structure else None,
            "rationale": self.rationale,
            "canonical_relation_handoff": self.canonical_relation_handoff.to_dict() if self.canonical_relation_handoff else None,
            "scoped_relation_reasons": to_jsonable(dict(self.scoped_relation_reasons)),
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
    materialized_relation_ids: tuple[str, ...] = ()
    materialized_relation_code_obligation_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "reduction_id", str(self.reduction_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "ready_candidate_ids", _as_tuple(self.ready_candidate_ids))
        object.__setattr__(self, "completed_candidate_ids", _as_tuple(self.completed_candidate_ids))
        object.__setattr__(self, "target_actions", tuple(self.target_actions))
        object.__setattr__(self, "required_next_routes", _as_tuple(self.required_next_routes))
        object.__setattr__(self, "compatibility_surfaces", tuple(self.compatibility_surfaces))
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
                lines.append(f"  - {action.action} {action.code_node_id}"
                             + (f" via {action.required_next_route}" if action.required_next_route else ""))
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
            "materialized_relation_ids": list(self.materialized_relation_ids),
            "materialized_relation_code_obligation_ids": list(self.materialized_relation_code_obligation_ids),
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
            ("completed_candidate_missing_evidence", "completed_candidate_blocked"),
            ("missing_required_next_route", "candidate_blocked"),
            ("public_entrypoint_requires_structure_mesh", "structure_mesh_required"),
            ("compatibility_surface_current_contract_blocks_contraction", "compatibility_surface_blocked"),
            ("retirement_compatibility_surface_retained", "compatibility_surface_blocked"),
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
    )


def _surfaces_by_candidate(
    surfaces: Sequence[CompatibilitySurfaceClassification],
) -> dict[str, tuple[CompatibilitySurfaceClassification, ...]]:
    grouped: dict[str, list[CompatibilitySurfaceClassification]] = {}
    for surface in surfaces:
        for candidate_id in surface.candidate_ids:
            grouped.setdefault(candidate_id, []).append(surface)
    return {candidate_id: tuple(items) for candidate_id, items in grouped.items()}


def _candidate_anchor_findings(plan: ArchitectureReductionPlan, project_root: str) -> list[ArchitectureReductionFinding]:
    from pathlib import Path

    from .map.check import anchor_problem
    from .map.inventory import Inventory, parse_python

    root = Path(project_root)
    paths = sorted({candidate.code_node_id.partition(":")[0] for candidate in plan.candidates if candidate.code_node_id})
    parsed = {path: parse_python(root, path, path[:-3].replace("/", "."), collect_bodies=False)
              for path in paths if path.endswith(".py") and (root / path).is_file()}
    inv = Inventory(root, paths, paths, [], parsed, {}, {})
    findings: list[ArchitectureReductionFinding] = []
    for candidate in plan.candidates:
        problem = anchor_problem(root, inv, candidate.code_node_id) if candidate.code_node_id else None
        if problem:
            findings.append(
                ArchitectureReductionFinding(
                    "candidate_anchor_missing",
                    problem,
                    candidate_id=candidate.candidate_id,
                    item_id=candidate.code_node_id,
                )
            )
    return findings


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


def review_architecture_reduction(
    plan: ArchitectureReductionPlan, project_root: str | None = None
) -> ArchitectureReductionReport:
    """Review whether modeled flow evidence supports code architecture contraction.

    With ``project_root`` every candidate ``code_node_id`` must name real code (``path.py:Symbol``).
    """

    findings: list[ArchitectureReductionFinding] = []
    ready_candidates: list[str] = []
    completed_candidates: list[str] = []
    target_actions: list[TargetArchitectureAction] = []
    required_routes: set[str] = set()
    compatibility_blocked_candidate_ids: set[str] = set()
    retirement_blocked_candidate_ids: set[str] = set()
    surfaces_by_candidate = _surfaces_by_candidate(plan.compatibility_surfaces)
    if project_root is not None:
        findings.extend(_candidate_anchor_findings(plan, project_root))
    relation_values = _plan_canonical_relation_findings(plan)
    findings.extend(relation_values[0])

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
        if candidate.required_next_route and candidate.required_next_route not in ARCHITECTURE_REDUCTION_COMPANION_ROUTES:
            findings.append(
                ArchitectureReductionFinding(
                    "missing_required_next_route",
                    "candidate does not name a recognized next route",
                    candidate_id=candidate.candidate_id,
                    item_id=candidate.required_next_route,
                )
            )
        elif candidate.required_next_route and candidate.lifecycle_disposition == CANDIDATE_DISPOSITION_ACTIVE:
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
            and candidate.proof_status != PROOF_SAFE_BY_EQUIVALENCE
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
        materialized_relation_ids=relation_values[1],
        materialized_relation_code_obligation_ids=relation_values[2],
    )


__all__ = [
    "ARCHITECTURE_REDUCTION_CANDIDATE_TYPES",
    "ARCHITECTURE_REDUCTION_CANDIDATE_DISPOSITIONS",
    "ARCHITECTURE_REDUCTION_COMPANION_ROUTES",
    "ARCHITECTURE_REDUCTION_PROOF_STATUSES",
    "ARCHITECTURE_REDUCTION_ROUTE",
    "ARCHITECTURE_REDUCTION_TARGET_ACTIONS",
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
    "PROOF_BLOCKED_BY_MISSING_EVIDENCE",
    "PROOF_AUTHORIZED_RETIREMENT",
    "PROOF_NEEDS_CONFORMANCE_REPLAY",
    "PROOF_PROPERTY_ONLY_SAFE",
    "PROOF_RISKY_KEEP",
    "PROOF_SAFE_BY_EQUIVALENCE",
    "PROOF_SAFE_BY_PUBLIC_FACADE",
    "READY_PROOF_STATUSES",
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
    "ArchitectureReductionCandidate",
    "ArchitectureReductionFinding",
    "ArchitectureReductionPlan",
    "ArchitectureReductionReport",
    "ArchitectureReductionTrigger",
    "CompatibilitySurfaceClassification",
    "ObservableArchitectureContract",
    "TargetArchitectureAction",
    "review_architecture_reduction",
]
