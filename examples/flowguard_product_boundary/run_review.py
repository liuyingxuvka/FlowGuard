"""Run the FlowGuard product-boundary self-review."""

from __future__ import annotations

import sys
from pathlib import Path


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.flowguard_product_boundary.model import run_product_boundary_review  # noqa: E402


def main() -> int:
    report = run_product_boundary_review()
    print("=== flowguard product-boundary review ===")
    print(report.format_text(max_counterexamples=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
