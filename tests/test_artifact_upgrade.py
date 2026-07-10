import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import flowguard
from flowguard.artifact_upgrade import (
    ARTIFACT_UPGRADE_STATUS_BLOCKED,
    ARTIFACT_UPGRADE_STATUS_UNCHANGED,
    ARTIFACT_UPGRADE_STATUS_UPGRADED,
    review_artifact_upgrades,
)


ROOT = Path(__file__).resolve().parents[1]


class ArtifactUpgradeTests(unittest.TestCase):
    def test_json_artifact_dry_run_reports_upgrade_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / ".flowguard" / "old_report.json"
            artifact.parent.mkdir()
            artifact.write_text(
                json.dumps(
                    {
                        "schema_version": "0.9",
                        "artifact_type": "flowguard_test_report",
                        "created_by": "flowguard",
                        "payload": {"ok": True},
                    }
                ),
                encoding="utf-8",
            )

            report = review_artifact_upgrades(root)

            self.assertTrue(report.ok, report.format_text())
            self.assertEqual(1, report.upgraded_count)
            self.assertEqual((), report.changed_files)
            self.assertEqual("0.9", json.loads(artifact.read_text(encoding="utf-8"))["schema_version"])

    def test_json_artifact_apply_writes_current_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / ".flowguard" / "old_report.json"
            artifact.parent.mkdir()
            artifact.write_text(
                json.dumps(
                    {
                        "schema_version": "0.8",
                        "artifact_type": "flowguard_test_report",
                        "payload": {"ok": True},
                    }
                ),
                encoding="utf-8",
            )

            report = review_artifact_upgrades(root, apply=True)

            self.assertTrue(report.ok, report.format_text())
            self.assertEqual((artifact.relative_to(root).as_posix(),), report.changed_files)
            self.assertEqual(flowguard.SCHEMA_VERSION, json.loads(artifact.read_text(encoding="utf-8"))["schema_version"])

    def test_namespaced_flowguard_and_skillguard_schemas_are_never_rewritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            flowguard_receipt = root / ".flowguard" / "receipt.json"
            skillguard_contract = root / ".agents" / "skills" / "sample" / ".skillguard" / "work-contract.json"
            flowguard_receipt.parent.mkdir(parents=True)
            skillguard_contract.parent.mkdir(parents=True)
            flowguard_receipt.write_text(
                json.dumps(
                    {
                        "schema_version": "flowguard.evidence_receipt.v1",
                        "artifact_type": "flowguard_evidence_receipt",
                        "status": "pass",
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            skillguard_contract.write_text(
                json.dumps(
                    {
                        "schema_version": "skillguard.work_contract.v1",
                        "target_type": "skill",
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            before = (flowguard_receipt.read_bytes(), skillguard_contract.read_bytes())

            report = review_artifact_upgrades(root, apply=True)

            self.assertTrue(report.ok, report.format_text())
            self.assertEqual((), report.changed_files)
            self.assertEqual(before, (flowguard_receipt.read_bytes(), skillguard_contract.read_bytes()))
            receipt_item = next(item for item in report.items if item.path.endswith("receipt.json"))
            self.assertEqual(ARTIFACT_UPGRADE_STATUS_UNCHANGED, receipt_item.status)
            self.assertEqual("namespaced_json_artifact", receipt_item.item_kind)

    def test_scan_ignores_project_tmp_not_system_tmp_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / ".flowguard" / "old_report.json"
            artifact.parent.mkdir()
            artifact.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_type": "flowguard_test_report",
                        "payload": {"ok": True},
                    }
                ),
                encoding="utf-8",
            )
            ignored = root / "tmp" / "old_report.json"
            ignored.parent.mkdir()
            ignored.write_text(artifact.read_text(encoding="utf-8"), encoding="utf-8")

            report = review_artifact_upgrades(root)

            self.assertTrue(report.ok, report.format_text())
            self.assertEqual(1, report.upgraded_count)
            self.assertEqual((".flowguard/old_report.json",), tuple(item.path for item in report.items))

    def test_known_alias_is_replaced_but_unknown_script_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            test_file = root / "tests" / "test_old.py"
            test_file.parent.mkdir()
            old_alias = "PlanIntake" + "Surface"
            test_file.write_text(
                f"from flowguard import {old_alias}\nvalue = {old_alias}\n",
                encoding="utf-8",
            )
            unknown = root / "examples" / "old_model.py"
            unknown.parent.mkdir()
            marker = "legacy_" + "flowguard_runtime_path"
            unknown.write_text(f"{marker} = True\n", encoding="utf-8")

            report = review_artifact_upgrades(root, apply=True)

            statuses = {item.path: item.status for item in report.items}
            self.assertEqual(ARTIFACT_UPGRADE_STATUS_UPGRADED, statuses["tests/test_old.py"])
            self.assertEqual(ARTIFACT_UPGRADE_STATUS_BLOCKED, statuses["examples/old_model.py"])
            self.assertFalse(report.ok)
            self.assertIn("PlanIntakeRiskSurface", test_file.read_text(encoding="utf-8"))

    def test_cli_reports_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / ".flowguard" / "old_report.json"
            artifact.parent.mkdir()
            artifact.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_type": "flowguard_test_report",
                        "payload": {},
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, "-m", "flowguard", "artifact-upgrade", "--root", directory, "--json"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("flowguard_artifact_upgrade_report", payload["artifact_type"])
            self.assertEqual(1, payload["upgraded_count"])


if __name__ == "__main__":
    unittest.main()
