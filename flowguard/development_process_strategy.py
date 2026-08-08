"""Conditional process optimization owned by DevelopmentProcessFlow.

The optimizer is intentionally small.  It does not run diagnostics, tests, or
repairs.  It admits process comparison only when a real optimization reason is
present, rejects routes that weaken the declared outcome contract, and keeps
every recommendation bounded by current evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Sequence

from .export import to_jsonable


_ACTIVATION_REASONS = {
    "explicit_request",
    "multiple_equivalent_routes",
    "material_rework_risk",
    "diagnostic_boundary_choice",
}
_DIAGNOSTIC_BOUNDARIES = {"targeted", "declared_complete", "budgeted"}
_EXECUTION_MODES = {"sequential", "safe_parallel"}
_COMPARISON_BASES = {"qualitative", "measured"}
_REPAIR_STATUSES = {"open", "complete", "blocked"}
_EVIDENCE_GAP_SUFFIXES = (
    "_evidence_missing",
    "_revision_missing",
    "_rationale_missing",
    "_selection_missing",
)
_COST_COMPONENT_IDS = (
    "invalidated_output", "repeated_write", "repeated_validation",
    "coordination", "side_effect_exposure", "effort",
)


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    return tuple(str(value) for value in values or ())


def _as_pairs(
    values: Sequence[Sequence[str]] | None,
) -> tuple[tuple[str, str], ...]:
    return tuple(
        (str(value[0]), str(value[1])) if len(value) == 2 else ("", "")
        for value in values or ()
    )


def _as_cost_pairs(values: Sequence[Sequence[object]] | None) -> tuple[tuple[str, float], ...]:
    rows: list[tuple[str, float]] = []
    for value in values or ():
        if len(value) != 2:
            rows.append(("", math.nan))
            continue
        try:
            cost = float(value[1])
        except (TypeError, ValueError):
            cost = math.nan
        rows.append((str(value[0]), cost))
    return tuple(rows)


def _record_dict(record: Any) -> dict[str, Any]:
    return dict(to_jsonable(asdict(record)))


@dataclass(frozen=True)
class ProcessOptimizationContract:
    contract_id: str
    terminal_outcome_ids: tuple[str, ...] = ()
    required_obligation_ids: tuple[str, ...] = ()
    required_evidence_ids: tuple[str, ...] = ()
    safety_constraint_ids: tuple[str, ...] = ()
    protected_side_effect_ids: tuple[str, ...] = ()
    dependency_authority_ids: tuple[str, ...] = ()
    execution_owner_ids: tuple[str, ...] = ()
    revision: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "contract_id", str(self.contract_id))
        for name in (
            "terminal_outcome_ids", "required_obligation_ids", "required_evidence_ids",
            "safety_constraint_ids", "protected_side_effect_ids",
            "dependency_authority_ids", "execution_owner_ids",
        ):
            object.__setattr__(self, name, _as_tuple(getattr(self, name)))
        object.__setattr__(self, "revision", str(self.revision))

    def to_dict(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class ProcessOptimizationCandidate:
    candidate_id: str
    contract_id: str
    terminal_outcome_ids: tuple[str, ...] = ()
    covered_obligation_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    safety_constraint_ids: tuple[str, ...] = ()
    protected_side_effect_ids: tuple[str, ...] = ()
    dependency_authority_ids: tuple[str, ...] = ()
    execution_owner_ids: tuple[str, ...] = ()
    step_ids: tuple[str, ...] = ()
    validation_requirement_ids: tuple[str, ...] = ()
    dependency_edges: tuple[tuple[str, str], ...] = ()
    step_artifact_reads: tuple[tuple[str, str], ...] = ()
    step_artifact_writes: tuple[tuple[str, str], ...] = ()
    step_artifact_invalidations: tuple[tuple[str, str], ...] = ()
    step_validation_ids: tuple[tuple[str, str], ...] = ()
    step_execution_owner_ids: tuple[tuple[str, str], ...] = ()
    step_side_effect_ids: tuple[tuple[str, str], ...] = ()
    step_effort_costs: tuple[tuple[str, float], ...] = ()
    step_effort_evidence_ids: tuple[tuple[str, str], ...] = ()
    stop_condition_ids: tuple[str, ...] = ()
    diagnostic_boundary: str = "targeted"
    execution_mode: str = "sequential"
    dependency_isolation_evidence_ids: tuple[str, ...] = ()
    state_isolation_evidence_ids: tuple[str, ...] = ()
    side_effect_isolation_evidence_ids: tuple[str, ...] = ()
    execution_owner_isolation_evidence_ids: tuple[str, ...] = ()
    comparison_basis: str = "qualitative"
    comparison_evidence_ids: tuple[str, ...] = ()
    applicable: bool = True
    current: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", str(self.candidate_id))
        object.__setattr__(self, "contract_id", str(self.contract_id))
        for name in (
            "terminal_outcome_ids", "covered_obligation_ids", "evidence_ids",
            "safety_constraint_ids", "protected_side_effect_ids", "dependency_authority_ids",
            "execution_owner_ids", "step_ids", "validation_requirement_ids", "stop_condition_ids",
            "dependency_isolation_evidence_ids", "state_isolation_evidence_ids",
            "side_effect_isolation_evidence_ids", "execution_owner_isolation_evidence_ids",
            "comparison_evidence_ids",
        ):
            object.__setattr__(self, name, _as_tuple(getattr(self, name)))
        object.__setattr__(self, "dependency_edges", _as_pairs(self.dependency_edges))
        for name in (
            "step_artifact_reads", "step_artifact_writes", "step_artifact_invalidations",
            "step_validation_ids", "step_execution_owner_ids", "step_side_effect_ids",
            "step_effort_evidence_ids",
        ):
            object.__setattr__(self, name, _as_pairs(getattr(self, name)))
        object.__setattr__(self, "step_effort_costs", _as_cost_pairs(self.step_effort_costs))
        object.__setattr__(self, "diagnostic_boundary", str(self.diagnostic_boundary))
        object.__setattr__(self, "execution_mode", str(self.execution_mode))
        object.__setattr__(self, "comparison_basis", str(self.comparison_basis))
        object.__setattr__(self, "applicable", bool(self.applicable))
        object.__setattr__(self, "current", bool(self.current))

    def to_dict(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class ProcessRepairGroup:
    group_id: str
    finding_ids: tuple[str, ...] = ()
    relation_evidence_ids: tuple[str, ...] = ()
    root_cause_claim: str = ""
    disproof_check_ids: tuple[str, ...] = ()
    affected_obligation_ids: tuple[str, ...] = ()
    owner_evidence_ids: tuple[str, ...] = ()
    repair_action_ids: tuple[str, ...] = ()
    required_revalidation_ids: tuple[str, ...] = ()
    current_revalidation_ids: tuple[str, ...] = ()
    status: str = "open"

    def __post_init__(self) -> None:
        object.__setattr__(self, "group_id", str(self.group_id))
        for name in (
            "finding_ids", "relation_evidence_ids", "disproof_check_ids",
            "affected_obligation_ids", "owner_evidence_ids", "repair_action_ids",
            "required_revalidation_ids", "current_revalidation_ids",
        ):
            object.__setattr__(self, name, _as_tuple(getattr(self, name)))
        object.__setattr__(self, "root_cause_claim", str(self.root_cause_claim))
        object.__setattr__(self, "status", str(self.status))

    def to_dict(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class ProcessOptimizationDecision:
    decision_id: str
    outcome_contract: ProcessOptimizationContract
    activation_reasons: tuple[str, ...] = ()
    candidates: tuple[ProcessOptimizationCandidate, ...] = ()
    repair_groups: tuple[ProcessRepairGroup, ...] = ()
    selected_candidate_id: str = ""
    input_revision: str = ""
    current_evidence_ids: tuple[str, ...] = ()
    material_evidence_ids: tuple[str, ...] = ()
    selection_rationale: str = ""

    def __post_init__(self) -> None:
        for name in ("decision_id", "selected_candidate_id", "input_revision", "selection_rationale"):
            object.__setattr__(self, name, str(getattr(self, name)))
        for name in ("activation_reasons", "current_evidence_ids", "material_evidence_ids"):
            object.__setattr__(self, name, _as_tuple(getattr(self, name)))
        for name in ("candidates", "repair_groups"):
            object.__setattr__(self, name, tuple(getattr(self, name)))

    def to_dict(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class ProcessOptimizationReport:
    ok: bool
    status: str
    decision_id: str
    selected_candidate_id: str = ""
    eligible_candidate_ids: tuple[str, ...] = ()
    rejected_candidate_ids: tuple[str, ...] = ()
    selected_comparison_basis: str = ""
    cost_component_ids: tuple[str, ...] = _COST_COMPONENT_IDS
    candidate_cost_rows: tuple[tuple[object, ...], ...] = ()
    non_dominated_candidate_ids: tuple[str, ...] = ()
    required_revalidation_ids: tuple[str, ...] = ()
    finding_codes: tuple[str, ...] = ()
    rejected_candidate_finding_codes: tuple[str, ...] = ()
    selection_rationale: str = ""
    caller_selection_rationale: str = ""
    claim_boundary: str = ""
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _record_dict(self)


def review_process_optimization(
    decision: ProcessOptimizationDecision,
) -> ProcessOptimizationReport:
    """Review one process choice through the sole private calculation owner."""

    from ._development_process_strategy_review import (
        _review_process_optimization,
    )

    return _review_process_optimization(decision)


__all__ = [
    "ProcessOptimizationContract",
    "ProcessOptimizationCandidate",
    "ProcessRepairGroup",
    "ProcessOptimizationDecision",
    "ProcessOptimizationReport",
    "review_process_optimization",
]
