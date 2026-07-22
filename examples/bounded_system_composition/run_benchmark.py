from __future__ import annotations

from examples.bounded_system_composition.benchmark import run_bounded_system_benchmark


if __name__ == "__main__":
    report = run_bounded_system_benchmark()
    print(report.to_json_text())
    raise SystemExit(0 if report.ok else 1)

