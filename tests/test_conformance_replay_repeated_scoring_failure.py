import unittest

from examples.job_matching.conformance import (
    generate_representative_traces,
    has_repeated_external_input,
    replay_job_matching_trace,
)
from examples.job_matching.production import BrokenRepeatedScoringSystem


class ConformanceReplayRepeatedScoringFailureTests(unittest.TestCase):
    def test_broken_repeated_scoring_system_fails_replay(self):
        trace = next(
            trace
            for trace in generate_representative_traces()
            if has_repeated_external_input(trace)
        )

        report = replay_job_matching_trace(trace, BrokenRepeatedScoringSystem())

        self.assertFalse(report.ok)
        self.assertIsNotNone(report.failed_step_index)
        self.assertIsNotNone(report.expected_trace)
        message = report.violations[0].message
        self.assertTrue("repeated scoring" in message or "score_attempts" in message)
        self.assertIn("ScoreJob", report.expected_trace.format_text())


if __name__ == "__main__":
    unittest.main()
