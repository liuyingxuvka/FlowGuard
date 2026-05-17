import unittest

from flowguard import (
    ModelObligation,
    ModelTestAlignmentPlan,
    TestEvidence,
    TEST_KIND_FAILURE_PATH,
    TEST_KIND_HAPPY_PATH,
    review_model_test_alignment,
)


def obligation(obligation_id, **kwargs):
    defaults = {"required_test_kinds": (TEST_KIND_HAPPY_PATH,)}
    defaults.update(kwargs)
    return ModelObligation(obligation_id, **defaults)


def evidence(evidence_id, *covered, **kwargs):
    defaults = {
        "result_status": "passed",
        "evidence_current": True,
        "test_kind": TEST_KIND_HAPPY_PATH,
        "covered_obligations": tuple(covered),
    }
    defaults.update(kwargs)
    return TestEvidence(evidence_id, **defaults)


class ModelTestAlignmentTests(unittest.TestCase):
    def test_complete_alignment_can_continue(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(
                obligation("accept_valid_order"),
                obligation("reject_duplicate_order"),
            ),
            test_evidence=(
                evidence("test_accept_valid_order", "accept_valid_order"),
                evidence("test_reject_duplicate_order", "reject_duplicate_order"),
            ),
        )

        report = review_model_test_alignment(plan)

        self.assertTrue(report.ok)
        self.assertEqual("model_test_alignment_green", report.decision)
        self.assertEqual([], report.to_dict()["findings"])
        self.assertIn("flowguard model-test alignment", report.format_text())

    def test_missing_test_evidence_blocks_green(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(obligation("reject_duplicate_order"),),
            test_evidence=(),
        )

        report = review_model_test_alignment(plan)

        self.assertFalse(report.ok)
        self.assertEqual("missing_test_evidence", report.decision)
        self.assertIn("missing_test_evidence", [finding.code for finding in report.findings])

    def test_orphan_and_unknown_test_evidence_are_visible(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(obligation("accept_valid_order"),),
            test_evidence=(
                evidence("test_unbound"),
                evidence("test_unknown", "unknown_obligation"),
                evidence("test_accept_valid_order", "accept_valid_order"),
            ),
        )

        report = review_model_test_alignment(plan)
        codes = [finding.code for finding in report.findings]

        self.assertFalse(report.ok)
        self.assertEqual("orphan_test_evidence", report.decision)
        self.assertIn("orphan_test_evidence", codes)
        self.assertIn("unknown_obligation_reference", codes)

    def test_duplicate_same_kind_claims_block_unless_shared(self):
        blocked = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(obligation("accept_valid_order"),),
            test_evidence=(
                evidence("test_accept_a", "accept_valid_order"),
                evidence("test_accept_b", "accept_valid_order"),
            ),
        )
        allowed = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(obligation("accept_valid_order", allow_shared_evidence=True),),
            test_evidence=blocked.test_evidence,
        )

        blocked_report = review_model_test_alignment(blocked)
        allowed_report = review_model_test_alignment(allowed)

        self.assertFalse(blocked_report.ok)
        self.assertEqual("duplicate_test_evidence_owner", blocked_report.decision)
        self.assertTrue(allowed_report.ok)

    def test_stale_or_non_passing_evidence_is_not_current_coverage(self):
        cases = (
            evidence("stale_pass", "reject_duplicate_order", evidence_current=False),
            evidence("skipped", "reject_duplicate_order", result_status="skipped"),
            evidence("failed", "reject_duplicate_order", result_status="failed"),
            evidence("timeout", "reject_duplicate_order", result_status="timeout"),
            evidence("not_run", "reject_duplicate_order", result_status="not_run"),
        )
        for item in cases:
            with self.subTest(item=item.evidence_id):
                plan = ModelTestAlignmentPlan(
                    model_id="checkout",
                    obligations=(obligation("reject_duplicate_order"),),
                    test_evidence=(item,),
                )

                report = review_model_test_alignment(plan)
                codes = [finding.code for finding in report.findings]

                self.assertFalse(report.ok)
                self.assertIn("missing_test_evidence", codes)

    def test_required_failure_path_cannot_be_replaced_by_happy_path_only(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(
                obligation(
                    "reject_duplicate_order",
                    required_test_kinds=(TEST_KIND_HAPPY_PATH, TEST_KIND_FAILURE_PATH),
                ),
            ),
            test_evidence=(evidence("test_duplicate_happy", "reject_duplicate_order"),),
        )

        report = review_model_test_alignment(plan)

        self.assertFalse(report.ok)
        self.assertEqual("missing_required_test_kind", report.decision)
        self.assertIn("missing_required_test_kind", [finding.code for finding in report.findings])

    def test_distinct_required_kinds_are_not_duplicate_ownership(self):
        plan = ModelTestAlignmentPlan(
            model_id="checkout",
            obligations=(
                obligation(
                    "reject_duplicate_order",
                    required_test_kinds=(TEST_KIND_HAPPY_PATH, TEST_KIND_FAILURE_PATH),
                ),
            ),
            test_evidence=(
                evidence("test_duplicate_happy", "reject_duplicate_order"),
                evidence(
                    "test_duplicate_failure",
                    "reject_duplicate_order",
                    test_kind=TEST_KIND_FAILURE_PATH,
                ),
            ),
        )

        report = review_model_test_alignment(plan)

        self.assertTrue(report.ok)


if __name__ == "__main__":
    unittest.main()
