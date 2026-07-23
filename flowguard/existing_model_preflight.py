"""Existing FlowGuard model preflight helpers.

Existing-model preflight is a companion review before an agent discusses,
proposes, or modifies behavior in an existing modeled system. It does not
replace downstream routes such as ModelMesh, StructureMesh, UI Flow Structure,
or Model-Miss Review. It checks that the agent first grounded its reasoning in
the model map that already exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .behavior_commitment import (
    BCL_BEHAVIOR_PLANES,
    BCL_HIT_ROLE_PRIMARY,
    BCL_LOOKUP_STATUSES,
    BCL_LOOKUP_STATUS_BLOCKED,
    BCL_LOOKUP_STATUS_FALLBACK,
    BCL_LOOKUP_STATUS_NOT_APPLICABLE,
    BCL_LOOKUP_STATUS_PERFORMED,
)
from .behavior_commitment_lookup import (
    BehaviorCommitmentHit,
    BehaviorLookupQuery,
    query_behavior_commitments_from_path,
)
from .behavior_plane import BCL_PLANE_DEVELOPMENT_PROCESS
from .export import to_jsonable
from .model_angle_deliberation import (
    MODEL_ANGLE_CONFIDENCE_BLOCKED,
    MODEL_ANGLE_CONFIDENCE_SCOPED,
    ModelAngleDeliberation,
    review_model_angle_deliberations,
)
from .model_similarity import SimilarityHandoff, normalize_similarity_handoff
from .model_authority_store import (
    audit_model_authority,
    load_observed_model_system,
)


PREFLIGHT_MODE_LIGHT = "light"
PREFLIGHT_MODE_FULL = "full"
PREFLIGHT_MODES = {PREFLIGHT_MODE_LIGHT, PREFLIGHT_MODE_FULL}

REUSE_DECISION_REUSE_EXISTING = "reuse_existing"
REUSE_DECISION_EXTEND_EXISTING = "extend_existing"
REUSE_DECISION_ADD_CHILD_MODEL = "add_child_model"
REUSE_DECISION_NEW_BOUNDARY = "new_boundary"
REUSE_DECISION_NO_MODEL_FOUND = "no_model_found"
REUSE_DECISION_SKIP = "skip_with_reason"
REUSE_DECISIONS = {
    REUSE_DECISION_REUSE_EXISTING,
    REUSE_DECISION_EXTEND_EXISTING,
    REUSE_DECISION_ADD_CHILD_MODEL,
    REUSE_DECISION_NEW_BOUNDARY,
    REUSE_DECISION_NO_MODEL_FOUND,
    REUSE_DECISION_SKIP,
}

DUPLICATE_RISK_RESOLUTIONS = {
    "reuse_existing",
    "extend_existing",
    "new_boundary_rationale",
    "out_of_scope",
    "blocked",
}

PREFLIGHT_SURFACE_KINDS = {
    "ui",
    "api",
    "cli",
    "alias",
    "adapter",
    "wrapper",
    "helper",
    "compatibility",
}


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


def _as_pairs(values: Sequence[tuple[str, str]] | None) -> tuple[tuple[str, str], ...]:
    if values is None:
        return ()
    return tuple((str(left), str(right)) for left, right in values)


@dataclass(frozen=True)
class ModelContextHit:
    """One existing model that may own part of the requested change."""

    model_id: str
    model_path: str = ""
    evidence_id: str = ""
    evidence_tier: str = "candidate_only"
    evidence_current: bool = True
    responsibilities: tuple[str, ...] = ()
    function_blocks: tuple[str, ...] = ()
    state_owned: tuple[str, ...] = ()
    side_effects_owned: tuple[str, ...] = ()
    public_entrypoints: tuple[str, ...] = ()
    fields_owned: tuple[str, ...] = ()
    parent_model_id: str = ""
    child_model_ids: tuple[str, ...] = ()
    layered_proof_evidence_id: str = ""
    parent_coverage_status: str = ""
    child_disjointness_status: str = ""
    child_reattachment_status: str = ""
    leaf_boundary_matrix_status: str = ""
    validation_evidence: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "model_path", str(self.model_path))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "evidence_tier", str(self.evidence_tier))
        object.__setattr__(self, "responsibilities", _as_tuple(self.responsibilities))
        object.__setattr__(self, "function_blocks", _as_tuple(self.function_blocks))
        object.__setattr__(self, "state_owned", _as_tuple(self.state_owned))
        object.__setattr__(self, "side_effects_owned", _as_tuple(self.side_effects_owned))
        object.__setattr__(self, "public_entrypoints", _as_tuple(self.public_entrypoints))
        object.__setattr__(self, "fields_owned", _as_tuple(self.fields_owned))
        object.__setattr__(self, "parent_model_id", str(self.parent_model_id))
        object.__setattr__(self, "child_model_ids", _as_tuple(self.child_model_ids))
        object.__setattr__(self, "layered_proof_evidence_id", str(self.layered_proof_evidence_id))
        object.__setattr__(self, "parent_coverage_status", str(self.parent_coverage_status))
        object.__setattr__(self, "child_disjointness_status", str(self.child_disjointness_status))
        object.__setattr__(self, "child_reattachment_status", str(self.child_reattachment_status))
        object.__setattr__(self, "leaf_boundary_matrix_status", str(self.leaf_boundary_matrix_status))
        object.__setattr__(self, "validation_evidence", _as_tuple(self.validation_evidence))
        object.__setattr__(self, "rationale", str(self.rationale))

    def has_ownership_evidence(self) -> bool:
        return bool(
            self.function_blocks
            or self.state_owned
            or self.side_effects_owned
            or self.public_entrypoints
            or self.fields_owned
            or self.responsibilities
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_path": self.model_path,
            "evidence_id": self.evidence_id,
            "evidence_tier": self.evidence_tier,
            "evidence_current": self.evidence_current,
            "responsibilities": list(self.responsibilities),
            "function_blocks": list(self.function_blocks),
            "state_owned": list(self.state_owned),
            "side_effects_owned": list(self.side_effects_owned),
            "public_entrypoints": list(self.public_entrypoints),
            "fields_owned": list(self.fields_owned),
            "parent_model_id": self.parent_model_id,
            "child_model_ids": list(self.child_model_ids),
            "layered_proof_evidence_id": self.layered_proof_evidence_id,
            "parent_coverage_status": self.parent_coverage_status,
            "child_disjointness_status": self.child_disjointness_status,
            "child_reattachment_status": self.child_reattachment_status,
            "leaf_boundary_matrix_status": self.leaf_boundary_matrix_status,
            "validation_evidence": list(self.validation_evidence),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ExistingOwnershipSnapshot:
    """Ownership summary extracted from existing FlowGuard model hits."""

    function_block_owners: tuple[tuple[str, str], ...] = ()
    state_owners: tuple[tuple[str, str], ...] = ()
    side_effect_owners: tuple[tuple[str, str], ...] = ()
    public_entrypoint_owners: tuple[tuple[str, str], ...] = ()
    field_owners: tuple[tuple[str, str], ...] = ()
    responsibility_owners: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "function_block_owners", _as_pairs(self.function_block_owners))
        object.__setattr__(self, "state_owners", _as_pairs(self.state_owners))
        object.__setattr__(self, "side_effect_owners", _as_pairs(self.side_effect_owners))
        object.__setattr__(self, "public_entrypoint_owners", _as_pairs(self.public_entrypoint_owners))
        object.__setattr__(self, "field_owners", _as_pairs(self.field_owners))
        object.__setattr__(self, "responsibility_owners", _as_pairs(self.responsibility_owners))

    def has_any(self) -> bool:
        return bool(
            self.function_block_owners
            or self.state_owners
            or self.side_effect_owners
            or self.public_entrypoint_owners
            or self.field_owners
            or self.responsibility_owners
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "function_block_owners": [list(pair) for pair in self.function_block_owners],
            "state_owners": [list(pair) for pair in self.state_owners],
            "side_effect_owners": [list(pair) for pair in self.side_effect_owners],
            "public_entrypoint_owners": [list(pair) for pair in self.public_entrypoint_owners],
            "field_owners": [list(pair) for pair in self.field_owners],
            "responsibility_owners": [list(pair) for pair in self.responsibility_owners],
        }


@dataclass(frozen=True)
class DuplicateBoundaryRisk:
    """A proposed boundary overlaps an existing model responsibility."""

    item_type: str
    item_id: str
    existing_owner_id: str
    proposed_owner_id: str = ""
    resolution: str = ""
    rationale: str = ""
    resolved: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_type", str(self.item_type))
        object.__setattr__(self, "item_id", str(self.item_id))
        object.__setattr__(self, "existing_owner_id", str(self.existing_owner_id))
        object.__setattr__(self, "proposed_owner_id", str(self.proposed_owner_id))
        object.__setattr__(self, "resolution", str(self.resolution))
        object.__setattr__(self, "rationale", str(self.rationale))

    def is_resolved(self) -> bool:
        if self.resolved:
            return True
        return self.resolution in DUPLICATE_RISK_RESOLUTIONS and bool(self.rationale)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_type": self.item_type,
            "item_id": self.item_id,
            "existing_owner_id": self.existing_owner_id,
            "proposed_owner_id": self.proposed_owner_id,
            "resolution": self.resolution,
            "rationale": self.rationale,
            "resolved": self.resolved,
        }


@dataclass(frozen=True)
class ExistingIntentSurface:
    """One affected surface materialized for an exact business intent."""

    surface_id: str
    surface_kind: str = ""
    business_intent_id: str = ""
    behavior_commitment_id: str = ""
    business_path_id: str = ""
    primary_path_id: str = ""
    expected_terminal: str = ""
    state_writes: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
    owner_id: str = ""
    source_ref: str = ""
    evidence_ids: tuple[str, ...] = ()
    evidence_current: bool = True
    similarity_relation_ids: tuple[str, ...] = ()
    in_scope: bool = True
    disposition: str = "materialized"
    scoped_out_reason: str = ""
    validation_boundary: str = ""
    rationale: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "surface_id",
            "surface_kind",
            "business_intent_id",
            "behavior_commitment_id",
            "business_path_id",
            "primary_path_id",
            "expected_terminal",
            "owner_id",
            "source_ref",
            "disposition",
            "scoped_out_reason",
            "validation_boundary",
            "rationale",
        ):
            object.__setattr__(self, field_name, str(getattr(self, field_name)))
        object.__setattr__(self, "state_writes", _as_tuple(self.state_writes))
        object.__setattr__(self, "side_effects", _as_tuple(self.side_effects))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))
        object.__setattr__(self, "similarity_relation_ids", _as_tuple(self.similarity_relation_ids))
        object.__setattr__(self, "in_scope", bool(self.in_scope))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def has_scoped_disposition(self) -> bool:
        return bool(
            not self.in_scope
            and self.disposition
            and self.scoped_out_reason
            and self.owner_id
            and self.validation_boundary
            and self.rationale
            and self.evidence_ids
        )

    def missing_material_fields(self) -> tuple[str, ...]:
        if not self.in_scope:
            return ()
        required = (
            "surface_id",
            "surface_kind",
            "business_intent_id",
            "behavior_commitment_id",
            "business_path_id",
            "primary_path_id",
            "expected_terminal",
            "owner_id",
        )
        missing = [field_name for field_name in required if not getattr(self, field_name)]
        if not self.evidence_ids:
            missing.append("evidence_ids")
        return tuple(missing)

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface_id": self.surface_id,
            "surface_kind": self.surface_kind,
            "business_intent_id": self.business_intent_id,
            "behavior_commitment_id": self.behavior_commitment_id,
            "business_path_id": self.business_path_id,
            "primary_path_id": self.primary_path_id,
            "expected_terminal": self.expected_terminal,
            "state_writes": list(self.state_writes),
            "side_effects": list(self.side_effects),
            "owner_id": self.owner_id,
            "source_ref": self.source_ref,
            "evidence_ids": list(self.evidence_ids),
            "evidence_current": self.evidence_current,
            "similarity_relation_ids": list(self.similarity_relation_ids),
            "in_scope": self.in_scope,
            "disposition": self.disposition,
            "scoped_out_reason": self.scoped_out_reason,
            "validation_boundary": self.validation_boundary,
            "rationale": self.rationale,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ExistingModelPreflight:
    """A light or full report grounding work in existing FlowGuard models."""

    preflight_id: str
    task_summary: str
    mode: str = PREFLIGHT_MODE_FULL
    existing_modeled_system: bool = True
    authority_required: bool = False
    authority_status: str = "not_checked"
    authority_snapshot_fingerprint: str = ""
    authority_subject_revision: str = ""
    authority_gap_ids: tuple[str, ...] = ()
    model_search_performed: bool = False
    search_paths: tuple[str, ...] = ()
    behavior_lookup_required: bool = False
    behavior_lookup_status: str = BCL_LOOKUP_STATUS_NOT_APPLICABLE
    primary_behavior_plane: str = ""
    primary_commitment_hits: tuple[BehaviorCommitmentHit | Mapping[str, Any], ...] = ()
    related_commitment_hits: tuple[BehaviorCommitmentHit | Mapping[str, Any], ...] = ()
    candidate_commitment_hits: tuple[BehaviorCommitmentHit | Mapping[str, Any], ...] = ()
    plane_ambiguity: bool = False
    ledger_fingerprint: str = ""
    behavior_lookup_reason: str = ""
    relevant_models: tuple[ModelContextHit, ...] = ()
    ownership_snapshot: ExistingOwnershipSnapshot | None = None
    reuse_decision: str = ""
    downstream_routes: tuple[str, ...] = ()
    rationale: str = ""
    no_model_found_reason: str = ""
    proposed_new_boundaries: tuple[str, ...] = ()
    duplicate_risks: tuple[DuplicateBoundaryRisk, ...] = ()
    behavior_field_ids: tuple[str, ...] = ()
    field_lifecycle_required: bool = False
    field_lifecycle_model_ids: tuple[str, ...] = ()
    field_lifecycle_gap_ids: tuple[str, ...] = ()
    model_angle_review_required: bool = False
    model_angle_deliberations: tuple[ModelAngleDeliberation | Mapping[str, Any], ...] = ()
    model_angle_gap_ids: tuple[str, ...] = ()
    similarity_review_required: bool = False
    similarity_handoff: SimilarityHandoff | Mapping[str, Any] | None = None
    affected_business_intent_id: str = ""
    selected_commitment_id: str = ""
    selected_primary_path_id: str = ""
    expected_surface_ids: tuple[str, ...] = ()
    intent_surfaces: tuple[ExistingIntentSurface | Mapping[str, Any], ...] = ()
    surface_inventory_revision: str = ""
    surface_inventory_evidence_ids: tuple[str, ...] = ()
    typed_external_difference_ids: tuple[str, ...] = ()
    require_complete_surface_inventory: bool = False
    skip_reason: str = ""
    spec_context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "preflight_id", str(self.preflight_id))
        object.__setattr__(self, "task_summary", str(self.task_summary))
        object.__setattr__(self, "mode", str(self.mode))
        object.__setattr__(self, "authority_required", bool(self.authority_required))
        object.__setattr__(self, "authority_status", str(self.authority_status))
        object.__setattr__(
            self,
            "authority_snapshot_fingerprint",
            str(self.authority_snapshot_fingerprint),
        )
        object.__setattr__(
            self,
            "authority_subject_revision",
            str(self.authority_subject_revision),
        )
        object.__setattr__(
            self,
            "authority_gap_ids",
            _as_tuple(self.authority_gap_ids),
        )
        object.__setattr__(self, "search_paths", _as_tuple(self.search_paths))
        object.__setattr__(self, "behavior_lookup_required", bool(self.behavior_lookup_required))
        object.__setattr__(self, "behavior_lookup_status", str(self.behavior_lookup_status))
        object.__setattr__(self, "primary_behavior_plane", str(self.primary_behavior_plane))
        object.__setattr__(
            self,
            "primary_commitment_hits",
            tuple(
                item if isinstance(item, BehaviorCommitmentHit) else BehaviorCommitmentHit(**dict(item))
                for item in self.primary_commitment_hits
            ),
        )
        object.__setattr__(
            self,
            "related_commitment_hits",
            tuple(
                item if isinstance(item, BehaviorCommitmentHit) else BehaviorCommitmentHit(**dict(item))
                for item in self.related_commitment_hits
            ),
        )
        object.__setattr__(
            self,
            "candidate_commitment_hits",
            tuple(
                item if isinstance(item, BehaviorCommitmentHit) else BehaviorCommitmentHit(**dict(item))
                for item in self.candidate_commitment_hits
            ),
        )
        object.__setattr__(self, "plane_ambiguity", bool(self.plane_ambiguity))
        object.__setattr__(self, "ledger_fingerprint", str(self.ledger_fingerprint))
        object.__setattr__(self, "behavior_lookup_reason", str(self.behavior_lookup_reason))
        object.__setattr__(self, "relevant_models", tuple(self.relevant_models))
        object.__setattr__(self, "reuse_decision", str(self.reuse_decision))
        object.__setattr__(self, "downstream_routes", _as_tuple(self.downstream_routes))
        object.__setattr__(self, "rationale", str(self.rationale))
        object.__setattr__(self, "no_model_found_reason", str(self.no_model_found_reason))
        object.__setattr__(self, "proposed_new_boundaries", _as_tuple(self.proposed_new_boundaries))
        object.__setattr__(self, "duplicate_risks", tuple(self.duplicate_risks))
        object.__setattr__(self, "behavior_field_ids", _as_tuple(self.behavior_field_ids))
        object.__setattr__(self, "field_lifecycle_required", bool(self.field_lifecycle_required))
        object.__setattr__(self, "field_lifecycle_model_ids", _as_tuple(self.field_lifecycle_model_ids))
        object.__setattr__(self, "field_lifecycle_gap_ids", _as_tuple(self.field_lifecycle_gap_ids))
        object.__setattr__(self, "model_angle_review_required", bool(self.model_angle_review_required))
        object.__setattr__(
            self,
            "model_angle_deliberations",
            tuple(
                item
                if isinstance(item, ModelAngleDeliberation)
                else ModelAngleDeliberation(**item)
                for item in self.model_angle_deliberations
            ),
        )
        object.__setattr__(self, "model_angle_gap_ids", _as_tuple(self.model_angle_gap_ids))
        object.__setattr__(self, "similarity_handoff", normalize_similarity_handoff(self.similarity_handoff))
        object.__setattr__(self, "affected_business_intent_id", str(self.affected_business_intent_id))
        object.__setattr__(self, "selected_commitment_id", str(self.selected_commitment_id))
        object.__setattr__(self, "selected_primary_path_id", str(self.selected_primary_path_id))
        object.__setattr__(self, "expected_surface_ids", _as_tuple(self.expected_surface_ids))
        object.__setattr__(
            self,
            "intent_surfaces",
            tuple(
                item if isinstance(item, ExistingIntentSurface) else ExistingIntentSurface(**dict(item))
                for item in self.intent_surfaces
            ),
        )
        object.__setattr__(self, "surface_inventory_revision", str(self.surface_inventory_revision))
        object.__setattr__(self, "surface_inventory_evidence_ids", _as_tuple(self.surface_inventory_evidence_ids))
        object.__setattr__(self, "typed_external_difference_ids", _as_tuple(self.typed_external_difference_ids))
        object.__setattr__(self, "require_complete_surface_inventory", bool(self.require_complete_surface_inventory))
        object.__setattr__(self, "skip_reason", str(self.skip_reason))
        object.__setattr__(self, "spec_context", dict(self.spec_context))

    def to_dict(self) -> dict[str, Any]:
        return {
            "preflight_id": self.preflight_id,
            "task_summary": self.task_summary,
            "mode": self.mode,
            "existing_modeled_system": self.existing_modeled_system,
            "authority_required": self.authority_required,
            "authority_status": self.authority_status,
            "authority_snapshot_fingerprint": (
                self.authority_snapshot_fingerprint
            ),
            "authority_subject_revision": self.authority_subject_revision,
            "authority_gap_ids": list(self.authority_gap_ids),
            "model_search_performed": self.model_search_performed,
            "search_paths": list(self.search_paths),
            "behavior_lookup_required": self.behavior_lookup_required,
            "behavior_lookup_status": self.behavior_lookup_status,
            "primary_behavior_plane": self.primary_behavior_plane,
            "primary_commitment_hits": [hit.to_dict() for hit in self.primary_commitment_hits],
            "related_commitment_hits": [hit.to_dict() for hit in self.related_commitment_hits],
            "candidate_commitment_hits": [hit.to_dict() for hit in self.candidate_commitment_hits],
            "plane_ambiguity": self.plane_ambiguity,
            "ledger_fingerprint": self.ledger_fingerprint,
            "behavior_lookup_reason": self.behavior_lookup_reason,
            "relevant_models": [model.to_dict() for model in self.relevant_models],
            "ownership_snapshot": self.ownership_snapshot.to_dict()
            if self.ownership_snapshot
            else None,
            "reuse_decision": self.reuse_decision,
            "downstream_routes": list(self.downstream_routes),
            "rationale": self.rationale,
            "no_model_found_reason": self.no_model_found_reason,
            "proposed_new_boundaries": list(self.proposed_new_boundaries),
            "duplicate_risks": [risk.to_dict() for risk in self.duplicate_risks],
            "behavior_field_ids": list(self.behavior_field_ids),
            "field_lifecycle_required": self.field_lifecycle_required,
            "field_lifecycle_model_ids": list(self.field_lifecycle_model_ids),
            "field_lifecycle_gap_ids": list(self.field_lifecycle_gap_ids),
            "model_angle_review_required": self.model_angle_review_required,
            "model_angle_deliberations": [item.to_dict() for item in self.model_angle_deliberations],
            "model_angle_gap_ids": list(self.model_angle_gap_ids),
            "similarity_review_required": self.similarity_review_required,
            "similarity_handoff": self.similarity_handoff.to_dict()
            if self.similarity_handoff
            else None,
            "affected_business_intent_id": self.affected_business_intent_id,
            "selected_commitment_id": self.selected_commitment_id,
            "selected_primary_path_id": self.selected_primary_path_id,
            "expected_surface_ids": list(self.expected_surface_ids),
            "intent_surfaces": [surface.to_dict() for surface in self.intent_surfaces],
            "surface_inventory_revision": self.surface_inventory_revision,
            "surface_inventory_evidence_ids": list(self.surface_inventory_evidence_ids),
            "typed_external_difference_ids": list(self.typed_external_difference_ids),
            "require_complete_surface_inventory": self.require_complete_surface_inventory,
            "skip_reason": self.skip_reason,
            "spec_context": to_jsonable(dict(self.spec_context)),
        }


@dataclass(frozen=True)
class ExistingModelPreflightFinding:
    """One preflight review finding."""

    code: str
    message: str
    severity: str = "blocker"
    model_id: str = ""
    item_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "item_id", str(self.item_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "model_id": self.model_id,
            "item_id": self.item_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ExistingModelPreflightReport:
    """Structured outcome of an existing-model preflight review."""

    ok: bool
    preflight_id: str
    decision: str
    findings: tuple[ExistingModelPreflightFinding, ...] = ()
    covered_surface_ids: tuple[str, ...] = ()
    scoped_surface_ids: tuple[str, ...] = ()
    missing_surface_ids: tuple[str, ...] = ()
    business_intent_id: str = ""
    behavior_commitment_id: str = ""
    primary_path_id: str = ""
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "preflight_id", str(self.preflight_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "covered_surface_ids", _as_tuple(self.covered_surface_ids))
        object.__setattr__(self, "scoped_surface_ids", _as_tuple(self.scoped_surface_ids))
        object.__setattr__(self, "missing_surface_ids", _as_tuple(self.missing_surface_ids))
        object.__setattr__(self, "business_intent_id", str(self.business_intent_id))
        object.__setattr__(self, "behavior_commitment_id", str(self.behavior_commitment_id))
        object.__setattr__(self, "primary_path_id", str(self.primary_path_id))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: preflight={self.preflight_id} decision={self.decision} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard existing model preflight review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"preflight: {self.preflight_id}",
            f"decision: {self.decision}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"model: {finding.model_id or '(none)'}",
                    f"item: {finding.item_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "preflight_id": self.preflight_id,
            "decision": self.decision,
            "findings": [finding.to_dict() for finding in self.findings],
            "covered_surface_ids": list(self.covered_surface_ids),
            "scoped_surface_ids": list(self.scoped_surface_ids),
            "missing_surface_ids": list(self.missing_surface_ids),
            "business_intent_id": self.business_intent_id,
            "behavior_commitment_id": self.behavior_commitment_id,
            "primary_path_id": self.primary_path_id,
            "summary": self.summary,
        }


def _blocker_findings(
    findings: Sequence[ExistingModelPreflightFinding],
) -> tuple[ExistingModelPreflightFinding, ...]:
    return tuple(finding for finding in findings if finding.severity == "blocker")


def _has_ownership_evidence(preflight: ExistingModelPreflight) -> bool:
    if preflight.ownership_snapshot and preflight.ownership_snapshot.has_any():
        return True
    return any(model.has_ownership_evidence() for model in preflight.relevant_models)


def _missing_layered_status_fields(model: ModelContextHit) -> tuple[str, ...]:
    if not model.child_model_ids:
        return ()
    missing: list[str] = []
    for field_name in (
        "layered_proof_evidence_id",
        "parent_coverage_status",
        "child_disjointness_status",
        "child_reattachment_status",
        "leaf_boundary_matrix_status",
    ):
        if not getattr(model, field_name):
            missing.append(field_name)
    return tuple(missing)


def _decision_for_findings(
    preflight: ExistingModelPreflight,
    findings: Sequence[ExistingModelPreflightFinding],
) -> str:
    blockers = _blocker_findings(findings)
    if preflight.skip_reason and not blockers:
        return "preflight_skipped_with_reason"
    if blockers:
        codes = {finding.code for finding in blockers}
        if "missing_model_search" in codes:
            return "model_search_required"
        if "missing_ownership_evidence" in codes:
            return "ownership_snapshot_required"
        if "layered_proof_status_unknown" in codes:
            return "layered_proof_status_required"
        if "missing_field_lifecycle_ownership" in codes:
            return "field_lifecycle_ownership_required"
        if "field_lifecycle_gap_unresolved" in codes:
            return "field_lifecycle_gap_blocked"
        if any(code.startswith("model_angle_") for code in codes):
            return "model_angle_review_blocked"
        if "duplicate_boundary_risk_unresolved" in codes:
            return "duplicate_boundary_risk_blocked"
        if "new_boundary_without_rationale" in codes:
            return "new_boundary_rationale_required"
        if "no_model_found_reason_missing" in codes:
            return "no_model_found_requires_reason"
        if any(
            code.startswith(("surface_inventory_", "intent_surface_"))
            or code
            in {
                "missing_expected_intent_surface",
                "duplicate_intent_surface_id",
                "missing_stable_intent_identity",
                "missing_stable_commitment_identity",
                "missing_stable_primary_path_identity",
                "same_intent_new_boundary_without_external_difference",
                "unmaterialized_similarity_obligations",
            }
            for code in codes
        ):
            return "intent_surface_inventory_blocked"
        return "existing_model_preflight_blocked"
    if preflight.reuse_decision == REUSE_DECISION_NO_MODEL_FOUND:
        return "no_model_found_can_continue"
    if preflight.mode == PREFLIGHT_MODE_LIGHT:
        return "light_model_grounding_can_continue"
    return "full_existing_model_preflight_can_continue"


def _model_id_from_path(path: Path, root: Path) -> str:
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path
    parts = list(relative.parts)
    if len(parts) >= 3 and parts[0] == ".flowguard":
        return ":".join(parts[1:-1]) or path.stem
    return ":".join(parts[:-1] + [path.stem]) or path.stem


def _class_names(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(re.findall(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)\b", text, re.MULTILINE)))


def _purpose_lines(text: str, limit: int = 3) -> tuple[str, ...]:
    lines: list[str] = []
    capture = False
    for raw_line in text.splitlines():
        line = raw_line.strip().strip("#").strip()
        if not line:
            if capture:
                break
            continue
        lowered = line.lower()
        if lowered.startswith("purpose:"):
            capture = True
            value = line.split(":", 1)[1].strip()
            if value:
                lines.append(value)
            continue
        if capture:
            if lowered.startswith(("guards against:", "use before editing:", "run:")):
                break
            lines.append(line)
        if len(lines) >= limit:
            break
    return tuple(lines)


def _matches_changed_paths(path: Path, text: str, changed_paths: Sequence[str]) -> bool:
    if not changed_paths:
        return True
    haystack = f"{path.as_posix()}\n{text}".lower()
    return any(str(item).lower().replace("\\", "/") in haystack for item in changed_paths)


def _owner_model_path(root_path: Path, owner_model_id: str) -> str:
    owner = str(owner_model_id).replace("\\", "/")
    candidates: list[Path] = []
    if owner.endswith(".py") or "/" in owner:
        candidates.append(Path(owner))
    if owner.startswith("model:"):
        candidates.append(Path(".flowguard") / owner.split(":", 1)[1] / "model.py")
    for candidate in candidates:
        path = candidate if candidate.is_absolute() else root_path / candidate
        if path.exists():
            try:
                return str(path.relative_to(root_path))
            except ValueError:
                return str(path)
    return ""


def _lookup_model_hit(
    root_path: Path,
    hit: BehaviorCommitmentHit,
    *,
    ledger_path: Path,
) -> ModelContextHit | None:
    if not hit.primary_owner_model_id:
        return None
    relative_ledger = str(ledger_path)
    try:
        relative_ledger = str(ledger_path.relative_to(root_path))
    except ValueError:
        pass
    return ModelContextHit(
        model_id=hit.primary_owner_model_id,
        model_path=_owner_model_path(root_path, hit.primary_owner_model_id),
        evidence_id=f"behavior-ledger:{hit.commitment_id}",
        evidence_tier="canonical_behavior_commitment",
        evidence_current=True,
        responsibilities=(
            f"{hit.hit_role} commitment {hit.commitment_id} in {hit.behavior_plane}",
        ),
        validation_evidence=(relative_ledger,),
        rationale=(
            "Primary owner selected by plane-first commitment lookup."
            if hit.hit_role == BCL_HIT_ROLE_PRIMARY
            else "Related owner reached through a typed commitment relation."
        ),
    )


def existing_model_preflight_from_project(
    root: str | Path,
    task_summary: str,
    *,
    preflight_id: str = "",
    changed_paths: Sequence[str] = (),
    downstream_routes: Sequence[str] = (),
    mode: str = PREFLIGHT_MODE_FULL,
    behavior_plane: str = "",
    canonical_terms: Sequence[str] = (),
    tool_ids: Sequence[str] = (),
    error_signatures: Sequence[str] = (),
    workflow_families: Sequence[str] = (),
    ledger_path: str | Path = "",
) -> ExistingModelPreflight:
    """Create an ExistingModelPreflight input from lightweight project inventory.

    This helper collects likely model context only. Use
    `review_existing_model_preflight(...)` for the actual confidence decision.
    """

    root_path = Path(root)
    search_roots = tuple(
        path
        for path in (
            root_path / ".flowguard",
            root_path / "docs",
            root_path / "openspec",
        )
        if path.exists()
    )
    canonical_ledger_path = Path(ledger_path) if ledger_path else root_path / ".flowguard" / "behavior_commitment_ledger" / "ledger.json"
    if not canonical_ledger_path.is_absolute():
        canonical_ledger_path = root_path / canonical_ledger_path
    behavior_lookup_required = bool(ledger_path) or canonical_ledger_path.parent.exists()
    lookup_report = None
    if behavior_lookup_required:
        lookup_report = query_behavior_commitments_from_path(
            canonical_ledger_path,
            BehaviorLookupQuery(
                task_summary,
                primary_plane=behavior_plane,
                canonical_terms=tuple(canonical_terms),
                changed_paths=tuple(changed_paths),
                tool_ids=tuple(tool_ids),
                error_signatures=tuple(error_signatures),
                workflow_families=tuple(workflow_families),
            ),
        )
    searched_path_values = [
        str(path.relative_to(root_path) if path.is_relative_to(root_path) else path)
        for path in search_roots
    ]
    if behavior_lookup_required:
        try:
            searched_path_values.insert(0, str(canonical_ledger_path.relative_to(root_path)))
        except ValueError:
            searched_path_values.insert(0, str(canonical_ledger_path))
    searched_paths = tuple(dict.fromkeys(searched_path_values))
    authority_report = audit_model_authority(root_path)
    authority_status = authority_report.status
    authority_snapshot_fingerprint = ""
    authority_subject_revision = ""
    authority_gap_ids: tuple[str, ...] = ()
    hits: list[ModelContextHit] = []
    if authority_report.ok:
        _, authority_snapshot = load_observed_model_system(root_path)
        authority_snapshot_fingerprint = authority_snapshot.fingerprint
        authority_subject_revision = authority_snapshot.subject_revision
        authority_gap_ids = authority_snapshot.unresolved_gap_ids
        for instance in authority_snapshot.model_instances:
            model_path = root_path / instance.model_path
            model_text = (
                model_path.read_text(encoding="utf-8", errors="replace")
                if model_path.is_file()
                else ""
            )
            if changed_paths and not _matches_changed_paths(
                model_path,
                model_text,
                changed_paths,
            ):
                continue
            hits.append(
                ModelContextHit(
                    model_id=instance.logical_model_id,
                    model_path=instance.model_path,
                    evidence_id=(
                        f"model-authority:{instance.fingerprint}"
                    ),
                    evidence_tier="authoritative_observed",
                    evidence_current=True,
                    responsibilities=_purpose_lines(model_text)
                    or (instance.logical_model_id,),
                    function_blocks=_class_names(model_text),
                    validation_evidence=(
                        authority_snapshot.fingerprint,
                        instance.purpose_closure_fingerprint,
                    ),
                    rationale=(
                        "Selected from the sole observed model-system authority."
                    ),
                )
            )
    primary_lookup_hits = lookup_report.primary_hits if lookup_report else ()
    related_lookup_hits = lookup_report.related_hits if lookup_report else ()
    candidate_lookup_hits = lookup_report.candidate_hits if lookup_report else ()
    for lookup_hit in (*primary_lookup_hits, *related_lookup_hits):
        model_hit = _lookup_model_hit(root_path, lookup_hit, ledger_path=canonical_ledger_path)
        if model_hit is not None:
            hits.append(model_hit)
    seen_model_ids = {hit.model_id for hit in hits}
    seen_model_paths = {hit.model_path.replace("\\", "/") for hit in hits if hit.model_path}
    flowguard_root = root_path / ".flowguard"
    if flowguard_root.exists():
        for path in sorted(flowguard_root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "FlowGuard" not in text and "Workflow" not in text and "Invariant" not in text:
                continue
            if primary_lookup_hits and not changed_paths:
                continue
            if not _matches_changed_paths(path, text, changed_paths):
                continue
            model_id = _model_id_from_path(path, flowguard_root)
            classes = _class_names(text)
            responsibilities = _purpose_lines(text) or (model_id,)
            relative_path = str(path.relative_to(root_path))
            fields_owned = tuple(dict.fromkeys(re.findall(r"field:[A-Za-z0-9_.:-]+", text)))
            normalized_relative = relative_path.replace("\\", "/")
            if model_id in seen_model_ids or normalized_relative in seen_model_paths:
                continue
            hits.append(
                ModelContextHit(
                    model_id=model_id,
                    model_path=relative_path,
                    evidence_tier="project_inventory",
                    evidence_current=False,
                    responsibilities=responsibilities,
                    function_blocks=classes,
                    fields_owned=fields_owned,
                    validation_evidence=(relative_path,),
                    rationale=(
                        "Discovered from project files as candidate context; "
                        "it is not current authority evidence."
                    ),
                )
            )
            seen_model_ids.add(model_id)
            seen_model_paths.add(normalized_relative)

    ownership_snapshot = None
    if hits:
        ownership_snapshot = ExistingOwnershipSnapshot(
            function_block_owners=tuple(
                (block, hit.model_id)
                for hit in hits
                for block in hit.function_blocks
            ),
            responsibility_owners=tuple(
                (responsibility, hit.model_id)
                for hit in hits
                for responsibility in hit.responsibilities
            ),
            field_owners=tuple(
                (field_id, hit.model_id)
                for hit in hits
                for field_id in hit.fields_owned
            ),
        )
    lookup_status = (
        lookup_report.status if lookup_report else BCL_LOOKUP_STATUS_NOT_APPLICABLE
    )
    lookup_reason = lookup_report.fallback_reason if lookup_report else ""
    if lookup_status == BCL_LOOKUP_STATUS_BLOCKED and hits:
        lookup_status = BCL_LOOKUP_STATUS_FALLBACK
    reuse_decision = REUSE_DECISION_REUSE_EXISTING if hits else REUSE_DECISION_NO_MODEL_FOUND
    no_model_found_reason = "" if hits else "No relevant FlowGuard model files were found in project inventory."
    rationale = (
        "Plane-first behavior lookup and project inventory found existing FlowGuard model context."
        if hits
        else "Proceed with explicit no-model-found boundary before downstream modeling."
    )
    return ExistingModelPreflight(
        preflight_id or "project-inventory-preflight",
        task_summary,
        mode=mode,
        existing_modeled_system=True,
        authority_required=True,
        authority_status=authority_status,
        authority_snapshot_fingerprint=authority_snapshot_fingerprint,
        authority_subject_revision=authority_subject_revision,
        authority_gap_ids=authority_gap_ids,
        model_search_performed=True,
        search_paths=searched_paths,
        behavior_lookup_required=behavior_lookup_required,
        behavior_lookup_status=lookup_status,
        primary_behavior_plane=lookup_report.selected_plane if lookup_report else "",
        primary_commitment_hits=primary_lookup_hits,
        related_commitment_hits=related_lookup_hits,
        candidate_commitment_hits=candidate_lookup_hits,
        plane_ambiguity=lookup_report.plane_ambiguity if lookup_report else False,
        ledger_fingerprint=lookup_report.ledger_fingerprint if lookup_report else "",
        behavior_lookup_reason=lookup_reason,
        relevant_models=tuple(hits),
        ownership_snapshot=ownership_snapshot,
        reuse_decision=reuse_decision,
        downstream_routes=tuple(downstream_routes),
        rationale=rationale,
        no_model_found_reason=no_model_found_reason,
    )


def review_existing_model_preflight(
    preflight: ExistingModelPreflight,
) -> ExistingModelPreflightReport:
    """Review an existing-model preflight report."""

    findings: list[ExistingModelPreflightFinding] = []

    if preflight.authority_required:
        if preflight.authority_status not in {"pass", "pass_with_gaps"}:
            findings.append(
                ExistingModelPreflightFinding(
                    "model_authority_missing_or_invalid",
                    "Project inventory cannot establish current model ownership "
                    "without one valid observed model-system authority.",
                )
            )
        elif (
            not preflight.authority_snapshot_fingerprint
            or not preflight.authority_subject_revision
        ):
            findings.append(
                ExistingModelPreflightFinding(
                    "model_authority_identity_missing",
                    "The observed model authority lacks snapshot or source identity.",
                )
            )

    inventory_required = bool(
        preflight.require_complete_surface_inventory
        or preflight.affected_business_intent_id
        or preflight.selected_commitment_id
        or preflight.selected_primary_path_id
        or preflight.expected_surface_ids
        or preflight.intent_surfaces
        or preflight.surface_inventory_revision
        or preflight.surface_inventory_evidence_ids
        or preflight.typed_external_difference_ids
    )
    covered_surface_ids = tuple(
        surface.surface_id for surface in preflight.intent_surfaces if surface.in_scope and surface.surface_id
    )
    scoped_surface_ids = tuple(
        surface.surface_id for surface in preflight.intent_surfaces if not surface.in_scope and surface.surface_id
    )
    missing_surface_ids = tuple(
        surface_id
        for surface_id in preflight.expected_surface_ids
        if surface_id not in set(covered_surface_ids) | set(scoped_surface_ids)
    )

    if not preflight.preflight_id:
        findings.append(
            ExistingModelPreflightFinding(
                "missing_preflight_id",
                "existing-model preflight has no id",
            )
        )
    if not preflight.task_summary:
        findings.append(
            ExistingModelPreflightFinding(
                "missing_task_summary",
                "existing-model preflight has no task summary",
            )
        )
    if preflight.mode not in PREFLIGHT_MODES:
        findings.append(
            ExistingModelPreflightFinding(
                "invalid_preflight_mode",
                f"existing-model preflight mode {preflight.mode!r} is not recognized",
            )
        )
    if preflight.reuse_decision and preflight.reuse_decision not in REUSE_DECISIONS:
        findings.append(
            ExistingModelPreflightFinding(
                "invalid_reuse_decision",
                f"reuse decision {preflight.reuse_decision!r} is not recognized",
            )
        )
    if preflight.behavior_lookup_status not in BCL_LOOKUP_STATUSES:
        findings.append(
            ExistingModelPreflightFinding(
                "invalid_behavior_lookup_status",
                "preflight behavior lookup status is not recognized",
                metadata={"behavior_lookup_status": preflight.behavior_lookup_status},
            )
        )
    if preflight.spec_context:
        context = preflight.spec_context
        missing = tuple(
            field_name
            for field_name in ("provider_id", "context_id", "change_id")
            if not str(context.get(field_name, ""))
        )
        if missing:
            findings.append(
                ExistingModelPreflightFinding(
                    "spec_context_identity_missing",
                    "OpenSpec context must preserve provider, context, and change identities",
                    metadata={"missing": list(missing)},
                )
            )
        if context.get("behavior_plane") != BCL_PLANE_DEVELOPMENT_PROCESS:
            findings.append(
                ExistingModelPreflightFinding(
                    "spec_context_wrong_plane",
                    "OpenSpec context belongs only to development_process",
                    metadata=dict(context),
                )
            )
        if context.get("provider_id") != "openspec":
            findings.append(
                ExistingModelPreflightFinding(
                    "spec_context_provider_unsupported",
                    "only official OpenSpec context is supported",
                    metadata=dict(context),
                )
            )
        if context.get("read_only") is not True:
            findings.append(
                ExistingModelPreflightFinding(
                    "spec_context_write_authority_forbidden",
                    "OpenSpec may be used only as read-only external context",
                    metadata=dict(context),
                )
            )
        if context.get("provider_owns_product_behavior") is not False:
            findings.append(
                ExistingModelPreflightFinding(
                    "spec_provider_takes_product_ownership",
                    "provider tasks may target but cannot own product-runtime commitments",
                    metadata=dict(context),
                )
            )
        if context.get("current") is not True:
            findings.append(
                ExistingModelPreflightFinding(
                    "spec_context_not_current",
                    "OpenSpec context must be current before it can support model selection",
                    metadata=dict(context),
                )
            )
        if not str(context.get("context_hash", "")).startswith("sha256:"):
            findings.append(
                ExistingModelPreflightFinding(
                    "spec_context_fingerprint_missing",
                    "OpenSpec context needs one current content identity",
                    metadata=dict(context),
                )
            )
        if not context.get("artifact_ids"):
            findings.append(
                ExistingModelPreflightFinding(
                    "spec_context_artifacts_missing",
                    "OpenSpec context needs proposal/design/spec/tasks/status artifact identities",
                    metadata=dict(context),
                )
            )
        if preflight.behavior_lookup_status != BCL_LOOKUP_STATUS_PERFORMED:
            findings.append(
                ExistingModelPreflightFinding(
                    "spec_context_before_plane_lookup",
                    "OpenSpec context may be consumed only after canonical plane-first lookup",
                    metadata=dict(context),
                )
            )
        elif preflight.primary_behavior_plane != BCL_PLANE_DEVELOPMENT_PROCESS:
            findings.append(
                ExistingModelPreflightFinding(
                    "spec_context_lookup_plane_mismatch",
                    "OpenSpec context cannot merge into a primary owner from another plane",
                    metadata={
                        "primary_behavior_plane": preflight.primary_behavior_plane,
                        "spec_context": dict(context),
                    },
                )
            )
    if preflight.behavior_lookup_required and preflight.behavior_lookup_status in {
        BCL_LOOKUP_STATUS_BLOCKED,
        BCL_LOOKUP_STATUS_FALLBACK,
        BCL_LOOKUP_STATUS_NOT_APPLICABLE,
    }:
        findings.append(
            ExistingModelPreflightFinding(
                "behavior_lookup_not_current",
                "required canonical behavior lookup did not complete; path inventory is fallback evidence only",
                severity="blocker" if preflight.mode == PREFLIGHT_MODE_FULL else "warning",
                metadata={
                    "behavior_lookup_status": preflight.behavior_lookup_status,
                    "reason": preflight.behavior_lookup_reason,
                },
            )
        )
    if preflight.behavior_lookup_status == BCL_LOOKUP_STATUS_PERFORMED:
        if not preflight.ledger_fingerprint:
            findings.append(
                ExistingModelPreflightFinding(
                    "behavior_lookup_missing_ledger_fingerprint",
                    "performed behavior lookup must preserve the canonical ledger fingerprint",
                )
            )
        if preflight.plane_ambiguity:
            findings.append(
                ExistingModelPreflightFinding(
                    "behavior_lookup_plane_ambiguous",
                    "behavior lookup kept multiple responsibility planes and cannot select one primary owner set",
                    severity="blocker" if preflight.mode == PREFLIGHT_MODE_FULL else "warning",
                    metadata={
                        "candidate_hits": [hit.to_dict() for hit in preflight.candidate_commitment_hits],
                    },
                )
            )
        if preflight.primary_commitment_hits and preflight.primary_behavior_plane not in BCL_BEHAVIOR_PLANES:
            findings.append(
                ExistingModelPreflightFinding(
                    "behavior_lookup_primary_plane_missing",
                    "primary commitment hits require one valid primary behavior plane",
                )
            )
        primary_ids = {hit.commitment_id for hit in preflight.primary_commitment_hits}
        relevant_owner_ids = {model.model_id for model in preflight.relevant_models}
        for hit in preflight.primary_commitment_hits:
            if hit.behavior_plane != preflight.primary_behavior_plane:
                findings.append(
                    ExistingModelPreflightFinding(
                        "behavior_lookup_wrong_plane_primary_hit",
                        "primary hit belongs to a different behavior plane",
                        model_id=hit.primary_owner_model_id,
                        item_id=hit.commitment_id,
                        metadata=hit.to_dict(),
                    )
                )
            if hit.hit_role != BCL_HIT_ROLE_PRIMARY:
                findings.append(
                    ExistingModelPreflightFinding(
                        "behavior_lookup_primary_hit_role_mismatch",
                        "primary hit must retain the primary role",
                        item_id=hit.commitment_id,
                        metadata=hit.to_dict(),
                    )
                )
            if hit.primary_owner_model_id and hit.primary_owner_model_id not in relevant_owner_ids:
                findings.append(
                    ExistingModelPreflightFinding(
                        "behavior_lookup_owner_model_not_projected",
                        "primary commitment owner model is missing from relevant model hits",
                        model_id=hit.primary_owner_model_id,
                        item_id=hit.commitment_id,
                    )
                )
        for hit in preflight.related_commitment_hits:
            if hit.hit_role == BCL_HIT_ROLE_PRIMARY:
                findings.append(
                    ExistingModelPreflightFinding(
                        "behavior_lookup_related_hit_promoted",
                        "typed related commitment cannot be presented as a primary instruction",
                        item_id=hit.commitment_id,
                        metadata=hit.to_dict(),
                    )
                )
            if hit.commitment_id in primary_ids:
                findings.append(
                    ExistingModelPreflightFinding(
                        "behavior_lookup_primary_related_overlap",
                        "one commitment cannot be both primary and related in the same lookup report",
                        item_id=hit.commitment_id,
                    )
                )

    if preflight.skip_reason:
        if inventory_required:
            findings.append(
                ExistingModelPreflightFinding(
                    "surface_inventory_skip_forbidden",
                    "same-intent surface discovery cannot be skipped after an affected intent or inventory has been declared",
                )
            )
        if preflight.reuse_decision and preflight.reuse_decision != REUSE_DECISION_SKIP:
            findings.append(
                ExistingModelPreflightFinding(
                    "skip_decision_mismatch",
                    "preflight skip reason conflicts with a non-skip reuse decision",
                )
            )
        if not preflight.rationale:
            findings.append(
                ExistingModelPreflightFinding(
                    "skip_without_rationale",
                    "preflight skip must explain why model grounding is unnecessary",
                )
            )
        blockers = _blocker_findings(findings)
        return ExistingModelPreflightReport(
            ok=not blockers,
            preflight_id=preflight.preflight_id,
            decision=_decision_for_findings(preflight, findings),
            findings=tuple(findings),
            covered_surface_ids=covered_surface_ids,
            scoped_surface_ids=scoped_surface_ids,
            missing_surface_ids=missing_surface_ids,
            business_intent_id=preflight.affected_business_intent_id,
            behavior_commitment_id=preflight.selected_commitment_id,
            primary_path_id=preflight.selected_primary_path_id,
        )

    if not preflight.model_search_performed:
        findings.append(
            ExistingModelPreflightFinding(
                "missing_model_search",
                "preflight claims model grounding without searching existing FlowGuard models",
            )
        )
    if not preflight.search_paths:
        findings.append(
            ExistingModelPreflightFinding(
                "missing_search_paths",
                "preflight does not record the model search path or inventory consulted",
            )
        )

    if preflight.relevant_models:
        if preflight.reuse_decision == REUSE_DECISION_NO_MODEL_FOUND:
            findings.append(
                ExistingModelPreflightFinding(
                    "model_found_decision_mismatch",
                    "preflight found relevant models but reuse decision says no model was found",
                )
            )
        if preflight.mode == PREFLIGHT_MODE_FULL and not _has_ownership_evidence(preflight):
            findings.append(
                ExistingModelPreflightFinding(
                    "missing_ownership_evidence",
                    "full preflight found models but does not record FunctionBlock, state, side-effect, entrypoint, or responsibility ownership",
                )
            )
        for model in preflight.relevant_models:
            if not model.model_id:
                findings.append(
                    ExistingModelPreflightFinding(
                        "missing_model_id",
                        "model context hit has no model id",
                        metadata=model.to_dict(),
                    )
                )
            if not model.evidence_current:
                findings.append(
                    ExistingModelPreflightFinding(
                        "stale_model_evidence",
                        "model context hit has stale evidence and needs downstream freshness handling",
                        severity="warning",
                        model_id=model.model_id,
                        metadata=model.to_dict(),
                    )
                )
            if preflight.mode == PREFLIGHT_MODE_FULL:
                missing_layered_fields = _missing_layered_status_fields(model)
                if missing_layered_fields:
                    findings.append(
                        ExistingModelPreflightFinding(
                            "layered_proof_status_unknown",
                            "full preflight found a parent model but does not record parent coverage, child disjointness, child reattachment, leaf matrix status, and layered proof evidence id",
                            model_id=model.model_id,
                            metadata={
                                "missing_fields": missing_layered_fields,
                                "model": model.to_dict(),
                            },
                        )
                    )
    else:
        if preflight.reuse_decision != REUSE_DECISION_NO_MODEL_FOUND:
            findings.append(
                ExistingModelPreflightFinding(
                    "no_model_found_decision_required",
                    "preflight found no relevant models but did not record no_model_found",
                )
            )
        if not preflight.no_model_found_reason:
            findings.append(
                ExistingModelPreflightFinding(
                    "no_model_found_reason_missing",
                    "preflight found no relevant models but does not explain the search result",
                )
            )

    if not preflight.reuse_decision:
        findings.append(
            ExistingModelPreflightFinding(
                "missing_reuse_decision",
                "preflight does not decide whether to reuse, extend, add child model, create a new boundary, or record no_model_found",
            )
        )

    if preflight.mode == PREFLIGHT_MODE_FULL:
        if not preflight.downstream_routes:
            findings.append(
                ExistingModelPreflightFinding(
                    "missing_downstream_route",
                    "full preflight does not name the downstream FlowGuard route",
                )
            )

    if inventory_required:
        if not preflight.affected_business_intent_id:
            findings.append(
                ExistingModelPreflightFinding(
                    "missing_stable_intent_identity",
                    "intent-surface inventory requires one stable business intent id",
                )
            )
        if not preflight.selected_commitment_id:
            findings.append(
                ExistingModelPreflightFinding(
                    "missing_stable_commitment_identity",
                    "intent-surface inventory requires the selected behavior commitment id",
                )
            )
        if not preflight.selected_primary_path_id:
            findings.append(
                ExistingModelPreflightFinding(
                    "missing_stable_primary_path_identity",
                    "intent-surface inventory requires the selected primary path id",
                )
            )
        if not preflight.surface_inventory_revision:
            findings.append(
                ExistingModelPreflightFinding(
                    "surface_inventory_revision_missing",
                    "intent-surface inventory has no revision or source snapshot identity",
                )
            )
        if not preflight.surface_inventory_evidence_ids:
            findings.append(
                ExistingModelPreflightFinding(
                    "surface_inventory_evidence_missing",
                    "intent-surface inventory has no current discovery evidence",
                )
            )
        if preflight.require_complete_surface_inventory and not preflight.expected_surface_ids:
            findings.append(
                ExistingModelPreflightFinding(
                    "surface_inventory_expected_set_missing",
                    "complete intent-surface review requires an explicit expected surface set",
                )
            )
        duplicate_expected_surface_ids = {
            surface_id
            for surface_id in preflight.expected_surface_ids
            if preflight.expected_surface_ids.count(surface_id) > 1
        }
        for surface_id in sorted(duplicate_expected_surface_ids):
            findings.append(
                ExistingModelPreflightFinding(
                    "duplicate_expected_intent_surface",
                    "complete intent-surface inventory repeats an expected surface id",
                    item_id=surface_id,
                )
            )
        for surface_id in missing_surface_ids:
            findings.append(
                ExistingModelPreflightFinding(
                    "missing_expected_intent_surface",
                    "an expected same-intent surface is absent from the materialized or scoped inventory",
                    item_id=surface_id,
                )
            )
        seen_surface_ids: set[str] = set()
        for surface in preflight.intent_surfaces:
            if (
                preflight.require_complete_surface_inventory
                and preflight.expected_surface_ids
                and surface.surface_id not in preflight.expected_surface_ids
            ):
                findings.append(
                    ExistingModelPreflightFinding(
                        "unexpected_intent_surface",
                        "materialized same-intent surface is absent from the declared complete expected set",
                        item_id=surface.surface_id,
                    )
                )
            if surface.surface_id in seen_surface_ids:
                findings.append(
                    ExistingModelPreflightFinding(
                        "duplicate_intent_surface_id",
                        "intent-surface inventory contains the same surface id more than once",
                        item_id=surface.surface_id,
                    )
                )
            seen_surface_ids.add(surface.surface_id)
            if surface.surface_kind not in PREFLIGHT_SURFACE_KINDS:
                findings.append(
                    ExistingModelPreflightFinding(
                        "intent_surface_kind_invalid",
                        "intent surface must use a recognized UI, API, CLI, alias, adapter, wrapper, helper, or compatibility kind",
                        item_id=surface.surface_id,
                        metadata={"surface_kind": surface.surface_kind},
                    )
                )
            if surface.in_scope:
                missing_fields = surface.missing_material_fields()
                if missing_fields:
                    findings.append(
                        ExistingModelPreflightFinding(
                            "intent_surface_materialization_incomplete",
                            "in-scope intent surface is missing stable identity, ownership, terminal, or evidence fields",
                            item_id=surface.surface_id,
                            metadata={"missing_fields": list(missing_fields)},
                        )
                    )
            elif not surface.has_scoped_disposition():
                findings.append(
                    ExistingModelPreflightFinding(
                        "intent_surface_scoped_disposition_incomplete",
                        "scoped-out same-intent surface needs owner, evidence, reason, validation boundary, and rationale",
                        item_id=surface.surface_id,
                    )
                )
            if not surface.evidence_current:
                findings.append(
                    ExistingModelPreflightFinding(
                        "intent_surface_evidence_stale",
                        "intent surface discovery or scoped-disposition evidence is stale",
                        item_id=surface.surface_id,
                    )
                )
            for field_name, expected_value in (
                ("business_intent_id", preflight.affected_business_intent_id),
                ("behavior_commitment_id", preflight.selected_commitment_id),
                ("primary_path_id", preflight.selected_primary_path_id),
            ):
                actual_value = getattr(surface, field_name)
                if (
                    expected_value
                    and actual_value
                    and actual_value != expected_value
                    and (surface.in_scope or field_name == "business_intent_id")
                ):
                    findings.append(
                        ExistingModelPreflightFinding(
                            f"intent_surface_{field_name}_mismatch",
                            f"in-scope intent surface points at a different {field_name}",
                            item_id=surface.surface_id,
                            metadata={"expected": expected_value, "actual": actual_value},
                        )
                    )

        if (
            preflight.reuse_decision == REUSE_DECISION_NEW_BOUNDARY
            and preflight.affected_business_intent_id
            and preflight.intent_surfaces
            and not preflight.typed_external_difference_ids
        ):
            findings.append(
                ExistingModelPreflightFinding(
                    "same_intent_new_boundary_without_external_difference",
                    "a new boundary for an already inventoried intent needs typed externally observable differences",
                    item_id=preflight.affected_business_intent_id,
                )
            )

        if preflight.similarity_handoff and preflight.similarity_handoff.relation_ids:
            material_test_obligations = getattr(preflight.similarity_handoff, "test_obligations", ())
            material_code_obligations = getattr(preflight.similarity_handoff, "code_obligations", ())
            if not (material_test_obligations or material_code_obligations):
                findings.append(
                    ExistingModelPreflightFinding(
                        "unmaterialized_similarity_obligations",
                        "similarity evidence must hand off material test or code obligations, not only opaque ids",
                        metadata={"relation_ids": list(preflight.similarity_handoff.relation_ids)},
                    )
                )
        if not preflight.rationale:
            findings.append(
                ExistingModelPreflightFinding(
                    "missing_preflight_rationale",
                    "full preflight does not explain the reuse or route decision",
                )
            )

    field_lifecycle_required = preflight.field_lifecycle_required or bool(preflight.behavior_field_ids)
    known_field_owner_ids = set(preflight.field_lifecycle_model_ids)
    for model in preflight.relevant_models:
        known_field_owner_ids.update(model.fields_owned)
    if preflight.ownership_snapshot:
        known_field_owner_ids.update(field_id for field_id, _owner in preflight.ownership_snapshot.field_owners)
    if field_lifecycle_required and not known_field_owner_ids:
        findings.append(
            ExistingModelPreflightFinding(
                "missing_field_lifecycle_ownership",
                "behavior-bearing fields are in scope but no field lifecycle model, field owner, or field ownership snapshot is recorded",
                metadata={
                    "behavior_field_ids": list(preflight.behavior_field_ids),
                    "downstream_routes": list(preflight.downstream_routes),
                },
            )
        )
    if field_lifecycle_required and "field_lifecycle_mesh" not in preflight.downstream_routes:
        findings.append(
            ExistingModelPreflightFinding(
                "missing_field_lifecycle_route",
                "behavior-bearing fields are in scope but field_lifecycle_mesh is not named as a downstream route",
                severity="warning",
                metadata={"behavior_field_ids": list(preflight.behavior_field_ids)},
            )
        )
    for gap_id in preflight.field_lifecycle_gap_ids:
        findings.append(
            ExistingModelPreflightFinding(
                "field_lifecycle_gap_unresolved",
                "existing field lifecycle preflight found an unresolved field model gap",
                item_id=gap_id,
                metadata={"field_lifecycle_gap_ids": list(preflight.field_lifecycle_gap_ids)},
            )
        )

    model_angle_required = preflight.model_angle_review_required or bool(
        preflight.model_angle_deliberations or preflight.model_angle_gap_ids
    )
    if model_angle_required:
        model_angle_report = review_model_angle_deliberations(
            f"{preflight.preflight_id}:model-angle",
            preflight.model_angle_deliberations,
            require_review=preflight.model_angle_review_required,
            broad_claim=preflight.mode == PREFLIGHT_MODE_FULL,
            allow_scoped_confidence=True,
        )
        for finding in model_angle_report.findings:
            severity = "warning"
            if finding.severity == "blocker" or model_angle_report.confidence == MODEL_ANGLE_CONFIDENCE_BLOCKED:
                severity = "blocker"
            elif model_angle_report.confidence == MODEL_ANGLE_CONFIDENCE_SCOPED:
                severity = "warning"
            findings.append(
                ExistingModelPreflightFinding(
                    f"model_angle_{finding.code}",
                    finding.message,
                    severity=severity,
                    model_id=",".join(
                        item.angle_id
                        for item in preflight.model_angle_deliberations
                        if item.angle_id == finding.angle_id
                    ),
                    item_id=finding.angle_id,
                    metadata={
                        "model_angle_finding": finding.to_dict(),
                        "model_angle_report": model_angle_report.to_dict(),
                    },
                )
            )
    for gap_id in preflight.model_angle_gap_ids:
        findings.append(
            ExistingModelPreflightFinding(
                "model_angle_gap_unresolved",
                "existing-model preflight found an unresolved model-angle gap",
                item_id=gap_id,
                metadata={"model_angle_gap_ids": list(preflight.model_angle_gap_ids)},
            )
        )

    similarity_handoff = preflight.similarity_handoff
    similarity_relation_ids = similarity_handoff.relation_ids if similarity_handoff else ()
    if preflight.mode == PREFLIGHT_MODE_FULL and preflight.similarity_review_required:
        if not similarity_relation_ids:
            findings.append(
                ExistingModelPreflightFinding(
                    "missing_similarity_evidence",
                    "full preflight requires model-similarity review but names no current relation ids",
                )
            )
        if similarity_handoff and not similarity_handoff.evidence_current:
            findings.append(
                ExistingModelPreflightFinding(
                    "stale_similarity_evidence",
                    "full preflight requires model-similarity review but the similarity evidence is stale",
                    metadata={"similarity_relation_ids": list(similarity_relation_ids)},
                )
            )
        for gap in similarity_handoff.unresolved_gaps if similarity_handoff else ():
            findings.append(
                ExistingModelPreflightFinding(
                    "unresolved_similarity_gap",
                    "model-similarity review reported an unresolved gap for this boundary decision",
                    item_id=gap,
                    metadata={"similarity_relation_ids": list(similarity_relation_ids)},
                )
            )
        if similarity_handoff and similarity_relation_ids and not (
            similarity_handoff.maintenance_group_ids or similarity_handoff.false_friend_rationales
        ):
            findings.append(
                ExistingModelPreflightFinding(
                    "missing_similarity_maintenance_group",
                    "current similarity relations should name the maintenance group or false-friend rationale that governs sibling review",
                    severity="warning",
                    metadata={"similarity_relation_ids": list(similarity_relation_ids)},
                )
            )
        if (
            similarity_handoff
            and similarity_handoff.impacted_model_ids
            and not similarity_handoff.change_impact_ids
        ):
            findings.append(
                ExistingModelPreflightFinding(
                    "missing_similarity_change_impact",
                    "impacted sibling models from model-similarity review require change-impact ids before claiming all related work was checked",
                    metadata={"impacted_similarity_model_ids": list(similarity_handoff.impacted_model_ids)},
                )
            )

    if preflight.reuse_decision in {
        REUSE_DECISION_ADD_CHILD_MODEL,
        REUSE_DECISION_NEW_BOUNDARY,
    } and not (preflight.proposed_new_boundaries and preflight.rationale):
        findings.append(
            ExistingModelPreflightFinding(
                "new_boundary_without_rationale",
                "new model or ownership boundary needs a named boundary and rationale for why existing models cannot carry it",
            )
        )
    if (
        preflight.reuse_decision == REUSE_DECISION_NEW_BOUNDARY
        and similarity_handoff
        and similarity_relation_ids
        and similarity_handoff.false_friend_rationales
        and not preflight.rationale
    ):
        findings.append(
            ExistingModelPreflightFinding(
                "false_friend_rationale_missing",
                "new boundary based on false-friend similarity must keep the separation rationale visible",
                metadata={"false_friend_rationales": list(similarity_handoff.false_friend_rationales)},
            )
        )

    for risk in preflight.duplicate_risks:
        if not risk.item_id or not risk.item_type or not risk.existing_owner_id:
            findings.append(
                ExistingModelPreflightFinding(
                    "incomplete_duplicate_boundary_risk",
                    "duplicate boundary risk must name the item type, item id, and existing owner",
                    item_id=risk.item_id,
                    metadata=risk.to_dict(),
                )
            )
        if not risk.is_resolved():
            findings.append(
                ExistingModelPreflightFinding(
                    "duplicate_boundary_risk_unresolved",
                    "duplicate model, state, side-effect, FunctionBlock, entrypoint, or responsibility ownership is not resolved",
                    model_id=risk.existing_owner_id,
                    item_id=risk.item_id,
                    metadata=risk.to_dict(),
                )
            )

    blockers = _blocker_findings(findings)
    return ExistingModelPreflightReport(
        ok=not blockers,
        preflight_id=preflight.preflight_id,
        decision=_decision_for_findings(preflight, findings),
        findings=tuple(findings),
        covered_surface_ids=covered_surface_ids,
        scoped_surface_ids=scoped_surface_ids,
        missing_surface_ids=missing_surface_ids,
        business_intent_id=preflight.affected_business_intent_id,
        behavior_commitment_id=preflight.selected_commitment_id,
        primary_path_id=preflight.selected_primary_path_id,
    )


__all__ = [
    "DUPLICATE_RISK_RESOLUTIONS",
    "ExistingModelPreflight",
    "ExistingModelPreflightFinding",
    "ExistingModelPreflightReport",
    "ExistingIntentSurface",
    "ExistingOwnershipSnapshot",
    "DuplicateBoundaryRisk",
    "ModelContextHit",
    "PREFLIGHT_MODE_FULL",
    "PREFLIGHT_MODE_LIGHT",
    "PREFLIGHT_MODES",
    "PREFLIGHT_SURFACE_KINDS",
    "REUSE_DECISION_ADD_CHILD_MODEL",
    "REUSE_DECISION_EXTEND_EXISTING",
    "REUSE_DECISION_NEW_BOUNDARY",
    "REUSE_DECISION_NO_MODEL_FOUND",
    "REUSE_DECISION_REUSE_EXISTING",
    "REUSE_DECISION_SKIP",
    "REUSE_DECISIONS",
    "review_existing_model_preflight",
    "existing_model_preflight_from_project",
]
