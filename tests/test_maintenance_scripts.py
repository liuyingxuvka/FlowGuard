import contextlib
import io
import tempfile
import textwrap
import unittest
from pathlib import Path

import importlib.metadata as metadata

from scripts.run_flowguard_model_regressions import main as run_model_regressions
from scripts.generate_field_lifecycle_inventory import (
    collect_field_inventory,
    infer_ai_surface_tier,
    infer_lifecycle_layer,
    infer_route_owner,
)
from scripts.sync_shadow_workspace import sync_workspace, verify_workspace


class MaintenanceScriptTests(unittest.TestCase):
    def test_model_regression_runner_requires_manifest_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = run_model_regressions(
                    ["--root", str(root), "--json"]
                )

            self.assertEqual(3, exit_code)
            self.assertIn("missing model regression manifest", output.getvalue())

    def test_shadow_sync_preserves_shadow_only_files(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
            source = Path(source_dir)
            target = Path(target_dir)
            source_file = source / "flowguard" / "module.py"
            source_file.parent.mkdir()
            source_file.write_text("VALUE = 1\n", encoding="utf-8")
            shadow_only = target / "peer_work.txt"
            shadow_only.write_text("keep me\n", encoding="utf-8")

            result = sync_workspace(source, target, source_sets=("flowguard",))

            self.assertIn("flowguard/module.py", result.copied_files)
            self.assertTrue((target / "flowguard" / "module.py").exists())
            self.assertEqual("keep me\n", shadow_only.read_text(encoding="utf-8"))

    def test_default_shadow_sync_includes_canonical_skillguard_inventory(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
            source = Path(source_dir)
            target = Path(target_dir)
            suite_map = source / ".skillguard" / "flowguard-suite" / "suite-map.json"
            suite_map.parent.mkdir(parents=True)
            suite_map.write_text('{"schema_version":"flowguard.skill_suite.v1"}\n', encoding="utf-8")

            result = sync_workspace(source, target)

            self.assertIn(".skillguard/flowguard-suite/suite-map.json", result.copied_files)
            self.assertEqual(suite_map.read_bytes(), (target / ".skillguard" / "flowguard-suite" / "suite-map.json").read_bytes())

    def test_shadow_verify_checks_import_path_version_and_helper(self):
        with tempfile.TemporaryDirectory() as target_dir:
            target = Path(target_dir)
            package = target / "flowguard"
            package.mkdir()
            package.joinpath("__init__.py").write_text(
                textwrap.dedent(
                    """
                    SCHEMA_VERSION = "1.0"
                    __version__ = "{version}"

                    def default_flowguard_self_maintenance_plan():
                        return None
                    """
                ).format(version=metadata.version("flowguard")).strip()
                + "\n",
                encoding="utf-8",
            )

            report = verify_workspace(target, expected_version=metadata.version("flowguard"))

            self.assertTrue(report["ok"], report)
            self.assertIn(str(package), report["source_path"])
            self.assertTrue(report["helper_available"])

    def test_field_inventory_infers_lifecycle_layers(self):
        self.assertEqual("behavior_or_contract", infer_lifecycle_layer("external_inputs"))
        self.assertEqual("compatibility_or_old_path", infer_lifecycle_layer("legacy_alias"))
        self.assertEqual("evidence_or_decision", infer_lifecycle_layer("evidence_refs"))
        self.assertEqual("display_or_metadata", infer_lifecycle_layer("description"))
        self.assertEqual("model_test_alignment", infer_route_owner("model_test_alignment"))
        self.assertEqual(
            "starter",
            infer_ai_surface_tier("owner_code_contract_id", "behavior_or_contract", "model_test_alignment"),
        )
        self.assertEqual(
            "advanced",
            infer_ai_surface_tier("legacy_alias", "compatibility_or_old_path", "field_lifecycle_mesh"),
        )

    def test_field_inventory_collects_dataclass_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "flowguard"
            package.mkdir()
            package.joinpath("sample.py").write_text(
                textwrap.dedent(
                    """
                    from dataclasses import dataclass

                    @dataclass(frozen=True)
                    class SamplePlan:
                        external_inputs: tuple[str, ...] = ()
                        description: str = ""
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            rows = collect_field_inventory(root)

            self.assertEqual(("external_inputs", "description"), tuple(row.field_name for row in rows))
            self.assertEqual("behavior_or_contract", rows[0].lifecycle_layer)
            self.assertEqual("display_or_metadata", rows[1].lifecycle_layer)
            self.assertEqual("core_or_internal", rows[0].route_owner)
            self.assertEqual("internal", rows[0].ai_surface_tier)


if __name__ == "__main__":
    unittest.main()
