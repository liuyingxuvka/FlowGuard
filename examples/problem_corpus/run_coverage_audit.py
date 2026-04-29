"""Run the Phase 11.2 benchmark coverage audit."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.problem_corpus.coverage_audit import review_benchmark_coverage  # noqa: E402


def main() -> int:
    report = review_benchmark_coverage()
    print(report.format_text())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
