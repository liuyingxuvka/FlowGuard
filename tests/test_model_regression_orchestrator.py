import json
import gzip
import tempfile
import textwrap
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from flowguard.model_regressions import MANIFEST_SCHEMA, run_manifest_regressions
from flowguard.model_purpose import build_model_purpose_closure, file_fingerprint


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
            purpose = build_model_purpose_closure(
                model_instance_id=f"regression:{model_id}:current",
                reusable_model_type_id=model_id,
                task_intent_id=f"flowguard-regression:{model_id}",
                guarded_purpose=f"Prevent the {model_id} model from accepting an invalid current outcome as completed evidence.",
                protected_failure_ids=(f"{model_id}:invalid",),
                known_good_case_id=f"native-runner:{model_id}:good",
                failure_bindings=({
                    "failure_id": f"{model_id}:invalid",
                    "known_bad_case_id": f"native-runner:{model_id}:bad",
                    "oracle_id": f"native:{model_id}:runner",
                },),
                claim_boundary=f"Current {model_id} fixture closure proves only the declared temporary test boundary and no production behavior.",
                evidence_check_ids=(f"check:{model_id}",),
                model_sha256=file_fingerprint(model_dir / "model.py"),
                runner_sha256=file_fingerprint(model_dir / "run_checks.py"),
            )
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
                    "purpose_closure": purpose.to_dict(),
                }
            )
        (root / ".flowguard" / "model-regression-manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": MANIFEST_SCHEMA,
                    "governed_input_globs": [".flowguard/**/*.py"],
                    "snapshot_only_input_globs": [],
                    "shared_input_groups": [],
                    "models": models,
                }
            ),
            encoding="utf-8",
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
        report = run_manifest_regressions(root, tier="full", output_dir=root / "outputs" / "out-timeout")
        self.assertEqual("timeout", report.status)
        receipt = json.loads(Path(report.results[0].receipt_path).read_text(encoding="utf-8"))
        self.assertEqual("1.0", receipt["schema_version"])
        self.assertEqual("error", receipt["result_status"])
        self.assertIn("owner_status:timeout", receipt["blockers"])
        result = report.results[0]
        self.assertEqual("regression:slow:current", result.model_instance_id)
        self.assertTrue(result.model_instance_fingerprint.startswith("sha256:"))
        self.assertEqual("executable_workflow", result.model_kind)
        self.assertTrue(result.input_inventory_fingerprint.startswith("sha256:"))
        self.assertEqual(
            [
                ".flowguard/slow/model.py",
                ".flowguard/slow/run_checks.py",
            ],
            [item["path"] for item in result.input_inventory],
        )
        self.assertTrue(
            all(item["sha256"].startswith("sha256:") for item in result.input_inventory)
        )
        self.assertTrue(result.purpose_closure_fingerprint.startswith("sha256:"))

    def test_cancellation_is_propagated_to_child_receipt(self):
        root = self.make_repo([{"model_id": "slow", "script": "import time\ntime.sleep(10)\n"}])
        cancel = threading.Event()
        timer = threading.Timer(0.2, cancel.set)
        timer.start()
        try:
            report = run_manifest_regressions(
                root, tier="full", output_dir=root / "outputs" / "out-cancel", cancel_event=cancel
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
            run_manifest_regressions(root, tier="full", jobs=2, output_dir=root / "outputs" / "out-unsafe")

    def test_tiers_filters_and_shards_have_scoped_claims(self):
        root = self.make_repo(
            [
                {"model_id": "a", "script": "print('a')\n", "tier": "fast"},
                {"model_id": "b", "script": "print('b')\n", "tier": "focused"},
                {"model_id": "c", "script": "print('c')\n", "tier": "full"},
            ]
        )
        fast = run_manifest_regressions(root, tier="fast", output_dir=root / "outputs" / "out-fast")
        shard = run_manifest_regressions(root, tier="full", shard="2/3", output_dir=root / "outputs" / "out-shard")
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
        report = run_manifest_regressions(root, tier="full", output_dir=root / "outputs" / "out-artifact")
        self.assertTrue(report.ok, report.to_dict())
        self.assertTrue(Path(report.results[0].artifact_paths[0]).is_file())

    def test_parent_logs_survive_child_replacing_isolated_output_directory(self):
        script = textwrap.dedent(
            """
            import os
            import shutil
            from pathlib import Path
            target = Path(os.environ['FLOWGUARD_OUTPUT_DIR'])
            shutil.rmtree(target)
            target.mkdir(parents=True)
            print('child replaced output directory')
            """
        )
        root = self.make_repo([{"model_id": "replacer", "script": script}])
        report = run_manifest_regressions(root, tier="full", output_dir=root / "outputs" / "out-replacer")
        self.assertTrue(report.ok, report.to_dict())
        self.assertIn(
            "child replaced output directory",
            gzip.decompress(Path(report.results[0].stdout_path).read_bytes()).decode("utf-8"),
        )
        self.assertTrue(Path(report.results[0].receipt_path).is_file())

    def test_child_imports_the_selected_repository_before_an_external_installation(self):
        root = self.make_repo(
            [
                {
                    "model_id": "source-identity",
                    "script": "import selected_repository_module\n"
                    "print(selected_repository_module.IDENTITY)\n",
                }
            ]
        )
        root.joinpath("selected_repository_module.py").write_text(
            "IDENTITY = 'selected repository'\n", encoding="utf-8"
        )
        with patch.dict("os.environ", {"PYTHONPATH": str(root.parent / "unrelated-install")}, clear=False):
            report = run_manifest_regressions(
                root, tier="full", output_dir=root / "outputs" / "out-source-identity"
            )
        self.assertTrue(report.ok, report.to_dict())
        self.assertIn(
            "selected repository",
            gzip.decompress(Path(report.results[0].stdout_path).read_bytes()).decode("utf-8"),
        )

    def test_tracked_mutation_blocks_success(self):
        script = "from pathlib import Path\nPath('tracked.txt').write_text('changed', encoding='utf-8')\n"
        root = self.make_repo([{"model_id": "writer", "script": script}])
        root.joinpath("tracked.txt").write_text("before", encoding="utf-8")
        with patch("flowguard.model_regressions._tracked_paths", return_value=(root / "tracked.txt",)):
            report = run_manifest_regressions(root, tier="full", output_dir=root / "outputs" / "out-mutation")
        self.assertEqual("blocked", report.status)
        self.assertEqual(("tracked.txt",), report.mutation_paths)

    def test_identical_second_run_reuses_receipt_without_invoking_runner(self):
        script = (
            "from pathlib import Path\n"
            "path = Path('invocations.txt')\n"
            "count = int(path.read_text() if path.exists() else '0')\n"
            "path.write_text(str(count + 1), encoding='utf-8')\n"
        )
        root = self.make_repo([{"model_id": "cached", "script": script}])
        with patch("flowguard.model_regressions._tracked_paths", return_value=()):
            first = run_manifest_regressions(
                root,
                tier="full",
                output_dir=root / "outputs" / "out-first",
            )
            second = run_manifest_regressions(
                root,
                tier="full",
                output_dir=root / "outputs" / "out-second",
            )
        self.assertTrue(first.ok, first.to_dict())
        self.assertTrue(second.ok, second.to_dict())
        self.assertEqual("1", (root / "invocations.txt").read_text(encoding="utf-8"))
        self.assertEqual("execute", first.results[0].execution_disposition)
        self.assertEqual("reuse_current", second.results[0].execution_disposition)
        self.assertEqual(0, second.results[0].producer_invocations)
        self.assertEqual(
            first.results[0].receipt_fingerprint,
            second.results[0].receipt_fingerprint,
        )

    def test_one_model_input_change_executes_only_that_model(self):
        script = (
            "from pathlib import Path\n"
            "model_id = __import__('os').environ['FLOWGUARD_MODEL_ID']\n"
            "path = Path(f'{model_id}-invocations.txt')\n"
            "count = int(path.read_text() if path.exists() else '0')\n"
            "path.write_text(str(count + 1), encoding='utf-8')\n"
        )
        root = self.make_repo(
            [
                {"model_id": "alpha", "script": script},
                {"model_id": "beta", "script": script},
            ]
        )
        alpha_config = root / ".flowguard" / "alpha" / "config.json"
        alpha_config.write_text('{"value": 1}\n', encoding="utf-8")
        manifest_path = root / ".flowguard" / "model-regression-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["models"][0]["input_globs"].append(
            ".flowguard/alpha/config.json"
        )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with patch("flowguard.model_regressions._tracked_paths", return_value=()):
            first = run_manifest_regressions(
                root,
                tier="full",
                output_dir=root / "outputs" / "out-first",
            )
            alpha_config.write_text('{"value": 2}\n', encoding="utf-8")
            second = run_manifest_regressions(
                root,
                tier="full",
                output_dir=root / "outputs" / "out-second",
            )
        self.assertTrue(first.ok, first.to_dict())
        self.assertTrue(second.ok, second.to_dict())
        by_id = {item.model_id: item for item in second.results}
        self.assertEqual("execute", by_id["alpha"].execution_disposition)
        self.assertEqual("reuse_current", by_id["beta"].execution_disposition)
        self.assertEqual("2", (root / "alpha-invocations.txt").read_text(encoding="utf-8"))
        self.assertEqual("1", (root / "beta-invocations.txt").read_text(encoding="utf-8"))

    def test_one_manifest_entry_change_executes_only_that_model(self):
        script = (
            "from pathlib import Path\n"
            "model_id = __import__('os').environ['FLOWGUARD_MODEL_ID']\n"
            "path = Path(f'{model_id}-manifest-invocations.txt')\n"
            "count = int(path.read_text() if path.exists() else '0')\n"
            "path.write_text(str(count + 1), encoding='utf-8')\n"
        )
        root = self.make_repo(
            [
                {"model_id": "alpha", "script": script},
                {"model_id": "beta", "script": script},
            ]
        )
        with patch("flowguard.model_regressions._tracked_paths", return_value=()):
            first = run_manifest_regressions(
                root,
                tier="full",
                output_dir=root / "outputs" / "out-first",
            )
            manifest_path = (
                root / ".flowguard" / "model-regression-manifest.json"
            )
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            beta = next(
                item
                for item in manifest["models"]
                if item["model_id"] == "beta"
            )
            beta["timeout_seconds"] = 6
            manifest_path.write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
            second = run_manifest_regressions(
                root,
                tier="full",
                output_dir=root / "outputs" / "out-second",
            )

        self.assertTrue(first.ok, first.to_dict())
        self.assertTrue(second.ok, second.to_dict())
        by_id = {item.model_id: item for item in second.results}
        self.assertEqual("reuse_current", by_id["alpha"].execution_disposition)
        self.assertEqual("execute", by_id["beta"].execution_disposition)
        self.assertEqual(
            "1",
            (root / "alpha-manifest-invocations.txt").read_text(
                encoding="utf-8"
            ),
        )
        self.assertEqual(
            "2",
            (root / "beta-manifest-invocations.txt").read_text(
                encoding="utf-8"
            ),
        )


if __name__ == "__main__":
    unittest.main()
