from dataclasses import fields
from pathlib import Path
import unittest

import flowguard


ROOT = Path(__file__).resolve().parents[1]


class ApiSurfaceTests(unittest.TestCase):
    def test_api_surface_groups_are_exported(self):
        self.assertEqual(
            set(flowguard.API_SURFACE),
            {"core", "modeling_helpers", "reporting_helpers", "evidence"},
        )

        grouped_names = []
        for group_name, names in flowguard.API_SURFACE.items():
            self.assertIsInstance(names, tuple, group_name)
            self.assertTrue(names, group_name)
            for name in names:
                self.assertIn(name, flowguard.__all__, f"{group_name}:{name}")
                self.assertTrue(hasattr(flowguard, name), f"{group_name}:{name}")
                grouped_names.append(name)

        self.assertEqual(len(grouped_names), len(set(grouped_names)))

    def test_core_group_keeps_minimal_path_visible(self):
        self.assertIn("Workflow", flowguard.CORE_API)
        self.assertIn("Explorer", flowguard.CORE_API)
        self.assertIn("Invariant", flowguard.CORE_API)
        self.assertIn("FunctionResult", flowguard.CORE_API)
        self.assertNotIn("run_model_first_checks", flowguard.CORE_API)

    def test_runner_and_internal_evidence_are_not_core(self):
        self.assertIn("RiskIntent", flowguard.REPORTING_HELPER_API)
        self.assertIn("RiskEvidenceLedgerPlan", flowguard.REPORTING_HELPER_API)
        self.assertIn("RiskEvidenceProof", flowguard.REPORTING_HELPER_API)
        self.assertIn("RiskEvidenceRow", flowguard.REPORTING_HELPER_API)
        self.assertIn("review_risk_evidence_ledger", flowguard.REPORTING_HELPER_API)
        self.assertIn("DefectFamilyCase", flowguard.REPORTING_HELPER_API)
        self.assertIn("DefectFamilyEvidence", flowguard.REPORTING_HELPER_API)
        self.assertIn("DefectFamilyGate", flowguard.REPORTING_HELPER_API)
        self.assertIn("DefectFamilyGatePlan", flowguard.REPORTING_HELPER_API)
        self.assertIn("DefectFamilyGateReport", flowguard.REPORTING_HELPER_API)
        self.assertIn("review_defect_family_gates", flowguard.REPORTING_HELPER_API)
        self.assertIn("TestResultReuseTicket", flowguard.REPORTING_HELPER_API)
        self.assertIn("coerce_test_result_reuse_ticket", flowguard.REPORTING_HELPER_API)
        self.assertIn("test_result_reuse_gap_codes", flowguard.REPORTING_HELPER_API)
        self.assertIn("AutoSplitCandidate", flowguard.REPORTING_HELPER_API)
        self.assertIn("AutoSplitPlan", flowguard.REPORTING_HELPER_API)
        self.assertIn("AutoSplitReport", flowguard.REPORTING_HELPER_API)
        self.assertIn("review_auto_mesh_splits", flowguard.REPORTING_HELPER_API)
        self.assertIn("MaintenanceScanPlan", flowguard.REPORTING_HELPER_API)
        self.assertIn("MaintenanceAction", flowguard.REPORTING_HELPER_API)
        self.assertIn("review_maintenance_scan", flowguard.REPORTING_HELPER_API)
        self.assertIn("maintenance_scan_template_files", flowguard.EVIDENCE_API)
        self.assertNotIn("review_maintenance_scan", flowguard.CORE_API)
        self.assertIn("ArtifactUpgradeItem", flowguard.REPORTING_HELPER_API)
        self.assertIn("ArtifactUpgradeReport", flowguard.REPORTING_HELPER_API)
        self.assertIn("review_artifact_upgrades", flowguard.REPORTING_HELPER_API)
        self.assertNotIn("review_artifact_upgrades", flowguard.CORE_API)
        self.assertIn("ModelFreshnessRecord", flowguard.REPORTING_HELPER_API)
        self.assertIn("UpgradeImpact", flowguard.REPORTING_HELPER_API)
        self.assertIn("ModelImpactAssessment", flowguard.REPORTING_HELPER_API)
        self.assertIn("ModelReuseTicket", flowguard.REPORTING_HELPER_API)
        self.assertIn("ModelRerunEvidence", flowguard.REPORTING_HELPER_API)
        self.assertIn("ModelImpactFreshnessPlan", flowguard.REPORTING_HELPER_API)
        self.assertIn("ModelImpactFreshnessReport", flowguard.REPORTING_HELPER_API)
        self.assertIn("review_model_impact_freshness", flowguard.REPORTING_HELPER_API)
        self.assertIn("ProjectAdoptionFinding", flowguard.REPORTING_HELPER_API)
        self.assertIn("ProjectAdoptionReport", flowguard.REPORTING_HELPER_API)
        self.assertIn("audit_project_adoption", flowguard.REPORTING_HELPER_API)
        self.assertIn("adopt_project", flowguard.REPORTING_HELPER_API)
        self.assertIn("upgrade_project", flowguard.REPORTING_HELPER_API)
        self.assertIn("run_model_first_checks", flowguard.REPORTING_HELPER_API)
        self.assertIn("audit_model", flowguard.REPORTING_HELPER_API)
        self.assertIn("CodeStructureRecommendation", flowguard.MODELING_HELPER_API)
        self.assertIn("TargetModuleRecommendation", flowguard.MODELING_HELPER_API)
        self.assertIn("review_code_structure_recommendation", flowguard.MODELING_HELPER_API)
        self.assertIn("UIInteractionModel", flowguard.MODELING_HELPER_API)
        self.assertIn("UIJourneyCoverage", flowguard.MODELING_HELPER_API)
        self.assertIn("UIJourneyCoverageReport", flowguard.MODELING_HELPER_API)
        self.assertIn("UIJourneyEntryPoint", flowguard.MODELING_HELPER_API)
        self.assertIn("UIFeatureJourney", flowguard.MODELING_HELPER_API)
        self.assertIn("UITerminalActionAllowance", flowguard.MODELING_HELPER_API)
        self.assertIn("UIResidualBlindspot", flowguard.MODELING_HELPER_API)
        self.assertIn("UIFeatureContract", flowguard.MODELING_HELPER_API)
        self.assertIn("UIImplementationJourneyRun", flowguard.MODELING_HELPER_API)
        self.assertIn("UIImplementationStepEvidence", flowguard.MODELING_HELPER_API)
        self.assertIn("UIImplementationBlindspot", flowguard.MODELING_HELPER_API)
        self.assertIn("UIImplementationValidation", flowguard.MODELING_HELPER_API)
        self.assertIn("UIImplementationValidationReport", flowguard.MODELING_HELPER_API)
        self.assertIn("UIDisplayElement", flowguard.MODELING_HELPER_API)
        self.assertIn("UIStructureDerivation", flowguard.MODELING_HELPER_API)
        self.assertIn("UITextHierarchyBlueprint", flowguard.MODELING_HELPER_API)
        self.assertIn("UITextElement", flowguard.MODELING_HELPER_API)
        self.assertIn("UITextHierarchyReport", flowguard.MODELING_HELPER_API)
        self.assertIn("UITypographyToken", flowguard.MODELING_HELPER_API)
        self.assertIn("review_ui_interaction_model", flowguard.MODELING_HELPER_API)
        self.assertIn("review_ui_journey_coverage", flowguard.MODELING_HELPER_API)
        self.assertIn("review_ui_implementation_validation", flowguard.MODELING_HELPER_API)
        self.assertIn("review_ui_structure_derivation", flowguard.MODELING_HELPER_API)
        self.assertIn("review_ui_text_hierarchy", flowguard.MODELING_HELPER_API)
        self.assertIn("ModelTestAlignmentPlan", flowguard.MODELING_HELPER_API)
        self.assertIn("review_model_test_alignment", flowguard.MODELING_HELPER_API)
        self.assertIn("ModelSignature", flowguard.MODELING_HELPER_API)
        self.assertIn("ModelSimilarityPlan", flowguard.MODELING_HELPER_API)
        self.assertIn("ModelSimilarityRelation", flowguard.MODELING_HELPER_API)
        self.assertIn("ModelSimilarityReport", flowguard.MODELING_HELPER_API)
        self.assertIn("ModelSimilarityMaintenanceGroup", flowguard.MODELING_HELPER_API)
        self.assertIn("ModelSimilarityChangeImpact", flowguard.MODELING_HELPER_API)
        self.assertIn("ModelSimilarityTestObligation", flowguard.MODELING_HELPER_API)
        self.assertIn("ModelSimilarityCodeObligation", flowguard.MODELING_HELPER_API)
        self.assertIn("SimilarityHandoff", flowguard.MODELING_HELPER_API)
        self.assertIn("model_signature_minimal", flowguard.MODELING_HELPER_API)
        self.assertIn("model_signature_maintenance", flowguard.MODELING_HELPER_API)
        self.assertIn("model_similarity_plan_for_changed_member", flowguard.MODELING_HELPER_API)
        self.assertIn("review_model_similarity_consolidation", flowguard.MODELING_HELPER_API)
        self.assertIn("RELATION_SAME_FAMILY_VARIANT", flowguard.MODELING_HELPER_API)
        self.assertIn("RECOMMEND_ROUTE_ARCHITECTURE_REDUCTION", flowguard.MODELING_HELPER_API)
        self.assertIn("ChildBoundaryChangeSummary", flowguard.MODELING_HELPER_API)
        self.assertIn("summarize_child_boundary_change", flowguard.MODELING_HELPER_API)
        self.assertIn("LayeredBoundaryProofPlan", flowguard.MODELING_HELPER_API)
        self.assertIn("LeafBoundaryMatrixCell", flowguard.MODELING_HELPER_API)
        self.assertIn("review_layered_boundary_proof", flowguard.MODELING_HELPER_API)
        self.assertIn("ModelMaturationPlan", flowguard.MODELING_HELPER_API)
        self.assertIn("ModelMaturationSignal", flowguard.MODELING_HELPER_API)
        self.assertIn("ModelMaturationReport", flowguard.MODELING_HELPER_API)
        self.assertIn("review_model_maturation_loop", flowguard.MODELING_HELPER_API)
        self.assertIn("UsageIntent", flowguard.MODELING_HELPER_API)
        self.assertIn("TopologyDigest", flowguard.MODELING_HELPER_API)
        self.assertIn("TopologyHazardCandidate", flowguard.MODELING_HELPER_API)
        self.assertIn("TopologyHazardReviewPlan", flowguard.MODELING_HELPER_API)
        self.assertIn("TopologyHazardReport", flowguard.MODELING_HELPER_API)
        self.assertIn("infer_topology_digest", flowguard.MODELING_HELPER_API)
        self.assertIn("infer_topology_hazard_plan", flowguard.MODELING_HELPER_API)
        self.assertIn("review_topology_hazards", flowguard.MODELING_HELPER_API)
        self.assertIn("ObservableArchitectureContract", flowguard.MODELING_HELPER_API)
        self.assertIn("CompatibilitySurfaceClassification", flowguard.MODELING_HELPER_API)
        self.assertIn("ArchitectureReductionCandidate", flowguard.MODELING_HELPER_API)
        self.assertIn("ArchitectureReductionPlan", flowguard.MODELING_HELPER_API)
        self.assertIn("review_architecture_reduction", flowguard.MODELING_HELPER_API)
        self.assertIn("COMPATIBILITY_SURFACE_PRUNE_CANDIDATE", flowguard.MODELING_HELPER_API)
        self.assertIn("COMPATIBILITY_ACTION_COLLECT_EVIDENCE", flowguard.MODELING_HELPER_API)
        self.assertIn("PlanDetail", flowguard.REPORTING_HELPER_API)
        self.assertIn("PlanDetailStep", flowguard.REPORTING_HELPER_API)
        self.assertIn("PlanDetailValidation", flowguard.REPORTING_HELPER_API)
        self.assertIn("review_plan_detail", flowguard.REPORTING_HELPER_API)
        self.assertIn("plan_detail_to_development_process", flowguard.REPORTING_HELPER_API)
        self.assertIn("plan_detailing_template_files", flowguard.EVIDENCE_API)
        self.assertNotIn("review_code_structure_recommendation", flowguard.CORE_API)
        self.assertNotIn("review_ui_interaction_model", flowguard.CORE_API)
        self.assertNotIn("review_ui_journey_coverage", flowguard.CORE_API)
        self.assertNotIn("review_ui_implementation_validation", flowguard.CORE_API)
        self.assertNotIn("review_model_test_alignment", flowguard.CORE_API)
        self.assertNotIn("summarize_child_boundary_change", flowguard.CORE_API)
        self.assertIn("build_executable_corpus_report", flowguard.EVIDENCE_API)
        self.assertIn("build_evidence_baseline_report", flowguard.EVIDENCE_API)
        self.assertIn("project_adoption_template_files", flowguard.EVIDENCE_API)
        self.assertNotIn("build_executable_corpus_report", flowguard.CORE_API)

    def test_model_test_alignment_code_contract_api_is_public_helper(self):
        expected = (
            "CodeBoundaryConformanceReport",
            "CodeBoundaryContract",
            "CodeBoundaryFinding",
            "CodeBoundaryObservation",
            "CodeContract",
            "TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT",
            "TEST_ASSERTION_SCOPE_INTERNAL_PATH",
            "TEST_ASSERTION_SCOPE_MIXED",
            "TEST_ASSERTION_SCOPE_UNKNOWN",
            "TEST_CLOSURE_ROLE_OBSERVED_REGRESSION",
            "TEST_CLOSURE_ROLE_SAME_CLASS_GENERALIZED",
            "TEST_CLOSURE_ROLE_UNSPECIFIED",
            "CODE_CONTRACT_ROLE_OWNER",
            "CODE_CONTRACT_ROLE_HELPER",
            "CODE_CONTRACT_ROLE_ADAPTER",
            "CODE_CONTRACT_ROLE_FACADE",
            "CODE_CONTRACT_ROLE_READ_ONLY",
            "TEST_EVIDENCE_ROLE_PRIMARY",
            "TEST_EVIDENCE_ROLE_PRIMARY_EDGE_PATH",
            "TEST_EVIDENCE_ROLE_LEAF_MATRIX_CELL",
            "TEST_EVIDENCE_ROLE_SUPPORTING_CONTRACT",
            "TEST_EVIDENCE_ROLE_INTEGRATION_SMOKE",
            "PythonCodeContractEvidence",
            "PythonTestAssertionEvidence",
            "ContractSourceAuditFinding",
            "ContractSourceAuditReport",
            "audit_python_code_contracts",
            "audit_python_test_assertions",
            "review_code_boundary_conformance",
            "review_python_contract_source_audit",
        )

        for name in expected:
            self.assertIn(name, flowguard.MODELING_HELPER_API)
            self.assertIn(name, flowguard.__all__)
            self.assertTrue(hasattr(flowguard, name), name)
            self.assertNotIn(name, flowguard.CORE_API)

    def test_route_api_registry_groups_public_names(self):
        expected_groups = {
            "template_structure",
            "evidence_field_structure",
            "model_similarity_consolidation",
            "architecture_reduction",
            "code_structure_recommendation",
            "model_test_alignment",
            "plan_detailing_compiler",
            "maintenance_scan_router",
            "state_closure",
            "model_topology_hazard_review",
        }
        self.assertEqual(expected_groups, set(flowguard.FLOWGUARD_ROUTE_API))

        for group_name, names in flowguard.FLOWGUARD_ROUTE_API.items():
            with self.subTest(group=group_name):
                self.assertIsInstance(names, tuple)
                self.assertTrue(names)
                for name in names:
                    self.assertIn(name, flowguard.__all__, name)
                    self.assertTrue(hasattr(flowguard, name), name)

        for name in flowguard.EVIDENCE_FIELD_STRUCTURE_API:
            self.assertIn(name, flowguard.EVIDENCE_API)

    def test_legacy_plan_intake_aliases_are_not_exported(self):
        removed_aliases = {
            "PlanIntakeSurface",
            "PlanIntakeCompletenessFinding",
            "FalseNegativeBackpropagationCase",
            "FlowGuardClaimFinding",
            "review_plan_mutation_results",
        }

        for name in removed_aliases:
            self.assertNotIn(name, flowguard.__all__)
            self.assertNotIn(name, flowguard.REPORTING_HELPER_API)
            self.assertFalse(hasattr(flowguard, name), name)

    def test_similarity_handoff_replaces_repeated_downstream_fields(self):
        for cls, removed in (
            (
                flowguard.ExistingModelPreflight,
                {
                    "similarity_relation_ids",
                    "similarity_maintenance_group_ids",
                    "similarity_change_impact_ids",
                    "impacted_similarity_model_ids",
                    "false_friend_rationales",
                },
            ),
            (
                flowguard.CodeStructureRecommendation,
                {
                    "similarity_relation_ids",
                    "similarity_maintenance_group_ids",
                    "similarity_code_obligation_ids",
                },
            ),
            (
                flowguard.ModelTestAlignmentPlan,
                {
                    "similarity_relation_ids",
                    "similarity_maintenance_group_ids",
                    "similarity_test_obligation_ids",
                    "same_family_similarity_relation_ids",
                    "evidence_duplicate_relation_ids",
                },
            ),
            (
                flowguard.ArchitectureReductionCandidate,
                {"similarity_relation_ids", "similarity_code_obligation_ids"},
            ),
        ):
            field_names = {field.name for field in fields(cls)}
            self.assertIn("similarity_handoff", field_names)
            self.assertTrue(removed.isdisjoint(field_names), cls.__name__)

    def test_api_docs_are_route_first_before_flat_helper_index(self):
        text = (ROOT / "docs" / "api_surface.md").read_text(encoding="utf-8")
        self.assertLess(text.index("## Route-Scoped Discovery First"), text.index("## Modeling Helpers"))
        self.assertLess(text.index("FLOWGUARD_ROUTE_API"), text.index("MODELING_HELPER_API"))
        self.assertIn("Use `MODELING_HELPER_API` only as the complete index", text)

    def test_public_all_is_derived_from_api_groups_and_supplement(self):
        expected_supplement = (
            "API_SURFACE",
            "ARCHITECTURE_REDUCTION_ROUTE_API",
            "CODE_STRUCTURE_RECOMMENDATION_ROUTE_API",
            "CORE_API",
            "EVIDENCE_FIELD_STRUCTURE_API",
            "EVIDENCE_API",
            "FLOWGUARD_ROUTE_API",
            "FLOWGUARD_CLOSURE_CONTRACT_API",
            "MAINTENANCE_SCAN_ROUTE_API",
            "MODEL_SIMILARITY_ROUTE_API",
            "MODEL_TEST_ALIGNMENT_ROUTE_API",
            "MODEL_IMPACT_FRESHNESS_API",
            "MODEL_MATURATION_API",
            "PLAN_DETAILING_ROUTE_API",
            "STATE_CLOSURE_ROUTE_API",
            "TOPOLOGY_HAZARD_ROUTE_API",
            "MODELING_HELPER_API",
            "REPORTING_HELPER_API",
            "TEMPLATE_STRUCTURE_API",
            "RISK_INTENT_FIELDS",
            "PROOF_ARTIFACT_STATUS_PASSED",
            "PROOF_ARTIFACT_STATUS_FAILED",
            "PROOF_ARTIFACT_STATUS_SKIPPED",
            "PROOF_ARTIFACT_STATUS_STALE",
            "PROOF_ARTIFACT_STATUS_NOT_RUN",
            "PROOF_ARTIFACT_STATUS_RUNNING",
            "PROOF_ARTIFACT_STATUS_PROGRESS_ONLY",
            "PROOF_ARTIFACT_STATUS_ERROR",
            "PROOF_ARTIFACT_SCOPE_EXTERNAL_CONTRACT",
            "PROOF_ARTIFACT_SCOPE_INTERNAL_PATH",
            "PROOF_ARTIFACT_SCOPE_MIXED",
            "PROOF_ARTIFACT_SCOPE_UNKNOWN",
            "PASSING_PROOF_ARTIFACT_STATUSES",
            "NON_PASSING_PROOF_ARTIFACT_STATUSES",
            "LEGACY_PATH_DELETED",
            "LEGACY_PATH_BLOCKED",
            "LEGACY_PATH_DELEGATED",
            "LEGACY_PATH_SAME_CONTRACT_REPAIRED",
            "LEGACY_PATH_OUT_OF_SCOPE",
            "LEGACY_PATH_UNKNOWN",
            "ARTIFACT_UPGRADE_STATUS_BLOCKED",
            "ARTIFACT_UPGRADE_STATUS_SKIPPED",
            "ARTIFACT_UPGRADE_STATUS_UNCHANGED",
            "ARTIFACT_UPGRADE_STATUS_UPGRADED",
            "ARTIFACT_UPGRADE_STATUSES",
            "ARTIFACT_UPGRADE_TEXT_REPLACEMENTS",
        )
        self.assertEqual(flowguard._PUBLIC_API_SUPPLEMENT, expected_supplement)

        expected = []
        for names in flowguard.API_SURFACE.values():
            expected.extend(names)
        expected.extend(expected_supplement)

        self.assertEqual(set(flowguard.__all__), set(expected))
        self.assertEqual(len(flowguard.__all__), len(set(flowguard.__all__)))
        for name in expected_supplement:
            self.assertTrue(hasattr(flowguard, name), name)


if __name__ == "__main__":
    unittest.main()
