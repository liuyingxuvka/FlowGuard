import subprocess
import sys
import unittest

from examples.flowguard_runner_self_review.model import (
    BROKEN_AUDIT_WARNING_PASS,
    BROKEN_CONFORMANCE_OVERCLAIM,
    BROKEN_EXPLORER_DOWNGRADED,
    BROKEN_MINIMIZER_DROPS_ORIGINAL,
    BROKEN_PACKS_MANDATORY,
    BROKEN_SCENARIO_AUTO_PASS,
    CORRECT_RUNNER,
    DIRECT_EXPLORER_ALLOWED,
    representative_summary_lines,
    run_runner_self_check_summary,
    run_runner_self_review,
)


class FlowguardRunnerSelfReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = run_runner_self_review()
        cls.statuses = {result.scenario_name: result.status for result in cls.review.results}
        cls.summary = run_runner_self_check_summary()
        cls.sections = {section.name: section for section in cls.summary.sections}

    def test_runner_self_review_catalog_matches_expectations(self):
        self.assertTrue(self.review.ok, self.review.format_text(max_counterexamples=1))
        self.assertEqual(8, self.review.total_scenarios)
        self.assertEqual(2, self.review.passed)
        self.assertEqual(6, self.review.expected_violations_observed)

    def test_supported_helper_runner_paths_pass(self):
        for case in (CORRECT_RUNNER, DIRECT_EXPLORER_ALLOWED):
            self.assertEqual("pass", self.statuses[case.name])

    def test_broken_helper_runner_variants_are_caught(self):
        for case in (
            BROKEN_EXPLORER_DOWNGRADED,
            BROKEN_AUDIT_WARNING_PASS,
            BROKEN_CONFORMANCE_OVERCLAIM,
            BROKEN_SCENARIO_AUTO_PASS,
            BROKEN_MINIMIZER_DROPS_ORIGINAL,
            BROKEN_PACKS_MANDATORY,
        ):
            self.assertEqual("expected_violation_observed", self.statuses[case.name])

    def test_runner_summary_preserves_gaps_without_failing_model_check(self):
        self.assertEqual("pass_with_gaps", self.summary.overall_status)
        self.assertEqual("pass_with_gaps", self.sections["model_quality_audit"].status)
        self.assertEqual("pass", self.sections["model_check"].status)
        self.assertEqual("not_run", self.sections["counterexample_minimization"].status)
        self.assertEqual("pass_with_gaps", self.sections["scenario_matrix"].status)
        self.assertEqual("pass_with_gaps", self.sections["scenario_review"].status)
        self.assertEqual("not_run", self.sections["conformance_replay"].status)

    def test_runner_summary_lines_are_easy_to_scan(self):
        lines = representative_summary_lines(self.summary)
        joined = "\n".join(lines)
        self.assertIn("model_check:pass", joined)
        self.assertIn("model_quality_audit:pass_with_gaps", joined)
        self.assertIn("conformance_replay:not_run", joined)

    def test_runner_self_review_script_succeeds(self):
        completed = subprocess.run(
            [sys.executable, "examples/flowguard_runner_self_review/run_review.py"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("flowguard runner self-review", completed.stdout)
        self.assertIn("expected violations observed: 6", completed.stdout)
        self.assertIn("overall_status: pass_with_gaps", completed.stdout)


if __name__ == "__main__":
    unittest.main()
