import unittest

from examples.job_matching.model import (
    BrokenScoreJob,
    Job,
    build_workflow,
    check_job_matching_model,
)


class RepeatedScoringDetectionTests(unittest.TestCase):
    def test_repeated_scoring_broken_model_fails_with_counterexample(self):
        repeated_input = Job("job_repeat", "high", "good", "high")

        report = check_job_matching_model(
            workflow=build_workflow(score_block=BrokenScoreJob()),
            external_inputs=(repeated_input,),
            max_sequence_length=2,
            required_labels=(),
        )

        self.assertFalse(report.ok)
        violation = next(
            item
            for item in report.violations
            if item.invariant_name == "no_repeated_scoring_without_refresh"
        )
        self.assertIn("repeated scoring without refresh", violation.message)
        self.assertEqual(("job_repeat", "job_repeat"), violation.state.score_attempts)

        trace_text = violation.trace.format_text()
        self.assertEqual(2, trace_text.count("BrokenScoreJob"))
        self.assertIn("RecordScoredJob", trace_text)
        self.assertIn("job_repeat", trace_text)


if __name__ == "__main__":
    unittest.main()
