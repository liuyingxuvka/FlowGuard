import subprocess
import sys
import unittest

from examples.flowguard_product_boundary.model import run_product_boundary_review


class FlowguardProductBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_product_boundary_review()
        cls.statuses = {result.scenario_name: result.status for result in cls.report.results}

    def test_product_boundary_catalog_matches_expectations(self):
        self.assertTrue(self.report.ok, self.report.format_text(max_counterexamples=1))
        self.assertEqual(5, self.report.total_scenarios)
        self.assertEqual(2, self.report.passed)
        self.assertEqual(3, self.report.expected_violations_observed)

    def test_public_minimal_system_scenarios_pass(self):
        self.assertEqual(
            "pass",
            self.statuses["PBS01_minimal_public_surface_keeps_internal_private"],
        )
        self.assertEqual("pass", self.statuses["PBS02_optional_cli_can_wait"])

    def test_broken_public_boundary_variants_are_caught(self):
        expected = {
            "PBS03_broken_exposes_internal_maintenance",
            "PBS04_broken_omits_codex_skill",
            "PBS05_broken_manual_log_burdens_user",
        }
        for name in expected:
            self.assertEqual("expected_violation_observed", self.statuses[name])

    def test_product_boundary_script_succeeds(self):
        completed = subprocess.run(
            [sys.executable, "examples/flowguard_product_boundary/run_review.py"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("flowguard product-boundary review", completed.stdout)
        self.assertIn("expected violations observed: 3", completed.stdout)


if __name__ == "__main__":
    unittest.main()
