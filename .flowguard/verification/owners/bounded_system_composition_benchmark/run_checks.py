from __future__ import annotations

from pathlib import Path
import sys

_FLOWGUARD_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOWGUARD_MODEL_ROOT = _FLOWGUARD_PROJECT_ROOT / ".flowguard" / "models" / "owners" / "bounded_system_composition_benchmark"
for _flowguard_path in (_FLOWGUARD_PROJECT_ROOT, _FLOWGUARD_MODEL_ROOT):
    if str(_flowguard_path) not in sys.path:
        sys.path.insert(0, str(_flowguard_path))


import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.bounded_system_composition.benchmark import run_bounded_system_benchmark


def main() -> int:
    report = run_bounded_system_benchmark()
    output_dir = os.environ.get("FLOWGUARD_OUTPUT_DIR", "")
    if output_dir:
        target = Path(output_dir) / "benchmark-report.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(report.to_json_text() + "\n", encoding="utf-8")
    print(report.format_text())
    return 0 if report.ok else 1

from flowguard.native_case_runner import native_main
if __name__ == "__main__":
    raise SystemExit(native_main("model:bounded_system_composition_benchmark", main))
