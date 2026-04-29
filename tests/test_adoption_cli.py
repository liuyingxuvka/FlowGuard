import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AdoptionCliTests(unittest.TestCase):
    def test_start_and_finish_append_structured_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            start = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "flowguard",
                    "adoption-start",
                    "--root",
                    str(root),
                    "--task-id",
                    "task-1",
                    "--project",
                    "demo",
                    "--task-summary",
                    "model output status cleanup",
                    "--trigger-reason",
                    "state write inventory needed",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, start.returncode, start.stderr)
            self.assertEqual("in_progress", json.loads(start.stdout)["status"])

            finish = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "flowguard",
                    "adoption-finish",
                    "--root",
                    str(root),
                    "--task-id",
                    "task-1",
                    "--project",
                    "demo",
                    "--task-summary",
                    "model output status cleanup",
                    "--trigger-reason",
                    "state write inventory needed",
                    "--command",
                    "python run_checks.py",
                    "--finding",
                    "state write inventory recorded",
                    "--skipped-step",
                    "production replay skipped with reason",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, finish.returncode, finish.stderr)
            self.assertEqual("completed", json.loads(finish.stdout)["status"])

            jsonl_path = root / ".flowguard" / "adoption_log.jsonl"
            markdown_path = root / "docs" / "flowguard_adoption_log.md"
            entries = [
                json.loads(line)
                for line in jsonl_path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(["in_progress", "completed"], [entry["status"] for entry in entries])
            self.assertTrue(entries[-1]["has_commands"])
            self.assertIn("state write inventory recorded", markdown_path.read_text(encoding="utf-8"))

    def test_failed_command_defaults_final_entry_to_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "flowguard",
                    "adoption-finish",
                    "--root",
                    directory,
                    "--task-id",
                    "task-2",
                    "--task-summary",
                    "model failed",
                    "--trigger-reason",
                    "counterexample found",
                    "--failed-command",
                    "python run_checks.py",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual("failed", data["status"])
            self.assertFalse(data["ok"])


if __name__ == "__main__":
    unittest.main()
