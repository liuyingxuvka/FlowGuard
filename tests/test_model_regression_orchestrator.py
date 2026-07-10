import json
import tempfile
import textwrap
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from flowguard.model_regressions import MANIFEST_SCHEMA, run_manifest_regressions


class ModelRegressionOrchestratorTests(unittest.TestCase):
    def make_repo(self, specs: list[dict[str, object]]) -> Path:
        root = Path(self.tempdir.name)
        models = []
        for spec in specs:
            model_id = str(spec["model_id"])
            model_dir = root / ".flowguard" / model_id
            model_dir.mkdir(parents=True)
            model_dir.joinpath("model.py").write_text("VALUE = 1\n", encoding="utf-8")
            model_dir.joinpath("run_checks.py").write_text(str(spec["script"]), encoding="utf-8")
            models.append(
                {
                    "model_id": model_id,
                    "model_path": f".flowguard/{model_id}/model.py",
                    "runner": ["{python}", f".flowguard/{model_id}/run_checks.py"],
                    "tier": spec.get("tier", "fast"),
                    "timeout_seconds": spec.get("timeout_seconds", 5),
                    "shard_safe": spec.get("shard_safe", True),
                    "mutation_policy": spec.get("mutation_policy", "none"),
                    "input_globs": [f".flowguard/{model_id}/model.py", f".flowguard/{model_id}/run_checks.py"],
                    "expected_artifacts": spec.get("expected_artifacts", []),
                    "exclusion_reason": "",
                }
            )
        (root / ".flowguard" / "model-regression-manifest.json").write_text(
            json.dumps({"schema_version": MANIFEST_SCHEMA, "models": models}), encoding="utf-8"
        )
        return root

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_timeout_produces_terminal_receipt_and_distinct_status(self):
        root = self.make_repo(
            [{"model_id": "slow", "script": "import time\ntime.sleep(10)\n", "timeout_seconds": 0.2}]
        )
        report = run_manifest_regressions(root, tier="full", output_dir=root.parent / "out-timeout")
        self.assertEqual("timeout", report.status)
        receipt = json.loads(Path(report.results[0].receipt_path).read_text(encoding="utf-8"))
        self.assertTrue(receipt["terminal"])
        self.assertEqual("timeout", receipt["status"])

    def test_cancellation_is_propagated_to_child_receipt(self):
        root = self.make_repo([{"model_id": "slow", "script": "import time\ntime.sleep(10)\n"}])
        cancel = threading.Event()
        timer = threading.Timer(0.2, cancel.set)
        timer.start()
        try:
            report = run_manifest_regressions(
                root, tier="full", output_dir=root.parent / "out-cancel", cancel_event=cancel
            )
        finally:
            timer.cancel()
        self.assertEqual("cancelled", report.status)
        self.assertEqual("cancelled", report.results[0].status)

    def test_parallel_run_rejects_non_shard_safe_entry(self):
        root = self.make_repo(
            [{"model_id": "unsafe", "script": "print('ok')\n", "shard_safe": False}]
        )
        with self.assertRaisesRegex(ValueError, "non-shard-safe"):
            run_manifest_regressions(root, tier="full", jobs=2, output_dir=root.parent / "out-unsafe")

    def test_tiers_filters_and_shards_have_scoped_claims(self):
        root = self.make_repo(
            [
                {"model_id": "a", "script": "print('a')\n", "tier": "fast"},
                {"model_id": "b", "script": "print('b')\n", "tier": "focused"},
                {"model_id": "c", "script": "print('c')\n", "tier": "full"},
            ]
        )
        fast = run_manifest_regressions(root, tier="fast", output_dir=root.parent / "out-fast")
        shard = run_manifest_regressions(root, tier="full", shard="2/3", output_dir=root.parent / "out-shard")
        self.assertEqual(("a",), fast.selected_model_ids)
        self.assertIn("does not support a full-model release claim", fast.to_validation_result().claim_boundary)
        self.assertEqual(("b",), shard.selected_model_ids)

    def test_isolated_artifact_is_required_and_preserved(self):
        script = textwrap.dedent(
            """
            import os
            from pathlib import Path
            target = Path(os.environ['FLOWGUARD_OUTPUT_DIR']) / 'result.json'
            target.write_text('{"ok": true}', encoding='utf-8')
            """
        )
        root = self.make_repo(
            [{"model_id": "artifact", "script": script, "expected_artifacts": ["result.json"]}]
        )
        report = run_manifest_regressions(root, tier="full", output_dir=root.parent / "out-artifact")
        self.assertTrue(report.ok, report.to_dict())
        self.assertTrue(Path(report.results[0].artifact_paths[0]).is_file())

    def test_tracked_mutation_blocks_success(self):
        script = "from pathlib import Path\nPath('tracked.txt').write_text('changed', encoding='utf-8')\n"
        root = self.make_repo([{"model_id": "writer", "script": script}])
        root.joinpath("tracked.txt").write_text("before", encoding="utf-8")
        with patch("flowguard.model_regressions._tracked_paths", return_value=(root / "tracked.txt",)):
            report = run_manifest_regressions(root, tier="full", output_dir=root.parent / "out-mutation")
        self.assertEqual("blocked", report.status)
        self.assertEqual(("tracked.txt",), report.mutation_paths)


if __name__ == "__main__":
    unittest.main()
