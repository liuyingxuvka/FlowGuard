"""Run job-matching conformance replay examples."""

from __future__ import annotations

import sys
from pathlib import Path


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.job_matching.conformance import (  # noqa: E402
    generate_representative_traces,
    replay_job_matching_trace,
)
from examples.job_matching.production import (  # noqa: E402
    BrokenDuplicateRecordSystem,
    BrokenRepeatedScoringSystem,
    CorrectJobMatchingSystem,
)


def run_case(title: str, system_factory, expected_ok: bool) -> bool:
    traces = generate_representative_traces()
    reports = [
        replay_job_matching_trace(trace, system_factory())
        for trace in traces
    ]
    ok = all(report.ok for report in reports)
    print(f"== {title} ==")
    print(f"representative_traces: {len(traces)}")
    print(f"status: {'OK' if ok else 'VIOLATION'}")
    for report in reports:
        if not report.ok:
            print(report.format_text(max_examples=1))
            break
    print()
    return ok is expected_ok


def main() -> int:
    cases = (
        ("correct production implementation", CorrectJobMatchingSystem, True),
        ("broken duplicate-record implementation", BrokenDuplicateRecordSystem, False),
        ("broken repeated-scoring implementation", BrokenRepeatedScoringSystem, False),
    )
    all_expected = True
    for title, factory, expected_ok in cases:
        all_expected = run_case(title, factory, expected_ok) and all_expected
    return 0 if all_expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
