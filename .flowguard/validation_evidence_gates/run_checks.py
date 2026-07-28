"""Run validation evidence gate rollout checks."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path


MODEL_PATH = Path(__file__).with_name("model.py")
spec = importlib.util.spec_from_file_location("validation_evidence_gates_model", MODEL_PATH)
model = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = model
spec.loader.exec_module(model)


CASES = (
    ("ok", model.scenario_ok, True),
    ("missing_payload_pack_blocks", model.scenario_missing_payload_pack_blocks, False),
    ("missing_clickthrough_blocks", model.scenario_missing_clickthrough_blocks, False),
    ("prose_manual_check_blocks", model.scenario_prose_manual_check_blocks, False),
    ("missing_installed_sync_blocks", model.scenario_missing_installed_sync_blocks, False),
)


def main() -> int:
    rows = []
    ok = True
    for name, fn, expected_invariant in CASES:
        try:
            result = fn()
            state = result if name == "ok" else result[0]
            invariant_ok = model.invariant_done_has_ui_payload_manual_and_sync(state)
            case_ok = invariant_ok is expected_invariant
        except Exception as exc:  # pragma: no cover - executable evidence output
            ok = False
            rows.append({"case": name, "ok": False, "error": repr(exc)})
        else:
            ok = ok and case_ok
            rows.append(
                {
                    "case": name,
                    "ok": case_ok,
                    "invariant_ok": invariant_ok,
                    "expected_invariant": expected_invariant,
                    "result": repr(result),
                }
            )
    payload = {"ok": ok, "cases": rows}
    output_dir = Path(os.environ.get("FLOWGUARD_OUTPUT_DIR", Path(__file__).parent))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir.joinpath("result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("=== flowguard validation evidence gates self-model ===")
    print("status:", "OK" if ok else "FAILED")
    for row in rows:
        print(f"- {row['case']}: {'OK' if row['ok'] else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
