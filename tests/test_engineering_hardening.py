import json
import subprocess
import sys
import unittest

from flowguard.schema import SCHEMA_VERSION, make_artifact, trace_artifact
from flowguard.templates import project_template_files
from flowguard.trace import Trace


class EngineeringHardeningTests(unittest.TestCase):
    def test_schema_envelope_is_versioned_and_json_serializable(self):
        artifact = make_artifact(
            "report",
            {"ok": True},
            model_name="model",
            scenario_name="scenario",
            trace_id="trace-1",
        )
        data = artifact.to_dict()
        self.assertEqual(SCHEMA_VERSION, data["schema_version"])
        self.assertEqual("report", data["artifact_type"])
        self.assertEqual("flowguard", data["created_by"])
        self.assertEqual("model", data["model_name"])
        self.assertEqual("scenario", data["scenario_name"])
        self.assertEqual("trace-1", data["trace_id"])
        self.assertEqual({"ok": True}, data["payload"])
        self.assertEqual(data, json.loads(artifact.to_json_text()))

    def test_trace_artifact_wraps_trace_payload(self):
        artifact = trace_artifact(Trace(), model_name="empty", trace_id="t0")
        data = artifact.to_dict()
        self.assertEqual("trace", data["artifact_type"])
        self.assertEqual("empty", data["model_name"])
        self.assertIn("steps", data["payload"])

    def test_project_templates_are_available_without_file_writes(self):
        files = project_template_files()
        paths = {item.path for item in files}
        self.assertIn("model.py", paths)
        self.assertIn("run_checks.py", paths)
        for item in files:
            self.assertTrue(item.content.strip())

    def test_cli_schema_version_wrapper(self):
        completed = subprocess.run(
            [sys.executable, "-m", "flowguard", "schema-version"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertEqual(SCHEMA_VERSION, completed.stdout.strip())

    def test_cli_adoption_template_wrapper(self):
        completed = subprocess.run(
            [sys.executable, "-m", "flowguard", "adoption-template"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("flowguard Adoption Log", completed.stdout)
        self.assertIn("elapsed time", completed.stdout)


if __name__ == "__main__":
    unittest.main()
