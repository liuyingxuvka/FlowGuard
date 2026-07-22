import json
import gzip
import tempfile
import unittest
from pathlib import Path

from flowguard.model_regressions import MANIFEST_SCHEMA, run_manifest_regressions
from flowguard.model_purpose import build_model_purpose_closure, file_fingerprint


class LongCheckObservabilityTests(unittest.TestCase):
    def test_progress_precedes_terminal_receipt_and_full_output_is_artifact_backed(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as output:
            root = Path(directory)
            model_dir = root / ".flowguard" / "observable"
            model_dir.mkdir(parents=True)
            model_dir.joinpath("model.py").write_text("VALUE = 1\n", encoding="utf-8")
            model_dir.joinpath("run_checks.py").write_text("print('x' * 50000)\n", encoding="utf-8")
            purpose = build_model_purpose_closure(
                model_instance_id="regression:observable:current",
                reusable_model_type_id="observable",
                task_intent_id="flowguard-regression:observable-output",
                guarded_purpose="Prevent a long observable check from losing progress or terminal artifact evidence.",
                protected_failure_ids=("observable:progress-or-output-lost",),
                known_good_case_id="native-runner:observable:artifact-backed-output",
                failure_bindings=(
                    {
                        "failure_id": "observable:progress-or-output-lost",
                        "known_bad_case_id": "native-runner:observable:missing-progress-or-artifact",
                        "oracle_id": "native:observable:progress-and-artifact-oracle",
                    },
                ),
                claim_boundary="This temporary regression instance proves only progress ordering and artifact-backed output for its current fixture.",
                evidence_check_ids=("check:observable:progress-and-terminal-artifact",),
                model_sha256=file_fingerprint(model_dir / "model.py"),
                runner_sha256=file_fingerprint(model_dir / "run_checks.py"),
            )
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
                        "purpose_closure": purpose.to_dict(),
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
            stdout_object = Path(report.results[0].stdout_path)
            self.assertGreater(len(gzip.decompress(stdout_object.read_bytes())), 40000)
            self.assertLess(stdout_object.stat().st_size, 1000)
            self.assertGreater(report.results[0].stdout["logical_bytes"], 40000)
            self.assertLess(len(report.to_validation_result().format_text()), 1000)


if __name__ == "__main__":
    unittest.main()
