"""Run task-local prediction and replay model checks."""

from __future__ import annotations

from pathlib import Path
import sys

_FLOWGUARD_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOWGUARD_MODEL_ROOT = _FLOWGUARD_PROJECT_ROOT / ".flowguard" / "models" / "owners" / "task_local_prediction_replay"
for _flowguard_path in (_FLOWGUARD_PROJECT_ROOT, _FLOWGUARD_MODEL_ROOT):
    if str(_flowguard_path) not in sys.path:
        sys.path.insert(0, str(_flowguard_path))

from pathlib import Path
import sys


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
            FormalWorkflowCase(
                "broken_rejection_base_model_loss",
                model.broken_rejection_base_model_loss_workflow(),
                False,
                external_inputs=(model.EXTERNAL_INPUTS[3],),
                max_sequence_length=1,
            ),
            FormalWorkflowCase(
                "broken_rollback_base_model_loss",
                model.broken_rollback_base_model_loss_workflow(),
                False,
                external_inputs=(model.EXTERNAL_INPUTS[0],),
                max_sequence_length=1,
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

from flowguard.native_case_runner import native_main
if __name__ == "__main__":
    raise SystemExit(native_main("model:task_local_prediction_replay", main))
