import unittest

from flowguard.architecture_reduction import (
    CANDIDATE_COLLAPSE_ADAPTER,
    PROOF_SAFE_BY_EQUIVALENCE,
    ROUTE_CODE_STRUCTURE_RECOMMENDATION,
    ROUTE_STRUCTURE_MESH,
    TARGET_ACTION_COLLAPSE,
    ArchitectureReductionCandidate,
    ArchitectureReductionPlan,
    ObservableArchitectureContract,
    review_architecture_reduction,
)
from flowguard.code_structure import (
    CodeStructureRecommendation,
    TargetModuleRecommendation,
    review_code_structure_recommendation,
)
from flowguard.contract_exhaustion import (
    ContractExhaustionPlan,
    contract_exhaustion_to_model_obligations,
    review_contract_exhaustion,
)
from flowguard.existing_model_preflight import (
    REUSE_DECISION_EXTEND_EXISTING,
    ExistingModelPreflight,
    ExistingOwnershipSnapshot,
    ModelContextHit,
    review_existing_model_preflight,
)
from flowguard.canonical_relation import (
    CanonicalRelation,
    CanonicalRelationHandoff,
    RELATION_ADAPTER_ONLY,
    RELATION_FALSE_FRIEND,
    RELATION_SAME_INTENT,
    RELATION_SHARED_MECHANISM,
)
from flowguard.model_test_alignment import (
    ModelTestAlignmentPlan,
    review_model_test_alignment,
)


def _relation(
    relation_id: str,
    relation_type: str,
    *,
    source_model_id: str = "checkout-simple",
    target_model_id: str = "checkout-retry",
) -> CanonicalRelation:
    return CanonicalRelation(
        relation_id=relation_id,
        relation_type=relation_type,
        source_endpoint_kind="model",
        source_endpoint_id=source_model_id,
        target_endpoint_kind="model",
        target_endpoint_id=target_model_id,
        source_ids=("observed-model:snapshot-current",),
    )


class CanonicalRelationIntegrationTests(unittest.TestCase):
    def test_existing_preflight_consumes_current_relation_without_a_review_route(self):
        relation = _relation(
            "relation:checkout-affected-sibling",
            RELATION_SAME_INTENT,
        )
        preflight = ExistingModelPreflight(
            "canonical-relation-current",
            "Change checkout validation",
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
            rationale="The current relation keeps the affected sibling explicit.",
            canonical_relation_handoff=CanonicalRelationHandoff(
                relations=(relation,),
                affected_model_ids=("checkout-retry",),
            ),
        )

        report = review_existing_model_preflight(preflight)
        codes = {finding.code for finding in report.findings}

        self.assertNotIn("stale_canonical_relation_evidence", codes)
        self.assertNotIn("unresolved_canonical_relation_gap", codes)
        handoff_payload = preflight.to_dict()["canonical_relation_handoff"]
        self.assertEqual(
            relation.relation_id,
            handoff_payload["relations"][0]["relation_id"],
        )

    def test_existing_preflight_blocks_stale_or_gapped_relation_input(self):
        report = review_existing_model_preflight(
            ExistingModelPreflight(
                "canonical-relation-gap",
                "Change checkout validation",
                mode="light",
                reuse_decision=REUSE_DECISION_EXTEND_EXISTING,
                rationale="The relation evidence is not ready.",
                canonical_relation_handoff=CanonicalRelationHandoff(
                    relations=(
                        _relation(
                            "relation:checkout-stale",
                            RELATION_SAME_INTENT,
                        ),
                    ),
                    gap_ids=("gap:checkout-owner",),
                    evidence_current=False,
                ),
            )
        )

        codes = {finding.code for finding in report.findings}
        self.assertIn("stale_canonical_relation_evidence", codes)
        self.assertIn("unresolved_canonical_relation_gap", codes)

    def test_architecture_reduction_does_not_treat_relation_as_contraction_proof(self):
        relation = _relation(
            "relation:checkout-adapter-only",
            RELATION_ADAPTER_ONLY,
        )
        report = review_architecture_reduction(
            ArchitectureReductionPlan(
                "relation-is-not-proof",
                observable_contract=ObservableArchitectureContract(
                    source_model_id="checkout",
                    source_code_boundary_id="checkout.handlers",
                    public_entrypoints=("checkout.submit",),
                    observable_outputs=("OrderStored",),
                    validation_boundaries=("equivalence replay",),
                    rationale="Keep current checkout behavior explicit.",
                ),
                rationale="Evaluate one duplicate adapter boundary.",
                candidates=(
                    ArchitectureReductionCandidate(
                        "collapse-retry-adapter",
                        candidate_type=CANDIDATE_COLLAPSE_ADAPTER,
                        code_node_id="checkout.retry_adapter",
                        source_model_element=relation.relation_id,
                        target_action=TARGET_ACTION_COLLAPSE,
                        proof_status=PROOF_SAFE_BY_EQUIVALENCE,
                        required_next_route=ROUTE_CODE_STRUCTURE_RECOMMENDATION,
                        rationale="The relation identifies a candidate, not proof.",
                        canonical_relation_handoff=CanonicalRelationHandoff(
                            relations=(relation,),
                        ),
                    ),
                ),
            )
        )

        self.assertIn(
            "canonical_relation_without_candidate_evidence",
            {finding.code for finding in report.findings},
        )

    def test_architecture_reduction_consumes_relation_with_owner_evidence(self):
        relation = _relation(
            "relation:checkout-adapter-evidence",
            RELATION_ADAPTER_ONLY,
        )
        report = review_architecture_reduction(
            ArchitectureReductionPlan(
                "relation-with-proof",
                observable_contract=ObservableArchitectureContract(
                    source_model_id="checkout",
                    source_code_boundary_id="checkout.handlers",
                    public_entrypoints=("checkout.submit",),
                    observable_outputs=("OrderStored",),
                    validation_boundaries=("equivalence replay",),
                    rationale="Keep current checkout behavior explicit.",
                ),
                rationale="Collapse only after owner evidence exists.",
                candidates=(
                    ArchitectureReductionCandidate(
                        "collapse-retry-adapter",
                        candidate_type=CANDIDATE_COLLAPSE_ADAPTER,
                        code_node_id="checkout.retry_adapter",
                        source_model_element=relation.relation_id,
                        target_action=TARGET_ACTION_COLLAPSE,
                        proof_status=PROOF_SAFE_BY_EQUIVALENCE,
                        required_next_route=ROUTE_STRUCTURE_MESH,
                        rationale="The consumer owns the contraction decision.",
                        affected_public_entrypoints=("checkout.submit",),
                        evidence_refs=("replay:checkout-equivalence",),
                        canonical_relation_handoff=CanonicalRelationHandoff(
                            relations=(relation,),
                            code_obligation_ids=(
                                "code-obligation:checkout-duplicate-boundary",
                            ),
                        ),
                    ),
                ),
            )
        )

        codes = {finding.code for finding in report.findings}
        self.assertNotIn("canonical_relation_without_candidate_evidence", codes)
        self.assertNotIn("missing_relation_code_obligation", codes)

    def test_code_structure_uses_relation_type_not_relation_name(self):
        relation = _relation(
            "relation:cache-pair-7",
            RELATION_FALSE_FRIEND,
            source_model_id="cache-refresh",
            target_model_id="cache-report",
        )
        report = review_code_structure_recommendation(
            CodeStructureRecommendation(
                "false-friend-structure",
                source_model_id="cache",
                parent_module_id="cache",
                target_modules=(
                    TargetModuleRecommendation(
                        "shared",
                        owns_function_blocks=("RefreshCache",),
                        rationale="Candidate shared owner.",
                    ),
                ),
                function_block_map=(("RefreshCache", "shared"),),
                facade_module_id="shared",
                canonical_relation_handoff=CanonicalRelationHandoff(relations=(relation,)),
                shared_kernel_module_id="shared",
                validation_boundaries=("manual review",),
                rationale="A typed false friend must not create shared ownership.",
            )
        )

        self.assertIn(
            "false_friend_relation_blocks_shared_structure",
            {finding.code for finding in report.findings},
        )

    def test_code_structure_consumes_exact_relation_group_and_code_obligation(self):
        relation = _relation(
            "relation:checkout-shared-kernel",
            RELATION_SHARED_MECHANISM,
        )
        report = review_code_structure_recommendation(
            CodeStructureRecommendation(
                "checkout-structure",
                source_model_id="checkout-family",
                parent_module_id="checkout",
                target_modules=(
                    TargetModuleRecommendation(
                        "core",
                        owns_function_blocks=("ValidateOrder",),
                        rationale="Exact shared owner.",
                    ),
                    TargetModuleRecommendation(
                        "retry_adapter",
                        rationale="Variant adapter.",
                    ),
                ),
                function_block_map=(("ValidateOrder", "core"),),
                facade_module_id="core",
                canonical_relation_handoff=CanonicalRelationHandoff(
                    relations=(relation,),
                    relation_group_ids=("relation-group:checkout",),
                    code_obligation_ids=("code-obligation:checkout-kernel",),
                ),
                shared_kernel_module_id="core",
                variant_adapter_module_ids=("retry_adapter",),
                validation_boundaries=("owner contract",),
                rationale="The code owner consumes exact current relations.",
            )
        )

        codes = {finding.code for finding in report.findings}
        self.assertNotIn("missing_relation_code_obligation", codes)
        self.assertNotIn("missing_relation_group_code_obligation", codes)

    def test_model_test_alignment_uses_typed_relation_for_family_scope(self):
        relation = _relation(
            "relation:checkout-same-intent",
            RELATION_SAME_INTENT,
        )
        report = review_model_test_alignment(
            ModelTestAlignmentPlan(
                "checkout",
                canonical_relation_handoff=CanonicalRelationHandoff(relations=(relation,)),
            )
        )

        self.assertIn(
            "missing_relation_family_evidence",
            {finding.code for finding in report.findings},
        )

    def test_model_test_alignment_requires_test_owner_for_relation_group(self):
        report = review_model_test_alignment(
            ModelTestAlignmentPlan(
                "checkout",
                canonical_relation_handoff=CanonicalRelationHandoff(
                    relation_group_ids=("relation-group:checkout",),
                ),
            )
        )

        self.assertIn(
            "missing_relation_test_obligations",
            {finding.code for finding in report.findings},
        )

    def test_contract_exhaustion_materializes_each_typed_handoff_identity(self):
        relation = _relation(
            "relation:router-duplicate",
            RELATION_SHARED_MECHANISM,
            source_model_id="router-ui",
            target_model_id="router-cli",
        )
        affected_model_id = "router-cli"
        test_obligation_id = "test-obligation:router-family"
        code_obligation_id = "code-obligation:router-kernel"
        materializations = {
            relation.relation_id: ("candidate:merge-handlers",),
            affected_model_id: ("model:router-cli",),
            test_obligation_id: ("member:router-ui",),
            code_obligation_id: ("candidate:merge-handlers",),
        }
        report = review_contract_exhaustion(
            ContractExhaustionPlan(
                "canonical-relation-materialization",
                model_id="router",
                inventory_revision="router:v3",
                canonical_relation_handoff=CanonicalRelationHandoff(
                    relations=(relation,),
                    affected_model_ids=(affected_model_id,),
                    test_obligation_ids=(test_obligation_id,),
                    code_obligation_ids=(code_obligation_id,),
                ),
                relation_materializations=materializations,
            )
        )

        self.assertEqual(
            tuple(materializations),
            report.materialized_relation_ids,
        )
        obligations = contract_exhaustion_to_model_obligations(report)
        self.assertTrue(
            any(
                affected_model_id in obligation.relation_impacted_model_ids
                for obligation in obligations
            )
        )


if __name__ == "__main__":
    unittest.main()
