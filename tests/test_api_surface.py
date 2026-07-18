from dataclasses import fields
from pathlib import Path
import unittest

import flowguard


ROOT = Path(__file__).resolve().parents[1]


class ApiSurfaceTests(unittest.TestCase):
    def test_process_optimization_is_compact_api_of_existing_development_process_route(self):
        self.assertNotIn("development_process_strategy", flowguard.FLOWGUARD_ROUTE_API)
        process_api = flowguard.FLOWGUARD_ROUTE_API["development_process_flow"]
        expected = {
            "ProcessOptimizationContract",
            "ProcessOptimizationCandidate",
            "ProcessRepairGroup",
            "ProcessOptimizationDecision",
            "ProcessOptimizationReport",
            "review_process_optimization",
        }
        self.assertTrue(expected.issubset(process_api))
        self.assertIn("PROCESS_EVIDENCE_PROCESS_OPTIMIZATION", process_api)
        retired = {
            "DevelopmentProcessStrategyPlan",
            "review_development_process_strategy",
            "PROCESS_EVIDENCE_DEVELOPMENT_PROCESS_STRATEGY",
            "ProcessStrategyAlignmentBinding",
        }
        self.assertTrue(retired.isdisjoint(process_api))
        for name in retired:
            self.assertFalse(hasattr(flowguard, name), name)

    def self_maintenance_child_reports(self):
        def child(child_id, owner_guard, artifact_kind):
            return flowguard.SelfMaintenanceChildReport(
                child_id,
                owner_guard,
                artifact_kind,
                receipt_id=f"receipt:{child_id}",
                receipt_fingerprint=f"sha256:{child_id}-receipt",
                input_fingerprint=f"sha256:{child_id}-inputs",
                claim_scope="full",
                covered_obligations=(f"flowguard.self_maintenance.{artifact_kind}",),
                verification_status=flowguard.SELF_MAINTENANCE_STATUS_PASS,
                verification_current=True,
                verification_eligible=True,
                safe_claim=f"{artifact_kind} evidence is current",
                unsafe_claim_boundary="does not prove package, shadow, or git sync",
            )

        return (
            child("route-graph", "flowguard_self_maintenance", "route_graph"),
            child("behavior-commitment-ledger", "behavior_commitment_ledger", "behavior_commitment_ledger"),
            child("contract-exhaustion-mesh", "contract_exhaustion_mesh", "contract_exhaustion_mesh"),
            child("test-mesh", "test_mesh_maintenance", "test_mesh_maintenance"),
            child("model-miss-backfeed", "model_miss_review", "model_miss_review"),
        )

    def iter_api_surface_names(self):
        for group in flowguard.API_SURFACE.values():
            if isinstance(group, dict):
                for names in group.values():
                    yield from names
            else:
                yield from group

    def test_api_surface_groups_are_exported(self):
        self.assertEqual(
            set(flowguard.API_SURFACE),
            {
                "agent_default",
                "route_starters",
                "route_advanced",
                "core",
                "modeling_helpers_full",
                "reporting_helpers_full",
                "evidence",
                "governance_and_distribution",
                "spec_context",
                "portable_verification",
            },
        )

        canonical_grouped_names = []
        for group_name, group in flowguard.API_SURFACE.items():
            if isinstance(group, dict):
                self.assertTrue(group, group_name)
                for route_id, names in group.items():
                    self.assertIsInstance(names, tuple, f"{group_name}:{route_id}")
                    self.assertTrue(names, f"{group_name}:{route_id}")
                    for name in names:
                        self.assertIn(name, flowguard.__all__, f"{group_name}:{route_id}:{name}")
                        self.assertTrue(hasattr(flowguard, name), f"{group_name}:{route_id}:{name}")
                        canonical_grouped_names.append(name)
            else:
                self.assertIsInstance(group, tuple, group_name)
                self.assertTrue(group, group_name)
                for name in group:
                    self.assertIn(name, flowguard.__all__, f"{group_name}:{name}")
                    self.assertTrue(hasattr(flowguard, name), f"{group_name}:{name}")
                    if group_name != "agent_default":
                        canonical_grouped_names.append(name)

        public_first_read_names = set(canonical_grouped_names) | set(flowguard._PUBLIC_API_SUPPLEMENT)
        self.assertTrue(set(flowguard.AGENT_DEFAULT_API).issubset(public_first_read_names))

    def test_agent_default_api_is_compact_first_read_surface(self):
        self.assertLessEqual(len(flowguard.AGENT_DEFAULT_API), 24)
        expected = {
            "Workflow",
            "Invariant",
            "RiskIntent",
            "RiskProfile",
            "FlowGuardCheckPlan",
            "MinimumModelContract",
            "KnownBadProof",
            "TemplateReuseReview",
            "TemplateHarvestReview",
            "review_known_bad_proofs",
            "run_model_first_checks",
            "FLOWGUARD_ROUTE_API",
            "audit_project_adoption",
            "review_development_process_flow",
            "review_model_test_alignment",
            "review_field_lifecycle",
        }
        self.assertTrue(expected.issubset(set(flowguard.AGENT_DEFAULT_API)))
        self.assertNotIn("Explorer", flowguard.AGENT_DEFAULT_API)
        self.assertEqual(flowguard.AGENT_DEFAULT_API, flowguard.API_SURFACE["agent_default"])

    def test_route_starter_api_is_compact_and_public(self):
        self.assertEqual(flowguard.ROUTE_STARTER_API, flowguard.API_SURFACE["route_starters"])
        self.assertEqual(flowguard.ROUTE_ADVANCED_API, flowguard.API_SURFACE["route_advanced"])
        self.assertIn("plan_intake_claims", flowguard.ROUTE_STARTER_API)
        self.assertLessEqual(max(len(names) for names in flowguard.ROUTE_STARTER_API.values()), 12)
        self.assertLessEqual(len(flowguard.PLAN_INTAKE_STARTER_API), 25)
        self.assertGreater(len(flowguard.PLAN_INTAKE_ADVANCED_API), len(flowguard.PLAN_INTAKE_STARTER_API))
        self.assertEqual(flowguard.PLAN_INTAKE_ADVANCED_API, flowguard.PLAN_INTAKE_CLAIM_API)

        broad_surfaces = {
            "MODELING_HELPER_API",
            "REPORTING_HELPER_API",
            "PLAN_INTAKE_CLAIM_API",
            "PLAN_INTAKE_ADVANCED_API",
        }
        for route_id, names in flowguard.ROUTE_STARTER_API.items():
            with self.subTest(route=route_id):
                self.assertTrue(names)
                self.assertTrue(broad_surfaces.isdisjoint(names))
                for name in names:
                    self.assertIn(name, flowguard.__all__, name)
                    self.assertTrue(hasattr(flowguard, name), name)

    def test_core_group_keeps_minimal_path_visible(self):
        self.assertIn("Workflow", flowguard.CORE_API)
        self.assertNotIn("Explorer", flowguard.CORE_API)
        self.assertFalse(hasattr(flowguard, "Explorer"))
        self.assertIn("Invariant", flowguard.CORE_API)
        self.assertIn("FunctionResult", flowguard.CORE_API)
        self.assertNotIn("run_model_first_checks", flowguard.CORE_API)

    def test_runner_and_internal_evidence_are_not_core(self):
        self.assertIn("RiskIntent", flowguard.REPORTING_HELPER_API)
        self.assertIn("KnownBadProof", flowguard.MODELING_HELPER_API)
        self.assertIn("review_known_bad_proofs", flowguard.MODELING_HELPER_API)
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
        self.assertIn("MaintenanceObligation", flowguard.REPORTING_HELPER_API)
        self.assertIn("MaintenanceObligationReport", flowguard.REPORTING_HELPER_API)
        self.assertIn("build_maintenance_obligation_report", flowguard.REPORTING_HELPER_API)
        self.assertIn("MaintenanceScanPlan", flowguard.REPORTING_HELPER_API)
        self.assertIn("MaintenanceAction", flowguard.REPORTING_HELPER_API)
        self.assertIn("review_maintenance_scan", flowguard.REPORTING_HELPER_API)
        self.assertIn("maintenance_scan_plan_from_summary_report", flowguard.REPORTING_HELPER_API)
        self.assertIn("maintenance_scan_template_files", flowguard.EVIDENCE_API)
        self.assertNotIn("review_maintenance_scan", flowguard.CORE_API)
        self.assertNotIn("maintenance_scan_plan_from_summary_report", flowguard.CORE_API)
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
        self.assertIn("existing_model_preflight_from_project", flowguard.MODELING_HELPER_API)
        self.assertNotIn("existing_model_preflight_from_project", flowguard.CORE_API)
        self.assertIn("ModelAngleDeliberation", flowguard.MODELING_HELPER_API)
        self.assertIn("ModelAngleReviewReport", flowguard.MODELING_HELPER_API)
        self.assertIn("review_model_angle_deliberations", flowguard.MODELING_HELPER_API)
        self.assertIn("model_angle_deliberation_template_files", flowguard.EVIDENCE_API)
        self.assertNotIn("review_model_angle_deliberations", flowguard.CORE_API)
        self.assertIn("RouteProfile", flowguard.MODELING_HELPER_API)
        self.assertIn("AIMaintenanceProfile", flowguard.MODELING_HELPER_API)
        self.assertIn("FieldLayerProfile", flowguard.MODELING_HELPER_API)
        self.assertIn("SelfMaintenancePlan", flowguard.MODELING_HELPER_API)
        self.assertIn("default_flowguard_self_maintenance_plan", flowguard.MODELING_HELPER_API)
        self.assertIn("review_flowguard_self_maintenance", flowguard.MODELING_HELPER_API)
        self.assertNotIn("default_flowguard_self_maintenance_plan", flowguard.CORE_API)
        self.assertNotIn("review_flowguard_self_maintenance", flowguard.CORE_API)
        self.assertIn("UIInteractionModel", flowguard.MODELING_HELPER_API)
        self.assertIn("UIJourneyCoverage", flowguard.MODELING_HELPER_API)
        self.assertIn("UIJourneyCoverageReport", flowguard.MODELING_HELPER_API)
        self.assertIn("UIJourneyEntryPoint", flowguard.MODELING_HELPER_API)
        self.assertIn("UIFeatureJourney", flowguard.MODELING_HELPER_API)
        self.assertIn("UITerminalActionAllowance", flowguard.MODELING_HELPER_API)
        self.assertIn("UIBlindspot", flowguard.MODELING_HELPER_API)
        self.assertIn("UIFeatureContract", flowguard.MODELING_HELPER_API)
        self.assertIn("UIImplementationJourneyRun", flowguard.MODELING_HELPER_API)
        self.assertIn("UIImplementationStepEvidence", flowguard.MODELING_HELPER_API)
        self.assertIn("UIImplementationValidation", flowguard.MODELING_HELPER_API)
        self.assertIn("UIImplementationValidationReport", flowguard.MODELING_HELPER_API)
        self.assertIn("UIDisplayElement", flowguard.MODELING_HELPER_API)
        self.assertIn("UIStructureDerivation", flowguard.MODELING_HELPER_API)
        self.assertIn("UITextHierarchyBlueprint", flowguard.MODELING_HELPER_API)
        self.assertIn("UITextElement", flowguard.MODELING_HELPER_API)
        self.assertIn("UITextHierarchyReport", flowguard.MODELING_HELPER_API)
        self.assertIn("UITypographyToken", flowguard.MODELING_HELPER_API)
        new_ui_surface_helpers = (
            "SUPPORTED_UI_EVIDENCE_KINDS",
            "UI_CONTENT_VISIBILITY_CLASSES",
            "UI_CONTENT_NEED_KINDS",
            "UI_CONTENT_VISIBILITY_EVIDENCE_KINDS",
            "UI_CONTENT_VISIBILITY_USER_VISIBLE",
            "UI_CONTENT_VISIBILITY_USER_ON_DEMAND",
            "UI_CONTENT_VISIBILITY_INTERNAL",
            "UI_VISIBLE_SURFACE_PRIORITIES",
            "UIContentVisibilityItem",
            "UIContentVisibilityEvidence",
            "UIContentVisibilityPlan",
            "UIContentVisibilityReport",
            "UIVisibleSurface",
            "UIVisibleSurfaceItem",
            "UIVisibleSurfaceReport",
            "UIRenderEvidence",
            "UIRenderEvidenceSet",
            "UIRenderEvidenceReport",
            "UIGeometryLayoutEvidence",
            "UIGeometryLayoutEvidenceSet",
            "UIGeometryLayoutEvidenceReport",
            "UIHotPathAction",
            "UIColdPathWork",
            "UIStableRegionRule",
            "UIResponsivenessContract",
            "UIResponsivenessContractReport",
            "review_ui_visible_surface",
            "review_ui_content_visibility",
            "ui_content_visibility_candidate_ids_from_field_lifecycle",
            "review_ui_render_evidence",
            "review_ui_geometry_layout_evidence",
            "review_ui_responsiveness_contract",
        )
        for name in new_ui_surface_helpers:
            self.assertIn(name, flowguard.MODELING_HELPER_API)
            self.assertIn(name, flowguard.UI_FLOW_STRUCTURE_ROUTE_API)
            self.assertIn(name, flowguard.__all__)
            self.assertTrue(hasattr(flowguard, name), name)
            self.assertNotIn(name, flowguard.CORE_API)
        new_ui_source_baseline_helpers = (
            "UI_WORK_MODES",
            "UI_SOURCE_TYPES",
            "UI_SOURCE_INTERACTION_KINDS",
            "UI_SOURCE_INTERACTION_REQUIRED_BRANCHES",
            "UI_SOURCE_NO_HANDLER_DISPOSITIONS",
            "UI_SOURCE_TARGET_DISPOSITIONS",
            "UI_SOURCE_CHANGED_DISPOSITIONS",
            "UIWorkModeDeclaration",
            "UISourceBaseline",
            "UISourceBaselineItem",
            "UISourceTargetMapping",
            "UISourceTargetMappingRow",
            "UIObservedSourceAlignment",
            "UISourceBaselineAlignmentReport",
            "UISourceInteractionSemantics",
            "UISourceBaselineInteractionGate",
            "UISourceBaselineInteractionReport",
            "review_ui_source_baseline_alignment",
            "review_ui_source_baseline_interactions",
        )
        for name in new_ui_source_baseline_helpers:
            self.assertIn(name, flowguard.MODELING_HELPER_API)
            self.assertIn(name, flowguard.UI_FLOW_STRUCTURE_ROUTE_API)
            self.assertIn(name, flowguard.__all__)
            self.assertTrue(hasattr(flowguard, name), name)
            self.assertNotIn(name, flowguard.CORE_API)
        new_ui_capability_helpers = (
            "UI_CAPABILITY_KINDS",
            "UI_CAPABILITY_OUTPUT_KINDS",
            "UI_CAPABILITY_RESULT_OUTPUT_KINDS",
            "UIFunctionalCapability",
            "UIFunctionalCapabilityInventory",
            "UICapabilityOutputContract",
            "UICapabilityCoverageBinding",
            "UIFunctionalCapabilityCoverageReport",
            "review_ui_functional_capability_coverage",
        )
        for name in new_ui_capability_helpers:
            self.assertIn(name, flowguard.MODELING_HELPER_API)
            self.assertIn(name, flowguard.UI_FLOW_STRUCTURE_ROUTE_API)
            self.assertIn(name, flowguard.__all__)
            self.assertTrue(hasattr(flowguard, name), name)
            self.assertNotIn(name, flowguard.CORE_API)
        new_ui_human_operability_helpers = (
            "UI_HUMAN_OPERABILITY_EVIDENCE_KINDS",
            "UI_PERCEIVED_ACTIONABLE_ROLES",
            "UI_ACTUAL_ACTIONABLE_ROLES",
            "UI_ACTUAL_NON_ACTIONABLE_ROLES",
            "UI_AFFORDANCE_MISMATCH_DISPOSITIONS",
            "UI_REGION_ROLES",
            "UI_DIALOG_TYPES",
            "UIUserTaskFrame",
            "UIUserTaskCoverageLedger",
            "UIRegionSemanticMap",
            "UIAffordanceContract",
            "UIActionGrammar",
            "UIDialogWindowContract",
            "UIKeyboardFocusContract",
            "UIHumanWalkthroughStep",
            "UIHumanWalkthroughScenario",
            "UIHumanOperabilityAssessment",
            "UIHumanOperabilityReport",
            "review_ui_human_operability",
        )
        for name in new_ui_human_operability_helpers:
            self.assertIn(name, flowguard.MODELING_HELPER_API)
            self.assertIn(name, flowguard.UI_FLOW_STRUCTURE_ROUTE_API)
            self.assertIn(name, flowguard.__all__)
            self.assertTrue(hasattr(flowguard, name), name)
            self.assertNotIn(name, flowguard.CORE_API)
        product_language_helpers = (
            "UIProductConsistencyRule",
            "UIProductSurface",
            "UIProductConsistencyObservation",
            "UIProductConsistencyException",
            "UIProductConsistencyPlan",
            "UIProductConsistencyFinding",
            "UIProductConsistencyReport",
            "UIProductLanguageCaseSeed",
            "UI_PRODUCT_CONSISTENCY_KINDS",
            "UI_PRODUCT_EXCEPTION_KINDS",
            "UI_PRODUCT_CLAIM_SCOPES",
            "review_ui_product_consistency",
            "default_ui_product_language_case_seeds",
        )
        for name in product_language_helpers:
            self.assertIn(name, flowguard.MODELING_HELPER_API)
            self.assertIn(name, flowguard.UI_FLOW_STRUCTURE_ROUTE_API)
            self.assertIn(name, flowguard.__all__)
            self.assertTrue(hasattr(flowguard, name), name)
            self.assertNotIn(name, flowguard.CORE_API)
        self.assertIn("review_ui_interaction_model", flowguard.MODELING_HELPER_API)
        self.assertIn("review_ui_journey_coverage", flowguard.MODELING_HELPER_API)
        self.assertIn("review_ui_implementation_validation", flowguard.MODELING_HELPER_API)
        self.assertIn("review_ui_structure_derivation", flowguard.MODELING_HELPER_API)
        self.assertIn("review_ui_text_hierarchy", flowguard.MODELING_HELPER_API)
        self.assertIn("ModelTestAlignmentPlan", flowguard.MODELING_HELPER_API)
        self.assertIn("ModelCodeTestBindingRow", flowguard.MODELING_HELPER_API)
        self.assertIn("review_model_test_alignment", flowguard.MODELING_HELPER_API)
        self.assertIn("TransitionCoverageCell", flowguard.MODELING_HELPER_API)
        self.assertIn("TransitionCoverageMatrix", flowguard.MODELING_HELPER_API)
        self.assertIn("MODEL_MESH_CLOSURE_RETRY_TEST_KINDS", flowguard.MODELING_HELPER_API)
        self.assertIn("TRANSITION_COVERAGE_SOURCE_MODEL_MESH_CLOSURE", flowguard.MODELING_HELPER_API)
        self.assertIn("model_mesh_closure_to_transition_coverage", flowguard.MODELING_HELPER_API)
        self.assertIn("transition_coverage_to_code_contracts", flowguard.MODELING_HELPER_API)
        self.assertIn("transition_coverage_to_model_obligations", flowguard.MODELING_HELPER_API)
        self.assertIn("ui_interaction_model_to_transition_coverage", flowguard.MODELING_HELPER_API)
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
        self.assertIn("BusinessPathIdentity", flowguard.MODELING_HELPER_API)
        self.assertIn("UsageIntent", flowguard.MODELING_HELPER_API)
        self.assertIn("TopologyDigest", flowguard.MODELING_HELPER_API)
        self.assertIn("TopologyHazardCandidate", flowguard.MODELING_HELPER_API)
        self.assertIn("TopologyHazardReviewPlan", flowguard.MODELING_HELPER_API)
        self.assertIn("TopologyHazardReport", flowguard.MODELING_HELPER_API)
        self.assertIn("infer_topology_digest", flowguard.MODELING_HELPER_API)
        self.assertIn("infer_topology_hazard_plan", flowguard.MODELING_HELPER_API)
        self.assertIn("review_topology_hazards", flowguard.MODELING_HELPER_API)
        self.assertIn("TOPOLOGY_LANDMARK_BUSINESS_PATH_DUPLICATE", flowguard.MODELING_HELPER_API)
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
        self.assertIn("field_lifecycle_template_files", flowguard.EVIDENCE_API)
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
            "ARTIFACT_PAYLOAD_METHOD_AUTOMATED_TEST",
            "ARTIFACT_PAYLOAD_METHOD_BROWSER",
            "ARTIFACT_PAYLOAD_METHOD_DESKTOP",
            "ARTIFACT_PAYLOAD_METHOD_MANUAL",
            "ARTIFACT_PAYLOAD_METHOD_REPLAY",
            "ARTIFACT_PAYLOAD_STATUS_ACCEPTED",
            "ARTIFACT_PAYLOAD_STATUS_REJECTED",
            "ArtifactPayloadCase",
            "ArtifactPayloadContract",
            "ArtifactPayloadEvidence",
            "ArtifactPayloadFinding",
            "ArtifactPayloadValidationReport",
            "CodeBoundaryConformanceReport",
            "CodeBoundaryContract",
            "CodeBoundaryFinding",
            "CodeBoundaryObservation",
            "CodeContract",
            "ClosureEvidenceTarget",
            "TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT",
            "TEST_ASSERTION_SCOPE_INTERNAL_PATH",
            "TEST_ASSERTION_SCOPE_MIXED",
            "TEST_ASSERTION_SCOPE_UNKNOWN",
            "TEST_CLOSURE_ROLE_COUNTEREXAMPLE_REGRESSION",
            "TEST_CLOSURE_ROLE_KNOWN_BAD_REPLAY",
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
            "TEST_EVIDENCE_ROLE_TRANSITION_CELL",
            "TEST_EVIDENCE_ROLE_SUPPORTING_CONTRACT",
            "TEST_EVIDENCE_ROLE_INTEGRATION_SMOKE",
            "ModelCodeTestBindingRow",
            "PythonCodeContractEvidence",
            "PythonTestAssertionEvidence",
            "ContractSourceAuditFinding",
            "ContractSourceAuditReport",
            "audit_python_code_contracts",
            "audit_python_test_assertions",
            "review_artifact_payload_validation",
            "review_code_boundary_conformance",
            "review_python_contract_source_audit",
        )

        for name in expected:
            self.assertIn(name, flowguard.MODELING_HELPER_API)
            self.assertIn(name, flowguard.__all__)
            self.assertTrue(hasattr(flowguard, name), name)
            self.assertNotIn(name, flowguard.CORE_API)

    def test_runtime_gateway_writer_inventory_api_is_public_helper(self):
        expected = (
            "ADOPTION_LEVEL_DESIGN_MODEL",
            "ADOPTION_LEVEL_RUNTIME_GATEWAY",
            "ADOPTION_LEVEL_TEST_ALIGNED",
            "RUNTIME_WRITE_DIRECT",
            "RUNTIME_WRITE_GATEWAY",
            "RuntimeGatewayAdoptionPlan",
            "RuntimeGatewayAdoptionReport",
            "RuntimeGatewayContract",
            "RuntimeGatewayFinding",
            "RuntimeStateSurface",
            "RuntimeWriterInventoryEvidence",
            "RuntimeWriteObservation",
            "review_runtime_gateway_adoption",
        )

        for name in expected:
            self.assertIn(name, flowguard.MODELING_HELPER_API)
            self.assertIn(name, flowguard.__all__)
            self.assertTrue(hasattr(flowguard, name), name)
            self.assertNotIn(name, flowguard.CORE_API)

    def test_model_test_alignment_source_audit_split_keeps_facade_imports(self):
        from flowguard import model_test_alignment_source

        self.assertTrue(hasattr(model_test_alignment_source, "audit_python_code_contracts"))
        self.assertTrue(hasattr(model_test_alignment_source, "audit_python_test_assertions"))
        self.assertTrue(hasattr(model_test_alignment_source, "review_python_contract_source_audit"))
        self.assertTrue(hasattr(flowguard, "audit_python_code_contracts"))
        self.assertTrue(hasattr(flowguard, "audit_python_test_assertions"))
        self.assertTrue(hasattr(flowguard, "review_python_contract_source_audit"))

    def test_transition_coverage_api_is_public_model_test_alignment_helper(self):
        expected = (
            "TransitionCoverageCell",
            "TransitionCoverageMatrix",
            "TRANSITION_COVERAGE_OBLIGATION_PREFIX",
            "TRANSITION_COVERAGE_OBLIGATION_TYPE",
            "TRANSITION_COVERAGE_SOURCE_MODEL",
            "TRANSITION_COVERAGE_SOURCE_UI",
            "TRANSITION_COVERAGE_SOURCE_WORKFLOW",
            "TRANSITION_COVERAGE_SOURCE_LEAF_BOUNDARY",
            "transition_coverage_to_code_contracts",
            "transition_coverage_to_model_obligations",
            "transition_coverage_to_required_leaf_cell_ids",
            "transition_obligation_id",
            "ui_interaction_model_to_transition_coverage",
        )

        for name in expected:
            self.assertIn(name, flowguard.MODELING_HELPER_API)
            self.assertIn(name, flowguard.MODEL_TEST_ALIGNMENT_ROUTE_API)
            self.assertIn(name, flowguard.__all__)
            self.assertTrue(hasattr(flowguard, name), name)
            self.assertNotIn(name, flowguard.CORE_API)

    def test_route_api_registry_groups_public_names(self):
        expected_groups = {
            "model_first_function_flow",
            "existing_model_preflight",
            "behavior_commitment_ledger",
            "architecture_reduction",
            "code_structure_recommendation",
            "model_test_alignment",
            "field_lifecycle_mesh",
            "contract_exhaustion_mesh",
            "ui_flow_structure",
            "model_mesh_maintenance",
            "test_mesh_maintenance",
            "structure_mesh_maintenance",
            "development_process_flow",
            "model_miss_review",
            "model_topology_hazard_review",
        }
        self.assertEqual(expected_groups, set(flowguard.FLOWGUARD_ROUTE_API))
        self.assertEqual(expected_groups, set(flowguard.PUBLIC_FLOWGUARD_ROUTE_GROUPS))

        expected_internal_groups = {
            "flowguard_self_maintenance",
            "template_structure",
            "evidence_field_structure",
            "primary_path_authority",
            "agent_workflow_rehearsal",
            "model_similarity_consolidation",
            "model_maturation_loop",
            "plan_detailing_compiler",
            "maintenance_obligation_memory",
            "maintenance_scan_router",
            "model_angle_deliberation",
            "development_process_simulator",
            "flowguard_closure_contract",
            "risk_evidence_ledger",
            "risk_template_library",
            "state_closure",
        }
        self.assertEqual(expected_internal_groups, set(flowguard.FLOWGUARD_INTERNAL_ROUTE_API))

        for group_name, names in flowguard.FLOWGUARD_ROUTE_API.items():
            with self.subTest(group=group_name):
                self.assertIsInstance(names, tuple)
                self.assertTrue(names)
                for name in names:
                    self.assertIn(name, flowguard.__all__, name)
                    self.assertTrue(hasattr(flowguard, name), name)

        for name in flowguard.EVIDENCE_FIELD_STRUCTURE_API:
            self.assertIn(name, flowguard.EVIDENCE_API)
        for name in flowguard.RISK_TEMPLATE_LIBRARY_API:
            self.assertIn(name, flowguard.MODELING_HELPER_API)
            self.assertIn(name, flowguard.__all__)
            self.assertTrue(hasattr(flowguard, name), name)
            self.assertNotIn(name, flowguard.CORE_API)
        for name in ("TemplateHarvestReview", "review_template_harvest_closure"):
            self.assertIn(name, flowguard.RISK_TEMPLATE_LIBRARY_API)
            self.assertNotIn("risk_template_library", flowguard.ROUTE_STARTER_API)
            self.assertIn(name, flowguard.ROUTE_ADVANCED_API["risk_template_library"])

        for internal_group in expected_internal_groups:
            self.assertNotIn(internal_group, flowguard.ROUTE_STARTER_API)
            self.assertIn(internal_group, flowguard.ROUTE_ADVANCED_API)

    def test_route_profiles_cover_public_route_api(self):
        profiles = flowguard.default_flowguard_route_profiles()
        profile_ids = {profile.route_id for profile in profiles}

        expected_profile_ids = {
            "model_first_function_flow",
            "flowguard_self_maintenance",
            "template_structure",
            "evidence_field_structure",
            "existing_model_preflight",
            "behavior_commitment_ledger",
            "primary_path_authority",
            "model_angle_deliberation",
            "model_maturation_loop",
            "risk_template_library",
            "maintenance_scan_router",
            "maintenance_obligation_memory",
            "field_lifecycle_mesh",
            "contract_exhaustion_mesh",
            "model_similarity_consolidation",
            "architecture_reduction",
            "code_structure_recommendation",
            "structure_mesh_maintenance",
            "model_test_alignment",
            "test_mesh_maintenance",
            "model_mesh_maintenance",
            "development_process_simulator",
            "development_process_flow",
            "risk_evidence_ledger",
            "flowguard_closure_contract",
            "agent_workflow_rehearsal",
            "ui_flow_structure",
            "model_miss_review",
            "plan_detailing_compiler",
            "state_closure",
            "model_topology_hazard_review",
        }
        self.assertEqual(expected_profile_ids, profile_ids)
        by_id = {profile.route_id: profile for profile in profiles}
        for group_id in flowguard.PUBLIC_FLOWGUARD_ROUTE_GROUPS:
            self.assertEqual(flowguard.ROUTE_ROLE_PUBLIC_OWNER, by_id[group_id].route_role)
            self.assertEqual(flowguard.ENTRY_POLICY_DIRECT, by_id[group_id].entry_policy)
        for group_id in flowguard.FLOWGUARD_INTERNAL_ROUTE_API:
            self.assertNotEqual(flowguard.ROUTE_ROLE_PUBLIC_OWNER, by_id[group_id].route_role)
            self.assertNotEqual(flowguard.ENTRY_POLICY_DIRECT, by_id[group_id].entry_policy)

        report = flowguard.review_flowguard_self_maintenance(
            flowguard.SelfMaintenancePlan(
                "api-route-profile-check",
                route_profiles=profiles,
                api_route_group_ids=tuple(flowguard.FLOWGUARD_ROUTE_API),
                ai_profiles=flowguard.default_ai_maintenance_profiles(),
                field_layers=flowguard.default_field_layer_profiles(),
                child_reports=self.self_maintenance_child_reports(),
            )
        )
        self.assertTrue(report.ok, report.format_text())
        self.assertFalse(report.findings, report.format_text())

    def test_contract_exhaustion_route_profile_mentions_cartesian_receipts_and_handoffs(self):
        profiles = {profile.route_id: profile for profile in flowguard.default_flowguard_route_profiles()}
        profile = profiles["contract_exhaustion_mesh"]

        self.assertIn("model axes", profile.minimal_inputs)
        self.assertIn("coverage universe", profile.minimal_inputs)
        self.assertIn("interaction groups", profile.minimal_inputs)
        self.assertIn("combination cases", profile.outputs)
        self.assertIn("coverage shards", profile.outputs)
        self.assertIn("coverage receipts", profile.outputs)
        self.assertIn("fault profiles", profile.outputs)
        self.assertIn("backfeed report", profile.outputs)
        target_ids = {handoff.target_id for handoff in profile.next_actions}
        self.assertIn("flowguard-model-mesh", target_ids)
        self.assertIn("flowguard-test-mesh", target_ids)
        checklist = tuple(profile.metadata["checklist"])
        self.assertTrue(any("declared finite axes" in item for item in checklist))
        self.assertTrue(any("coverage universe" in item for item in checklist))
        self.assertTrue(any("actionable oracle feedback" in item for item in checklist))
        self.assertTrue(any("observed real misses" in item for item in checklist))
        self.assertTrue(any("contract_coverage_shard" in item for item in checklist))

        mta = profiles["model_test_alignment"]
        self.assertIn("contract-exhaustion obligation ids", mta.minimal_inputs)
        self.assertIn("combination obligation coverage", mta.outputs)

        test_mesh = profiles["test_mesh_maintenance"]
        self.assertIn("required shard ids", test_mesh.minimal_inputs)
        self.assertIn("shard evidence", test_mesh.outputs)

        model_mesh = profiles["model_mesh_maintenance"]
        self.assertIn("coverage receipts", model_mesh.minimal_inputs)
        self.assertIn("required child receipt ids", model_mesh.minimal_inputs)
        self.assertIn("coverage receipt status", model_mesh.outputs)

        risk = profiles["risk_evidence_ledger"]
        self.assertIn("cartesian coverage gates", risk.minimal_inputs)
        self.assertIn("coverage gate gaps", risk.outputs)

        miss = profiles["model_miss_review"]
        self.assertIn("combination case id", miss.minimal_inputs)
        self.assertIn("interaction group upgrade", miss.outputs)
        self.assertIn("coverage receipt", miss.outputs)

    def test_contract_exhaustion_api_exports_coverage_universe_helpers(self):
        expected = (
            "ContractCoverageUniverse",
            "ContractCoverageExclusion",
            "ContractFaultProfile",
            "ObservedProblemBackfeed",
            "ObservedProblemBackfeedReport",
            "contract_fault_profiles_from_report",
            "review_observed_problem_backfeed",
        )

        for name in expected:
            self.assertIn(name, flowguard.CONTRACT_EXHAUSTION_MESH_API)
            self.assertIn(name, flowguard.MODELING_HELPER_API)
            self.assertIn(name, flowguard.__all__)
            self.assertTrue(hasattr(flowguard, name), name)

    def test_default_self_maintenance_plan_folds_common_fields(self):
        plan = flowguard.default_flowguard_self_maintenance_plan(
            "default-self-maintenance-plan",
            child_reports=self.self_maintenance_child_reports(),
        )

        self.assertEqual(tuple(flowguard.FLOWGUARD_ROUTE_API), plan.api_route_group_ids)
        self.assertEqual(
            {profile.route_id for profile in flowguard.default_flowguard_route_profiles()},
            {profile.route_id for profile in plan.route_profiles},
        )
        self.assertEqual(set(flowguard.FIELD_LAYERS), {layer.layer_id for layer in plan.field_layers})
        self.assertTrue(plan.ai_profiles)
        self.assertTrue(plan.broad_claim)
        report = flowguard.review_flowguard_self_maintenance(plan)
        self.assertTrue(report.ok, report.format_text())
        self.assertFalse(report.findings, report.format_text())

    def test_broad_self_maintenance_requires_behavior_child_reports(self):
        plan = flowguard.default_flowguard_self_maintenance_plan(
            "missing-behavior-ledger-child-report",
            child_reports=tuple(
                report
                for report in self.self_maintenance_child_reports()
                if report.artifact_kind != "behavior_commitment_ledger"
            ),
        )

        report = flowguard.review_flowguard_self_maintenance(plan)

        self.assertFalse(report.ok, report.format_text())
        self.assertIn("required_child_report_missing", {finding.code for finding in report.findings})
        self.assertIn("behavior_commitment_ledger", {finding.child_id for finding in report.findings})

    def test_route_completeness_reports_missing_route_group(self):
        profiles = flowguard.default_flowguard_route_profiles()
        api_groups = tuple(
            group
            for group in flowguard.FLOWGUARD_ROUTE_API
            if group != "field_lifecycle_mesh"
        )

        findings = flowguard.route_graph_completeness_findings(profiles, api_groups)

        self.assertIn("route_profile_missing_api_group", {finding.code for finding in findings})
        self.assertIn("field_lifecycle_mesh", {finding.owner_route for finding in findings})

    def test_route_completeness_blocks_internal_public_exposure(self):
        profiles = flowguard.default_flowguard_route_profiles()
        api_groups = tuple(flowguard.FLOWGUARD_ROUTE_API) + ("model_angle_deliberation",)

        findings = flowguard.route_graph_completeness_findings(profiles, api_groups)

        self.assertIn("internal_route_exposed_publicly", {finding.code for finding in findings})
        self.assertIn("model_angle_deliberation", {finding.owner_route for finding in findings})

    def test_field_layer_profiles_are_entry_only_and_preserve_expansion(self):
        layers = flowguard.default_field_layer_profiles()
        by_layer = {layer.layer_id: layer for layer in layers}

        self.assertEqual(set(flowguard.FIELD_LAYERS), set(by_layer))
        self.assertEqual("first_read", by_layer[flowguard.FIELD_LAYER_CORE].first_read_exposure)
        self.assertEqual(
            "expand_when_route_runs",
            by_layer[flowguard.FIELD_LAYER_ROUTE_OWNED].first_read_exposure,
        )
        self.assertTrue(by_layer[flowguard.FIELD_LAYER_REPLACEMENT_DISPOSITION].disposition_required)
        self.assertIn(
            "model_test_alignment",
            by_layer[flowguard.FIELD_LAYER_ROUTE_OWNED].expansion_required_for,
        )

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
            "AGENT_WORKFLOW_REHEARSAL_ROUTE_API",
            "AGENT_DEFAULT_API",
            "API_SURFACE",
            "ARCHITECTURE_REDUCTION_ROUTE_API",
            "CODE_STRUCTURE_RECOMMENDATION_ROUTE_API",
            "CONTRACT_EXHAUSTION_MESH_API",
            "CORE_API",
            "DEVELOPMENT_PROCESS_FLOW_ROUTE_API",
            "DEVELOPMENT_PROCESS_SIMULATOR_ROUTE_API",
            "EVIDENCE_FIELD_STRUCTURE_API",
            "EVIDENCE_API",
            "EXISTING_MODEL_PREFLIGHT_ROUTE_API",
            "FLOWGUARD_INTERNAL_ROUTE_API",
            "FLOWGUARD_GOVERNANCE_API",
            "FLOWGUARD_ROUTE_API",
            "BEHAVIOR_COMMITMENT_LOOKUP_API",
            "BEHAVIOR_COMMITMENT_LEDGER_ROUTE_API",
            "FLOWGUARD_CLOSURE_CONTRACT_API",
            "FLOWGUARD_SELF_MAINTENANCE_ROUTE_API",
            "FIELD_LIFECYCLE_MESH_API",
            "MAINTENANCE_OBLIGATION_MEMORY_API",
            "MAINTENANCE_SCAN_ROUTE_API",
            "MODEL_ANGLE_DELIBERATION_API",
            "MODEL_MESH_ROUTE_API",
            "MODEL_MISS_REVIEW_ROUTE_API",
            "MODEL_SIMILARITY_ROUTE_API",
            "MODEL_TEST_ALIGNMENT_ROUTE_API",
            "MODEL_IMPACT_FRESHNESS_API",
            "MODEL_MATURATION_API",
            "PLAN_DETAILING_ROUTE_API",
            "PLAN_INTAKE_ADVANCED_API",
            "PRIMARY_PATH_AUTHORITY_ROUTE_API",
            "PUBLIC_FLOWGUARD_ROUTE_GROUPS",
            "ROUTE_TOPOLOGY_API",
            "RISK_EVIDENCE_LEDGER_ROUTE_API",
            "RISK_TEMPLATE_LIBRARY_API",
            "ROUTE_ADVANCED_API",
            "ROUTE_STARTER_API",
            "PLAN_INTAKE_STARTER_API",
            "PORTABLE_VERIFICATION_API",
            "STATE_CLOSURE_ROUTE_API",
            "SPEC_CONTEXT_API",
            "STRUCTURE_MESH_ROUTE_API",
            "TEST_MESH_ROUTE_API",
            "TOPOLOGY_HAZARD_ROUTE_API",
            "UI_FLOW_STRUCTURE_ROUTE_API",
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
        expected.extend(self.iter_api_surface_names())
        expected.extend(expected_supplement)

        self.assertEqual(set(flowguard.__all__), set(expected))
        self.assertEqual(len(flowguard.__all__), len(set(flowguard.__all__)))
        for name in expected_supplement:
            self.assertTrue(hasattr(flowguard, name), name)


if __name__ == "__main__":
    unittest.main()
