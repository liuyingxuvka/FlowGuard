"""Run the ModelMesh closure self-model checks."""

from __future__ import annotations

import sys
from pathlib import Path

from flowguard import Workflow
from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite

sys.path.insert(0, str(Path(__file__).resolve().parent))
import model  # noqa: E402


def main() -> int:
    exact_ok = run_exact_workflow_case(
        "correct_model_mesh_closure",
        workflow=Workflow(model.build_blocks()),
        initial_state=model.initial_state(),
        external_input_sequence=model.external_inputs(),
        invariants=model.invariants,
        final_state_predicate=lambda state: state.terminal and state.normal_exit,
    )
    report = run_formal_workflow_suite(
        "model_mesh_closure_model",
        (
            FormalWorkflowCase(
                "broken_missing_join",
                Workflow((model.StartRoot(), model.ChildPayment(), model.FinishOrder()), name="missing_join"),
                False,
                required_labels=("normal_exit",),
            ),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.external_inputs(),
        invariants=model.invariants,
        max_sequence_length=1,
        terminal_predicate=model.terminal_predicate,
        protected_error_class="model_mesh_missing_join",
    )
    return 0 if exact_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
