"""Run the model/test/code alignment rollout review."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import model


def run_native_pytest_contract() -> bool:
    """Run the exact native tests declared by the alignment model."""

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
    results = model.run_rollout_review()
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


if __name__ == "__main__":
    raise SystemExit(main())
