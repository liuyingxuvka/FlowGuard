"""Run FlowGuard checks for AI route handoff continuity."""

from __future__ import annotations

from flowguard import Explorer

import model


def run_workflow(name: str, workflow, *, expect_ok: bool) -> bool:
    report = Explorer(
        workflow=workflow,
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=(
            "summary_gap_recorded",
            "scan_action_created",
            "specialist_route_ran",
            "owner_proof_recorded",
            "claim_full",
        ),
    ).explore()
    ok = report.ok
    print(f"{name}: {'OK' if ok else 'VIOLATION'}")
    print(report.format_text(max_examples=1))
    print()
    return ok is expect_ok


def main() -> int:
    checks = [run_workflow("correct_ai_route_handoff", model.build_correct_workflow(), expect_ok=True)]
    for broken in model.build_broken_workflows():
        checks.append(run_workflow(broken.name, broken, expect_ok=False))
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
