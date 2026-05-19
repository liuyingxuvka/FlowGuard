"""Hierarchical model-mesh governance helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable


OWNERSHIP_CHILD = "child"
OWNERSHIP_PARENT = "parent"
OWNERSHIP_READ_ONLY = "read_only"
OWNERSHIP_SHARED_KERNEL = "shared_kernel"
OWNING_MODES = {OWNERSHIP_CHILD, OWNERSHIP_PARENT, OWNERSHIP_SHARED_KERNEL}
ALLOWED_OWNERSHIP = OWNING_MODES | {OWNERSHIP_READ_ONLY}

EVIDENCE_CANDIDATE_ONLY = "candidate_only"
EVIDENCE_ABSTRACT_GREEN = "abstract_green"
EVIDENCE_HAZARD_GREEN = "hazard_green"
EVIDENCE_LIVE_CURRENT_GREEN = "live_current_green"
EVIDENCE_CONFORMANCE_GREEN = "conformance_green"
EVIDENCE_MESH_GREEN = "mesh_green"

MESH_CLOSURE_NORMAL_EXIT = "normal_exit"
MESH_CLOSURE_FAILURE_EXIT = "failure_exit"
MESH_CLOSURE_OUT_OF_SCOPE = "out_of_scope"
MESH_CLOSURE_TERMINAL_SIDE_EFFECT = "terminal_side_effect"
ALLOWED_MESH_CLOSURE_TERMINALS = {
    MESH_CLOSURE_NORMAL_EXIT,
    MESH_CLOSURE_FAILURE_EXIT,
    MESH_CLOSURE_OUT_OF_SCOPE,
    MESH_CLOSURE_TERMINAL_SIDE_EFFECT,
}

DEFAULT_LARGE_MODEL_STATE_THRESHOLD = 10_000

BOUNDARY_PROPAGATION_UNAFFECTED = "unaffected"
BOUNDARY_PROPAGATION_REATTACH_ONLY = "reattach_only"
BOUNDARY_PROPAGATION_PARENT_RERUN_REQUIRED = "parent_rerun_required"
BOUNDARY_PROPAGATION_SIBLING_RERUN_REQUIRED = "sibling_rerun_required"
BOUNDARY_PROPAGATION_SPLIT_REVIEW_REQUIRED = "split_review_required"
ALLOWED_BOUNDARY_PROPAGATION = {
    BOUNDARY_PROPAGATION_UNAFFECTED,
    BOUNDARY_PROPAGATION_REATTACH_ONLY,
    BOUNDARY_PROPAGATION_PARENT_RERUN_REQUIRED,
    BOUNDARY_PROPAGATION_SIBLING_RERUN_REQUIRED,
    BOUNDARY_PROPAGATION_SPLIT_REVIEW_REQUIRED,
}

_BOUNDARY_SEQUENCE_FIELDS = (
    "functions_owned",
    "inputs_accepted",
    "outputs_emitted",
    "state_owned",
    "side_effects_owned",
    "functional_areas",
    "invariants_owned",
    "contracts_in",
    "contracts_out",
    "depends_on",
    "risk_classes",
    "validation_evidence",
)
_PARENT_RERUN_FIELDS = {
    "functions_owned",
    "inputs_accepted",
    "outputs_emitted",
    "contracts_in",
    "contracts_out",
    "depends_on",
    "risk_boundary",
    "risk_classes",
    "validation_evidence",
}
_SIBLING_RERUN_FIELDS = {
    "functions_owned",
    "state_owned",
    "side_effects_owned",
    "functional_areas",
    "invariants_owned",
    "contracts_out",
    "risk_classes",
}


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


def _as_tuple_mapping(values: Mapping[str, Sequence[str]] | None) -> dict[str, tuple[str, ...]]:
    if values is None:
        return {}
    return {
        str(key): _as_tuple(value)
        for key, value in sorted(values.items(), key=lambda item: str(item[0]))
    }


@dataclass(frozen=True)
class HierarchyCoverageItem:
    """One parent-space item that must be owned, shared, or explicitly read-only."""

    item_id: str
    item_type: str = "function"
    owner_model_id: str = ""
    ownership: str = OWNERSHIP_CHILD
    description: str = ""
    allowed_shared_with: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_id", str(self.item_id))
        object.__setattr__(self, "item_type", str(self.item_type))
        object.__setattr__(self, "owner_model_id", str(self.owner_model_id))
        object.__setattr__(self, "ownership", str(self.ownership))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "allowed_shared_with", _as_tuple(self.allowed_shared_with))

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_type": self.item_type,
            "owner_model_id": self.owner_model_id,
            "ownership": self.ownership,
            "description": self.description,
            "allowed_shared_with": list(self.allowed_shared_with),
        }


@dataclass(frozen=True)
class ChildModelEvidence:
    """Contract and evidence summary for one child model."""

    model_id: str
    evidence_id: str = ""
    risk_boundary: str = ""
    inputs_accepted: tuple[str, ...] = ()
    outputs_emitted: tuple[str, ...] = ()
    state_owned: tuple[str, ...] = ()
    side_effects_owned: tuple[str, ...] = ()
    functional_areas: tuple[str, ...] = ()
    contracts_in: tuple[str, ...] = ()
    contracts_out: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    evidence_tier: str = EVIDENCE_CANDIDATE_ONLY
    evidence_current: bool = True
    skipped_checks: tuple[str, ...] = ()
    not_run_checks: tuple[str, ...] = ()
    estimated_state_count: int | None = None
    observed_state_count: int | None = None
    budgeted_incomplete: bool = False
    unrelated_functional_areas: bool = False
    structurally_cohesive: bool = True
    is_legacy: bool = False
    has_compatibility_contract: bool = True
    overlaps_existing_model: str = ""
    functions_owned: tuple[str, ...] = ()
    invariants_owned: tuple[str, ...] = ()
    risk_classes: tuple[str, ...] = ()
    validation_evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "risk_boundary", str(self.risk_boundary))
        object.__setattr__(self, "functions_owned", _as_tuple(self.functions_owned))
        object.__setattr__(self, "inputs_accepted", _as_tuple(self.inputs_accepted))
        object.__setattr__(self, "outputs_emitted", _as_tuple(self.outputs_emitted))
        object.__setattr__(self, "state_owned", _as_tuple(self.state_owned))
        object.__setattr__(self, "side_effects_owned", _as_tuple(self.side_effects_owned))
        object.__setattr__(self, "functional_areas", _as_tuple(self.functional_areas))
        object.__setattr__(self, "invariants_owned", _as_tuple(self.invariants_owned))
        object.__setattr__(self, "contracts_in", _as_tuple(self.contracts_in))
        object.__setattr__(self, "contracts_out", _as_tuple(self.contracts_out))
        object.__setattr__(self, "depends_on", _as_tuple(self.depends_on))
        object.__setattr__(self, "risk_classes", _as_tuple(self.risk_classes))
        object.__setattr__(self, "validation_evidence", _as_tuple(self.validation_evidence))
        object.__setattr__(self, "evidence_tier", str(self.evidence_tier))
        object.__setattr__(self, "skipped_checks", _as_tuple(self.skipped_checks))
        object.__setattr__(self, "not_run_checks", _as_tuple(self.not_run_checks))
        object.__setattr__(self, "overlaps_existing_model", str(self.overlaps_existing_model))

    def largest_state_count(self) -> int:
        counts = [
            count
            for count in (self.estimated_state_count, self.observed_state_count)
            if count is not None
        ]
        return max(counts) if counts else 0

    def requires_large_model_review(self, threshold: int = DEFAULT_LARGE_MODEL_STATE_THRESHOLD) -> bool:
        return (
            self.largest_state_count() > threshold
            or self.budgeted_incomplete
            or self.unrelated_functional_areas
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "evidence_id": self.evidence_id,
            "risk_boundary": self.risk_boundary,
            "functions_owned": list(self.functions_owned),
            "inputs_accepted": list(self.inputs_accepted),
            "outputs_emitted": list(self.outputs_emitted),
            "state_owned": list(self.state_owned),
            "side_effects_owned": list(self.side_effects_owned),
            "functional_areas": list(self.functional_areas),
            "invariants_owned": list(self.invariants_owned),
            "contracts_in": list(self.contracts_in),
            "contracts_out": list(self.contracts_out),
            "depends_on": list(self.depends_on),
            "risk_classes": list(self.risk_classes),
            "validation_evidence": list(self.validation_evidence),
            "evidence_tier": self.evidence_tier,
            "evidence_current": self.evidence_current,
            "skipped_checks": list(self.skipped_checks),
            "not_run_checks": list(self.not_run_checks),
            "estimated_state_count": self.estimated_state_count,
            "observed_state_count": self.observed_state_count,
            "budgeted_incomplete": self.budgeted_incomplete,
            "unrelated_functional_areas": self.unrelated_functional_areas,
            "structurally_cohesive": self.structurally_cohesive,
            "is_legacy": self.is_legacy,
            "has_compatibility_contract": self.has_compatibility_contract,
            "overlaps_existing_model": self.overlaps_existing_model,
        }


@dataclass(frozen=True)
class ChildBoundaryChangeSummary:
    """Boundary diff summary a parent mesh can consume without inlining child state."""

    child_model_id: str
    propagation: str = BOUNDARY_PROPAGATION_UNAFFECTED
    previous_evidence_id: str = ""
    current_evidence_id: str = ""
    changed_fields: tuple[str, ...] = ()
    added_by_field: Mapping[str, Sequence[str]] = field(default_factory=dict)
    removed_by_field: Mapping[str, Sequence[str]] = field(default_factory=dict)
    previous_risk_boundary: str = ""
    current_risk_boundary: str = ""
    current_bug_id: str = ""
    known_bug_ids: tuple[str, ...] = ()
    generalized_target: str = ""
    current_bug_is_only_model_target: bool = False
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "child_model_id", str(self.child_model_id))
        object.__setattr__(self, "propagation", str(self.propagation))
        object.__setattr__(self, "previous_evidence_id", str(self.previous_evidence_id))
        object.__setattr__(self, "current_evidence_id", str(self.current_evidence_id))
        object.__setattr__(self, "changed_fields", _as_tuple(self.changed_fields))
        object.__setattr__(self, "added_by_field", _as_tuple_mapping(self.added_by_field))
        object.__setattr__(self, "removed_by_field", _as_tuple_mapping(self.removed_by_field))
        object.__setattr__(self, "previous_risk_boundary", str(self.previous_risk_boundary))
        object.__setattr__(self, "current_risk_boundary", str(self.current_risk_boundary))
        object.__setattr__(self, "current_bug_id", str(self.current_bug_id))
        object.__setattr__(self, "known_bug_ids", _as_tuple(self.known_bug_ids))
        object.__setattr__(self, "generalized_target", str(self.generalized_target))
        object.__setattr__(
            self,
            "current_bug_is_only_model_target",
            bool(self.current_bug_is_only_model_target),
        )
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "child_model_id": self.child_model_id,
            "propagation": self.propagation,
            "previous_evidence_id": self.previous_evidence_id,
            "current_evidence_id": self.current_evidence_id,
            "changed_fields": list(self.changed_fields),
            "added_by_field": {
                key: list(values) for key, values in self.added_by_field.items()
            },
            "removed_by_field": {
                key: list(values) for key, values in self.removed_by_field.items()
            },
            "previous_risk_boundary": self.previous_risk_boundary,
            "current_risk_boundary": self.current_risk_boundary,
            "current_bug_id": self.current_bug_id,
            "known_bug_ids": list(self.known_bug_ids),
            "generalized_target": self.generalized_target,
            "current_bug_is_only_model_target": self.current_bug_is_only_model_target,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ModelTargetSplitDerivation:
    """Model-derived target child layout for one parent ModelMesh boundary."""

    source_model_id: str
    target_child_model_ids: tuple[str, ...] = ()
    covered_partition_item_ids: tuple[str, ...] = ()
    state_owner_fields: tuple[str, ...] = ()
    side_effect_owner_fields: tuple[str, ...] = ()
    source_model_path: str = ""
    rationale: str = ""
    derived_from_flowguard_model: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_model_id", str(self.source_model_id))
        object.__setattr__(self, "target_child_model_ids", _as_tuple(self.target_child_model_ids))
        object.__setattr__(self, "covered_partition_item_ids", _as_tuple(self.covered_partition_item_ids))
        object.__setattr__(self, "state_owner_fields", _as_tuple(self.state_owner_fields))
        object.__setattr__(self, "side_effect_owner_fields", _as_tuple(self.side_effect_owner_fields))
        object.__setattr__(self, "source_model_path", str(self.source_model_path))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_model_id": self.source_model_id,
            "target_child_model_ids": list(self.target_child_model_ids),
            "covered_partition_item_ids": list(self.covered_partition_item_ids),
            "state_owner_fields": list(self.state_owner_fields),
            "side_effect_owner_fields": list(self.side_effect_owner_fields),
            "source_model_path": self.source_model_path,
            "rationale": self.rationale,
            "derived_from_flowguard_model": self.derived_from_flowguard_model,
        }


@dataclass(frozen=True)
class ChildReattachmentContract:
    """Parent expectations for one child model's handoff back into the mesh."""

    child_model_id: str
    consumed_evidence_id: str = ""
    expected_inputs: tuple[str, ...] = ()
    expected_outputs: tuple[str, ...] = ()
    expected_state_owned: tuple[str, ...] = ()
    expected_side_effects_owned: tuple[str, ...] = ()
    expected_contracts_out: tuple[str, ...] = ()
    allow_extra_inputs: bool = False
    allow_extra_outputs: bool = False
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "child_model_id", str(self.child_model_id))
        object.__setattr__(self, "consumed_evidence_id", str(self.consumed_evidence_id))
        object.__setattr__(self, "expected_inputs", _as_tuple(self.expected_inputs))
        object.__setattr__(self, "expected_outputs", _as_tuple(self.expected_outputs))
        object.__setattr__(self, "expected_state_owned", _as_tuple(self.expected_state_owned))
        object.__setattr__(self, "expected_side_effects_owned", _as_tuple(self.expected_side_effects_owned))
        object.__setattr__(self, "expected_contracts_out", _as_tuple(self.expected_contracts_out))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "child_model_id": self.child_model_id,
            "consumed_evidence_id": self.consumed_evidence_id,
            "expected_inputs": list(self.expected_inputs),
            "expected_outputs": list(self.expected_outputs),
            "expected_state_owned": list(self.expected_state_owned),
            "expected_side_effects_owned": list(self.expected_side_effects_owned),
            "expected_contracts_out": list(self.expected_contracts_out),
            "allow_extra_inputs": self.allow_extra_inputs,
            "allow_extra_outputs": self.allow_extra_outputs,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class MeshClosureTransition:
    """One model-to-model closure transition over abstract handoff tokens."""

    transition_id: str
    consumes: tuple[str, ...] = ()
    emits: tuple[str, ...] = ()
    consumer_model_id: str = ""
    loop: bool = False
    progress_rule: str = ""
    max_iterations: int | None = None
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "transition_id", str(self.transition_id))
        object.__setattr__(self, "consumes", _as_tuple(self.consumes))
        object.__setattr__(self, "emits", _as_tuple(self.emits))
        object.__setattr__(self, "consumer_model_id", str(self.consumer_model_id))
        object.__setattr__(self, "loop", bool(self.loop))
        if self.max_iterations is not None:
            object.__setattr__(self, "max_iterations", int(self.max_iterations))
        object.__setattr__(self, "progress_rule", str(self.progress_rule))
        object.__setattr__(self, "rationale", str(self.rationale))

    def has_progress_rule(self) -> bool:
        return bool(self.progress_rule) or self.max_iterations is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "consumes": list(self.consumes),
            "emits": list(self.emits),
            "consumer_model_id": self.consumer_model_id,
            "loop": self.loop,
            "progress_rule": self.progress_rule,
            "max_iterations": self.max_iterations,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class MeshClosureJoin:
    """A parent-level join point that must consume all required handoff tokens."""

    join_id: str
    required_inputs: tuple[str, ...] = ()
    emits: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "join_id", str(self.join_id))
        object.__setattr__(self, "required_inputs", _as_tuple(self.required_inputs))
        object.__setattr__(self, "emits", _as_tuple(self.emits))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "join_id": self.join_id,
            "required_inputs": list(self.required_inputs),
            "emits": list(self.emits),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class MeshClosureTerminal:
    """A terminal or explicit disposition for closure tokens."""

    terminal_id: str
    consumes: tuple[str, ...] = ()
    terminal_kind: str = MESH_CLOSURE_NORMAL_EXIT
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "terminal_id", str(self.terminal_id))
        object.__setattr__(self, "consumes", _as_tuple(self.consumes))
        object.__setattr__(self, "terminal_kind", str(self.terminal_kind))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "terminal_id": self.terminal_id,
            "consumes": list(self.consumes),
            "terminal_kind": self.terminal_kind,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class MeshClosureModel:
    """FlowGuard-style meta-model for parent/child model handoff closure."""

    parent_model_id: str
    root_entries: tuple[str, ...] = ()
    transitions: tuple[MeshClosureTransition, ...] = ()
    joins: tuple[MeshClosureJoin, ...] = ()
    terminals: tuple[MeshClosureTerminal, ...] = ()
    required_outputs: tuple[str, ...] = ()
    require_normal_exit: bool = True
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "parent_model_id", str(self.parent_model_id))
        object.__setattr__(self, "root_entries", _as_tuple(self.root_entries))
        object.__setattr__(self, "transitions", tuple(self.transitions))
        object.__setattr__(self, "joins", tuple(self.joins))
        object.__setattr__(self, "terminals", tuple(self.terminals))
        object.__setattr__(self, "required_outputs", _as_tuple(self.required_outputs))
        object.__setattr__(self, "require_normal_exit", bool(self.require_normal_exit))
        object.__setattr__(self, "rationale", str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_model_id": self.parent_model_id,
            "root_entries": list(self.root_entries),
            "transitions": [transition.to_dict() for transition in self.transitions],
            "joins": [join.to_dict() for join in self.joins],
            "terminals": [terminal.to_dict() for terminal in self.terminals],
            "required_outputs": list(self.required_outputs),
            "require_normal_exit": self.require_normal_exit,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class MeshClosureFinding:
    """One closure-model finding from the executable handoff meta-model."""

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
class MeshClosureReport:
    """Structured outcome of a mesh closure meta-model review."""

    ok: bool
    parent_model_id: str
    decision: str
    findings: tuple[MeshClosureFinding, ...] = ()
    reachable_tokens: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "parent_model_id", str(self.parent_model_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "reachable_tokens", _as_tuple(self.reachable_tokens))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: parent={self.parent_model_id} closure_decision={self.decision} findings={len(self.findings)}",
            )

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard mesh closure review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"parent: {self.parent_model_id}",
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
            "parent_model_id": self.parent_model_id,
            "decision": self.decision,
            "findings": [finding.to_dict() for finding in self.findings],
            "reachable_tokens": list(self.reachable_tokens),
            "summary": self.summary,
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(to_jsonable(self.to_dict()), indent=indent, sort_keys=True)


@dataclass(frozen=True)
class HierarchyPartitionMap:
    """Partition map for one parent model boundary."""

    parent_model_id: str
    coverage_items: tuple[HierarchyCoverageItem, ...] = ()
    child_models: tuple[ChildModelEvidence, ...] = ()
    target_split_derivation: ModelTargetSplitDerivation | None = None
    reattachment_contracts: tuple[ChildReattachmentContract, ...] = ()
    required_evidence_tier: str = EVIDENCE_ABSTRACT_GREEN
    allowed_shared_areas: tuple[str, ...] = ()
    boundary_changes: tuple[ChildBoundaryChangeSummary, ...] = ()
    closure_model: MeshClosureModel | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "parent_model_id", str(self.parent_model_id))
        object.__setattr__(self, "coverage_items", tuple(self.coverage_items))
        object.__setattr__(self, "child_models", tuple(self.child_models))
        object.__setattr__(self, "reattachment_contracts", tuple(self.reattachment_contracts))
        object.__setattr__(self, "required_evidence_tier", str(self.required_evidence_tier))
        object.__setattr__(self, "allowed_shared_areas", _as_tuple(self.allowed_shared_areas))
        object.__setattr__(self, "boundary_changes", tuple(self.boundary_changes))

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_model_id": self.parent_model_id,
            "coverage_items": [item.to_dict() for item in self.coverage_items],
            "child_models": [child.to_dict() for child in self.child_models],
            "target_split_derivation": (
                self.target_split_derivation.to_dict()
                if self.target_split_derivation is not None
                else None
            ),
            "reattachment_contracts": [
                contract.to_dict() for contract in self.reattachment_contracts
            ],
            "required_evidence_tier": self.required_evidence_tier,
            "allowed_shared_areas": list(self.allowed_shared_areas),
            "boundary_changes": [summary.to_dict() for summary in self.boundary_changes],
            "closure_model": (
                self.closure_model.to_dict() if self.closure_model is not None else None
            ),
        }


@dataclass(frozen=True)
class HierarchyMeshFinding:
    """One partition, overlap, evidence, or legacy finding from a mesh review."""

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
class HierarchyMeshReport:
    """Structured outcome of a hierarchical mesh review."""

    ok: bool
    parent_model_id: str
    decision: str
    activation_reasons: tuple[str, ...] = ()
    findings: tuple[HierarchyMeshFinding, ...] = ()
    split_decisions: Mapping[str, str] = field(default_factory=dict)
    summary: str = ""
    boundary_change_decisions: Mapping[str, str] = field(default_factory=dict)
    closure_report: MeshClosureReport | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "parent_model_id", str(self.parent_model_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "activation_reasons", _as_tuple(self.activation_reasons))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "split_decisions", dict(self.split_decisions))
        object.__setattr__(self, "boundary_change_decisions", dict(self.boundary_change_decisions))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: parent={self.parent_model_id} decision={self.decision} findings={len(self.findings)}",
            )

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard hierarchical mesh review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"parent: {self.parent_model_id}",
            f"decision: {self.decision}",
            f"activation_reasons: {', '.join(self.activation_reasons) if self.activation_reasons else '(none)'}",
            f"findings: {len(self.findings)}",
        ]
        if self.split_decisions:
            lines.append("split_decisions:")
            for model_id, decision in sorted(self.split_decisions.items()):
                lines.append(f"  - {model_id}: {decision}")
        if self.boundary_change_decisions:
            lines.append("boundary_change_decisions:")
            for model_id, decision in sorted(self.boundary_change_decisions.items()):
                lines.append(f"  - {model_id}: {decision}")
        if self.closure_report is not None:
            lines.append(f"closure_decision: {self.closure_report.decision}")
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
            "parent_model_id": self.parent_model_id,
            "decision": self.decision,
            "activation_reasons": list(self.activation_reasons),
            "findings": [finding.to_dict() for finding in self.findings],
            "split_decisions": to_jsonable(dict(self.split_decisions)),
            "summary": self.summary,
            "boundary_change_decisions": to_jsonable(dict(self.boundary_change_decisions)),
            "closure_report": (
                self.closure_report.to_dict() if self.closure_report is not None else None
            ),
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(to_jsonable(self.to_dict()), indent=indent, sort_keys=True)


@dataclass(frozen=True)
class LegacyModelRecord:
    """Discovery-time facts about an existing FlowGuard model."""

    model_id: str
    model_file: str = ""
    has_compatibility_contract: bool = False
    estimated_state_count: int | None = None
    observed_state_count: int | None = None
    budgeted_incomplete: bool = False
    functional_area_count: int = 1
    evidence_current: bool = True
    skipped_checks: tuple[str, ...] = ()
    not_run_checks: tuple[str, ...] = ()
    overlaps_existing_model: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "model_file", str(self.model_file))
        object.__setattr__(self, "skipped_checks", _as_tuple(self.skipped_checks))
        object.__setattr__(self, "not_run_checks", _as_tuple(self.not_run_checks))
        object.__setattr__(self, "overlaps_existing_model", str(self.overlaps_existing_model))


@dataclass(frozen=True)
class LegacyModelClassification:
    """Compatibility classification for a legacy model."""

    model_id: str
    labels: tuple[str, ...]
    requires_split_review: bool = False
    can_be_strong_evidence: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "labels": list(self.labels),
            "requires_split_review": self.requires_split_review,
            "can_be_strong_evidence": self.can_be_strong_evidence,
            "reason": self.reason,
        }


def _evidence_rank(tier: str) -> int:
    order = {
        EVIDENCE_CANDIDATE_ONLY: 0,
        EVIDENCE_ABSTRACT_GREEN: 1,
        EVIDENCE_HAZARD_GREEN: 2,
        EVIDENCE_LIVE_CURRENT_GREEN: 3,
        EVIDENCE_CONFORMANCE_GREEN: 4,
        EVIDENCE_MESH_GREEN: 5,
    }
    return order.get(str(tier), -1)


def _is_large_child(child: ChildModelEvidence, threshold: int) -> bool:
    return child.requires_large_model_review(threshold)


@dataclass(frozen=True)
class _ClosureState:
    available: frozenset[str]
    consumed: frozenset[str] = frozenset()
    completed_joins: frozenset[str] = frozenset()
    terminal_kind: str = ""


def _child_output_tokens(child_models: Sequence[ChildModelEvidence]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                output
                for child in child_models
                for output in child.outputs_emitted
            }
        )
    )


def _closure_consumed_tokens(model: MeshClosureModel) -> set[str]:
    tokens: set[str] = set()
    for transition in model.transitions:
        tokens.update(transition.consumes)
    for join in model.joins:
        tokens.update(join.required_inputs)
    for terminal in model.terminals:
        tokens.update(terminal.consumes)
    return tokens


def _closure_known_tokens(model: MeshClosureModel, child_models: Sequence[ChildModelEvidence]) -> set[str]:
    tokens = set(model.root_entries)
    tokens.update(model.required_outputs)
    tokens.update(_child_output_tokens(child_models))
    for transition in model.transitions:
        tokens.update(transition.emits)
    for join in model.joins:
        tokens.update(join.emits)
    return tokens


def _mesh_closure_decision(findings: Sequence[MeshClosureFinding]) -> str:
    blocking = [finding for finding in findings if finding.severity in {"blocker", "refactor"}]
    if not blocking:
        return "mesh_closure_green"
    priority = (
        "missing_root_entry",
        "unknown_closure_reference",
        "unknown_closure_consumer",
        "out_of_scope_rationale_required",
        "loop_progress_required",
        "unconsumed_child_output",
        "unreachable_required_output",
        "missing_join_point",
        "terminal_leak",
        "unreachable_normal_exit",
    )
    codes = {finding.code for finding in blocking}
    for code in priority:
        if code in codes:
            return code
    return "mesh_closure_blocked"


def review_mesh_closure_model(
    closure_model: MeshClosureModel,
    child_models: Sequence[ChildModelEvidence] = (),
) -> MeshClosureReport:
    """Review model-to-model handoff closure without expanding child internals."""

    findings: list[MeshClosureFinding] = []
    children = {child.model_id: child for child in child_models}
    known_models = set(children) | {closure_model.parent_model_id}
    child_outputs = set(_child_output_tokens(child_models))
    required_outputs = set(closure_model.required_outputs) | child_outputs
    consumed_tokens = _closure_consumed_tokens(closure_model)

    if not closure_model.root_entries:
        findings.append(
            MeshClosureFinding(
                "missing_root_entry",
                "mesh closure model has no parent entry token",
                model_id=closure_model.parent_model_id,
            )
        )

    known_tokens = _closure_known_tokens(closure_model, child_models)
    for token in sorted(consumed_tokens - known_tokens):
        findings.append(
            MeshClosureFinding(
                "unknown_closure_reference",
                "closure item consumes a token that is never produced or declared",
                model_id=closure_model.parent_model_id,
                item_id=token,
            )
        )

    for transition in closure_model.transitions:
        if transition.consumer_model_id and transition.consumer_model_id not in known_models:
            findings.append(
                MeshClosureFinding(
                    "unknown_closure_consumer",
                    "closure transition names an unregistered consumer model",
                    model_id=transition.consumer_model_id,
                    item_id=transition.transition_id,
                    metadata=transition.to_dict(),
                )
            )
        if transition.loop and not transition.has_progress_rule():
            findings.append(
                MeshClosureFinding(
                    "loop_progress_required",
                    "loop-like closure transition lacks a bound or progress rule",
                    model_id=transition.consumer_model_id or closure_model.parent_model_id,
                    item_id=transition.transition_id,
                    metadata=transition.to_dict(),
                )
            )

    for terminal in closure_model.terminals:
        if terminal.terminal_kind not in ALLOWED_MESH_CLOSURE_TERMINALS:
            findings.append(
                MeshClosureFinding(
                    "unknown_terminal_disposition",
                    "closure terminal uses an unknown disposition",
                    model_id=closure_model.parent_model_id,
                    item_id=terminal.terminal_id,
                    metadata=terminal.to_dict(),
                )
            )
        if terminal.terminal_kind == MESH_CLOSURE_OUT_OF_SCOPE and not terminal.rationale:
            findings.append(
                MeshClosureFinding(
                    "out_of_scope_rationale_required",
                    "out-of-scope closure disposition needs an explicit rationale",
                    model_id=closure_model.parent_model_id,
                    item_id=terminal.terminal_id,
                    metadata=terminal.to_dict(),
                )
            )

    for output in sorted(required_outputs - consumed_tokens):
        findings.append(
            MeshClosureFinding(
                "unconsumed_child_output",
                "required child or closure output has no declared consumer",
                model_id=closure_model.parent_model_id,
                item_id=output,
                metadata={"required_outputs": sorted(required_outputs)},
            )
        )

    states: set[_ClosureState] = {
        _ClosureState(available=frozenset(closure_model.root_entries))
    }
    changed = True
    while changed:
        changed = False
        next_states = set(states)
        for state in states:
            if state.terminal_kind:
                continue
            for transition in closure_model.transitions:
                consumes = frozenset(transition.consumes)
                if consumes.issubset(state.available):
                    candidate = _ClosureState(
                        available=state.available | frozenset(transition.emits),
                        consumed=state.consumed | consumes,
                        completed_joins=state.completed_joins,
                    )
                    if candidate not in next_states:
                        next_states.add(candidate)
                        changed = True
            for join in closure_model.joins:
                required = frozenset(join.required_inputs)
                if required.issubset(state.available):
                    candidate = _ClosureState(
                        available=state.available | frozenset(join.emits),
                        consumed=state.consumed | required,
                        completed_joins=state.completed_joins | frozenset({join.join_id}),
                    )
                    if candidate not in next_states:
                        next_states.add(candidate)
                        changed = True
            for terminal in closure_model.terminals:
                consumes = frozenset(terminal.consumes)
                if consumes.issubset(state.available):
                    candidate = _ClosureState(
                        available=state.available,
                        consumed=state.consumed | consumes,
                        completed_joins=state.completed_joins,
                        terminal_kind=terminal.terminal_kind,
                    )
                    if candidate not in next_states:
                        next_states.add(candidate)
                        changed = True
        states = next_states

    reachable_tokens = tuple(sorted({token for state in states for token in state.available}))
    reachable_required = set(reachable_tokens) & required_outputs
    for output in sorted(required_outputs - reachable_required):
        findings.append(
            MeshClosureFinding(
                "unreachable_required_output",
                "required child or closure output is not reachable from a root entry",
                model_id=closure_model.parent_model_id,
                item_id=output,
                metadata={"reachable_tokens": reachable_tokens},
            )
        )

    for join in closure_model.joins:
        if not any(join.join_id in state.completed_joins for state in states):
            missing = tuple(sorted(set(join.required_inputs) - set(reachable_tokens)))
            findings.append(
                MeshClosureFinding(
                    "missing_join_point",
                    "required join point is not completed by reachable closure tokens",
                    model_id=closure_model.parent_model_id,
                    item_id=join.join_id,
                    metadata={"join": join.to_dict(), "missing_inputs": missing},
                )
            )

    terminal_states = [state for state in states if state.terminal_kind]
    for state in terminal_states:
        pending = tuple(sorted(required_outputs - set(state.consumed)))
        if pending:
            findings.append(
                MeshClosureFinding(
                    "terminal_leak",
                    "closure reaches a terminal disposition with pending required outputs",
                    model_id=closure_model.parent_model_id,
                    metadata={
                        "terminal_kind": state.terminal_kind,
                        "pending_outputs": pending,
                    },
                )
            )

    if closure_model.require_normal_exit and not any(
        state.terminal_kind == MESH_CLOSURE_NORMAL_EXIT and not (required_outputs - set(state.consumed))
        for state in terminal_states
    ):
        findings.append(
            MeshClosureFinding(
                "unreachable_normal_exit",
                "closure model does not reach a normal exit with all required outputs consumed",
                model_id=closure_model.parent_model_id,
                metadata={"reachable_tokens": reachable_tokens},
            )
        )

    decision = _mesh_closure_decision(findings)
    blocking = [finding for finding in findings if finding.severity in {"blocker", "refactor"}]
    return MeshClosureReport(
        ok=not blocking,
        parent_model_id=closure_model.parent_model_id,
        decision=decision,
        findings=tuple(findings),
        reachable_tokens=reachable_tokens,
    )


def _split_decision(child: ChildModelEvidence, threshold: int) -> str:
    if not _is_large_child(child, threshold):
        return "not_large"
    if child.overlaps_existing_model:
        return "merge_with_existing_model"
    if child.unrelated_functional_areas or not child.structurally_cohesive:
        return "split_into_children"
    if child.budgeted_incomplete:
        return "continue_with_budgeted_execution_only"
    return "keep_as_single_model"


def _boundary_propagation_rank(status: str) -> int:
    order = {
        BOUNDARY_PROPAGATION_UNAFFECTED: 0,
        BOUNDARY_PROPAGATION_REATTACH_ONLY: 1,
        BOUNDARY_PROPAGATION_SIBLING_RERUN_REQUIRED: 2,
        BOUNDARY_PROPAGATION_PARENT_RERUN_REQUIRED: 3,
        BOUNDARY_PROPAGATION_SPLIT_REVIEW_REQUIRED: 4,
    }
    return order.get(str(status), -1)


def _strongest_boundary_propagation(statuses: Sequence[str]) -> str:
    valid = [str(status) for status in statuses if str(status) in ALLOWED_BOUNDARY_PROPAGATION]
    if not valid:
        return ""
    return max(valid, key=_boundary_propagation_rank)


def _diff_sequence_field(
    previous_child: ChildModelEvidence,
    current_child: ChildModelEvidence,
    field_name: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    previous_values = set(getattr(previous_child, field_name))
    current_values = set(getattr(current_child, field_name))
    return (
        tuple(sorted(current_values - previous_values)),
        tuple(sorted(previous_values - current_values)),
    )


def _has_parent_contract_drift(
    child: ChildModelEvidence,
    contract: ChildReattachmentContract | None,
) -> bool:
    if contract is None:
        return False
    if _missing_items(contract.expected_inputs, child.inputs_accepted):
        return True
    if not contract.allow_extra_inputs and _extra_items(contract.expected_inputs, child.inputs_accepted):
        return True
    if _missing_items(contract.expected_outputs, child.outputs_emitted):
        return True
    if not contract.allow_extra_outputs and _extra_items(contract.expected_outputs, child.outputs_emitted):
        return True
    return bool(
        _missing_items(contract.expected_state_owned, child.state_owned)
        or _missing_items(contract.expected_side_effects_owned, child.side_effects_owned)
        or _missing_items(contract.expected_contracts_out, child.contracts_out)
    )


def _has_sibling_boundary_overlap(
    child: ChildModelEvidence,
    sibling_models: Sequence[ChildModelEvidence],
) -> bool:
    overlap_fields = (
        "functions_owned",
        "state_owned",
        "side_effects_owned",
        "functional_areas",
        "invariants_owned",
        "contracts_out",
        "risk_classes",
    )
    for sibling in sibling_models:
        if sibling.model_id == child.model_id:
            continue
        for field_name in overlap_fields:
            if set(getattr(child, field_name)) & set(getattr(sibling, field_name)):
                return True
        if set(child.state_owned) & set(sibling.depends_on):
            return True
        if set(child.side_effects_owned) & set(sibling.depends_on):
            return True
        if set(child.contracts_out) & set(sibling.depends_on):
            return True
    return False


def summarize_child_boundary_change(
    previous_child: ChildModelEvidence,
    current_child: ChildModelEvidence,
    *,
    parent_contract: ChildReattachmentContract | None = None,
    sibling_models: Sequence[ChildModelEvidence] = (),
    current_bug_id: str = "",
    known_bug_ids: Sequence[str] = (),
    generalized_target: str = "",
    large_model_threshold: int = DEFAULT_LARGE_MODEL_STATE_THRESHOLD,
    rationale: str = "",
) -> ChildBoundaryChangeSummary:
    """Summarize child boundary drift for parent ModelMesh propagation."""

    if previous_child.model_id != current_child.model_id:
        raise ValueError("previous_child and current_child must describe the same model_id")

    added_by_field: dict[str, tuple[str, ...]] = {}
    removed_by_field: dict[str, tuple[str, ...]] = {}
    changed_fields: list[str] = []
    for field_name in _BOUNDARY_SEQUENCE_FIELDS:
        added, removed = _diff_sequence_field(previous_child, current_child, field_name)
        if added:
            added_by_field[field_name] = added
        if removed:
            removed_by_field[field_name] = removed
        if added or removed:
            changed_fields.append(field_name)

    if previous_child.risk_boundary != current_child.risk_boundary:
        changed_fields.append("risk_boundary")
    if previous_child.evidence_id != current_child.evidence_id:
        changed_fields.append("evidence_id")

    current_bug_text = str(current_bug_id)
    generalized_target_text = str(generalized_target)
    current_bug_is_only_target = bool(
        current_bug_text
        and current_child.risk_boundary == current_bug_text
        and not generalized_target_text
    )

    changed_field_set = set(changed_fields)
    parent_handoff_changed = bool(changed_field_set & _PARENT_RERUN_FIELDS)
    parent_handoff_changed = parent_handoff_changed or _has_parent_contract_drift(
        current_child,
        parent_contract,
    )
    sibling_boundary_changed = bool(changed_field_set & _SIBLING_RERUN_FIELDS)
    sibling_boundary_changed = sibling_boundary_changed or _has_sibling_boundary_overlap(
        current_child,
        sibling_models,
    )

    if _is_large_child(current_child, large_model_threshold):
        propagation = BOUNDARY_PROPAGATION_SPLIT_REVIEW_REQUIRED
    elif current_bug_is_only_target or parent_handoff_changed:
        propagation = BOUNDARY_PROPAGATION_PARENT_RERUN_REQUIRED
    elif sibling_boundary_changed:
        propagation = BOUNDARY_PROPAGATION_SIBLING_RERUN_REQUIRED
    elif previous_child.evidence_id != current_child.evidence_id:
        propagation = BOUNDARY_PROPAGATION_REATTACH_ONLY
    else:
        propagation = BOUNDARY_PROPAGATION_UNAFFECTED

    return ChildBoundaryChangeSummary(
        child_model_id=current_child.model_id,
        propagation=propagation,
        previous_evidence_id=previous_child.evidence_id,
        current_evidence_id=current_child.evidence_id,
        changed_fields=tuple(sorted(set(changed_fields))),
        added_by_field=added_by_field,
        removed_by_field=removed_by_field,
        previous_risk_boundary=previous_child.risk_boundary,
        current_risk_boundary=current_child.risk_boundary,
        current_bug_id=current_bug_text,
        known_bug_ids=_as_tuple(known_bug_ids),
        generalized_target=generalized_target_text,
        current_bug_is_only_model_target=current_bug_is_only_target,
        rationale=rationale,
    )


def classify_legacy_model(
    record: LegacyModelRecord,
    *,
    large_model_threshold: int = DEFAULT_LARGE_MODEL_STATE_THRESHOLD,
) -> LegacyModelClassification:
    """Classify one discovered legacy model without rewriting it."""

    labels: list[str] = ["standalone_legacy"]
    counts = [
        count
        for count in (record.estimated_state_count, record.observed_state_count)
        if count is not None
    ]
    large = bool(counts and max(counts) > large_model_threshold) or record.budgeted_incomplete
    if large or record.functional_area_count > 1:
        labels.append("legacy_large_review_needed")
    if record.functional_area_count > 1:
        labels.append("legacy_candidate_parent")
    elif record.has_compatibility_contract:
        labels.append("legacy_candidate_child")
    if record.overlaps_existing_model:
        labels.append("legacy_overlaps_existing")
    if not record.evidence_current or record.skipped_checks or record.not_run_checks:
        labels.append("legacy_stale_or_partial")
    if not record.has_compatibility_contract:
        labels.append("legacy_without_contract")

    can_be_strong = (
        record.has_compatibility_contract
        and not large
        and record.evidence_current
        and not record.skipped_checks
        and not record.not_run_checks
    )
    reason = "strong child evidence allowed" if can_be_strong else "compatibility review required"
    return LegacyModelClassification(
        model_id=record.model_id,
        labels=tuple(labels),
        requires_split_review=large or record.functional_area_count > 1,
        can_be_strong_evidence=can_be_strong,
        reason=reason,
    )


def _target_split_derivation_findings(partition_map: HierarchyPartitionMap) -> list[HierarchyMeshFinding]:
    findings: list[HierarchyMeshFinding] = []
    if not partition_map.coverage_items and not partition_map.child_models:
        return findings

    derivation = partition_map.target_split_derivation
    if derivation is None:
        return [
            HierarchyMeshFinding(
                "missing_target_split_derivation",
                "parent model boundary lacks FlowGuard-derived target split structure",
                model_id=partition_map.parent_model_id,
            )
        ]

    if not derivation.derived_from_flowguard_model or not derivation.source_model_id:
        findings.append(
            HierarchyMeshFinding(
                "invalid_target_split_derivation",
                "target model split derivation must name the FlowGuard source model",
                model_id=partition_map.parent_model_id,
                metadata=derivation.to_dict(),
            )
        )

    child_ids = {child.model_id for child in partition_map.child_models}
    target_ids = set(derivation.target_child_model_ids)
    if not target_ids:
        findings.append(
            HierarchyMeshFinding(
                "missing_target_children",
                "target model split derivation has no target child models",
                model_id=partition_map.parent_model_id,
                metadata=derivation.to_dict(),
            )
        )
    else:
        unknown_targets = tuple(sorted(target_ids - child_ids))
        if unknown_targets:
            findings.append(
                HierarchyMeshFinding(
                    "unknown_target_child_model",
                    "target model split derivation names unregistered child models",
                    model_id=partition_map.parent_model_id,
                    metadata={"unknown_targets": unknown_targets, "derivation": derivation.to_dict()},
                )
            )
        missing_targets = tuple(sorted(child_ids - target_ids))
        if missing_targets:
            findings.append(
                HierarchyMeshFinding(
                    "incomplete_target_children",
                    "target model split derivation omits registered child models",
                    model_id=partition_map.parent_model_id,
                    metadata={"missing_targets": missing_targets, "derivation": derivation.to_dict()},
                )
            )

    coverage_ids = {item.item_id for item in partition_map.coverage_items}
    derived_coverage = set(derivation.covered_partition_item_ids)
    missing_coverage = tuple(sorted(coverage_ids - derived_coverage))
    if missing_coverage:
        findings.append(
            HierarchyMeshFinding(
                "incomplete_target_split_coverage",
                "target model split derivation does not cover all parent partition items",
                model_id=partition_map.parent_model_id,
                metadata={"missing_coverage": missing_coverage, "derivation": derivation.to_dict()},
            )
        )

    if not derivation.state_owner_fields and any(child.state_owned for child in partition_map.child_models):
        findings.append(
            HierarchyMeshFinding(
                "missing_target_state_owner_map",
                "target model split derivation omits state owner fields",
                model_id=partition_map.parent_model_id,
                metadata=derivation.to_dict(),
            )
        )
    if not derivation.side_effect_owner_fields and any(child.side_effects_owned for child in partition_map.child_models):
        findings.append(
            HierarchyMeshFinding(
                "missing_target_side_effect_owner_map",
                "target model split derivation omits side-effect owner fields",
                model_id=partition_map.parent_model_id,
                metadata=derivation.to_dict(),
            )
        )
    if not derivation.rationale:
        findings.append(
            HierarchyMeshFinding(
                "missing_target_split_rationale",
                "target model split derivation lacks rationale",
                model_id=partition_map.parent_model_id,
                metadata=derivation.to_dict(),
            )
        )
    return findings


def _missing_items(expected: Sequence[str], actual: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(set(expected) - set(actual)))


def _extra_items(expected: Sequence[str], actual: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(set(actual) - set(expected)))


def _add_reattachment_set_finding(
    findings: list[HierarchyMeshFinding],
    *,
    code: str,
    message: str,
    contract: ChildReattachmentContract,
    values: tuple[str, ...],
) -> None:
    if not values:
        return
    findings.append(
        HierarchyMeshFinding(
            code,
            message,
            model_id=contract.child_model_id,
            metadata={
                "values": values,
                "reattachment_contract": contract.to_dict(),
            },
        )
    )


def _child_reattachment_findings(partition_map: HierarchyPartitionMap) -> list[HierarchyMeshFinding]:
    findings: list[HierarchyMeshFinding] = []
    children = {child.model_id: child for child in partition_map.child_models}

    for contract in partition_map.reattachment_contracts:
        child = children.get(contract.child_model_id)
        if child is None:
            findings.append(
                HierarchyMeshFinding(
                    "child_reattachment_unknown_child",
                    "parent reattachment contract names an unregistered child model",
                    model_id=contract.child_model_id,
                    metadata=contract.to_dict(),
                )
            )
            continue

        if not contract.consumed_evidence_id:
            findings.append(
                HierarchyMeshFinding(
                    "child_reattachment_missing_parent_consumption",
                    "parent mesh does not record the child evidence id it consumed",
                    model_id=child.model_id,
                    metadata={"child": child.to_dict(), "reattachment_contract": contract.to_dict()},
                )
            )
        elif not child.evidence_id:
            findings.append(
                HierarchyMeshFinding(
                    "child_reattachment_missing_child_evidence_id",
                    "child model evidence has no current evidence id for parent consumption",
                    model_id=child.model_id,
                    metadata={"child": child.to_dict(), "reattachment_contract": contract.to_dict()},
                )
            )
        elif child.evidence_id != contract.consumed_evidence_id:
            findings.append(
                HierarchyMeshFinding(
                    "child_reattachment_stale_evidence",
                    "parent mesh consumed a stale child evidence id",
                    model_id=child.model_id,
                    metadata={
                        "child_evidence_id": child.evidence_id,
                        "consumed_evidence_id": contract.consumed_evidence_id,
                    },
                )
            )

        _add_reattachment_set_finding(
            findings,
            code="child_reattachment_missing_input",
            message="child no longer accepts an input expected by the parent",
            contract=contract,
            values=_missing_items(contract.expected_inputs, child.inputs_accepted),
        )
        if not contract.allow_extra_inputs:
            _add_reattachment_set_finding(
                findings,
                code="child_reattachment_extra_input",
                message="child accepts an input outside the parent handoff",
                contract=contract,
                values=_extra_items(contract.expected_inputs, child.inputs_accepted),
            )

        _add_reattachment_set_finding(
            findings,
            code="child_reattachment_missing_output",
            message="child no longer emits an output expected by the parent",
            contract=contract,
            values=_missing_items(contract.expected_outputs, child.outputs_emitted),
        )
        if not contract.allow_extra_outputs:
            _add_reattachment_set_finding(
                findings,
                code="child_reattachment_extra_output",
                message="child emits an output outside the parent handoff",
                contract=contract,
                values=_extra_items(contract.expected_outputs, child.outputs_emitted),
            )

        _add_reattachment_set_finding(
            findings,
            code="child_reattachment_missing_state_owner",
            message="child no longer owns a state field expected by the parent",
            contract=contract,
            values=_missing_items(contract.expected_state_owned, child.state_owned),
        )
        _add_reattachment_set_finding(
            findings,
            code="child_reattachment_missing_side_effect_owner",
            message="child no longer owns a side effect expected by the parent",
            contract=contract,
            values=_missing_items(contract.expected_side_effects_owned, child.side_effects_owned),
        )
        _add_reattachment_set_finding(
            findings,
            code="child_reattachment_missing_contract",
            message="child no longer declares an outgoing guarantee expected by the parent",
            contract=contract,
            values=_missing_items(contract.expected_contracts_out, child.contracts_out),
        )

    return findings


def _boundary_change_findings(
    partition_map: HierarchyPartitionMap,
) -> tuple[list[HierarchyMeshFinding], dict[str, str]]:
    findings: list[HierarchyMeshFinding] = []
    decisions: dict[str, str] = {}
    children = {child.model_id: child for child in partition_map.child_models}
    contracts = {
        contract.child_model_id: contract
        for contract in partition_map.reattachment_contracts
    }

    for change in partition_map.boundary_changes:
        propagation = str(change.propagation)
        decisions[change.child_model_id] = propagation
        child = children.get(change.child_model_id)
        if child is None:
            findings.append(
                HierarchyMeshFinding(
                    "boundary_change_unknown_child",
                    "boundary change summary names an unregistered child model",
                    model_id=change.child_model_id,
                    metadata=change.to_dict(),
                )
            )
            continue
        if propagation not in ALLOWED_BOUNDARY_PROPAGATION:
            findings.append(
                HierarchyMeshFinding(
                    "invalid_boundary_propagation",
                    "boundary change summary uses an unknown propagation decision",
                    model_id=change.child_model_id,
                    metadata=change.to_dict(),
                )
            )
            continue

        if change.current_bug_id and not change.generalized_target:
            findings.append(
                HierarchyMeshFinding(
                    "missing_bug_class_responsibility",
                    "observed bug instance is present without a generalized bug-class responsibility boundary",
                    model_id=change.child_model_id,
                    metadata=change.to_dict(),
                )
            )
        if change.current_bug_is_only_model_target:
            findings.append(
                HierarchyMeshFinding(
                    "point_fix_only_model_target",
                    "observed bug instance is being used as the model target instead of holdout evidence",
                    model_id=change.child_model_id,
                    metadata=change.to_dict(),
                )
            )

        if propagation == BOUNDARY_PROPAGATION_REATTACH_ONLY:
            contract = contracts.get(change.child_model_id)
            if contract is None or contract.consumed_evidence_id != change.current_evidence_id:
                findings.append(
                    HierarchyMeshFinding(
                        "boundary_change_reattachment_required",
                        "child boundary change only needs reattachment, but the parent has not consumed the current evidence id",
                        model_id=change.child_model_id,
                        metadata={
                            "boundary_change": change.to_dict(),
                            "reattachment_contract": contract.to_dict() if contract is not None else None,
                        },
                    )
                )
        elif propagation == BOUNDARY_PROPAGATION_PARENT_RERUN_REQUIRED:
            findings.append(
                HierarchyMeshFinding(
                    "boundary_change_parent_rerun_required",
                    "child boundary change affects parent handoff or responsibility and requires parent rerun",
                    model_id=change.child_model_id,
                    metadata=change.to_dict(),
                )
            )
        elif propagation == BOUNDARY_PROPAGATION_SIBLING_RERUN_REQUIRED:
            findings.append(
                HierarchyMeshFinding(
                    "boundary_change_sibling_rerun_required",
                    "child boundary change intersects sibling ownership, dependency, or handoff assumptions",
                    model_id=change.child_model_id,
                    metadata=change.to_dict(),
                )
            )
        elif propagation == BOUNDARY_PROPAGATION_SPLIT_REVIEW_REQUIRED:
            findings.append(
                HierarchyMeshFinding(
                    "boundary_change_split_review_required",
                    "child boundary change is large or mixed enough to require split review",
                    severity="refactor",
                    model_id=change.child_model_id,
                    metadata=change.to_dict(),
                )
            )

    return findings, decisions


def review_hierarchical_mesh(
    partition_map: HierarchyPartitionMap,
    *,
    model_count: int | None = None,
    large_model_threshold: int = DEFAULT_LARGE_MODEL_STATE_THRESHOLD,
) -> HierarchyMeshReport:
    """Review one parent boundary without expanding child state graphs."""

    findings: list[HierarchyMeshFinding] = []
    activation_reasons: list[str] = []
    child_ids = {child.model_id for child in partition_map.child_models}
    effective_model_count = len(partition_map.child_models) if model_count is None else model_count
    if effective_model_count >= 3:
        activation_reasons.append("model_count")

    for child in partition_map.child_models:
        if _is_large_child(child, large_model_threshold):
            activation_reasons.append(f"large_model:{child.model_id}")

    findings.extend(_target_split_derivation_findings(partition_map))
    findings.extend(_child_reattachment_findings(partition_map))
    boundary_change_findings, boundary_change_decisions = _boundary_change_findings(partition_map)
    if boundary_change_decisions:
        activation_reasons.append("boundary_change")
    findings.extend(boundary_change_findings)
    closure_report = None
    if partition_map.closure_model is not None:
        activation_reasons.append("closure_model")
        closure_report = review_mesh_closure_model(
            partition_map.closure_model,
            partition_map.child_models,
        )
        for closure_finding in closure_report.findings:
            findings.append(
                HierarchyMeshFinding(
                    closure_finding.code,
                    closure_finding.message,
                    severity=closure_finding.severity,
                    model_id=closure_finding.model_id,
                    item_id=closure_finding.item_id,
                    metadata={
                        "mesh_closure": closure_finding.to_dict(),
                        "closure_decision": closure_report.decision,
                    },
                )
            )

    owner_by_item: dict[str, list[HierarchyCoverageItem]] = {}
    for item in partition_map.coverage_items:
        if item.ownership not in ALLOWED_OWNERSHIP:
            findings.append(
                HierarchyMeshFinding(
                    "unknown_ownership",
                    f"coverage item uses unknown ownership mode {item.ownership!r}",
                    item_id=item.item_id,
                    metadata={"ownership": item.ownership},
                )
            )
        if item.ownership == OWNERSHIP_PARENT:
            owner = item.owner_model_id or partition_map.parent_model_id
        else:
            owner = item.owner_model_id
        if not owner and item.ownership != OWNERSHIP_READ_ONLY:
            findings.append(
                HierarchyMeshFinding(
                    "coverage_gap",
                    "parent coverage item has no owner",
                    item_id=item.item_id,
                    metadata={"item_type": item.item_type},
                )
            )
        if owner and item.ownership not in {OWNERSHIP_PARENT, OWNERSHIP_SHARED_KERNEL} and owner not in child_ids:
            findings.append(
                HierarchyMeshFinding(
                    "unknown_child_owner",
                    f"coverage item owner {owner!r} is not a registered child",
                    item_id=item.item_id,
                    model_id=owner,
                )
            )
        if item.ownership in OWNING_MODES:
            owner_by_item.setdefault(item.item_id, []).append(item)

    for item_id, owners in sorted(owner_by_item.items()):
        distinct_owners = {
            item.owner_model_id or partition_map.parent_model_id
            for item in owners
        }
        if len(distinct_owners) > 1:
            findings.append(
                HierarchyMeshFinding(
                    "duplicate_coverage_owner",
                    "coverage item has multiple owning models",
                    item_id=item_id,
                    metadata={"owners": sorted(distinct_owners)},
                )
            )

    _add_duplicate_owner_findings(
        findings,
        partition_map.child_models,
        field_name="functions_owned",
        code="duplicate_function_owner",
        noun="function",
    )
    _add_duplicate_owner_findings(
        findings,
        partition_map.child_models,
        field_name="state_owned",
        code="duplicate_state_owner",
        noun="state field",
    )
    _add_duplicate_owner_findings(
        findings,
        partition_map.child_models,
        field_name="side_effects_owned",
        code="duplicate_side_effect_owner",
        noun="side effect",
    )
    _add_duplicate_owner_findings(
        findings,
        partition_map.child_models,
        field_name="invariants_owned",
        code="duplicate_invariant_owner",
        noun="invariant",
    )
    _add_duplicate_owner_findings(
        findings,
        partition_map.child_models,
        field_name="risk_classes",
        code="duplicate_risk_class_owner",
        noun="risk class",
    )

    allowed_shared = set(partition_map.allowed_shared_areas)
    for left_index, left in enumerate(partition_map.child_models):
        for right in partition_map.child_models[left_index + 1 :]:
            overlap = set(left.functional_areas) & set(right.functional_areas)
            unsafe = tuple(sorted(overlap - allowed_shared))
            if unsafe:
                findings.append(
                    HierarchyMeshFinding(
                        "excessive_functional_overlap",
                        "sibling child models share functional areas without an allowed shared kernel",
                        severity="refactor",
                        metadata={"models": (left.model_id, right.model_id), "areas": unsafe},
                    )
                )

    split_decisions: dict[str, str] = {}
    for child in partition_map.child_models:
        decision = _split_decision(child, large_model_threshold)
        if decision != "not_large":
            split_decisions[child.model_id] = decision
            if decision in {"split_into_children", "merge_with_existing_model"}:
                findings.append(
                    HierarchyMeshFinding(
                        "large_model_split_review",
                        f"large model requires split review decision {decision}",
                        severity="refactor",
                        model_id=child.model_id,
                        metadata={"decision": decision, "state_count": child.largest_state_count()},
                    )
                )
        if not child.evidence_current:
            findings.append(
                HierarchyMeshFinding(
                    "stale_child_evidence",
                    "child evidence is stale",
                    model_id=child.model_id,
                    metadata={"evidence_tier": child.evidence_tier},
                )
            )
        if child.skipped_checks or child.not_run_checks:
            findings.append(
                HierarchyMeshFinding(
                    "missing_or_skipped_child_check",
                    "child has skipped or not-run checks",
                    model_id=child.model_id,
                    metadata={
                        "skipped_checks": child.skipped_checks,
                        "not_run_checks": child.not_run_checks,
                    },
                )
            )
        if _evidence_rank(child.evidence_tier) < _evidence_rank(partition_map.required_evidence_tier):
            findings.append(
                HierarchyMeshFinding(
                    "insufficient_evidence_tier",
                    "child evidence tier is below the parent requirement",
                    model_id=child.model_id,
                    metadata={
                        "required": partition_map.required_evidence_tier,
                        "actual": child.evidence_tier,
                    },
                )
            )
        if child.is_legacy and not child.has_compatibility_contract:
            findings.append(
                HierarchyMeshFinding(
                    "legacy_without_contract",
                    "legacy model cannot be strong child evidence before compatibility wrapping",
                    model_id=child.model_id,
                )
            )

    blocking = [finding for finding in findings if finding.severity in {"blocker", "refactor"}]
    if not blocking:
        decision = "mesh_green_can_continue"
    elif any(finding.code in {
        "missing_target_split_derivation",
        "invalid_target_split_derivation",
        "missing_target_children",
        "unknown_target_child_model",
        "incomplete_target_children",
        "incomplete_target_split_coverage",
        "missing_target_state_owner_map",
        "missing_target_side_effect_owner_map",
        "missing_target_split_rationale",
    } for finding in blocking):
        decision = "target_split_derivation_required"
    elif any(finding.code.startswith("child_reattachment_") for finding in blocking):
        decision = "child_reattachment_required"
    elif any(finding.code == "boundary_change_split_review_required" for finding in blocking):
        decision = BOUNDARY_PROPAGATION_SPLIT_REVIEW_REQUIRED
    elif any(finding.code in {
        "boundary_change_parent_rerun_required",
        "missing_bug_class_responsibility",
        "point_fix_only_model_target",
    } for finding in blocking):
        decision = BOUNDARY_PROPAGATION_PARENT_RERUN_REQUIRED
    elif any(finding.code == "boundary_change_sibling_rerun_required" for finding in blocking):
        decision = BOUNDARY_PROPAGATION_SIBLING_RERUN_REQUIRED
    elif any(finding.code == "boundary_change_reattachment_required" for finding in blocking):
        decision = BOUNDARY_PROPAGATION_REATTACH_ONLY
    elif any(finding.code == "coverage_gap" for finding in blocking):
        decision = "coverage_gap_blocked"
    elif any(finding.code == "excessive_functional_overlap" for finding in blocking):
        decision = "overlap_too_high_refactor_needed"
    elif any(finding.code in {"duplicate_state_owner", "duplicate_side_effect_owner"} for finding in blocking):
        decision = "ownership_conflict"
    elif any(finding.code in {
        "duplicate_function_owner",
        "duplicate_invariant_owner",
        "duplicate_risk_class_owner",
    } for finding in blocking):
        decision = "ownership_conflict"
    elif any(finding.code == "large_model_split_review" for finding in blocking):
        decision = "large_model_split_review_required"
    elif any(finding.code == "legacy_without_contract" for finding in blocking):
        decision = "legacy_compatibility_required"
    elif any(finding.code == "stale_child_evidence" for finding in blocking):
        decision = "blocked_by_stale_evidence"
    elif closure_report is not None and not closure_report.ok:
        decision = closure_report.decision
    else:
        decision = "mesh_review_blocked"

    unique_activation = tuple(dict.fromkeys(activation_reasons))
    return HierarchyMeshReport(
        ok=not blocking,
        parent_model_id=partition_map.parent_model_id,
        decision=decision,
        activation_reasons=unique_activation,
        findings=tuple(findings),
        split_decisions=split_decisions,
        boundary_change_decisions=boundary_change_decisions,
        closure_report=closure_report,
    )


def _add_duplicate_owner_findings(
    findings: list[HierarchyMeshFinding],
    children: Sequence[ChildModelEvidence],
    *,
    field_name: str,
    code: str,
    noun: str,
) -> None:
    owners: dict[str, list[str]] = {}
    for child in children:
        for value in getattr(child, field_name):
            owners.setdefault(value, []).append(child.model_id)
    for value, model_ids in sorted(owners.items()):
        unique = tuple(sorted(set(model_ids)))
        if len(unique) > 1:
            findings.append(
                HierarchyMeshFinding(
                    code,
                    f"{noun} is owned by multiple child models",
                    item_id=value,
                    metadata={"owners": unique},
                )
            )


__all__ = [
    "ALLOWED_BOUNDARY_PROPAGATION",
    "ALLOWED_OWNERSHIP",
    "BOUNDARY_PROPAGATION_PARENT_RERUN_REQUIRED",
    "BOUNDARY_PROPAGATION_REATTACH_ONLY",
    "BOUNDARY_PROPAGATION_SIBLING_RERUN_REQUIRED",
    "BOUNDARY_PROPAGATION_SPLIT_REVIEW_REQUIRED",
    "BOUNDARY_PROPAGATION_UNAFFECTED",
    "DEFAULT_LARGE_MODEL_STATE_THRESHOLD",
    "EVIDENCE_ABSTRACT_GREEN",
    "EVIDENCE_CANDIDATE_ONLY",
    "EVIDENCE_CONFORMANCE_GREEN",
    "EVIDENCE_HAZARD_GREEN",
    "EVIDENCE_LIVE_CURRENT_GREEN",
    "EVIDENCE_MESH_GREEN",
    "MESH_CLOSURE_FAILURE_EXIT",
    "MESH_CLOSURE_NORMAL_EXIT",
    "MESH_CLOSURE_OUT_OF_SCOPE",
    "MESH_CLOSURE_TERMINAL_SIDE_EFFECT",
    "ChildBoundaryChangeSummary",
    "HierarchyCoverageItem",
    "HierarchyMeshFinding",
    "HierarchyMeshReport",
    "HierarchyPartitionMap",
    "ChildReattachmentContract",
    "ChildModelEvidence",
    "LegacyModelClassification",
    "LegacyModelRecord",
    "MeshClosureFinding",
    "MeshClosureJoin",
    "MeshClosureModel",
    "MeshClosureReport",
    "MeshClosureTerminal",
    "MeshClosureTransition",
    "ModelTargetSplitDerivation",
    "OWNERSHIP_CHILD",
    "OWNERSHIP_PARENT",
    "OWNERSHIP_READ_ONLY",
    "OWNERSHIP_SHARED_KERNEL",
    "classify_legacy_model",
    "review_hierarchical_mesh",
    "review_mesh_closure_model",
    "summarize_child_boundary_change",
]
