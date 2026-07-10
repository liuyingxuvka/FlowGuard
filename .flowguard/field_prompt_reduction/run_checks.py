"""Run FlowGuard checks for AI-facing field prompt reduction."""

from __future__ import annotations

from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite
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
    exact_ok = run_exact_workflow_case(
        "correct_field_prompt_reduction",
        workflow=model.build_correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: state.done_claim == "accepted",
    )
    report = run_formal_workflow_suite(
        "field_prompt_reduction",
        (
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
    return 0 if exact_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
