"""Run the template harvest closure self-checks."""

from __future__ import annotations

from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite
import model


REQUIRED_LABELS = ("minimum_model_accepted", "template_harvest_closed", "model_completion_claimed")


def main() -> int:
    report = run_formal_workflow_suite(
        "template_harvest_closure",
        (
            FormalWorkflowCase("correct_template_harvest_closure", model.correct_workflow(), True),
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
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
