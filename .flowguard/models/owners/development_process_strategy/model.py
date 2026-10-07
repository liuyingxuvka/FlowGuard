"""Executable child model for conditional development-process optimization.

The stable model id and directory retain ``development_process_strategy`` so
existing model ownership remains intact.  The behavior is deliberately
smaller: ordinary work stays inactive, while only explicitly justified work
compares outcome-equivalent candidates.  TestMesh owns diagnostic execution
details; this model consumes only its current evidence boundary.

Every block implements ``Input x State -> Set(Output x State)``.

Run:
python .flowguard/verification/owners/development_process_strategy/run_checks.py
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
    dependency_order_valid: bool = True
    step_artifact_bindings_current: bool = True
    process_cost_vector_complete: bool = True
    eligible_candidate_count: int = 1
    unique_pareto_dominator: bool = True
    caller_selected_pareto_dominator: bool = True
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
    dependency_order_violated: bool = False
    incomplete_process_cost_vector: bool = False
    dominated_caller_selection: bool = False
    unresolved_non_dominated_boundary: bool = False
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
        "dependency_order_valid",
        "step_artifact_bindings_current",
        "process_cost_vector_complete",
        "eligible_candidate_count",
        "unique_pareto_dominator",
        "caller_selected_pareto_dominator",
        "finite_boundary_named",
    )
    writes = (
        "selected",
        "selected_execution_mode",
        "decision_revision",
        "unsafe_parallel_selected",
        "unsupported_minimum_claimed",
        "global_optimum_claimed",
        "dependency_order_violated",
        "incomplete_process_cost_vector",
        "dominated_caller_selection",
        "unresolved_non_dominated_boundary",
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
            and input_obj.process_cost_vector_complete
            and input_obj.unique_pareto_dominator
        )
        dependency_order_violated = not input_obj.dependency_order_valid
        incomplete_process_cost_vector = (
            not input_obj.step_artifact_bindings_current
            or not input_obj.process_cost_vector_complete
        )
        unresolved_non_dominated_boundary = (
            input_obj.eligible_candidate_count > 1
            and not input_obj.unique_pareto_dominator
        )
        dominated_caller_selection = (
            input_obj.unique_pareto_dominator
            and not input_obj.caller_selected_pareto_dominator
        )
        stale = state.material_revision > input_obj.decision_revision
        invalid = (
            not state.equivalence_checked
            or input_obj.execution_mode not in EXECUTION_MODES
            or not input_obj.comparison_evidence_current
            or unsafe_parallel
            or unsupported_minimum
            or dependency_order_violated
            or incomplete_process_cost_vector
            or unresolved_non_dominated_boundary
            or dominated_caller_selection
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
                        dependency_order_violated=dependency_order_violated,
                        incomplete_process_cost_vector=incomplete_process_cost_vector,
                        dominated_caller_selection=dominated_caller_selection,
                        unresolved_non_dominated_boundary=unresolved_non_dominated_boundary,
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
                    dependency_order_violated=True,
                    incomplete_process_cost_vector=True,
                    dominated_caller_selection=True,
                    unresolved_non_dominated_boundary=True,
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
    if state.dependency_order_violated:
        failures.append("dependency_order_violated")
    if state.incomplete_process_cost_vector:
        failures.append("incomplete_process_cost_vector")
    if state.dominated_caller_selection:
        failures.append("dominated_caller_selection")
    if state.unresolved_non_dominated_boundary:
        failures.append("unresolved_non_dominated_boundary")
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
    *, boundary: str = "targeted", execution_mode: str = "sequential",
    comparison_basis: str = "qualitative",
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
        OptimizationInput(
            "select", execution_mode=execution_mode,
            comparison_basis=comparison_basis,
        ), state
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
        "freeze_first_measured": _active_state(
            comparison_basis="measured"
        ),
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
        "declared_order_violation": apply_event(
            OptimizationInput("select", dependency_order_valid=False), equivalent
        ),
        "measured_step_cost_missing": apply_event(
            OptimizationInput(
                "select",
                comparison_basis="measured",
                process_cost_vector_complete=False,
            ),
            equivalent,
        ),
        "dominated_caller_preselection": apply_event(
            OptimizationInput(
                "select",
                comparison_basis="measured",
                caller_selected_pareto_dominator=False,
            ),
            equivalent,
        ),
        "unresolved_non_dominated_boundary": apply_event(
            OptimizationInput(
                "select",
                eligible_candidate_count=2,
                unique_pareto_dominator=False,
            ),
            equivalent,
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



def export_path_quality_source(model_instance_fingerprint: str):
    """Declare explicit event components from fixed current apply source, never traces."""
    import ast
    import inspect
    import textwrap
    from dataclasses import fields
    from pathlib import Path
    from flowguard.model_path_quality import compile_declared_path_quality_source
    from flowguard.source_identity import functional_source_fingerprint

    model_id = "development_process_strategy"
    source_path = f".flowguard/models/owners/{model_id}/model.py"
    source_ref = {"path": source_path, "source_fingerprint": functional_source_fingerprint(Path(__file__).resolve().parents[4], source_path)}
    # These exact classes and events are the declared ports, not discovered runners.
    components = (("route", RouteOptimization), ("equivalence", CheckOutcomeEquivalence), ("diagnostic", AdmitDiagnosticEvidence), ("repair", AdmitRepairGroup), ("select", SelectCandidate), ("material_change", RecordMaterialEvidence))
    facts = {name: [] for name in ("states", "transitions", "branches", "function_blocks", "fields", "effects", "outputs", "validations", "owners", "initial_state_ids", "terminal_state_ids", "input_classes")}
    facts.update({
        "state_schema": [field.name for field in fields(OptimizationState)],
        "input_schema": [field.name for field in fields(OptimizationInput)],
        "event_dispatch": True, "constants": {"ACTIVATION_REASONS": list(ACTIVATION_REASONS), "DIAGNOSTIC_BOUNDARIES": list(DIAGNOSTIC_BOUNDARIES), "EXECUTION_MODES": list(EXECUTION_MODES)},
        "dispatcher_rejection": {"event_guard": "input_obj.event not in declared event ids", "outcome": "AssertionError: result count is not exactly one", "source_symbol": "apply_event", "source_definition": next(ast.get_source_segment(Path(__file__).read_text(encoding="utf-8"), node) for node in ast.parse(Path(__file__).read_text(encoding="utf-8")).body if isinstance(node, ast.FunctionDef) and node.name == "apply_event")},
    })
    groundings = {}
    field_uses = {}
    observable_state_outputs = {}
    def field_id(role, name):
        return f"field:{model_id}:{role}:{name}"
    for event, block_type in components:
        block = block_type()
        source = textwrap.dedent(inspect.getsource(block_type.apply))
        function = ast.parse(source).body[0]
        anchor = {"kind": "explicit_event_dispatch", "source_symbol": f"{block_type.__name__}.apply", "source_definition": source, "event": event}
        predicates = {}
        outcomes = []
        no_result_guards = []
        def branches(statements, guards):
            current = list(guards)
            for node in statements:
                if isinstance(node, ast.If):
                    test = ast.unparse(node.test)
                    branches(node.body, current + [test])
                    if node.orelse:
                        branches(node.orelse, current + [f"not ({test})"])
                    # Current fixed branch bodies terminate. Never guess a new shape.
                    if not any(isinstance(item, ast.Return) for item in node.body):
                        raise ValueError(f"unsupported nonterminal dispatcher guard:{event}")
                    current.append(f"not ({test})")
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            predicates[target.id] = ast.unparse(node.value)
                elif isinstance(node, ast.Return):
                    calls = [item for item in ast.walk(node.value) if isinstance(item, ast.Call) and isinstance(item.func, ast.Name) and item.func.id == "FunctionResult"]
                    if not calls:
                        if not isinstance(node.value, ast.Tuple) or node.value.elts:
                            raise ValueError(f"unsupported no-result dispatcher source:{event}")
                        no_result_guards.append(" and ".join(current))
                        return
                    if len(calls) != 1:
                        raise ValueError(f"ambiguous dispatcher outcome:{event}")
                    call = calls[0]
                    output = call.args[0]
                    value = output.args[0].value if isinstance(output, ast.Call) and isinstance(output.func, ast.Name) and output.func.id == "OptimizationOutput" else None
                    replacement = call.args[1]
                    if value is None or not isinstance(replacement, ast.Call) or not isinstance(replacement.func, ast.Name) or replacement.func.id != "replace" or len(replacement.args) != 1 or not isinstance(replacement.args[0], ast.Name) or replacement.args[0].id != "state":
                        raise ValueError(f"unsupported dispatcher outcome:{event}")
                    updates = {keyword.arg: ast.unparse(keyword.value) for keyword in replacement.keywords}
                    outcomes.append((value, " and ".join(current), updates))
                    return
        branches(function.body, [])
        before = f"state:{model_id}:{event}:input"
        facts["states"].append({"id": before, "initial": True, "terminal": False, "state_schema": facts["state_schema"], "component_id": event})
        facts["initial_state_ids"].append(before)
        groundings[before] = {**anchor, "role": "current immutable input state"}
        read_ids = sorted({field_id(node.value.id, node.attr) for node in ast.walk(function) if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in ("input_obj", "state")})
        written_ids = sorted({field_id("state", key) for _, _, updates in outcomes for key in updates})
        block_id = f"function-block:{model_id}:{event}"
        transition_ids = []
        output_ids = []
        for value, guard, updates in outcomes:
            transition_id = f"transition:{model_id}:{event}:{value}"
            output_id = f"output:{model_id}:{event}:{value}"
            state_output_id = output_id + ":new-state"
            after = f"state:{model_id}:{event}:{value}"
            update_ids = [field_id("state", key) for key in sorted(updates)]
            facts["states"].append({"id": after, "initial": False, "terminal": False, "component_id": event, "field_values": updates, "unchanged_fields": sorted(set(facts["state_schema"]) - set(updates)), "continuation": "shared immutable state supplied to next event"})
            facts["transitions"].append({"id": transition_id, "source": before, "target": after, "trigger": event, "guard": guard, "guard_bindings": predicates, "outputs": [output_id, state_output_id], "reads": read_ids, "writes": update_ids, "state_updates": update_ids, "field_updates": updates, "function_block_ids": [block_id], "effects": [], "errors": [], "component_id": event})
            facts["outputs"].append({"id": output_id, "symbol": value, "terminal": False, "producer_id": transition_id, "consumer_ids": ["caller:event-dispatch"]})
            # FunctionResult exposes this exact immutable replacement as new_state.
            # Its updated fields are returned data, even if later guards do not read them.
            facts["outputs"].append({"id": state_output_id, "symbol": "FunctionResult.new_state", "terminal": False, "producer_id": transition_id, "consumer_ids": ["caller:event-dispatch:new_state"], "observable_field_ids": update_ids})
            groundings[state_output_id] = {**anchor, "role": "returned immutable FunctionResult.new_state", "field_updates": updates}
            for element_id in update_ids:
                observable_state_outputs.setdefault(element_id, []).append(state_output_id)
            groundings[after] = {**anchor, "guard": guard, "field_updates": updates}
            groundings[transition_id] = {**anchor, "guard": guard, "guard_bindings": predicates, "field_updates": updates}
            transition_ids.append(transition_id)
            output_ids.extend((output_id, state_output_id))
            facts["input_classes"].append({"id": f"input-class:{model_id}:{event}:{value}", "event": event, "guard": guard, "guard_bindings": predicates})
        facts["function_blocks"].append({"id": block_id, "inputs": [f"external-input:{event}"], "outputs": output_ids, "reads": read_ids, "writes": written_ids, "component_id": event, "no_result_guards": no_result_guards})
        groundings[block_id] = anchor
        branch_id = f"branch:{model_id}:{event}"
        facts["branches"].append({"id": branch_id, "source": before, "trigger": event, "transition_ids": transition_ids, "no_result_guards": no_result_guards})
        groundings[branch_id] = anchor
        for element_id in set(read_ids + written_ids):
            role, name = element_id.rsplit(":", 2)[-2:]
            uses = field_uses.setdefault(element_id, {"reads": [], "writes": [], "groundings": []})
            if element_id in read_ids:
                uses["reads"].append(block_id)
            if element_id in written_ids:
                uses["writes"].append(block_id)
            uses["groundings"].append(f"{block_type.__name__}.apply")
            groundings[element_id] = {"kind": "explicit_dispatch_field", "source_symbol": f"{'OptimizationInput' if role == 'input_obj' else 'OptimizationState'}:{name}", "apply_anchors": uses["groundings"]}
    for element_id, uses in sorted(field_uses.items()):
        output_refs = sorted(set(observable_state_outputs.get(element_id, ())))
        facts["fields"].append({"id": element_id, "used_by": sorted(set(uses["reads"] + uses["writes"])), "reads_by": sorted(set(uses["reads"])), "writes_by": sorted(set(uses["writes"])), "observable": bool(output_refs), "observable_output_ids": output_refs})
        if output_refs:
            groundings[element_id]["observable_output_ids"] = output_refs
    for invariant in INVARIANTS:
        validation_id = f"validation:{model_id}:{invariant.name}"
        facts["validations"].append({
            "id": validation_id,
            "contract": invariant.description,
            "obligation_id": f"obligation:native-invariant:{model_id}:{invariant.name}",
            "oracle_id": f"oracle:native-invariant:{model_id}:{invariant.name}",
            "subject_fingerprint": model_instance_fingerprint,
            "evidence_boundary_id": f"native-runner:{model_id}",
        })
        groundings[validation_id] = {"kind": "declared_invariant", "source_symbol": "INVARIANTS", "invariant_name": invariant.name}
    return compile_declared_path_quality_source(
        model_id=model_id, model_instance_fingerprint=model_instance_fingerprint,
        source_refs=(source_ref,), graph_scope="model_behavior",
        provider_kind="flowguard.explicit-event-dispatch.v1",
        model_facts=facts, element_groundings=groundings,
    )


__all__ = [
    "export_path_quality_source",
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
