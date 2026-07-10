"""Run FlowGuard checks for AI route handoff continuity."""

from __future__ import annotations

from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite

import model


REQUIRED_LABELS = (
            "summary_gap_recorded",
            "scan_action_created",
            "specialist_route_ran",
            "owner_proof_recorded",
            "claim_full",
)


def main() -> int:
    exact_ok = run_exact_workflow_case(
        "correct_ai_route_handoff",
        workflow=model.build_correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: state.final_claim == "full",
    )
    cases = [
        FormalWorkflowCase(broken.name, broken, False, required_labels=REQUIRED_LABELS)
        for broken in model.build_broken_workflows()
    ]
    report = run_formal_workflow_suite(
        "ai_route_handoffs",
        tuple(cases),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        protected_error_class="route_handoff_gap",
    )
    return 0 if exact_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
