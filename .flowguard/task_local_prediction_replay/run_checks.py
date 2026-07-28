"""Run task-local prediction and replay model checks."""

from __future__ import annotations

from flowguard import run_exact_sequence
from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite
import model


REQUIRED_LABELS = (
    "prediction_frozen",
    "replay_matched",
    "revision_proposed",
    "revision_accepted",
    "revision_rolled_back",
    "revision_rejected",
)


def main() -> int:
    correct = run_exact_sequence(
        workflow=model.correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=(model.EXTERNAL_INPUTS[0],),
        invariants=model.INVARIANTS,
    )
    correct_ok = correct.model_report.ok and len(correct.final_states) == 1
    print(
        "correct_task_local_prediction_replay: "
        f"{'exact model pass' if correct_ok else 'failed'}"
    )
    report = run_formal_workflow_suite(
        "task_local_prediction_replay",
        (
            FormalWorkflowCase(
                "broken_status_only",
                model.broken_status_only_workflow(),
                False,
            ),
            FormalWorkflowCase(
                "broken_expected_output",
                model.broken_expected_output_workflow(),
                False,
            ),
            FormalWorkflowCase(
                "broken_accept_without_replay",
                model.broken_accept_without_replay_workflow(),
                False,
            ),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=REQUIRED_LABELS,
        protected_error_class="prediction_replay_false_green",
    )
    return 0 if correct_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
