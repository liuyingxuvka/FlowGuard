"""Run local prompt-behavior checks for user-facing model visibility."""

from __future__ import annotations

from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite

import model


def main() -> int:
    exact_inputs = (
        model.TASKS["tiny"],
        model.TASKS["ui"],
        model.TASKS["miss"],
        model.TASKS["release"],
        model.TASKS["suppressed"],
    )
    exact_ok = run_exact_workflow_case(
        "correct_visibility_prompt",
        workflow=model.workflow(),
        initial_state=model.State(),
        external_input_sequence=exact_inputs,
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: len(state.evidence) == len(exact_inputs),
    )
    report = run_formal_workflow_suite(
        "model_visibility",
        (
            FormalWorkflowCase(
                "broken_optional_only_prompt",
                model.workflow(decider=model.BrokenOptionalOnly()),
                False,
                external_inputs=(model.TASKS["ui"],),
                max_sequence_length=1,
            ),
            FormalWorkflowCase(
                "broken_diagram_as_validation_prompt",
                model.workflow(shower=model.BrokenDiagramAsValidation()),
                False,
                external_inputs=(model.TASKS["ui"],),
                max_sequence_length=1,
            ),
            FormalWorkflowCase(
                "broken_no_update_on_change_prompt",
                model.workflow(shower=model.BrokenNoUpdateOnChange()),
                False,
                external_inputs=(model.TASKS["miss"],),
                max_sequence_length=1,
            ),
            FormalWorkflowCase(
                "broken_no_current_situation_prompt",
                model.workflow(shower=model.BrokenNoCurrentSituation()),
                False,
                external_inputs=(model.TASKS["ui"],),
                max_sequence_length=1,
            ),
            FormalWorkflowCase(
                "broken_tiny_forced_prompt",
                model.workflow(decider=model.BrokenForceTinyDiagram()),
                False,
                external_inputs=(model.TASKS["tiny"],),
                max_sequence_length=1,
            ),
        ),
        initial_states=(model.State(),),
        external_inputs=(model.TASKS["tiny"],),
        invariants=model.INVARIANTS,
        max_sequence_length=1,
        protected_error_class="model_visibility_prompt_gap",
    )
    return 0 if exact_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
