from dataclasses import replace
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
    FINAL_CLAIM_FULL,
    REHEARSAL_STATUS_BLOCKED,
    REHEARSAL_STATUS_NEEDS_REVISION,
    REHEARSAL_STATUS_PASS,
    REHEARSAL_STATUS_SCOPED,
    UI_EVIDENCE_ROLE_SOURCE_BASELINE,
    UI_EVIDENCE_ROLE_FUNCTIONAL_CAPABILITY,
    UI_EVIDENCE_ROLE_HUMAN_OPERABILITY,
    UI_EVIDENCE_ROLE_IMPLEMENTATION_VALIDATION,
    UI_EVIDENCE_ROLE_INVENTORY,
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

    def test_completion_ledger_exposes_passing_handoff_points(self):
        report = review_agent_workflow_rehearsal(GOOD_PLAN)
        expected_steps = tuple(step.step_id for step in GOOD_PLAN.steps)

        self.assertEqual(expected_steps, report.planned_steps)
        self.assertEqual(expected_steps, report.completed_steps)
        self.assertEqual((), report.blocked_steps)
        self.assertEqual((), report.skipped_steps)
        self.assertEqual((), report.required_rechecks)
        self.assertEqual(GOOD_PLAN.final_claim, report.final_claim_boundary)
        for evidence_id in ("kb-hits", "process-evidence", "release-evidence"):
            self.assertIn(evidence_id, report.handoff_points)

        data = report.to_dict()
        self.assertEqual(list(expected_steps), data["planned_steps"])
        self.assertEqual(GOOD_PLAN.final_claim, data["final_claim_boundary"])
        text = report.format_text()
        self.assertIn("planned_steps:", text)
        self.assertIn("handoff_points:", text)

    def test_completion_ledger_exposes_blocked_and_skipped_items(self):
        report = review_agent_workflow_rehearsal(MISSING_REQUIRED_SKILL_PLAN)

        self.assertIn("skill:frontend-design", report.blocked_steps)
        self.assertIn("skill:frontend-design", report.skipped_steps)
        self.assertTrue(
            any(recheck.endswith(":required_candidate_skill_skipped") for recheck in report.required_rechecks),
            report.to_json(),
        )
        self.assertEqual(MISSING_REQUIRED_SKILL_PLAN.final_claim, report.final_claim_boundary)

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

    def test_full_ui_claim_requires_separate_role_evidence(self):
        missing_roles = replace(
            GOOD_PLAN,
            plan_id="ui-full-missing-role-evidence",
            task_summary="UI implementation full claim",
            final_claim=FINAL_CLAIM_FULL,
            final_evidence_ids=("evidence:ui-done",),
            risk_flags=("ui",),
            ui_evidence_roles=(UI_EVIDENCE_ROLE_INVENTORY,),
        )
        report = review_agent_workflow_rehearsal(missing_roles)

        self.assertEqual(REHEARSAL_STATUS_BLOCKED, report.status, report.format_text())
        self.assertIn("ui_agent_role_evidence_missing", {finding.code for finding in report.findings})

    def test_full_ui_claim_passes_with_inventory_source_baseline_click_and_human_roles(self):
        complete_roles = replace(
            GOOD_PLAN,
            plan_id="ui-full-complete-role-evidence",
            task_summary="UI implementation full claim",
            final_claim=FINAL_CLAIM_FULL,
            final_evidence_ids=("evidence:ui-done",),
            risk_flags=("ui",),
            ui_evidence_roles=(
                UI_EVIDENCE_ROLE_INVENTORY,
                UI_EVIDENCE_ROLE_FUNCTIONAL_CAPABILITY,
                UI_EVIDENCE_ROLE_SOURCE_BASELINE,
                UI_EVIDENCE_ROLE_IMPLEMENTATION_VALIDATION,
                UI_EVIDENCE_ROLE_HUMAN_OPERABILITY,
            ),
        )
        report = review_agent_workflow_rehearsal(complete_roles)

        self.assertEqual(REHEARSAL_STATUS_PASS, report.status, report.format_text())

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
