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
    def test_template_files_execute_expected_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_template_files(root, maintenance_workflow_template_files())
            template_dir = root / ".flowguard" / "maintenance_workflow"
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
        printed = subprocess.run(
            [sys.executable, "-m", "flowguard", "maintenance-template"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, printed.returncode, printed.stderr)
        data = json.loads(printed.stdout)
        self.assertEqual("maintenance_workflow", data["template"])
        self.assertIn(
            ".flowguard/maintenance_workflow/model.py",
            {item["path"] for item in data["files"]},
        )

        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-m", "flowguard", "maintenance-template", "--output", directory],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            write_report = json.loads(result.stdout)
            self.assertEqual("flowguard_template_write", write_report["artifact_type"])
            self.assertTrue((Path(directory) / ".flowguard" / "maintenance_workflow" / "model.py").exists())
            self.assertTrue((Path(directory) / "docs" / "flowguard_maintenance_workflow.md").exists())

    def test_template_write_refuses_overwrite_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_template_files(root, maintenance_workflow_template_files())

            with self.assertRaises(FileExistsError):
                write_template_files(root, maintenance_workflow_template_files())


if __name__ == "__main__":
    unittest.main()
