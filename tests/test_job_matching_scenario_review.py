import subprocess
import sys
import unittest

from flowguard.review import review_scenarios
from examples.job_matching.scenarios import all_job_matching_scenarios


class JobMatchingScenarioReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = review_scenarios(all_job_matching_scenarios())
        cls.statuses = {result.scenario_name: result.status for result in cls.report.results}

    def test_catalog_review_succeeds(self):
        self.assertTrue(self.report.ok, self.report.format_text(max_counterexamples=1))
        self.assertEqual(30, self.report.total_scenarios)
        self.assertEqual(2, self.report.needs_human_review)

    def test_correct_model_scenarios_pass_or_expected_review(self):
        for name in [f"S{index:02d}" for index in range(1, 13) if index != 11]:
            matching = [key for key in self.statuses if key.startswith(name)]
            self.assertEqual(1, len(matching), name)
            self.assertEqual("pass", self.statuses[matching[0]])

        self.assertEqual(
            "expected_violation_observed",
            self.statuses["S11_inconsistent_initial_record_without_score"],
        )

    def test_key_broken_models_are_caught(self):
        expected = {
            "B01_broken_duplicate_record_repeated_high",
            "B03_broken_repeated_scoring_high_twice",
            "B05_broken_low_score_recorded",
            "B08_broken_downstream_non_consumable_output",
            "B11_broken_wrong_state_owner",
        }
        for name in expected:
            self.assertEqual("expected_violation_observed", self.statuses[name])

    def test_run_scenario_review_script_succeeds(self):
        completed = subprocess.run(
            [sys.executable, "examples/job_matching/run_scenario_review.py"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("expected violations observed", completed.stdout)
        self.assertIn("needs human review", completed.stdout)


if __name__ == "__main__":
    unittest.main()
