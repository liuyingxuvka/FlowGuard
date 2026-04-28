import unittest

from examples.job_matching.model import (
    BrokenRecordScoredJob,
    Job,
    build_workflow,
    check_job_matching_model,
)


class DuplicateRecordDetectionTests(unittest.TestCase):
    def test_duplicate_record_broken_model_fails_with_counterexample(self):
        repeated_input = Job("job_dup", "high", "good", "high")

        report = check_job_matching_model(
            workflow=build_workflow(record_block=BrokenRecordScoredJob()),
            external_inputs=(repeated_input,),
            max_sequence_length=2,
            required_labels=(),
        )

        self.assertFalse(report.ok)
        violation = next(
            item
            for item in report.violations
            if item.invariant_name == "no_duplicate_application_records"
        )
        self.assertIn("duplicate application_records", violation.message)
        self.assertEqual(("job_dup", "job_dup"), violation.state.application_records)

        trace_text = violation.trace.format_text()
        self.assertIn("ScoreJob", trace_text)
        self.assertEqual(2, trace_text.count("BrokenRecordScoredJob"))
        self.assertIn("job_dup", trace_text)

    def test_duplicate_record_report_is_readable(self):
        repeated_input = Job("job_dup", "high", "good", "high")

        report = check_job_matching_model(
            workflow=build_workflow(record_block=BrokenRecordScoredJob()),
            external_inputs=(repeated_input,),
            max_sequence_length=2,
            required_labels=(),
        )

        rendered = report.format_text()
        self.assertIn("status: VIOLATION", rendered)
        self.assertIn("counterexample:", rendered)
        self.assertIn("no_duplicate_application_records", rendered)


if __name__ == "__main__":
    unittest.main()
