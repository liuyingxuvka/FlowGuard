import unittest
from dataclasses import replace

from flowguard import (
    PROCESS_ARTIFACT_CODE,
    PROCESS_ARTIFACT_BUG_REPAIR_CLOSURE,
    PROCESS_ARTIFACT_FIELD_LIFECYCLE,
    PROCESS_ARTIFACT_FIELD_PROJECTION,
    PROCESS_ARTIFACT_MODEL,
    PROCESS_ARTIFACT_UI_SOURCE_BASELINE_GATE,
    PROCESS_ARTIFACT_REPLACEMENT_DISPOSITION,
    PROCESS_ARTIFACT_REQUIREMENT,
    PROCESS_ARTIFACT_TEST,
    PROCESS_ARTIFACT_UI_DONE_CLAIM,
    PROCESS_ARTIFACT_UI_FUNCTIONAL_CAPABILITY_COVERAGE,
    PROCESS_ARTIFACT_UI_FUNCTIONAL_CHAIN,
    PROCESS_ARTIFACT_UI_HUMAN_OPERABILITY,
    PROCESS_ARTIFACT_UI_OBSERVED_INVENTORY,
    PROCESS_EVIDENCE_BUG_REPAIR_CLOSURE,
    PROCESS_EVIDENCE_FIELD_LIFECYCLE,
    PROCESS_EVIDENCE_FIELD_PROJECTION,
    PROCESS_EVIDENCE_FAILED,
    PROCESS_EVIDENCE_PROCESS_OPTIMIZATION,
    PROCESS_EVIDENCE_UI_SOURCE_BASELINE_GATE,
    PROCESS_EVIDENCE_UI_FUNCTIONAL_CAPABILITY_COVERAGE,
    PROCESS_EVIDENCE_MODEL_MISS_REVIEW,
    PROCESS_EVIDENCE_NOT_RUN,
    PROCESS_EVIDENCE_PASSED,
    PROCESS_EVIDENCE_RUNNING,
    PROCESS_EVIDENCE_UI_IMPLEMENTATION_VALIDATION,
    PROCESS_EVIDENCE_UI_HUMAN_OPERABILITY,
    PROCESS_SCOPE_RELEASE,
    PROCESS_SCOPE_ROUTINE,
    DevelopmentProcessPlan,
    FreshnessRule,
    ProofArtifactRef,
    ProcessAction,
    ProcessArtifact,
    ProcessEvidence,
    ValidationRequirement,
    derive_revalidation_plan,
    review_development_process_flow,
)


def base_artifacts(*, code_version="2", test_version="1", requirement_version="1"):
    return (
        ProcessArtifact("requirements.search", PROCESS_ARTIFACT_REQUIREMENT, requirement_version),
        ProcessArtifact(
            "code.search",
            PROCESS_ARTIFACT_CODE,
            code_version,
            upstream_artifact_ids=("requirements.search",),
        ),
        ProcessArtifact("tests.search", PROCESS_ARTIFACT_TEST, test_version),
        ProcessArtifact("model.search", PROCESS_ARTIFACT_MODEL, "1"),
    )


def proof_artifact(artifact_id="artifact:unit", *covered):
    return ProofArtifactRef(
        artifact_id,
        result_status=PROCESS_EVIDENCE_PASSED,
        exit_code=0,
        result_path=f"tmp/{artifact_id.replace(':', '_')}.json",
        artifact_fingerprints={f"tmp/{artifact_id.replace(':', '_')}.json": "sha256:test"},
        covered_obligation_ids=covered,
    )


class DevelopmentProcessFlowTests(unittest.TestCase):
    def test_active_process_optimization_requires_current_typed_evidence(self):
        current = ProcessEvidence(
            "optimization:decision:v1",
            evidence_kind=PROCESS_EVIDENCE_PROCESS_OPTIMIZATION,
            status=PROCESS_EVIDENCE_PASSED,
            result_path="tmp/process-optimization.json",
        )
        plan = DevelopmentProcessPlan(
            "optimization-aware-process",
            evidence=(current,),
            process_optimization_reasons=("material_rework_risk",),
            required_process_optimization_evidence_ids=(current.evidence_id,),
        )
        current_report = review_development_process_flow(plan)
        self.assertTrue(current_report.ok)
        self.assertEqual("selected", current_report.process_optimization_status)

        stale = replace(current, status=PROCESS_EVIDENCE_FAILED)
        report = review_development_process_flow(replace(plan, evidence=(stale,)))
        self.assertIn(
            "process_optimization_evidence_not_current",
            {finding.code for finding in report.findings},
        )

        ordinary = review_development_process_flow(DevelopmentProcessPlan("ordinary-process"))
        self.assertTrue(ordinary.ok)
        self.assertEqual("not_needed", ordinary.process_optimization_status)

    def test_revalidation_selection_covers_all_requirements_before_cost_tie_breaking(self):
        evidence = (
            ProcessEvidence(
                "unit:a",
                evidence_kind="unit",
                status=PROCESS_EVIDENCE_FAILED,
                validation_requirement_ids=("req:a",),
                command="pytest a",
                revalidation_cost=0.75,
                revalidation_cost_basis="measured",
            ),
            ProcessEvidence(
                "unit:b",
                evidence_kind="unit",
                status=PROCESS_EVIDENCE_FAILED,
                validation_requirement_ids=("req:b",),
                command="pytest b",
                revalidation_cost=0.75,
                revalidation_cost_basis="measured",
            ),
            ProcessEvidence(
                "unit:combined",
                evidence_kind="unit",
                status=PROCESS_EVIDENCE_FAILED,
                validation_requirement_ids=("req:a", "req:b"),
                command="pytest a b",
                revalidation_cost=1.0,
                revalidation_cost_basis="measured",
            ),
        )
        requirements = (
            ValidationRequirement("req:a", required_evidence_kinds=("unit",)),
            ValidationRequirement("req:b", required_evidence_kinds=("unit",)),
        )
        report = review_development_process_flow(
            DevelopmentProcessPlan(
                "coverage-aware-revalidation",
                evidence=evidence,
                validation_requirements=requirements,
            )
        )
        self.assertEqual(1, len(report.revalidation_recommendations))
        recommendation = report.revalidation_recommendations[0]
        self.assertEqual("unit:combined", recommendation.evidence_id)
        self.assertEqual(("req:a", "req:b"), recommendation.covered_requirement_ids)
        self.assertIn("minimum measured-cost set cover", report.revalidation_optimality_boundary)

    def test_estimated_revalidation_cost_does_not_claim_a_minimum(self):
        evidence = (
            ProcessEvidence(
                "unit:focused",
                evidence_kind="unit",
                status=PROCESS_EVIDENCE_FAILED,
                validation_requirement_ids=("req:a",),
                command="pytest a",
                revalidation_cost=0.25,
                revalidation_cost_basis="estimated",
            ),
        )
        report = review_development_process_flow(
            DevelopmentProcessPlan(
                "estimated-revalidation",
                evidence=evidence,
                validation_requirements=(
                    ValidationRequirement("req:a", required_evidence_kinds=("unit",)),
                ),
            )
        )
        self.assertIn("coverage-complete preferred set", report.revalidation_optimality_boundary)
        self.assertNotIn("measured-cost", report.revalidation_optimality_boundary)

    def spec_process_plan(self):
        lifecycle = (
            "spec_provider_read",
            "spec_reconcile",
            "spec_session_begin",
            "spec_check",
            "spec_post_snapshot",
            "spec_provider_verify",
            "spec_sync",
            "spec_archive_ready",
        )
        actions = tuple(
            ProcessAction(
                f"spec:{index}:{action_type}",
                action_type=action_type,
                order_after=((f"spec:{index - 1}:{lifecycle[index - 1]}",) if index else ()),
            )
            for index, action_type in enumerate(lifecycle)
        )
        evidence = ProcessEvidence(
            "evidence:spec-check",
            status=PROCESS_EVIDENCE_PASSED,
            spec_work_package_id="change-one",
            spec_check_id="check.one",
            spec_session_id="session:one",
            spec_session_state="closed",
            spec_begin_fingerprint="sha256:inputs",
            spec_post_fingerprint="sha256:inputs",
            spec_close_record_path=".flowguard/evidence/spec-work-packages/sessions/history/one/close.json",
            spec_consumer_ids=("consumer:one",),
            spec_execution_state="executed",
            spec_receipt_id="receipt:one",
            spec_receipt_fingerprint="sha256:receipt",
            spec_provider_verified=True,
            spec_provider_archive_ready=True,
        )
        return DevelopmentProcessPlan(
            "spec-process",
            actions=actions,
            evidence=(evidence,),
            spec_work_package_ids=("openspec:change-one",),
            required_spec_session_ids=("session:one",),
            required_spec_receipt_ids=("receipt:one",),
            require_spec_session_close=True,
            require_spec_provider_close=True,
        )

    def test_spec_process_requires_same_session_close_and_terminal_receipt(self):
        plan = self.spec_process_plan()
        self.assertTrue(review_development_process_flow(plan).ok)

        stale_evidence = replace(plan.evidence[0], spec_post_fingerprint="sha256:peer-write")
        report = review_development_process_flow(replace(plan, evidence=(stale_evidence,)))
        codes = {finding.code for finding in report.findings}
        self.assertIn("required_spec_session_not_closed", codes)
        self.assertIn("spec_receipt_binding_incomplete", codes)
    def test_current_v_model_plan_is_green(self):
        plan = DevelopmentProcessPlan(
            "search-lifecycle",
            artifacts=base_artifacts(code_version="2"),
            actions=(
                ProcessAction("edit-code", writes_artifacts=("code.search",)),
                ProcessAction("run-unit", produced_evidence_ids=("unit-pass",)),
                ProcessAction(
                    "claim-done",
                    action_type="claim_done",
                    required_validation_ids=("unit-current",),
                ),
            ),
            evidence=(
                ProcessEvidence(
                    "unit-pass",
                    evidence_kind="unit",
                    status=PROCESS_EVIDENCE_PASSED,
                    covers_artifacts=("code.search",),
                    verifier_artifacts=("tests.search",),
                    covered_versions={"code.search": "2", "tests.search": "1"},
                    validation_requirement_ids=("unit-current",),
                    produced_by_action_id="run-unit",
                ),
            ),
            validation_requirements=(
                ValidationRequirement(
                    "unit-current",
                    required_artifact_ids=("code.search",),
                    required_evidence_kinds=("unit",),
                    v_model_pair=True,
                ),
            ),
        )

        report = review_development_process_flow(plan)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("development_process_flow_green_can_continue", report.decision)
        self.assertEqual([], report.to_dict()["findings"])
        self.assertIn("flowguard development process flow", report.format_text())

    def test_code_change_after_validation_requires_revalidation(self):
        plan = DevelopmentProcessPlan(
            "stale-code",
            artifacts=base_artifacts(code_version="2"),
            actions=(
                ProcessAction("run-unit", produced_evidence_ids=("unit-pass",)),
                ProcessAction("edit-code", writes_artifacts=("code.search",)),
                ProcessAction(
                    "claim-release",
                    action_type="claim_release",
                    required_evidence_ids=("unit-pass",),
                ),
            ),
            evidence=(
                ProcessEvidence(
                    "unit-pass",
                    evidence_kind="unit",
                    status=PROCESS_EVIDENCE_PASSED,
                    covers_artifacts=("code.search",),
                    covered_versions={"code.search": "1"},
                    produced_by_action_id="run-unit",
                ),
            ),
            validation_requirements=(
                ValidationRequirement(
                    "unit-current",
                    required_artifact_ids=("code.search",),
                    required_evidence_kinds=("unit",),
                    evidence_ids=("unit-pass",),
                ),
            ),
            decision_scope=PROCESS_SCOPE_RELEASE,
        )

        report = review_development_process_flow(plan)
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertIn("stale_evidence_after_artifact_change", codes)
        self.assertIn("release_claim_with_stale_evidence", codes)
        self.assertEqual("revalidation_required", report.decision)
        recommendations = derive_revalidation_plan(plan)
        self.assertEqual(("unit-current",), tuple(r.requirement_id for r in recommendations))
        self.assertEqual("unit-pass", recommendations[0].evidence_id)
        self.assertEqual("development_process_flow", recommendations[0].producer_route)
        self.assertIn("stale_evidence_after_artifact_change", recommendations[0].freshness_gap_codes)
        self.assertIn(PROCESS_SCOPE_RELEASE, recommendations[0].blocks_claim_scopes)

    def test_ui_lifecycle_evidence_cannot_be_running_for_done_claim(self):
        plan = DevelopmentProcessPlan(
            "ui-lifecycle",
            artifacts=(
                ProcessArtifact("ui.inventory", PROCESS_ARTIFACT_UI_OBSERVED_INVENTORY, "1"),
                ProcessArtifact("ui.chain", PROCESS_ARTIFACT_UI_FUNCTIONAL_CHAIN, "1"),
                ProcessArtifact("ui.source_baseline", PROCESS_ARTIFACT_UI_SOURCE_BASELINE_GATE, "1"),
                ProcessArtifact("ui.done", PROCESS_ARTIFACT_UI_DONE_CLAIM, "1"),
            ),
            actions=(
                ProcessAction("validate-ui", produced_evidence_ids=("ui-click-running",)),
                ProcessAction(
                    "claim-done",
                    action_type="claim_done",
                    required_validation_ids=("ui-implementation-current",),
                ),
            ),
            evidence=(
                ProcessEvidence(
                    "ui-click-running",
                    evidence_kind=PROCESS_EVIDENCE_UI_IMPLEMENTATION_VALIDATION,
                    status=PROCESS_EVIDENCE_RUNNING,
                    covers_artifacts=("ui.done",),
                    covered_versions={"ui.done": "1"},
                    validation_requirement_ids=("ui-implementation-current",),
                    produced_by_action_id="validate-ui",
                    background=True,
                    has_exit_artifact=False,
                    has_result_artifact=False,
                ),
                ProcessEvidence(
                    "ui-source-baseline-pass",
                    evidence_kind=PROCESS_EVIDENCE_UI_SOURCE_BASELINE_GATE,
                    status=PROCESS_EVIDENCE_PASSED,
                    covers_artifacts=("ui.source_baseline",),
                    covered_versions={"ui.source_baseline": "1"},
                ),
            ),
            validation_requirements=(
                ValidationRequirement(
                    "ui-implementation-current",
                    required_artifact_ids=("ui.done",),
                    required_evidence_kinds=(PROCESS_EVIDENCE_UI_IMPLEMENTATION_VALIDATION,),
                    evidence_ids=("ui-click-running",),
                ),
            ),
        )

        report = review_development_process_flow(plan)
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertIn("validation_evidence_not_current", codes)
        self.assertIn("progress_only_validation_claimed_complete", codes)
        self.assertIn("missing_required_revalidation", codes)

    def test_ui_human_operability_change_stales_operability_evidence(self):
        plan = DevelopmentProcessPlan(
            "ui-human-operability-lifecycle",
            artifacts=(ProcessArtifact("ui.human", PROCESS_ARTIFACT_UI_HUMAN_OPERABILITY, "2"),),
            actions=(
                ProcessAction("review-human-operability", produced_evidence_ids=("ui-human-pass",)),
                ProcessAction("edit-action-grammar", writes_artifacts=("ui.human",)),
                ProcessAction("claim-done", action_type="claim_done"),
            ),
            evidence=(
                ProcessEvidence(
                    "ui-human-pass",
                    evidence_kind=PROCESS_EVIDENCE_UI_HUMAN_OPERABILITY,
                    status=PROCESS_EVIDENCE_PASSED,
                    covers_artifacts=("ui.human",),
                    covered_versions={"ui.human": "1"},
                    produced_by_action_id="review-human-operability",
                ),
            ),
        )

        report = review_development_process_flow(plan)
        self.assertFalse(report.ok)
        self.assertIn("ui_human_operability_changed_after_evidence", {finding.code for finding in report.findings})

    def test_ui_functional_capability_change_stales_capability_evidence(self):
        plan = DevelopmentProcessPlan(
            "ui-capability-lifecycle",
            artifacts=(ProcessArtifact("ui.capabilities", PROCESS_ARTIFACT_UI_FUNCTIONAL_CAPABILITY_COVERAGE, "2"),),
            actions=(
                ProcessAction("review-capability-coverage", produced_evidence_ids=("ui-capability-pass",)),
                ProcessAction("edit-output-contract", writes_artifacts=("ui.capabilities",)),
                ProcessAction("claim-done", action_type="claim_done"),
            ),
            evidence=(
                ProcessEvidence(
                    "ui-capability-pass",
                    evidence_kind=PROCESS_EVIDENCE_UI_FUNCTIONAL_CAPABILITY_COVERAGE,
                    status=PROCESS_EVIDENCE_PASSED,
                    covers_artifacts=("ui.capabilities",),
                    covered_versions={"ui.capabilities": "1"},
                    produced_by_action_id="review-capability-coverage",
                ),
            ),
        )

        report = review_development_process_flow(plan)
        self.assertFalse(report.ok)
        self.assertIn("ui_functional_capability_coverage_changed_after_evidence", {finding.code for finding in report.findings})

    def test_test_verifier_change_after_test_pass_is_stale(self):
        plan = DevelopmentProcessPlan(
            "stale-tests",
            artifacts=base_artifacts(code_version="1", test_version="2"),
            actions=(
                ProcessAction("run-unit", produced_evidence_ids=("unit-pass",)),
                ProcessAction("edit-tests", writes_artifacts=("tests.search",)),
            ),
            evidence=(
                ProcessEvidence(
                    "unit-pass",
                    evidence_kind="unit",
                    status=PROCESS_EVIDENCE_PASSED,
                    covers_artifacts=("code.search",),
                    verifier_artifacts=("tests.search",),
                    covered_versions={"code.search": "1", "tests.search": "1"},
                    produced_by_action_id="run-unit",
                ),
            ),
            validation_requirements=(
                ValidationRequirement(
                    "unit-current",
                    required_artifact_ids=("code.search",),
                    required_evidence_kinds=("unit",),
                    evidence_ids=("unit-pass",),
                ),
            ),
        )

        report = review_development_process_flow(plan)

        self.assertFalse(report.ok)
        self.assertIn("test_changed_after_test_pass", {finding.code for finding in report.findings})

    def test_revalidation_recommendation_marks_required_proof_artifact(self):
        plan = DevelopmentProcessPlan(
            "proof-required-rerun",
            require_proof_artifacts=True,
            artifacts=base_artifacts(code_version="2"),
            evidence=(
                ProcessEvidence(
                    "unit-pass",
                    evidence_kind="unit",
                    status=PROCESS_EVIDENCE_PASSED,
                    covers_artifacts=("code.search",),
                    covered_versions={"code.search": "1"},
                    validation_requirement_ids=("unit-current",),
                    command="python -m unittest tests.test_search",
                ),
            ),
            validation_requirements=(
                ValidationRequirement(
                    "unit-current",
                    required_artifact_ids=("code.search",),
                    required_evidence_kinds=("unit",),
                    evidence_ids=("unit-pass",),
                    command="python -m unittest tests.test_search",
                ),
            ),
        )

        recommendation = derive_revalidation_plan(plan)[0]

        self.assertTrue(recommendation.proof_artifact_required)
        self.assertEqual(("stale_evidence_after_artifact_change",), recommendation.freshness_gap_codes)
        self.assertEqual(("code.search",), recommendation.artifact_ids)

    def test_model_change_after_alignment_pass_is_stale(self):
        plan = DevelopmentProcessPlan(
            "stale-alignment",
            artifacts=base_artifacts(),
            actions=(
                ProcessAction("run-alignment", produced_evidence_ids=("alignment-pass",)),
                ProcessAction("edit-model", writes_artifacts=("model.search",)),
            ),
            evidence=(
                ProcessEvidence(
                    "alignment-pass",
                    evidence_kind="model_test_alignment",
                    status=PROCESS_EVIDENCE_PASSED,
                    covers_artifacts=("model.search", "tests.search"),
                    covered_versions={"model.search": "0", "tests.search": "1"},
                    produced_by_action_id="run-alignment",
                ),
            ),
            validation_requirements=(
                ValidationRequirement(
                    "alignment-current",
                    required_artifact_ids=("model.search", "tests.search"),
                    required_evidence_kinds=("model_test_alignment",),
                    evidence_ids=("alignment-pass",),
                ),
            ),
        )

        report = review_development_process_flow(plan)

        self.assertFalse(report.ok)
        self.assertIn("model_changed_after_alignment_pass", {finding.code for finding in report.findings})

    def test_field_lifecycle_projection_replacement_and_bug_repair_changes_are_stale(self):
        plan = DevelopmentProcessPlan(
            "field-stale",
            artifacts=(
                ProcessArtifact("field.lifecycle", PROCESS_ARTIFACT_FIELD_LIFECYCLE, "2"),
                ProcessArtifact("field.projection", PROCESS_ARTIFACT_FIELD_PROJECTION, "2"),
                ProcessArtifact("replacement.disposition", PROCESS_ARTIFACT_REPLACEMENT_DISPOSITION, "2"),
                ProcessArtifact("bug.repair.closure", PROCESS_ARTIFACT_BUG_REPAIR_CLOSURE, "2"),
            ),
            evidence=(
                ProcessEvidence(
                    "field-lifecycle-pass",
                    evidence_kind=PROCESS_EVIDENCE_FIELD_LIFECYCLE,
                    status=PROCESS_EVIDENCE_PASSED,
                    covers_artifacts=("field.lifecycle",),
                    covered_versions={"field.lifecycle": "1"},
                ),
                ProcessEvidence(
                    "field-projection-pass",
                    evidence_kind=PROCESS_EVIDENCE_FIELD_PROJECTION,
                    status=PROCESS_EVIDENCE_PASSED,
                    covers_artifacts=("field.projection",),
                    covered_versions={"field.projection": "1"},
                ),
                ProcessEvidence(
                    "replacement-pass",
                    evidence_kind="flowguard_closure_contract",
                    status=PROCESS_EVIDENCE_PASSED,
                    covers_artifacts=("replacement.disposition",),
                    covered_versions={"replacement.disposition": "1"},
                ),
                ProcessEvidence(
                    "bug-repair-pass",
                    evidence_kind=PROCESS_EVIDENCE_MODEL_MISS_REVIEW,
                    status=PROCESS_EVIDENCE_PASSED,
                    covers_artifacts=("bug.repair.closure",),
                    covered_versions={"bug.repair.closure": "1"},
                ),
            ),
            validation_requirements=(
                ValidationRequirement(
                    "field-current",
                    required_artifact_ids=("field.lifecycle",),
                    required_evidence_kinds=(PROCESS_EVIDENCE_FIELD_LIFECYCLE,),
                    evidence_ids=("field-lifecycle-pass",),
                ),
                ValidationRequirement(
                    "projection-current",
                    required_artifact_ids=("field.projection",),
                    required_evidence_kinds=(PROCESS_EVIDENCE_FIELD_PROJECTION,),
                    evidence_ids=("field-projection-pass",),
                ),
                ValidationRequirement(
                    "replacement-current",
                    required_artifact_ids=("replacement.disposition",),
                    required_evidence_kinds=("flowguard_closure_contract",),
                    evidence_ids=("replacement-pass",),
                ),
                ValidationRequirement(
                    "bug-repair-current",
                    required_artifact_ids=("bug.repair.closure",),
                    required_evidence_kinds=(PROCESS_EVIDENCE_MODEL_MISS_REVIEW,),
                    evidence_ids=("bug-repair-pass",),
                ),
            ),
        )

        report = review_development_process_flow(plan)
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertIn("field_lifecycle_changed_after_field_evidence", codes)
        self.assertIn("field_projection_changed_after_alignment_pass", codes)
        self.assertIn("replacement_disposition_changed_after_closure_pass", codes)
        self.assertIn("bug_repair_closure_changed_after_review_pass", codes)
        self.assertEqual("revalidation_required", report.decision)

    def test_requirement_change_propagates_with_freshness_rule(self):
        plan = DevelopmentProcessPlan(
            "requirement-propagates",
            artifacts=base_artifacts(code_version="1", requirement_version="2"),
            actions=(
                ProcessAction("run-unit", produced_evidence_ids=("unit-pass",)),
                ProcessAction("edit-requirement", writes_artifacts=("requirements.search",)),
            ),
            evidence=(
                ProcessEvidence(
                    "unit-pass",
                    evidence_kind="unit",
                    status=PROCESS_EVIDENCE_PASSED,
                    covers_artifacts=("code.search",),
                    covered_versions={"code.search": "1"},
                    produced_by_action_id="run-unit",
                ),
            ),
            validation_requirements=(
                ValidationRequirement(
                    "unit-current",
                    required_artifact_ids=("code.search",),
                    required_evidence_kinds=("unit",),
                    evidence_ids=("unit-pass",),
                ),
            ),
            freshness_rules=(
                FreshnessRule(
                    "requirements-affect-code",
                    upstream_artifact_id="requirements.search",
                    invalidates_artifact_ids=("code.search",),
                ),
            ),
        )

        report = review_development_process_flow(plan)

        self.assertFalse(report.ok)
        self.assertIn(
            "requirement_change_without_downstream_revalidation",
            {finding.code for finding in report.findings},
        )

    def test_ambiguous_freshness_policy_is_visible(self):
        plan = DevelopmentProcessPlan(
            "ambiguous-policy",
            artifacts=base_artifacts(requirement_version="2"),
            actions=(ProcessAction("edit-requirement", writes_artifacts=("requirements.search",)),),
            validation_requirements=(
                ValidationRequirement(
                    "unit-current",
                    required_artifact_ids=("code.search",),
                    required_evidence_kinds=("unit",),
                ),
            ),
        )

        report = review_development_process_flow(plan)

        self.assertFalse(report.ok)
        self.assertIn("ambiguous_freshness_policy", {finding.code for finding in report.findings})

    def test_failed_progress_and_hidden_skip_evidence_do_not_support_claims(self):
        plan = DevelopmentProcessPlan(
            "bad-evidence",
            artifacts=base_artifacts(code_version="1"),
            evidence=(
                ProcessEvidence(
                    "failed",
                    evidence_kind="unit",
                    status=PROCESS_EVIDENCE_FAILED,
                    covers_artifacts=("code.search",),
                    covered_versions={"code.search": "1"},
                ),
                ProcessEvidence(
                    "progress",
                    evidence_kind="integration",
                    status=PROCESS_EVIDENCE_PASSED,
                    covers_artifacts=("code.search",),
                    covered_versions={"code.search": "1"},
                    background=True,
                    progress_only=True,
                    has_exit_artifact=False,
                    has_result_artifact=False,
                ),
                ProcessEvidence(
                    "hidden-skip",
                    evidence_kind="acceptance",
                    status=PROCESS_EVIDENCE_PASSED,
                    covers_artifacts=("requirements.search",),
                    covered_versions={"requirements.search": "1"},
                    skipped_count=1,
                    skipped_visible=False,
                ),
                ProcessEvidence(
                    "not-run",
                    evidence_kind="release",
                    status=PROCESS_EVIDENCE_NOT_RUN,
                    covers_artifacts=("code.search",),
                    covered_versions={"code.search": "1"},
                ),
            ),
        )

        report = review_development_process_flow(plan)
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertIn("failed_validation_claimed_current", codes)
        self.assertIn("progress_only_validation_claimed_complete", codes)
        self.assertIn("hidden_skipped_validation_claimed_pass", codes)
        self.assertIn("validation_evidence_not_current", codes)

    def test_release_only_requirement_can_defer_in_routine_but_blocks_release(self):
        requirement = ValidationRequirement(
            "release-current",
            required_artifact_ids=("code.search",),
            required_evidence_kinds=("release",),
            release_required=True,
            scope=PROCESS_SCOPE_RELEASE,
        )
        routine_plan = DevelopmentProcessPlan(
            "routine-release-deferred",
            artifacts=base_artifacts(code_version="1"),
            validation_requirements=(requirement,),
            decision_scope=PROCESS_SCOPE_ROUTINE,
        )
        release_plan = DevelopmentProcessPlan(
            "release-required",
            artifacts=base_artifacts(code_version="1"),
            validation_requirements=(requirement,),
            decision_scope=PROCESS_SCOPE_RELEASE,
        )

        routine_report = review_development_process_flow(routine_plan)
        release_report = review_development_process_flow(release_plan)

        self.assertTrue(routine_report.ok, routine_report.format_text())
        self.assertEqual(("release-current",), routine_report.release_obligations)
        self.assertFalse(release_report.ok)
        self.assertIn("release_evidence_not_current", {finding.code for finding in release_report.findings})

    def test_unknown_peer_write_is_a_blocker(self):
        plan = DevelopmentProcessPlan(
            "peer-write",
            artifacts=base_artifacts(code_version="2"),
            actions=(
                ProcessAction("run-unit", produced_evidence_ids=("unit-pass",)),
                ProcessAction("peer-edit", writes_artifacts=("code.search",), actor="peer-agent"),
            ),
            evidence=(
                ProcessEvidence(
                    "unit-pass",
                    evidence_kind="unit",
                    status=PROCESS_EVIDENCE_PASSED,
                    covers_artifacts=("code.search",),
                    covered_versions={"code.search": "1"},
                    produced_by_action_id="run-unit",
                ),
            ),
        )

        report = review_development_process_flow(plan)

        self.assertFalse(report.ok)
        self.assertIn("unknown_writer_invalidates_evidence", {finding.code for finding in report.findings})

    def test_process_evidence_rejects_auto_split_metrics(self):
        removed_field_sets = (
            {"observed_state_count": 20_000},
            {"duration_seconds": 301},
            {"covered_obligation_count": 8},
            {"auto_split_suggested_child_ids": ("unit", "integration")},
            {"auto_split_partition_item_ids": ("fast", "slow")},
        )

        for kwargs in removed_field_sets:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(TypeError):
                    ProcessEvidence(
                        "split-review-belongs-to-autosplit",
                        evidence_kind="test",
                        status=PROCESS_EVIDENCE_PASSED,
                        covers_artifacts=("code.search",),
                        covered_versions={"code.search": "2"},
                        **kwargs,
                    )

    def test_missing_v_model_validation_pair_is_distinct(self):
        plan = DevelopmentProcessPlan(
            "missing-v-pair",
            artifacts=base_artifacts(code_version="1"),
            validation_requirements=(
                ValidationRequirement(
                    "acceptance-current",
                    required_artifact_ids=("requirements.search", "code.search"),
                    required_evidence_kinds=("acceptance",),
                    v_model_pair=True,
                ),
            ),
        )

        report = review_development_process_flow(plan)

        self.assertFalse(report.ok)
        self.assertIn("missing_v_model_validation_pair", {finding.code for finding in report.findings})

    def test_strict_process_evidence_rejects_declaration_only_pass(self):
        plan = DevelopmentProcessPlan(
            "strict-process",
            require_proof_artifacts=True,
            artifacts=base_artifacts(code_version="1"),
            evidence=(
                ProcessEvidence(
                    "unit-pass",
                    evidence_kind="unit",
                    status=PROCESS_EVIDENCE_PASSED,
                    covers_artifacts=("code.search",),
                    covered_versions={"code.search": "1"},
                ),
            ),
        )

        report = review_development_process_flow(plan)

        self.assertFalse(report.ok)
        self.assertIn("missing_process_proof_artifact", {finding.code for finding in report.findings})

    def test_strict_process_evidence_accepts_artifact_backed_pass(self):
        plan = DevelopmentProcessPlan(
            "strict-process-green",
            require_proof_artifacts=True,
            artifacts=base_artifacts(code_version="1"),
            evidence=(
                ProcessEvidence(
                    "unit-pass",
                    evidence_kind="unit",
                    status=PROCESS_EVIDENCE_PASSED,
                    covers_artifacts=("code.search",),
                    covered_versions={"code.search": "1"},
                    result_path="tmp/unit.json",
                    proof_artifact=proof_artifact("artifact:unit"),
                ),
            ),
        )

        report = review_development_process_flow(plan)

        self.assertTrue(report.ok, report.format_text())

    def test_process_actions_reference_sibling_planes_without_becoming_their_owner(self):
        relation_ref = "commitment:process-validation|validates|commitment:product-download"
        good = DevelopmentProcessPlan(
            "plane-aware-process",
            actions=(
                ProcessAction(
                    "validate-product-download",
                    behavior_plane="development_process",
                    target_behavior_planes=("product_runtime",),
                    target_commitment_ids=("commitment:product-download",),
                    typed_commitment_relation_refs=(relation_ref,),
                ),
            ),
            behavior_plane="development_process",
            require_behavior_plane_boundary=True,
        )

        report = review_development_process_flow(good)
        self.assertTrue(report.ok, report.format_text())

        bad = DevelopmentProcessPlan(
            "mixed-owner-process",
            actions=(
                ProcessAction(
                    "validate-product-download",
                    behavior_plane="product_runtime",
                    target_behavior_planes=("product_runtime",),
                    target_commitment_ids=("commitment:product-download",),
                    typed_commitment_relation_refs=(relation_ref,),
                ),
            ),
            behavior_plane="development_process",
            require_behavior_plane_boundary=True,
        )
        bad_report = review_development_process_flow(bad)
        self.assertFalse(bad_report.ok)
        self.assertIn(
            "process_action_absorbs_target_behavior_plane",
            {finding.code for finding in bad_report.findings},
        )


if __name__ == "__main__":
    unittest.main()
