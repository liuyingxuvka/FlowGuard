"""Executable self-review model for FlowGuard's helper runner architecture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from flowguard import (
    FlowGuardCheckPlan,
    FunctionResult,
    Invariant,
    InvariantResult,
    RiskProfile,
    Scenario,
    ScenarioExpectation,
    Workflow,
    review_scenarios,
    run_model_first_checks,
)


@dataclass(frozen=True)
class RunnerCase:
    name: str


@dataclass(frozen=True)
class RunnerState:
    case_name: str = ""
    explorer_status: str = "not_run"
    audit_status: str = "not_run"
    summary_status: str = "not_run"
    conformance_status: str = "not_run"
    confidence_claim: str = "model_level"
    generated_scenarios_status: str = "not_generated"
    has_counterexample: bool = False
    minimizer_kept_original: bool = True
    direct_explorer_supported: bool = True
    runner_required: bool = False
    packs_required: bool = False
    notes: tuple[str, ...] = ()


CORRECT_RUNNER = RunnerCase("correct_runner_pass_with_gaps")
DIRECT_EXPLORER_ALLOWED = RunnerCase("direct_explorer_still_allowed")
BROKEN_EXPLORER_DOWNGRADED = RunnerCase("broken_explorer_failure_downgraded")
BROKEN_AUDIT_WARNING_PASS = RunnerCase("broken_audit_warning_reported_pass")
BROKEN_CONFORMANCE_OVERCLAIM = RunnerCase("broken_conformance_not_run_claims_production")
BROKEN_SCENARIO_AUTO_PASS = RunnerCase("broken_generated_scenario_treated_as_pass")
BROKEN_MINIMIZER_DROPS_ORIGINAL = RunnerCase("broken_minimizer_drops_original")
BROKEN_PACKS_MANDATORY = RunnerCase("broken_packs_or_runner_mandatory")


class EvaluateRunnerArchitecture:
    name = "EvaluateRunnerArchitecture"
    reads = ("case_name",)
    writes = (
        "case_name",
        "explorer_status",
        "audit_status",
        "summary_status",
        "conformance_status",
        "confidence_claim",
        "generated_scenarios_status",
        "has_counterexample",
        "minimizer_kept_original",
        "direct_explorer_supported",
        "runner_required",
        "packs_required",
        "notes",
    )

    def apply(self, input_obj: RunnerCase, state: RunnerState):
        del state
        return (
            FunctionResult(
                output=input_obj,
                new_state=_state_for_case(input_obj),
                label=input_obj.name,
            ),
        )


def _state_for_case(case: RunnerCase) -> RunnerState:
    if case == CORRECT_RUNNER:
        return RunnerState(
            case_name=case.name,
            explorer_status="pass",
            audit_status="pass_with_gaps",
            summary_status="pass_with_gaps",
            conformance_status="not_run",
            confidence_claim="model_level",
            generated_scenarios_status="needs_human_review",
            has_counterexample=False,
            minimizer_kept_original=True,
            direct_explorer_supported=True,
            runner_required=False,
            packs_required=False,
            notes=("correct helper-runner behavior",),
        )
    if case == DIRECT_EXPLORER_ALLOWED:
        return RunnerState(
            case_name=case.name,
            explorer_status="pass",
            audit_status="not_run",
            summary_status="pass",
            conformance_status="not_run",
            confidence_claim="model_level",
            direct_explorer_supported=True,
            runner_required=False,
            packs_required=False,
            notes=("minimal Explorer path remains valid",),
        )
    if case == BROKEN_EXPLORER_DOWNGRADED:
        return RunnerState(
            case_name=case.name,
            explorer_status="failed",
            audit_status="pass",
            summary_status="pass_with_gaps",
            conformance_status="not_run",
            confidence_claim="model_level",
            has_counterexample=True,
            minimizer_kept_original=True,
            notes=("Explorer failure must not be downgraded",),
        )
    if case == BROKEN_AUDIT_WARNING_PASS:
        return RunnerState(
            case_name=case.name,
            explorer_status="pass",
            audit_status="pass_with_gaps",
            summary_status="pass",
            conformance_status="not_run",
            confidence_claim="model_level",
            generated_scenarios_status="needs_human_review",
            notes=("Audit warning should keep pass_with_gaps",),
        )
    if case == BROKEN_CONFORMANCE_OVERCLAIM:
        return RunnerState(
            case_name=case.name,
            explorer_status="pass",
            audit_status="pass_with_gaps",
            summary_status="pass_with_gaps",
            conformance_status="not_run",
            confidence_claim="production_conformance",
            generated_scenarios_status="needs_human_review",
            notes=("No production confidence without conformance evidence",),
        )
    if case == BROKEN_SCENARIO_AUTO_PASS:
        return RunnerState(
            case_name=case.name,
            explorer_status="pass",
            audit_status="pass",
            summary_status="pass",
            conformance_status="not_run",
            confidence_claim="model_level",
            generated_scenarios_status="pass",
            notes=("Generated scenarios need human review",),
        )
    if case == BROKEN_MINIMIZER_DROPS_ORIGINAL:
        return RunnerState(
            case_name=case.name,
            explorer_status="failed",
            audit_status="pass",
            summary_status="failed",
            conformance_status="not_run",
            confidence_claim="model_level",
            has_counterexample=True,
            minimizer_kept_original=False,
            notes=("Minimizer must preserve original counterexample",),
        )
    if case == BROKEN_PACKS_MANDATORY:
        return RunnerState(
            case_name=case.name,
            explorer_status="pass",
            audit_status="pass",
            summary_status="pass",
            conformance_status="not_run",
            confidence_claim="model_level",
            direct_explorer_supported=False,
            runner_required=True,
            packs_required=True,
            notes=("Packs and runner must stay optional",),
        )
    raise ValueError(f"unknown runner case: {case!r}")


def _fail(name: str, message: str) -> InvariantResult:
    return InvariantResult.fail(message, {"violation": name})


def failed_explorer_forces_failed_summary(state: RunnerState, trace) -> InvariantResult:
    del trace
    if state.explorer_status == "failed" and state.summary_status != "failed":
        return _fail(
            "failed_explorer_forces_failed_summary",
            f"Explorer failed but summary was {state.summary_status!r}",
        )
    return InvariantResult.pass_()


def audit_warning_prevents_plain_pass(state: RunnerState, trace) -> InvariantResult:
    del trace
    if (
        state.explorer_status == "pass"
        and state.audit_status == "pass_with_gaps"
        and state.summary_status == "pass"
    ):
        return _fail(
            "audit_warning_prevents_plain_pass",
            "Audit warning was collapsed into plain pass",
        )
    return InvariantResult.pass_()


def no_production_confidence_without_conformance(state: RunnerState, trace) -> InvariantResult:
    del trace
    if (
        state.confidence_claim == "production_conformance"
        and state.conformance_status in {"not_run", "skipped_with_reason", "not_feasible"}
    ):
        return _fail(
            "no_production_confidence_without_conformance",
            "Production confidence was claimed without conformance evidence",
        )
    return InvariantResult.pass_()


def generated_scenarios_need_review(state: RunnerState, trace) -> InvariantResult:
    del trace
    if state.generated_scenarios_status == "pass":
        return _fail(
            "generated_scenarios_need_review",
            "Auto-generated scenarios were treated as pass instead of needs_human_review",
        )
    return InvariantResult.pass_()


def minimizer_preserves_original_counterexample(state: RunnerState, trace) -> InvariantResult:
    del trace
    if state.has_counterexample and not state.minimizer_kept_original:
        return _fail(
            "minimizer_preserves_original_counterexample",
            "Minimizer dropped the original failing sequence",
        )
    return InvariantResult.pass_()


def helper_flow_remains_optional(state: RunnerState, trace) -> InvariantResult:
    del trace
    if not state.direct_explorer_supported or state.runner_required or state.packs_required:
        return _fail(
            "helper_flow_remains_optional",
            "Runner or packs became mandatory and replaced direct Explorer usage",
        )
    return InvariantResult.pass_()


def build_workflow() -> Workflow:
    return Workflow((EvaluateRunnerArchitecture(),), name="flowguard_runner_self_review")


def invariants() -> tuple[Invariant, ...]:
    return (
        Invariant(
            "failed_explorer_forces_failed_summary",
            "Explorer failed implies summary failed",
            failed_explorer_forces_failed_summary,
        ),
        Invariant(
            "audit_warning_prevents_plain_pass",
            "Explorer pass plus audit warnings should be pass_with_gaps",
            audit_warning_prevents_plain_pass,
        ),
        Invariant(
            "no_production_confidence_without_conformance",
            "Production confidence requires conformance evidence",
            no_production_confidence_without_conformance,
        ),
        Invariant(
            "generated_scenarios_need_review",
            "Generated scenarios default to needs_human_review",
            generated_scenarios_need_review,
        ),
        Invariant(
            "minimizer_preserves_original_counterexample",
            "Minimizer keeps original failing sequence",
            minimizer_preserves_original_counterexample,
        ),
        Invariant(
            "helper_flow_remains_optional",
            "Runner and packs remain optional helper paths",
            helper_flow_remains_optional,
        ),
    )


def all_cases() -> tuple[RunnerCase, ...]:
    return (
        CORRECT_RUNNER,
        DIRECT_EXPLORER_ALLOWED,
        BROKEN_EXPLORER_DOWNGRADED,
        BROKEN_AUDIT_WARNING_PASS,
        BROKEN_CONFORMANCE_OVERCLAIM,
        BROKEN_SCENARIO_AUTO_PASS,
        BROKEN_MINIMIZER_DROPS_ORIGINAL,
        BROKEN_PACKS_MANDATORY,
    )


def self_review_scenarios() -> tuple[Scenario, ...]:
    expected_violations = {
        BROKEN_EXPLORER_DOWNGRADED.name: ("failed_explorer_forces_failed_summary",),
        BROKEN_AUDIT_WARNING_PASS.name: ("audit_warning_prevents_plain_pass",),
        BROKEN_CONFORMANCE_OVERCLAIM.name: ("no_production_confidence_without_conformance",),
        BROKEN_SCENARIO_AUTO_PASS.name: ("generated_scenarios_need_review",),
        BROKEN_MINIMIZER_DROPS_ORIGINAL.name: ("minimizer_preserves_original_counterexample",),
        BROKEN_PACKS_MANDATORY.name: ("helper_flow_remains_optional",),
    }
    workflow = build_workflow()
    checks = invariants()
    scenarios = []
    for case in all_cases():
        if case.name in expected_violations:
            expected = ScenarioExpectation(
                expected_status="violation",
                expected_violation_names=expected_violations[case.name],
                summary=f"VIOLATION; {expected_violations[case.name][0]}",
            )
        else:
            expected = ScenarioExpectation(
                expected_status="ok",
                summary="OK; helper runner architecture preserves intended boundary",
            )
        scenarios.append(
            Scenario(
                name=case.name,
                description=f"Review runner architecture case {case.name}",
                initial_state=RunnerState(),
                external_input_sequence=(case,),
                expected=expected,
                workflow=workflow,
                invariants=checks,
                tags=("flowguard_runner_self_review",),
            )
        )
    return tuple(scenarios)


def run_runner_self_review():
    return review_scenarios(self_review_scenarios())


def run_runner_self_check_summary():
    """Exercise the new RiskProfile + FlowGuardCheckPlan + runner path."""

    plan = FlowGuardCheckPlan(
        workflow=build_workflow(),
        initial_states=(RunnerState(),),
        external_inputs=(CORRECT_RUNNER, DIRECT_EXPLORER_ALLOWED),
        invariants=invariants(),
        max_sequence_length=1,
        risk_profile=RiskProfile(
            modeled_boundary="FlowGuard helper runner architecture",
            risk_classes=("deduplication", "conformance"),
            confidence_goal="model_level",
            skipped_checks=(
                {
                    "name": "production_conformance",
                    "reason": "self-review models FlowGuard helper architecture, not production adapter behavior",
                    "status": "not_feasible",
                },
            ),
        ),
        scenario_matrix_config={"max_scenarios": 4},
    )
    return run_model_first_checks(plan)


def representative_summary_lines(report) -> tuple[str, ...]:
    return tuple(
        f"{section.name}:{section.status}:{section.summary}"
        for section in report.sections
    )


__all__ = [
    "BROKEN_AUDIT_WARNING_PASS",
    "BROKEN_CONFORMANCE_OVERCLAIM",
    "BROKEN_EXPLORER_DOWNGRADED",
    "BROKEN_MINIMIZER_DROPS_ORIGINAL",
    "BROKEN_PACKS_MANDATORY",
    "BROKEN_SCENARIO_AUTO_PASS",
    "CORRECT_RUNNER",
    "DIRECT_EXPLORER_ALLOWED",
    "RunnerCase",
    "RunnerState",
    "all_cases",
    "build_workflow",
    "invariants",
    "representative_summary_lines",
    "run_runner_self_check_summary",
    "run_runner_self_review",
    "self_review_scenarios",
]
