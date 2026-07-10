"""Run the AI surface streamlining self-model."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path


MODEL_PATH = Path(__file__).with_name("model.py")
spec = importlib.util.spec_from_file_location("ai_surface_streamlining_model", MODEL_PATH)
model = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = model
spec.loader.exec_module(model)


CASES = (
    ("ok", model.scenario_ok),
    ("wrapper_bloat_blocks", model.scenario_wrapper_bloat_blocks),
    ("dropping_full_schema_blocks", model.scenario_dropping_full_schema_blocks),
    ("commit_without_shadow_blocks", model.scenario_commit_without_shadow_blocks),
)


def main() -> int:
    rows = []
    ok = True
    for name, fn in CASES:
        try:
            result = fn()
        except Exception as exc:  # pragma: no cover - executable evidence output
            ok = False
            rows.append({"case": name, "ok": False, "error": repr(exc)})
        else:
            rows.append({"case": name, "ok": True, "result": repr(result)})
    payload = {"ok": ok, "cases": rows}
    output_dir = Path(os.environ.get("FLOWGUARD_OUTPUT_DIR", Path(__file__).parent))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir.joinpath("result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("=== flowguard ai surface streamlining self-model ===")
    print("status:", "OK" if ok else "FAILED")
    for row in rows:
        print(f"- {row['case']}: {'OK' if row['ok'] else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
