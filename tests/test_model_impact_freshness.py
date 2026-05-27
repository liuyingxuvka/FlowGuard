import unittest

from flowguard import (
    MODEL_FRESHNESS_DECISION_AFFECTED_RERUN_REQUIRED,
    MODEL_FRESHNESS_DECISION_CURRENT,
    MODEL_FRESHNESS_DECISION_REUSE_INVALID,
    MODEL_FRESHNESS_DECISION_UNKNOWN,
    MODEL_IMPACT_AFFECTED,
    MODEL_IMPACT_DEPRECATED,
    MODEL_IMPACT_NOT_IMPACTED,
    MODEL_RERUN_STATUS_PASSED,
    ModelFreshnessRecord,
    ModelImpactAssessment,
    ModelImpactFreshnessPlan,
    ModelReuseTicket,
    ModelRerunEvidence,
    UpgradeImpact,
    review_model_impact_freshness,
)


def codes(report):
    return {finding.code for finding in report.findings}


class ModelImpactFreshnessTests(unittest.TestCase):
    def test_affected_reuse_and_deprecated_paths_pass_with_explicit_evidence(self):
        report = review_model_impact_freshness(
            ModelImpactFreshnessPlan(
                "upgrade-024",
                records=(
                    ModelFreshnessRecord(
                        "plan-intake",
                        ".flowguard/plan_intake/model.py",
                        dependency_artifact_ids=("flowguard.plan_intake",),
                        previous_evidence_id="plan-intake-prev",
                    ),
                    ModelFreshnessRecord(
                        "release-visibility",
                        ".flowguard/release_visibility_process/model.py",
                        dependency_artifact_ids=("flowguard.release",),
                        previous_evidence_id="release-prev",
                    ),
                    ModelFreshnessRecord(
                        "old-visibility",
                        ".flowguard/model_visibility/model.py",
                        replacement_model_id="release-visibility",
                    ),
                ),
                impact=UpgradeImpact(
                    "upgrade-024",
                    changed_artifact_ids=("flowguard.plan_intake",),
                    changed_flowguard_semantic_ids=("claim-boundary",),
                ),
                assessments=(
                    ModelImpactAssessment(
                        "plan-intake",
                        MODEL_IMPACT_AFFECTED,
                        rationale="plan-intake helper changed its claim boundary",
                    ),
                    ModelImpactAssessment(
                        "release-visibility",
                        MODEL_IMPACT_NOT_IMPACTED,
                        rationale="release model dependencies and output fingerprint are unchanged",
                    ),
                    ModelImpactAssessment(
                        "old-visibility",
                        MODEL_IMPACT_DEPRECATED,
                        rationale="superseded by release-visibility",
                        replacement_model_id="release-visibility",
                    ),
                ),
                reuse_tickets=(
                    ModelReuseTicket(
                        "release-visibility",
                        reason="same dependency fingerprint and same output",
                        previous_evidence_id="release-prev",
                        same_output_proof_id="release-same-output",
                    ),
                ),
                rerun_evidence=(
                    ModelRerunEvidence(
                        "plan-intake",
                        status=MODEL_RERUN_STATUS_PASSED,
                        current=True,
                        evidence_id="plan-intake-rerun",
                        command="python .flowguard/plan_intake/run_checks.py",
                        model_update_reviewed=True,
                        model_updated=True,
                        test_update_reviewed=True,
                        tests_updated=True,
                    ),
                ),
            )
        )

        self.assertTrue(report.ok)
        self.assertEqual(MODEL_FRESHNESS_DECISION_CURRENT, report.decision)
        self.assertEqual(("plan-intake",), report.rerun_model_ids)
        self.assertEqual(("release-visibility",), report.reused_model_ids)
        self.assertEqual(("old-visibility",), report.deprecated_model_ids)

    def test_affected_model_requires_current_rerun_evidence(self):
        report = review_model_impact_freshness(
            ModelImpactFreshnessPlan(
                "upgrade",
                records=(ModelFreshnessRecord("checkout", dependency_artifact_ids=("flowguard.core",)),),
                impact=UpgradeImpact("upgrade", changed_artifact_ids=("flowguard.core",)),
                assessments=(
                    ModelImpactAssessment("checkout", MODEL_IMPACT_AFFECTED, rationale="core semantics changed"),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(MODEL_FRESHNESS_DECISION_AFFECTED_RERUN_REQUIRED, report.decision)
        self.assertIn("affected_model_rerun_missing", codes(report))

    def test_not_impacted_model_requires_reuse_ticket(self):
        report = review_model_impact_freshness(
            ModelImpactFreshnessPlan(
                "upgrade",
                records=(ModelFreshnessRecord("checkout", previous_evidence_id="checkout-prev"),),
                assessments=(
                    ModelImpactAssessment("checkout", MODEL_IMPACT_NOT_IMPACTED, rationale="not touched"),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(MODEL_FRESHNESS_DECISION_REUSE_INVALID, report.decision)
        self.assertIn("model_reuse_ticket_missing", codes(report))

    def test_directly_touched_model_cannot_reuse_without_same_output_proof(self):
        report = review_model_impact_freshness(
            ModelImpactFreshnessPlan(
                "upgrade",
                records=(
                    ModelFreshnessRecord(
                        "checkout",
                        dependency_artifact_ids=("flowguard.runner",),
                        previous_evidence_id="checkout-prev",
                    ),
                ),
                impact=UpgradeImpact("upgrade", changed_artifact_ids=("flowguard.runner",)),
                assessments=(
                    ModelImpactAssessment("checkout", MODEL_IMPACT_NOT_IMPACTED, rationale="runner change bypasses this model"),
                ),
                reuse_tickets=(
                    ModelReuseTicket(
                        "checkout",
                        reason="dependency still produces same reachable graph",
                        previous_evidence_id="checkout-prev",
                        same_output_proof_id="",
                        output_fingerprint="",
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(MODEL_FRESHNESS_DECISION_REUSE_INVALID, report.decision)
        self.assertIn("same_output_proof_missing", codes(report))

    def test_directly_touched_model_can_reuse_with_explicit_same_output_ticket(self):
        report = review_model_impact_freshness(
            ModelImpactFreshnessPlan(
                "upgrade",
                records=(
                    ModelFreshnessRecord(
                        "checkout",
                        dependency_artifact_ids=("flowguard.runner",),
                        previous_evidence_id="checkout-prev",
                    ),
                ),
                impact=UpgradeImpact("upgrade", changed_artifact_ids=("flowguard.runner",)),
                assessments=(
                    ModelImpactAssessment("checkout", MODEL_IMPACT_NOT_IMPACTED, rationale="same reachable graph"),
                ),
                reuse_tickets=(
                    ModelReuseTicket(
                        "checkout",
                        reason="reran fingerprint comparison and reachable graph is unchanged",
                        previous_evidence_id="checkout-prev",
                        same_output_proof_id="checkout-graph-compare",
                    ),
                ),
            )
        )

        self.assertTrue(report.ok)
        self.assertEqual(MODEL_FRESHNESS_DECISION_CURRENT, report.decision)

    def test_missing_classification_blocks_before_claiming_freshness(self):
        report = review_model_impact_freshness(
            ModelImpactFreshnessPlan(
                "upgrade",
                records=(ModelFreshnessRecord("checkout"),),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(MODEL_FRESHNESS_DECISION_UNKNOWN, report.decision)
        self.assertIn("model_impact_classification_missing", codes(report))

    def test_affected_model_records_update_review_even_when_no_file_change_is_needed(self):
        report = review_model_impact_freshness(
            ModelImpactFreshnessPlan(
                "upgrade",
                records=(ModelFreshnessRecord("checkout"),),
                assessments=(ModelImpactAssessment("checkout", MODEL_IMPACT_AFFECTED, rationale="schema touched"),),
                rerun_evidence=(
                    ModelRerunEvidence(
                        "checkout",
                        status=MODEL_RERUN_STATUS_PASSED,
                        current=True,
                        evidence_id="checkout-rerun",
                        model_update_reviewed=True,
                        model_update_not_required_reason="model already used the new schema-neutral boundary",
                        test_update_reviewed=True,
                        test_update_not_required_reason="existing test still covers the unchanged trace",
                    ),
                ),
            )
        )

        self.assertTrue(report.ok)
        self.assertEqual(MODEL_FRESHNESS_DECISION_CURRENT, report.decision)


if __name__ == "__main__":
    unittest.main()
