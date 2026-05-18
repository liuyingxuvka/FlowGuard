import unittest

from flowguard import (
    PROCESS_ARTIFACT_CODE,
    PROCESS_ARTIFACT_MODEL,
    PROCESS_ARTIFACT_REQUIREMENT,
    PROCESS_ARTIFACT_TEST,
    PROCESS_EVIDENCE_FAILED,
    PROCESS_EVIDENCE_NOT_RUN,
    PROCESS_EVIDENCE_PASSED,
    PROCESS_SCOPE_RELEASE,
    PROCESS_SCOPE_ROUTINE,
    DevelopmentProcessPlan,
    FreshnessRule,
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
        self.assertEqual(("unit-current",), tuple(r.requirement_id for r in derive_revalidation_plan(plan)))

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


if __name__ == "__main__":
    unittest.main()
