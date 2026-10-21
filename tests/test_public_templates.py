import contextlib
import io
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
from flowguard.__main__ import main as flowguard_cli_main
from flowguard.templates import (
    behavior_commitment_ledger_template_files,
    code_structure_recommendation_template_files,
    contract_exhaustion_template_files,
    field_lifecycle_template_files,
    maintenance_workflow_template_files,
    model_mesh_template_files,
    model_miss_review_full_template_files,
    model_miss_review_template_files,
    model_test_alignment_full_template_files,
    model_test_alignment_template_files,
    primary_path_authority_template_files,
    risk_intent_template_files,
    risk_template_library_template_files,
    runtime_path_evidence_template_files,
    work_context_template_files,
    structure_mesh_template_files,
    topology_hazard_template_files,
    ui_flow_structure_full_template_files,
    ui_flow_structure_template_files,
    workflow_step_contracts_template_files,
    write_template_files,
)
from flowguard.risk_templates import (
    TemplateHarvestReview,
    harvest_risk_template_candidate,
    review_template_harvest_closure,
    search_risk_templates,
)


ROOT = Path(__file__).resolve().parents[1]

PUBLIC_TEMPLATE_FACTORIES = (
    risk_intent_template_files,
    risk_template_library_template_files,
    behavior_commitment_ledger_template_files,
    primary_path_authority_template_files,
    model_miss_review_template_files,
    model_test_alignment_template_files,
    code_structure_recommendation_template_files,
    field_lifecycle_template_files,
    runtime_path_evidence_template_files,
    ui_flow_structure_template_files,
    workflow_step_contracts_template_files,
    model_mesh_template_files,
    contract_exhaustion_template_files,
    structure_mesh_template_files,
    topology_hazard_template_files,
    work_context_template_files,
)

TEMPLATE_CLI_COMMANDS = {
    "work-context-template": "work_context",
    "risk-intent-template": "risk_intent_check_plan",
    "risk-template-library-template": "risk_template_library",
    "behavior-commitment-ledger-template": "behavior_commitment_ledger",
    "primary-path-authority-template": "primary_path_authority",
    "model-miss-template": "model_miss_review",
    "model-miss-full-template": "model_miss_review_full",
    "model-test-alignment-template": "model_test_alignment",
    "model-test-alignment-full-template": "model_test_alignment_full",
    "runtime-path-evidence-template": "runtime_path_evidence",
    "code-structure-recommendation-template": "code_structure_recommendation",
    "field-lifecycle-template": "field_lifecycle",
    "ui-flow-structure-template": "ui_flow_structure",
    "ui-flow-structure-full-template": "ui_flow_structure_full",
    "workflow-step-contracts-template": "workflow_step_contracts",
    "model-mesh-template": "model_mesh",
    "contract-exhaustion-template": "contract_exhaustion",
    "structure-mesh-template": "structure_mesh",
    "topology-hazard-template": "model_topology_hazard_review",
}


def _template_env():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return env


class PublicTemplateTests(unittest.TestCase):
    def run_written_template(self, files, run_dir_parts, expected_returncode=0):
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
        self.assertEqual(expected_returncode, result.returncode, result.stdout + result.stderr)
        return result.stdout

    def run_cli(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                return_code = flowguard_cli_main(list(argv))
        except SystemExit as exc:
            return_code = int(exc.code or 0)
        return return_code, stdout.getvalue(), stderr.getvalue()

    def test_template_text_is_route_scoped_behind_public_facade(self):
        template_text_root = ROOT / "flowguard" / "template_text"
        route_modules = {path.stem for path in template_text_root.glob("*.py") if path.name != "__init__.py"}

        self.assertIn("ui_flow_structure", route_modules)
        self.assertNotIn("model_similarity_consolidation", route_modules)
        self.assertNotIn("risk_evidence_ledger", route_modules)
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
            (".flowguard", "verification", "owners", "risk_intent_check_plan"),
        )
        self.assertIn("flowguard summary", output)
        self.assertIn("risk_intent", output)

    def test_risk_template_library_template_executes(self):
        output = self.run_written_template(
            risk_template_library_template_files(),
            (".flowguard", "verification", "owners", "risk_template_library"),
        )
        self.assertIn("flowguard risk template search", output)
        self.assertIn("completion_requires_evidence", output)
        self.assertIn("flowguard minimum valuable model review", output)
        self.assertIn("flowguard risk template harvest", output)
        self.assertIn("flowguard template harvest closure", output)

    def test_behavior_commitment_ledger_template_executes(self):
        output = self.run_written_template(
            behavior_commitment_ledger_template_files(),
            (".flowguard", "verification", "owners", "behavior_commitment_ledger"),
        )
        self.assertIn("flowguard behavior commitment ledger", output)
        self.assertIn("full_inventory_registered: yes", output)
        self.assertIn("behavior_commitment_coverage_green", output)

    def test_behavior_commitment_template_has_one_canonical_ledger_authority(self):
        files = behavior_commitment_ledger_template_files()
        by_path = {file.path: file.content for file in files}

        self.assertIn(".flowguard/behavior/inventory/ledger.json", by_path)
        payload = json.loads(by_path[".flowguard/behavior/inventory/ledger.json"])
        canonical = behavior_commitment_ledger_from_mapping(payload)
        self.assertEqual(payload, behavior_commitment_ledger_to_mapping(canonical))
        commitment = payload["ledger"]["commitments"][0]
        self.assertEqual("product_runtime", commitment["behavior_plane"])
        self.assertEqual("end_user", commitment["actor_kind"])
        self.assertEqual("intent:run-primary-workflow", commitment["business_intent_id"])
        model_text = by_path[".flowguard/models/owners/behavior_commitment_ledger/model.py"]
        self.assertIn("load_behavior_commitment_ledger", model_text)
        self.assertNotIn("BehaviorCommitment(", model_text)

    def test_primary_path_authority_template_executes(self):
        output = self.run_written_template(
            primary_path_authority_template_files(),
            (".flowguard", "verification", "owners", "primary_path_authority"),
        )
        self.assertIn("Primary Path Authority checks passed", output)
        self.assertIn("primary_path_authority_green", output)

    def test_model_miss_review_template_executes(self):
        output = self.run_written_template(model_miss_review_template_files(),
            (".flowguard", "verification", "owners", "model_miss_review"))
        self.assertIn("false-negative", output)
        self.assertIn("missing_new_model_obligation", output)
        self.assertIn("missing_false_negative_closure_evidence", output)


    def test_model_test_alignment_template_executes(self):
        output = self.run_written_template(model_test_alignment_template_files(),
            (".flowguard", "verification", "owners", "model_test_alignment"))
        self.assertIn("flowguard model-test alignment", output)
        self.assertIn("design-ready scaffold; target execution: not_run", output)
        self.assertIn("test_evidence_not_passing", output)


    def test_model_test_alignment_full_template_executes_all_six_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_template_files(root, model_test_alignment_full_template_files())
            result = subprocess.run(
                [sys.executable, "-c", "import json, run_checks; "
                 "print(json.dumps([report.ok for report in run_checks.run_checks()]))"],
                cwd=root / ".flowguard" / "verification" / "owners" / "model_test_alignment",
                env=_template_env(),
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        # Alignment, boundary conformance and source audit each reject their bad example.
        self.assertEqual([True, False, True, False, True, False], json.loads(result.stdout))

    def test_runtime_path_evidence_template_executes_and_prints_model_target(self):
        output = self.run_written_template(
            runtime_path_evidence_template_files(),
            (".flowguard", "verification", "owners", "runtime_path_evidence"),
        )

        self.assertIn("flowguard runtime path evidence", output)
        self.assertIn("flowguard.runtime_path", output)
        self.assertIn("model=checkout.leaf", output)
        self.assertIn("model_path=.flowguard/models/owners/checkout_leaf/model.py", output)
        self.assertIn("runtime_node_missing_observation", output)

    def test_model_mesh_template_executes_and_exposes_negative_fixture(self):
        output = self.run_written_template(
            model_mesh_template_files(),
            (".flowguard", "verification", "owners", "model_mesh"),
        )
        self.assertIn("flowguard hierarchical mesh", output)
        self.assertIn("decision:", output)
        self.assertIn("missing", output.lower())
        self.assertNotIn("negative-case matrix: PASS", output)

    def test_contract_exhaustion_template_executes_and_exposes_negative_fixture(self):
        output = self.run_written_template(
            contract_exhaustion_template_files(),
            (".flowguard", "verification", "owners", "contract_exhaustion"),
        )
        self.assertIn("flowguard contract exhaustion mesh", output)
        self.assertIn("decision:", output)
        self.assertIn("missing", output.lower())
        self.assertNotIn("negative-case matrix: PASS", output)

    def test_code_structure_recommendation_template_executes(self):
        output = self.run_written_template(
            code_structure_recommendation_template_files(),
            (".flowguard", "verification", "owners", "code_structure_recommendation"),
        )
        self.assertIn("flowguard code structure recommendation", output)
        self.assertIn("missing_source_model", output)

    def test_ui_flow_structure_template_executes(self):
        output = self.run_written_template(ui_flow_structure_template_files(),
            (".flowguard", "verification", "owners", "ui_flow_structure"))
        self.assertIn("flowguard UI interaction model", output)
        self.assertIn("transition_target_state_not_registered", output)
        self.assertNotIn("UI implementation validation", output)


    def test_ui_flow_structure_full_template_executes_content_visibility_cases(self):
        output = self.run_written_template(
            ui_flow_structure_full_template_files(),
            (".flowguard", "verification", "owners", "ui_flow_structure"),
        )

        self.assertIn("flowguard UI content visibility review", output)
        self.assertIn("internal_content_mapped_to_ui", output)
        self.assertIn("unknown_content_visibility_class", output)
        self.assertIn("on_demand_content_visible_in_default_state", output)
        self.assertIn("flowguard UI product consistency review", output)
        self.assertIn("product_semantic_drift", output)

    def test_structure_mesh_template_executes(self):
        output = self.run_written_template(
            structure_mesh_template_files(),
            (".flowguard", "verification", "owners", "structure_mesh"),
        )
        self.assertIn("flowguard structure mesh", output)
        self.assertIn("release_obligations", output)
        self.assertIn("duplicate_state_owner", output)

    def test_topology_hazard_template_executes(self):
        output = self.run_written_template(
            topology_hazard_template_files(),
            (".flowguard", "verification", "owners", "model_topology_hazard_review"),
            expected_returncode=1,
        )
        self.assertIn("flowguard topology hazard review", output)
        self.assertIn("topology_hazard_blocked", output)
        self.assertIn("unresolved_hazard_ids", output)

    def test_topology_hazard_template_good_review_exits_zero(self):
        from dataclasses import replace

        files = topology_hazard_template_files()
        good_review = """
def build_review():
    from flowguard import TOPOLOGY_USAGE_LOCAL
    plan = infer_topology_hazard_plan(
        workflow=Workflow((SaveRecord(),), name="save-record"),
        initial_states=(State(),), external_inputs=(),
        usage_intent=UsageIntent(usage_modes=(TOPOLOGY_USAGE_LOCAL,), final_claim="local"),
    )
    return review_topology_hazards(plan)
"""
        files = tuple(replace(file, content=file.content + good_review)
                      if file.path.endswith("model.py") else file for file in files)
        output = self.run_written_template(
            files, (".flowguard", "verification", "owners", "model_topology_hazard_review"),
        )
        self.assertIn("topology_hazard_pass", output)

    def test_workflow_step_contracts_template_executes(self):
        output = self.run_written_template(
            workflow_step_contracts_template_files(),
            (".flowguard", "verification", "owners", "workflow_step_contracts"),
        )
        self.assertIn("flowguard workflow step contracts", output)
        self.assertIn("missing_claim_receipt", output)
        self.assertIn("model_obligations", output)

    def test_field_lifecycle_template_executes(self):
        output = self.run_written_template(
            field_lifecycle_template_files(),
            (".flowguard", "verification", "owners", "field_lifecycle"),
        )
        self.assertIn("flowguard field lifecycle mesh", output)
        self.assertIn("projected_model_obligations: 2", output)
        self.assertIn("behavior_field_projection_missing", output)
        self.assertIn("old_field_disposition_open", output)

    def test_template_cli_prints_and_writes_new_templates(self):
        factories = {
            factory.__name__.removesuffix("_template_files"): factory
            for factory in PUBLIC_TEMPLATE_FACTORIES
        }
        factories["risk_intent_check_plan"] = risk_intent_template_files
        factories["model_miss_review_full"] = model_miss_review_full_template_files
        factories["model_test_alignment_full"] = model_test_alignment_full_template_files
        factories["ui_flow_structure_full"] = ui_flow_structure_full_template_files
        factories["model_topology_hazard_review"] = topology_hazard_template_files
        for command, template_name in TEMPLATE_CLI_COMMANDS.items():
            self.assertIn(template_name, factories, command)
            files = factories[template_name]()
            self.assertTrue(files, command)

            with tempfile.TemporaryDirectory() as directory:
                write_template_files(directory, files)
                written_paths = tuple(Path(directory).rglob("*"))
                self.assertTrue(written_paths, command)

        # Every starter template is reachable through one CLI verb.
        code, stdout, _stderr = self.run_cli(["template", "--list"])
        self.assertEqual(0, code)
        listed = stdout.split()
        self.assertNotIn("project", listed)
        self.assertIn("ui-flow-structure-full", listed)
        for name in listed:
            code, stdout, stderr = self.run_cli(["template", name])
            self.assertEqual(0, code, name + stderr)
            self.assertIn("===== ", stdout, name)
        with tempfile.TemporaryDirectory() as directory:
            code, stdout, _stderr = self.run_cli(["template", "structure-mesh", "--write", directory])
            self.assertEqual(0, code)
            self.assertTrue(any(Path(directory).rglob("run_checks.py")))
            code, _stdout, stderr = self.run_cli(["template", "structure-mesh", "--write", directory])
            self.assertEqual(1, code)
            self.assertIn("--force", stderr)
        code, _stdout, _stderr = self.run_cli(["template", "no-such-template"])
        self.assertEqual(2, code)

    def test_risk_template_cli_searches_and_harvests(self):
        search_report = search_risk_templates(
            "completion evidence",
            include_local=False,
        )
        self.assertEqual(("public",), search_report.searched_layers)
        self.assertEqual(
            "completion_requires_evidence",
            search_report.matches[0].template.template_id,
        )

        harvest_report = harvest_risk_template_candidate(
            template_id="cli_sample",
            title="CLI sample",
            summary="CLI sample.",
            protected_error_classes=("premature_completion",),
            required_state=("completed",),
            required_evidence=("completion_receipt",),
            known_bad_cases=("ack_only",),
            known_bad_proofs=(
                {
                    "case_id": "ack_only",
                    "protected_error_class": "premature_completion",
                    "method": "broken_workflow_variant",
                    "observed_status": "failed",
                    "observed_failure": "ack-only completion was rejected",
                    "evidence_id": "cli:known-bad",
                },
            ),
            write=False,
        )
        self.assertTrue(harvest_report.ok)
        self.assertEqual("candidate_ready", harvest_report.status)
        self.assertEqual("", harvest_report.path)

        closure = review_template_harvest_closure(
            TemplateHarvestReview(
                disposition="duplicate_linked",
                linked_template_ids=("completion_requires_evidence",),
            )
        )
        self.assertTrue(closure.ok)

    def test_public_templates_do_not_contain_local_project_markers(self):
        home_path = Path.home()
        private_markers = [
            "C:" + "\\Users",
            "FlowGuardProjectAutopilot",
            "FlowPilot",
            "Cockpit",
            "heartbeat",
        ]
        if home_path.name.lower() not in {"runner", "root"}:
            private_markers.append(str(home_path))
        for factory in PUBLIC_TEMPLATE_FACTORIES:
            with self.subTest(factory=factory.__name__):
                for file in factory():
                    for marker in private_markers:
                        self.assertNotIn(marker, file.content)


if __name__ == "__main__":
    unittest.main()
