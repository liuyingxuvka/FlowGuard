"""Run FlowGuard checks for default replacement and field lifecycle closure."""

from __future__ import annotations

from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite

import model


REQUIRED_LABELS = (
            "fields_accounted",
            "field_projection_and_disposition_done",
            "model_code_test_and_bug_repair_done",
            "freshness_and_closure_current",
            "claim_full",
)


def main() -> int:
    cases = [
        FormalWorkflowCase("correct_default_replacement_field_lifecycle", model.build_correct_workflow(), True, required_labels=REQUIRED_LABELS)
    ]
    for workflow in model.build_broken_workflows():
        cases.append(FormalWorkflowCase(workflow.name, workflow, False, required_labels=REQUIRED_LABELS))
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
    if report.ok:
        print("default replacement field lifecycle model checks passed")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
