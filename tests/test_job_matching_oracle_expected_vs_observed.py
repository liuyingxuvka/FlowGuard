import unittest

from flowguard.review import review_scenarios
from examples.job_matching.scenarios import all_job_matching_scenarios


class JobMatchingOracleExpectedObservedTests(unittest.TestCase):
    def test_expected_vs_observed_statuses_are_structured(self):
        report = review_scenarios(all_job_matching_scenarios())
        by_name = {result.scenario_name: result for result in report.results}

        duplicate = by_name["B01_broken_duplicate_record_repeated_high"]
        self.assertEqual("expected_violation_observed", duplicate.status)
        self.assertIn("no_duplicate_application_records", duplicate.observed_summary)
        self.assertIsNotNone(duplicate.counterexample_trace)

        repeated = by_name["B03_broken_repeated_scoring_high_twice"]
        self.assertEqual("expected_violation_observed", repeated.status)
        self.assertIn("no_repeated_scoring_without_refresh", repeated.observed_summary)

        conflict = by_name["S13_same_job_id_conflicting_features"]
        self.assertEqual("needs_human_review", conflict.status)
        self.assertTrue(
            any("conflicting identity" in evidence for evidence in conflict.evidence)
        )

    def test_report_json_keeps_expected_and_observed_side_by_side(self):
        report = review_scenarios(all_job_matching_scenarios())
        exported = report.to_dict()
        first = exported["results"][0]

        self.assertIn("expected_summary", first)
        self.assertIn("observed_summary", first)
        self.assertIn("status", first)


if __name__ == "__main__":
    unittest.main()
