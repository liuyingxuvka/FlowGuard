"""Run the executable real software problem corpus review."""

from __future__ import annotations

import sys
from pathlib import Path


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.problem_corpus.executable import review_executable_corpus  # noqa: E402


def main() -> int:
    report = review_executable_corpus()
    print(report.format_text())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
