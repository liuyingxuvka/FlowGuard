"""Run the budgeted model-group rollout model."""

from __future__ import annotations

import sys
from pathlib import Path


if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.budgeted_model_groups.model import run_budgeted_model_group_review  # noqa: E402


def main() -> int:
    report = run_budgeted_model_group_review()
    print(report.format_text(max_counterexamples=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
