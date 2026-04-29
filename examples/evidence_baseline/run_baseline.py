"""Run the Phase 10.5 evidence baseline scorecard."""

from __future__ import annotations

import sys
from pathlib import Path


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.evidence_baseline.baseline import build_current_evidence_baseline  # noqa: E402


def main() -> int:
    report = build_current_evidence_baseline()
    print(report.format_text())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
