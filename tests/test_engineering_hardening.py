import json
import unittest

from flowguard.schema import SCHEMA_VERSION, make_artifact, trace_artifact
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

if __name__ == "__main__":
    unittest.main()
