"""Run the Runtime Path Evidence rollout model checks."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite
import model


def main() -> int:
    exact_ok = run_exact_workflow_case(
        "correct_runtime_path_evidence_flow",
        workflow=model.build_workflow(broken=False),
        initial_state=model.initial_state(),
        external_input_sequence=model.GOOD_EVENTS,
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: state.closure_full,
    )
    report = run_formal_workflow_suite(
        "runtime_path_evidence",
        (
            FormalWorkflowCase(
                "broken_runtime_path_evidence_flow",
                model.build_workflow(broken=True),
                False,
                external_inputs=model.EVENTS,
                max_sequence_length=3,
            ),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.GOOD_EVENTS,
        invariants=model.INVARIANTS,
        max_sequence_length=6,
        protected_error_class="runtime_path_evidence_missing",
    )
    return 0 if exact_ok and report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
