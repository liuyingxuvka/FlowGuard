import subprocess
import sys
import unittest

from examples.flowguard_self_review.model import run_self_review


class FlowguardSelfReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_self_review()
        cls.statuses = {result.scenario_name: result.status for result in cls.report.results}

    def test_self_review_catalog_matches_expectations(self):
        self.assertTrue(self.report.ok, self.report.format_text(max_counterexamples=1))
        self.assertEqual(15, self.report.total_scenarios)
        self.assertEqual(7, self.report.passed)
        self.assertEqual(8, self.report.expected_violations_observed)

    def test_correct_product_flow_scenarios_pass(self):
        for name in (
            "FGS01_new_project_architecture_requires_model",
            "FGS02_retry_dedup_workflow_runs_progress_checks",
            "FGS03_production_change_runs_conformance",
            "FGS04_architecture_revision_reruns_model_checks",
            "FGS05_counterexample_blocks_production",
            "FGS06_trivial_docs_can_skip_with_reason",
            "FGS07_missing_toolchain_blocks_full_adoption",
        ):
            self.assertEqual("pass", self.statuses[name])

    def test_broken_product_flow_variants_are_caught(self):
        expected = {
            "FGB01_broken_trigger_skips_architecture",
            "FGB02_broken_missing_conformance",
            "FGB03_broken_missing_adoption_log",
            "FGB04_broken_no_rerun_for_architecture_revision",
            "FGB05_broken_approves_counterexample",
            "FGB06_broken_daily_review_replaces_checks",
            "FGB07_broken_toolchain_substitute_claims_full_adoption",
            "FGB08_broken_in_progress_adoption_treated_as_final",
        }
        for name in expected:
            self.assertEqual("expected_violation_observed", self.statuses[name])

    def test_self_review_script_succeeds(self):
        completed = subprocess.run(
            [sys.executable, "examples/flowguard_self_review/run_self_review.py"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("flowguard self-review", completed.stdout)
        self.assertIn("expected violations observed: 8", completed.stdout)

    def test_self_review_cli_wrapper_succeeds(self):
        completed = subprocess.run(
            [sys.executable, "-m", "flowguard", "self-review"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("expected violations observed: 8", completed.stdout)


if __name__ == "__main__":
    unittest.main()
