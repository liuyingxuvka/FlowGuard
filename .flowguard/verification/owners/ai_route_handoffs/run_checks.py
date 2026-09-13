"""Run FlowGuard checks for AI route handoff continuity."""

from __future__ import annotations

from pathlib import Path
import sys

_FLOWGUARD_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOWGUARD_MODEL_ROOT = _FLOWGUARD_PROJECT_ROOT / ".flowguard" / "models" / "owners" / "ai_route_handoffs"
for _flowguard_path in (_FLOWGUARD_PROJECT_ROOT, _FLOWGUARD_MODEL_ROOT):
    if str(_flowguard_path) not in sys.path:
        sys.path.insert(0, str(_flowguard_path))

from pathlib import Path
import sys


from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite

import model


REQUIRED_LABELS = (
            "summary_gap_recorded",
            "owner_action_bound",
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

from flowguard.native_case_runner import native_main
if __name__ == "__main__":
    raise SystemExit(native_main("model:ai_route_handoffs", main))
