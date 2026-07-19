import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flowguard import (
    behavior_commitment_ledger_from_mapping,
    behavior_commitment_ledger_to_mapping,
)
from flowguard.templates import (
    behavior_commitment_ledger_template_files,
    closure_contract_template_files,
    code_structure_recommendation_template_files,
    development_process_flow_template_files,
    existing_model_preflight_template_files,
    field_lifecycle_template_files,
    layered_boundary_proof_template_files,
    maintenance_workflow_template_files,
    model_angle_deliberation_template_files,
    model_miss_review_full_template_files,
    model_miss_review_template_files,
    model_similarity_consolidation_template_files,
    model_test_alignment_full_template_files,
    model_test_alignment_template_files,
    plan_detailing_template_files,
    primary_path_authority_template_files,
    project_adoption_template_files,
    project_template_files,
    risk_evidence_ledger_template_files,
    risk_intent_template_files,
    risk_template_library_template_files,
    runtime_path_evidence_template_files,
    spec_context_template_files,
    structure_mesh_template_files,
    test_mesh_template_files as mesh_template_files_factory,
    topology_hazard_template_files,
    ui_flow_structure_full_template_files,
    ui_flow_structure_template_files,
    workflow_step_contracts_template_files,
    write_template_files,
)


ROOT = Path(__file__).resolve().parents[1]

PUBLIC_TEMPLATE_FACTORIES = (
    project_template_files,
    risk_intent_template_files,
    risk_template_library_template_files,
    plan_detailing_template_files,
    behavior_commitment_ledger_template_files,
    primary_path_authority_template_files,
    model_miss_review_template_files,
    model_test_alignment_template_files,
    code_structure_recommendation_template_files,
    existing_model_preflight_template_files,
    model_angle_deliberation_template_files,
    field_lifecycle_template_files,
    model_similarity_consolidation_template_files,
    risk_evidence_ledger_template_files,
    runtime_path_evidence_template_files,
    layered_boundary_proof_template_files,
    closure_contract_template_files,
    ui_flow_structure_template_files,
    development_process_flow_template_files,
    workflow_step_contracts_template_files,
    mesh_template_files_factory,
    structure_mesh_template_files,
    topology_hazard_template_files,
    spec_context_template_files,
)

TEMPLATE_CLI_COMMANDS = {
    "project-template": "project",
    "project-adoption-template": "project_adoption",
    "spec-context-template": "spec_context",
    "risk-intent-template": "risk_intent_check_plan",
    "risk-template-library-template": "risk_template_library",
    "plan-detailing-template": "plan_detailing",
    "behavior-commitment-ledger-template": "behavior_commitment_ledger",
    "primary-path-authority-template": "primary_path_authority",
    "model-miss-template": "model_miss_review",
    "model-miss-full-template": "model_miss_review_full",
    "model-test-alignment-template": "model_test_alignment",
    "model-test-alignment-full-template": "model_test_alignment_full",
    "runtime-path-evidence-template": "runtime_path_evidence",
    "code-structure-recommendation-template": "code_structure_recommendation",
    "existing-model-preflight-template": "existing_model_preflight",
    "model-angle-template": "model_angle_deliberation",
    "field-lifecycle-template": "field_lifecycle",
    "model-similarity-template": "model_similarity_consolidation",
    "risk-evidence-ledger-template": "risk_evidence_ledger",
    "layered-boundary-proof-template": "layered_boundary_proof",
    "closure-contract-template": "closure_contract",
    "ui-flow-structure-template": "ui_flow_structure",
    "ui-flow-structure-full-template": "ui_flow_structure_full",
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
        self.assertIn("completed_with_evidence", output)
        self.assertIn("rejected_duplicate", output)
        self.assertIn("known_bad_without_evidence_rejected: yes", output)

    def test_public_run_templates_use_formal_entry_not_direct_explorer(self):
        for factory in PUBLIC_TEMPLATE_FACTORIES + (maintenance_workflow_template_files,):
            with self.subTest(factory=factory.__name__):
                for file in factory():
                    if file.path.endswith("run_checks.py"):
                        self.assertNotIn("Explorer(", file.content)
                        self.assertNotIn("from flowguard import Explorer", file.content)

    def test_template_text_is_route_scoped_behind_public_facade(self):
        template_text_root = ROOT / "flowguard" / "template_text"
        route_modules = {path.stem for path in template_text_root.glob("*.py") if path.name != "__init__.py"}

        self.assertIn("ui_flow_structure", route_modules)
        self.assertIn("model_similarity_consolidation", route_modules)
        self.assertIn("risk_evidence_ledger", route_modules)
        self.assertLess(len((ROOT / "flowguard" / "templates.py").read_text(encoding="utf-8").splitlines()), 1000)
        self.assertIn("UIInteractionModel", (template_text_root / "ui_flow_structure.py").read_text(encoding="utf-8"))

    def test_active_ui_guidance_does_not_hardcode_specific_source_technology(self):
        forbidden_terms = (
            "MATLAB",
            "matlab",
            "uigetfile",
            "uigetdir",
            "winopen",
            "MATLABBaselineCallbackGate",
            "MATLABCallbackSemantics",
            "review_matlab_baseline_callback_gate",
            "matlab_callback",
            "baseline_callback",
            "covered_callback_ids",
            "UI_EVIDENCE_ROLE_BASELINE_SEMANTICS",
            "ui_baseline_semantics",
        )
        roots = (ROOT / "flowguard", ROOT / "docs", ROOT / ".agents" / "skills", ROOT / "openspec" / "changes")
        suffixes = {".py", ".md", ".txt", ".toml", ".yaml", ".yml", ".json"}
        ignored_parts = {
            ".git",
            "__pycache__",
            "archive",
        }
        ignored_names = {
            "CHANGELOG.md",
            "flowguard_adoption_log.md",
        }
        offenders = []
        for root in roots:
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix not in suffixes:
                    continue
                if ignored_parts.intersection(path.parts) or path.name in ignored_names:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                hits = [term for term in forbidden_terms if term in text]
                if hits:
                    offenders.append(f"{path.relative_to(ROOT)}: {', '.join(hits)}")

        self.assertEqual([], offenders)

    def test_risk_intent_template_executes(self):
        output = self.run_written_template(
            risk_intent_template_files(),
            (".flowguard", "risk_intent_check_plan"),
        )
        self.assertIn("flowguard summary", output)
        self.assertIn("risk_intent", output)

    def test_risk_template_library_template_executes(self):
        output = self.run_written_template(
            risk_template_library_template_files(),
            (".flowguard", "risk_template_library"),
        )
        self.assertIn("flowguard risk template search", output)
        self.assertIn("completion_requires_evidence", output)
        self.assertIn("flowguard minimum valuable model review", output)
        self.assertIn("flowguard risk template harvest", output)
        self.assertIn("flowguard template harvest closure", output)

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

    def test_behavior_commitment_ledger_template_executes(self):
        output = self.run_written_template(
            behavior_commitment_ledger_template_files(),
            (".flowguard", "behavior_commitment_ledger"),
        )
        self.assertIn("flowguard behavior commitment ledger", output)
        self.assertIn("full_inventory_registered: yes", output)
        self.assertIn("behavior_commitment_coverage_green", output)

    def test_behavior_commitment_template_has_one_canonical_ledger_authority(self):
        files = behavior_commitment_ledger_template_files()
        by_path = {file.path: file.content for file in files}

        self.assertIn(".flowguard/behavior_commitment_ledger/ledger.json", by_path)
        payload = json.loads(by_path[".flowguard/behavior_commitment_ledger/ledger.json"])
        canonical = behavior_commitment_ledger_from_mapping(payload)
        self.assertEqual(payload, behavior_commitment_ledger_to_mapping(canonical))
        commitment = payload["ledger"]["commitments"][0]
        self.assertEqual("product_runtime", commitment["behavior_plane"])
        self.assertEqual("end_user", commitment["actor_kind"])
        self.assertEqual("intent:run-primary-workflow", commitment["business_intent_id"])
        model_text = by_path[".flowguard/behavior_commitment_ledger/model.py"]
        self.assertIn("load_behavior_commitment_ledger", model_text)
        self.assertNotIn("BehaviorCommitment(", model_text)

    def test_primary_path_authority_template_executes(self):
        output = self.run_written_template(
            primary_path_authority_template_files(),
            (".flowguard", "primary_path_authority"),
        )
        self.assertIn("Primary Path Authority checks passed", output)
        self.assertIn("primary_path_authority_green", output)

    def test_model_miss_review_template_executes(self):
        output = self.run_written_template(
            model_miss_review_template_files(),
            (".flowguard", "model_miss_review"),
        )
        self.assertIn("correct_model_miss_review: PASS", output)
        self.assertIn("expected violations observed: 7", output)
        self.assertIn("root_cause_backpropagated", output)
        self.assertIn("same_class_test_evidence_added", output)
        self.assertIn("owner_code_contract_bound", output)
        self.assertIn("replay_or_negative_check_added", output)
        self.assertIn("ui_promised_capability_miss_not_classified", output)

    def test_model_miss_review_template_is_compact_but_preserves_gates(self):
        files = model_miss_review_template_files()
        combined = "\n".join(file.content for file in files)

        self.assertIn("root_cause_backpropagated", combined)
        self.assertIn("owner_code_contract_bound", combined)
        self.assertIn("legacy_path_disposition_recorded", combined)
        self.assertIn("same_class_test_evidence_added", combined)
        self.assertIn("replay_or_negative_check_added", combined)
        self.assertIn("fix_validation_requires_root_cause_backpropagation", combined)
        self.assertIn("validate_without_root_cause_backpropagation", combined)
        self.assertIn("point_fix_only_without_same_class_test", combined)
        self.assertIn("validate_without_owner_code_contract", combined)
        self.assertIn("ui_promised_capability_missing_after_green_claim", combined)
        self.assertIn("missing_same_class_ui_capability_scan", combined)
        self.assertIn("missing_same_plane_behavior_lookup", combined)
        self.assertIn("existing_commitment_reused_or_gap_registered", combined)
        self.assertIn("cross_plane_context_promoted_to_primary", combined)
        self.assertLessEqual(next(file for file in files if file.path.endswith("model.py")).content.count("\n"), 140)

    def test_model_miss_full_template_keeps_deep_review_material(self):
        files = model_miss_review_full_template_files()
        combined = "\n".join(file.content for file in files)

        self.assertIn("generalized_bad_case_in_scope", combined)
        self.assertIn("generalized_bad_case_represented_in_model", combined)
        self.assertIn("known_bug_used_as_holdout", combined)
        self.assertIn("record_known_bug_holdout", combined)
        self.assertIn("legacy_path_disposition_recorded", combined)
        self.assertIn("model_test_alignment_rerun", combined)
        self.assertIn("recurring_family_detected", combined)
        self.assertIn("defect_family_gate_promoted", combined)
        self.assertIn("defect_family_gate_reviewed", combined)
        self.assertIn("recurring_family_requires_defect_family_gate", combined)
        self.assertIn("validate_recurring_without_defect_family_gate", combined)
        self.assertIn("broken_point_fix_only_validation", combined)
        self.assertIn("ContractExhaustionMesh same-class case", combined)

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

        self.assertIn("plain model obligations", combined)
        self.assertIn("plain test", combined)
        self.assertIn("evidence", combined)
        self.assertIn("owner code external contracts", combined)
        self.assertIn("CodeContract", combined)
        self.assertIn("CompactAlignmentPlan", combined)
        self.assertIn("same_class_or_negative_test_present", combined)
        self.assertIn("replay_evidence_id", combined)
        self.assertIn("missing_artifact_payload_pack", combined)
        self.assertIn("synthetic payload case on real surface", combined)
        self.assertIn("missing_artifact_payload_execution_proof", combined)
        self.assertIn("payload_evidence_ref", combined)
        self.assertIn("missing_required_test_kind", combined)
        self.assertIn("missing_same_class_test_evidence", combined)
        self.assertIn("model-test-alignment-full-template", combined)
        self.assertLessEqual(next(file for file in files if file.path.endswith("model.py")).content.count("\n"), 130)
        self.assertNotIn("optional code external contracts", combined)
        self.assertNotIn("review_hierarchical_mesh", combined)
        self.assertNotIn("review_test_mesh", combined)
        self.assertNotIn("review_structure_mesh", combined)

    def test_model_test_alignment_full_template_teaches_conservative_python_source_audit(self):
        files = model_test_alignment_full_template_files()
        combined = "\n".join(file.content for file in files)

        self.assertIn("CodeBoundaryContract", combined)
        self.assertIn("CodeBoundaryObservation", combined)
        self.assertIn("review_code_boundary_conformance", combined)
        self.assertIn("TransitionCoverageMatrix", combined)
        self.assertIn("TransitionCoverageCell", combined)
        self.assertIn("TEST_EVIDENCE_ROLE_TRANSITION_CELL", combined)
        self.assertIn("transition_coverage_to_code_contracts", combined)
        self.assertIn("transition_coverage_to_model_obligations", combined)
        self.assertIn("model_mesh_closure_to_transition_coverage", combined)
        self.assertIn("ModelMesh closure projection", combined)
        self.assertIn("TestResultReuseTicket", combined)
        self.assertIn("audit_python_code_contracts", combined)
        self.assertIn("audit_python_test_assertions", combined)
        self.assertIn("review_python_contract_source_audit", combined)
        self.assertIn("ArtifactPayloadContract", combined)
        self.assertIn("real payload surface", combined)
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
            mesh_template_files_factory(),
            (".flowguard", "test_mesh"),
        )
        self.assertIn("flowguard test mesh", output)
        self.assertIn("release_obligations", output)
        self.assertIn("stale_test_evidence", output)

    def test_test_mesh_template_teaches_parent_child_hierarchy(self):
        files = mesh_template_files_factory()
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
        self.assertIn("model_mesh_closure_to_transition_coverage", combined)
        self.assertIn("ModelMesh closure projection cells", combined)
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
        self.assertIn("flowguard UI functional capability coverage", output)
        self.assertIn("flowguard UI implementation validation", output)
        self.assertIn("flowguard UI human operability", output)
        self.assertIn("flowguard UI structure derivation", output)
        self.assertIn("flowguard UI text hierarchy", output)
        self.assertIn("flowguard UI visible surface", output)
        self.assertIn("flowguard UI content visibility", output)
        self.assertIn("missing_state_availability_matrix", output)
        self.assertIn("feature_entry_point_not_declared", output)
        self.assertIn("required_capability_missing_binding", output)
        self.assertIn("result_capability_missing_output_contract", output)
        self.assertIn("feature_without_user_task", output)
        self.assertIn("missing_human_walkthrough", output)
        self.assertIn("missing_implementation_run_for_journey", output)
        self.assertIn("source_interaction_model_not_reviewed", output)
        self.assertIn("text_role_too_prominent", output)
        self.assertIn("visible_internal_terminology", output)
        self.assertIn("missing_disabled_reason", output)
        self.assertIn("missing_render_evidence_kind", output)
        self.assertIn("internal_content_mapped_to_ui", output)
        self.assertIn("unknown_content_visibility_class", output)
        self.assertIn("on_demand_content_visible_in_default_state", output)

    def test_ui_flow_structure_full_template_executes_content_visibility_cases(self):
        output = self.run_written_template(
            ui_flow_structure_full_template_files(),
            (".flowguard", "ui_flow_structure"),
        )

        self.assertIn("flowguard UI content visibility review", output)
        self.assertIn("internal_content_mapped_to_ui", output)
        self.assertIn("unknown_content_visibility_class", output)
        self.assertIn("on_demand_content_visible_in_default_state", output)
        self.assertIn("flowguard UI product consistency review", output)
        self.assertIn("product_semantic_drift", output)

    def test_ui_flow_structure_template_uses_visual_job_typography_scale(self):
        files = ui_flow_structure_template_files()
        combined = "\n".join(file.content for file in files)

        self.assertIn('"surface-title"', combined)
        self.assertIn('"region-heading"', combined)
        self.assertIn('"standard-text"', combined)
        self.assertIn('"supporting-text"', combined)
        self.assertIn("The text hierarchy contract is semantic", combined)
        self.assertIn("similar text jobs should usually reuse visual treatments", combined)
        self.assertIn("ui-flow-structure-full-template", combined)
        self.assertIn("candidate_content_ids", combined)
        self.assertIn("content_visibility_items", combined)
        self.assertIn("default_visible_content_ids", combined)
        self.assertIn("default_hidden_content_ids", combined)
        self.assertIn('"user_visible"', combined)
        self.assertIn('"user_on_demand"', combined)
        self.assertIn('"internal"', combined)
        self.assertIn("click_show_details", combined)
        self.assertIn("registered in-scope task", combined)
        self.assertIn("carry no extra state/metadata", combined)
        self.assertIn("structured_content_visibility", combined)
        self.assertIn("unknown_user_content_need_kind", combined)
        self.assertLessEqual(next(file for file in files if file.path.endswith("model.py")).content.count("\n"), 245)
        self.assertNotIn('scale=f"level-{level}"', combined)

    def test_ui_flow_structure_full_template_keeps_deep_route_material(self):
        files = ui_flow_structure_full_template_files()
        combined = "\n".join(file.content for file in files)

        self.assertIn("UIJourneyCoverage", combined)
        self.assertIn("UIImplementationValidation", combined)
        self.assertIn("UIHumanOperabilityAssessment", combined)
        self.assertIn("review_ui_human_operability", combined)
        self.assertIn("every reachable enabled", combined)
        self.assertIn("UIStructureDerivation", combined)
        self.assertIn("UITextHierarchyBlueprint", combined)
        self.assertIn("UIFeatureContract", combined)
        self.assertIn("UIFunctionalCapabilityInventory", combined)
        self.assertIn("review_ui_functional_capability_coverage", combined)
        self.assertIn("UIVisibleSurface", combined)
        self.assertIn("UIContentVisibilityItem", combined)
        self.assertIn("UIContentVisibilityPlan", combined)
        self.assertIn("UIRenderEvidenceSet", combined)
        self.assertIn("UIGeometryLayoutEvidenceSet", combined)
        self.assertIn("UIResponsivenessContract", combined)
        self.assertIn("review_ui_visible_surface", combined)
        self.assertIn("review_ui_content_visibility", combined)
        self.assertIn("review_ui_render_evidence", combined)
        self.assertIn("review_ui_geometry_layout_evidence", combined)
        self.assertIn("review_ui_responsiveness_contract", combined)
        self.assertIn('"screenshot"', combined)
        self.assertIn("hidden_displays", combined)
        self.assertIn("content_visibility_id", combined)
        self.assertIn("content_visibility_plan_id", combined)
        self.assertIn("broken_internal_visible_content_plan", combined)
        self.assertIn("broken_missing_content_class_plan", combined)
        self.assertIn("broken_on_demand_visible_before_reveal_plan", combined)
        self.assertIn("analysis_refresh_no_guard", combined)
        self.assertIn("old cold results can overwrite newer state", combined)

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

        self.assertIn("development-process simulator front door", combined)
        self.assertIn("does not inspect", combined)
        self.assertIn("does not make FlowGuard a task orchestrator", combined)
        self.assertIn("run AutoSplit, ModelMesh, or TestMesh as its own", combined)
        self.assertIn("UI observed inventory, functional capability coverage", combined)
        self.assertIn("Do not copy\nAutoSplit metrics onto `ProcessEvidence`", combined)
        self.assertIn("producer_route=\"test_mesh_maintenance\"", combined)
        self.assertIn("strategy_selection", combined)
        self.assertIn("safe_parallel", combined)
        self.assertIn("Ordinary single-route work needs no optimization records", combined)
        self.assertIn("never a global\noptimum", combined)
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

    def test_model_angle_deliberation_template_executes(self):
        output = self.run_written_template(
            model_angle_deliberation_template_files(),
            (".flowguard", "model_angle_deliberation"),
        )
        self.assertIn("flowguard model-angle deliberation", output)
        self.assertIn("unresolved_required_model_angle", output)
        self.assertIn("template checks passed", output)

    def test_field_lifecycle_template_executes(self):
        output = self.run_written_template(
            field_lifecycle_template_files(),
            (".flowguard", "field_lifecycle"),
        )
        self.assertIn("flowguard field lifecycle mesh", output)
        self.assertIn("projected_model_obligations: 2", output)
        self.assertIn("behavior_field_projection_missing", output)
        self.assertIn("old_field_disposition_open", output)

    def test_field_lifecycle_template_teaches_default_replacement_handoffs(self):
        files = field_lifecycle_template_files()
        combined = "\n".join(file.content for file in files)

        self.assertIn("FieldLifecycleMesh", combined)
        self.assertIn("Default replacement policy", combined)
        self.assertIn("old fields", combined)
        self.assertIn("compatibility intent", combined)
        self.assertIn("field_lifecycle_to_model_obligations", combined)
        self.assertIn("field_lifecycle_to_code_contracts", combined)
        self.assertIn("Model-Test Alignment", combined)
        self.assertIn("DevelopmentProcessFlow", combined)
        self.assertIn("gate:", combined)
        self.assertIn("test:", combined)
        self.assertIn("replay:", combined)
        self.assertIn("Field route refs are handoff labels", combined)

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
        self.assertIn("missing_artifact_payload_gate", output)
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

    def test_risk_template_cli_searches_and_harvests(self):
        search = subprocess.run(
            [
                sys.executable,
                "-m",
                "flowguard",
                "risk-template-search",
                "completion evidence",
                "--no-local",
                "--json",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, search.returncode, search.stderr)
        search_report = json.loads(search.stdout)
        self.assertEqual(["public"], search_report["searched_layers"])
        self.assertEqual("completion_requires_evidence", search_report["matches"][0]["template"]["template_id"])

        harvest = subprocess.run(
            [
                sys.executable,
                "-m",
                "flowguard",
                "risk-template-harvest",
                "--template-id",
                "cli_sample",
                "--title",
                "CLI sample",
                "--summary",
                "CLI sample.",
                "--protected-error-class",
                "premature_completion",
                "--required-state",
                "completed",
                "--required-evidence",
                "completion_receipt",
                "--known-bad-case",
                "ack_only",
                "--known-bad-proof",
                json.dumps(
                    {
                        "case_id": "ack_only",
                        "protected_error_class": "premature_completion",
                        "method": "broken_workflow_variant",
                        "observed_status": "failed",
                        "observed_failure": "ack-only completion was rejected",
                        "evidence_id": "cli:known-bad",
                    }
                ),
                "--no-write",
                "--json",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, harvest.returncode, harvest.stderr)
        harvest_report = json.loads(harvest.stdout)
        self.assertTrue(harvest_report["ok"])
        self.assertEqual("candidate_ready", harvest_report["status"])
        self.assertEqual("", harvest_report["path"])

        closure = subprocess.run(
            [
                sys.executable,
                "-m",
                "flowguard",
                "risk-template-harvest-review",
                "--disposition",
                "duplicate_linked",
                "--linked-template-id",
                "completion_requires_evidence",
                "--json",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, closure.returncode, closure.stderr)
        closure_report = json.loads(closure.stdout)
        self.assertEqual("duplicate_linked", closure_report["review"]["disposition"])
        self.assertTrue(closure_report["report"]["ok"])

    def test_public_templates_do_not_contain_local_project_markers(self):
        home_name = Path.home().name
        private_markers = [
            "C:" + "\\Users",
            "FlowGuardProjectAutopilot",
            "FlowPilot",
            "Cockpit",
            "heartbeat",
        ]
        if home_name.lower() not in {"runner", "root"}:
            private_markers.append(home_name)
        for factory in PUBLIC_TEMPLATE_FACTORIES + (project_adoption_template_files,):
            with self.subTest(factory=factory.__name__):
                for file in factory():
                    for marker in private_markers:
                        self.assertNotIn(marker, file.content)


if __name__ == "__main__":
    unittest.main()
