"""Run the FlowGuard Skill trigger reliability self-review."""

from __future__ import annotations

import sys
from pathlib import Path


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.flowguard_skill_trigger.model import run_skill_trigger_review  # noqa: E402


def main() -> int:
    report = run_skill_trigger_review()
    print("=== flowguard Skill trigger review ===")
    print(report.format_text(max_counterexamples=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
