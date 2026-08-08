import unittest

from flowguard import (
    UI_MODEL_MISS_AFFORDANCE_MISMATCH,
    UI_MODEL_MISS_BOUNDARY_MISSING,
    UI_MODEL_MISS_EVIDENCE_OVERCLAIMED,
    UI_MODEL_MISS_PROMISED_CAPABILITY_TYPES,
    UIModelMissRecord,
    UIModelMissReviewPlan,
    review_ui_model_misses,
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


class ModelMissReviewTests(unittest.TestCase):
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

    def test_missing_promised_ui_capability_can_close_with_capability_scope(self):
        report = review_ui_model_misses(
            UIModelMissReviewPlan(
                "ui-capability-miss-plan",
                ui_misses=(
                    ui_miss(
                        miss_type=UI_MODEL_MISS_BOUNDARY_MISSING,
                        missing_promised_capability_ids=("capability:plot-result",),
                        affected_capability_ids=("capability:plot-result",),
                        affected_control_ids=(),
                        same_class_capability_ids=("capability:load-result", "capability:export-result"),
                        same_class_control_ids=(),
                        required_test_ids=("test:plot-result-visible",),
                        required_implementation_evidence_ids=("evidence:plot-click-visible-result",),
                        code_owner="ui.plot_result",
                    ),
                ),
            )
        )

        self.assertTrue(report.ok, report.summary)
        self.assertIn(UI_MODEL_MISS_BOUNDARY_MISSING, UI_MODEL_MISS_PROMISED_CAPABILITY_TYPES)
        self.assertIn(UI_MODEL_MISS_EVIDENCE_OVERCLAIMED, UI_MODEL_MISS_PROMISED_CAPABILITY_TYPES)

    def test_missing_promised_ui_capability_rejects_wrong_classification(self):
        report = review_ui_model_misses(
            UIModelMissReviewPlan(
                "ui-capability-miss-plan",
                ui_misses=(
                    ui_miss(
                        miss_type=UI_MODEL_MISS_AFFORDANCE_MISMATCH,
                        missing_promised_capability_ids=("capability:plot-result",),
                        affected_capability_ids=("capability:load-result",),
                        affected_control_ids=(),
                        same_class_capability_ids=("capability:load-result",),
                        same_class_control_ids=(),
                    ),
                ),
            )
        )

        codes = set(finding_codes(report))
        self.assertFalse(report.ok)
        self.assertIn("ui_model_miss_missing_capability_not_affected", codes)
        self.assertIn("ui_model_miss_missing_capability_misclassified", codes)

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
        self.assertIn("ui_model_miss_missing_same_class_scope", codes)
        self.assertIn("ui_model_miss_missing_same_class_evidence", codes)
        self.assertIn("ui_model_miss_missing_backpropagation", codes)
        self.assertIn("ui_model_miss_missing_code_owner", codes)


if __name__ == "__main__":
    unittest.main()
