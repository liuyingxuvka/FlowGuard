"""Executable child model for conditional development-process optimization.

The stable model id and directory retain ``development_process_strategy`` so
existing model ownership remains intact.  The behavior is deliberately
smaller: ordinary work stays inactive, while only explicitly justified work
compares outcome-equivalent candidates.  TestMesh owns diagnostic execution
details; this model consumes only its current evidence boundary.

Every block implements ``Input x State -> Set(Output x State)``.

Run:
python .flowguard/development_process_strategy/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"

ACTIVATION_REASONS = (
    "explicit_request",
    "multiple_equivalent_routes",
    "material_rework_risk",
    "diagnostic_boundary_choice",
)
DIAGNOSTIC_BOUNDARIES = ("targeted", "declared_complete", "budgeted")
EXECUTION_MODES = ("sequential", "safe_parallel")


@dataclass(frozen=True)
class OptimizationInput:
    event: str
    activation_reasons: tuple[str, ...] = ()
    terminal_outcome_equal: bool = True
    obligation_evidence_equal: bool = True
    safety_equal: bool = True
    side_effects_equal: bool = True
    dependency_authority_equal: bool = True
    execution_owner_equal: bool = True
    diagnostic_boundary: str = "targeted"
    testmesh_evidence_current: bool = True
    hard_blocker: bool = False
    grouped_finding_count: int = 0
    relation_evidence_current: bool = True
    primary_owner_current: bool = True
    required_revalidation_ids: tuple[str, ...] = ()
    current_revalidation_ids: tuple[str, ...] = ()
    execution_mode: str = "sequential"
    dependency_isolation_current: bool = True
    mutable_state_isolation_current: bool = True
    side_effect_isolation_current: bool = True
    execution_owner_isolation_current: bool = True
    comparison_evidence_current: bool = True
    comparison_basis: str = "qualitative"
    finite_boundary_named: bool = False
    claim_minimum: bool = False
    claim_global_optimum: bool = False
    decision_revision: int = 1


@dataclass(frozen=True)
class OptimizationOutput:
    status: str


@dataclass(frozen=True)
class OptimizationState:
    activation_reasons: tuple[str, ...] = ()
    inactive: bool = False
    active: bool = False
    equivalence_checked: bool = False
    diagnostic_evidence_current: bool = False
    diagnostic_boundary: str = ""
    repair_group_ready: bool = False
    selected: bool = False
    selected_execution_mode: str = ""
    decision_revision: int = 0
    material_revision: int = 0
    hard_blocker_visible: bool = False
    non_equivalent_selected: bool = False
    unsafe_parallel_selected: bool = False
    unrelated_findings_grouped: bool = False
    unowned_repair_selected: bool = False
    repair_closed_without_revalidation: bool = False
    stale_decision_reused: bool = False
    unsupported_minimum_claimed: bool = False
    global_optimum_claimed: bool = False
    blocked: bool = False


class RouteOptimization:
    name = "route_process_optimization"
    reads = ("activation_reasons",)
    writes = ("inactive", "active", "activation_reasons", "blocked")
    input_description = "Stable activation reasons or an ordinary inactive path"
    output_description = "Inactive ordinary work, active optimization, or rejected reasons"
    idempotency = "stable for one request revision"

    def apply(
        self, input_obj: OptimizationInput, state: OptimizationState
    ) -> Iterable[FunctionResult]:
        if input_obj.event != "route":
            return ()
        reasons = tuple(input_obj.activation_reasons)
        invalid = set(reasons) - set(ACTIVATION_REASONS)
        if invalid or len(reasons) != len(set(reasons)):
            return (
                FunctionResult(
                    OptimizationOutput("activation_rejected"),
                    replace(state, blocked=True),
                    "invalid_activation_reason",
                ),
            )
        if not reasons:
            return (
                FunctionResult(
                    OptimizationOutput("not_needed"),
                    replace(state, inactive=True),
                    "ordinary_path_has_no_optimization_ceremony",
                ),
            )
        return (
            FunctionResult(
                OptimizationOutput("optimization_active"),
                replace(state, active=True, activation_reasons=reasons),
                "conditional_optimization_activated",
            ),
        )


class CheckOutcomeEquivalence:
    name = "check_outcome_equivalence"
    reads = (
        "terminal_outcome_equal",
        "obligation_evidence_equal",
        "safety_equal",
        "side_effects_equal",
        "dependency_authority_equal",
        "execution_owner_equal",
    )
    writes = ("equivalence_checked", "blocked")
    input_description = "Six hard equivalence dimensions"
    output_description = "Equivalent candidate boundary or hard rejection"
    idempotency = "stable for one candidate revision"

    def apply(
        self, input_obj: OptimizationInput, state: OptimizationState
    ) -> Iterable[FunctionResult]:
        if input_obj.event != "equivalence":
            return ()
        equivalent = state.active and all(
            (
                input_obj.terminal_outcome_equal,
                input_obj.obligation_evidence_equal,
                input_obj.safety_equal,
                input_obj.side_effects_equal,
                input_obj.dependency_authority_equal,
                input_obj.execution_owner_equal,
            )
        )
        if not equivalent:
            return (
                FunctionResult(
                    OptimizationOutput("candidate_rejected"),
                    replace(state, blocked=True),
                    "hard_equivalence_gate_rejected",
                ),
            )
        return (
            FunctionResult(
                OptimizationOutput("candidate_equivalent"),
                replace(state, equivalence_checked=True),
                "hard_equivalence_gate_passed",
            ),
        )


class AdmitDiagnosticEvidence:
    name = "admit_testmesh_diagnostic_evidence"
    reads = ("diagnostic_boundary", "testmesh_evidence_current", "hard_blocker")
    writes = (
        "diagnostic_evidence_current",
        "diagnostic_boundary",
        "hard_blocker_visible",
        "blocked",
    )
    input_description = "TestMesh-owned boundary evidence and visible hard blocker"
    output_description = "Current bounded evidence or a stopped process"
    idempotency = "stable for one TestMesh evidence revision"

    def apply(
        self, input_obj: OptimizationInput, state: OptimizationState
    ) -> Iterable[FunctionResult]:
        if input_obj.event != "diagnostic":
            return ()
        if input_obj.hard_blocker:
            return (
                FunctionResult(
                    OptimizationOutput("hard_blocker"),
                    replace(state, hard_blocker_visible=True, blocked=True),
                    "hard_blocker_stops_downstream_work",
                ),
            )
        if (
            input_obj.diagnostic_boundary not in DIAGNOSTIC_BOUNDARIES
            or not input_obj.testmesh_evidence_current
        ):
            return (
                FunctionResult(
                    OptimizationOutput("diagnostic_evidence_rejected"),
                    replace(state, blocked=True),
                    "diagnostic_boundary_or_evidence_invalid",
                ),
            )
        return (
            FunctionResult(
                OptimizationOutput("diagnostic_evidence_admitted"),
                replace(
                    state,
                    diagnostic_evidence_current=True,
                    diagnostic_boundary=input_obj.diagnostic_boundary,
                ),
                "testmesh_evidence_reused_without_copying_counts",
            ),
        )


class AdmitRepairGroup:
    name = "admit_root_cause_repair_group"
    reads = (
        "grouped_finding_count",
        "relation_evidence_current",
        "primary_owner_current",
        "required_revalidation_ids",
        "current_revalidation_ids",
    )
    writes = (
        "repair_group_ready",
        "unrelated_findings_grouped",
        "unowned_repair_selected",
        "repair_closed_without_revalidation",
        "blocked",
    )
    input_description = "Finding Ledger ids, relation evidence, owner, and affected revalidation"
    output_description = "Traceable repair group or hard rejection"
    idempotency = "stable for one repair-group revision"

    def apply(
        self, input_obj: OptimizationInput, state: OptimizationState
    ) -> Iterable[FunctionResult]:
        if input_obj.event != "repair":
            return ()
        relation_missing = (
            input_obj.grouped_finding_count > 1
            and not input_obj.relation_evidence_current
        )
        owner_missing = not input_obj.primary_owner_current
        revalidation_missing = not set(input_obj.required_revalidation_ids).issubset(
            input_obj.current_revalidation_ids
        )
        if relation_missing or owner_missing or revalidation_missing:
            return (
                FunctionResult(
                    OptimizationOutput("repair_group_rejected"),
                    replace(
                        state,
                        unrelated_findings_grouped=relation_missing,
                        unowned_repair_selected=owner_missing,
                        repair_closed_without_revalidation=revalidation_missing,
                        blocked=True,
                    ),
                    "repair_group_contract_rejected",
                ),
            )
        return (
            FunctionResult(
                OptimizationOutput("repair_group_ready"),
                replace(state, repair_group_ready=True),
                "repair_group_owned_and_revalidated",
            ),
        )


class SelectCandidate:
    name = "select_bounded_process_candidate"
    reads = (
        "equivalence_checked",
        "execution_mode",
        "comparison_evidence_current",
        "comparison_basis",
        "finite_boundary_named",
    )
    writes = (
        "selected",
        "selected_execution_mode",
        "decision_revision",
        "unsafe_parallel_selected",
        "unsupported_minimum_claimed",
        "global_optimum_claimed",
        "stale_decision_reused",
        "blocked",
    )
    input_description = "Equivalent candidate, two-dimensional execution choice, and bounded claim"
    output_description = "Selected candidate or explicit rejection"
    idempotency = "deterministic for one current input revision"

    def apply(
        self, input_obj: OptimizationInput, state: OptimizationState
    ) -> Iterable[FunctionResult]:
        if input_obj.event != "select":
            return ()
        isolation_current = all(
            (
                input_obj.dependency_isolation_current,
                input_obj.mutable_state_isolation_current,
                input_obj.side_effect_isolation_current,
                input_obj.execution_owner_isolation_current,
            )
        )
        unsafe_parallel = (
            input_obj.execution_mode == "safe_parallel" and not isolation_current
        )
        unsupported_minimum = input_obj.claim_minimum and not (
            input_obj.comparison_basis == "measured"
            and input_obj.finite_boundary_named
        )
        stale = state.material_revision > input_obj.decision_revision
        invalid = (
            not state.equivalence_checked
            or input_obj.execution_mode not in EXECUTION_MODES
            or not input_obj.comparison_evidence_current
            or unsafe_parallel
            or unsupported_minimum
            or input_obj.claim_global_optimum
            or stale
        )
        if invalid:
            return (
                FunctionResult(
                    OptimizationOutput("selection_rejected"),
                    replace(
                        state,
                        non_equivalent_selected=not state.equivalence_checked,
                        unsafe_parallel_selected=unsafe_parallel,
                        unsupported_minimum_claimed=unsupported_minimum,
                        global_optimum_claimed=input_obj.claim_global_optimum,
                        stale_decision_reused=stale,
                        blocked=True,
                    ),
                    "bounded_selection_contract_rejected",
                ),
            )
        return (
            FunctionResult(
                OptimizationOutput("selected"),
                replace(
                    state,
                    selected=True,
                    selected_execution_mode=input_obj.execution_mode,
                    decision_revision=input_obj.decision_revision,
                ),
                "bounded_candidate_selected",
            ),
        )


class RecordMaterialEvidence:
    name = "record_material_evidence"
    reads = ("decision_revision",)
    writes = ("material_revision",)
    input_description = "Material evidence that can invalidate an old decision"
    output_description = "Decision revision becomes stale until reevaluated"
    idempotency = "monotonic by revision"

    def apply(
        self, input_obj: OptimizationInput, state: OptimizationState
    ) -> Iterable[FunctionResult]:
        if input_obj.event != "material_change":
            return ()
        revision = max(state.material_revision + 1, input_obj.decision_revision)
        return (
            FunctionResult(
                OptimizationOutput("decision_stale"),
                replace(state, material_revision=revision, selected=False),
                "material_evidence_requires_new_selection",
            ),
        )


BLOCKS = (
    RouteOptimization(),
    CheckOutcomeEquivalence(),
    AdmitDiagnosticEvidence(),
    AdmitRepairGroup(),
    SelectCandidate(),
    RecordMaterialEvidence(),
)


class BrokenSelector(SelectCandidate):
    name = "broken_selector"

    def apply(
        self, input_obj: OptimizationInput, state: OptimizationState
    ) -> Iterable[FunctionResult]:
        if input_obj.event != "select":
            return ()
        return (
            FunctionResult(
                OptimizationOutput("selected"),
                replace(
                    state,
                    selected=True,
                    non_equivalent_selected=not state.equivalence_checked,
                    unsafe_parallel_selected=input_obj.execution_mode == "safe_parallel",
                    unrelated_findings_grouped=True,
                    unowned_repair_selected=True,
                    repair_closed_without_revalidation=True,
                    stale_decision_reused=True,
                    unsupported_minimum_claimed=True,
                    global_optimum_claimed=True,
                ),
                "broken_selection",
            ),
        )


def optimization_safety_invariant(
    state: OptimizationState, _trace=None
) -> InvariantResult:
    failures = []
    if state.non_equivalent_selected:
        failures.append("non_equivalent_candidate_selected")
    if state.unsafe_parallel_selected:
        failures.append("unsafe_parallel_selected")
    if state.unrelated_findings_grouped:
        failures.append("unrelated_findings_grouped")
    if state.unowned_repair_selected:
        failures.append("unowned_repair_selected")
    if state.repair_closed_without_revalidation:
        failures.append("repair_without_revalidation")
    if state.stale_decision_reused:
        failures.append("stale_decision_reused")
    if state.unsupported_minimum_claimed:
        failures.append("unsupported_minimum_claimed")
    if state.global_optimum_claimed:
        failures.append("global_optimum_claimed")
    if failures:
        return InvariantResult.fail(",".join(failures))
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        "conditional_optimization_preserves_hard_contracts",
        "Ordinary work stays light; active optimization selects only equivalent, current, safe, owned, and honestly bounded candidates.",
        optimization_safety_invariant,
    ),
)


def apply_event(
    input_obj: OptimizationInput, state: OptimizationState
) -> FunctionResult:
    results = [result for block in BLOCKS for result in block.apply(input_obj, state)]
    if len(results) != 1:
        raise AssertionError(
            f"event {input_obj.event!r} produced {len(results)} results"
        )
    return results[0]


def _active_state(
    *, boundary: str = "targeted", execution_mode: str = "sequential"
) -> OptimizationState:
    state = OptimizationState()
    state = apply_event(
        OptimizationInput("route", activation_reasons=("material_rework_risk",)),
        state,
    ).new_state
    state = apply_event(OptimizationInput("equivalence"), state).new_state
    state = apply_event(
        OptimizationInput("diagnostic", diagnostic_boundary=boundary), state
    ).new_state
    state = apply_event(
        OptimizationInput(
            "repair",
            grouped_finding_count=2,
            required_revalidation_ids=("evidence:affected",),
            current_revalidation_ids=("evidence:affected",),
        ),
        state,
    ).new_state
    state = apply_event(
        OptimizationInput("select", execution_mode=execution_mode), state
    ).new_state
    return state


def run_model_checks() -> dict[str, object]:
    findings: list[str] = []

    ordinary = apply_event(OptimizationInput("route"), OptimizationState()).new_state
    if not ordinary.inactive or ordinary.active or ordinary.blocked:
        findings.append("ordinary_path_not_lightweight")

    valid_paths = {
        "targeted_sequential": _active_state(),
        "declared_complete_parallel": _active_state(
            boundary="declared_complete", execution_mode="safe_parallel"
        ),
        "budgeted_sequential": _active_state(boundary="budgeted"),
    }
    for case_id, state in valid_paths.items():
        if not state.selected or state.blocked:
            findings.append(f"valid_{case_id}_not_selected")
        if not optimization_safety_invariant(state).ok:
            findings.append(f"valid_{case_id}_violates_invariant")

    base = apply_event(
        OptimizationInput("route", activation_reasons=("explicit_request",)),
        OptimizationState(),
    ).new_state
    equivalent = apply_event(OptimizationInput("equivalence"), base).new_state
    diagnostic = apply_event(OptimizationInput("diagnostic"), equivalent).new_state
    selected = apply_event(OptimizationInput("select"), equivalent).new_state
    material = apply_event(
        OptimizationInput("material_change", decision_revision=2), selected
    ).new_state

    known_bad = {
        "cheaper_non_equivalent": apply_event(
            OptimizationInput("equivalence", safety_equal=False), base
        ),
        "hard_blocker": apply_event(
            OptimizationInput("diagnostic", hard_blocker=True), equivalent
        ),
        "unsafe_parallel": apply_event(
            OptimizationInput(
                "select",
                execution_mode="safe_parallel",
                mutable_state_isolation_current=False,
            ),
            equivalent,
        ),
        "unrelated_findings": apply_event(
            OptimizationInput(
                "repair",
                grouped_finding_count=2,
                relation_evidence_current=False,
            ),
            diagnostic,
        ),
        "missing_primary_owner": apply_event(
            OptimizationInput("repair", primary_owner_current=False), diagnostic
        ),
        "incomplete_revalidation": apply_event(
            OptimizationInput(
                "repair",
                required_revalidation_ids=("evidence:affected",),
            ),
            diagnostic,
        ),
        "qualitative_minimum_overclaim": apply_event(
            OptimizationInput("select", claim_minimum=True), equivalent
        ),
        "global_optimum_overclaim": apply_event(
            OptimizationInput("select", claim_global_optimum=True), equivalent
        ),
        "stale_decision": apply_event(
            OptimizationInput("select", decision_revision=1), material
        ),
    }
    for case_id, result in known_bad.items():
        if not result.new_state.blocked:
            findings.append(f"known_bad_{case_id}_not_blocked")

    broken = BrokenSelector().apply(
        OptimizationInput("select", execution_mode="safe_parallel"),
        OptimizationState(),
    )[0].new_state
    broken_invariant = optimization_safety_invariant(broken)
    if broken_invariant.ok:
        findings.append("broken_selector_not_caught")

    return {
        "artifact_type": "flowguard_development_process_optimization_model_review",
        "ok": not findings,
        "status": "pass" if not findings else "blocked",
        "findings": findings,
        "function_blocks": [block.name for block in BLOCKS],
        "inactive_path": "ordinary work adds no optimization records or evidence gates",
        "valid_paths": list(valid_paths),
        "known_bad": {
            case_id: {
                "status": result.output.status,
                "label": result.label,
                "blocked": result.new_state.blocked,
            }
            for case_id, result in known_bad.items()
        },
        "broken_counterexample": broken_invariant.message,
        "claim_boundary": "Finite executable model evidence only; no global workflow optimum and no universal collect-all rule is claimed.",
    }


__all__ = [
    "ACTIVATION_REASONS",
    "BLOCKS",
    "DIAGNOSTIC_BOUNDARIES",
    "EXECUTION_MODES",
    "FLOWGUARD_MODEL_MARKER",
    "INVARIANTS",
    "OptimizationInput",
    "OptimizationOutput",
    "OptimizationState",
    "apply_event",
    "run_model_checks",
]
