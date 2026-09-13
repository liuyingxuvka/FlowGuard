"""Run formal checks for maturation receipt verification and admission."""

from __future__ import annotations

from pathlib import Path
import sys

_FLOWGUARD_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOWGUARD_MODEL_ROOT = _FLOWGUARD_PROJECT_ROOT / ".flowguard" / "models" / "owners" / "model_maturation_loop"
for _flowguard_path in (_FLOWGUARD_PROJECT_ROOT, _FLOWGUARD_MODEL_ROOT):
    if str(_flowguard_path) not in sys.path:
        sys.path.insert(0, str(_flowguard_path))

from pathlib import Path
import sys


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
        (
            FormalWorkflowCase("broken_permission_upgrades_blocked_maturation", model.broken_permission_upgrade_workflow(), False),
            FormalWorkflowCase("broken_path_quality_bypasses_maturation", model.broken_path_quality_bypass_workflow(), False),
        ),
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

from flowguard.native_case_runner import native_main
if __name__ == "__main__":
    raise SystemExit(native_main("model:model_maturation_loop", main))
