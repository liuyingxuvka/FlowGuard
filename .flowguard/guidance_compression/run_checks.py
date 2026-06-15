"""Run FlowGuard checks for AI guidance compression."""

from __future__ import annotations

from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite
import model


REQUIRED_LABELS = (
            "guidance_compressed",
            "budget_tests_added",
            "validations_passed",
            "local_surfaces_synced",
            "done_accepted",
)


def main() -> int:
    workflow_report = run_formal_workflow_suite(
        "guidance_compression",
        (
            FormalWorkflowCase("correct_guidance_compression", model.build_correct_workflow(), True, required_labels=REQUIRED_LABELS),
            FormalWorkflowCase("broken_prompt_only_completion", model.build_broken_workflow(), False, required_labels=REQUIRED_LABELS),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        protected_error_class="guidance_prompt_only_completion",
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
    return 0 if workflow_report.ok and all(report_checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
