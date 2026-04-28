import unittest

from examples.job_matching.conformance import (
    generate_representative_traces,
    has_repeated_external_input,
    replay_job_matching_trace,
)
from examples.job_matching.production import CorrectJobMatchingSystem


class ConformanceReplaySuccessTests(unittest.TestCase):
    def test_correct_production_replays_representative_trace(self):
        trace = next(
            trace
            for trace in generate_representative_traces()
            if has_repeated_external_input(trace)
        )

        report = replay_job_matching_trace(trace, CorrectJobMatchingSystem())

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(len(trace.steps), len(report.replayed_steps))
        self.assertIsNone(report.failed_step_index)


if __name__ == "__main__":
    unittest.main()
