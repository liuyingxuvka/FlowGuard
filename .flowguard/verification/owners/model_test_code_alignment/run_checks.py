"""Run the model/test/code alignment rollout review."""

from __future__ import annotations

from pathlib import Path
import sys

_FLOWGUARD_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOWGUARD_MODEL_ROOT = _FLOWGUARD_PROJECT_ROOT / ".flowguard" / "models" / "owners" / "model_test_code_alignment"
for _flowguard_path in (_FLOWGUARD_PROJECT_ROOT, _FLOWGUARD_MODEL_ROOT):
    if str(_flowguard_path) not in sys.path:
        sys.path.insert(0, str(_flowguard_path))


import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

import model
from flowguard.validation_ownership import nested_owner_launch_allowed

# Import the producer into this module's namespace so native_main can wrap the
# one authoritative rollout call.  Calling ``model.run_rollout_review`` would
# leave the typed tuple outside the explicit capture allow-list and force the
# bridge to fall back to display text, losing the model's violation status.
from model import run_rollout_review


def run_native_pytest_contract() -> bool:
    """Run the exact native tests declared by the alignment model."""

    if not nested_owner_launch_allowed(
        "model_test_code_alignment", "model_test_code_alignment:native_pytest"
    ):
        print(
            "native alignment tests: REUSED_CURRENT "
            "(outer validation plan owns the declared pytest producer; no relaunch)"
        )
        return True

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *model.NATIVE_PYTEST_SELECTORS,
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=ROOT,
        check=False,
    )
    return completed.returncode == 0


def main() -> int:
    results = run_rollout_review()
    print("=== flowguard model/test/code alignment rollout ===")
    failed = []
    for name, ok, codes in results:
        status = "PASS" if ok else "FAIL"
        print(f"{name}: {status} codes={list(codes)}")
        if not ok:
            failed.append(name)
    print(f"cases: {len(results)}")
    print(f"failed: {len(failed)}")
    obligation_bindings_ok = model.native_test_obligation_bindings_are_executed()
    print(
        "native obligation bindings: "
        f"{'PASS' if obligation_bindings_ok else 'FAIL'} "
        f"obligations={len(model.NATIVE_TEST_OBLIGATION_BINDINGS)}"
    )
    pytest_ok = run_native_pytest_contract()
    print(
        "native alignment tests: "
        f"{'PASS' if pytest_ok else 'FAIL'} "
        f"selectors={len(model.NATIVE_PYTEST_SELECTORS)}"
    )
    return 0 if not failed and obligation_bindings_ok and pytest_ok else 1

from flowguard.native_case_runner import native_main
if __name__ == "__main__":
    raise SystemExit(native_main("model:model_test_code_alignment", main))
