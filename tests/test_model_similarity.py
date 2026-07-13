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
    RELATION_DUPLICATE_BOUNDARY,
    SimilarityHandoff,
    model_signature_maintenance,
    model_signature_minimal,
    model_similarity_plan_for_changed_member,
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
    def test_minimal_signature_helper_builds_full_signature(self):
        built = model_signature_minimal(
            "checkout-simple",
            workflow_family="checkout",
            variant_id="simple",
            function_blocks=("ValidateOrder",),
            state_owned=("orders",),
            evidence_ids=("sim:checkout",),
        )

        self.assertIsInstance(built, ModelSignature)
        self.assertEqual("checkout-simple", built.model_id)
        self.assertEqual(("ValidateOrder",), built.function_blocks)
        self.assertEqual(("sim:checkout",), built.evidence_ids)

    def test_maintenance_plan_helper_and_report_handoff(self):
        left = model_signature_maintenance(
            "checkout-simple",
            workflow_family="checkout",
            variant_id="simple",
            function_blocks=("ValidateOrder",),
            code_paths=("flowguard/checkout/simple.py",),
            test_paths=("tests/test_checkout_simple.py",),
            shared_kernel_id="checkout_core",
            adapter_ids=("simple_adapter",),
        )
        right = model_signature_maintenance(
            "checkout-retry",
            workflow_family="checkout",
            variant_id="retry",
            function_blocks=("ValidateOrder",),
            code_paths=("flowguard/checkout/retry.py",),
            test_paths=("tests/test_checkout_retry.py",),
            shared_kernel_id="checkout_core",
            adapter_ids=("retry_adapter",),
        )
        plan = model_similarity_plan_for_changed_member(
            "checkout-handoff",
            (left, right),
            changed_model_id="checkout-simple",
        )

        report = review_model_similarity_consolidation(plan)
        handoff = report.to_handoff()

        self.assertIsInstance(handoff, SimilarityHandoff)
        self.assertTrue(handoff.relation_ids)
        self.assertEqual(("checkout-retry",), handoff.impacted_model_ids)
        self.assertTrue(handoff.maintenance_group_ids)
        self.assertTrue(handoff.test_obligation_ids)
        self.assertTrue(handoff.code_obligation_ids)

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

    def test_cross_plane_shared_language_is_quarantined_with_typed_context(self):
        typed_ref = "commitment:agent-download|invokes|commitment:product-download"
        report = review_model_similarity_consolidation(
            ModelSimilarityPlan(
                "cross-plane-download",
                signatures=(
                    signature(
                        "product-download",
                        behavior_plane="product_runtime",
                        typed_commitment_relation_refs=(typed_ref,),
                    ),
                    signature(
                        "agent-download",
                        behavior_plane="agent_operation",
                        typed_commitment_relation_refs=(typed_ref,),
                    ),
                ),
                comparison_pairs=(("product-download", "agent-download"),),
                evidence=(
                    ModelSimilarityEvidence(
                        "evidence:cross-plane-download",
                        relation_id="product-download:agent-download:false_friend",
                        compared_behavior_planes=("product_runtime", "agent_operation"),
                        typed_commitment_relation_refs=(typed_ref,),
                    ),
                ),
                require_behavior_plane_identity=True,
            )
        )

        self.assertTrue(report.ok, report.format_text())
        relation = report.relations[0]
        self.assertEqual(RELATION_FALSE_FRIEND, relation.relation_type)
        self.assertEqual("keep_separate", relation.recommendation)
        self.assertEqual("product_runtime", relation.left_behavior_plane)
        self.assertEqual("agent_operation", relation.right_behavior_plane)
        self.assertEqual((typed_ref,), relation.typed_commitment_relation_refs)
        self.assertIn("behavior_plane_conflict", {item.code for item in report.findings})
        self.assertEqual((), report.maintenance_groups)
        handoff = report.to_handoff()
        self.assertEqual({"product_runtime", "agent_operation"}, set(handoff.behavior_planes))
        self.assertEqual((typed_ref,), handoff.typed_commitment_relation_refs)
        self.assertEqual((relation.relation_id,), handoff.cross_plane_relation_ids)

    def test_plane_aware_similarity_requires_every_signature_identity(self):
        report = review_model_similarity_consolidation(
            ModelSimilarityPlan(
                "missing-plane",
                signatures=(
                    signature("product-download", behavior_plane="product_runtime"),
                    signature("unclassified-download"),
                ),
                require_behavior_plane_identity=True,
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_behavior_plane_identity", {item.code for item in report.findings})

    def test_similarity_evidence_must_bind_the_compared_planes(self):
        report = review_model_similarity_consolidation(
            ModelSimilarityPlan(
                "plane-evidence-mismatch",
                signatures=(
                    signature("checkout-a", behavior_plane="product_runtime"),
                    signature("checkout-b", behavior_plane="product_runtime"),
                ),
                comparison_pairs=(("checkout-a", "checkout-b"),),
                evidence=(
                    ModelSimilarityEvidence(
                        "evidence:wrong-plane",
                        relation_id="checkout-a:checkout-b:same_workflow",
                        compared_behavior_planes=("agent_operation",),
                    ),
                ),
                require_behavior_plane_identity=True,
            )
        )

        self.assertFalse(report.ok)
        self.assertIn(
            "similarity_evidence_behavior_plane_mismatch",
            {item.code for item in report.findings},
        )

    def test_shared_business_path_marks_duplicate_boundary(self):
        report = review_model_similarity_consolidation(
            ModelSimilarityPlan(
                "business-path-duplicate",
                signatures=(
                    ModelSignature(
                        "web-submit",
                        function_blocks=("SubmitFromWeb",),
                        state_owned=("order_status",),
                        side_effects_owned=("write_order",),
                        business_path_ids=("submit_order",),
                        business_intents=("submit order",),
                        path_terminals=("accepted",),
                    ),
                    ModelSignature(
                        "cli-submit",
                        function_blocks=("SubmitFromCli",),
                        state_owned=("order_status",),
                        side_effects_owned=("write_order",),
                        business_path_ids=("submit_order",),
                        business_intents=("submit order",),
                        path_terminals=("accepted",),
                    ),
                ),
                comparison_pairs=(("web-submit", "cli-submit"),),
            )
        )

        relation = report.relations[0]
        self.assertEqual(RELATION_DUPLICATE_BOUNDARY, relation.relation_type)
        self.assertIn("business_path:submit_order", relation.matched_elements)

    def test_business_terminal_divergence_marks_false_friend(self):
        report = review_model_similarity_consolidation(
            ModelSimilarityPlan(
                "business-path-false-friend",
                signatures=(
                    ModelSignature(
                        "submit-accepted",
                        business_intents=("submit order",),
                        path_terminals=("accepted",),
                        state_owned=("order_status",),
                    ),
                    ModelSignature(
                        "submit-rejected",
                        business_intents=("submit order",),
                        path_terminals=("rejected",),
                        state_owned=("order_status",),
                    ),
                ),
                comparison_pairs=(("submit-accepted", "submit-rejected"),),
            )
        )

        self.assertEqual(RELATION_FALSE_FRIEND, report.relations[0].relation_type)

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

    def test_stable_exact_intent_handoff_materializes_surface_test_and_code_obligations(self):
        shared = {
            "function_blocks": ("SubmitOrder",),
            "state_owned": ("orders",),
            "side_effects_owned": ("write_order",),
            "business_intent_ids": ("intent:submit-order",),
            "behavior_commitment_ids": ("commitment:submit-order",),
            "primary_path_ids": ("path:submit-order",),
            "path_terminals": ("accepted_or_visible_error",),
        }
        report = review_model_similarity_consolidation(
            ModelSimilarityPlan(
                "stable-exact-intent",
                signatures=(
                    ModelSignature(
                        "submit-ui",
                        public_surface_ids=("surface:ui-submit",),
                        test_paths=("tests/test_submit_ui.py",),
                        **shared,
                    ),
                    ModelSignature(
                        "submit-api",
                        public_surface_ids=("surface:api-submit",),
                        test_paths=("tests/test_submit_api.py",),
                        **shared,
                    ),
                ),
                expected_surface_ids=("surface:ui-submit", "surface:api-submit"),
                surface_inventory_revision="submit-order-surfaces:v1",
                require_complete_surface_inventory=True,
                require_stable_authority_identity=True,
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(RELATION_DUPLICATE_BOUNDARY, report.relations[0].relation_type)
        handoff = report.to_handoff()
        self.assertTrue(handoff.test_obligations)
        self.assertTrue(handoff.code_obligations)
        self.assertEqual(("intent:submit-order",), handoff.business_intent_ids)
        self.assertEqual(
            {"surface:ui-submit", "surface:api-submit"},
            set(handoff.affected_surface_ids),
        )
        self.assertTrue(all(item.surface_ids for item in handoff.test_obligations))

    def test_complete_similarity_inventory_blocks_omitted_same_intent_surface(self):
        report = review_model_similarity_consolidation(
            ModelSimilarityPlan(
                "missing-stable-surface",
                signatures=(
                    ModelSignature(
                        "submit-ui",
                        business_intent_ids=("intent:submit-order",),
                        behavior_commitment_ids=("commitment:submit-order",),
                        primary_path_ids=("path:submit-order",),
                        public_surface_ids=("surface:ui-submit",),
                    ),
                ),
                expected_surface_ids=("surface:ui-submit", "surface:api-submit"),
                surface_inventory_revision="submit-order-surfaces:v1",
                require_complete_surface_inventory=True,
                require_stable_authority_identity=True,
            )
        )

        self.assertFalse(report.ok)
        self.assertIn(
            "missing_expected_similarity_surface",
            {finding.code for finding in report.findings},
        )

    def test_maintenance_helpers_preserve_stable_authority_and_surface_inventory(self):
        common = {
            "workflow_family": "submit-order",
            "behavior_plane": "product_runtime",
            "function_blocks": ("SubmitOrder",),
            "business_path_ids": ("submit-order",),
            "business_intents": ("submit order",),
            "business_intent_ids": ("intent:submit-order",),
            "behavior_commitment_ids": ("commitment:submit-order",),
            "primary_path_ids": ("path:submit-order",),
            "evidence_ids": ("sim:submit-order",),
        }
        signatures = (
            model_signature_maintenance(
                "submit-ui",
                variant_id="ui",
                code_paths=("submit/ui.py",),
                test_paths=("tests/test_submit_ui.py",),
                public_surface_ids=("surface:ui-submit",),
                **common,
            ),
            model_signature_maintenance(
                "submit-api",
                variant_id="api",
                code_paths=("submit/api.py",),
                test_paths=("tests/test_submit_api.py",),
                public_surface_ids=("surface:api-submit",),
                **common,
            ),
        )
        plan = model_similarity_plan_for_changed_member(
            "submit-order-helper-plan",
            signatures,
            changed_model_id="submit-ui",
            evidence=(
                ModelSimilarityEvidence(
                    "sim:submit-order",
                    summary="current family review",
                    compared_behavior_planes=("product_runtime",),
                ),
            ),
            expected_surface_ids=("surface:ui-submit", "surface:api-submit"),
            surface_inventory_revision="submit-order-surfaces:v1",
            require_complete_surface_inventory=True,
            require_stable_authority_identity=True,
            require_behavior_plane_identity=True,
            require_current_evidence=True,
        )

        report = review_model_similarity_consolidation(plan)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(("intent:submit-order",), signatures[0].business_intent_ids)
        self.assertEqual(("surface:api-submit",), signatures[1].public_surface_ids)
        self.assertEqual("submit-order-surfaces:v1", plan.surface_inventory_revision)


if __name__ == "__main__":
    unittest.main()
