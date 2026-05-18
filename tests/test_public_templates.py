import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flowguard.templates import (
    code_structure_recommendation_template_files,
    model_miss_review_template_files,
    model_test_alignment_template_files,
    project_template_files,
    risk_intent_template_files,
    structure_mesh_template_files,
    test_mesh_template_files,
    write_template_files,
)


ROOT = Path(__file__).resolve().parents[1]


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

    def test_risk_intent_template_executes(self):
        output = self.run_written_template(
            risk_intent_template_files(),
            (".flowguard", "risk_intent_check_plan"),
        )
        self.assertIn("flowguard summary", output)
        self.assertIn("risk_intent", output)

    def test_model_miss_review_template_executes(self):
        output = self.run_written_template(
            model_miss_review_template_files(),
            (".flowguard", "model_miss_review"),
        )
        self.assertIn("correct_model_miss_review: PASS", output)
        self.assertIn("expected violations observed: 2", output)

    def test_model_test_alignment_template_executes(self):
        output = self.run_written_template(
            model_test_alignment_template_files(),
            (".flowguard", "model_test_alignment"),
        )
        self.assertIn("flowguard model-test alignment", output)
        self.assertIn("missing_required_test_kind", output)

    def test_model_test_alignment_template_covers_code_contracts_without_mesh_helpers(self):
        files = model_test_alignment_template_files()
        combined = "\n".join(file.content for file in files)

        self.assertIn("does not use TestMesh, StructureMesh, or ModelMesh", combined)
        self.assertIn("plain model obligations", combined)
        self.assertIn("plain test", combined)
        self.assertIn("evidence", combined)
        self.assertIn("code external contracts", combined)
        self.assertIn("CodeContract", combined)
        self.assertIn("covered code contract ids", combined)
        self.assertNotIn("review_hierarchical_mesh", combined)
        self.assertNotIn("review_test_mesh", combined)
        self.assertNotIn("review_structure_mesh", combined)

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

    def test_code_structure_recommendation_template_executes(self):
        output = self.run_written_template(
            code_structure_recommendation_template_files(),
            (".flowguard", "code_structure_recommendation"),
        )
        self.assertIn("flowguard code structure recommendation", output)
        self.assertIn("missing_source_model", output)

    def test_structure_mesh_template_executes(self):
        output = self.run_written_template(
            structure_mesh_template_files(),
            (".flowguard", "structure_mesh"),
        )
        self.assertIn("flowguard structure mesh", output)
        self.assertIn("release_obligations", output)
        self.assertIn("duplicate_state_owner", output)

    def test_public_model_templates_include_risk_purpose_headers(self):
        for files in (
            project_template_files(),
            risk_intent_template_files(),
            model_miss_review_template_files(),
            model_test_alignment_template_files(),
            code_structure_recommendation_template_files(),
            test_mesh_template_files(),
            structure_mesh_template_files(),
        ):
            model_file = next(file for file in files if file.path.endswith("model.py"))
            self.assert_risk_purpose_header(model_file.content)

    def test_template_cli_prints_and_writes_new_templates(self):
        commands = {
            "project-template": "project",
            "risk-intent-template": "risk_intent_check_plan",
            "model-miss-template": "model_miss_review",
            "model-test-alignment-template": "model_test_alignment",
            "code-structure-recommendation-template": "code_structure_recommendation",
            "test-mesh-template": "test_mesh",
            "structure-mesh-template": "structure_mesh",
        }
        for command, template_name in commands.items():
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
            "liu_y",
            "FlowGuardProjectAutopilot",
            "FlowPilot",
            "Cockpit",
            "heartbeat",
        )
        for files in (
            project_template_files(),
            risk_intent_template_files(),
            model_miss_review_template_files(),
            model_test_alignment_template_files(),
            code_structure_recommendation_template_files(),
            test_mesh_template_files(),
            structure_mesh_template_files(),
        ):
            for file in files:
                for marker in private_markers:
                    self.assertNotIn(marker, file.content)


if __name__ == "__main__":
    unittest.main()
