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
    upgrade_behavior_commitment_ledger_mapping,
)


ROOT = Path(__file__).resolve().parents[1]


class ArtifactUpgradeTests(unittest.TestCase):
    def legacy_behavior_ledger(self):
        return {
            "ledger_id": "ledger:legacy",
            "project_boundary": "legacy behavior ledger",
            "current_revision": "old-revision",
            "commitments": [
                {
                    "commitment_id": "commitment:download-page",
                    "commitment_kind": "ui",
                    "actor": "user",
                    "primary_owner_model_id": "model:download-page",
                    "dependency_commitment_ids": ["commitment:download-api"],
                },
                {
                    "commitment_id": "commitment:download-api",
                    "commitment_kind": "public_api",
                    "actor": "external client",
                    "primary_owner_model_id": "model:download-api",
                    "dependency_commitment_ids": [],
                },
            ],
            "expected_commitment_ids": [
                "commitment:download-page",
                "commitment:download-api",
            ],
        }

    def test_behavior_ledger_mapping_upgrade_converts_same_plane_dependencies(self):
        legacy = self.legacy_behavior_ledger()

        result = upgrade_behavior_commitment_ledger_mapping(legacy)

        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual(ARTIFACT_UPGRADE_STATUS_UPGRADED, result.status)
        self.assertNotIn("artifact_type", legacy)
        self.assertEqual("flowguard_behavior_commitment_ledger", result.mapping["artifact_type"])
        rows = result.mapping["ledger"]["commitments"]
        self.assertNotIn("dependency_commitment_ids", rows[0])
        self.assertEqual("product_runtime", rows[0]["behavior_plane"])
        self.assertEqual("end_user", rows[0]["actor_kind"])
        self.assertEqual(
            {
                "target_commitment_id": "commitment:download-api",
                "relation_type": "depends_on",
            },
            {
                "target_commitment_id": rows[0]["relations"][0]["target_commitment_id"],
                "relation_type": rows[0]["relations"][0]["relation_type"],
            },
        )

    def test_behavior_ledger_dry_run_does_not_write_and_apply_preserves_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / ".flowguard" / "behavior_commitment_ledger" / "ledger.json"
            artifact.parent.mkdir(parents=True)
            artifact.write_text(json.dumps(self.legacy_behavior_ledger()), encoding="utf-8")
            before = artifact.read_bytes()

            dry_run = review_artifact_upgrades(root, paths=(artifact,))

            self.assertTrue(dry_run.ok, dry_run.format_text())
            self.assertEqual(before, artifact.read_bytes())
            self.assertEqual(ARTIFACT_UPGRADE_STATUS_UPGRADED, dry_run.items[0].status)

            applied = review_artifact_upgrades(root, paths=(artifact,), apply=True)

            self.assertTrue(applied.ok, applied.format_text())
            payload = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertEqual("ledger:legacy", payload["ledger"]["ledger_id"])
            self.assertEqual(
                ["commitment:download-page", "commitment:download-api"],
                payload["ledger"]["expected_commitment_ids"],
            )
            current = review_artifact_upgrades(root, paths=(artifact,))
            self.assertEqual(ARTIFACT_UPGRADE_STATUS_UNCHANGED, current.items[0].status)

    def test_ambiguous_legacy_workflow_and_cross_plane_dependency_block_without_writing(self):
        ambiguous = self.legacy_behavior_ledger()
        ambiguous["commitments"].append(
            {
                "commitment_id": "commitment:ambiguous-workflow",
                "commitment_kind": "workflow",
                "actor": "system",
                "dependency_commitment_ids": [],
            }
        )
        result = upgrade_behavior_commitment_ledger_mapping(ambiguous)
        self.assertFalse(result.ok)
        self.assertIn(
            "behavior_ledger_plane_actor_requires_manual_classification",
            {finding.code for finding in result.findings},
        )

        cross_plane = self.legacy_behavior_ledger()
        cross_plane["commitments"][0]["dependency_commitment_ids"] = [
            "commitment:release-check"
        ]
        cross_plane["commitments"].append(
            {
                "commitment_id": "commitment:release-check",
                "commitment_kind": "process",
                "actor": "release automation",
                "dependency_commitment_ids": [],
            }
        )
        result = upgrade_behavior_commitment_ledger_mapping(cross_plane)
        self.assertFalse(result.ok)
        self.assertIn(
            "behavior_ledger_cross_plane_dependency_requires_typed_relation",
            {finding.code for finding in result.findings},
        )

    def test_embedded_python_behavior_inventory_is_rejected_not_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root / ".flowguard" / "behavior_commitment_ledger" / "model.py"
            model.parent.mkdir(parents=True)
            model.write_text(
                "def build():\n    return BehaviorCommitmentLedger(commitments=(BehaviorCommitment('x'),))\n",
                encoding="utf-8",
            )
            before = model.read_bytes()

            report = review_artifact_upgrades(root, paths=(model,), apply=True)

            self.assertFalse(report.ok)
            self.assertEqual(ARTIFACT_UPGRADE_STATUS_BLOCKED, report.items[0].status)
            self.assertEqual(before, model.read_bytes())
            self.assertIn("not executed", report.items[0].message)

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
