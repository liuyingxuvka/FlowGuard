"""Run FlowGuard checks for AI route handoff continuity."""

from __future__ import annotations

from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite

import model


REQUIRED_LABELS = (
            "summary_gap_recorded",
            "scan_action_created",
            "specialist_route_ran",
            "owner_proof_recorded",
            "claim_full",
)


def main() -> int:
    cases = [FormalWorkflowCase("correct_ai_route_handoff", model.build_correct_workflow(), True, required_labels=REQUIRED_LABELS)]
    for broken in model.build_broken_workflows():
        cases.append(FormalWorkflowCase(broken.name, broken, False, required_labels=REQUIRED_LABELS))
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
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
