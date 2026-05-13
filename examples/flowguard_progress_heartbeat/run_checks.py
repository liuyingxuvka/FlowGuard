"""Run the Explorer progress heartbeat rollout model."""

from __future__ import annotations

from model import run_progress_heartbeat_review


def main() -> int:
    report = run_progress_heartbeat_review()
    print(report.format_text(max_counterexamples=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

