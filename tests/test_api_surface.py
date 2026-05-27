import unittest

import flowguard


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
        self.assertIn("ChildBoundaryChangeSummary", flowguard.MODELING_HELPER_API)
        self.assertIn("summarize_child_boundary_change", flowguard.MODELING_HELPER_API)
        self.assertIn("LayeredBoundaryProofPlan", flowguard.MODELING_HELPER_API)
        self.assertIn("LeafBoundaryMatrixCell", flowguard.MODELING_HELPER_API)
        self.assertIn("review_layered_boundary_proof", flowguard.MODELING_HELPER_API)
        self.assertIn("ObservableArchitectureContract", flowguard.MODELING_HELPER_API)
        self.assertIn("ArchitectureReductionCandidate", flowguard.MODELING_HELPER_API)
        self.assertIn("ArchitectureReductionPlan", flowguard.MODELING_HELPER_API)
        self.assertIn("review_architecture_reduction", flowguard.MODELING_HELPER_API)
        self.assertNotIn("review_code_structure_recommendation", flowguard.CORE_API)
        self.assertNotIn("review_ui_interaction_model", flowguard.CORE_API)
        self.assertNotIn("review_ui_journey_coverage", flowguard.CORE_API)
        self.assertNotIn("review_ui_implementation_validation", flowguard.CORE_API)
        self.assertNotIn("review_model_test_alignment", flowguard.CORE_API)
        self.assertNotIn("summarize_child_boundary_change", flowguard.CORE_API)
        self.assertIn("build_executable_corpus_report", flowguard.EVIDENCE_API)
        self.assertIn("build_evidence_baseline_report", flowguard.EVIDENCE_API)
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


if __name__ == "__main__":
    unittest.main()
