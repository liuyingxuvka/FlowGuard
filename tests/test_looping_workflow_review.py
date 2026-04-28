import subprocess
import sys
import unittest

from examples.looping_workflow.model import run_loop_review


class LoopingWorkflowReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_loop_review()
        cls.statuses = {result.scenario_name: result.status for result in cls.report.results}

    def test_loop_review_succeeds_with_known_limitations(self):
        self.assertTrue(self.report.ok, self.report.format_text())
        self.assertEqual(14, self.report.total)
        self.assertEqual(0, self.report.known_limitations)

    def test_good_and_bad_loop_scenarios_are_classified(self):
        self.assertEqual("pass", self.statuses["L01_good_rewrite_once_then_ready"])
        self.assertEqual("expected_violation_observed", self.statuses["L02_bad_infinite_rewrite_loop"])
        self.assertEqual("pass", self.statuses["L03_good_retry_limit_then_needs_human"])
        self.assertEqual("expected_violation_observed", self.statuses["L04_bad_retry_no_limit"])
        self.assertEqual("expected_violation_observed", self.statuses["L05_bad_waiting_self_loop"])
        self.assertEqual("expected_violation_observed", self.statuses["L08_terminal_with_outgoing_edge"])
        self.assertEqual("expected_violation_observed", self.statuses["L09_unreachable_success"])

    def test_escape_edge_cycles_are_progress_findings(self):
        self.assertEqual("expected_violation_observed", self.statuses["L13_bad_branch_has_one_good_one_bad_loop"])
        self.assertEqual("expected_violation_observed", self.statuses["L14_bad_cycle_with_escape_but_no_forced_progress"])
        for result in self.report.results:
            if result.scenario_name in {
                "L13_bad_branch_has_one_good_one_bad_loop",
                "L14_bad_cycle_with_escape_but_no_forced_progress",
            }:
                self.assertIn("potential_nontermination", result.observed_summary)
                self.assertIn("missing_progress_guarantee", result.observed_summary)

    def test_run_loop_review_script_succeeds(self):
        completed = subprocess.run(
            [sys.executable, "examples/looping_workflow/run_loop_review.py"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("flowguard loop review", completed.stdout)
        self.assertIn("expected violations observed", completed.stdout)


if __name__ == "__main__":
    unittest.main()
