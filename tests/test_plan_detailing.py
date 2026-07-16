import subprocess
import sys
import unittest
from dataclasses import replace

import flowguard
from examples.plan_detailing_compiler.model import (
    GOOD_PLAN,
    SPEC_MAPPED_PLAN,
    BROKEN_SPEC_MAPPING,
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
        self.assertEqual(8, self.report.total_scenarios)
        self.assertEqual(8, self.report.passed)
        self.assertEqual(0, self.report.oracle_mismatches)

    def test_direct_review_statuses(self):
        cases = (
            (GOOD_PLAN, flowguard.PLAN_DETAIL_STATUS_PASS),
            (VAGUE_PLAN, flowguard.PLAN_DETAIL_STATUS_BLOCKED),
            (HAPPY_PATH_ONLY_PLAN, flowguard.PLAN_DETAIL_STATUS_BLOCKED),
            (MISSING_REWORK_PLAN, flowguard.PLAN_DETAIL_STATUS_BLOCKED),
            (UNGATED_SIDE_EFFECT_PLAN, flowguard.PLAN_DETAIL_STATUS_BLOCKED),
            (SCOPED_HUMAN_REVIEW_PLAN, flowguard.PLAN_DETAIL_STATUS_SCOPED),
            (SPEC_MAPPED_PLAN, flowguard.PLAN_DETAIL_STATUS_PASS),
            (BROKEN_SPEC_MAPPING, flowguard.PLAN_DETAIL_STATUS_BLOCKED),
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

    def test_process_optimization_projects_to_development_process_without_step_level_duplicates(self):
        decision = flowguard.PlanDetailEvidence(
            "evidence:process-optimization",
            evidence_kind=flowguard.PROCESS_EVIDENCE_PROCESS_OPTIMIZATION,
            status="passed",
            produced_by_step_id=GOOD_PLAN.steps[0].step_id,
        )
        detailed = replace(
            GOOD_PLAN,
            evidence=GOOD_PLAN.evidence + (decision,),
            process_optimization_reasons=("material_rework_risk",),
            required_process_optimization_evidence_ids=(decision.evidence_id,),
        )
        report = flowguard.review_plan_detail(detailed)
        self.assertEqual(flowguard.PLAN_DETAIL_STATUS_PASS, report.status, report.format_text())
        process = flowguard.plan_detail_to_development_process(detailed)
        self.assertEqual(("material_rework_risk",), process.process_optimization_reasons)
        self.assertEqual(
            (decision.evidence_id,),
            process.required_process_optimization_evidence_ids,
        )


    def ui_plan(self, *, evidence_kind="ui_runtime_click", evidence_status="passed", include_capability=True):
        step_evidence_ids = ("evidence:ui-click",)
        validation_evidence_ids = ("evidence:ui-click",)
        final_evidence_ids = ("evidence:ui-click",)
        required_evidence_kinds = ("ui_runtime_click",)
        evidence_rows = (
            flowguard.PlanDetailEvidence(
                "evidence:ui-click",
                evidence_kind=evidence_kind,
                status=evidence_status,
                produced_by_step_id="step:validate-ui",
                covers_artifacts=("artifact:ui-code",),
                validation_ids=("validation:ui-click",),
                result_path="tmp/ui-click.json",
            ),
        )
        if include_capability:
            step_evidence_ids += ("evidence:ui-capability",)
            validation_evidence_ids += ("evidence:ui-capability",)
            final_evidence_ids += ("evidence:ui-capability",)
            required_evidence_kinds += ("ui_functional_capability_coverage",)
            evidence_rows += (
                flowguard.PlanDetailEvidence(
                    "evidence:ui-capability",
                    evidence_kind="ui_functional_capability_coverage",
                    status="passed",
                    produced_by_step_id="step:validate-ui",
                    covers_artifacts=("artifact:ui-code",),
                    validation_ids=("validation:ui-click",),
                    result_path="tmp/ui-capability.json",
                ),
            )
        return flowguard.PlanDetail(
            "plan:ui",
            task_summary="UI button implementation",
            goal="claim the UI button is implemented",
            sources=(flowguard.PlanDetailSource("source:real-page", source_kind="browser_observation"),),
            surfaces=(
                flowguard.PlanDetailSurface(
                    "surface:ui-button",
                    surface_kind="ui_control",
                    source_ids=("source:real-page",),
                ),
            ),
            artifacts=(flowguard.ProcessArtifact("artifact:ui-code", path="app/ui.py"),),
            state_surfaces=(
                flowguard.PlanDetailStateSurface(
                    "state:ui-result",
                    owner="ui",
                    read_by_step_ids=("step:validate-ui",),
                    written_by_step_ids=("step:validate-ui",),
                ),
            ),
            steps=(
                flowguard.PlanDetailStep(
                    "step:implement-ui",
                    action="wire UI button",
                    writes_artifacts=("artifact:ui-code",),
                    produces_receipts=("receipt:ui-implemented",),
                ),
                flowguard.PlanDetailStep(
                    "step:validate-ui",
                    action="click UI button and observe state",
                    skill_name="flowguard-ui-flow-structure",
                    step_type="validation",
                    order_after=("step:implement-ui",),
                    reads_artifacts=("artifact:ui-code",),
                    required_evidence_ids=step_evidence_ids,
                    produced_evidence_ids=step_evidence_ids,
                    continue_evidence_ids=step_evidence_ids,
                    validation_required=True,
                    rework_step_id="step:implement-ui",
                    produces_receipts=("receipt:ui-validated",),
                    claim_labels=("done_claimed",),
                ),
            ),
            validations=(
                flowguard.PlanDetailValidation(
                    "validation:ui-click",
                    required_artifact_ids=("artifact:ui-code",),
                    required_evidence_kinds=required_evidence_kinds,
                    evidence_ids=validation_evidence_ids,
                    command="click button and observe result",
                ),
            ),
            evidence=evidence_rows,
            failure_branches=(
                flowguard.PlanDetailFailureBranch(
                    "branch:ui-click-fails",
                    trigger="button click does not update visible state",
                    step_id="step:validate-ui",
                    rework_step_id="step:implement-ui",
                ),
            ),
            final_claim=flowguard.PLAN_DETAIL_CLAIM_FULL,
            final_evidence_ids=final_evidence_ids,
        )

    def test_ui_task_checkbox_needs_current_ui_evidence_type(self):
        report = flowguard.review_plan_detail(self.ui_plan())

        self.assertEqual(flowguard.PLAN_DETAIL_STATUS_PASS, report.status, report.format_text())

    def test_ui_human_walkthrough_evidence_type_can_satisfy_ui_task(self):
        report = flowguard.review_plan_detail(self.ui_plan(evidence_kind="ui_human_walkthrough"))

        self.assertEqual(flowguard.PLAN_DETAIL_STATUS_PASS, report.status, report.format_text())

    def test_ui_source_alignment_evidence_type_can_satisfy_ui_task(self):
        report = flowguard.review_plan_detail(self.ui_plan(evidence_kind="ui_observed_source_alignment"))

        self.assertEqual(flowguard.PLAN_DETAIL_STATUS_PASS, report.status, report.format_text())

    def test_full_ui_plan_requires_capability_coverage_evidence_type(self):
        report = flowguard.review_plan_detail(self.ui_plan(include_capability=False))

        self.assertEqual(flowguard.PLAN_DETAIL_STATUS_BLOCKED, report.status, report.format_text())
        self.assertIn("ui_plan_missing_capability_evidence_type", {finding.code for finding in report.findings})

    def test_ui_task_rejects_generic_or_planned_evidence(self):
        generic = flowguard.review_plan_detail(self.ui_plan(evidence_kind="test"))
        generic_codes = {finding.code for finding in generic.findings}
        self.assertEqual(flowguard.PLAN_DETAIL_STATUS_BLOCKED, generic.status, generic.format_text())
        self.assertIn("ui_task_missing_evidence_type", generic_codes)
        self.assertIn("ui_validation_evidence_type_mismatch", generic_codes)

        planned = flowguard.review_plan_detail(self.ui_plan(evidence_status="planned"))
        planned_codes = {finding.code for finding in planned.findings}
        self.assertEqual(flowguard.PLAN_DETAIL_STATUS_BLOCKED, planned.status, planned.format_text())
        self.assertIn("ui_task_evidence_not_current", planned_codes)
        self.assertIn("ui_validation_evidence_not_current", planned_codes)
        self.assertIn("ui_evidence_status_not_passing", planned_codes)

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

    def test_plane_aware_projection_keeps_product_behavior_as_target_context(self):
        relation_ref = "commitment:agent-ui-change|validates|commitment:product-ui"
        steps = tuple(
            replace(
                step,
                behavior_plane="agent_operation",
                target_behavior_planes=("product_runtime",),
                target_commitment_ids=("commitment:product-ui",),
                typed_commitment_relation_refs=(relation_ref,),
            )
            for step in GOOD_PLAN.steps
        )
        plan = replace(
            GOOD_PLAN,
            plan_id="plane-aware-projection",
            steps=steps,
            require_behavior_plane_boundary=True,
        )

        detail_report = flowguard.review_plan_detail(plan)
        self.assertEqual(flowguard.PLAN_DETAIL_STATUS_PASS, detail_report.status, detail_report.format_text())

        process = flowguard.plan_detail_to_development_process(plan)
        self.assertEqual("development_process", process.behavior_plane)
        self.assertTrue(all(action.behavior_plane == "development_process" for action in process.actions))
        self.assertTrue(all("product_runtime" in action.target_behavior_planes for action in process.actions))
        self.assertTrue(flowguard.review_development_process_flow(process).ok)

        inventory = flowguard.SkillInventorySnapshot("current", current=True, from_cache=False)
        workflow = flowguard.plan_detail_to_agent_workflow_plan(plan, inventory)
        self.assertEqual("agent_operation", workflow.behavior_plane)
        self.assertTrue(all(step.behavior_plane == "agent_operation" for step in workflow.steps))
        self.assertTrue(all("product_runtime" in step.target_behavior_planes for step in workflow.steps))

        bad = replace(plan, steps=(replace(steps[0], behavior_plane="product_runtime"),) + steps[1:])
        bad_report = flowguard.review_plan_detail(bad)
        self.assertIn(
            "plan_step_absorbs_target_behavior_plane",
            {finding.code for finding in bad_report.findings},
        )

    def test_plan_detailing_script_succeeds(self):
        completed = subprocess.run(
            [sys.executable, "examples/plan_detailing_compiler/run_review.py"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("flowguard scenario review", completed.stdout)
        self.assertIn("total: 8", completed.stdout)

    def test_spec_mapping_survives_development_process_projection(self):
        process = flowguard.plan_detail_to_development_process(SPEC_MAPPED_PLAN)
        self.assertIn("1.1", {task for action in process.actions for task in action.spec_task_ids})
        self.assertIn(
            "req.one",
            {obligation for validation in process.validation_requirements for obligation in validation.spec_obligation_ids},
        )


if __name__ == "__main__":
    unittest.main()
