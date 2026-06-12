import unittest

from flowguard import (
    DEFECT_FAMILY_DECISION_FULL,
    DEFECT_FAMILY_DECISION_SCOPED,
    RISK_CONFIDENCE_BLOCKED,
    RISK_CONFIDENCE_FULL,
    RISK_CONFIDENCE_SCOPED,
    RISK_PROOF_SCOPE_INTERNAL_PATH,
    RISK_PROOF_STATUS_PASSED,
    RISK_PROOF_STATUS_PROGRESS_ONLY,
    DefectFamilyEvidence,
    DefectFamilyGate,
    DefectFamilyGatePlan,
    LEGACY_PATH_DELEGATED,
    LEGACY_PATH_KIND_FIELD,
    LegacyPathDisposition,
    ProofArtifactRef,
    UI_MODEL_MISS_BOUNDARY_MISSING,
    UI_MODEL_MISS_EVIDENCE_OVERCLAIMED,
    UI_MODEL_MISS_AFFORDANCE_MISMATCH,
    UIModelMissRecord,
    UIModelMissReviewPlan,
    review_defect_family_gates,
    review_ui_model_misses,
)


def proof(evidence_id="proof:family", **kwargs):
    return DefectFamilyEvidence(
        evidence_id,
        result_status=kwargs.pop("result_status", RISK_PROOF_STATUS_PASSED),
        **kwargs,
    )


def proof_artifact(artifact_id="artifact:family", *covered):
    return ProofArtifactRef(
        artifact_id,
        result_status=RISK_PROOF_STATUS_PASSED,
        exit_code=0,
        result_path=f"tmp/{artifact_id.replace(':', '_')}.json",
        artifact_fingerprints={f"tmp/{artifact_id.replace(':', '_')}.json": "sha256:test"},
        covered_obligation_ids=covered or ("model:duplicate-submit-family",),
    )


def promoted_gate(**kwargs):
    return DefectFamilyGate(
        "duplicate-submit-family",
        recurrence_count=kwargs.pop("recurrence_count", 2),
        promoted=kwargs.pop("promoted", True),
        model_obligation_id=kwargs.pop("model_obligation_id", "model:duplicate-submit-family"),
        authority_boundary=kwargs.pop("authority_boundary", "public submit API"),
        observed_failure_case_id=kwargs.pop("observed_failure_case_id", "observed:flowpilot-openstack-1"),
        same_class_generalized_case_id=kwargs.pop("same_class_generalized_case_id", "same-class:submit-retry"),
        historical_holdout_case_id=kwargs.pop("historical_holdout_case_id", "holdout:flowpilot-openstack-2"),
        proof_evidence_ids=kwargs.pop("proof_evidence_ids", ("proof:family",)),
        **kwargs,
    )


def plan(*, gates=None, proof_evidence=None, **kwargs):
    return DefectFamilyGatePlan(
        "recurring-miss-plan",
        gates=tuple(gates if gates is not None else (promoted_gate(),)),
        proof_evidence=tuple(proof_evidence if proof_evidence is not None else (proof(),)),
        **kwargs,
    )


def finding_codes(report):
    return [finding.code for finding in report.findings]


def ui_miss(**kwargs):
    return UIModelMissRecord(
        "ui-miss:load-table",
        previous_claim_id=kwargs.pop("previous_claim_id", "claim:ui-green"),
        previous_green_reason=kwargs.pop("previous_green_reason", "API existed and label matched"),
        observed_failure=kwargs.pop("observed_failure", "Load table button did not update the table"),
        observed_failure_evidence_ref=kwargs.pop("observed_failure_evidence_ref", "manual:2026-06-12"),
        miss_type=kwargs.pop("miss_type", UI_MODEL_MISS_EVIDENCE_OVERCLAIMED),
        affected_control_ids=kwargs.pop("affected_control_ids", ("control:load-table",)),
        same_class_control_ids=kwargs.pop(
            "same_class_control_ids",
            ("control:select", "control:open-txt", "control:load-file"),
        ),
        required_test_ids=kwargs.pop("required_test_ids", ("test:load-table-click",)),
        required_implementation_evidence_ids=kwargs.pop(
            "required_implementation_evidence_ids",
            ("evidence:load-table-click",),
        ),
        root_cause_backpropagation=kwargs.pop(
            "root_cause_backpropagation",
            "add functional-chain and visible-state-update obligations",
        ),
        code_owner=kwargs.pop("code_owner", "ui.load_table"),
        rationale=kwargs.pop("rationale", "user observed escaped UI behavior after green model"),
        **kwargs,
    )


class RecurringModelMissTests(unittest.TestCase):
    def test_single_ordinary_miss_does_not_require_defect_family_gate(self):
        report = review_defect_family_gates(
            plan(
                gates=(
                    DefectFamilyGate(
                        "single-ordinary-miss",
                        recurrence_count=1,
                        promoted=False,
                    ),
                ),
                proof_evidence=(),
            )
        )

        self.assertTrue(report.ok)
        self.assertEqual(DEFECT_FAMILY_DECISION_FULL, report.decision)
        self.assertEqual(RISK_CONFIDENCE_FULL, report.confidence)

    def test_recurring_miss_without_promotion_blocks_full_confidence(self):
        report = review_defect_family_gates(
            plan(gates=(DefectFamilyGate("repeat-family", recurrence_count=2, promoted=False),))
        )

        self.assertFalse(report.ok)
        self.assertEqual(RISK_CONFIDENCE_BLOCKED, report.confidence)
        self.assertEqual("recurring_miss_not_promoted", report.decision)
        self.assertIn("recurring_miss_not_promoted", finding_codes(report))

    def test_promoted_family_with_current_external_proof_passes(self):
        report = review_defect_family_gates(plan())

        self.assertTrue(report.ok)
        self.assertEqual(DEFECT_FAMILY_DECISION_FULL, report.decision)
        self.assertIn("status: OK", report.format_text())
        self.assertIn("duplicate-submit-family", report.passed_gate_ids)

    def test_promoted_family_requires_same_class_and_historical_holdout_cases(self):
        report = review_defect_family_gates(
            plan(
                gates=(
                    promoted_gate(
                        same_class_generalized_case_id="",
                        historical_holdout_case_id="",
                    ),
                )
            )
        )

        codes = finding_codes(report)
        self.assertFalse(report.ok)
        self.assertIn("missing_same_class_generalized_case", codes)
        self.assertIn("missing_historical_holdout_case", codes)

    def test_field_root_cause_requires_same_class_field_case(self):
        report = review_defect_family_gates(
            plan(
                gates=(
                    promoted_gate(
                        root_cause_field_ids=("field:mode",),
                        same_class_field_ids=(),
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_same_class_field_case", finding_codes(report))

    def test_old_field_in_model_miss_requires_field_disposition_when_strict(self):
        report = review_defect_family_gates(
            plan(
                require_legacy_path_dispositions=True,
                gates=(
                    promoted_gate(
                        root_cause_field_ids=("field:mode",),
                        same_class_field_ids=("field:mode:legacy-empty",),
                        old_field_ids=("field:old_mode",),
                        legacy_path_dispositions=(),
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_old_field_disposition", finding_codes(report))

    def test_field_model_miss_with_old_field_disposition_can_pass(self):
        report = review_defect_family_gates(
            plan(
                require_legacy_path_dispositions=True,
                gates=(
                    promoted_gate(
                        root_cause_field_ids=("field:mode",),
                        same_class_field_ids=("field:mode:legacy-empty",),
                        old_field_ids=("field:old_mode",),
                        legacy_path_dispositions=(
                            LegacyPathDisposition(
                                "field:old_mode",
                                disposition=LEGACY_PATH_DELEGATED,
                                path_kind=LEGACY_PATH_KIND_FIELD,
                                field_id="field:old_mode",
                                replacement_field_id="field:mode",
                                repaired_contract_id="model:duplicate-submit-family",
                            ),
                        ),
                    ),
                ),
            )
        )

        self.assertTrue(report.ok, report.format_text())

    def test_progress_only_and_internal_only_proof_do_not_satisfy_family_gate(self):
        progress_report = review_defect_family_gates(
            plan(proof_evidence=(proof(result_status=RISK_PROOF_STATUS_PROGRESS_ONLY),))
        )
        self.assertFalse(progress_report.ok)
        self.assertIn("defect_family_proof_not_passing", finding_codes(progress_report))
        self.assertIn("missing_current_defect_family_proof", finding_codes(progress_report))

        internal_report = review_defect_family_gates(
            plan(proof_evidence=(proof(assertion_scope=RISK_PROOF_SCOPE_INTERNAL_PATH),))
        )
        self.assertFalse(internal_report.ok)
        self.assertIn("defect_family_proof_internal_path_only", finding_codes(internal_report))

    def test_scoped_family_gate_downgrades_without_blocking_when_allowed(self):
        report = review_defect_family_gates(
            plan(gates=(promoted_gate(scoped_confidence_reasons=("release-only holdout deferred",)),))
        )

        self.assertTrue(report.ok)
        self.assertEqual(DEFECT_FAMILY_DECISION_SCOPED, report.decision)
        self.assertEqual(RISK_CONFIDENCE_SCOPED, report.confidence)
        self.assertIn("defect_family_scoped_confidence", finding_codes(report))

    def test_strict_defect_family_rejects_declaration_only_proof(self):
        report = review_defect_family_gates(plan(require_proof_artifacts=True))

        self.assertFalse(report.ok)
        self.assertIn("missing_defect_family_proof_artifact", finding_codes(report))

    def test_strict_defect_family_requires_legacy_path_disposition(self):
        report = review_defect_family_gates(
            plan(
                require_proof_artifacts=True,
                require_legacy_path_dispositions=True,
                gates=(
                    promoted_gate(
                        legacy_path_dispositions=(
                            LegacyPathDisposition(
                                "old-route",
                                disposition=LEGACY_PATH_DELEGATED,
                                repaired_contract_id="model:duplicate-submit-family",
                                proof_artifact=proof_artifact("artifact:legacy"),
                            ),
                        ),
                    ),
                ),
                proof_evidence=(proof(proof_artifact=proof_artifact()),),
            )
        )

        self.assertTrue(report.ok, report.format_text())

    def test_user_observed_ui_failure_is_a_model_miss_with_same_class_closure(self):
        report = review_ui_model_misses(
            UIModelMissReviewPlan("ui-miss-plan", ui_misses=(ui_miss(),))
        )

        self.assertTrue(report.ok, report.summary)
        self.assertEqual(0, report.blocker_count())

    def test_human_operability_confusion_is_a_ui_model_miss_type(self):
        report = review_ui_model_misses(
            UIModelMissReviewPlan(
                "ui-affordance-miss-plan",
                ui_misses=(ui_miss(miss_type=UI_MODEL_MISS_AFFORDANCE_MISMATCH),),
            )
        )

        self.assertTrue(report.ok, report.summary)

    def test_ui_model_miss_rejects_local_button_only_fix(self):
        report = review_ui_model_misses(
            UIModelMissReviewPlan(
                "ui-miss-plan",
                ui_misses=(
                    ui_miss(
                        previous_claim_id="",
                        previous_green_reason="",
                        miss_type=UI_MODEL_MISS_BOUNDARY_MISSING,
                        same_class_control_ids=(),
                        required_test_ids=(),
                        required_implementation_evidence_ids=(),
                        root_cause_backpropagation="",
                        code_owner="",
                    ),
                ),
            )
        )

        codes = set(finding_codes(report))
        self.assertFalse(report.ok)
        self.assertIn("ui_model_miss_missing_previous_claim", codes)
        self.assertIn("ui_model_miss_missing_previous_green_reason", codes)
        self.assertIn("ui_model_miss_missing_same_class_scan", codes)
        self.assertIn("ui_model_miss_missing_same_class_evidence", codes)
        self.assertIn("ui_model_miss_missing_backpropagation", codes)
        self.assertIn("ui_model_miss_missing_code_owner", codes)


if __name__ == "__main__":
    unittest.main()
