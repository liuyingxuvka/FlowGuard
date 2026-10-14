"""Run the model/test/code alignment rollout review."""

from __future__ import annotations

from pathlib import Path
import sys

_FLOWGUARD_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOWGUARD_MODEL_ROOT = _FLOWGUARD_PROJECT_ROOT / ".flowguard" / "models" / "owners" / "model_test_code_alignment"
for _flowguard_path in (_FLOWGUARD_PROJECT_ROOT, _FLOWGUARD_MODEL_ROOT):
    if str(_flowguard_path) not in sys.path:
        sys.path.insert(0, str(_flowguard_path))

import model

# Import the producer into this module's namespace so native_main can wrap the
# one authoritative rollout call.  Calling ``model.run_rollout_review`` would
# leave the typed tuple outside the explicit capture allow-list and force the
# bridge to fall back to display text, losing the model's violation status.
from model import run_rollout_review


def main() -> int:
    results = run_rollout_review()
    print("=== flowguard model/test/code alignment declaration rules ===")
    failed = []
    for name, ok, codes in results:
        status = "PASS" if ok else "FAIL"
        print(f"{name}: {status} codes={list(codes)}")
        if not ok:
            failed.append(name)
    print(f"cases: {len(results)}")
    print(f"failed: {len(failed)}")
    obligation_bindings_ok = model.native_test_obligation_bindings_are_consistent()
    print(
        "native obligation declaration consistency: "
        f"{'PASS' if obligation_bindings_ok else 'FAIL'} "
        f"obligations={len(model.NATIVE_TEST_OBLIGATION_BINDINGS)}"
    )
    print("native execution evidence: NOT PROVIDED (run outer pytest and bind its exact results)")
    return 0 if not failed and obligation_bindings_ok else 1

from flowguard.map.runner import run_owner
if __name__ == "__main__":
    raise SystemExit(run_owner(main))
