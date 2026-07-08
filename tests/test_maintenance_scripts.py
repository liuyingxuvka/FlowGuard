import tempfile
import textwrap
import unittest
from pathlib import Path

import importlib.metadata as metadata

from scripts.run_flowguard_model_regressions import discover_runners, run_regressions
from scripts.generate_field_lifecycle_inventory import (
    collect_field_inventory,
    infer_ai_surface_tier,
    infer_lifecycle_layer,
    infer_route_owner,
)
from scripts.sync_shadow_workspace import sync_workspace, verify_workspace


class MaintenanceScriptTests(unittest.TestCase):
    def test_model_regression_runner_reports_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            passing = root / ".flowguard" / "passing" / "run_checks.py"
            failing = root / ".flowguard" / "failing" / "run_checks.py"
            passing.parent.mkdir(parents=True)
            failing.parent.mkdir(parents=True)
            passing.write_text("print('pass')\n", encoding="utf-8")
            failing.write_text("print('fail')\nraise SystemExit(3)\n", encoding="utf-8")

            runners = discover_runners(root)
            results = run_regressions(root)

            self.assertEqual(2, len(runners))
            self.assertEqual(2, len(results))
            self.assertEqual(1, sum(not result.ok for result in results))
            self.assertEqual(3, [result.exit_code for result in results if not result.ok][0])

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
