import contextlib
import io
import json
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

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

<<<<<<< HEAD
=======
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

    def test_default_shadow_sync_excludes_runtime_evidence_but_keeps_model_authority(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
            source = Path(source_dir)
            target = Path(target_dir)
            evidence = source / ".flowguard" / "evidence" / "run-1" / "receipt.json"
            evidence.parent.mkdir(parents=True)
            evidence.write_text('{"status":"pass"}\n', encoding="utf-8")
            snapshot = source / ".flowguard" / "model-mesh" / "snapshots" / "current.json"
            snapshot.parent.mkdir(parents=True)
            snapshot.write_text('{"snapshot":"current"}\n', encoding="utf-8")

            result = sync_workspace(source, target)

            self.assertNotIn(
                ".flowguard/evidence/run-1/receipt.json",
                result.copied_files,
            )
            self.assertFalse(
                (target / ".flowguard" / "evidence" / "run-1" / "receipt.json").exists()
            )
            self.assertIn(
                ".flowguard/model-mesh/snapshots/current.json",
                result.copied_files,
            )
            self.assertEqual(
                snapshot.read_bytes(),
                (
                    target
                    / ".flowguard"
                    / "model-mesh"
                    / "snapshots"
                    / "current.json"
                ).read_bytes(),
            )

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

            with patch(
                "scripts.sync_shadow_workspace.verify_shadow_skill_projection",
                return_value={"ok": True},
            ):
                report = verify_workspace(
                    target,
                    expected_version=metadata.version("flowguard"),
                )

            self.assertTrue(report["ok"], report)
            self.assertIn(str(package), report["source_path"])
            self.assertTrue(report["helper_available"])

    def _shadow_authority_fixture(self, root: Path):
        member_ids = ("flowguard",) + tuple(
            f"flowguard-route-{index}" for index in range(1, 15)
        )
        files = []
        for member_id in member_ids:
            skill = root / ".agents" / "skills" / member_id / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(f"# {member_id}\n", encoding="utf-8")
            files.append(
                FileFingerprint.from_path(
                    skill,
                    f"{member_id}/SKILL.md",
                )
            )
        authority = ConsumerSuiteAuthority(
            source="<package-authority>",
            flowguard_version="9.9.9",
            member_ids=member_ids,
            files=tuple(files),
            raw_tree_hash="A" * 64,
            semantic_tree_hash="B" * 64,
            authority_hash="sha256:" + "c" * 64,
        )
        candidate = authority.to_dict()
        return authority, candidate

    def test_shadow_authority_exact_parity_and_unrelated_visibility(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authority, candidate = self._shadow_authority_fixture(root)
            unrelated = root / ".agents" / "skills" / "unrelated-skill"
            unrelated.mkdir()
            with (
                patch(
                    "scripts.sync_shadow_workspace.load_consumer_suite_authority",
                    return_value=authority,
                ),
                patch(
                    "scripts.sync_shadow_workspace.build_consumer_suite_authority_bytes",
                    return_value=json.dumps(candidate).encode("utf-8"),
                ),
            ):
                report = verify_shadow_skill_projection(root)

            self.assertTrue(report["ok"], report)
            self.assertEqual(
                ["unrelated-skill"],
                report["unrelated_colocated_members"],
            )

    def test_shadow_authority_blocks_retired_extra_and_missing_member(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authority, candidate = self._shadow_authority_fixture(root)
            (root / ".agents" / "skills" / authority.member_ids[-1]).rename(
                root / "missing-member"
            )
            retired = (
                root
                / ".agents"
                / "skills"
                / "flowguard-plan-detailing-compiler"
            )
            retired.mkdir()
            with (
                patch(
                    "scripts.sync_shadow_workspace.load_consumer_suite_authority",
                    return_value=authority,
                ),
                patch(
                    "scripts.sync_shadow_workspace.build_consumer_suite_authority_bytes",
                    return_value=json.dumps(candidate).encode("utf-8"),
                ),
            ):
                report = verify_shadow_skill_projection(root)

            codes = {item["code"] for item in report["findings"]}
            self.assertFalse(report["ok"])
            self.assertIn("shadow_authority_member_missing", codes)
            self.assertIn("shadow_reserved_flowguard_member_extra", codes)

    def test_shadow_authority_blocks_content_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authority, candidate = self._shadow_authority_fixture(root)
            candidate["files"][0]["raw_hash"] = "D" * 64
            candidate["raw_tree_hash"] = "E" * 64
            candidate["authority_hash"] = "sha256:" + "f" * 64
            with (
                patch(
                    "scripts.sync_shadow_workspace.load_consumer_suite_authority",
                    return_value=authority,
                ),
                patch(
                    "scripts.sync_shadow_workspace.build_consumer_suite_authority_bytes",
                    return_value=json.dumps(candidate).encode("utf-8"),
                ),
            ):
                report = verify_shadow_skill_projection(root)

            codes = {item["code"] for item in report["findings"]}
            self.assertFalse(report["ok"])
            self.assertIn("shadow_authority_content_drift", codes)
            self.assertIn("shadow_authority_raw_tree_hash_mismatch", codes)

>>>>>>> agent/harden-currentness-validation
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
