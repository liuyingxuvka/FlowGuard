"""Run FlowGuard checks for AI-facing field prompt reduction."""

from __future__ import annotations

from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite
import model


REQUIRED_LABELS = (
            "fields_grouped",
            "tests_added",
            "focused_validation_passed",
            "broad_regression_complete",
            "local_surfaces_synced",
            "done_accepted",
)


def main() -> int:
    report = run_formal_workflow_suite(
        "field_prompt_reduction",
        (
            FormalWorkflowCase("correct_field_prompt_reduction", model.build_correct_workflow(), True, required_labels=REQUIRED_LABELS),
            FormalWorkflowCase("broken_drops_required_evidence", model.build_broken_evidence_workflow(), False, required_labels=REQUIRED_LABELS),
            FormalWorkflowCase("broken_prompt_only_completion", model.build_broken_prompt_only_workflow(), False, required_labels=REQUIRED_LABELS),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        protected_error_class="prompt_only_completion",
    )
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
