"""Run FlowGuard checks for AI guidance compression."""

from __future__ import annotations

from flowguard import Explorer
import model


def run_workflow(name: str, workflow, *, expect_ok: bool) -> bool:
    report = Explorer(
        workflow=workflow,
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=(
            "guidance_compressed",
            "budget_tests_added",
            "validations_passed",
            "local_surfaces_synced",
            "done_accepted",
        ),
    ).explore()
    ok = report.ok
    print(f"{name}: {'OK' if ok else 'VIOLATION'}")
    print(report.format_text(max_examples=1))
    print()
    return ok is expect_ok


def main() -> int:
    workflow_checks = (
        run_workflow("correct_guidance_compression", model.build_correct_workflow(), expect_ok=True),
        run_workflow("broken_prompt_only_completion", model.build_broken_workflow(), expect_ok=False),
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
    return 0 if all(workflow_checks) and all(report_checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
