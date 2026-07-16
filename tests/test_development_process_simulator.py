import unittest

from flowguard import (
    DEVELOPMENT_PROCESS_FRONT_DOOR_SKILL,
    SIMULATOR_MODE_AGENT_WORKFLOW,
    SIMULATOR_MODE_EXECUTION_FRESHNESS,
    SIMULATOR_MODE_PLAN_DETAILING,
    SIMULATOR_MODE_STRATEGY_SELECTION,
    SIMULATOR_STATUS_PASS,
    SIMULATOR_STATUS_SCOPED,
    SIMULATOR_STATUS_SKIPPED,
    DevelopmentProcessSimulationRequest,
    review_development_process_simulator,
)


class DevelopmentProcessSimulatorTests(unittest.TestCase):
    def test_process_optimization_is_conditional_and_ordered_between_plan_and_agent_modes(self):
        report = review_development_process_simulator(
            DevelopmentProcessSimulationRequest(
                "optimize-process",
                rough_plan=True,
                process_optimization_reasons=(
                    "multiple_equivalent_routes",
                    "material_rework_risk",
                ),
                multiple_skills_or_tools=True,
                staged_validation=True,
                process_optimization_evidence_ids=("optimization:decision:v1",),
            )
        )
        self.assertEqual(
            (
                SIMULATOR_MODE_PLAN_DETAILING,
                SIMULATOR_MODE_STRATEGY_SELECTION,
                SIMULATOR_MODE_AGENT_WORKFLOW,
                SIMULATOR_MODE_EXECUTION_FRESHNESS,
            ),
            report.selected_modes,
        )
        strategy = report.mode_decisions[1]
        self.assertEqual(DEVELOPMENT_PROCESS_FRONT_DOOR_SKILL, strategy.delegated_skill)
        self.assertEqual("review_process_optimization", strategy.required_review)

    def test_rough_plan_selects_plan_detailing_under_front_door(self):
        report = review_development_process_simulator(
            DevelopmentProcessSimulationRequest(
                "rough-plan",
                task_summary="discuss a detailed implementation plan",
                rough_plan=True,
                plan_discussion=True,
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(DEVELOPMENT_PROCESS_FRONT_DOOR_SKILL, report.front_door_skill)
        self.assertEqual((SIMULATOR_MODE_PLAN_DETAILING,), report.selected_modes)
        self.assertEqual(("review_plan_detail",), report.required_reviews)
        self.assertIn("flowguard-plan-detailing-compiler", report.format_text())

    def test_multi_skill_workflow_selects_agent_workflow_under_front_door(self):
        report = review_development_process_simulator(
            DevelopmentProcessSimulationRequest(
                "multi-skill",
                task_summary="combine OpenSpec, FlowGuard, install sync, and git evidence",
                multiple_skills_or_tools=True,
                external_side_effects=True,
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(DEVELOPMENT_PROCESS_FRONT_DOOR_SKILL, report.front_door_skill)
        self.assertEqual((SIMULATOR_MODE_AGENT_WORKFLOW,), report.selected_modes)
        self.assertEqual(("review_agent_workflow_rehearsal",), report.required_reviews)
        self.assertIn("flowguard-agent-workflow-rehearsal", report.format_text())

    def test_execution_and_release_select_execution_freshness(self):
        report = review_development_process_simulator(
            DevelopmentProcessSimulationRequest(
                "release-flow",
                task_summary="implement, test, sync install, tag local git",
                implementation_work=True,
                staged_validation=True,
                install_sync=True,
                shadow_workspace_sync=True,
                local_git_sync=True,
                release_archive_or_publish=True,
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual((SIMULATOR_MODE_EXECUTION_FRESHNESS,), report.selected_modes)
        self.assertEqual(("review_development_process_flow",), report.required_reviews)

    def test_full_plan_to_release_chain_preserves_mode_order_and_scopes_claim(self):
        report = review_development_process_simulator(
            DevelopmentProcessSimulationRequest(
                "plan-to-release",
                rough_plan=True,
                multiple_skills_or_tools=True,
                implementation_work=True,
                staged_validation=True,
                install_sync=True,
                shadow_workspace_sync=True,
                local_git_sync=True,
                final_claim_requested=True,
                plan_detail_evidence_ids=("plan-detail-report",),
                agent_workflow_evidence_ids=("agent-workflow-report",),
            )
        )

        self.assertEqual(
            (
                SIMULATOR_MODE_PLAN_DETAILING,
                SIMULATOR_MODE_AGENT_WORKFLOW,
                SIMULATOR_MODE_EXECUTION_FRESHNESS,
            ),
            report.selected_modes,
        )
        self.assertEqual(SIMULATOR_STATUS_SCOPED, report.status)
        self.assertFalse(report.ok)
        self.assertIn("final_claim_missing_execution_evidence", {finding.code for finding in report.findings})

    def test_final_claim_adds_execution_mode_and_scopes_without_evidence(self):
        report = review_development_process_simulator(
            DevelopmentProcessSimulationRequest(
                "bad-final-claim",
                rough_plan=True,
                final_claim_requested=True,
                plan_detail_evidence_ids=("plan-detail-report",),
            )
        )

        self.assertEqual(
            (SIMULATOR_MODE_PLAN_DETAILING, SIMULATOR_MODE_EXECUTION_FRESHNESS),
            report.selected_modes,
        )
        self.assertEqual(SIMULATOR_STATUS_SCOPED, report.status)
        self.assertIn("final_claim_missing_execution_evidence", {finding.code for finding in report.findings})

    def test_trivial_task_can_skip_with_reason(self):
        report = review_development_process_simulator(
            DevelopmentProcessSimulationRequest("trivial-copy", task_trivial=True)
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(SIMULATOR_STATUS_SKIPPED, report.status)
        self.assertEqual((), report.selected_modes)

    def test_report_serializes_mode_decisions(self):
        report = review_development_process_simulator(
            DevelopmentProcessSimulationRequest("serialize", rough_plan=True)
        )

        data = report.to_dict()
        self.assertEqual(["plan_detailing"], data["selected_modes"])
        self.assertEqual("review_plan_detail", data["mode_decisions"][0]["required_review"])
        self.assertEqual(DEVELOPMENT_PROCESS_FRONT_DOOR_SKILL, data["front_door_skill"])


if __name__ == "__main__":
    unittest.main()
