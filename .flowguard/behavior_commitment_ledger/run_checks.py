"""Run FlowGuard checks for the self behavior commitment ledger."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard import review_behavior_commitment_ledger

from model import build_flowguard_behavior_commitment_ledger


def main() -> int:
    report = review_behavior_commitment_ledger(build_flowguard_behavior_commitment_ledger())
    payload = {"ok": report.ok, "report": report.to_dict()}
    output_dir = Path(os.environ.get("FLOWGUARD_OUTPUT_DIR", Path(__file__).parent))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir.joinpath("result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(report.format_text())
    print()
    if report.ok:
        print("flowguard behavior commitment ledger checks passed")
        return 0
    print("flowguard behavior commitment ledger checks failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
