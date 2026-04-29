"""Run FlowGuard's helper-runner self-review model."""

from __future__ import annotations

import sys
from pathlib import Path


if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.flowguard_runner_self_review.model import (  # noqa: E402
    run_runner_self_check_summary,
    run_runner_self_review,
)


def main() -> int:
    review = run_runner_self_review()
    summary = run_runner_self_check_summary()

    print("=== flowguard runner self-review ===")
    print(review.format_text(max_counterexamples=2))
    print()
    print("=== flowguard runner self-check summary ===")
    print(summary.format_text(verbose=True))

    if not review.ok:
        return 1
    if summary.overall_status not in {"pass", "pass_with_gaps"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
