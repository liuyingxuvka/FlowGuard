import tempfile
import unittest
from unittest.mock import patch
from dataclasses import replace
from pathlib import Path

from flowguard.model_authority import (
    LIFECYCLE_ACTIVE,
    REVISION_EVIDENCE_PASS,
    REVISION_EVIDENCE_REQUIRED,
    ROLLBACK_RESULT_EXACT,
    SUBJECT_OBSERVED_IMPLEMENTATION,
    AuthorityEndpointRef,
    CoverageDimension,
    CoverageUniverse,
    ModelAuthorityError,
    ModelInputRef,
    ModelInstanceRef,
    ModelRevisionSet,
    ModelRollbackContract,
    ModelRollbackEffect,
    ModelSystemSnapshot,
    RevisionEvidenceRef,
    RevisionMemberChange,
)
from flowguard.model_revision_set import (
    derive_revision_affected_closure,
    derive_revision_snapshot_diff,
)
from flowguard.model_authority_store import (
    activate_model_revision_set,
    audit_model_authority,
    bootstrap_model_authority,
    load_observed_model_system,
    rollback_observed_model_system,
)
from flowguard.existing_model_preflight import (
    existing_model_preflight_from_project,
    review_existing_model_preflight,
)
from flowguard.project_manifest import project_manifest_lock
from flowguard.model_system_inventory import ManifestModelInventory


SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
SHA_D = "sha256:" + "d" * 64


def model(sha: str) -> ModelInstanceRef:
    return ModelInstanceRef(
        logical_model_id="authority",
        model_kind="workflow",
        model_path=".flowguard/authority/model.py",
        model_sha256=sha,
        runner_path=".flowguard/authority/run_checks.py",
        runner_sha256=SHA_D,
        purpose_closure_fingerprint=SHA_C,
        inputs=(
            ModelInputRef(".flowguard/authority/model.py", sha),
            ModelInputRef(".flowguard/authority/run_checks.py", SHA_D),
        ),
    )


def snapshot(revision: str, sha: str, snapshot_id: str) -> ModelSystemSnapshot:
    member = model(sha)
    dimensions = tuple(
        CoverageDimension(
            dimension_id=value,
            required_ids=(f"{value}:one",),
            covered_ids=(f"{value}:one",),
        )
        for value in sorted(
            {
                "external_surfaces",
                "behavior_commitments",
                "model_instances",
                "fields_state_side_effects",
                "code_contracts",
                "tests_evidence",
            }
        )
    )
    return ModelSystemSnapshot(
        snapshot_id=snapshot_id,
        system_id="flowguard",
        subject_lane=SUBJECT_OBSERVED_IMPLEMENTATION,
        lifecycle=LIFECYCLE_ACTIVE,
        subject_revision=revision,
        root_instance_fingerprints=(member.fingerprint,),
        model_instances=(member,),
        relations=(),
        coverage=CoverageUniverse(
            boundary_id="store-test",
            source_inventory_fingerprint=SHA_A,
            dimensions=dimensions,
            claim_boundary=(
                "This finite store test boundary does not claim production "
                "software or unenumerated external behavior."
            ),
        ),
        owner_artifact_refs=(
            AuthorityEndpointRef(
                endpoint_kind="development_process",
                endpoint_id="dpf:authority",
                fingerprint=SHA_B,
                owner_route="development_process_flow",
            ),
        ),
        unresolved_gap_ids=(),
        claim_boundary=(
            "This snapshot exists only for durable store transaction tests and "
            "does not claim production software behavior."
        ),
    )


def revision(head, base, candidate) -> ModelRevisionSet:
    diff = derive_revision_snapshot_diff(base, candidate)
    closure = derive_revision_affected_closure(base, candidate, diff)
    ids_by_owner: dict[str, list[str]] = {}
    for affected_id, owner_route in closure.owner_bindings:
        ids_by_owner.setdefault(owner_route, []).append(affected_id)
    required = tuple(
        RevisionEvidenceRef(
            receipt_id=f"receipt:store:{index}",
            receipt_fingerprint=(
                "sha256:" + f"{index:x}"[-1] * 64
            ),
            owner_route=owner_route,
            subject_fingerprint=candidate.fingerprint,
            obligation_ids=(f"obligation:store:{index}",),
            affected_closure_fingerprint=closure.fingerprint,
            covered_affected_ids=tuple(ids_by_owner[owner_route]),
            candidate_snapshot_fingerprint=candidate.fingerprint,
            toolchain_fingerprint=SHA_C,
            environment_fingerprint=SHA_D,
            status=REVISION_EVIDENCE_REQUIRED,
            current=True,
            eligible=True,
        )
        for index, owner_route in enumerate(sorted(ids_by_owner), 1)
    )
    proposed = ModelRevisionSet(
        revision_set_id="revision:store",
        task_id="task:store",
        expected_head_fingerprint=head.fingerprint,
        base_snapshot_fingerprint=base.fingerprint,
        candidate_snapshot_fingerprint=candidate.fingerprint,
        members=diff.members,
        affected_closure_ids=closure.affected_ids,
        affected_closure_fingerprint=closure.fingerprint,
        affected_edge_ids=closure.edge_ids,
        affected_owner_bindings=closure.owner_bindings,
        snapshot_diff_fingerprint=diff.fingerprint,
        changed_root_ids=diff.changed_root_ids,
        changed_relation_ids=diff.changed_relation_ids,
        changed_source_surface_ids=diff.changed_source_surface_ids,
        changed_commitment_ids=diff.changed_commitment_ids,
        changed_field_ids=diff.changed_field_ids,
        changed_side_effect_ids=diff.changed_side_effect_ids,
        changed_contract_ids=diff.changed_contract_ids,
        changed_test_ids=diff.changed_test_ids,
        changed_system_property_ids=diff.changed_system_property_ids,
        changed_coverage_ids=diff.changed_coverage_ids,
        changed_gap_ids=diff.changed_gap_ids,
        changed_owner_artifact_ids=diff.changed_owner_artifact_ids,
        added_ids=diff.added_ids,
        removed_ids=diff.removed_ids,
        fingerprint_changed_ids=diff.fingerprint_changed_ids,
        no_declared_intent_rationale_id="no-intent:store-fixture",
        no_declared_intent_evidence_fingerprints=(
            ("fixture_scope", candidate.fingerprint),
        ),
        no_declared_intent_rationale=(
            "This isolated durable-store fixture has no external product intent "
            "beyond exercising its declared transaction boundary."
        ),
        required_evidence_refs=required,
    )
    return proposed.accept(
        (
            *(
                replace(
                    item,
                    status=REVISION_EVIDENCE_PASS,
                )
                for item in required
            ),
        ),
        reason="store evidence passed",
    )


def manifest_inventory() -> ManifestModelInventory:
    return ManifestModelInventory(
        declared_ids=("authority",),
        materialized_ids=("authority",),
        required_ids=("authority",),
        covered_ids=("authority",),
        missing_ids=(),
    )


class ModelAuthorityStoreTests(unittest.TestCase):
    def test_bootstrap_and_activation_update_pointer_last(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text(
                '[flowguard]\nadopted_package_version = "0.61.0"\n',
                encoding="utf-8",
            )
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted = revision(head, base, candidate)

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ):
                next_head, receipt = activate_model_revision_set(
                    root,
                    candidate,
                    accepted,
                    receipt_id="activation:store",
                )

            loaded_head, loaded_snapshot = load_observed_model_system(root)
            self.assertEqual(next_head, loaded_head)
            self.assertEqual(candidate, loaded_snapshot)
            self.assertEqual(receipt.fingerprint, loaded_head.activation_receipt_fingerprint)
            self.assertTrue(
                (
                    root
                    / ".flowguard"
                    / "model-mesh"
                    / "revisions"
                    / f"{accepted.fingerprint.split(':')[1]}.json"
                ).is_file()
            )

    def test_stale_candidate_cannot_overwrite_advanced_head(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted = revision(head, base, candidate)
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ):
                activate_model_revision_set(
                    root,
                    candidate,
                    accepted,
                    receipt_id="activation:first",
                )
                with self.assertRaisesRegex(
                    ModelAuthorityError,
                    "mismatch|changed|rebase",
                ):
                    activate_model_revision_set(
                        root,
                        candidate,
                        accepted,
                        receipt_id="activation:stale",
                    )

    def test_failure_before_pointer_replacement_preserves_old_head_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted = revision(head, base, candidate)
            before = manifest.read_bytes()

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ), patch(
                "flowguard.model_authority_store._write_immutable_json",
                side_effect=RuntimeError("injected immutable record failure"),
            ):
                with self.assertRaisesRegex(RuntimeError, "injected"):
                    activate_model_revision_set(
                        root,
                        candidate,
                        accepted,
                        receipt_id="activation:injected",
                    )

            self.assertEqual(before, manifest.read_bytes())
            loaded_head, loaded_snapshot = load_observed_model_system(root)
            self.assertEqual(head, loaded_head)
            self.assertEqual(base, loaded_snapshot)

    def test_final_live_resample_drift_preserves_old_head(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted = revision(head, base, candidate)
            drifted = replace(
                candidate,
                claim_boundary=(
                    "This final resample intentionally differs and therefore "
                    "cannot update the observed authority pointer."
                ),
            )
            before = manifest.read_bytes()

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                side_effect=(candidate, drifted),
            ):
                with self.assertRaisesRegex(
                    ModelAuthorityError,
                    "changed before pointer",
                ):
                    activate_model_revision_set(
                        root,
                        candidate,
                        accepted,
                        receipt_id="activation:drift",
                    )

            self.assertEqual(before, manifest.read_bytes())
            self.assertEqual(head, load_observed_model_system(root)[0])

    def test_pointer_persistence_failure_preserves_old_head(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted = revision(head, base, candidate)
            before = manifest.read_bytes()

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ), patch(
                "flowguard.model_authority_store.replace_project_manifest_locked",
                side_effect=RuntimeError("injected pointer persistence failure"),
            ):
                with self.assertRaisesRegex(RuntimeError, "pointer persistence"):
                    activate_model_revision_set(
                        root,
                        candidate,
                        accepted,
                        receipt_id="activation:pointer-failure",
                    )

            self.assertEqual(before, manifest.read_bytes())
            self.assertEqual(head, load_observed_model_system(root)[0])

    def test_two_candidates_from_one_head_have_one_cas_winner(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate_b = snapshot(
                "git:" + "b" * 40,
                SHA_B,
                "observed-b",
            )
            candidate_c = snapshot(
                "git:" + "c" * 40,
                SHA_C,
                "observed-c",
            )
            revision_b = revision(head, base, candidate_b)
            revision_c = replace(
                revision(head, base, candidate_c),
                revision_set_id="revision:store-c",
            )

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate_b,
            ):
                winner_head, _ = activate_model_revision_set(
                    root,
                    candidate_b,
                    revision_b,
                    receipt_id="activation:winner",
                )
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate_c,
            ):
                with self.assertRaisesRegex(
                    ModelAuthorityError,
                    "changed|rebase|base snapshot",
                ):
                    activate_model_revision_set(
                        root,
                        candidate_c,
                        revision_c,
                        receipt_id="activation:loser",
                    )

            loaded_head, loaded_snapshot = load_observed_model_system(root)
            self.assertEqual(2, loaded_head.generation)
            self.assertEqual(winner_head, loaded_head)
            self.assertEqual(candidate_b, loaded_snapshot)

    def test_exact_rollback_activates_a_reverse_revision_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            initial_head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            forward = revision(initial_head, base, candidate)
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ):
                current_head, activation = activate_model_revision_set(
                    root,
                    candidate,
                    forward,
                    receipt_id="activation:forward",
                )
            contract = ModelRollbackContract(
                contract_id="rollback:store",
                expected_head_fingerprint=current_head.fingerprint,
                originating_revision_set_fingerprint=forward.fingerprint,
                originating_activation_receipt_fingerprint=(
                    activation.fingerprint
                ),
                from_snapshot_fingerprint=candidate.fingerprint,
                to_snapshot_fingerprint=base.fingerprint,
                effects=(
                    ModelRollbackEffect(
                        effect_id="source",
                        kind="code_config",
                        disposition="restore",
                        required_evidence_fingerprints=(SHA_C,),
                    ),
                ),
                old_snapshot_conformance_evidence_fingerprints=(SHA_D,),
            )
            reverse = replace(
                revision(current_head, candidate, base),
                revision_set_id="revision:reverse-store",
                rollback_contract_fingerprint=contract.fingerprint,
                originating_revision_set_fingerprint=forward.fingerprint,
                originating_activation_receipt_fingerprint=(
                    activation.fingerprint
                ),
            )

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=base,
            ):
                rolled_head, rollback_receipt = rollback_observed_model_system(
                    root,
                    contract,
                    base,
                    reverse,
                    completed_evidence_fingerprints=(SHA_C, SHA_D),
                    requested_result=ROLLBACK_RESULT_EXACT,
                    receipt_id="rollback:store-receipt",
                    reason="source restored and old snapshot reconformed",
                )

            loaded_head, loaded_snapshot = load_observed_model_system(root)
            self.assertEqual(3, rolled_head.generation)
            self.assertEqual(reverse.fingerprint, rolled_head.accepted_revision_set_fingerprint)
            self.assertEqual(
                rollback_receipt.fingerprint,
                rolled_head.activation_receipt_fingerprint,
            )
            self.assertNotEqual(
                rollback_receipt.fingerprint,
                rolled_head.accepted_revision_set_fingerprint,
            )
            self.assertEqual(rolled_head, loaded_head)
            self.assertEqual(base, loaded_snapshot)

    def test_shared_manifest_lock_blocks_activation_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted = revision(head, base, candidate)

            with project_manifest_lock(manifest):
                with self.assertRaisesRegex(Exception, "locked"):
                    activate_model_revision_set(
                        root,
                        candidate,
                        accepted,
                        receipt_id="activation:locked",
                    )

    def test_audit_reports_valid_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=base,
            ), patch(
                "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                return_value=manifest_inventory(),
            ):
                report = audit_model_authority(root)

            self.assertTrue(report.ok)
            self.assertEqual("pass", report.status)
            self.assertEqual(base.fingerprint, report.observed_snapshot_fingerprint)

    def test_audit_blocks_when_live_manifest_differs_from_stored_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            live = snapshot("git:" + "b" * 40, SHA_B, "observed-a")
            bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=live,
            ), patch(
                "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                return_value=manifest_inventory(),
            ):
                report = audit_model_authority(root)

            self.assertFalse(report.ok)
            self.assertEqual("blocked", report.status)
            self.assertIn(
                "observed_model_inventory_stale",
                {finding.code for finding in report.findings},
            )

    def test_audit_reports_exact_declared_materialized_and_missing_sets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            incomplete = ManifestModelInventory(
                declared_ids=("authority", "missing"),
                materialized_ids=("authority",),
                required_ids=("authority", "missing"),
                covered_ids=("authority",),
                missing_ids=("missing",),
            )

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=base,
            ), patch(
                "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                return_value=incomplete,
            ):
                report = audit_model_authority(root)

            self.assertFalse(report.ok)
            self.assertEqual(("authority", "missing"), report.declared_model_ids)
            self.assertEqual(("authority",), report.materialized_model_ids)
            self.assertEqual(("missing",), report.missing_model_ids)
            self.assertIn(
                "live_model_manifest_incomplete",
                {finding.code for finding in report.findings},
            )

    def test_existing_model_preflight_reads_observed_authority_first(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=base,
            ), patch(
                "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                return_value=manifest_inventory(),
            ):
                preflight = existing_model_preflight_from_project(
                    root,
                    "Review authority ownership",
                    downstream_routes=("development_process_flow",),
                )
            report = review_existing_model_preflight(preflight)

            self.assertTrue(report.ok, report.format_text())
            self.assertEqual("pass", preflight.authority_status)
            self.assertEqual(base.fingerprint, preflight.authority_snapshot_fingerprint)
            self.assertEqual("authoritative_observed", preflight.relevant_models[0].evidence_tier)
            self.assertTrue(preflight.relevant_models[0].evidence_current)


if __name__ == "__main__":
    unittest.main()
