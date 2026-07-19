import subprocess
import sys
import unittest

from examples.latest_schema_upgrade_policy.model import (
    BROKEN_CLASSIFIER_DELETED,
    BROKEN_NUMERIC_TARGET_JSON_REWRITE,
    BROKEN_PARTIAL_LEDGER_REWRITE,
    BROKEN_RUNTIME_COMPAT,
    BROKEN_SILENT_SKIP,
    BROKEN_UNSUPPORTED_REGISTERED_ENVELOPE_REWRITE,
    BROKEN_UNKNOWN_REWRITE,
    CURRENT_ARTIFACT,
    LEGACY_BCL_ARTIFACT_UPGRADED,
    OLDER_PROJECT_TRIGGERS_SCAN,
    RECORDS_ONLY_SCOPED,
    TARGET_OWNED_JSON_PRESERVED,
    UNSUPPORTED_REGISTERED_ENVELOPE_BLOCKED,
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
        self.assertEqual(14, self.review.total_scenarios)
        self.assertEqual(7, self.review.passed)
        self.assertEqual(7, self.review.expected_violations_observed)

    def test_supported_policy_paths_pass(self):
        for case in (
            CURRENT_ARTIFACT,
            LEGACY_BCL_ARTIFACT_UPGRADED,
            UNSUPPORTED_REGISTERED_ENVELOPE_BLOCKED,
            OLDER_PROJECT_TRIGGERS_SCAN,
            UNKNOWN_SCRIPT_BLOCKED,
            RECORDS_ONLY_SCOPED,
            TARGET_OWNED_JSON_PRESERVED,
        ):
            self.assertEqual("pass", self.statuses[case.name])

    def test_broken_policy_paths_are_caught(self):
        for case in (
            BROKEN_RUNTIME_COMPAT,
            BROKEN_SILENT_SKIP,
            BROKEN_UNKNOWN_REWRITE,
            BROKEN_CLASSIFIER_DELETED,
            BROKEN_NUMERIC_TARGET_JSON_REWRITE,
            BROKEN_PARTIAL_LEDGER_REWRITE,
            BROKEN_UNSUPPORTED_REGISTERED_ENVELOPE_REWRITE,
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
        self.assertIn("expected violations observed: 7", completed.stdout)


if __name__ == "__main__":
    unittest.main()
