"""Run the template harvest closure self-checks."""

from __future__ import annotations

from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite
import model


REQUIRED_LABELS = ("minimum_model_accepted", "template_harvest_closed", "model_completion_claimed")


def main() -> int:
    exact_inputs = tuple(input_obj for input_obj in model.EXTERNAL_INPUTS if input_obj.known_bad_case)
    exact_ok = run_exact_workflow_case(
        "correct_template_harvest_closure",
        workflow=model.correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=exact_inputs,
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: len(state.claimed_model_ids) == len(exact_inputs),
    )
    report = run_formal_workflow_suite(
        "template_harvest_closure",
        (
            FormalWorkflowCase("broken_without_harvest", model.broken_without_harvest_workflow(), False),
            FormalWorkflowCase("broken_vague_skip", model.broken_vague_skip_workflow(), False),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=REQUIRED_LABELS,
        protected_error_class="template_harvest_not_closed",
    )
    return 0 if exact_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
