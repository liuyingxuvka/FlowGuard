"""Run the FlowGuard closure-contract model checks."""

from __future__ import annotations

from flowguard import Scenario, ScenarioExpectation, review_scenarios
import model


def run_scenarios() -> bool:
    scenarios = (
        Scenario(
            "good_closure_contract",
            "complete FlowGuard use consumes every closure gate",
            model.initial_state(),
            model.GOOD_SEQUENCE,
            ScenarioExpectation(expected_status="ok"),
            workflow=model.build_correct_workflow(),
        ),
        Scenario(
            "broken_point_evidence_completion",
            "model ownership plus alignment is not enough for complete FlowGuard use",
            model.initial_state(),
            model.BROKEN_POINT_SEQUENCE,
            ScenarioExpectation(
                expected_status="violation",
                expected_violation_names=("no_complete_claim_without_closure",),
            ),
            workflow=model.build_broken_workflow(),
        ),
        Scenario(
            "broken_optional_mode",
            "closure cannot be described as an optional/default mode",
            model.initial_state(),
            model.BROKEN_MODE_SEQUENCE,
            ScenarioExpectation(
                expected_status="violation",
                expected_violation_names=("closure_is_not_optional_mode",),
            ),
            workflow=model.build_correct_workflow(),
        ),
    )
    report = review_scenarios(scenarios, default_invariants=model.INVARIANTS)
    print(report.format_text())
    return report.ok


def main() -> int:
    return 0 if run_scenarios() else 1


if __name__ == "__main__":
    raise SystemExit(main())
