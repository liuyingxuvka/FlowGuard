import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flowguard.templates import (
    model_miss_review_template_files,
    project_template_files,
    risk_intent_template_files,
    write_template_files,
)


ROOT = Path(__file__).resolve().parents[1]


def _template_env():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return env


class PublicTemplateTests(unittest.TestCase):
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

    def test_template_cli_prints_and_writes_new_templates(self):
        commands = {
            "project-template": "project",
            "risk-intent-template": "risk_intent_check_plan",
            "model-miss-template": "model_miss_review",
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
        ):
            for file in files:
                for marker in private_markers:
                    self.assertNotIn(marker, file.content)


if __name__ == "__main__":
    unittest.main()
