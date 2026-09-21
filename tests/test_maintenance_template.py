import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flowguard.templates import maintenance_workflow_template_files, write_template_files


ROOT = Path(__file__).resolve().parents[1]


class MaintenanceWorkflowTemplateTests(unittest.TestCase):
    def test_model_template_includes_risk_purpose_header(self):
        files = maintenance_workflow_template_files()
        model_file = next(file for file in files if file.path.endswith("model.py"))
        self.assertIn("FlowGuard Risk Purpose Header", model_file.content)
        self.assertIn("https://github.com/liuyingxuvka/FlowGuard", model_file.content)
        self.assertIn("Purpose:", model_file.content)
        self.assertIn("Guards against:", model_file.content)
        self.assertIn("Use before editing:", model_file.content)
        self.assertIn("Run:", model_file.content)

    def test_template_files_execute_expected_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_template_files(root, maintenance_workflow_template_files())
            template_dir = root / ".flowguard" / "verification" / "owners" / "maintenance_workflow"
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")

            result = subprocess.run(
                [sys.executable, "run_checks.py"],
                cwd=template_dir,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("correct_maintenance_workflow: OK", result.stdout)
            self.assertIn("broken_duplicate_sleep_action: VIOLATION", result.stdout)
            self.assertIn("broken_completed_without_report: VIOLATION", result.stdout)
            self.assertIn("broken_publish_without_install_sync: VIOLATION", result.stdout)

    def test_cli_prints_and_writes_template(self):
        help_result = subprocess.run(
            [sys.executable, "-m", "flowguard", "maintenance-template", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        payload = json.loads(help_result.stdout)
        self.assertEqual(2, help_result.returncode, help_result.stderr)
        self.assertEqual("blocked", payload["status"])
        self.assertEqual("block", payload["decision"])
        self.assertEqual(0, payload["producer_count"])
        self.assertEqual(
            "unknown operation: maintenance-template",
            payload["error"],
        )
        self.assertEqual(["read", "change", "release"], payload["allowed_operations"])

    def test_template_write_refuses_overwrite_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_template_files(root, maintenance_workflow_template_files())

            with self.assertRaises(FileExistsError):
                write_template_files(root, maintenance_workflow_template_files())


if __name__ == "__main__":
    unittest.main()
