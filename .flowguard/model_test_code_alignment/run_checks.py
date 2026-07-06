"""Run the model/test/code alignment rollout review."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from model import run_rollout_review


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
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
