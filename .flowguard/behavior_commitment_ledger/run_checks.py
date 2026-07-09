"""Run FlowGuard checks for the self behavior commitment ledger."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard import review_behavior_commitment_ledger

from model import build_flowguard_behavior_commitment_ledger


def main() -> int:
    report = review_behavior_commitment_ledger(build_flowguard_behavior_commitment_ledger())
    print(report.format_text())
    print()
    if report.ok:
        print("flowguard behavior commitment ledger checks passed")
        return 0
    print("flowguard behavior commitment ledger checks failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
