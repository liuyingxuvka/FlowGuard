"""Run the README positioning maintenance FlowGuard checks."""

from __future__ import annotations

from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite
import model


REQUIRED_LABELS = (
    "facts_checked",
    "logic_model_ready",
    "pain_first_written",
    "validation_passed",
    "done_accepted",
)


def main() -> int:
    exact_ok = run_exact_workflow_case(
        "correct_readme_positioning",
        workflow=model.build_correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: state.done_claim == "accepted",
    )
    report = run_formal_workflow_suite(
        "readme_positioning_20260602",
        (
            FormalWorkflowCase("broken_readme_positioning", model.build_broken_workflow(), False),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=REQUIRED_LABELS,
        protected_error_class="readme_positioning_without_validation",
    )
    return 0 if exact_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
