import json
import tempfile
import unittest
from pathlib import Path

from flowguard.model_purpose import (
    build_model_purpose_closure,
    file_fingerprint,
)
from flowguard.model_regressions import MANIFEST_SCHEMA
from flowguard.model_system_inventory import (
    build_manifest_model_system_snapshot,
)


class ModelSystemInventoryTests(unittest.TestCase):
    def test_repository_snapshot_has_no_owner_coverage_gaps(self):
        root = Path(__file__).resolve().parents[1]
        snapshot = build_manifest_model_system_snapshot(
            root,
            snapshot_id="snapshot:repository-test",
        )

        self.assertEqual(
            "complete_within_declared_boundary",
            snapshot.coverage_status,
        )
        self.assertFalse(snapshot.unresolved_gap_ids)
        self.assertTrue(snapshot.coverage.complete)
        self.assertTrue(snapshot.model_instances)

    def test_manifest_snapshot_connects_model_purpose_and_commitment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_dir = root / ".flowguard" / "owner"
            model_dir.mkdir(parents=True)
            model_path = model_dir / "model.py"
            runner_path = model_dir / "run_checks.py"
            model_path.write_text("VALUE = 1\n", encoding="utf-8")
            runner_path.write_text("print('ok')\n", encoding="utf-8")
            purpose = build_model_purpose_closure(
                model_instance_id="regression:owner:fixture",
                reusable_model_type_id="owner",
                task_intent_id="flowguard-regression:owner",
                guarded_purpose=(
                    "Prevent the owner fixture from accepting incomplete "
                    "project-model authority."
                ),
                protected_failure_ids=("owner:incomplete",),
                known_good_case_id="native:owner:complete",
                failure_bindings=(
                    {
                        "failure_id": "owner:incomplete",
                        "known_bad_case_id": "native:owner:incomplete",
                        "oracle_id": "native:owner:run-checks",
                    },
                ),
                claim_boundary=(
                    "This fixture proves only manifest-to-purpose and "
                    "commitment relation assembly inside a temporary project."
                ),
                evidence_check_ids=("check:owner",),
                model_sha256=file_fingerprint(model_path),
                runner_sha256=file_fingerprint(runner_path),
            )
            manifest = {
                "schema_version": MANIFEST_SCHEMA,
                "models": [
                    {
                        "model_id": "owner",
                        "model_path": ".flowguard/owner/model.py",
                        "runner": [
                            "{python}",
                            ".flowguard/owner/run_checks.py",
                        ],
                        "tier": "fast",
                        "timeout_seconds": 5,
                        "shard_safe": True,
                        "mutation_policy": "none",
                        "input_globs": [
                            ".flowguard/owner/model.py",
                            ".flowguard/owner/run_checks.py",
                        ],
                        "expected_artifacts": [],
                        "exclusion_reason": "",
                        "purpose_closure": purpose.to_dict(),
                    }
                ],
            }
            (root / ".flowguard" / "model-regression-manifest.json").write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
            ledger_dir = root / ".flowguard" / "behavior_commitment_ledger"
            ledger_dir.mkdir()
            (ledger_dir / "ledger.json").write_text(
                json.dumps(
                    {
                        "ledger": {
                            "commitments": [
                                {
                                    "commitment_id": "commitment:owner",
                                    "primary_owner_model_id": (
                                        ".flowguard/owner/model.py"
                                    ),
                                    "source_surface_ids": ("surface:owner",),
                                    "state_writes": ("state:owner",),
                                    "side_effects": (),
                                    "evidence": {
                                        "code_contract_ids": (
                                            "contract:owner",
                                        ),
                                        "test_evidence_ids": ("test:owner",),
                                    },
                                }
                            ],
                            "source_surfaces": [
                                {"surface_id": "surface:owner"}
                            ],
                        }
                    }
                ),
                encoding="utf-8",
            )

            snapshot = build_manifest_model_system_snapshot(
                root,
                snapshot_id="snapshot:owner",
                subject_revision="git:" + "a" * 40,
            )

            self.assertEqual(1, len(snapshot.model_instances))
            self.assertEqual(7, len(snapshot.relations))
            self.assertEqual(
                {
                    "behavior_commitment",
                    "code_contract",
                    "external_surface",
                    "field_inventory",
                    "model_instance",
                    "parent_closure",
                    "test_evidence",
                },
                {
                    endpoint.endpoint_kind
                    for relation in snapshot.relations
                    for endpoint in (relation.source, relation.target)
                },
            )
            self.assertEqual(
                {"contains", "produces_for", "realizes", "validates"},
                {relation.kind for relation in snapshot.relations},
            )
            self.assertEqual(
                "complete_within_declared_boundary",
                snapshot.coverage_status,
            )
            self.assertFalse(snapshot.unresolved_gap_ids)


if __name__ == "__main__":
    unittest.main()
