import subprocess
import sys
import unittest

from examples.flowguard_skill_collaboration.model import run_skill_collaboration_review


class FlowguardSkillCollaborationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_skill_collaboration_review()
        cls.statuses = {result.scenario_name: result.status for result in cls.report.results}

    def test_collaboration_catalog_matches_expectations(self):
        self.assertTrue(self.report.ok, self.report.format_text(max_counterexamples=1))
        self.assertEqual(12, self.report.total_scenarios)
        self.assertEqual(5, self.report.passed)
        self.assertEqual(7, self.report.expected_violations_observed)

    def test_good_modes_pass(self):
        for name in (
            "SCS01_standalone_mode_still_works",
            "SCS02_collaboration_mode_accepts_complete_handoff",
            "SCS03_missing_upstream_tool_falls_back",
            "SCS04_trivial_work_skips_with_reason",
            "SCS05_incomplete_handoff_blocks_collaboration",
        ):
            self.assertEqual("pass", self.statuses[name])

    def test_broken_collaboration_variants_are_caught(self):
        expected = {
            "SCB01_broken_hard_dependency_on_upstream_tool",
            "SCB02_broken_side_effects_not_mapped",
            "SCB03_broken_parallel_work_without_ownership",
            "SCB04_broken_skip_without_reason",
            "SCB05_broken_counterexample_ignored",
            "SCB06_broken_trivial_work_overtriggers",
            "SCB07_broken_completion_without_evidence",
        }
        for name in expected:
            self.assertEqual("expected_violation_observed", self.statuses[name])

    def test_collaboration_review_script_succeeds(self):
        completed = subprocess.run(
            [sys.executable, "examples/flowguard_skill_collaboration/run_review.py"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("flowguard skill collaboration review", completed.stdout)
        self.assertIn("expected violations observed: 7", completed.stdout)


if __name__ == "__main__":
    unittest.main()
