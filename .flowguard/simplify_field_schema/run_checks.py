"""Run FlowGuard checks for direct field schema simplification."""

from __future__ import annotations

from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite

import model


REQUIRED_LABELS = (
    "spec_and_model_valid",
    "field_surfaces_removed",
    "focused_tests_passed",
    "broad_regression_passed",
    "sync_boundaries_checked",
    "done_accepted",
)


def run_workflow_suite() -> bool:
    exact_ok = run_exact_workflow_case(
        "correct_field_schema_cleanup",
        workflow=model.build_correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: state.done_claim == "accepted",
    )
    report = run_formal_workflow_suite(
        "simplify_field_schema",
        (
            FormalWorkflowCase("broken_keeps_fallback_surface", model.build_broken_fallback_workflow(), False),
            FormalWorkflowCase("broken_skips_broad_regression", model.build_broken_regression_workflow(), False),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=REQUIRED_LABELS,
        protected_error_class="field_schema_fallback_retained",
    )
    return exact_ok and report.ok


def main() -> int:
    workflow_checks = run_workflow_suite()
    route_reports = (
        ("architecture reduction", model.architecture_reduction_report()),
        ("development process flow", model.development_process_report()),
    )
    route_checks = []
    for label, report in route_reports:
        print(f"=== {label} ===")
        print(report.format_text())
        print()
        route_checks.append(report.ok)
    return 0 if workflow_checks and all(route_checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
