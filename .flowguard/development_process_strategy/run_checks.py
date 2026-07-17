"""Run the DPF-owned development-process strategy executable model."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import contract_exhaustion
import architecture_reduction
import field_lifecycle
import model


def main() -> int:
    report = model.run_model_checks()
    field_report = field_lifecycle.review_development_process_strategy_fields()
    contract_report = contract_exhaustion.review_development_process_strategy_contracts()
    alignment_report = contract_exhaustion.review_development_process_strategy_alignment()
    reduction_report = architecture_reduction.review_development_process_strategy_reduction()
    payload = {
        "ok": bool(
            report["ok"]
            and field_report.ok
            and contract_report.ok
            and alignment_report.ok
            and reduction_report.ok
        ),
        "model": report,
        "field_lifecycle": field_report.to_dict(),
        "contract_exhaustion": contract_report.to_dict(),
        "model_test_alignment": alignment_report.to_dict(),
        "architecture_reduction": reduction_report.to_dict(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
