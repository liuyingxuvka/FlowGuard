"""Run expected-vs-observed scenario review for job_matching."""

from __future__ import annotations

import sys
from pathlib import Path


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from flowguard.review import review_scenarios  # noqa: E402
from examples.job_matching.scenarios import all_job_matching_scenarios  # noqa: E402


def main() -> int:
    report = review_scenarios(all_job_matching_scenarios())
    print("=== flowguard scenario review: job_matching ===")
    print(report.format_text(max_counterexamples=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
