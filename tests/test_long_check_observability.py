import json
import tempfile
import unittest
from pathlib import Path

from flowguard.model_regressions import MANIFEST_SCHEMA, run_manifest_regressions


class LongCheckObservabilityTests(unittest.TestCase):
    def test_progress_precedes_terminal_receipt_and_full_output_is_artifact_backed(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as output:
            root = Path(directory)
            model_dir = root / ".flowguard" / "observable"
            model_dir.mkdir(parents=True)
            model_dir.joinpath("model.py").write_text("VALUE = 1\n", encoding="utf-8")
            model_dir.joinpath("run_checks.py").write_text("print('x' * 50000)\n", encoding="utf-8")
            manifest = {
                "schema_version": MANIFEST_SCHEMA,
                "models": [
                    {
                        "model_id": "observable",
                        "model_path": ".flowguard/observable/model.py",
                        "runner": ["{python}", ".flowguard/observable/run_checks.py"],
                        "tier": "fast",
                        "timeout_seconds": 5,
                        "shard_safe": True,
                        "mutation_policy": "none",
                        "input_globs": [".flowguard/observable/model.py", ".flowguard/observable/run_checks.py"],
                        "expected_artifacts": [],
                        "exclusion_reason": "",
                    }
                ],
            }
            (root / ".flowguard" / "model-regression-manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            events = []
            report = run_manifest_regressions(root, output_dir=output, progress=events.append)
            self.assertEqual(["started", "finished"], [item["event"] for item in events])
            self.assertTrue(Path(report.results[0].receipt_path).is_file())
            self.assertGreater(Path(report.results[0].stdout_path).stat().st_size, 40000)
            self.assertLess(len(report.to_validation_result().format_text()), 1000)


if __name__ == "__main__":
    unittest.main()
