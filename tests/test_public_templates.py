import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flowguard.templates import (
    closure_contract_template_files,
    code_structure_recommendation_template_files,
    development_process_flow_template_files,
    existing_model_preflight_template_files,
    layered_boundary_proof_template_files,
    model_miss_review_template_files,
    model_similarity_consolidation_template_files,
    model_test_alignment_template_files,
    plan_detailing_template_files,
    project_adoption_template_files,
    project_template_files,
    risk_evidence_ledger_template_files,
    risk_intent_template_files,
    runtime_path_evidence_template_files,
    structure_mesh_template_files,
    test_mesh_template_files,
    topology_hazard_template_files,
    ui_flow_structure_template_files,
    workflow_step_contracts_template_files,
    write_template_files,
)


ROOT = Path(__file__).resolve().parents[1]

PUBLIC_TEMPLATE_FACTORIES = (
    project_template_files,
    risk_intent_template_files,
    plan_detailing_template_files,
    model_miss_review_template_files,
    model_test_alignment_template_files,
    code_structure_recommendation_template_files,
    existing_model_preflight_template_files,
    model_similarity_consolidation_template_files,
    risk_evidence_ledger_template_files,
    runtime_path_evidence_template_files,
    layered_boundary_proof_template_files,
    closure_contract_template_files,
    ui_flow_structure_template_files,
    development_process_flow_template_files,
    workflow_step_contracts_template_files,
    test_mesh_template_files,
    structure_mesh_template_files,
    topology_hazard_template_files,
)

TEMPLATE_CLI_COMMANDS = {
    "project-template": "project",
    "project-adoption-template": "project_adoption",
    "risk-intent-template": "risk_intent_check_plan",
    "plan-detailing-template": "plan_detailing",
    "model-miss-template": "model_miss_review",
    "model-test-alignment-template": "model_test_alignment",
    "runtime-path-evidence-template": "runtime_path_evidence",
    "code-structure-recommendation-template": "code_structure_recommendation",
    "existing-model-preflight-template": "existing_model_preflight",
    "model-similarity-template": "model_similarity_consolidation",
    "risk-evidence-ledger-template": "risk_evidence_ledger",
    "layered-boundary-proof-template": "layered_boundary_proof",
    "closure-contract-template": "closure_contract",
    "ui-flow-structure-template": "ui_flow_structure",
    "development-process-flow-template": "development_process_flow",
    "workflow-step-contracts-template": "workflow_step_contracts",
    "test-mesh-template": "test_mesh",
    "structure-mesh-template": "structure_mesh",
    "maintenance-scan-template": "maintenance_scan",
    "topology-hazard-template": "model_topology_hazard_review",
}


def _template_env():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return env


class PublicTemplateTests(unittest.TestCase):
    def assert_risk_purpose_header(self, text):
        self.assertIn("FlowGuard Risk Purpose Header", text)
        self.assertIn("Created with FlowGuard:", text)
        self.assertIn("https://github.com/liuyingxuvka/FlowGuard", text)
        self.assertIn("Purpose:", text)
        self.assertIn("Guards against:", text)
        self.assertIn("Use before editing:", text)
        self.assertIn("Run:", text)

    def run_written_template(self, files, run_dir_parts):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_template_files(root, files)
            result = subprocess.run(
                [sys.executable, "run_checks.py"],
                cwd=root.joinpath(*run_dir_parts),
                env=_template_env(),
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        return result.stdout

    def test_project_template_executes(self):
        output = self.run_written_template(project_template_files(), ())
        self.assertIn("status: OK", output)
        self.assertIn("stored", output)
        self.assertIn("rejected_duplicate", output)

    def test_template_text_is_route_scoped_behind_public_facade(self):
        template_text_root = ROOT / "flowguard" / "template_text"
        route_modules = {path.stem for path in template_text_root.glob("*.py") if path.name != "__init__.py"}

        self.assertIn("ui_flow_structure", route_modules)
        self.assertIn("model_similarity_consolidation", route_modules)
        self.assertIn("risk_evidence_ledger", route_modules)
        self.assertLess(len((ROOT / "flowguard" / "templates.py").read_text(encoding="utf-8").splitlines()), 1000)
        self.assertIn("UIInteractionModel", (template_text_root / "ui_flow_structure.py").read_text(encoding="utf-8"))

    def test_risk_intent_template_executes(self):
        output = self.run_written_template(
            risk_intent_template_files(),
            (".flowguard", "risk_intent_check_plan"),
        )
        self.assertIn("flowguard summary", output)
        self.assertIn("risk_intent", output)

    def test_plan_detailing_template_executes(self):
        output = self.run_written_template(
            plan_detailing_template_files(),
            (".flowguard", "plan_detailing"),
        )
        self.assertIn("flowguard plan-detailing template", output)
        self.assertIn("flowguard plan detailing review", output)
        self.assertIn("missing_failure_branches", output)
        self.assertIn("rework_gate_missing", output)
        self.assertIn("missing_validations", output)

    def test_plan_detailing_template_teaches_detail_rows(self):
        files = plan_detailing_template_files()
        combined = "\n".join(file.content for file in files)

        self.assertIn("PlanDetail", combined)
        self.assertIn("PlanDetailStep", combined)
        self.assertIn("PlanDetailValidation", combined)
        self.assertIn("PlanDetailFailureBranch", combined)
        self.assertIn("plan_detail_to_development_process", combined)
        self.assertIn("plan_detail_to_step_contracts", combined)
        self.assertIn("FlowGuard Risk Purpose Header", combined)

    def test_model_miss_review_template_executes(self):
        output = self.run_written_template(
            model_miss_review_template_files(),
            (".flowguard", "model_miss_review"),
        )
        self.assertIn("correct_model_miss_review: PASS", output)
        self.assertIn("expected violations observed: 6", output)

    def test_model_miss_review_template_requires_generalized_bad_case(self):
        files = model_miss_review_template_files()
        combined = "\n".join(file.content for file in files)

        self.assertIn("generalized_bad_case_in_scope", combined)
        self.assertIn("generalized_bad_case_represented_in_model", combined)
        self.assertIn("known_bug_used_as_holdout", combined)
        self.assertIn("represent_generalized_bad_case", combined)
        self.assertIn("record_known_bug_holdout", combined)
        self.assertIn("fix_validation_requires_generalized_bad_case", combined)
        self.assertIn("fix_validation_requires_known_bug_holdout_role", combined)
        self.assertIn("fix_validation_requires_same_class_test_evidence", combined)
        self.assertIn("point_fix_only_without_generalized_bad_case", combined)
        self.assertIn("validate_without_known_bug_holdout_role", combined)
        self.assertIn("validate_without_same_class_test_evidence", combined)
        self.assertIn("same_class_test_evidence_added", combined)
        self.assertIn("model_test_alignment_rerun", combined)
        self.assertIn("recurring_family_detected", combined)
        self.assertIn("defect_family_gate_promoted", combined)
        self.assertIn("defect_family_gate_reviewed", combined)
        self.assertIn("recurring_family_requires_defect_family_gate", combined)
        self.assertIn("validate_recurring_without_defect_family_gate", combined)
        self.assertIn("broken_point_fix_only_validation", combined)
        self.assertIn("same-class generalized bad case", combined)

    def test_model_test_alignment_template_executes(self):
        output = self.run_written_template(
            model_test_alignment_template_files(),
            (".flowguard", "model_test_alignment"),
        )
        self.assertIn("flowguard model-test alignment", output)
        self.assertIn("missing_required_test_kind", output)
        self.assertIn("missing_same_class_test_evidence", output)

    def test_model_test_alignment_template_covers_code_contracts_without_mesh_helpers(self):
        files = model_test_alignment_template_files()
        combined = "\n".join(file.content for file in files)

        self.assertIn("does not use TestMesh, StructureMesh, or ModelMesh", combined)
        self.assertIn("plain model obligations", combined)
        self.assertIn("plain test", combined)
        self.assertIn("evidence", combined)
        self.assertIn("code external contracts", combined)
        self.assertIn("CodeContract", combined)
        self.assertIn("CodeBoundaryContract", combined)
        self.assertIn("CodeBoundaryObservation", combined)
        self.assertIn("covered code contract ids", combined)
        self.assertIn("review_code_boundary_conformance", combined)
        self.assertIn("audit_python_code_contracts", combined)
        self.assertIn("audit_python_test_assertions", combined)
        self.assertIn("review_python_contract_source_audit", combined)
        self.assertIn("TEST_CLOSURE_ROLE_OBSERVED_REGRESSION", combined)
        self.assertIn("TEST_CLOSURE_ROLE_SAME_CLASS_GENERALIZED", combined)
        self.assertIn("same-class evidence", combined)
        self.assertIn("representative unknown/other", combined)
        self.assertIn("state closure evidence", combined)
        self.assertIn("TestResultReuseTicket", combined)
        self.assertIn("result_reused=True", combined)
        self.assertIn("TransitionCoverageMatrix", combined)
        self.assertIn("TransitionCoverageCell", combined)
        self.assertIn("TEST_EVIDENCE_ROLE_TRANSITION_CELL", combined)
        self.assertIn("transition_coverage_to_model_obligations", combined)
        self.assertNotIn("review_hierarchical_mesh", combined)
        self.assertNotIn("review_test_mesh", combined)
        self.assertNotIn("review_structure_mesh", combined)

    def test_model_test_alignment_template_teaches_conservative_python_source_audit(self):
        files = model_test_alignment_template_files()
        combined = "\n".join(file.content for file in files)

        self.assertIn("audit_python_code_contracts", combined)
        self.assertIn("audit_python_test_assertions", combined)
        self.assertIn("review_python_contract_source_audit", combined)
        self.assertIn("PythonCodeContractEvidence", combined)
        self.assertIn("PythonTestAssertionEvidence", combined)
        self.assertIn("function signatures, return values, raises, assignments, and calls", combined)
        self.assertIn("tests must call the declared code contract symbol", combined)
        self.assertIn("assert or unittest assertion", combined)
        self.assertIn("conservative source audit", combined)

    def test_runtime_path_evidence_template_executes_and_prints_model_target(self):
        output = self.run_written_template(
            runtime_path_evidence_template_files(),
            (".flowguard", "runtime_path_evidence"),
        )

        self.assertIn("flowguard runtime path evidence", output)
        self.assertIn("flowguard.runtime_path", output)
        self.assertIn("model=checkout.leaf", output)
        self.assertIn("model_path=.flowguard/checkout_leaf/model.py", output)
        self.assertIn("runtime_node_missing_observation", output)

    def test_test_mesh_template_executes(self):
        output = self.run_written_template(
            test_mesh_template_files(),
            (".flowguard", "test_mesh"),
        )
        self.assertIn("flowguard test mesh", output)
        self.assertIn("release_obligations", output)
        self.assertIn("stale_test_evidence", output)

    def test_test_mesh_template_teaches_parent_child_hierarchy(self):
        files = test_mesh_template_files()
        combined = "\n".join(file.content for file in files)

        self.assertIn("parent test gate", combined)
        self.assertIn("child suites/scripts", combined)
        self.assertIn("parallel to ModelMesh and StructureMesh", combined)
        self.assertIn("one giant parent graph", combined)
        self.assertIn("model-derived split", combined)
        self.assertIn("TestResultReuseTicket", combined)
        self.assertIn("result_reused=True", combined)
        self.assertIn("TransitionCoverageMatrix", combined)
        self.assertIn("transition_coverage_to_required_leaf_cell_ids", combined)
        self.assertIn("required_leaf_cell_ids", combined)

    def test_code_structure_recommendation_template_executes(self):
        output = self.run_written_template(
            code_structure_recommendation_template_files(),
            (".flowguard", "code_structure_recommendation"),
        )
        self.assertIn("flowguard code structure recommendation", output)
        self.assertIn("missing_source_model", output)

    def test_ui_flow_structure_template_executes(self):
        output = self.run_written_template(
            ui_flow_structure_template_files(),
            (".flowguard", "ui_flow_structure"),
        )
        self.assertIn("flowguard UI interaction model", output)
        self.assertIn("flowguard UI journey coverage", output)
        self.assertIn("flowguard UI implementation validation", output)
        self.assertIn("flowguard UI structure derivation", output)
        self.assertIn("flowguard UI text hierarchy", output)
        self.assertIn("missing_state_availability_matrix", output)
        self.assertIn("feature_entry_point_not_declared", output)
        self.assertIn("missing_implementation_run_for_journey", output)
        self.assertIn("source_interaction_model_not_reviewed", output)
        self.assertIn("text_role_too_prominent", output)

    def test_structure_mesh_template_executes(self):
        output = self.run_written_template(
            structure_mesh_template_files(),
            (".flowguard", "structure_mesh"),
        )
        self.assertIn("flowguard structure mesh", output)
        self.assertIn("release_obligations", output)
        self.assertIn("duplicate_state_owner", output)

    def test_topology_hazard_template_executes(self):
        output = self.run_written_template(
            topology_hazard_template_files(),
            (".flowguard", "model_topology_hazard_review"),
        )
        self.assertIn("flowguard topology hazard review", output)
        self.assertIn("topology_hazard_blocked", output)
        self.assertIn("unresolved_hazard_ids", output)

    def test_development_process_flow_template_executes(self):
        output = self.run_written_template(
            development_process_flow_template_files(),
            (".flowguard", "development_process_flow"),
        )
        self.assertIn("flowguard development process flow", output)
        self.assertIn("release_claim_with_stale_evidence", output)
        self.assertIn("revalidation", output)

    def test_development_process_flow_template_keeps_sibling_boundary(self):
        files = development_process_flow_template_files()
        combined = "\n".join(file.content for file in files)

        self.assertIn("sibling sub-protocol", combined)
        self.assertIn("does not inspect", combined)
        self.assertIn("does not make FlowGuard a task orchestrator", combined)
        self.assertIn("review_auto_mesh_splits()", combined)
        self.assertIn("automatic ModelMesh/TestMesh split triggers", combined)
        self.assertIn("producer_route=\"test_mesh_maintenance\"", combined)
        self.assertIn("FlowGuard Risk Purpose Header", combined)

    def test_workflow_step_contracts_template_executes(self):
        output = self.run_written_template(
            workflow_step_contracts_template_files(),
            (".flowguard", "workflow_step_contracts"),
        )
        self.assertIn("flowguard workflow step contracts", output)
        self.assertIn("missing_claim_receipt", output)
        self.assertIn("process_requirements", output)
        self.assertIn("model_obligations", output)

    def test_workflow_step_contracts_template_teaches_receipts(self):
        files = workflow_step_contracts_template_files()
        combined = "\n".join(file.content for file in files)

        self.assertIn("WorkflowStepContract", combined)
        self.assertIn("requires_receipts", combined)
        self.assertIn("produces_receipts", combined)
        self.assertIn("invalidates_receipts", combined)
        self.assertIn("required_for_claims", combined)
        self.assertIn("step_contracts_to_validation_requirements", combined)
        self.assertIn("step_contracts_to_model_obligations", combined)
        self.assertIn("FlowGuard Risk Purpose Header", combined)

    def test_existing_model_preflight_template_executes(self):
        output = self.run_written_template(
            existing_model_preflight_template_files(),
            (".flowguard", "existing_model_preflight"),
        )
        self.assertIn("flowguard existing model preflight", output)
        self.assertIn("duplicate_boundary_risk_unresolved", output)

    def test_model_similarity_consolidation_template_executes(self):
        output = self.run_written_template(
            model_similarity_consolidation_template_files(),
            (".flowguard", "model_similarity_consolidation"),
        )
        self.assertIn("flowguard model similarity consolidation", output)
        self.assertIn("same_family_variant", output)
        self.assertIn("maintenance_group", output)
        self.assertIn("change_impact", output)
        self.assertIn("shared_behavior_tests", output)
        self.assertIn("variant_behavior_tests", output)
        self.assertIn("missing_current_similarity_evidence", output)
        self.assertIn("false_friend", output)
        combined = "\n".join(file.content for file in model_similarity_consolidation_template_files())
        self.assertIn("Basic Path", combined)
        self.assertIn("Full Schema Path", combined)
        self.assertIn("SimilarityHandoff", combined)

    def test_risk_evidence_ledger_template_executes(self):
        output = self.run_written_template(
            risk_evidence_ledger_template_files(),
            (".flowguard", "risk_evidence_ledger"),
        )
        self.assertIn("flowguard risk evidence ledger", output)
        self.assertIn("internal_path_only_evidence", output)
        self.assertIn("proof_evidence_not_passing", output)
        self.assertIn("missing_defect_family_gate", output)
        self.assertIn("missing_model_split_gate", output)
        self.assertIn("open_maintenance_obligation", output)
        self.assertIn("defect-family", output)

    def test_layered_boundary_proof_template_executes(self):
        output = self.run_written_template(
            layered_boundary_proof_template_files(),
            (".flowguard", "layered_boundary_proof"),
        )
        self.assertIn("flowguard layered boundary proof", output)
        self.assertIn("parent_coverage_gap", output)
        self.assertIn("leaf_cell_extra_output", output)

    def test_layered_boundary_proof_template_teaches_four_tables(self):
        files = layered_boundary_proof_template_files()
        combined = "\n".join(file.content for file in files)

        self.assertIn("Parent coverage", combined)
        self.assertIn("Child disjointness", combined)
        self.assertIn("Child reattachment", combined)
        self.assertIn("Leaf boundary matrix", combined)
        self.assertIn("Input x State", combined)

    def test_closure_contract_template_executes(self):
        output = self.run_written_template(
            closure_contract_template_files(),
            (".flowguard", "closure_contract"),
        )
        self.assertIn("flowguard closure contract", output)
        self.assertIn("flowguard_closure_full_confidence", output)
        self.assertIn("flowguard_closure_blocked", output)
        self.assertIn("runtime_trace_unmapped_model_obligation", output)

    def test_closure_contract_template_teaches_final_coordinator(self):
        files = closure_contract_template_files()
        combined = "\n".join(file.content for file in files)

        self.assertIn("final coordinator", combined)
        self.assertIn("runtime traces", combined)
        self.assertIn("same-class", combined)
        self.assertIn("runtime gateway inventory", combined)
        self.assertIn("Risk Evidence Ledger", combined)

    def test_public_model_templates_include_risk_purpose_headers(self):
        for factory in PUBLIC_TEMPLATE_FACTORIES:
            with self.subTest(factory=factory.__name__):
                model_file = next(file for file in factory() if file.path.endswith("model.py"))
                self.assert_risk_purpose_header(model_file.content)

    def test_project_adoption_template_includes_version_gate_materials(self):
        files = project_adoption_template_files()
        paths = {file.path for file in files}
        combined = "\n".join(file.content for file in files)

        self.assertIn("AGENTS.md", paths)
        self.assertIn(".flowguard/project.toml", paths)
        self.assertIn("docs/flowguard_adoption_log.md", paths)
        self.assertIn("https://github.com/liuyingxuvka/FlowGuard", combined)
        self.assertIn("project-audit", combined)
        self.assertIn("project-upgrade", combined)
        self.assertIn("latest-schema-first", combined)
        self.assertIn("artifact/model/test upgrade scanning", combined)
        self.assertIn("adopted_package_version", combined)
        self.assertIn("schema_version", combined)

    def test_template_cli_prints_and_writes_new_templates(self):
        for command, template_name in TEMPLATE_CLI_COMMANDS.items():
            help_result = subprocess.run(
                [sys.executable, "-m", "flowguard", command, "--help"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, help_result.returncode, help_result.stderr)
            self.assertIn("--output", help_result.stdout)
            self.assertIn("--force", help_result.stdout)

            printed = subprocess.run(
                [sys.executable, "-m", "flowguard", command],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, printed.returncode, printed.stderr)
            data = json.loads(printed.stdout)
            self.assertEqual(template_name, data["template"])
            self.assertTrue(data["files"])

            with tempfile.TemporaryDirectory() as directory:
                written = subprocess.run(
                    [sys.executable, "-m", "flowguard", command, "--output", directory],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(0, written.returncode, written.stderr)
                report = json.loads(written.stdout)
                self.assertEqual("flowguard_template_write", report["artifact_type"])
                self.assertEqual(template_name, report["template"])

    def test_public_templates_do_not_contain_local_project_markers(self):
        private_markers = (
            "C:\\Users",
            Path.home().name,
            "FlowGuardProjectAutopilot",
            "FlowPilot",
            "Cockpit",
            "heartbeat",
        )
        for factory in PUBLIC_TEMPLATE_FACTORIES + (project_adoption_template_files,):
            with self.subTest(factory=factory.__name__):
                for file in factory():
                    for marker in private_markers:
                        self.assertNotIn(marker, file.content)


if __name__ == "__main__":
    unittest.main()
