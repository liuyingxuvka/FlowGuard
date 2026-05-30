import subprocess
import sys
import unittest

import flowguard
from examples.plan_detailing_compiler.model import (
    GOOD_PLAN,
    HAPPY_PATH_ONLY_PLAN,
    MISSING_REWORK_PLAN,
    SCOPED_HUMAN_REVIEW_PLAN,
    UNGATED_SIDE_EFFECT_PLAN,
    VAGUE_PLAN,
    run_plan_detailing_review,
)


class PlanDetailingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_plan_detailing_review()

    def test_plan_detailing_model_covers_good_and_broken_paths(self):
        self.assertTrue(self.report.ok, self.report.format_text(max_counterexamples=1))
        self.assertEqual(6, self.report.total_scenarios)
        self.assertEqual(6, self.report.passed)
        self.assertEqual(0, self.report.oracle_mismatches)

    def test_direct_review_statuses(self):
        cases = (
            (GOOD_PLAN, flowguard.PLAN_DETAIL_STATUS_PASS),
            (VAGUE_PLAN, flowguard.PLAN_DETAIL_STATUS_BLOCKED),
            (HAPPY_PATH_ONLY_PLAN, flowguard.PLAN_DETAIL_STATUS_BLOCKED),
            (MISSING_REWORK_PLAN, flowguard.PLAN_DETAIL_STATUS_BLOCKED),
            (UNGATED_SIDE_EFFECT_PLAN, flowguard.PLAN_DETAIL_STATUS_BLOCKED),
            (SCOPED_HUMAN_REVIEW_PLAN, flowguard.PLAN_DETAIL_STATUS_SCOPED),
        )
        for plan, expected_status in cases:
            with self.subTest(plan=plan.plan_id):
                report = flowguard.review_plan_detail(plan)
                self.assertEqual(expected_status, report.status, report.format_text())

    def test_findings_name_missing_detail(self):
        expected_codes = (
            (VAGUE_PLAN, {"missing_source_evidence", "missing_steps", "full_claim_missing_final_evidence"}),
            (HAPPY_PATH_ONLY_PLAN, {"missing_failure_branches", "full_claim_has_detail_gaps"}),
            (MISSING_REWORK_PLAN, {"rework_gate_missing", "full_claim_has_detail_gaps"}),
            (UNGATED_SIDE_EFFECT_PLAN, {"side_effect_missing_evidence_gate", "full_claim_has_detail_gaps"}),
            (SCOPED_HUMAN_REVIEW_PLAN, {"human_question_unresolved"}),
        )
        for plan, codes in expected_codes:
            with self.subTest(plan=plan.plan_id):
                found = {finding.code for finding in flowguard.review_plan_detail(plan).findings}
                self.assertTrue(codes.issubset(found), found)

    def test_projection_helpers_feed_existing_routes(self):
        intake = flowguard.plan_detail_to_plan_intake(GOOD_PLAN)
        contracts = flowguard.plan_detail_to_step_contracts(GOOD_PLAN)
        process = flowguard.plan_detail_to_development_process(GOOD_PLAN)
        inventory = flowguard.SkillInventorySnapshot("current", current=True, from_cache=False)
        workflow_plan = flowguard.plan_detail_to_agent_workflow_plan(GOOD_PLAN, inventory)

        self.assertEqual(GOOD_PLAN.plan_id, intake.plan_id)
        self.assertTrue(flowguard.review_plan_intake_completeness(intake).ok)
        self.assertGreaterEqual(len(contracts), len(GOOD_PLAN.steps))
        self.assertTrue(any("done_claimed" in contract.required_for_claims for contract in contracts))
        self.assertEqual(GOOD_PLAN.plan_id, process.process_id)
        self.assertTrue(flowguard.review_development_process_flow(process).ok)
        self.assertEqual(GOOD_PLAN.plan_id, workflow_plan.plan_id)
        self.assertEqual(flowguard.FINAL_CLAIM_FULL, workflow_plan.final_claim)

    def test_plan_detailing_script_succeeds(self):
        completed = subprocess.run(
            [sys.executable, "examples/plan_detailing_compiler/run_review.py"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("flowguard scenario review", completed.stdout)
        self.assertIn("total: 6", completed.stdout)


if __name__ == "__main__":
    unittest.main()
