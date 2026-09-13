"""Run the DPF-owned development-process strategy executable model."""

from __future__ import annotations

from pathlib import Path
import sys

_FLOWGUARD_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOWGUARD_MODEL_ROOT = _FLOWGUARD_PROJECT_ROOT / ".flowguard" / "models" / "owners" / "development_process_strategy"
for _flowguard_path in (_FLOWGUARD_PROJECT_ROOT, _FLOWGUARD_MODEL_ROOT):
    if str(_flowguard_path) not in sys.path:
        sys.path.insert(0, str(_flowguard_path))


import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
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
    finding_set = {str(item) for item in report.get("findings", ())}
    native_cases = [
        {
            "name": "ordinary_path_lightweight",
            "ok": "ordinary_path_not_lightweight" not in finding_set,
            "observed_status": "ok",
            "case_kind": "good",
            "projection_priority": 60,
            "projection_source": "structured",
        }
    ]
    for case_id in (
        "targeted_sequential",
        "declared_complete_parallel",
        "budgeted_sequential",
        "freeze_first_measured",
    ):
        native_cases.append(
            {
                "name": case_id,
                "ok": f"valid_{case_id}_not_selected" not in finding_set
                and f"valid_{case_id}_violates_invariant" not in finding_set,
                "observed_status": "ok",
                "case_kind": "good",
                "projection_priority": 60,
                "projection_source": "structured",
            }
        )
    native_cases.extend(
        {
            "name": name,
            "ok": bool(subreport.ok),
            "observed_status": "ok",
            "case_kind": "good",
            "projection_priority": 60,
            "projection_source": "structured",
        }
        for name, subreport in (
            ("field_lifecycle", field_report),
            ("contract_exhaustion", contract_report),
            ("model_test_alignment", alignment_report),
            ("architecture_reduction", reduction_report),
        )
    )
    for name, value in report.get("known_bad", {}).items():
        native_cases.append(
            {
                "name": str(name),
                "ok": bool(value.get("blocked")),
                "observed_status": "ok",
                "case_kind": "bad",
                "projection_priority": 60,
                "projection_source": "structured",
            }
        )
    native_cases.append(
        {
            "name": "broken_selector",
            "ok": "broken_selector_not_caught" not in finding_set,
            "observed_status": "ok",
            "case_kind": "bad",
            "projection_priority": 60,
            "projection_source": "structured",
        }
    )
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
        # The composite report remains intact for human diagnosis.  These
        # exact rows are the already-computed assertions that the finite
        # native mapping consumes; they do not rerun any model or infer a
        # leaf from a summary count.
        "native_cases": native_cases,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1

from flowguard.native_case_runner import native_main
if __name__ == "__main__":
    raise SystemExit(native_main("model:development_process_strategy", main))
