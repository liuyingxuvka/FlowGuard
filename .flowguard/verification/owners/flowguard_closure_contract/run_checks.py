"""Run the thin FlowGuard closure-contract model checks."""

from __future__ import annotations

from pathlib import Path
import os
import sys

_FLOWGUARD_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOWGUARD_MODEL_ROOT = _FLOWGUARD_PROJECT_ROOT / ".flowguard" / "models" / "owners" / "flowguard_closure_contract"
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
        # The broken runner violates the invariant as soon as it consumes a
        # verified maturation result and then checks closure (two inputs).  Do
        # not multiply the three four-step example traces into an unnecessary
        # Cartesian search: the expected-bad proof needs only this minimal
        # counterexample and no completion labels.
        max_sequence_length=2,
        terminal_predicate=model.terminal_predicate,
        required_labels=(),
        protected_error_class="closure_upstream_authority_bypass",
    )
    return 0 if correct_ok and report.ok else 1

from flowguard.native_case_runner import native_main
if __name__ == "__main__":
    # Native evidence is work-in-progress output.  Keep it in a bounded,
    # invocation-local workspace so the runner never scans historical project
    # artifacts as if they were current input evidence.
    os.environ.setdefault(
        "FLOWGUARD_OUTPUT_DIR",
        str(
            _FLOWGUARD_PROJECT_ROOT
            / "work"
            / "flowguard"
            / "native-owner-tests"
            / f"flowguard-closure-contract-{os.getpid()}"
        ),
    )
    raise SystemExit(native_main("model:flowguard_closure_contract", main))
