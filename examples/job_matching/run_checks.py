"""Run job-matching flowguard checks."""

from __future__ import annotations

import sys
from pathlib import Path


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from examples.job_matching.model import (  # noqa: E402
    BrokenRecordScoredJob,
    BrokenScoreJob,
    build_workflow,
    check_job_matching_model,
)


def main() -> int:
    cases = (
        ("correct model", build_workflow(), True, ("decision_apply", "record_skipped")),
        ("broken duplicate record model", build_workflow(record_block=BrokenRecordScoredJob()), False, ()),
        ("broken repeated scoring model", build_workflow(score_block=BrokenScoreJob()), False, ()),
    )

    all_expected = True
    for title, workflow, expected_ok, required_labels in cases:
        report = check_job_matching_model(
            workflow=workflow,
            max_sequence_length=2,
            required_labels=required_labels,
        )
        print(f"== {title} ==")
        print(report.format_text(max_examples=2))
        print()
        all_expected = all_expected and report.ok is expected_ok

    return 0 if all_expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
