import unittest

from flowguard import (
    RELATION_EVIDENCE_DUPLICATE,
    RELATION_FALSE_FRIEND,
    RELATION_SAME_FAMILY_VARIANT,
    RELATION_SHARED_KERNEL,
    RELATION_UNRELATED,
    ModelSignature,
    ModelSimilarityEvidence,
    ModelSimilarityPlan,
    review_model_similarity_consolidation,
)


def signature(model_id: str, **kwargs) -> ModelSignature:
    defaults = {
        "workflow_family": "checkout",
        "function_blocks": ("ValidateOrder", "PersistOrder"),
        "state_owned": ("orders",),
        "side_effects_owned": ("write_order",),
        "failure_modes": ("duplicate_submit",),
        "evidence_ids": ("sim:checkout",),
    }
    defaults.update(kwargs)
    return ModelSignature(model_id, **defaults)


class ModelSimilarityReviewTests(unittest.TestCase):
    def test_family_variant_with_current_evidence_is_ready(self):
        plan = ModelSimilarityPlan(
            "family-variant",
            signatures=(
                signature("checkout-simple", variant_id="simple"),
                signature("checkout-retry", variant_id="retry"),
            ),
            comparison_pairs=(("checkout-simple", "checkout-retry"),),
            evidence=(ModelSimilarityEvidence("sim:checkout"),),
            require_current_evidence=True,
        )

        report = review_model_similarity_consolidation(plan)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("model_similarity_ready", report.decision)
        self.assertEqual(RELATION_SAME_FAMILY_VARIANT, report.relations[0].relation_type)
        self.assertIn("model_mesh", report.recommended_next_routes)
        self.assertIn("model_test_alignment", report.recommended_next_routes)

    def test_missing_required_current_evidence_blocks(self):
        plan = ModelSimilarityPlan(
            "missing-evidence",
            signatures=(
                signature("checkout-simple", variant_id="simple", evidence_ids=()),
                signature("checkout-retry", variant_id="retry", evidence_ids=()),
            ),
            comparison_pairs=(("checkout-simple", "checkout-retry"),),
            require_current_evidence=True,
        )

        report = review_model_similarity_consolidation(plan)

        self.assertFalse(report.ok)
        self.assertEqual("model_similarity_blocked", report.decision)
        self.assertIn("missing_current_similarity_evidence", {finding.code for finding in report.findings})
        self.assertEqual("scoped", report.relations[0].confidence)

    def test_false_friend_keeps_boundaries_separate(self):
        plan = ModelSimilarityPlan(
            "false-friend",
            signatures=(
                ModelSignature(
                    "cache-refresh",
                    function_blocks=("RefreshCache",),
                    state_owned=("cache_entries",),
                    side_effects_owned=("write_cache",),
                    failure_modes=("stale_cache",),
                    false_friend_model_ids=("cache-report",),
                ),
                ModelSignature(
                    "cache-report",
                    function_blocks=("RenderReport",),
                    state_owned=("report_rows",),
                    side_effects_owned=("write_report",),
                    failure_modes=("missing_report_row",),
                ),
            ),
            comparison_pairs=(("cache-refresh", "cache-report"),),
        )

        report = review_model_similarity_consolidation(plan)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(RELATION_FALSE_FRIEND, report.relations[0].relation_type)
        self.assertEqual("keep_separate", report.relations[0].recommendation)
        self.assertEqual("blocked", report.relations[0].confidence)

    def test_shared_kernel_routes_to_structure_recommendation(self):
        plan = ModelSimilarityPlan(
            "shared-kernel",
            signatures=(
                ModelSignature(
                    "billing-import",
                    function_blocks=("NormalizeInvoice", "ValidateInvoice"),
                    invariants=("invoice_has_source",),
                    failure_modes=("invalid_invoice",),
                ),
                ModelSignature(
                    "billing-api",
                    function_blocks=("NormalizeInvoice", "ValidateInvoice"),
                    invariants=("invoice_has_source",),
                    failure_modes=("invalid_invoice",),
                ),
            ),
            comparison_pairs=(("billing-import", "billing-api"),),
        )

        report = review_model_similarity_consolidation(plan)

        self.assertTrue(report.ok, report.format_text())
        self.assertIn(report.relations[0].relation_type, {RELATION_SHARED_KERNEL, "adapter_only_difference"})
        self.assertIn("code_structure_recommendation", report.recommended_next_routes)

    def test_evidence_duplicate_relation_routes_to_alignment(self):
        plan = ModelSimilarityPlan(
            "evidence-duplicate",
            signatures=(
                ModelSignature("a", function_blocks=("A",), evidence_ids=("test:shared",)),
                ModelSignature("b", function_blocks=("B",), evidence_ids=("test:shared",)),
            ),
            comparison_pairs=(("a", "b"),),
            evidence=(ModelSimilarityEvidence("test:shared"),),
        )

        report = review_model_similarity_consolidation(plan)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(RELATION_EVIDENCE_DUPLICATE, report.relations[0].relation_type)
        self.assertIn("model_test_alignment", report.recommended_next_routes)

    def test_unrelated_relation_has_no_route(self):
        plan = ModelSimilarityPlan(
            "unrelated",
            signatures=(
                ModelSignature("a", function_blocks=("A",)),
                ModelSignature("b", function_blocks=("B",)),
            ),
            comparison_pairs=(("a", "b"),),
        )

        report = review_model_similarity_consolidation(plan)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(RELATION_UNRELATED, report.relations[0].relation_type)
        self.assertEqual((), report.recommended_next_routes)

    def test_incomplete_signature_blocks(self):
        report = review_model_similarity_consolidation(
            ModelSimilarityPlan("incomplete", signatures=(ModelSignature("empty"),))
        )

        self.assertFalse(report.ok)
        self.assertIn("incomplete_model_signature", {finding.code for finding in report.findings})

    def test_family_variants_form_maintenance_group_and_change_impact(self):
        plan = ModelSimilarityPlan(
            "checkout-maintenance",
            signatures=(
                signature(
                    "checkout-simple",
                    variant_id="simple",
                    code_paths=("flowguard/checkout/simple.py",),
                    test_paths=("tests/test_checkout_simple.py",),
                    owned_public_behaviors=("submit_order",),
                    shared_kernel_id="checkout_core",
                    adapter_ids=("simple_adapter",),
                    maintenance_tags=("checkout", "order-write"),
                ),
                signature(
                    "checkout-retry",
                    variant_id="retry",
                    code_paths=("flowguard/checkout/retry.py",),
                    test_paths=("tests/test_checkout_retry.py",),
                    owned_public_behaviors=("submit_order", "retry_order"),
                    shared_kernel_id="checkout_core",
                    adapter_ids=("retry_adapter",),
                    maintenance_tags=("checkout", "order-write"),
                ),
                signature(
                    "checkout-cancel",
                    variant_id="cancel",
                    code_paths=("flowguard/checkout/cancel.py",),
                    test_paths=("tests/test_checkout_cancel.py",),
                    owned_public_behaviors=("cancel_order",),
                    shared_kernel_id="checkout_core",
                    adapter_ids=("cancel_adapter",),
                    maintenance_tags=("checkout", "order-write"),
                ),
            ),
            changed_model_ids=("checkout-simple",),
        )

        report = review_model_similarity_consolidation(plan)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(1, len(report.maintenance_groups), report.format_text())
        group = report.maintenance_groups[0]
        self.assertEqual(
            ("checkout-cancel", "checkout-retry", "checkout-simple"),
            tuple(sorted(group.member_model_ids)),
        )
        self.assertIn("ValidateOrder", group.shared_elements)
        self.assertIn("flowguard/checkout/retry.py", group.code_paths)
        self.assertIn("tests/test_checkout_cancel.py", group.test_paths)
        self.assertEqual(1, len(report.change_impacts), report.format_text())
        impact = report.change_impacts[0]
        self.assertEqual("checkout-simple", impact.changed_model_id)
        self.assertEqual(("checkout-cancel", "checkout-retry"), tuple(sorted(impact.impacted_model_ids)))
        self.assertIn("flowguard/checkout/cancel.py", impact.impacted_code_paths)
        obligation_types = {obligation.obligation_type for obligation in report.test_obligations}
        self.assertIn("shared_behavior_tests", obligation_types)
        self.assertIn("variant_behavior_tests", obligation_types)
        code_obligation_types = {obligation.obligation_type for obligation in report.code_obligations}
        self.assertIn("shared_kernel_or_adapter", code_obligation_types)

    def test_changed_code_path_maps_to_similarity_sibling_review(self):
        report = review_model_similarity_consolidation(
            ModelSimilarityPlan(
                "changed-code-path",
                signatures=(
                    signature(
                        "checkout-simple",
                        variant_id="simple",
                        code_paths=("flowguard/checkout/simple.py",),
                        test_paths=("tests/test_checkout_simple.py",),
                    ),
                    signature(
                        "checkout-retry",
                        variant_id="retry",
                        code_paths=("flowguard/checkout/retry.py",),
                        test_paths=("tests/test_checkout_retry.py",),
                    ),
                ),
                changed_code_paths=("flowguard/checkout/simple.py",),
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("checkout-simple", report.change_impacts[0].changed_model_id)
        self.assertEqual(("checkout-retry",), report.change_impacts[0].impacted_model_ids)

    def test_false_friend_is_quarantined_from_maintenance_group(self):
        report = review_model_similarity_consolidation(
            ModelSimilarityPlan(
                "false-friend-quarantine",
                signatures=(
                    ModelSignature(
                        "checkout-submit",
                        function_blocks=("SubmitOrder",),
                        state_owned=("orders",),
                        side_effects_owned=("write_order",),
                        false_friend_model_ids=("checkout-report",),
                        code_paths=("flowguard/checkout/submit.py",),
                    ),
                    ModelSignature(
                        "checkout-report",
                        function_blocks=("RenderCheckoutReport",),
                        state_owned=("report_rows",),
                        side_effects_owned=("write_report",),
                        code_paths=("flowguard/checkout/report.py",),
                    ),
                ),
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual((), report.maintenance_groups)
        self.assertIn(
            "false_friend_quarantine",
            {obligation.obligation_type for obligation in report.code_obligations},
        )

    def test_required_maintenance_test_paths_block_missing_sibling_tests(self):
        report = review_model_similarity_consolidation(
            ModelSimilarityPlan(
                "missing-sibling-test-paths",
                signatures=(
                    signature(
                        "checkout-simple",
                        variant_id="simple",
                        test_paths=("tests/test_checkout_simple.py",),
                    ),
                    signature("checkout-retry", variant_id="retry", test_paths=()),
                ),
                require_maintenance_test_paths=True,
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_maintenance_test_path", {finding.code for finding in report.findings})


if __name__ == "__main__":
    unittest.main()
