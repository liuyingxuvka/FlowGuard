import hashlib
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
    review_artifact_upgrades,
)


ROOT = Path(__file__).resolve().parents[1]


class ArtifactUpgradeTests(unittest.TestCase):
    def legacy_report(self, schema_version="0.1", artifact_type="report"):
        return {
            "schema_version": schema_version,
            "artifact_type": artifact_type,
            "created_by": "flowguard",
            "model_name": "legacy-model",
            "scenario_name": "legacy-scenario",
            "trace_id": "",
            "payload": {"ok": True},
        }

    def legacy_evidence(self):
        return {
            "model_obligation_ids": [],
            "code_contract_ids": [],
            "test_evidence_ids": [],
            "proof_artifact_ids": [],
            "risk_gate_ids": [],
            "coverage_case_ids": [],
            "coverage_shard_ids": [],
            "coverage_receipt_ids": [],
            "evidence_state": "missing",
            "test_mesh_state": "shard_current",
            "current": False,
            "metadata": {},
        }

    def legacy_path_authority(self):
        return {
            "path_sensitive": False,
            "business_intent": "",
            "ppa_report_id": "",
            "ppa_decision": "",
            "ppa_confidence": "",
            "ppa_ok": None,
            "primary_path_ids": [],
            "fallback_candidate_ids": [],
            "ppa_coverage_receipt_ids": [],
            "ppa_coverage_shard_ids": [],
            "ppa_risk_gate_ids": [],
            "scoped_out_reason": "",
            "evidence_refs": [],
            "metadata": {},
        }

    def legacy_commitment(
        self,
        commitment_id,
        *,
        commitment_kind,
        actor,
        primary_owner_model_id,
        dependency_commitment_ids=(),
        migration_behavior_plane=None,
        migration_actor_kind=None,
    ):
        metadata = {}
        if migration_behavior_plane is not None:
            metadata["migration_behavior_plane"] = migration_behavior_plane
        if migration_actor_kind is not None:
            metadata["migration_actor_kind"] = migration_actor_kind
        return {
            "commitment_id": commitment_id,
            "label": commitment_id,
            "commitment_kind": commitment_kind,
            "actor": actor,
            "trigger": "",
            "expected_result": "",
            "failure_boundary": "",
            "source_surface_ids": [],
            "source_refs": [],
            "primary_owner_model_id": primary_owner_model_id,
            "supporting_model_ids": [],
            "child_model_ids": [],
            "dependency_commitment_ids": list(dependency_commitment_ids),
            "excluded_behavior_ids": [],
            "replacement_state": "active",
            "model_sync_state": "owner_model_current",
            "miss_origin_state": "no_miss",
            "path_authority": self.legacy_path_authority(),
            "evidence": self.legacy_evidence(),
            "in_scope": True,
            "scoped_out_reason": "",
            "owner": "",
            "validation_boundary": "",
            "rationale": "",
            "metadata": metadata,
        }

    def legacy_behavior_ledger(self):
        return {
            "ledger_id": "ledger:legacy",
            "project_boundary": "legacy behavior ledger",
            "current_revision": "old-revision",
            "commitments": [
                self.legacy_commitment(
                    "commitment:download-page",
                    commitment_kind="ui",
                    actor="user",
                    primary_owner_model_id="model:download-page",
                    dependency_commitment_ids=("commitment:download-api",),
                    migration_behavior_plane="product_runtime",
                    migration_actor_kind="end_user",
                ),
                self.legacy_commitment(
                    "commitment:download-api",
                    commitment_kind="public_api",
                    actor="external client",
                    primary_owner_model_id="model:download-api",
                    migration_behavior_plane="product_runtime",
                    migration_actor_kind="external_system",
                ),
            ],
            "source_surfaces": [
                {
                    "surface_id": "surface:download",
                    "surface_kind": "ui",
                    "label": "download surface",
                    "source_ref": "legacy/download.py",
                    "commitment_ids": [
                        "commitment:download-page",
                        "commitment:download-api",
                    ],
                    "freshness_state": "current",
                    "in_scope": True,
                    "scoped_out_reason": "",
                    "owner": "",
                    "validation_boundary": "",
                    "rationale": "",
                    "metadata": {},
                }
            ],
            "expected_commitment_ids": [
                "commitment:download-page",
                "commitment:download-api",
            ],
            "claim_scope": "routine",
            "change_mode": "bootstrap_ledger",
            "require_current_evidence": False,
            "require_risk_gates_for_broad_claim": True,
            "owner": "",
            "validation_boundary": "",
            "rationale": "",
            "metadata": {},
        }

    def test_embedded_python_behavior_inventory_is_rejected_not_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = (
                root
                / ".flowguard"
                / "models"
                / "owners"
                / "behavior_commitment_ledger"
                / "model.py"
            )
            model.parent.mkdir(parents=True)
            model.write_text(
                "def build():\n    return BehaviorCommitmentLedger(commitments=(BehaviorCommitment('x'),))\n",
                encoding="utf-8",
            )
            before = model.read_bytes()

            report = review_artifact_upgrades(root, paths=(model,))

            self.assertFalse(report.ok)
            self.assertEqual(ARTIFACT_UPGRADE_STATUS_BLOCKED, report.items[0].status)
            self.assertEqual(before, model.read_bytes())
            self.assertIn("not executed", report.items[0].message)

    def test_current_registered_envelope_is_unchanged_without_reserialization(self):
        for artifact_type in ("report", "trace"):
            with self.subTest(artifact_type=artifact_type), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                artifact = root / ".flowguard" / f"old_{artifact_type}.json"
                artifact.parent.mkdir()
                artifact.write_text(
                    json.dumps(
                        self.legacy_report(flowguard.SCHEMA_VERSION, artifact_type),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    encoding="utf-8",
                )
                before = artifact.read_bytes()

                report = review_artifact_upgrades(root)

                self.assertTrue(report.ok, report.format_text())
                self.assertEqual(0, report.upgraded_count)
                self.assertEqual((), report.changed_files)
                self.assertEqual(before, artifact.read_bytes())
                self.assertEqual(ARTIFACT_UPGRADE_STATUS_UNCHANGED, report.items[0].status)

    def test_registered_envelope_unknown_version_blocks_without_writing(self):
        for artifact_type in ("report", "trace"):
            with self.subTest(artifact_type=artifact_type), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                artifact = root / ".flowguard" / f"old_{artifact_type}.json"
                artifact.parent.mkdir()
                artifact.write_text(
                    json.dumps(self.legacy_report("0.8", artifact_type)),
                    encoding="utf-8",
                )
                before = artifact.read_bytes()

                report = review_artifact_upgrades(root)

                self.assertFalse(report.ok)
                self.assertEqual(ARTIFACT_UPGRADE_STATUS_BLOCKED, report.items[0].status)
                self.assertEqual((), report.changed_files)
                self.assertEqual(before, artifact.read_bytes())

    def test_unregistered_namespaced_flowguard_and_skillguard_schemas_are_never_rewritten(self):
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

            report = review_artifact_upgrades(root)

            self.assertTrue(report.ok, report.format_text())
            self.assertEqual((), report.changed_files)
            self.assertEqual(before, (flowguard_receipt.read_bytes(), skillguard_contract.read_bytes()))
            self.assertEqual(0, report.scanned_count)

    def test_unregistered_target_json_never_gains_ownership_from_shared_markers(self):
        legacy_top_extra = self.legacy_behavior_ledger()
        legacy_top_extra["target_schema"] = "target.v1"
        legacy_row_extra = self.legacy_behavior_ledger()
        legacy_row_extra["commitments"][0]["target_only_field"] = True
        legacy_surface_extra = self.legacy_behavior_ledger()
        legacy_surface_extra["source_surfaces"][0]["target_only_field"] = True
        legacy_evidence_extra = self.legacy_behavior_ledger()
        legacy_evidence_extra["commitments"][0]["evidence"]["target_only_field"] = True
        legacy_path_extra = self.legacy_behavior_ledger()
        legacy_path_extra["commitments"][0]["path_authority"][
            "target_only_field"
        ] = True
        cases = (
            (
                "integer-schema.json",
                {
                    "schema_version": 1,
                    "cases": [{"query": "target-owned"}],
                },
            ),
            (
                "numeric-string-envelope.json",
                {
                    "schema_version": "1",
                    "payload": {"target": True},
                },
            ),
            (
                "producer-label.json",
                {
                    "schema_version": "0.1",
                    "created_by": "flowguard",
                    "payload": {"target": True},
                },
            ),
            (
                "flowguard-looking-type.json",
                {
                    "schema_version": "0.1",
                    "artifact_type": "flowguard_target_owned_fixture",
                    "payload": {"target": True},
                },
            ),
            (
                "partial-ledger-shape.json",
                {
                    "ledger_id": "ledger:target",
                    "project_boundary": "target-owned",
                    "current_revision": "target-revision",
                    "commitments": [],
                    "expected_commitment_ids": [],
                },
            ),
            ("legacy-ledger-top-extra.json", legacy_top_extra),
            ("legacy-ledger-row-extra.json", legacy_row_extra),
            ("legacy-ledger-surface-extra.json", legacy_surface_extra),
            ("legacy-ledger-evidence-extra.json", legacy_evidence_extra),
            ("legacy-ledger-path-extra.json", legacy_path_extra),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture_root = root / "tests" / "fixtures"
            fixture_root.mkdir(parents=True)
            before: dict[str, tuple[bytes, str]] = {}
            for name, payload in cases:
                path = fixture_root / name
                path.write_text(
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8",
                )
                raw = path.read_bytes()
                before[name] = (raw, hashlib.sha256(raw).hexdigest())

            report = review_artifact_upgrades(root)

            self.assertTrue(report.ok, report.format_text())
            self.assertEqual(0, report.scanned_count)
            self.assertEqual((), report.changed_files)
            for name, (expected_bytes, expected_hash) in before.items():
                with self.subTest(name=name):
                    actual = (fixture_root / name).read_bytes()
                    self.assertEqual(expected_bytes, actual)
                    self.assertEqual(expected_hash, hashlib.sha256(actual).hexdigest())

    def test_registered_envelope_shape_and_version_fail_closed_without_writing(self):
        current = self.legacy_report(flowguard.SCHEMA_VERSION)
        cases = {
            "missing-field": {
                key: value for key, value in current.items() if key != "trace_id"
            },
            "extra-field": {**current, "target_extra": True},
            "wrong-version-type": {**current, "schema_version": 1},
            "future-version": {**current, "schema_version": "999.0"},
            "unsupported-old-version": {**current, "schema_version": "0.9"},
            "namespaced-version": {
                **current,
                "schema_version": "flowguard.report.v1",
            },
        }
        for name, payload in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                artifact = root / "tests" / f"{name}.json"
                artifact.parent.mkdir(parents=True)
                artifact.write_text(
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8",
                )
                before = artifact.read_bytes()

                report = review_artifact_upgrades(root, paths=(artifact,))

                self.assertFalse(report.ok)
                self.assertEqual(ARTIFACT_UPGRADE_STATUS_BLOCKED, report.items[0].status)
                self.assertEqual((), report.changed_files)
                self.assertEqual(before, artifact.read_bytes())

    def test_unknown_or_future_bcl_envelope_blocks_without_writing(self):
        current = {
            "artifact_type": "flowguard_behavior_commitment_ledger",
            "schema_version": flowguard.SCHEMA_VERSION,
            "format_version": "999",
            "ledger": {},
        }
        cases = {
            "future-schema": {**current, "schema_version": "999.0"},
            "future-format": {**current, "format_version": "999"},
            "extra-envelope-field": {**current, "target_extra": True},
        }
        for name, payload in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                artifact = root / ".flowguard" / f"{name}.json"
                artifact.parent.mkdir(parents=True)
                artifact.write_text(
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8",
                )
                before = artifact.read_bytes()

                report = review_artifact_upgrades(root, paths=(artifact,))

                self.assertFalse(report.ok)
                self.assertEqual(ARTIFACT_UPGRADE_STATUS_BLOCKED, report.items[0].status)
                self.assertEqual((), report.changed_files)
                self.assertEqual(before, artifact.read_bytes())

    def test_scan_ignores_project_tmp_not_system_tmp_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = (
                root
                / ".flowguard"
                / "behavior"
                / "inventory"
                / "ledger.json"
            )
            artifact.parent.mkdir(parents=True)
            ignored = root / "tmp" / "old_report.json"
            ignored.parent.mkdir()
            artifact.write_text(
                json.dumps(self.legacy_behavior_ledger()),
                encoding="utf-8",
            )
            ignored.write_text(
                json.dumps(self.legacy_behavior_ledger()),
                encoding="utf-8",
            )

            report = review_artifact_upgrades(root)

            self.assertFalse(report.ok, report.format_text())
            self.assertEqual(0, report.upgraded_count)
            self.assertEqual(1, report.blocked_count)
            self.assertEqual(
                (".flowguard/behavior/inventory/ledger.json",),
                tuple(item.path for item in report.items),
            )

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

            report = review_artifact_upgrades(root)

            statuses = {item.path: item.status for item in report.items}
            self.assertEqual(ARTIFACT_UPGRADE_STATUS_BLOCKED, statuses["tests/test_old.py"])
            self.assertEqual(ARTIFACT_UPGRADE_STATUS_BLOCKED, statuses["examples/old_model.py"])
            self.assertFalse(report.ok)
            self.assertEqual(
                f"from flowguard import {old_alias}\nvalue = {old_alias}\n",
                test_file.read_text(encoding="utf-8"),
            )

    def test_retired_artifact_upgrade_cli_route_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = (
                root
                / ".flowguard"
                / "behavior_commitment_ledger"
                / "ledger.json"
            )
            artifact.parent.mkdir(parents=True)
            artifact.write_text(
                json.dumps(self.legacy_behavior_ledger()),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, "-m", "flowguard", "artifact-upgrade", "--root", directory, "--json"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(2, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("flowguard_compact_operation", payload["artifact_type"])
            self.assertEqual("blocked", payload["status"])
            self.assertEqual("block", payload["decision"])
            self.assertEqual(0, payload["producer_count"])
            self.assertEqual("unknown operation: artifact-upgrade", payload["error"])
            self.assertEqual(["read", "change", "release"], payload["allowed_operations"])


if __name__ == "__main__":
    unittest.main()
