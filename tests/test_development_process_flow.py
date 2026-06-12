import unittest

from flowguard import (
    PROCESS_ARTIFACT_CODE,
    PROCESS_ARTIFACT_BUG_REPAIR_CLOSURE,
    PROCESS_ARTIFACT_FIELD_LIFECYCLE,
    PROCESS_ARTIFACT_FIELD_PROJECTION,
    PROCESS_ARTIFACT_MODEL,
    PROCESS_ARTIFACT_MATLAB_CALLBACK_GATE,
    PROCESS_ARTIFACT_REPLACEMENT_DISPOSITION,
    PROCESS_ARTIFACT_REQUIREMENT,
    PROCESS_ARTIFACT_TEST,
    PROCESS_ARTIFACT_UI_DONE_CLAIM,
    PROCESS_ARTIFACT_UI_FUNCTIONAL_CHAIN,
    PROCESS_ARTIFACT_UI_OBSERVED_INVENTORY,
    PROCESS_EVIDENCE_BUG_REPAIR_CLOSURE,
    PROCESS_EVIDENCE_FIELD_LIFECYCLE,
    PROCESS_EVIDENCE_FIELD_PROJECTION,
    PROCESS_EVIDENCE_FAILED,
    PROCESS_EVIDENCE_MATLAB_CALLBACK_GATE,
    PROCESS_EVIDENCE_MODEL_MISS_REVIEW,
    PROCESS_EVIDENCE_NOT_RUN,
    PROCESS_EVIDENCE_PASSED,
    PROCESS_EVIDENCE_RUNNING,
    PROCESS_EVIDENCE_UI_IMPLEMENTATION_VALIDATION,
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
                ProcessArtifact("ui.matlab", PROCESS_ARTIFACT_MATLAB_CALLBACK_GATE, "1"),
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
                    "ui-callback-pass",
                    evidence_kind=PROCESS_EVIDENCE_MATLAB_CALLBACK_GATE,
                    status=PROCESS_EVIDENCE_PASSED,
                    covers_artifacts=("ui.matlab",),
                    covered_versions={"ui.matlab": "1"},
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


if __name__ == "__main__":
    unittest.main()
