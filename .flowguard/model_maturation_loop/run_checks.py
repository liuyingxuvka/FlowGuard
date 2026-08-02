"""Run formal checks for maturation receipt verification and admission."""

from __future__ import annotations

from flowguard import run_exact_sequence
from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite
import model


def main() -> int:
    correct = run_exact_sequence(
        workflow=model.correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=(model.CLOSED_REQUEST,),
        invariants=model.INVARIANTS,
    )
    correct_ok = correct.model_report.ok and len(correct.final_states) == 1
    print(f"correct_model_maturation_loop: {'exact model pass' if correct_ok else 'failed'}")
    report = run_formal_workflow_suite(
        "model_maturation_loop",
        (FormalWorkflowCase("broken_permission_upgrades_blocked_maturation", model.broken_permission_upgrade_workflow(), False),),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=(
            "maturation_closed",
            "maturation_receipt_published",
            "maturation_receipt_verified",
            "implementation_ready",
            "risk_confidence_full",
            "closure_integrity_closed",
        ),
        protected_error_class="model_maturation_authority_bypass",
    )
    return 0 if correct_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
