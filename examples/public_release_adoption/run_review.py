"""Run public release adoption expected-vs-observed review."""

from __future__ import annotations

from pathlib import Path
import sys


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from flowguard.review import review_scenarios

from examples.public_release_adoption.model import scenarios


def main() -> int:
    report = review_scenarios(scenarios())
    print("=== flowguard public release adoption review ===")
    print(report.format_text(max_counterexamples=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
