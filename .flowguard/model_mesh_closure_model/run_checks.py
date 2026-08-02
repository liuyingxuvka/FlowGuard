"""Run the whole-system understanding ModelMesh closure checks."""

from __future__ import annotations

import sys
from pathlib import Path

from flowguard import Workflow
from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite

sys.path.insert(0, str(Path(__file__).resolve().parent))
import model  # noqa: E402


def _case(name: str, input_value: model.ClosureInput) -> FormalWorkflowCase:
    return FormalWorkflowCase(
        name,
        Workflow(model.build_blocks(), name=name),
        False,
        external_inputs=(input_value,),
        max_sequence_length=1,
    )


def main() -> int:
    exact_ok = run_exact_workflow_case(
        "correct_whole_system_understanding_closure",
        workflow=Workflow(model.build_blocks()),
        initial_state=model.initial_state(),
        external_input_sequence=model.external_inputs(),
        invariants=model.invariants,
        final_state_predicate=lambda state: (
            state.terminal and state.normal_exit and not state.pending
        ),
    )
    report = run_formal_workflow_suite(
        "model_mesh_closure_model",
        (
            FormalWorkflowCase(
                "broken_missing_semantic_join",
                Workflow(
                    (
                        model.StartUnderstanding(),
                        model.CompileOwnerDemand(),
                        model.VerifyMaturation(),
                        model.DecideImplementationAdmission(),
                        model.DecideRisk(),
                        model.FinishUnderstanding(),
                    ),
                    name="missing_semantic_join",
                ),
                False,
                required_labels=("understanding_closed",),
            ),
            _case(
                "broken_inventory_only_without_relations",
                model.ClosureInput("root_start", semantic_relation_fingerprint=""),
            ),
            _case(
                "broken_five_model_slice",
                model.ClosureInput(
                    "root_start",
                    semantic_derivation_fingerprint="sha256:five-model-slice",
                ),
            ),
            _case(
                "broken_empty_semantic_fingerprint",
                model.ClosureInput("root_start", semantic_mesh_fingerprint=""),
            ),
            _case(
                "broken_unverified_semantic_artifact",
                model.ClosureInput("root_start", evidence_status="not_run"),
            ),
            _case(
                "broken_semantic_gap_hidden",
                model.ClosureInput("root_start", semantic_gap_ids=("model:unmapped",)),
            ),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.external_inputs(),
        invariants=model.invariants,
        max_sequence_length=1,
        terminal_predicate=model.terminal_predicate,
        protected_error_class="whole_system_understanding_closure_incomplete",
    )
    return 0 if exact_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
