import contextlib
import io
import tempfile
import textwrap
import unittest
from pathlib import Path

from scripts.run_flowguard_model_regressions import main as run_model_regressions
from scripts.generate_field_lifecycle_inventory import (
    collect_field_inventory,
    infer_ai_surface_tier,
    infer_lifecycle_layer,
    infer_route_owner,
)


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
