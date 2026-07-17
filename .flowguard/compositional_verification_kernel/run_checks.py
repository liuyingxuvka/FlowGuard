"""Run the portable compositional verification kernel model checks."""

from __future__ import annotations

from flowguard import run_exact_sequence
from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite

import model


REQUIRED_LABELS = (
    "validated",
    "semantics_checked",
    "refinement_checked",
    "composition_checked",
    "accepted",
)


def main() -> int:
    correct = run_exact_sequence(
        workflow=model.workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=(model.EXTERNAL_INPUTS[0],),
        invariants=model.INVARIANTS,
    )
    correct_ok = correct.model_report.ok
    print(f"correct_portable_kernel: {'exact model pass' if correct_ok else 'failed'}")
    report = run_formal_workflow_suite(
        "compositional_verification_kernel",
        (
            FormalWorkflowCase(
                "broken_schema_gate",
                model.workflow(schema_gate=model.BrokenSchemaGate()),
                False,
            ),
            FormalWorkflowCase(
                "broken_temporal_gate",
                model.workflow(semantics_gate=model.BrokenTemporalGate()),
                False,
            ),
            FormalWorkflowCase(
                "broken_refinement_gate",
                model.workflow(refinement_gate=model.BrokenRefinementGate()),
                False,
            ),
            FormalWorkflowCase(
                "broken_composition_gate",
                model.workflow(composition_gate=model.BrokenCompositionGate()),
                False,
            ),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=REQUIRED_LABELS,
        protected_error_class="portable_verification_missing_gate",
    )
    return 0 if correct_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
