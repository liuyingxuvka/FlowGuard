import subprocess
import sys
import unittest

from examples.latest_schema_upgrade_policy.model import (
    BROKEN_CLASSIFIER_DELETED,
    BROKEN_RUNTIME_COMPAT,
    BROKEN_SILENT_SKIP,
    BROKEN_UNKNOWN_REWRITE,
    CURRENT_ARTIFACT,
    KNOWN_OLD_ARTIFACT_UPGRADED,
    OLDER_PROJECT_TRIGGERS_SCAN,
    RECORDS_ONLY_SCOPED,
    UNKNOWN_SCRIPT_BLOCKED,
    run_latest_schema_upgrade_policy_review,
)


class LatestSchemaUpgradePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = run_latest_schema_upgrade_policy_review()
        cls.statuses = {result.scenario_name: result.status for result in cls.review.results}

    def test_policy_model_matches_expectations(self):
        self.assertTrue(self.review.ok, self.review.format_text(max_counterexamples=1))
        self.assertEqual(9, self.review.total_scenarios)
        self.assertEqual(5, self.review.passed)
        self.assertEqual(4, self.review.expected_violations_observed)

    def test_supported_policy_paths_pass(self):
        for case in (
            CURRENT_ARTIFACT,
            KNOWN_OLD_ARTIFACT_UPGRADED,
            OLDER_PROJECT_TRIGGERS_SCAN,
            UNKNOWN_SCRIPT_BLOCKED,
            RECORDS_ONLY_SCOPED,
        ):
            self.assertEqual("pass", self.statuses[case.name])

    def test_broken_policy_paths_are_caught(self):
        for case in (
            BROKEN_RUNTIME_COMPAT,
            BROKEN_SILENT_SKIP,
            BROKEN_UNKNOWN_REWRITE,
            BROKEN_CLASSIFIER_DELETED,
        ):
            self.assertEqual("expected_violation_observed", self.statuses[case.name])

    def test_policy_review_script_succeeds(self):
        completed = subprocess.run(
            [sys.executable, "examples/latest_schema_upgrade_policy/run_review.py"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("latest-schema upgrade policy", completed.stdout)
        self.assertIn("expected violations observed: 4", completed.stdout)


if __name__ == "__main__":
    unittest.main()
