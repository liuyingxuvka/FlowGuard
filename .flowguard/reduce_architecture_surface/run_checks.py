"""Run FlowGuard checks for the public facade architecture reduction."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    reports = run_checks()
    labels = (
        "architecture reduction",
        "structure mesh",
        "development process flow",
        "test mesh",
    )
    for label, report in zip(labels, reports):
        print(f"=== {label} ===")
        print(report.format_text())
        print()
    return 0 if all(report.ok for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
