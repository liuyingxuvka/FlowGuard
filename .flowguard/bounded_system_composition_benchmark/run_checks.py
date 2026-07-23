from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
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


if __name__ == "__main__":
    raise SystemExit(main())
