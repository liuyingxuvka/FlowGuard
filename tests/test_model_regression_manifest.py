import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flowguard.model_regressions import (
    MANIFEST_SCHEMA,
    ModelRegressionManifest,
    audit_manifest,
    discover_model_directories,
)
from flowguard.model_purpose import build_model_purpose_closure, file_fingerprint


class ModelRegressionManifestTests(unittest.TestCase):
    def test_repository_manifest_accounts_for_every_model(self):
        root = Path(__file__).resolve().parents[1]
        manifest = ModelRegressionManifest.load(root)
        audit = audit_manifest(root, manifest)
        self.assertTrue(audit.ok, audit.errors)
        self.assertEqual(62, len(audit.registered_model_ids))
        discovered = {
            path.relative_to(root / ".flowguard").as_posix()
            for path in discover_model_directories(root)
        }
        required_public = {
            entry.model_id
            for entry in manifest.entries
            if entry.distribution_policy == "required_public"
        }
        self.assertTrue(required_public.issubset(discovered))
        self.assertTrue(discovered.issubset(set(audit.registered_model_ids)))
        self.assertIn("template_public_release", audit.registered_model_ids)

    def test_required_public_model_entries_are_tracked_release_files(self):
        git = shutil.which("git")
        if not git:
            self.skipTest("git is required to verify public model distribution")
        root = Path(__file__).resolve().parents[1]
        repository_probe = subprocess.run(
            [git, "rev-parse", "--is-inside-work-tree"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if repository_probe.returncode != 0:
            self.skipTest("public model distribution check requires a git checkout")
        completed = subprocess.run([git, "ls-files", "-z"], cwd=root, capture_output=True, check=True)
        tracked = {
            item.decode("utf-8", errors="surrogateescape").replace("\\", "/")
            for item in completed.stdout.split(b"\0")
            if item
        }
        # The new manifest and the formerly omitted template runner are part of
        # this release and are force-added by the release workflow.
        tracked.update(
            {
                ".flowguard/model-regression-manifest.json",
                ".flowguard/template_public_release/model.py",
                ".flowguard/template_public_release/run_checks.py",
                ".flowguard/development_process_strategy/model.py",
                ".flowguard/development_process_strategy/run_checks.py",
                ".flowguard/compositional_verification_kernel/model.py",
                ".flowguard/compositional_verification_kernel/run_checks.py",
                ".flowguard/task_local_prediction_replay/model.py",
                ".flowguard/task_local_prediction_replay/run_checks.py",
                ".flowguard/spec_context/model.py",
                ".flowguard/spec_context/run_checks.py",
                "flowguard/spec_context.py",
                ".flowguard/bounded_system_composition_benchmark/model.py",
                ".flowguard/bounded_system_composition_benchmark/run_checks.py",
            }
        )
        manifest = ModelRegressionManifest.load(root)
        for entry in manifest.entries:
            with self.subTest(model=entry.model_id):
                if entry.distribution_policy == "required_public":
                    self.assertIn(entry.model_path, tracked)
                    self.assertIn(entry.runner[1], tracked)
                else:
                    self.assertGreaterEqual(len(entry.absence_reason), 12)

    def test_ui_content_visibility_model_accepts_external_output_directory(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            env = os.environ.copy()
            env["FLOWGUARD_OUTPUT_DIR"] = directory
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import runpy; "
                        "model = runpy.run_path('.flowguard/harden_ui_content_visibility_validation/model.py'); "
                        "print(model['CORE_PYTEST_ARGS'][-1])"
                    ),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertIn(Path(directory).resolve().as_posix(), completed.stdout.replace("\\", "/"))

    def test_unregistered_and_extra_records_are_both_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            present = root / ".flowguard" / "present"
            present.mkdir(parents=True)
            present.joinpath("model.py").write_text("if __name__ == '__main__': pass\n", encoding="utf-8")
            payload = {
                "schema_version": MANIFEST_SCHEMA,
                "models": [self.entry("extra", root)],
            }
            manifest_path = root / ".flowguard" / "model-regression-manifest.json"
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            audit = audit_manifest(root, ModelRegressionManifest.load(root))
            self.assertFalse(audit.ok)
            self.assertTrue(any("unregistered model directory: present" in item for item in audit.errors))
            self.assertTrue(any("manifest required-public model missing from filesystem: extra" in item for item in audit.errors))

    def test_absent_optional_local_record_is_explicit_but_not_a_public_blocker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".flowguard").mkdir()
            entry = {
                **self.entry("local_only", root),
                "distribution_policy": "optional_local",
                "absence_reason": "This checkout-local model is executed only when its adoption record is present.",
            }
            (root / ".flowguard" / "model-regression-manifest.json").write_text(
                json.dumps({"schema_version": MANIFEST_SCHEMA, "models": [entry]}), encoding="utf-8"
            )
            audit = audit_manifest(root, ModelRegressionManifest.load(root))
            self.assertTrue(audit.ok, audit.errors)

    def test_invalid_runner_and_unjustified_exclusion_fail_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_dir = root / ".flowguard" / "sample"
            model_dir.mkdir(parents=True)
            model_dir.joinpath("model.py").write_text("print('model')\n", encoding="utf-8")
            payload = {
                "schema_version": MANIFEST_SCHEMA,
                "models": [{**self.entry("sample", root), "runner": [], "exclusion_reason": "short"}],
            }
            (root / ".flowguard" / "model-regression-manifest.json").write_text(json.dumps(payload), encoding="utf-8")
            audit = audit_manifest(root, ModelRegressionManifest.load(root))
            self.assertFalse(audit.ok)
            self.assertTrue(any("exclusion reason" in item for item in audit.errors))

    @staticmethod
    def entry(model_id: str, root: Path) -> dict[str, object]:
        model_path = root / ".flowguard" / model_id / "model.py"
        runner_path = root / ".flowguard" / model_id / "run_checks.py"
        zero = "sha256:" + "0" * 64
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
            model_sha256=file_fingerprint(model_path) if model_path.is_file() else zero,
            runner_sha256=file_fingerprint(runner_path) if runner_path.is_file() else zero,
        )
        return {
            "model_id": model_id,
            "model_path": f".flowguard/{model_id}/model.py",
            "runner": ["{python}", f".flowguard/{model_id}/run_checks.py"],
            "tier": "full",
            "timeout_seconds": 10,
            "shard_safe": True,
            "mutation_policy": "none",
            "input_globs": [f".flowguard/{model_id}/model.py"],
            "expected_artifacts": [],
            "exclusion_reason": "",
            "purpose_closure": purpose.to_dict(),
        }


if __name__ == "__main__":
    unittest.main()
