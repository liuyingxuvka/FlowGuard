"""Run the OpenSpec-scoped validated template-pack registry model checks."""

from __future__ import annotations

from flowguard.formal_runner import (
    FormalWorkflowCase,
    run_exact_workflow_case,
    run_formal_workflow_suite,
)

import model


REQUIRED_LABELS = (
    "manifest_validated",
    "selection_receipt_emitted",
    "instance_receipt_emitted",
    "instance_accepted",
)


def main() -> int:
    exact_ok = run_exact_workflow_case(
        "correct_template_pack_registry",
        workflow=model.workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: state.accepted_ids == model.EXPECTED_ACCEPTED_IDS,
    )
    report = run_formal_workflow_suite(
        "validated_template_pack_registry",
        (
            FormalWorkflowCase(
                "broken_manifest_gate",
                model.workflow(manifest_gate=model.BrokenManifestGate()),
                False,
            ),
            FormalWorkflowCase(
                "broken_selection_gate",
                model.workflow(selection_gate=model.BrokenSelectionGate()),
                False,
            ),
            FormalWorkflowCase(
                "broken_parameter_gate",
                model.workflow(parameter_gate=model.BrokenParameterGate()),
                False,
            ),
            FormalWorkflowCase(
                "broken_freshness_gate",
                model.workflow(freshness_gate=model.BrokenFreshnessGate()),
                False,
            ),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=REQUIRED_LABELS,
        protected_error_class="template_pack_registry_gate_bypass",
    )
    return 0 if exact_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
