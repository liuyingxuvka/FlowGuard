"""FlowGuard Risk Purpose Header.

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review the implementation plan for Explorer progress heartbeat output.
Guards against: template-only progress, stdout pollution, noisy per-sequence
logging, missing small-model progress, threshold rounding bugs, changed report
semantics, missing opt-outs, duplicate runner/template logic, and release sync
omissions.
Use before editing: run before changing `flowguard/explorer.py`, templates,
docs, version files, or release workflow for this feature.
Run: `python examples/flowguard_progress_heartbeat/run_checks.py`
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
class HeartbeatPlan:
    core_explorer_changed: bool = False
    top_level_work_counted: bool = False
    progress_stream: str = "none"
    progress_style: str = "none"
    progress_steps: int = 0
    small_total_policy: str = "none"
    threshold_policy: str = "none"
    report_semantics_unchanged: bool = False
    api_optout: bool = False
    env_optout: bool = False
    runner_policy: str = "none"
    template_policy: str = "none"
    focused_tests_added: bool = False
    release_sync_checks: bool = False
    finalized: bool = False


@dataclass(frozen=True)
class PlanDecision:
    name: str


class ApplyPlanDecision:
    name = "ApplyPlanDecision"
    reads = ("HeartbeatPlan",)
    writes = ("HeartbeatPlan",)
    input_description = "PlanDecision"
    output_description = "HeartbeatPlan"
    idempotency = "same decision overwrites the same plan field"
    accepted_input_type = PlanDecision

    def apply(self, input_obj: PlanDecision, state: HeartbeatPlan) -> Iterable[FunctionResult]:
        decision = input_obj.name
        new_state = apply_decision(decision, state)
        yield FunctionResult(
            output=input_obj,
            new_state=new_state,
            label=decision,
            reason=f"applied plan decision {decision}",
        )


def apply_decision(decision: str, state: HeartbeatPlan) -> HeartbeatPlan:
    if decision == "change_core_explorer":
        return replace(state, core_explorer_changed=True)
    if decision == "template_only_progress":
        return replace(state, core_explorer_changed=False, template_policy="custom_progress_loop")
    if decision == "count_initial_state_sequence_work":
        return replace(state, top_level_work_counted=True)
    if decision == "use_stderr":
        return replace(state, progress_stream="stderr")
    if decision == "use_stdout":
        return replace(state, progress_stream="stdout")
    if decision == "use_ten_step_buckets":
        return replace(state, progress_style="bucket", progress_steps=10)
    if decision == "use_one_percent_buckets":
        return replace(state, progress_style="bucket", progress_steps=100)
    if decision == "use_per_sequence_output":
        return replace(state, progress_style="per_sequence", progress_steps=0)
    if decision == "support_small_totals":
        return replace(state, small_total_policy="emit_each_until_100")
    if decision == "skip_small_total_progress":
        return replace(state, small_total_policy="skip_until_threshold")
    if decision == "use_unique_ceil_thresholds":
        return replace(state, threshold_policy="ceil_unique_ending_100")
    if decision == "use_floor_thresholds":
        return replace(state, threshold_policy="floor_can_skip")
    if decision == "preserve_report_semantics":
        return replace(state, report_semantics_unchanged=True)
    if decision == "change_report_semantics":
        return replace(state, report_semantics_unchanged=False)
    if decision == "add_api_optout":
        return replace(state, api_optout=True)
    if decision == "add_env_optout":
        return replace(state, env_optout=True)
    if decision == "runner_inherits_core":
        return replace(state, runner_policy="inherit_core")
    if decision == "runner_custom_progress":
        return replace(state, runner_policy="custom_progress")
    if decision == "templates_reference_core":
        return replace(state, template_policy="plain_explorer")
    if decision == "templates_custom_progress":
        return replace(state, template_policy="custom_progress_loop")
    if decision == "add_focused_tests":
        return replace(state, focused_tests_added=True)
    if decision == "release_sync_checks":
        return replace(state, release_sync_checks=True)
    if decision == "finalize":
        return replace(state, finalized=True)
    return state


def _not_final(state: HeartbeatPlan) -> bool:
    return not state.finalized


def _pass() -> InvariantResult:
    return InvariantResult.pass_()


def _fail(message: str) -> InvariantResult:
    return InvariantResult.fail(message)


def core_change_reaches_old_callers(state: HeartbeatPlan, _trace: object) -> InvariantResult:
    if _not_final(state):
        return _pass()
    if not state.core_explorer_changed:
        return _fail("progress must be implemented in core Explorer so old callers inherit it")
    if not state.top_level_work_counted:
        return _fail("progress must count initial_state x input_sequence top-level work")
    return _pass()


def progress_uses_stderr(state: HeartbeatPlan, _trace: object) -> InvariantResult:
    if _not_final(state):
        return _pass()
    if state.progress_stream != "stderr":
        return _fail("progress output must use stderr, not stdout")
    return _pass()


def progress_is_bounded_ten_step(state: HeartbeatPlan, _trace: object) -> InvariantResult:
    if _not_final(state):
        return _pass()
    if state.progress_style != "bucket" or state.progress_steps != 10:
        return _fail("default progress must use bounded ten-step buckets")
    return _pass()


def small_totals_still_report(state: HeartbeatPlan, _trace: object) -> InvariantResult:
    if _not_final(state):
        return _pass()
    if state.small_total_policy != "emit_each_until_100":
        return _fail("small totals must still emit useful progress through 100%")
    return _pass()


def thresholds_are_unique_and_finish(state: HeartbeatPlan, _trace: object) -> InvariantResult:
    if _not_final(state):
        return _pass()
    if state.threshold_policy != "ceil_unique_ending_100":
        return _fail("thresholds must be monotonic, unique, and end at 100%")
    return _pass()


def report_semantics_stay_unchanged(state: HeartbeatPlan, _trace: object) -> InvariantResult:
    if _not_final(state):
        return _pass()
    if not state.report_semantics_unchanged:
        return _fail("progress must not change CheckReport pass/fail or trace semantics")
    return _pass()


def optouts_exist(state: HeartbeatPlan, _trace: object) -> InvariantResult:
    if _not_final(state):
        return _pass()
    if not state.api_optout or not state.env_optout:
        return _fail("progress must support both API and environment opt-out")
    return _pass()


def runner_and_templates_do_not_fork_logic(state: HeartbeatPlan, _trace: object) -> InvariantResult:
    if _not_final(state):
        return _pass()
    if state.runner_policy != "inherit_core":
        return _fail("runner must inherit core Explorer progress instead of adding duplicate logic")
    if state.template_policy != "plain_explorer":
        return _fail("templates must keep plain Explorer calls and not copy progress loops")
    return _pass()


def tests_and_release_sync_are_required(state: HeartbeatPlan, _trace: object) -> InvariantResult:
    if _not_final(state):
        return _pass()
    if not state.focused_tests_added:
        return _fail("focused regression tests must cover progress behavior")
    if not state.release_sync_checks:
        return _fail("release must include local install and shadow workspace sync checks")
    return _pass()


INVARIANTS = (
    Invariant(
        "core_change_reaches_old_callers",
        "Core Explorer progress reaches existing model scripts without caller edits.",
        core_change_reaches_old_callers,
    ),
    Invariant(
        "progress_uses_stderr",
        "Progress must not pollute stdout report or JSON pipelines.",
        progress_uses_stderr,
    ),
    Invariant(
        "progress_is_bounded_ten_step",
        "Default progress is a bounded ten-step signal, not per-sequence noise.",
        progress_is_bounded_ten_step,
    ),
    Invariant(
        "small_totals_still_report",
        "Tiny runs still emit useful progress and reach 100%.",
        small_totals_still_report,
    ),
    Invariant(
        "thresholds_are_unique_and_finish",
        "Threshold rounding cannot skip or duplicate progress buckets.",
        thresholds_are_unique_and_finish,
    ),
    Invariant(
        "report_semantics_stay_unchanged",
        "Heartbeat output cannot change model pass/fail or trace semantics.",
        report_semantics_stay_unchanged,
    ),
    Invariant(
        "optouts_exist",
        "Strict CI and API callers can disable progress.",
        optouts_exist,
    ),
    Invariant(
        "runner_and_templates_do_not_fork_logic",
        "Runner and templates inherit the core implementation instead of duplicating it.",
        runner_and_templates_do_not_fork_logic,
    ),
    Invariant(
        "tests_and_release_sync_are_required",
        "Focused tests and release sync checks are part of completion.",
        tests_and_release_sync_are_required,
    ),
)


CORRECT_PLAN = (
    "change_core_explorer",
    "count_initial_state_sequence_work",
    "use_stderr",
    "use_ten_step_buckets",
    "support_small_totals",
    "use_unique_ceil_thresholds",
    "preserve_report_semantics",
    "add_api_optout",
    "add_env_optout",
    "runner_inherits_core",
    "templates_reference_core",
    "add_focused_tests",
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
        initial_state=HeartbeatPlan(),
        external_input_sequence=_decisions(decisions),
        expected=expected,
        workflow=Workflow((ApplyPlanDecision(),), name="progress_heartbeat_rollout"),
        invariants=INVARIANTS,
        tags=("progress_heartbeat",),
    )


def _expect_ok() -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="ok",
        required_trace_labels=("finalize",),
        summary="OK; minimal serial ten-step Explorer progress rollout is complete",
    )


def _expect_violation(name: str) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="violation",
        expected_violation_names=(name,),
        summary=f"VIOLATION; {name}",
    )


def progress_heartbeat_scenarios() -> tuple[Scenario, ...]:
    return (
        _scenario(
            "PH01_correct_minimal_rollout_passes",
            "The agreed minimal serial Explorer heartbeat rollout includes every required guard.",
            CORRECT_PLAN,
            _expect_ok(),
        ),
        _scenario(
            "PHB01_template_only_progress_does_not_reach_old_callers",
            "Broken plan only updates templates, so old Explorer callers do not inherit progress.",
            ("template_only_progress",) + CORRECT_PLAN[1:],
            _expect_violation("core_change_reaches_old_callers"),
        ),
        _scenario(
            "PHB02_stdout_progress_breaks_pipelines",
            "Broken plan writes progress to stdout.",
            CORRECT_PLAN[:2] + ("use_stdout",) + CORRECT_PLAN[3:],
            _expect_violation("progress_uses_stderr"),
        ),
        _scenario(
            "PHB03_per_sequence_progress_is_too_noisy",
            "Broken plan emits progress for every sequence.",
            CORRECT_PLAN[:3] + ("use_per_sequence_output",) + CORRECT_PLAN[4:],
            _expect_violation("progress_is_bounded_ten_step"),
        ),
        _scenario(
            "PHB04_one_percent_default_is_out_of_scope",
            "Broken plan defaults to one hundred progress buckets instead of ten.",
            CORRECT_PLAN[:3] + ("use_one_percent_buckets",) + CORRECT_PLAN[4:],
            _expect_violation("progress_is_bounded_ten_step"),
        ),
        _scenario(
            "PHB05_small_totals_skip_progress",
            "Broken plan skips useful progress for tiny totals.",
            CORRECT_PLAN[:4] + ("skip_small_total_progress",) + CORRECT_PLAN[5:],
            _expect_violation("small_totals_still_report"),
        ),
        _scenario(
            "PHB06_floor_thresholds_can_skip_or_duplicate",
            "Broken plan uses unsafe threshold rounding.",
            CORRECT_PLAN[:5] + ("use_floor_thresholds",) + CORRECT_PLAN[6:],
            _expect_violation("thresholds_are_unique_and_finish"),
        ),
        _scenario(
            "PHB07_progress_changes_report_semantics",
            "Broken plan lets progress affect CheckReport semantics.",
            CORRECT_PLAN[:6] + ("change_report_semantics",) + CORRECT_PLAN[7:],
            _expect_violation("report_semantics_stay_unchanged"),
        ),
        _scenario(
            "PHB08_missing_environment_optout",
            "Broken plan leaves strict environments unable to silence progress.",
            CORRECT_PLAN[:8] + CORRECT_PLAN[9:],
            _expect_violation("optouts_exist"),
        ),
        _scenario(
            "PHB09_runner_duplicates_progress_logic",
            "Broken plan adds a second runner progress implementation.",
            CORRECT_PLAN[:9] + ("runner_custom_progress",) + CORRECT_PLAN[10:],
            _expect_violation("runner_and_templates_do_not_fork_logic"),
        ),
        _scenario(
            "PHB10_templates_copy_progress_loop",
            "Broken plan copies progress logic into generated templates.",
            CORRECT_PLAN[:10] + ("templates_custom_progress",) + CORRECT_PLAN[11:],
            _expect_violation("runner_and_templates_do_not_fork_logic"),
        ),
        _scenario(
            "PHB11_missing_release_sync_checks",
            "Broken plan tries to publish without local install and shadow workspace sync checks.",
            CORRECT_PLAN[:-2] + ("finalize",),
            _expect_violation("tests_and_release_sync_are_required"),
        ),
    )


def run_progress_heartbeat_review():
    return review_scenarios(progress_heartbeat_scenarios())


__all__ = [
    "HeartbeatPlan",
    "PlanDecision",
    "progress_heartbeat_scenarios",
    "run_progress_heartbeat_review",
]

