"""Run FlowGuard checks for legacy compatibility cleanup."""

from __future__ import annotations

from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite
import model


REQUIRED_LABELS = (
            "audit_classified",
            "route_first_replacement_done",
            "focused_validation_passed",
            "local_surfaces_synced",
            "done_accepted",
)


def main() -> int:
    exact_ok = run_exact_workflow_case(
        "correct_legacy_compatibility_cleanup",
        workflow=model.build_correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: state.done_claim == "accepted",
    )
    workflow_report = run_formal_workflow_suite(
        "legacy_compatibility_cleanup",
        (
            FormalWorkflowCase("broken_deletes_safety_classifier", model.build_broken_safety_workflow(), False, required_labels=REQUIRED_LABELS),
            FormalWorkflowCase("broken_skips_installed_skill_parity", model.build_broken_installed_skill_workflow(), False, required_labels=REQUIRED_LABELS),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        protected_error_class="legacy_compatibility_cleanup_gap",
    )
    reports = (
        ("architecture reduction", model.architecture_reduction_report()),
        ("development process flow", model.development_process_report()),
    )
    report_checks = []
    for label, report in reports:
        print(f"=== {label} ===")
        print(report.format_text())
        print()
        report_checks.append(report.ok)
    return 0 if exact_ok and workflow_report.ok and all(report_checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
