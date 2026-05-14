"""FlowGuard Risk Purpose Header.

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review the implementation plan for budgeted model-group execution.
Guards against: progress-only sharding, rerunning every shard from scratch,
silent stale result reuse, per-shard pass misreported as whole-model pass,
memory-heavy full graph retention, local-only reachability checks, lightweight
substitute models, and release sync omissions.
Use before editing: run before changing budgeted graph execution, large-model
reporting, docs, version files, or release workflow for this feature.
Run: `python examples/budgeted_model_groups/run_checks.py`
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Sequence

from flowguard import (
    FunctionResult,
    Invariant,
    InvariantResult,
    Scenario,
    ScenarioExpectation,
    Workflow,
    review_scenarios,
)


@dataclass(frozen=True)
class BudgetedGroupPlan:
    graph_helper_added: bool = False
    default_budget: int = 0
    ledger_kind: str = "none"
    ledger_records_seen: bool = False
    ledger_records_pending: bool = False
    ledger_records_processed: bool = False
    resume_policy: str = "none"
    fingerprint_policy: str = "none"
    memory_policy: str = "full_graph"
    shard_progress: bool = False
    group_progress: bool = False
    incomplete_status_policy: str = "unknown"
    global_label_policy: str = "per_shard"
    invariant_policy: str = "per_shard"
    lightweight_fallback: bool = False
    explorer_compatibility: bool = False
    focused_tests_added: bool = False
    docs_added: bool = False
    release_sync_checks: bool = False
    finalized: bool = False


@dataclass(frozen=True)
class PlanDecision:
    name: str


class ApplyBudgetedGroupDecision:
    name = "ApplyBudgetedGroupDecision"
    reads = ("BudgetedGroupPlan",)
    writes = ("BudgetedGroupPlan",)
    input_description = "PlanDecision"
    output_description = "BudgetedGroupPlan"
    accepted_input_type = PlanDecision

    def apply(
        self,
        input_obj: PlanDecision,
        state: BudgetedGroupPlan,
    ) -> Iterable[FunctionResult]:
        decision = input_obj.name
        new_state = apply_decision(decision, state)
        yield FunctionResult(
            output=input_obj,
            new_state=new_state,
            label=decision,
            reason=f"applied budgeted model-group decision {decision}",
        )


def apply_decision(decision: str, state: BudgetedGroupPlan) -> BudgetedGroupPlan:
    if decision == "add_graph_helper":
        return replace(state, graph_helper_added=True)
    if decision == "set_budget_10000":
        return replace(state, default_budget=10_000)
    if decision == "set_budget_100000":
        return replace(state, default_budget=100_000)
    if decision == "use_sqlite_ledger":
        return replace(state, ledger_kind="sqlite")
    if decision == "use_json_summary_only":
        return replace(state, ledger_kind="json_summary")
    if decision == "record_seen_pending_processed":
        return replace(
            state,
            ledger_records_seen=True,
            ledger_records_pending=True,
            ledger_records_processed=True,
        )
    if decision == "record_only_shard_summary":
        return replace(
            state,
            ledger_records_seen=False,
            ledger_records_pending=False,
            ledger_records_processed=False,
        )
    if decision == "resume_from_pending":
        return replace(state, resume_policy="pending_queue")
    if decision == "restart_from_initial":
        return replace(state, resume_policy="restart")
    if decision == "fingerprint_model_inputs":
        return replace(state, fingerprint_policy="model_inputs")
    if decision == "reuse_fixed_directory":
        return replace(state, fingerprint_policy="fixed_directory")
    if decision == "process_budgeted_frontier":
        return replace(state, memory_policy="budgeted_frontier")
    if decision == "build_full_graph_first":
        return replace(state, memory_policy="full_graph")
    if decision == "emit_shard_progress":
        return replace(state, shard_progress=True)
    if decision == "emit_group_progress":
        return replace(state, group_progress=True)
    if decision == "mark_pending_as_incomplete":
        return replace(state, incomplete_status_policy="incomplete_not_ok")
    if decision == "mark_shard_pass_as_ok":
        return replace(state, incomplete_status_policy="shard_pass_ok")
    if decision == "check_labels_globally":
        return replace(state, global_label_policy="whole_group")
    if decision == "check_labels_per_shard":
        return replace(state, global_label_policy="per_shard")
    if decision == "aggregate_invariants_globally":
        return replace(state, invariant_policy="whole_group")
    if decision == "check_invariants_per_shard_only":
        return replace(state, invariant_policy="per_shard")
    if decision == "allow_lightweight_fallback":
        return replace(state, lightweight_fallback=True)
    if decision == "forbid_lightweight_fallback":
        return replace(state, lightweight_fallback=False)
    if decision == "preserve_explorer_behavior":
        return replace(state, explorer_compatibility=True)
    if decision == "add_focused_tests":
        return replace(state, focused_tests_added=True)
    if decision == "add_docs":
        return replace(state, docs_added=True)
    if decision == "release_sync_checks":
        return replace(state, release_sync_checks=True)
    if decision == "finalize":
        return replace(state, finalized=True)
    return state


def _not_final(state: BudgetedGroupPlan) -> bool:
    return not state.finalized


def _pass() -> InvariantResult:
    return InvariantResult.pass_()


def _fail(message: str) -> InvariantResult:
    return InvariantResult.fail(message)


def graph_helper_and_budget_exist(state: BudgetedGroupPlan, _trace: object) -> InvariantResult:
    if _not_final(state):
        return _pass()
    if not state.graph_helper_added:
        return _fail("large graph models need a dedicated budgeted graph helper")
    if state.default_budget != 10_000:
        return _fail("default shard budget must be 10,000 processed states")
    return _pass()


def ledger_can_continue_without_restarting(state: BudgetedGroupPlan, _trace: object) -> InvariantResult:
    if _not_final(state):
        return _pass()
    if state.ledger_kind != "sqlite":
        return _fail("model group needs a durable SQLite ledger")
    if not (state.ledger_records_seen and state.ledger_records_pending and state.ledger_records_processed):
        return _fail("ledger must record seen, pending, and processed states")
    if state.resume_policy != "pending_queue":
        return _fail("reruns must resume from pending states instead of restarting")
    return _pass()


def fingerprint_prevents_stale_reuse(state: BudgetedGroupPlan, _trace: object) -> InvariantResult:
    if _not_final(state):
        return _pass()
    if state.fingerprint_policy != "model_inputs":
        return _fail("changed model inputs must get a separate ledger fingerprint")
    return _pass()


def memory_is_reduced_by_design(state: BudgetedGroupPlan, _trace: object) -> InvariantResult:
    if _not_final(state):
        return _pass()
    if state.memory_policy != "budgeted_frontier":
        return _fail("runner must process a budgeted frontier instead of building the full graph first")
    return _pass()


def progress_has_two_levels(state: BudgetedGroupPlan, _trace: object) -> InvariantResult:
    if _not_final(state):
        return _pass()
    if not state.shard_progress:
        return _fail("current shard still needs bounded ten-step progress")
    if not state.group_progress:
        return _fail("whole model group progress must show pending and processed work")
    return _pass()


def incomplete_group_is_not_ok(state: BudgetedGroupPlan, _trace: object) -> InvariantResult:
    if _not_final(state):
        return _pass()
    if state.incomplete_status_policy != "incomplete_not_ok":
        return _fail("a finished shard with pending states must be incomplete, not OK")
    return _pass()


def results_are_global_not_per_shard(state: BudgetedGroupPlan, _trace: object) -> InvariantResult:
    if _not_final(state):
        return _pass()
    if state.global_label_policy != "whole_group":
        return _fail("required labels must be checked across the whole model group")
    if state.invariant_policy != "whole_group":
        return _fail("invariant failures from any shard must fail the whole model group")
    return _pass()


def no_lightweight_substitute_model(state: BudgetedGroupPlan, _trace: object) -> InvariantResult:
    if _not_final(state):
        return _pass()
    if state.lightweight_fallback:
        return _fail("large-model checks must not silently switch to a lightweight substitute")
    return _pass()


def compatibility_tests_docs_and_release_sync(state: BudgetedGroupPlan, _trace: object) -> InvariantResult:
    if _not_final(state):
        return _pass()
    if not state.explorer_compatibility:
        return _fail("existing Explorer progress behavior must remain compatible")
    if not state.focused_tests_added:
        return _fail("focused tests must cover sharding, resume, and reporting")
    if not state.docs_added:
        return _fail("docs/example must show how callers use the budgeted model group")
    if not state.release_sync_checks:
        return _fail("release must include install, shadow workspace, git, and GitHub sync checks")
    return _pass()


INVARIANTS = (
    Invariant(
        "graph_helper_and_budget_exist",
        "The plan must add a graph-style helper with a 10,000-state default shard budget.",
        graph_helper_and_budget_exist,
    ),
    Invariant(
        "ledger_can_continue_without_restarting",
        "The plan must persist a ledger and resume from pending states.",
        ledger_can_continue_without_restarting,
    ),
    Invariant(
        "fingerprint_prevents_stale_reuse",
        "Changed model inputs cannot reuse stale ledger results.",
        fingerprint_prevents_stale_reuse,
    ),
    Invariant(
        "memory_is_reduced_by_design",
        "The runner must avoid building the full graph before processing shards.",
        memory_is_reduced_by_design,
    ),
    Invariant(
        "progress_has_two_levels",
        "Progress must distinguish current shard progress from whole-group progress.",
        progress_has_two_levels,
    ),
    Invariant(
        "incomplete_group_is_not_ok",
        "A shard-local pass cannot become whole-model OK while pending states remain.",
        incomplete_group_is_not_ok,
    ),
    Invariant(
        "results_are_global_not_per_shard",
        "Labels and invariant failures must be aggregated across the whole group.",
        results_are_global_not_per_shard,
    ),
    Invariant(
        "no_lightweight_substitute_model",
        "The plan must not use a lightweight substitute model as a fallback.",
        no_lightweight_substitute_model,
    ),
    Invariant(
        "compatibility_tests_docs_and_release_sync",
        "Compatibility, tests, docs, and release synchronization are required.",
        compatibility_tests_docs_and_release_sync,
    ),
)


CORRECT_PLAN = (
    "add_graph_helper",
    "set_budget_10000",
    "use_sqlite_ledger",
    "record_seen_pending_processed",
    "resume_from_pending",
    "fingerprint_model_inputs",
    "process_budgeted_frontier",
    "emit_shard_progress",
    "emit_group_progress",
    "mark_pending_as_incomplete",
    "check_labels_globally",
    "aggregate_invariants_globally",
    "forbid_lightweight_fallback",
    "preserve_explorer_behavior",
    "add_focused_tests",
    "add_docs",
    "release_sync_checks",
    "finalize",
)


def _decisions(names: Sequence[str]) -> tuple[PlanDecision, ...]:
    return tuple(PlanDecision(name) for name in names)


def _scenario(
    name: str,
    description: str,
    decisions: Sequence[str],
    expected: ScenarioExpectation,
) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        initial_state=BudgetedGroupPlan(),
        external_input_sequence=_decisions(decisions),
        expected=expected,
        workflow=Workflow((ApplyBudgetedGroupDecision(),), name="budgeted_model_group_rollout"),
        invariants=INVARIANTS,
        tags=("budgeted_model_groups",),
    )


def _expect_ok() -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="ok",
        required_trace_labels=("finalize",),
        summary="OK; budgeted model-group rollout is complete",
    )


def _expect_violation(name: str) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="violation",
        expected_violation_names=(name,),
        summary=f"VIOLATION; {name}",
    )


def budgeted_model_group_scenarios() -> tuple[Scenario, ...]:
    return (
        _scenario(
            "BMG01_correct_budgeted_model_group_plan_passes",
            "The agreed plan shards graph models, persists a ledger, resumes, and reports whole-group status.",
            CORRECT_PLAN,
            _expect_ok(),
        ),
        _scenario(
            "BMGB01_progress_only_sharding_is_not_enough",
            "Broken plan emits progress but never adds a budgeted graph helper.",
            CORRECT_PLAN[1:],
            _expect_violation("graph_helper_and_budget_exist"),
        ),
        _scenario(
            "BMGB02_budget_100000_ignores_user_threshold",
            "Broken plan uses a 100,000-state default instead of the agreed 10,000-state budget.",
            ("add_graph_helper", "set_budget_100000") + CORRECT_PLAN[2:],
            _expect_violation("graph_helper_and_budget_exist"),
        ),
        _scenario(
            "BMGB03_summary_only_ledger_cannot_resume",
            "Broken plan records only per-shard summaries and cannot continue safely.",
            CORRECT_PLAN[:2] + ("use_json_summary_only", "record_only_shard_summary") + CORRECT_PLAN[4:],
            _expect_violation("ledger_can_continue_without_restarting"),
        ),
        _scenario(
            "BMGB04_restart_from_initial_wastes_work",
            "Broken plan restarts later shards from the initial state.",
            CORRECT_PLAN[:4] + ("restart_from_initial",) + CORRECT_PLAN[5:],
            _expect_violation("ledger_can_continue_without_restarting"),
        ),
        _scenario(
            "BMGB05_fixed_directory_reuses_stale_results",
            "Broken plan reuses the same directory even after the model changes.",
            CORRECT_PLAN[:5] + ("reuse_fixed_directory",) + CORRECT_PLAN[6:],
            _expect_violation("fingerprint_prevents_stale_reuse"),
        ),
        _scenario(
            "BMGB06_full_graph_first_keeps_memory_heavy",
            "Broken plan builds the full graph before splitting output.",
            CORRECT_PLAN[:6] + ("build_full_graph_first",) + CORRECT_PLAN[7:],
            _expect_violation("memory_is_reduced_by_design"),
        ),
        _scenario(
            "BMGB07_missing_group_progress_hides_total_status",
            "Broken plan shows shard progress but not model-group pending work.",
            CORRECT_PLAN[:8] + CORRECT_PLAN[9:],
            _expect_violation("progress_has_two_levels"),
        ),
        _scenario(
            "BMGB08_shard_pass_misreported_as_ok",
            "Broken plan marks one passing shard as OK while the queue still has pending states.",
            CORRECT_PLAN[:9] + ("mark_shard_pass_as_ok",) + CORRECT_PLAN[10:],
            _expect_violation("incomplete_group_is_not_ok"),
        ),
        _scenario(
            "BMGB09_labels_checked_per_shard",
            "Broken plan checks required labels inside each shard instead of globally.",
            CORRECT_PLAN[:10] + ("check_labels_per_shard",) + CORRECT_PLAN[11:],
            _expect_violation("results_are_global_not_per_shard"),
        ),
        _scenario(
            "BMGB10_invariants_checked_per_shard_only",
            "Broken plan loses invariant failures from earlier shards.",
            CORRECT_PLAN[:11] + ("check_invariants_per_shard_only",) + CORRECT_PLAN[12:],
            _expect_violation("results_are_global_not_per_shard"),
        ),
        _scenario(
            "BMGB11_lightweight_fallback_is_not_allowed",
            "Broken plan silently substitutes a smaller model when the real model is too large.",
            CORRECT_PLAN[:12] + ("allow_lightweight_fallback",) + CORRECT_PLAN[13:],
            _expect_violation("no_lightweight_substitute_model"),
        ),
        _scenario(
            "BMGB12_missing_release_sync_checks",
            "Broken plan ships without install, shadow workspace, git, and GitHub synchronization checks.",
            CORRECT_PLAN[:-2] + ("finalize",),
            _expect_violation("compatibility_tests_docs_and_release_sync"),
        ),
    )


def run_budgeted_model_group_review():
    return review_scenarios(budgeted_model_group_scenarios())


__all__ = [
    "BudgetedGroupPlan",
    "PlanDecision",
    "budgeted_model_group_scenarios",
    "run_budgeted_model_group_review",
]
