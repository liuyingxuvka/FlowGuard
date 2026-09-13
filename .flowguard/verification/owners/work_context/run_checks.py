"""Run the provider-neutral WorkContext executable model."""

from __future__ import annotations

from pathlib import Path
import sys

_FLOWGUARD_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOWGUARD_MODEL_ROOT = _FLOWGUARD_PROJECT_ROOT / ".flowguard" / "models" / "owners" / "work_context"
for _flowguard_path in (_FLOWGUARD_PROJECT_ROOT, _FLOWGUARD_MODEL_ROOT):
    if str(_flowguard_path) not in sys.path:
        sys.path.insert(0, str(_flowguard_path))

from pathlib import Path
import sys


import json

import model


def main() -> int:
    report = model.run_model_checks()
    native_cases = [
        {
            "name": name,
            "ok": bool(report.get(key)),
            "observed_status": "ok" if bool(report.get(key)) else "violation",
            "case_kind": "good",
            "projection_priority": 60,
            "projection_source": "structured",
        }
        for name, key in (
            ("peer_adapter_selection", "peer_adapter_selection_ok"),
            ("current_context_projection", "current_context_projection_ok"),
            ("explicit_behavior_source_admission", "explicit_behavior_source_admission_ok"),
            ("multiple_distinct_contexts", "multiple_distinct_contexts_ok"),
        )
    ]
    native_cases.extend(
        {
            "name": f"known_bad:{name}",
            "ok": value == "blocked",
            "observed_status": value,
            "case_kind": "bad",
            "projection_priority": 60,
            "projection_source": "structured",
        }
        for name, value in report.get("known_bad", {}).items()
    )
    payload = dict(report)
    payload["native_cases"] = native_cases
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1

from flowguard.native_case_runner import native_main
if __name__ == "__main__":
    raise SystemExit(native_main("model:work_context", main))
