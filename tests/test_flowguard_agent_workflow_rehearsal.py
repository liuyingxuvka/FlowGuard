import subprocess
import sys
import unittest

from examples.flowguard_agent_workflow_rehearsal.model import (
    GOOD_PLAN,
    MISSING_REWORK_PLAN,
    MISSING_REQUIRED_SKILL_PLAN,
    OVERBROAD_CLAIM_PLAN,
    OVERTRIGGER_PLAN,
    STALE_SNAPSHOT_PLAN,
    WEAK_VALIDATION_PLAN,
    WRONG_ORDER_PLAN,
    run_agent_workflow_rehearsal_review,
)
from flowguard import (
    REHEARSAL_STATUS_BLOCKED,
    REHEARSAL_STATUS_NEEDS_REVISION,
    REHEARSAL_STATUS_PASS,
    REHEARSAL_STATUS_SCOPED,
    review_agent_workflow_rehearsal,
)


class FlowguardAgentWorkflowRehearsalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_agent_workflow_rehearsal_review()
        cls.statuses = {result.scenario_name: result.status for result in cls.report.results}

    def test_rehearsal_catalog_matches_expectations(self):
        self.assertTrue(self.report.ok, self.report.format_text(max_counterexamples=1))
        self.assertEqual(8, self.report.total_scenarios)
        self.assertEqual(8, self.report.passed)
        self.assertEqual(0, self.report.expected_violations_observed)
        self.assertEqual(0, self.report.oracle_mismatches)

    def test_direct_rehearsal_statuses(self):
        cases = {
            GOOD_PLAN: REHEARSAL_STATUS_PASS,
            STALE_SNAPSHOT_PLAN: REHEARSAL_STATUS_BLOCKED,
            MISSING_REQUIRED_SKILL_PLAN: REHEARSAL_STATUS_BLOCKED,
            WEAK_VALIDATION_PLAN: REHEARSAL_STATUS_SCOPED,
            MISSING_REWORK_PLAN: REHEARSAL_STATUS_NEEDS_REVISION,
            WRONG_ORDER_PLAN: REHEARSAL_STATUS_BLOCKED,
            OVERBROAD_CLAIM_PLAN: REHEARSAL_STATUS_BLOCKED,
            OVERTRIGGER_PLAN: REHEARSAL_STATUS_NEEDS_REVISION,
        }
        for plan, expected_status in cases.items():
            with self.subTest(plan=plan.plan_id):
                report = review_agent_workflow_rehearsal(plan)
                self.assertEqual(expected_status, report.status, report.format_text())

    def test_rehearsal_findings_cover_key_hazards(self):
        expected_codes = {
            STALE_SNAPSHOT_PLAN: "stale_or_cached_skill_inventory",
            MISSING_REQUIRED_SKILL_PLAN: "required_candidate_skill_skipped",
            WEAK_VALIDATION_PLAN: "selected_skill_has_weak_validation_guidance",
            MISSING_REWORK_PLAN: "rework_gate_missing",
            WRONG_ORDER_PLAN: "workflow_step_missing_required_evidence",
            OVERBROAD_CLAIM_PLAN: "full_claim_missing_final_evidence",
            OVERTRIGGER_PLAN: "trivial_task_overtriggers_skills",
        }
        for plan, expected_code in expected_codes.items():
            with self.subTest(plan=plan.plan_id):
                report = review_agent_workflow_rehearsal(plan)
                codes = {finding.code for finding in report.findings}
                self.assertIn(expected_code, codes)

    def test_rehearsal_script_succeeds(self):
        completed = subprocess.run(
            [sys.executable, "examples/flowguard_agent_workflow_rehearsal/run_review.py"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("flowguard agent workflow rehearsal review", completed.stdout)
        self.assertIn("total: 8", completed.stdout)


if __name__ == "__main__":
    unittest.main()
