import json
import unittest

from examples.job_matching.model import check_job_matching_model


class TraceExportTests(unittest.TestCase):
    def test_trace_exports_to_dict_and_json_text(self):
        report = check_job_matching_model(max_sequence_length=1)
        trace = report.traces[0]

        exported = trace.to_dict()

        self.assertIn("steps", exported)
        self.assertIn("external_inputs", exported)
        self.assertIn("final_state", exported)

        first_step = exported["steps"][0]
        for key in (
            "function_name",
            "function_input",
            "function_output",
            "old_state",
            "new_state",
            "label",
            "reason",
        ):
            self.assertIn(key, first_step)

        loaded = json.loads(trace.to_json_text())
        self.assertEqual(exported["steps"][0]["function_name"], loaded["steps"][0]["function_name"])

    def test_report_exports_to_dict_and_json_text(self):
        report = check_job_matching_model(max_sequence_length=1)

        exported = report.to_dict()

        self.assertTrue(exported["ok"])
        self.assertIn("traces", exported)
        self.assertIn("violations", exported)
        self.assertIn("dead_branches", exported)

        loaded = json.loads(report.to_json_text())
        self.assertTrue(loaded["ok"])
        self.assertGreater(len(loaded["traces"]), 0)


if __name__ == "__main__":
    unittest.main()
