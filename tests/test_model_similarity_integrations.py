import unittest

from flowguard import (
    CANDIDATE_COLLAPSE_ADAPTER,
    PROOF_SAFE_BY_EQUIVALENCE,
    REUSE_DECISION_EXTEND_EXISTING,
    ROUTE_CODE_STRUCTURE_RECOMMENDATION,
    ROUTE_STRUCTURE_MESH,
    TARGET_ACTION_COLLAPSE,
    ArchitectureReductionCandidate,
    ArchitectureReductionPlan,
    CodeContract,
    CodeStructureRecommendation,
    ExistingModelPreflight,
    ExistingOwnershipSnapshot,
    ModelContextHit,
    ModelObligation,
    ModelTestAlignmentPlan,
    ObservableArchitectureContract,
    ObligationFamily,
    ObligationFamilyEvidence,
    ObligationFamilyMember,
    SimilarityHandoff,
    TargetModuleRecommendation,
    TestEvidence,
    review_architecture_reduction,
    review_code_structure_recommendation,
    review_existing_model_preflight,
    review_model_test_alignment,
)


class ModelSimilarityIntegrationTests(unittest.TestCase):
    def test_existing_preflight_requires_declared_similarity_evidence(self):
        preflight = ExistingModelPreflight(
            "similarity-required",
            "Add checkout retry model",
            mode="full",
            model_search_performed=True,
            search_paths=(".flowguard/checkout",),
            relevant_models=(
                ModelContextHit(
                    "checkout-simple",
                    function_blocks=("ValidateOrder",),
                    state_owned=("orders",),
                ),
            ),
            ownership_snapshot=ExistingOwnershipSnapshot(
                function_block_owners=(("ValidateOrder", "checkout-simple"),),
                state_owners=(("orders", "checkout-simple"),),
            ),
            reuse_decision=REUSE_DECISION_EXTEND_EXISTING,
            downstream_routes=("development_process_flow",),
            rationale="The retry variant extends the existing checkout model.",
            similarity_review_required=True,
        )

        report = review_existing_model_preflight(preflight)

        self.assertFalse(report.ok)
        self.assertIn("missing_similarity_evidence", {finding.code for finding in report.findings})

    def test_existing_preflight_accepts_current_similarity_relation(self):
        preflight = ExistingModelPreflight(
            "similarity-current",
            "Add checkout retry model",
            mode="full",
            model_search_performed=True,
            search_paths=(".flowguard/checkout",),
            relevant_models=(
                ModelContextHit(
                    "checkout-simple",
                    function_blocks=("ValidateOrder",),
                    state_owned=("orders",),
                ),
            ),
            ownership_snapshot=ExistingOwnershipSnapshot(
                function_block_owners=(("ValidateOrder", "checkout-simple"),),
                state_owners=(("orders", "checkout-simple"),),
            ),
            reuse_decision=REUSE_DECISION_EXTEND_EXISTING,
            downstream_routes=("development_process_flow",),
            rationale="The retry variant extends the existing checkout model.",
            similarity_review_required=True,
            similarity_handoff=SimilarityHandoff(
                relation_ids=("checkout-simple:checkout-retry:same_family_variant",),
                maintenance_group_ids=("maintenance:checkout-retry+checkout-simple",),
            ),
        )

        report = review_existing_model_preflight(preflight)

        self.assertTrue(report.ok, report.format_text())

    def test_existing_preflight_requires_change_impact_for_impacted_sibling_models(self):
        report = review_existing_model_preflight(
            ExistingModelPreflight(
                "similarity-change-impact",
                "Change checkout validation",
                mode="full",
                model_search_performed=True,
                search_paths=(".flowguard/checkout",),
                relevant_models=(ModelContextHit("checkout-simple", function_blocks=("ValidateOrder",)),),
                reuse_decision=REUSE_DECISION_EXTEND_EXISTING,
                downstream_routes=("development_process_flow",),
                rationale="Changing one checkout variant requires sibling review.",
                similarity_review_required=True,
                similarity_handoff=SimilarityHandoff(
                    relation_ids=("checkout-simple:checkout-retry:same_family_variant",),
                    maintenance_group_ids=("maintenance:checkout-retry+checkout-simple",),
                    impacted_model_ids=("checkout-retry",),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_similarity_change_impact", {finding.code for finding in report.findings})

    def test_architecture_reduction_similarity_is_not_proof_by_itself(self):
        plan = ArchitectureReductionPlan(
            "similarity-reduction",
            observable_contract=ObservableArchitectureContract(
                source_model_id="checkout",
                source_code_boundary_id="checkout.handlers",
                public_entrypoints=("checkout.submit",),
                observable_outputs=("OrderStored",),
                validation_boundaries=("model similarity review",),
                rationale="Keep checkout public behavior stable.",
            ),
            rationale="Collapse adapter after similarity review.",
            candidates=(
                ArchitectureReductionCandidate(
                    "collapse-retry-adapter",
                    candidate_type=CANDIDATE_COLLAPSE_ADAPTER,
                    code_node_id="checkout.retry_adapter",
                    source_model_element="checkout-simple:checkout-retry:adapter_only_difference",
                    target_action=TARGET_ACTION_COLLAPSE,
                    proof_status=PROOF_SAFE_BY_EQUIVALENCE,
                    required_next_route=ROUTE_CODE_STRUCTURE_RECOMMENDATION,
                    rationale="The relation says adapter-only difference, but this row cites no contraction evidence.",
                    similarity_handoff=SimilarityHandoff(
                        relation_ids=("checkout-simple:checkout-retry:adapter_only_difference",),
                    ),
                ),
            ),
        )

        report = review_architecture_reduction(plan)

        self.assertFalse(report.ok)
        self.assertIn(
            "similarity_relation_without_candidate_evidence",
            {finding.code for finding in report.findings},
        )

    def test_code_structure_accepts_similarity_shared_kernel_modules(self):
        report = review_code_structure_recommendation(
            CodeStructureRecommendation(
                "checkout-structure",
                source_model_id="checkout-family",
                parent_module_id="checkout",
                target_modules=(
                    TargetModuleRecommendation("core", owns_function_blocks=("ValidateOrder",), rationale="shared kernel"),
                    TargetModuleRecommendation("retry_adapter", rationale="variant adapter"),
                ),
                function_block_map=(("ValidateOrder", "core"),),
                facade_module_id="core",
                similarity_handoff=SimilarityHandoff(
                    relation_ids=("checkout-simple:checkout-retry:shared_kernel_candidate",),
                    maintenance_group_ids=("maintenance:checkout-retry+checkout-simple",),
                    code_obligation_ids=("checkout-simple:checkout-retry:shared_kernel_candidate:shared-kernel",),
                ),
                shared_kernel_module_id="core",
                variant_adapter_module_ids=("retry_adapter",),
                validation_boundaries=("model similarity review",),
                rationale="Shared kernel is derived from model similarity.",
            )
        )

        self.assertTrue(report.ok, report.format_text())

    def test_code_structure_warns_when_maintenance_group_lacks_code_obligation(self):
        report = review_code_structure_recommendation(
            CodeStructureRecommendation(
                "missing-code-obligation",
                source_model_id="checkout-family",
                parent_module_id="checkout",
                target_modules=(
                    TargetModuleRecommendation("core", owns_function_blocks=("ValidateOrder",), rationale="shared kernel"),
                    TargetModuleRecommendation("retry_adapter", rationale="variant adapter"),
                ),
                function_block_map=(("ValidateOrder", "core"),),
                facade_module_id="core",
                similarity_handoff=SimilarityHandoff(
                    relation_ids=("checkout-simple:checkout-retry:shared_kernel_candidate",),
                    maintenance_group_ids=("maintenance:checkout-retry+checkout-simple",),
                ),
                shared_kernel_module_id="core",
                variant_adapter_module_ids=("retry_adapter",),
                validation_boundaries=("model similarity review",),
                rationale="Shared kernel is derived from model similarity.",
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertIn("missing_similarity_code_obligation", {finding.code for finding in report.findings})

    def test_code_structure_blocks_false_friend_relation(self):
        report = review_code_structure_recommendation(
            CodeStructureRecommendation(
                "false-friend-structure",
                source_model_id="cache",
                parent_module_id="cache",
                target_modules=(TargetModuleRecommendation("shared", rationale="bad shared module"),),
                function_block_map=(("RefreshCache", "shared"),),
                similarity_handoff=SimilarityHandoff(
                    relation_ids=("cache-refresh:cache-report:false_friend",),
                ),
                shared_kernel_module_id="shared",
                validation_boundaries=("manual review",),
                rationale="False friend should not drive shared module.",
            )
        )

        self.assertFalse(report.ok)
        self.assertIn(
            "false_friend_similarity_blocks_shared_structure",
            {finding.code for finding in report.findings},
        )

    def test_model_test_alignment_requires_family_rows_for_similarity_family_claim(self):
        report = review_model_test_alignment(
            ModelTestAlignmentPlan(
                "checkout",
                similarity_handoff=SimilarityHandoff(
                    relation_ids=("checkout-simple:checkout-retry:same_family_variant",),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_similarity_family_evidence", {finding.code for finding in report.findings})

    def test_model_test_alignment_requires_similarity_test_obligations_for_maintenance_group(self):
        report = review_model_test_alignment(
            ModelTestAlignmentPlan(
                "checkout",
                similarity_handoff=SimilarityHandoff(
                    maintenance_group_ids=("maintenance:checkout-retry+checkout-simple",),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_similarity_test_obligations", {finding.code for finding in report.findings})

    def test_model_test_alignment_accepts_similarity_test_obligations(self):
        test_obligation_ids = (
            "maintenance:checkout-retry+checkout-simple:shared-tests",
            "maintenance:checkout-retry+checkout-simple:variant-tests",
        )
        obligation_id = "checkout-maintenance-tests"
        contract_id = "checkout.maintenance-tests"
        report = review_model_test_alignment(
            ModelTestAlignmentPlan(
                "checkout",
                obligations=(
                    ModelObligation(
                        obligation_id,
                        required_test_kinds=("happy_path",),
                        similarity_test_obligation_ids=test_obligation_ids,
                    ),
                ),
                code_contracts=(
                    CodeContract(
                        contract_id,
                        path="checkout/tests_contract.py",
                        symbol="CheckoutMaintenanceTests.run",
                        implements_obligations=(obligation_id,),
                    ),
                ),
                test_evidence=(
                    TestEvidence(
                        "test-checkout-maintenance-family",
                        result_status="passed",
                        covered_obligations=(obligation_id,),
                        covered_code_contracts=(contract_id,),
                    ),
                ),
                similarity_handoff=SimilarityHandoff(
                    maintenance_group_ids=("maintenance:checkout-retry+checkout-simple",),
                    test_obligation_ids=test_obligation_ids,
                ),
            )
        )

        self.assertTrue(report.ok, report.format_text())

    def test_model_test_alignment_accepts_family_rows_for_similarity_family_claim(self):
        relation_id = "checkout-simple:checkout-retry:same_family_variant"
        obligation_id = "checkout-family:simple:dedupe"
        contract_id = "checkout.simple-dedupe"
        report = review_model_test_alignment(
            ModelTestAlignmentPlan(
                "checkout",
                obligations=(
                    ModelObligation(
                        obligation_id,
                        required_test_kinds=("happy_path",),
                        similarity_relation_ids=(relation_id,),
                    ),
                ),
                code_contracts=(
                    CodeContract(
                        contract_id,
                        path="checkout/simple.py",
                        symbol="SimpleCheckout.dedupe",
                        implements_obligations=(obligation_id,),
                        similarity_relation_ids=(relation_id,),
                    ),
                ),
                test_evidence=(
                    TestEvidence(
                        "test-simple-dedupe",
                        result_status="passed",
                        covered_obligations=(obligation_id,),
                        covered_code_contracts=(contract_id,),
                    ),
                ),
                obligation_families=(
                    ObligationFamily(
                        "checkout-family",
                        members=(
                            ObligationFamilyMember(
                                "simple",
                                obligation_ids=(obligation_id,),
                            ),
                        ),
                        required_mechanisms=("dedupe",),
                        allowed_provenance=("runtime_observed",),
                    ),
                ),
                family_evidence=(
                    ObligationFamilyEvidence(
                        "family-simple",
                        family_id="checkout-family",
                        member_id="simple",
                        mechanism_id="dedupe",
                        provenance="runtime_observed",
                        result_status="passed",
                        covered_obligations=(obligation_id,),
                    ),
                ),
                similarity_handoff=SimilarityHandoff(
                    relation_ids=(relation_id,),
                ),
            )
        )

        self.assertTrue(report.ok, report.format_text())

    def test_architecture_reduction_accepts_similarity_with_evidence_refs(self):
        report = review_architecture_reduction(
            ArchitectureReductionPlan(
                "ready-similarity-reduction",
                observable_contract=ObservableArchitectureContract(
                    source_model_id="checkout",
                    source_code_boundary_id="checkout.handlers",
                    public_entrypoints=("checkout.submit",),
                    observable_outputs=("OrderStored",),
                    validation_boundaries=("model similarity review",),
                    rationale="Keep checkout public behavior stable.",
                ),
                rationale="Collapse adapter after similarity review and equivalence evidence.",
                candidates=(
                    ArchitectureReductionCandidate(
                        "collapse-retry-adapter",
                        candidate_type=CANDIDATE_COLLAPSE_ADAPTER,
                        code_node_id="checkout.retry_adapter",
                        source_model_element="checkout-simple:checkout-retry:adapter_only_difference",
                        target_action=TARGET_ACTION_COLLAPSE,
                        proof_status=PROOF_SAFE_BY_EQUIVALENCE,
                        required_next_route=ROUTE_STRUCTURE_MESH,
                        rationale="Similarity is backed by equivalence replay.",
                        affected_public_entrypoints=("checkout.submit",),
                        evidence_refs=("replay:checkout-equivalence",),
                        similarity_handoff=SimilarityHandoff(
                            relation_ids=("checkout-simple:checkout-retry:adapter_only_difference",),
                            code_obligation_ids=(
                                "checkout-simple:checkout-retry:adapter_only_difference:duplicate-boundary",
                            ),
                        ),
                    ),
                ),
            )
        )

        self.assertTrue(report.ok, report.format_text())


if __name__ == "__main__":
    unittest.main()
