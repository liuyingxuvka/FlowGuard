"""Run FlowGuard checks for default replacement and field lifecycle closure."""

from __future__ import annotations

from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite

import model


REQUIRED_LABELS = (
            "fields_accounted",
            "field_projection_and_disposition_done",
            "model_code_test_and_bug_repair_done",
            "freshness_and_closure_current",
            "claim_full",
)


def main() -> int:
    exact_ok = run_exact_workflow_case(
        "correct_default_replacement_field_lifecycle",
        workflow=model.build_correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: state.final_claim == "full",
    )
    cases = [
        FormalWorkflowCase(workflow.name, workflow, False, required_labels=REQUIRED_LABELS)
        for workflow in model.build_broken_workflows()
    ]
    report = run_formal_workflow_suite(
        "default_replacement_field_lifecycle",
        tuple(cases),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        protected_error_class="old_field_disposition_gap",
    )
    if exact_ok and report.ok:
        print("default replacement field lifecycle model checks passed")
    return 0 if exact_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
