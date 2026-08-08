import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from flowguard.model_purpose import build_model_purpose_closure, file_fingerprint
from flowguard.model_regressions import MANIFEST_SCHEMA
from flowguard.self_blueprint import SELF_BLUEPRINT_DEFINITION_SCHEMA


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compile_flowguard_self_blueprint_definition.py"


def _load_compiler_module():
    spec = importlib.util.spec_from_file_location(
        "flowguard_self_blueprint_definition_compiler_test_module",
        SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


COMPILER = _load_compiler_module()


class SelfBlueprintDefinitionCompilerTests(unittest.TestCase):
    def _fixture(
        self,
        root: Path,
        *,
        owners=("alpha",),
        stale_identity: bool = False,
    ) -> Path:
        entries = []
        contract_rows = []
        for owner in owners:
            model_relative = f".flowguard/{owner}/model.py"
            runner_relative = f".flowguard/{owner}/run_checks.py"
            model_path = root / model_relative
            runner_path = root / runner_relative
            model_path.parent.mkdir(parents=True, exist_ok=True)
            model_path.write_text(f"MODEL_ID = {owner!r}\n", encoding="utf-8")
            runner_path.write_text("print('ok')\n", encoding="utf-8")
            purpose = build_model_purpose_closure(
                model_instance_id=f"regression:{owner}:current",
                reusable_model_type_id=owner,
                task_intent_id=f"flowguard-regression:{owner}",
                guarded_purpose=(
                    f"Prevent incomplete {owner} behavior from being accepted as current."
                ),
                protected_failure_ids=(f"{owner}:incomplete-current-behavior",),
                known_good_case_id=f"native:{owner}:complete-current-behavior",
                failure_bindings=(
                    {
                        "failure_id": f"{owner}:incomplete-current-behavior",
                        "known_bad_case_id": f"native:{owner}:incomplete-behavior",
                        "oracle_id": f"native:{owner}:run-checks",
                    },
                ),
                claim_boundary=(
                    f"Current closure covers the declared finite {owner} fixture only; "
                    "it does not prove undeclared behavior."
                ),
                evidence_check_ids=(f"native:{owner}:run-checks",),
                model_sha256=file_fingerprint(model_path),
                runner_sha256=file_fingerprint(runner_path),
            )
            entries.append(
                {
                    "absence_reason": "",
                    "distribution_policy": "required_public",
                    "exclusion_reason": "",
                    "expected_artifacts": [],
                    "input_globs": [model_relative, runner_relative],
                    "model_id": owner,
                    "model_path": model_relative,
                    "mutation_policy": "none",
                    "runner": ["{python}", runner_relative],
                    "shard_safe": True,
                    "tier": "fast",
                    "timeout_seconds": 10,
                    "purpose_closure": purpose.to_dict(),
                }
            )
            source_identity = {
                "purpose_source_id": (
                    ".flowguard/model-regression-manifest.json"
                    f"#model:{owner}:purpose-declaration"
                ),
                "purpose_source_owner_id": f"model-purpose-declaration:{owner}",
                "model_path": model_relative,
                "model_source_fingerprint": purpose.model_sha256,
                "runner_path": runner_relative,
                "runner_source_fingerprint": purpose.runner_sha256,
                "purpose_declaration_fingerprint": purpose.declaration_fingerprint,
                "purpose_closure_fingerprint": purpose.closure_fingerprint,
            }
            contract_rows.append(
                {
                    "owner_id": owner,
                    "surface_key": f"{model_relative}#<module>",
                    "contracts": {
                        "input": f"composite-contract:{owner}:input",
                        "state": f"composite-contract:{owner}:state",
                        "effect": f"composite-contract:{owner}:effect",
                        "output": f"composite-contract:{owner}:output",
                        "completion": f"composite-contract:{owner}:completion",
                        "semantics": f"composite-contract:{owner}:semantics",
                    },
                    "source_identity": source_identity,
                }
            )

        manifest = {
            "governed_input_globs": [".flowguard/**/*.py"],
            "snapshot_only_input_globs": [],
            "shared_input_groups": [],
            "models": entries,
            "schema_version": MANIFEST_SCHEMA,
        }
        manifest_path = root / ".flowguard" / "model-regression-manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        definition = {
            "schema_version": SELF_BLUEPRINT_DEFINITION_SCHEMA,
            "blueprint_id": "blueprint:test",
            "inventory_id": "implementation-inventory:test",
            "boundary": {"manual_boundary": "keep-this-authored-choice"},
            "scan_python_patterns": ["manual/**/*.py"],
            "scoped_out_patterns": ["manual/archive/**/*"],
            "bounded_dynamic_prefixes": ["getattr:"],
            "dynamic_allowances": [
                {
                    "surface_key": "manual.py#owner",
                    "operations": ["getattr"],
                    "rationale": "keep this exact authored allowance",
                }
            ],
            "dynamic_selector_contracts": [],
            "composite_behavior_contracts": contract_rows,
            "owner_overrides": {"manual.py": owners[0]},
            "resource_groups": [{"resource_id": "manual-resource"}],
            "claim_boundary": "Keep this exact manually authored blueprint boundary.",
        }
        if stale_identity:
            definition["composite_behavior_contracts"][0]["source_identity"][
                "model_source_fingerprint"
            ] = "sha256:" + ("0" * 64)
        definition_path = (
            root
            / ".flowguard"
            / "authoritative_model_system"
            / "software_blueprint_definition.json"
        )
        definition_path.parent.mkdir(parents=True, exist_ok=True)
        definition_path.write_text(
            json.dumps(definition, indent=2) + "\n",
            encoding="utf-8",
        )
        return definition_path

    def _run(self, root: Path, *args: str):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(root), *args],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        return completed, json.loads(completed.stdout)

    @staticmethod
    def _authored_projection(payload):
        result = copy.deepcopy(payload)
        for row in result["composite_behavior_contracts"]:
            row.pop("source_identity")
        return result

    @staticmethod
    def _manifest_authored_projection(payload):
        result = copy.deepcopy(payload)
        for row in result["models"]:
            purpose = row["purpose_closure"]
            for field in (
                "model_sha256",
                "runner_sha256",
                "declaration_fingerprint",
                "closure_fingerprint",
            ):
                purpose.pop(field)
        return result

    def test_default_check_reports_diff_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            definition_path = self._fixture(root, stale_identity=True)
            before = definition_path.read_bytes()

            completed, result = self._run(root)

            self.assertEqual(1, completed.returncode, completed.stderr)
            self.assertFalse(result["ok"])
            self.assertEqual("check", result["mode"])
            self.assertTrue(result["changed"])
            self.assertFalse(result["wrote"])
            self.assertFalse(result["manifest_changed"])
            self.assertTrue(result["definition_changed"])
            self.assertEqual(["alpha"], result["changed_owner_ids"])
            self.assertEqual(
                ["model_source_fingerprint"],
                result["source_identity_diffs"][0]["changed_fields"],
            )
            self.assertEqual(before, definition_path.read_bytes())

    def test_authored_dynamic_selector_contracts_are_rejected_in_v5(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            definition_path = self._fixture(root)
            definition = json.loads(definition_path.read_text(encoding="utf-8"))
            definition["dynamic_selector_contracts"] = [
                {
                    "surface_key": "manual.py#owner",
                    "operation": "getattr",
                }
            ]
            definition_path.write_text(
                json.dumps(definition, indent=2) + "\n",
                encoding="utf-8",
            )

            completed, result = self._run(root)

            self.assertNotEqual(0, completed.returncode)
            self.assertFalse(result["ok"])
            self.assertIn("cannot be authored", result["error"])

    def test_explicit_write_refreshes_only_identities_and_then_checks_current(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            definition_path = self._fixture(
                root,
                owners=("alpha", "beta"),
                stale_identity=True,
            )
            before = json.loads(definition_path.read_text(encoding="utf-8"))

            completed, result = self._run(root, "--write")

            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertTrue(result["ok"])
            self.assertTrue(result["changed"])
            self.assertTrue(result["wrote"])
            self.assertFalse(result["manifest_wrote"])
            self.assertTrue(result["definition_wrote"])
            after = json.loads(definition_path.read_text(encoding="utf-8"))
            self.assertEqual(
                self._authored_projection(before),
                self._authored_projection(after),
            )
            manifest = json.loads(
                (root / ".flowguard" / "model-regression-manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            purposes = {
                row["model_id"]: row["purpose_closure"]
                for row in manifest["models"]
            }
            for row in after["composite_behavior_contracts"]:
                purpose = purposes[row["owner_id"]]
                identity = row["source_identity"]
                self.assertEqual(purpose["model_sha256"], identity["model_source_fingerprint"])
                self.assertEqual(purpose["runner_sha256"], identity["runner_source_fingerprint"])
                self.assertEqual(
                    purpose["declaration_fingerprint"],
                    identity["purpose_declaration_fingerprint"],
                )
                self.assertEqual(
                    purpose["closure_fingerprint"],
                    identity["purpose_closure_fingerprint"],
                )

            check, current = self._run(root)
            self.assertEqual(0, check.returncode, check.stderr)
            self.assertTrue(current["ok"])
            self.assertFalse(current["changed"])
            self.assertFalse(current["wrote"])

    def test_explicit_write_refreshes_manifest_purpose_before_blueprint_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            definition_path = self._fixture(root, owners=("alpha", "beta"))
            manifest_path = root / ".flowguard" / "model-regression-manifest.json"
            model_path = root / ".flowguard" / "alpha" / "model.py"
            model_path.write_text("MODEL_ID = 'alpha-current'\n", encoding="utf-8")
            manifest_before = json.loads(manifest_path.read_text(encoding="utf-8"))
            definition_before = json.loads(
                definition_path.read_text(encoding="utf-8")
            )

            check, stale = self._run(root)

            self.assertEqual(1, check.returncode, check.stderr)
            self.assertTrue(stale["manifest_changed"])
            self.assertTrue(stale["definition_changed"])
            self.assertFalse(stale["wrote"])
            self.assertEqual(["alpha"], stale["changed_owner_ids"])
            self.assertEqual(
                ["model_sha256", "closure_fingerprint"],
                stale["purpose_fingerprint_diffs"][0]["changed_fields"],
            )
            self.assertEqual(
                manifest_before,
                json.loads(manifest_path.read_text(encoding="utf-8")),
            )

            paths = []
            original_atomic_write = COMPILER._atomic_write

            def record_atomic_write(path, payload):
                paths.append(path)
                original_atomic_write(path, payload)

            with patch.object(COMPILER, "_atomic_write", record_atomic_write):
                result = COMPILER.compile_self_blueprint_definition(root, write=True)

            self.assertTrue(result["ok"])
            self.assertTrue(result["manifest_wrote"])
            self.assertTrue(result["definition_wrote"])
            self.assertEqual([manifest_path, definition_path], paths)
            manifest_after = json.loads(manifest_path.read_text(encoding="utf-8"))
            definition_after = json.loads(
                definition_path.read_text(encoding="utf-8")
            )
            self.assertEqual(
                self._manifest_authored_projection(manifest_before),
                self._manifest_authored_projection(manifest_after),
            )
            self.assertEqual(
                self._authored_projection(definition_before),
                self._authored_projection(definition_after),
            )
            purposes = {
                row["model_id"]: row["purpose_closure"]
                for row in manifest_after["models"]
            }
            identities = {
                row["owner_id"]: row["source_identity"]
                for row in definition_after["composite_behavior_contracts"]
            }
            self.assertEqual(
                purposes["alpha"]["closure_fingerprint"],
                identities["alpha"]["purpose_closure_fingerprint"],
            )

            current = COMPILER.compile_self_blueprint_definition(root)
            self.assertTrue(current["ok"])
            self.assertFalse(current["changed"])

    def test_missing_foreign_and_duplicate_owner_inventories_hard_fail(self):
        cases = ("missing", "foreign", "duplicate")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                definition_path = self._fixture(root)
                payload = json.loads(definition_path.read_text(encoding="utf-8"))
                if case == "missing":
                    payload["composite_behavior_contracts"] = []
                elif case == "foreign":
                    row = copy.deepcopy(payload["composite_behavior_contracts"][0])
                    row["owner_id"] = "foreign"
                    row["surface_key"] = ".flowguard/foreign/model.py#<module>"
                    payload["composite_behavior_contracts"].append(row)
                else:
                    payload["composite_behavior_contracts"].append(
                        copy.deepcopy(payload["composite_behavior_contracts"][0])
                    )
                definition_path.write_text(
                    json.dumps(payload, indent=2) + "\n",
                    encoding="utf-8",
                )
                before = definition_path.read_bytes()

                completed, result = self._run(root, "--write")

                self.assertEqual(1, completed.returncode, completed.stderr)
                self.assertFalse(result["ok"])
                self.assertIn(case, result["error"])
                self.assertFalse(result["wrote"])
                self.assertEqual(before, definition_path.read_bytes())

    def test_post_write_source_drift_restores_original_definition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            definition_path = self._fixture(root, stale_identity=True)
            original_definition = definition_path.read_bytes()
            model_path = root / ".flowguard" / "alpha" / "model.py"
            original_atomic_write = COMPILER._atomic_write
            calls = 0

            def atomic_write_then_drift(path, payload):
                nonlocal calls
                calls += 1
                original_atomic_write(path, payload)
                if calls == 1:
                    model_path.write_text(
                        "MODEL_ID = 'alpha-drifted'\n",
                        encoding="utf-8",
                    )

            with patch.object(COMPILER, "_atomic_write", atomic_write_then_drift):
                with self.assertRaisesRegex(
                    COMPILER.SelfBlueprintDefinitionInputDriftError,
                    "atomically restored",
                ):
                    COMPILER.compile_self_blueprint_definition(root, write=True)

            self.assertEqual(2, calls)
            self.assertEqual(original_definition, definition_path.read_bytes())
            self.assertEqual([], list(definition_path.parent.glob("*.tmp")))

    def test_drift_after_manifest_write_restores_manifest_and_leaves_definition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            definition_path = self._fixture(root)
            manifest_path = root / ".flowguard" / "model-regression-manifest.json"
            model_path = root / ".flowguard" / "alpha" / "model.py"
            runner_path = root / ".flowguard" / "alpha" / "run_checks.py"
            model_path.write_text("MODEL_ID = 'alpha-current'\n", encoding="utf-8")
            original_manifest = manifest_path.read_bytes()
            original_definition = definition_path.read_bytes()
            original_atomic_write = COMPILER._atomic_write
            calls = []

            def atomic_write_then_drift(path, payload):
                calls.append(path)
                original_atomic_write(path, payload)
                if len(calls) == 1:
                    runner_path.write_text("print('peer-drift')\n", encoding="utf-8")

            with patch.object(COMPILER, "_atomic_write", atomic_write_then_drift):
                with self.assertRaisesRegex(
                    COMPILER.SelfBlueprintDefinitionInputDriftError,
                    "atomically restored",
                ):
                    COMPILER.compile_self_blueprint_definition(root, write=True)

            self.assertEqual([manifest_path, manifest_path], calls)
            self.assertEqual(original_manifest, manifest_path.read_bytes())
            self.assertEqual(original_definition, definition_path.read_bytes())
            self.assertEqual([], list(manifest_path.parent.glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()
