"""Run the risk evidence ledger rollout model."""

from __future__ import annotations

from flowguard import Explorer

try:
    from examples.risk_evidence_ledger.model import (
        BrokenAllowAllRiskLedgerGate,
        build_workflow,
        initial_state,
        invariants,
        ledger_cases,
    )
except ModuleNotFoundError:
    from model import (  # type: ignore[no-redef]
        BrokenAllowAllRiskLedgerGate,
        build_workflow,
        initial_state,
        invariants,
        ledger_cases,
    )


def run_rollout_checks():
    correct = Explorer(
        workflow=build_workflow(),
        initial_states=(initial_state(),),
        external_inputs=ledger_cases(),
        invariants=invariants(),
        max_sequence_length=1,
        required_labels=("claim_allowed", "claim_blocked"),
    ).explore()
    broken = Explorer(
        workflow=build_workflow(gate=BrokenAllowAllRiskLedgerGate()),
        initial_states=(initial_state(),),
        external_inputs=ledger_cases(),
        invariants=invariants(),
        max_sequence_length=1,
    ).explore()
    return correct, broken


def main() -> int:
    correct, broken = run_rollout_checks()
    print("=== risk evidence ledger rollout ===")
    print(correct.format_text(max_examples=1))
    print()
    print("=== expected broken gate violation ===")
    print(broken.format_text(max_examples=1))
    return 0 if correct.ok and not broken.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
