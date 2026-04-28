"""Run loop/stuck-state review examples."""

from __future__ import annotations

import sys
from pathlib import Path


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.looping_workflow.model import run_loop_review  # noqa: E402


def main() -> int:
    report = run_loop_review()
    print(report.format_text())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
