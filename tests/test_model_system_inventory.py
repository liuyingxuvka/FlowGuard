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
    inspect_manifest_model_inventory,
)
from flowguard.behavior_commitment import (
    BehaviorCommitment,
    BehaviorCommitmentLedger,
    BehaviorEvidenceBinding,
    BehaviorSourceSurface,
    write_behavior_commitment_ledger,
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
        inventory = inspect_manifest_model_inventory(root)
        self.assertEqual(62, len(inventory.declared_ids))
        self.assertEqual(inventory.declared_ids, inventory.materialized_ids)
        self.assertEqual(inventory.required_ids, inventory.covered_ids)
        self.assertFalse(inventory.missing_ids)
        self.assertEqual(62, len(snapshot.model_instances))
        model_dimension = next(
            item
            for item in snapshot.coverage.dimensions
            if item.dimension_id == "model_instances"
        )
        self.assertEqual(inventory.required_ids, model_dimension.required_ids)
        self.assertEqual(inventory.covered_ids, model_dimension.covered_ids)
        self.assertFalse(model_dimension.excluded_ids)
        self.assertEqual("flowguard.model_system_snapshot.v2", snapshot.schema)
        self.assertTrue(
            all(
                model.schema == "flowguard.model_instance_ref.v2"
                and "subject_revision" not in model.to_dict()
                for model in snapshot.model_instances
            )
        )

    def test_optional_local_absence_remains_declared_and_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_dir = root / ".flowguard"
            manifest_dir.mkdir()
            (manifest_dir / "model-regression-manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": MANIFEST_SCHEMA,
                        "governed_input_globs": [],
                        "snapshot_only_input_globs": [],
                        "shared_input_groups": [],
                        "models": [
                            {
                                "model_id": "missing_local",
                                "model_path": ".flowguard/missing/model.py",
                                "runner": [
                                    "{python}",
                                    ".flowguard/missing/run_checks.py",
                                ],
                                "tier": "fast",
                                "timeout_seconds": 5,
                                "shard_safe": True,
                                "mutation_policy": "none",
                                "input_globs": [],
                                "expected_artifacts": [],
                                "exclusion_reason": "",
                                "distribution_policy": "optional_local",
                                "absence_reason": (
                                    "The local fixture is intentionally absent."
                                ),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            inventory = inspect_manifest_model_inventory(root)

            self.assertEqual(("missing_local",), inventory.declared_ids)
            self.assertEqual((), inventory.materialized_ids)
            self.assertEqual(("missing_local",), inventory.required_ids)
            self.assertEqual((), inventory.covered_ids)
            self.assertEqual(("missing_local",), inventory.missing_ids)
            self.assertFalse(inventory.complete)

    def test_local_model_identity_changes_only_for_its_resolved_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_paths = {}
            runner_paths = {}
            for model_id in ("alpha", "beta"):
                model_dir = root / ".flowguard" / model_id
                model_dir.mkdir(parents=True)
                model_paths[model_id] = model_dir / "model.py"
                runner_paths[model_id] = model_dir / "run_checks.py"
                model_paths[model_id].write_text(
                    f"VALUE = {model_id!r}\n",
                    encoding="utf-8",
                )
                runner_paths[model_id].write_text(
                    "print('ok')\n",
                    encoding="utf-8",
                )

            def write_manifest() -> None:
                models = []
                for model_id in ("alpha", "beta"):
                    purpose = build_model_purpose_closure(
                        model_instance_id=f"regression:{model_id}:fixture",
                        reusable_model_type_id=model_id,
                        task_intent_id=f"flowguard-regression:{model_id}",
                        guarded_purpose=(
                            f"Prevent the {model_id} fixture from accepting "
                            "an incorrect local model identity."
                        ),
                        protected_failure_ids=(f"{model_id}:incorrect",),
                        known_good_case_id=f"native:{model_id}:complete",
                        failure_bindings=(
                            {
                                "failure_id": f"{model_id}:incorrect",
                                "known_bad_case_id": (
                                    f"native:{model_id}:incorrect"
                                ),
                                "oracle_id": f"native:{model_id}:run-checks",
                            },
                        ),
                        claim_boundary=(
                            "This fixture proves only local model input "
                            "identity isolation inside a temporary project."
                        ),
                        evidence_check_ids=(f"check:{model_id}",),
                        model_sha256=file_fingerprint(model_paths[model_id]),
                        runner_sha256=file_fingerprint(runner_paths[model_id]),
                    )
                    models.append(
                        {
                            "model_id": model_id,
                            "model_path": (
                                f".flowguard/{model_id}/model.py"
                            ),
                            "runner": [
                                "{python}",
                                f".flowguard/{model_id}/run_checks.py",
                            ],
                            "tier": "fast",
                            "timeout_seconds": 5,
                            "shard_safe": True,
                            "mutation_policy": "none",
                            "input_globs": [
                                f".flowguard/{model_id}/model.py",
                                f".flowguard/{model_id}/run_checks.py",
                            ],
                            "expected_artifacts": [],
                            "exclusion_reason": "",
                            "purpose_closure": purpose.to_dict(),
                        }
                    )
                (
                    root / ".flowguard" / "model-regression-manifest.json"
                ).write_text(
                    json.dumps(
                        {
                            "schema_version": MANIFEST_SCHEMA,
                            "governed_input_globs": [".flowguard/**/*.py"],
                            "snapshot_only_input_globs": [],
                            "shared_input_groups": [],
                            "models": models,
                        }
                    ),
                    encoding="utf-8",
                )

            write_manifest()
            before = build_manifest_model_system_snapshot(
                root,
                snapshot_id="snapshot:local-identity",
            )
            before_by_id = {
                item.logical_model_id: item for item in before.model_instances
            }

            model_paths["alpha"].write_text(
                "VALUE = 'alpha-changed'\n",
                encoding="utf-8",
            )
            write_manifest()
            after = build_manifest_model_system_snapshot(
                root,
                snapshot_id="snapshot:local-identity",
            )
            after_by_id = {
                item.logical_model_id: item for item in after.model_instances
            }

            self.assertNotEqual(
                before_by_id["alpha"].fingerprint,
                after_by_id["alpha"].fingerprint,
            )
            self.assertEqual(
                before_by_id["beta"].fingerprint,
                after_by_id["beta"].fingerprint,
            )
            self.assertNotEqual(before.subject_revision, after.subject_revision)
            self.assertNotEqual(before.fingerprint, after.fingerprint)

            runner_paths["beta"].unlink()
            incomplete = build_manifest_model_system_snapshot(
                root,
                snapshot_id="snapshot:required-runner-missing",
            )
            model_dimension = next(
                item
                for item in incomplete.coverage.dimensions
                if item.dimension_id == "model_instances"
            )
            self.assertEqual(("alpha", "beta"), model_dimension.required_ids)
            self.assertEqual(("alpha",), model_dimension.covered_ids)
            self.assertEqual(("beta",), model_dimension.missing_ids)
            self.assertEqual(
                "incomplete_within_declared_boundary",
                incomplete.coverage_status,
            )

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
                "governed_input_globs": [".flowguard/**/*.py"],
                "snapshot_only_input_globs": [],
                "shared_input_groups": [],
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
            write_behavior_commitment_ledger(
                ledger_dir / "ledger.json",
                BehaviorCommitmentLedger(
                    "ledger:owner",
                    project_boundary="temporary owner fixture",
                    current_revision="git:" + "a" * 40,
                    subject_lane="observed_implementation",
                    expected_source_surface_ids=("surface:owner",),
                    source_inventory_revision="inventory:owner",
                    source_inventory_fingerprint="sha256:" + "1" * 64,
                    source_inventory_evidence_ids=("discovery:owner",),
                    require_complete_source_inventory=True,
                    expected_commitment_ids=("commitment:owner",),
                    expected_business_intent_ids=("intent:owner",),
                    source_surfaces=(
                        BehaviorSourceSurface(
                            "surface:owner",
                            source_system_id="fixture",
                            native_artifact_id="owner",
                            content_fingerprint="sha256:" + "2" * 64,
                            inventory_revision="inventory:owner",
                            discovery_evidence_ids=("discovery:owner",),
                            source_authority_role="observed",
                            declared_semantics_fingerprint="sha256:" + "3" * 64,
                            coverage_disposition="modeled",
                            commitment_ids=("commitment:owner",),
                            business_intent_ids=("intent:owner",),
                            freshness_state="current",
                        ),
                    ),
                    commitments=(
                        BehaviorCommitment(
                            "commitment:owner",
                            business_intent_id="intent:owner",
                            source_surface_ids=("surface:owner",),
                            primary_owner_model_id=".flowguard/owner/model.py",
                            state_writes=("state:owner",),
                            evidence=BehaviorEvidenceBinding(
                                code_contract_ids=("contract:owner",),
                                test_evidence_ids=("test:owner",),
                            ),
                        ),
                    ),
                ),
            )

            snapshot = build_manifest_model_system_snapshot(
                root,
                snapshot_id="snapshot:owner",
                subject_revision="git:" + "a" * 40,
            )
            changed_global_revision = build_manifest_model_system_snapshot(
                root,
                snapshot_id="snapshot:owner",
                subject_revision="source-inventory:" + "b" * 64,
            )

            self.assertEqual(1, len(snapshot.model_instances))
            self.assertEqual(
                snapshot.model_instances[0].fingerprint,
                changed_global_revision.model_instances[0].fingerprint,
            )
            self.assertNotEqual(
                snapshot.fingerprint,
                changed_global_revision.fingerprint,
            )
            self.assertNotIn(
                "subject_revision",
                snapshot.model_instances[0].to_dict(),
            )
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
