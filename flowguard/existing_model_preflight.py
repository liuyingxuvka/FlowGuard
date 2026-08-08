"""Existing FlowGuard model preflight helpers.

Existing-model preflight is a companion review before an agent discusses,
proposes, or modifies behavior in an existing modeled system. It does not
replace downstream routes such as ModelMesh, StructureMesh, UI Flow Structure,
or Model-Miss Review. It checks that the agent first grounded its reasoning in
the model map that already exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from ._normalization import string_sequence as _as_tuple
from .behavior_commitment import (
    BCL_BEHAVIOR_PLANES,
    BCL_HIT_ROLE_PRIMARY,
    BCL_LOOKUP_STATUS_BLOCKED,
    BCL_LOOKUP_STATUS_NOT_APPLICABLE,
    BCL_LOOKUP_STATUS_PERFORMED,
)
from .behavior_commitment_lookup import (
    BehaviorCommitmentHit,
    BehaviorLookupQuery,
    query_behavior_commitments_from_path,
)
from .export import to_jsonable
from .model_authority import SUBJECT_LANES
from .canonical_relation import (
    CanonicalRelation,
    CanonicalRelationHandoff,
    normalize_canonical_relation_handoff,
)
from .model_authority_store import (
    audit_model_authority,
    load_observed_model_system,
)
from .proof_artifact import ProofArtifactRef, coerce_proof_artifact_ref
from .task_coverage_demand import (
    COVERAGE_DISPOSITION_BLOCKED,
    COVERAGE_DISPOSITION_SATISFIED,
    OwnerCoverageResolution,
    TASK_FACT_DISPOSITION_CONTRADICTORY,
    TASK_FACT_DISPOSITION_DECLARED,
    TASK_FACT_DISPOSITION_OMITTED,
    TASK_FACT_DISPOSITION_SCOPED_OUT,
    TASK_FACT_DISPOSITION_UNKNOWN,
    TASK_FACT_DISPOSITION_UNMAPPED,
    TASK_FACT_SOURCE_CURRENT_MODEL,
    TASK_FACT_SOURCE_STATUS_COMPLETE,
    TaskCoverageDemand,
    TaskFactObservation,
    TaskFactSourceSnapshot,
    TaskFacts,
)
from .evidence_receipts import fingerprint_value


PREFLIGHT_MODE_LIGHT = "light"
PREFLIGHT_MODE_FULL = "full"
PREFLIGHT_MODES = {PREFLIGHT_MODE_LIGHT, PREFLIGHT_MODE_FULL}

PREFLIGHT_INVENTORY_SELECTED = "selected_owner_closure"
PREFLIGHT_INVENTORY_BROAD = "broad_authority_inventory"
PREFLIGHT_INVENTORY_SCOPES = {
    PREFLIGHT_INVENTORY_SELECTED,
    PREFLIGHT_INVENTORY_BROAD,
}

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

PREFLIGHT_GROUNDING_MODELED_CURRENT = "modeled_current"
PREFLIGHT_GROUNDING_ADOPTION_CANDIDATE = "adoption_candidate"
PREFLIGHT_GROUNDING_STATES = {
    PREFLIGHT_GROUNDING_MODELED_CURRENT,
    PREFLIGHT_GROUNDING_ADOPTION_CANDIDATE,
}

_CURRENT_PREFLIGHT_LOOKUP_STATUSES = {
    BCL_LOOKUP_STATUS_PERFORMED,
    BCL_LOOKUP_STATUS_NOT_APPLICABLE,
    BCL_LOOKUP_STATUS_BLOCKED,
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
    relation_ids: tuple[str, ...] = ()
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
        object.__setattr__(self, "relation_ids", _as_tuple(self.relation_ids))
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
            "relation_ids": list(self.relation_ids),
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
    inventory_scope: str = PREFLIGHT_INVENTORY_SELECTED
    existing_modeled_system: bool = True
    grounding_state: str = PREFLIGHT_GROUNDING_MODELED_CURRENT
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
    canonical_relation_handoff: CanonicalRelationHandoff | Mapping[str, Any] | None = None
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
    work_contexts: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "preflight_id", str(self.preflight_id))
        object.__setattr__(self, "task_summary", str(self.task_summary))
        object.__setattr__(self, "mode", str(self.mode))
        object.__setattr__(self, "inventory_scope", str(self.inventory_scope))
        object.__setattr__(self, "existing_modeled_system", bool(self.existing_modeled_system))
        object.__setattr__(self, "grounding_state", str(self.grounding_state))
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
        object.__setattr__(
            self,
            "canonical_relation_handoff",
            normalize_canonical_relation_handoff(self.canonical_relation_handoff),
        )
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
        object.__setattr__(
            self,
            "work_contexts",
            tuple(dict(item) for item in self.work_contexts),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "preflight_id": self.preflight_id,
            "task_summary": self.task_summary,
            "mode": self.mode,
            "inventory_scope": self.inventory_scope,
            "existing_modeled_system": self.existing_modeled_system,
            "grounding_state": self.grounding_state,
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
            "canonical_relation_handoff": self.canonical_relation_handoff.to_dict()
            if self.canonical_relation_handoff
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
            "work_contexts": [
                to_jsonable(dict(item)) for item in self.work_contexts
            ],
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

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict())

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


@dataclass(frozen=True)
class BlueprintPreflightHandoff:
    """Typed handoff from current model ownership to independent implementation discovery."""

    ok: bool
    preflight_fingerprint: str
    blueprint_requested: bool
    implementation_inventory_fingerprint: str = ""
    implementation_surface_ids: tuple[str, ...] = ()
    unresolved_surface_ids: tuple[str, ...] = ()
    downstream_owner_routes: tuple[str, ...] = ()
    claim_boundary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "preflight_fingerprint", str(self.preflight_fingerprint))
        object.__setattr__(self, "blueprint_requested", bool(self.blueprint_requested))
        object.__setattr__(
            self,
            "implementation_inventory_fingerprint",
            str(self.implementation_inventory_fingerprint),
        )
        object.__setattr__(self, "implementation_surface_ids", _as_tuple(self.implementation_surface_ids))
        object.__setattr__(self, "unresolved_surface_ids", _as_tuple(self.unresolved_surface_ids))
        object.__setattr__(self, "downstream_owner_routes", _as_tuple(self.downstream_owner_routes))
        object.__setattr__(self, "claim_boundary", str(self.claim_boundary))

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "preflight_fingerprint": self.preflight_fingerprint,
            "blueprint_requested": self.blueprint_requested,
            "implementation_inventory_fingerprint": self.implementation_inventory_fingerprint,
            "implementation_surface_ids": list(self.implementation_surface_ids),
            "unresolved_surface_ids": list(self.unresolved_surface_ids),
            "downstream_owner_routes": list(self.downstream_owner_routes),
            "claim_boundary": self.claim_boundary,
        }


def project_existing_model_preflight_blueprint_handoff(
    report: ExistingModelPreflightReport,
    *,
    blueprint_requested: bool,
    implementation_inventory_report: Any | None = None,
) -> BlueprintPreflightHandoff:
    """Preserve affected-only ordinary preflight and bind full discovery only on request."""

    if not blueprint_requested:
        return BlueprintPreflightHandoff(
            ok=report.ok,
            preflight_fingerprint=report.fingerprint,
            blueprint_requested=False,
            unresolved_surface_ids=report.missing_surface_ids,
            downstream_owner_routes=("model_first_function_flow",),
            claim_boundary=(
                "Ordinary affected-slice preflight only; no whole-software implementation "
                "inventory was requested or loaded."
            ),
        )
    if implementation_inventory_report is None:
        return BlueprintPreflightHandoff(
            ok=False,
            preflight_fingerprint=report.fingerprint,
            blueprint_requested=True,
            unresolved_surface_ids=tuple(sorted(set(report.missing_surface_ids) | {"implementation_inventory:missing"})),
            downstream_owner_routes=(
                "model_test_alignment",
                "model_mesh_maintenance",
                "structure_mesh_maintenance",
                "development_process_flow",
            ),
            claim_boundary="Whole-software blueprint preflight is blocked until independent discovery exists.",
        )
    inventory_ok = bool(getattr(implementation_inventory_report, "ok", False))
    inventory_fingerprint = str(
        getattr(implementation_inventory_report, "inventory_fingerprint", "")
    )
    surface_ids = tuple(
        sorted({str(value) for value in getattr(implementation_inventory_report, "required_surface_ids", ())})
    )
    inventory_findings = tuple(getattr(implementation_inventory_report, "findings", ()))
    inventory_gaps = tuple(
        sorted(
            {
                str(
                    getattr(finding, "surface_id", "")
                    or getattr(finding, "item_id", "")
                    or getattr(finding, "code", "implementation_inventory:blocked")
                )
                for finding in inventory_findings
                if str(getattr(finding, "severity", "blocker")) == "blocker"
            }
        )
    )
    unresolved = tuple(sorted(set(report.missing_surface_ids) | set(inventory_gaps)))
    return BlueprintPreflightHandoff(
        ok=report.ok and inventory_ok and bool(inventory_fingerprint) and not unresolved,
        preflight_fingerprint=report.fingerprint,
        blueprint_requested=True,
        implementation_inventory_fingerprint=inventory_fingerprint,
        implementation_surface_ids=surface_ids,
        unresolved_surface_ids=unresolved,
        downstream_owner_routes=(
            "model_test_alignment",
            "model_mesh_maintenance",
            "structure_mesh_maintenance",
            "development_process_flow",
        ),
        claim_boundary=(
            "This handoff binds existing model ownership to an independently discovered "
            "implementation denominator; it does not itself prove blueprint completion."
        ),
    )


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
        if "adoption_candidate_not_current" in codes:
            return PREFLIGHT_GROUNDING_ADOPTION_CANDIDATE
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


def _normalized_model_path(value: str) -> str:
    normalized = str(value).strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.rstrip("/").casefold()


def _path_identity_equivalent(left: str, right: str) -> bool:
    left_value = _normalized_model_path(left)
    right_value = _normalized_model_path(right)
    if not left_value or not right_value:
        return False
    if left_value == right_value:
        return True
    left_pathlike = "/" in left_value or left_value.endswith(".py")
    right_pathlike = "/" in right_value or right_value.endswith(".py")
    if not (left_pathlike and right_pathlike):
        return False
    left_absolute = bool(re.match(r"^[a-z]:/|^/", left_value))
    right_absolute = bool(re.match(r"^[a-z]:/|^/", right_value))
    if left_absolute == right_absolute:
        return False
    absolute, relative = (
        (left_value, right_value) if left_absolute else (right_value, left_value)
    )
    return "/" in relative and absolute.endswith("/" + relative)


def _normalized_owner_fingerprint(value: str) -> str:
    normalized = str(value).strip().casefold()
    if normalized.startswith("model-authority:"):
        normalized = normalized.split("model-authority:", 1)[1]
    return normalized if normalized.startswith("sha256:") else ""


def _owner_matches_instance(owner_id: str, instance) -> bool:
    owner = str(owner_id).strip()
    if not owner:
        return False
    logical_owner = owner.split("model:", 1)[1] if owner.startswith("model:") else owner
    if _normalized_model_path(logical_owner) == _normalized_model_path(instance.logical_model_id):
        return True
    if _path_identity_equivalent(owner, instance.model_path):
        return True
    owner_fingerprint = _normalized_owner_fingerprint(owner)
    return bool(owner_fingerprint and owner_fingerprint == str(instance.fingerprint).casefold())


def _owner_matches_model_hit(owner_id: str, hit: ModelContextHit) -> bool:
    owner = str(owner_id).strip()
    if not owner:
        return False
    logical_owner = owner.split("model:", 1)[1] if owner.startswith("model:") else owner
    if _normalized_model_path(logical_owner) == _normalized_model_path(hit.model_id):
        return True
    if _path_identity_equivalent(owner, hit.model_path):
        return True
    owner_fingerprint = _normalized_owner_fingerprint(owner)
    evidence_fingerprint = _normalized_owner_fingerprint(hit.evidence_id)
    return bool(owner_fingerprint and owner_fingerprint == evidence_fingerprint)


def _lookup_owner_instance_fingerprints(snapshot, lookup_hits) -> set[str]:
    owner_ids = tuple(
        hit.primary_owner_model_id
        for hit in lookup_hits
        if hit.primary_owner_model_id
    )
    selected: set[str] = set()
    for instance in snapshot.model_instances:
        if any(_owner_matches_instance(owner_id, instance) for owner_id in owner_ids):
            selected.add(instance.fingerprint)
    return selected


def _relation_neighbor_fingerprints(snapshot, selected: set[str]) -> set[str]:
    neighbors: set[str] = set()
    for relation in snapshot.relations:
        source = relation.source
        target = relation.target
        if (
            source.endpoint_kind == "model_instance"
            and target.endpoint_kind == "model_instance"
        ):
            if source.fingerprint in selected:
                neighbors.add(target.fingerprint)
            if target.fingerprint in selected:
                neighbors.add(source.fingerprint)
    return neighbors


def _canonical_relations(
    snapshot,
    selected: set[str],
) -> tuple[CanonicalRelation, ...]:
    """Return exact observed relations directly attached to selected owners."""

    relations: list[CanonicalRelation] = []
    for relation in snapshot.relations:
        source = relation.source
        target = relation.target
        if (
            source.endpoint_kind == "model_instance"
            and source.fingerprint in selected
        ) or (
            target.endpoint_kind == "model_instance"
            and target.fingerprint in selected
        ):
            commitment_refs = tuple(
                endpoint.endpoint_id
                for endpoint in (source, target)
                if endpoint.endpoint_kind == "behavior_commitment"
            )
            source_ids = tuple(getattr(relation, "evidence_fingerprints", ())) or (
                str(snapshot.fingerprint),
            )
            relations.append(
                CanonicalRelation(
                    relation_id=relation.relation_id,
                    relation_type=relation.kind,
                    source_endpoint_kind=source.endpoint_kind,
                    source_endpoint_id=source.endpoint_id,
                    target_endpoint_kind=target.endpoint_kind,
                    target_endpoint_id=target.endpoint_id,
                    source_ids=source_ids,
                    typed_commitment_relation_refs=commitment_refs,
                )
            )
    return tuple(relations)


def _project_declares_model_authority(root_path: Path) -> bool:
    """Distinguish a never-adopted target from a broken current authority."""

    manifest_path = root_path / ".flowguard" / "project.toml"
    if not manifest_path.is_file():
        return False
    try:
        manifest_text = manifest_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return True
    return bool(re.search(r"(?m)^\s*\[model_authority\]\s*$", manifest_text))


def existing_model_preflight_from_project(
    root: str | Path,
    task_summary: str,
    *,
    preflight_id: str = "",
    changed_paths: Sequence[str] = (),
    downstream_routes: Sequence[str] = (),
    mode: str = PREFLIGHT_MODE_FULL,
    inventory_scope: str = PREFLIGHT_INVENTORY_SELECTED,
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
    authority_declared = bool(
        authority_report.ok or _project_declares_model_authority(root_path)
    )
    grounding_state = (
        PREFLIGHT_GROUNDING_MODELED_CURRENT
        if authority_declared
        else PREFLIGHT_GROUNDING_ADOPTION_CANDIDATE
    )
    authority_status = (
        authority_report.status if authority_declared else "not_adopted"
    )
    authority_snapshot_fingerprint = ""
    authority_subject_revision = ""
    authority_gap_ids: tuple[str, ...] = ()
    affected_relations: tuple[CanonicalRelation, ...] = ()
    hits: list[ModelContextHit] = []
    primary_lookup_hits = tuple(
        getattr(lookup_report, "primary_hits", ()) if lookup_report else ()
    )
    related_lookup_hits = tuple(
        getattr(lookup_report, "related_hits", ()) if lookup_report else ()
    )
    candidate_lookup_hits = tuple(
        getattr(lookup_report, "candidate_hits", ()) if lookup_report else ()
    )
    if authority_report.ok:
        _, authority_snapshot = load_observed_model_system(root_path)
        authority_snapshot_fingerprint = authority_snapshot.fingerprint
        authority_subject_revision = authority_snapshot.subject_revision
        authority_gap_ids = authority_snapshot.unresolved_gap_ids
        lookup_hits = (*primary_lookup_hits, *related_lookup_hits)
        selected_fingerprints = _lookup_owner_instance_fingerprints(
            authority_snapshot,
            lookup_hits,
        )
        if inventory_scope == PREFLIGHT_INVENTORY_BROAD:
            selected_fingerprints = {
                instance.fingerprint
                for instance in authority_snapshot.model_instances
            }
        if inventory_scope == PREFLIGHT_INVENTORY_SELECTED:
            selected_fingerprints.update(
                _relation_neighbor_fingerprints(
                    authority_snapshot,
                    selected_fingerprints,
                )
            )
        affected_relations = _canonical_relations(
            authority_snapshot,
            selected_fingerprints,
        )
        for instance in authority_snapshot.model_instances:
            if instance.fingerprint not in selected_fingerprints:
                continue
            model_path = root_path / instance.model_path
            model_text = (
                model_path.read_text(encoding="utf-8", errors="replace")
                if mode == PREFLIGHT_MODE_FULL and model_path.is_file()
                else ""
            )
            hits.append(
                ModelContextHit(
                    model_id=instance.logical_model_id,
                    model_path=instance.model_path,
                    evidence_id=(
                        f"model-authority:{instance.fingerprint}"
                    ),
                    evidence_tier="authoritative_observed",
                    evidence_current=True,
                    responsibilities=(
                        _purpose_lines(model_text)
                        if mode == PREFLIGHT_MODE_FULL
                        else (instance.logical_model_id,)
                    )
                    or (instance.logical_model_id,),
                    function_blocks=(
                        _class_names(model_text)
                        if mode == PREFLIGHT_MODE_FULL
                        else ()
                    ),
                    validation_evidence=(
                        authority_snapshot.fingerprint,
                        instance.purpose_closure_fingerprint,
                    ),
                    rationale=(
                        "Selected from the sole observed model-system authority."
                    ),
                )
            )
    seen_model_ids = {hit.model_id for hit in hits}
    seen_model_paths = {hit.model_path.replace("\\", "/") for hit in hits if hit.model_path}
    flowguard_root = root_path / ".flowguard"
    if grounding_state == PREFLIGHT_GROUNDING_ADOPTION_CANDIDATE and flowguard_root.exists():
        for path in sorted(flowguard_root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "FlowGuard" not in text and "Workflow" not in text and "Invariant" not in text:
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
                    evidence_tier=PREFLIGHT_GROUNDING_ADOPTION_CANDIDATE,
                    evidence_current=False,
                    responsibilities=responsibilities,
                    function_blocks=classes,
                    fields_owned=fields_owned,
                    validation_evidence=(relative_path,),
                    rationale=(
                        "Discovered for possible DNA adoption only; it proves no "
                        "current understanding, ownership, or implementation readiness."
                    ),
                )
            )
            seen_model_ids.add(model_id)
            seen_model_paths.add(normalized_relative)

    ownership_snapshot = None
    if authority_report.ok and hits:
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
    reuse_decision = (
        REUSE_DECISION_REUSE_EXISTING
        if authority_report.ok and hits
        else REUSE_DECISION_NO_MODEL_FOUND
    )
    if grounding_state == PREFLIGHT_GROUNDING_ADOPTION_CANDIDATE:
        no_model_found_reason = (
            "No validated current model authority is adopted; discovered paths are "
            "non-authoritative adoption candidates only."
        )
        rationale = (
            "Candidate discovery may help create the first DNA, but it cannot support "
            "a current understanding, ownership, or implementation-readiness claim."
        )
    elif hits:
        no_model_found_reason = ""
        rationale = (
            "Validated observed authority and exact behavior commitments resolved the "
            "current owner closure and its canonical affected relations."
        )
    else:
        no_model_found_reason = (
            "A modeled target exists, but no exact current affected owner was resolved."
        )
        rationale = (
            "Keep current ownership blocked until canonical commitment or affected-owner "
            "resolution succeeds; repository matches cannot substitute for it."
        )
    return ExistingModelPreflight(
        preflight_id or "project-inventory-preflight",
        task_summary,
        mode=mode,
        inventory_scope=inventory_scope,
        existing_modeled_system=authority_declared,
        grounding_state=grounding_state,
        authority_required=authority_declared,
        authority_status=authority_status,
        authority_snapshot_fingerprint=authority_snapshot_fingerprint,
        authority_subject_revision=authority_subject_revision,
        authority_gap_ids=authority_gap_ids,
        model_search_performed=True,
        search_paths=searched_paths,
        behavior_lookup_required=behavior_lookup_required,
        behavior_lookup_status=lookup_status,
        primary_behavior_plane=getattr(lookup_report, "selected_plane", "") if lookup_report else "",
        primary_commitment_hits=primary_lookup_hits,
        related_commitment_hits=related_lookup_hits,
        candidate_commitment_hits=candidate_lookup_hits,
        plane_ambiguity=getattr(lookup_report, "plane_ambiguity", False) if lookup_report else False,
        ledger_fingerprint=getattr(lookup_report, "ledger_fingerprint", "") if lookup_report else "",
        relevant_models=tuple(hits),
        ownership_snapshot=ownership_snapshot,
        reuse_decision=reuse_decision,
        downstream_routes=tuple(downstream_routes),
        rationale=rationale,
        no_model_found_reason=no_model_found_reason,
        canonical_relation_handoff=(
            CanonicalRelationHandoff(
                relations=affected_relations,
                affected_model_ids=tuple(hit.model_id for hit in hits),
                evidence_current=True,
            )
            if affected_relations
            else None
        ),
    )


def review_existing_model_preflight(
    preflight: ExistingModelPreflight,
) -> ExistingModelPreflightReport:
    """Review an existing-model preflight report."""

    findings: list[ExistingModelPreflightFinding] = []

    if preflight.grounding_state not in PREFLIGHT_GROUNDING_STATES:
        findings.append(
            ExistingModelPreflightFinding(
                "invalid_grounding_state",
                "existing-model preflight must declare modeled_current or adoption_candidate",
                metadata={"grounding_state": preflight.grounding_state},
            )
        )
    if preflight.grounding_state == PREFLIGHT_GROUNDING_ADOPTION_CANDIDATE:
        findings.append(
            ExistingModelPreflightFinding(
                "adoption_candidate_not_current",
                "Candidate discovery found no validated current DNA; current understanding, "
                "ownership, and implementation readiness remain unproved.",
                metadata={
                    "candidate_model_ids": [model.model_id for model in preflight.relevant_models],
                },
            )
        )
        if preflight.existing_modeled_system or preflight.authority_required:
            findings.append(
                ExistingModelPreflightFinding(
                    "adoption_candidate_claim_boundary_invalid",
                    "adoption_candidate cannot also claim an existing modeled system or current authority",
                )
            )
        if preflight.ownership_snapshot or any(
            model.evidence_current for model in preflight.relevant_models
        ):
            findings.append(
                ExistingModelPreflightFinding(
                    "adoption_candidate_promoted_to_current",
                    "candidate paths cannot project current ownership or current model evidence",
                )
            )
    elif not preflight.existing_modeled_system:
        findings.append(
            ExistingModelPreflightFinding(
                "modeled_current_claim_boundary_invalid",
                "modeled_current requires an existing modeled-system claim",
            )
        )

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
    if preflight.inventory_scope not in PREFLIGHT_INVENTORY_SCOPES:
        findings.append(
            ExistingModelPreflightFinding(
                "invalid_preflight_inventory_scope",
                (
                    "existing-model preflight inventory scope "
                    f"{preflight.inventory_scope!r} is not recognized"
                ),
            )
        )
    if preflight.reuse_decision and preflight.reuse_decision not in REUSE_DECISIONS:
        findings.append(
            ExistingModelPreflightFinding(
                "invalid_reuse_decision",
                f"reuse decision {preflight.reuse_decision!r} is not recognized",
            )
        )
    if preflight.behavior_lookup_status not in _CURRENT_PREFLIGHT_LOOKUP_STATUSES:
        findings.append(
            ExistingModelPreflightFinding(
                "invalid_behavior_lookup_status",
                "preflight behavior lookup status is not recognized",
                metadata={"behavior_lookup_status": preflight.behavior_lookup_status},
            )
        )
    for context in preflight.work_contexts:
        missing = tuple(
            field_name
            for field_name in (
                "adapter_id",
                "context_id",
                "native_work_id",
                "native_owner_id",
            )
            if not str(context.get(field_name, ""))
        )
        if missing:
            findings.append(
                ExistingModelPreflightFinding(
                    "work_context_identity_missing",
                    "WorkContext must preserve adapter, context, native work, and native owner identities",
                    metadata={"missing": list(missing)},
                )
            )
        if context.get("subject_lane") not in SUBJECT_LANES:
            findings.append(
                ExistingModelPreflightFinding(
                    "work_context_subject_lane_invalid",
                    "WorkContext must preserve one current model-system subject lane",
                    metadata=dict(context),
                )
            )
        if context.get("read_only") is not True:
            findings.append(
                ExistingModelPreflightFinding(
                    "work_context_write_authority_forbidden",
                    "every external WorkContext must be read-only",
                    metadata=dict(context),
                )
            )
        if context.get("provider_owns_product_behavior") is not False:
            findings.append(
                ExistingModelPreflightFinding(
                    "work_context_takes_product_ownership",
                    "native provider artifacts may source but cannot own product-runtime commitments",
                    metadata=dict(context),
                )
            )
        if context.get("current") is not True:
            findings.append(
                ExistingModelPreflightFinding(
                    "work_context_not_current",
                    "WorkContext must be current before it can support model selection",
                    metadata=dict(context),
                )
            )
        if not str(context.get("context_fingerprint", "")).startswith("sha256:"):
            findings.append(
                ExistingModelPreflightFinding(
                    "work_context_fingerprint_missing",
                    "WorkContext needs one current content identity",
                    metadata=dict(context),
                )
            )
        if not context.get("artifact_ids"):
            findings.append(
                ExistingModelPreflightFinding(
                    "work_context_artifacts_missing",
                    "WorkContext needs native artifact identities and generic roles",
                    metadata=dict(context),
                )
            )
        if preflight.behavior_lookup_status != BCL_LOOKUP_STATUS_PERFORMED:
            findings.append(
                ExistingModelPreflightFinding(
                    "work_context_before_plane_lookup",
                    "WorkContext may be consumed only after canonical plane-first lookup",
                    metadata=dict(context),
                )
            )
        mapped_surface_ids = set(context.get("behavior_source_surface_ids", ()))
        if (
            preflight.selected_commitment_id
            and not mapped_surface_ids
        ):
            findings.append(
                ExistingModelPreflightFinding(
                    "work_context_behavior_mapping_missing",
                    "selected behavior ownership requires WorkContext source-surface mapping",
                    metadata={
                        "primary_behavior_plane": preflight.primary_behavior_plane,
                        "selected_commitment_id": preflight.selected_commitment_id,
                        "context": dict(context),
                    },
                )
            )
    if (
        preflight.behavior_lookup_required
        and preflight.behavior_lookup_status != BCL_LOOKUP_STATUS_PERFORMED
    ):
        findings.append(
            ExistingModelPreflightFinding(
                "behavior_lookup_not_current",
                "required canonical behavior lookup did not complete; repository paths "
                "cannot substitute for the blocked current owner lookup",
                metadata={
                    "behavior_lookup_status": preflight.behavior_lookup_status,
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
        if preflight.behavior_lookup_required and not preflight.primary_commitment_hits:
            findings.append(
                ExistingModelPreflightFinding(
                    "behavior_lookup_primary_owner_missing",
                    "performed lookup resolved no exact primary behavior commitment owner",
                )
            )
        if preflight.plane_ambiguity:
            findings.append(
                ExistingModelPreflightFinding(
                    "behavior_lookup_plane_ambiguous",
                    "behavior lookup kept multiple responsibility planes and cannot select one primary owner set",
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
        for hit in preflight.primary_commitment_hits:
            if not hit.primary_owner_model_id:
                findings.append(
                    ExistingModelPreflightFinding(
                        "behavior_lookup_primary_owner_identity_missing",
                        "primary commitment hit does not identify one current owner model",
                        item_id=hit.commitment_id,
                        metadata=hit.to_dict(),
                    )
                )
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
            if hit.primary_owner_model_id:
                owner_matches = tuple(
                    model
                    for model in preflight.relevant_models
                    if _owner_matches_model_hit(hit.primary_owner_model_id, model)
                )
                if not owner_matches:
                    findings.append(
                        ExistingModelPreflightFinding(
                            "behavior_lookup_owner_model_not_projected",
                            "primary commitment owner model is missing from relevant model hits",
                            model_id=hit.primary_owner_model_id,
                            item_id=hit.commitment_id,
                        )
                    )
                elif len(owner_matches) > 1:
                    findings.append(
                        ExistingModelPreflightFinding(
                            "behavior_lookup_owner_model_ambiguous",
                            "primary commitment owner identity resolves to more than one relevant model hit",
                            model_id=hit.primary_owner_model_id,
                            item_id=hit.commitment_id,
                            metadata={
                                "matched_model_ids": [model.model_id for model in owner_matches],
                                "matched_model_paths": [model.model_path for model in owner_matches],
                            },
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

    if preflight.grounding_state == PREFLIGHT_GROUNDING_ADOPTION_CANDIDATE:
        claimable_models: tuple[ModelContextHit, ...] = ()
    elif preflight.authority_required:
        claimable_models = tuple(
            model
            for model in preflight.relevant_models
            if model.evidence_current
            and model.evidence_tier == "authoritative_observed"
        )
    else:
        claimable_models = tuple(preflight.relevant_models)

    if (
        preflight.authority_required
        and preflight.authority_status in {"pass", "pass_with_gaps"}
        and any(model not in claimable_models for model in preflight.relevant_models)
    ):
        findings.append(
            ExistingModelPreflightFinding(
                "non_authoritative_model_promoted",
                "current modeled ownership may contain only exact observed-authority hits",
                metadata={
                    "non_authoritative_model_ids": [
                        model.model_id
                        for model in preflight.relevant_models
                        if model not in claimable_models
                    ],
                },
            )
        )

    if claimable_models:
        if preflight.reuse_decision == REUSE_DECISION_NO_MODEL_FOUND:
            findings.append(
                ExistingModelPreflightFinding(
                    "model_found_decision_mismatch",
                    "preflight found an exact current owner but reuse decision says no model was found",
                )
            )
        if preflight.mode == PREFLIGHT_MODE_FULL and not _has_ownership_evidence(preflight):
            findings.append(
                ExistingModelPreflightFinding(
                    "missing_ownership_evidence",
                    "full preflight found models but does not record FunctionBlock, state, side-effect, entrypoint, or responsibility ownership",
                )
            )
        for model in claimable_models:
            if not model.model_id:
                findings.append(
                    ExistingModelPreflightFinding(
                        "missing_model_id",
                        "model context hit has no model id",
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
        if (
            preflight.grounding_state == PREFLIGHT_GROUNDING_MODELED_CURRENT
            and preflight.authority_required
        ):
            findings.append(
                ExistingModelPreflightFinding(
                    "modeled_current_owner_unresolved",
                    "validated or declared DNA did not resolve one exact current affected owner; "
                    "root, lexical, class-name, and file matches remain non-authoritative",
                )
            )
        if preflight.reuse_decision != REUSE_DECISION_NO_MODEL_FOUND:
            findings.append(
                ExistingModelPreflightFinding(
                    "no_model_found_decision_required",
                    "preflight found no exact current owner but did not record no_model_found",
                )
            )
        if not preflight.no_model_found_reason:
            findings.append(
                ExistingModelPreflightFinding(
                    "no_model_found_reason_missing",
                    "preflight found no exact current owner but does not explain the search result",
                )
            )

    for model in preflight.relevant_models:
        if model in claimable_models:
            continue
        findings.append(
            ExistingModelPreflightFinding(
                "adoption_candidate_context"
                if preflight.grounding_state == PREFLIGHT_GROUNDING_ADOPTION_CANDIDATE
                else "non_current_model_context",
                "model-like project context is non-authoritative and cannot support current ownership",
                severity="warning",
                model_id=model.model_id,
                metadata=model.to_dict(),
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

    canonical_relation_handoff = preflight.canonical_relation_handoff
    relation_ids = canonical_relation_handoff.relation_ids if canonical_relation_handoff else ()
    if canonical_relation_handoff and not canonical_relation_handoff.evidence_current:
        findings.append(
            ExistingModelPreflightFinding(
                "stale_canonical_relation_evidence",
                "canonical affected-relation evidence is stale",
                metadata={"relation_ids": list(relation_ids)},
            )
        )
    for gap in canonical_relation_handoff.gap_ids if canonical_relation_handoff else ():
        findings.append(
            ExistingModelPreflightFinding(
                "unresolved_canonical_relation_gap",
                "a minimal canonical relation handoff retains an unresolved affected-owner gap",
                item_id=gap,
                metadata={"relation_ids": list(relation_ids)},
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


def existing_model_preflight_projection_obligation_ids(
    preflight: ExistingModelPreflight,
    report: ExistingModelPreflightReport,
) -> tuple[str, ...]:
    """Return the exact native obligations consumed by the standard projection."""

    if preflight.preflight_id != report.preflight_id:
        raise ValueError("preflight input and report identities do not match")
    obligation_ids = {
        "existing-model-owner",
        f"preflight:{preflight.preflight_id}",
    }
    obligation_ids.update(f"model:{model.model_id}" for model in preflight.relevant_models)
    obligation_ids.update(
        f"surface:{surface_id}"
        for surface_id in (
            set(preflight.expected_surface_ids)
            | set(report.covered_surface_ids)
            | set(report.scoped_surface_ids)
            | set(report.missing_surface_ids)
        )
    )
    return tuple(sorted(obligation_ids))


def _validate_current_preflight_proof(
    preflight: ExistingModelPreflight,
    report: ExistingModelPreflightReport,
    proof: ProofArtifactRef,
) -> tuple[str, ...]:
    gaps = list(proof.material_gap_codes())
    if not proof.has_current_pass():
        gaps.append("existing_model_preflight_proof_not_current_pass")
    if proof.producer_route != "existing_model_preflight":
        gaps.append("existing_model_preflight_proof_wrong_owner")
    if proof.subject_id != preflight.preflight_id:
        gaps.append("existing_model_preflight_proof_wrong_subject")
    if proof.subject_fingerprint != report.fingerprint:
        gaps.append("existing_model_preflight_proof_wrong_report_fingerprint")
    if not proof.covers_all(
        existing_model_preflight_projection_obligation_ids(preflight, report)
    ):
        gaps.append("existing_model_preflight_proof_missing_projection_obligations")
    return tuple(dict.fromkeys(gaps))


def _preflight_task_fact_observations(
    preflight: ExistingModelPreflight,
    report: ExistingModelPreflightReport,
) -> tuple[TaskFactObservation, ...]:
    disposition_rank = {
        TASK_FACT_DISPOSITION_DECLARED: 0,
        TASK_FACT_DISPOSITION_SCOPED_OUT: 1,
        TASK_FACT_DISPOSITION_UNKNOWN: 2,
        TASK_FACT_DISPOSITION_OMITTED: 3,
        TASK_FACT_DISPOSITION_UNMAPPED: 4,
        TASK_FACT_DISPOSITION_CONTRADICTORY: 5,
    }
    observations: dict[str, TaskFactObservation] = {}

    def add(
        fact_id: str,
        disposition: str,
        *,
        reason: str,
        owner_route: str = "existing_model_preflight",
    ) -> None:
        candidate = TaskFactObservation(
            fact_id,
            TASK_FACT_SOURCE_CURRENT_MODEL,
            disposition,
            owner_route=owner_route,
            reason=reason,
        )
        current = observations.get(fact_id)
        if current is None or disposition_rank[disposition] > disposition_rank[
            current.disposition
        ]:
            observations[fact_id] = candidate

    for model in preflight.relevant_models:
        add(
            f"model:{model.model_id}",
            (
                TASK_FACT_DISPOSITION_DECLARED
                if model.evidence_current
                else TASK_FACT_DISPOSITION_UNKNOWN
            ),
            reason=model.rationale or "current-model preflight model hit",
        )
    ownership = preflight.ownership_snapshot
    if ownership is not None:
        for prefix, pairs in (
            ("function-block", ownership.function_block_owners),
            ("state", ownership.state_owners),
            ("side-effect", ownership.side_effect_owners),
            ("entrypoint", ownership.public_entrypoint_owners),
            ("field", ownership.field_owners),
            ("responsibility", ownership.responsibility_owners),
        ):
            for item_id, owner_id in pairs:
                add(
                    f"{prefix}:{item_id}",
                    TASK_FACT_DISPOSITION_DECLARED,
                    reason=f"owned by current model {owner_id}",
                )

    covered = set(report.covered_surface_ids)
    scoped = set(report.scoped_surface_ids)
    missing = set(report.missing_surface_ids)
    for surface_id in sorted(
        set(preflight.expected_surface_ids) | covered | scoped | missing
    ):
        if surface_id in missing:
            disposition = TASK_FACT_DISPOSITION_OMITTED
            reason = "expected public surface was missing from current preflight coverage"
        elif surface_id in scoped:
            disposition = TASK_FACT_DISPOSITION_SCOPED_OUT
            reason = "public surface was explicitly scoped out"
        elif surface_id in covered:
            disposition = TASK_FACT_DISPOSITION_DECLARED
            reason = "public surface was covered by current preflight"
        else:
            disposition = TASK_FACT_DISPOSITION_UNMAPPED
            reason = "expected public surface has no current preflight disposition"
        add(f"surface:{surface_id}", disposition, reason=reason)

    for gap_id in preflight.authority_gap_ids:
        add(
            f"authority-gap:{gap_id}",
            TASK_FACT_DISPOSITION_UNKNOWN,
            reason="current observed model authority reported a gap",
        )
    for index, finding in enumerate(report.findings):
        if finding.severity != "blocker":
            continue
        finding_id = finding.item_id or finding.model_id or str(index)
        if "missing" in finding.code or "omitted" in finding.code:
            disposition = TASK_FACT_DISPOSITION_OMITTED
        elif "duplicate" in finding.code or "conflict" in finding.code:
            disposition = TASK_FACT_DISPOSITION_CONTRADICTORY
        else:
            disposition = TASK_FACT_DISPOSITION_UNKNOWN
        add(
            f"preflight-finding:{finding.code}:{finding_id}",
            disposition,
            reason=finding.message,
        )
    return tuple(observations[key] for key in sorted(observations))


def project_existing_model_preflight_to_task_facts(
    base_facts: TaskFacts,
    preflight: ExistingModelPreflight,
    report: ExistingModelPreflightReport,
    proof: ProofArtifactRef | Mapping[str, Any],
) -> TaskFacts:
    """Replace the current-model fact plane from one exact native preflight proof."""

    proof_ref = coerce_proof_artifact_ref(proof)
    proof_gaps = _validate_current_preflight_proof(preflight, report, proof_ref)
    if proof_gaps:
        raise ValueError(
            "current preflight proof is not projection-ready: " + ",".join(proof_gaps)
        )
    observations = _preflight_task_fact_observations(preflight, report)
    snapshot = TaskFactSourceSnapshot(
        TASK_FACT_SOURCE_CURRENT_MODEL,
        proof_ref.result_path,
        report.fingerprint,
        status=TASK_FACT_SOURCE_STATUS_COMPLETE,
        observations=observations,
        reason="standard current-model projection from ExistingModelPreflight",
    )

    snapshot_observation_keys = {
        (observation.fact_id, observation.source_plane)
        for source_snapshot in base_facts.source_snapshots
        for observation in source_snapshot.observations
    }
    explicit_observations = tuple(
        observation
        for observation in base_facts.fact_observations
        if (observation.fact_id, observation.source_plane)
        not in snapshot_observation_keys
        and observation.source_plane != TASK_FACT_SOURCE_CURRENT_MODEL
    )
    source_snapshots = tuple(
        source_snapshot
        for source_snapshot in base_facts.source_snapshots
        if source_snapshot.source_plane != TASK_FACT_SOURCE_CURRENT_MODEL
    ) + (snapshot,)
    return replace(
        base_facts,
        fact_observations=explicit_observations,
        source_snapshots=source_snapshots,
        related_model_ids=tuple(
            sorted(
                set(base_facts.related_model_ids)
                | {model.model_id for model in preflight.relevant_models}
            )
        ),
        affected_surface_ids=tuple(
            sorted(
                set(base_facts.affected_surface_ids)
                | set(preflight.expected_surface_ids)
                | set(report.covered_surface_ids)
                | set(report.scoped_surface_ids)
                | set(report.missing_surface_ids)
            )
        ),
    )


def project_existing_model_preflight_resolution(
    facts: TaskFacts,
    demand: TaskCoverageDemand,
    preflight: ExistingModelPreflight,
    report: ExistingModelPreflightReport,
    proof: ProofArtifactRef | Mapping[str, Any],
) -> OwnerCoverageResolution:
    """Project the same preflight proof into the sole owner-resolution value."""

    proof_ref = coerce_proof_artifact_ref(proof)
    owned_rows = tuple(
        row
        for row in demand.rows
        if row.triggered and row.owner_route == "existing_model_preflight"
    )
    if demand.task_id != facts.task_id or demand.task_fingerprint != facts.fingerprint:
        raise ValueError("preflight resolution requires the exact task demand")
    if not owned_rows:
        raise ValueError("task demand does not require existing-model preflight")
    obligations = tuple(
        sorted(
            {
                coverage_id
                for row in owned_rows
                for coverage_id in row.coverage_ids
            }
            | set(existing_model_preflight_projection_obligation_ids(preflight, report))
        )
    )
    proof_gaps = list(_validate_current_preflight_proof(preflight, report, proof_ref))
    snapshot = next(
        (
            value
            for value in facts.source_snapshots
            if value.source_plane == TASK_FACT_SOURCE_CURRENT_MODEL
        ),
        None,
    )
    if snapshot is None or snapshot.source_fingerprint != report.fingerprint:
        proof_gaps.append("existing_model_preflight_task_fact_snapshot_stale")
    blocker_codes = list(proof_gaps)
    blocker_codes.extend(
        finding.code for finding in report.findings if finding.severity == "blocker"
    )
    blocker_codes.extend(
        f"missing_surface:{surface_id}" for surface_id in report.missing_surface_ids
    )
    blocker_codes = list(dict.fromkeys(blocker_codes))
    disposition = (
        COVERAGE_DISPOSITION_SATISFIED
        if report.ok and not blocker_codes
        else COVERAGE_DISPOSITION_BLOCKED
    )
    resolution_payload = {
        "task_id": facts.task_id,
        "demand_id": demand.demand_id,
        "demand_fingerprint": demand.fingerprint,
        "preflight_id": preflight.preflight_id,
        "report_fingerprint": report.fingerprint,
        "proof_id": proof_ref.artifact_id,
        "disposition": disposition,
    }
    resolution_id = (
        "resolution:existing-model-preflight:"
        + fingerprint_value(resolution_payload).removeprefix("sha256:")[:20]
    )
    projection_artifact_id = f"proof:{resolution_id}"
    projection_fingerprint_values = {
        "preflight_report": report.fingerprint,
        "native_preflight_proof": fingerprint_value(proof_ref.to_dict()),
        **proof_ref.artifact_fingerprints,
    }
    evidence_fingerprints = tuple(
        sorted(set(projection_fingerprint_values.values()))
    )
    return OwnerCoverageResolution(
        resolution_id,
        facts.task_id,
        demand.demand_id,
        demand.fingerprint,
        "existing_model_preflight",
        disposition,
        obligations,
        evidence_ids=(
            (projection_artifact_id,)
            if disposition == COVERAGE_DISPOSITION_SATISFIED
            else ()
        ),
        evidence_fingerprints=(
            evidence_fingerprints
            if disposition == COVERAGE_DISPOSITION_SATISFIED
            else ()
        ),
        blocker_codes=tuple(blocker_codes),
    )


def project_existing_model_preflight_maturation_contribution(
    facts: TaskFacts,
    demand: TaskCoverageDemand,
    preflight: ExistingModelPreflight,
    report: ExistingModelPreflightReport,
    proof: ProofArtifactRef | Mapping[str, Any],
    *,
    candidate_model_fingerprint: str,
):
    """Create the canonical maturation view without re-entering owner semantics."""

    from .model_maturation import ModelMaturationCoverageContribution

    proof_ref = coerce_proof_artifact_ref(proof)
    resolution = project_existing_model_preflight_resolution(
        facts, demand, preflight, report, proof_ref
    )
    projection_fingerprints = {
        "preflight_report": report.fingerprint,
        "native_preflight_proof": fingerprint_value(proof_ref.to_dict()),
        **proof_ref.artifact_fingerprints,
    }
    projected_proof = replace(
        proof_ref,
        artifact_id=(
            resolution.evidence_ids[0]
            if resolution.evidence_ids
            else f"proof:{resolution.resolution_id}:blocked"
        ),
        subject_id=resolution.resolution_id,
        subject_fingerprint=resolution.resolution_fingerprint,
        artifact_fingerprints=projection_fingerprints,
        covered_obligation_ids=resolution.obligation_ids,
    )
    return ModelMaturationCoverageContribution(
        f"contribution:{resolution.resolution_id}",
        owner_route=resolution.owner_route,
        task_id=facts.task_id,
        coverage_source_refs=(preflight.preflight_id, proof_ref.artifact_id),
        coverage_ids=resolution.obligation_ids,
        required_probe_ids=(f"probe:{preflight.preflight_id}",),
        evidence_ref=projected_proof,
        owner_resolution=resolution,
        candidate_model_fingerprint=candidate_model_fingerprint,
        subject_fingerprints=dict(projected_proof.artifact_fingerprints),
    )


__all__ = [
    "BlueprintPreflightHandoff",
    "DUPLICATE_RISK_RESOLUTIONS",
    "ExistingModelPreflight",
    "ExistingModelPreflightFinding",
    "ExistingModelPreflightReport",
    "ExistingIntentSurface",
    "ExistingOwnershipSnapshot",
    "DuplicateBoundaryRisk",
    "ModelContextHit",
    "PREFLIGHT_INVENTORY_BROAD",
    "PREFLIGHT_INVENTORY_SCOPES",
    "PREFLIGHT_INVENTORY_SELECTED",
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
    "existing_model_preflight_projection_obligation_ids",
    "project_existing_model_preflight_maturation_contribution",
    "project_existing_model_preflight_blueprint_handoff",
    "project_existing_model_preflight_resolution",
    "project_existing_model_preflight_to_task_facts",
    "review_existing_model_preflight",
    "existing_model_preflight_from_project",
]
