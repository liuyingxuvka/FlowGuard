"""Run FlowGuard checks for the self behavior commitment ledger."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard import review_behavior_commitment_ledger

from model import build_flowguard_behavior_commitment_ledger


def main() -> int:
    ledger = build_flowguard_behavior_commitment_ledger()
    report = review_behavior_commitment_ledger(ledger)
    payload = {"ok": report.ok, "report": report.to_dict()}
    output_dir = Path(os.environ.get("FLOWGUARD_OUTPUT_DIR", Path(__file__).parent))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir.joinpath("result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(report.format_text())
    print()
    duplicate_commitment = replace(
        ledger.commitments[0],
        commitment_id="commitment:duplicate-exact-intent",
        source_surface_ids=ledger.commitments[0].source_surface_ids,
    )
    duplicate_report = review_behavior_commitment_ledger(
        replace(
            ledger,
            commitments=ledger.commitments + (duplicate_commitment,),
            expected_commitment_ids=ledger.expected_commitment_ids + (duplicate_commitment.commitment_id,),
        )
    )
    duplicate_codes = {finding.code for finding in duplicate_report.findings}
    duplicate_ok = "duplicate_exact_intent_commitment" in duplicate_codes

    delegate_commitment = replace(
        ledger.commitments[0],
        commitment_id="commitment:delegate-only",
        business_intent_id="intent:delegate-only",
        surface_delegation_only=True,
    )
    delegate_report = review_behavior_commitment_ledger(
        replace(
            ledger,
            commitments=ledger.commitments + (delegate_commitment,),
            expected_commitment_ids=ledger.expected_commitment_ids + (delegate_commitment.commitment_id,),
            expected_business_intent_ids=ledger.expected_business_intent_ids + (delegate_commitment.business_intent_id,),
        )
    )
    delegate_codes = {finding.code for finding in delegate_report.findings}
    delegate_ok = "delegate_commitment_forbidden" in delegate_codes

    if report.ok and duplicate_ok and delegate_ok:
        print("flowguard behavior commitment ledger checks passed")
        return 0
    print("flowguard behavior commitment ledger checks failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
