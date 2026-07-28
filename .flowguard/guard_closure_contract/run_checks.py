"""Run the Guard closure contract FlowGuard checks."""

from __future__ import annotations

from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite
import model


REQUIRED_LABELS = (
    "clean_closure_report",
    "done_claim_allowed",
    "obligation_stale_evidence",
    "obligation_non_pass",
)


def main() -> int:
    exact_ok = run_exact_workflow_case(
        "guard_closure_contract",
        workflow=model.build_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=(model.EXTERNAL_INPUTS[0],),
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: state.done_claims == ("clean",),
    )
    report = run_formal_workflow_suite(
        "guard_closure_contract",
        (
            FormalWorkflowCase(
                "guard_closure_non_pass_is_obligation",
                model.build_workflow(),
                False,
                external_inputs=(model.EXTERNAL_INPUTS[1],),
                max_sequence_length=1,
                required_labels=("done_claim_allowed",),
                known_bad_labels=("obligation_non_pass",),
            ),
            FormalWorkflowCase(
                "guard_closure_stale_is_obligation",
                model.build_workflow(),
                False,
                external_inputs=(model.EXTERNAL_INPUTS[2],),
                max_sequence_length=1,
                required_labels=("done_claim_allowed",),
                known_bad_labels=("obligation_stale_evidence",),
            ),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=REQUIRED_LABELS,
        protected_error_class="unclean_guard_closure_claim",
    )
    return 0 if exact_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
