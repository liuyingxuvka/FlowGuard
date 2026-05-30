"""Run the plan-detailing compiler FlowGuard scenarios."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.plan_detailing_compiler.model import run_plan_detailing_review


def main() -> int:
    report = run_plan_detailing_review()
    print(report.format_text(max_counterexamples=1))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
