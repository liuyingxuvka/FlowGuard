"""Run the thin FlowGuard closure-contract model checks."""

from __future__ import annotations

from flowguard import run_exact_sequence
from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite
import model


def main() -> int:
    correct = run_exact_sequence(
        workflow=model.build_correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=model.GOOD_SEQUENCE,
        invariants=model.INVARIANTS,
    )
    correct_ok = correct.model_report.ok and len(correct.final_states) == 1
    print(f"thin_closure_contract: {'exact model pass' if correct_ok else 'failed'}")
    report = run_formal_workflow_suite(
        "thin_closure_contract",
        (
            FormalWorkflowCase(
                "closure_rescores_blocked_risk",
                model.build_broken_workflow(),
                False,
            ),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=(
            "maturation_consumed",
            "admission_consumed",
            "risk_consumed",
            "closure_accepted",
        ),
        protected_error_class="closure_upstream_authority_bypass",
    )
    return 0 if correct_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
