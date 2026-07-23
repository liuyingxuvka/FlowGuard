import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from flowguard.model_authority import (
    LIFECYCLE_ACTIVE,
    REVISION_EVIDENCE_PASS,
    REVISION_EVIDENCE_REQUIRED,
    SUBJECT_OBSERVED_IMPLEMENTATION,
    AuthorityEndpointRef,
    CoverageDimension,
    CoverageUniverse,
    ModelAuthorityError,
    ModelInputRef,
    ModelInstanceRef,
    ModelRevisionSet,
    ModelSystemSnapshot,
    RevisionEvidenceRef,
    RevisionMemberChange,
    derive_affected_closure_fingerprint,
)
from flowguard.model_authority_store import (
    activate_model_revision_set,
    audit_model_authority,
    bootstrap_model_authority,
    load_observed_model_system,
)
from flowguard.existing_model_preflight import (
    existing_model_preflight_from_project,
    review_existing_model_preflight,
)
from flowguard.project_manifest import project_manifest_lock


SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
SHA_D = "sha256:" + "d" * 64


def model(revision: str, sha: str) -> ModelInstanceRef:
    return ModelInstanceRef(
        logical_model_id="authority",
        model_kind="workflow",
        model_path=".flowguard/authority/model.py",
        model_sha256=sha,
        runner_path=".flowguard/authority/run_checks.py",
        runner_sha256=SHA_D,
        purpose_closure_fingerprint=SHA_C,
        subject_revision=revision,
        inputs=(
            ModelInputRef(".flowguard/authority/model.py", sha),
            ModelInputRef(".flowguard/authority/run_checks.py", SHA_D),
        ),
    )


def snapshot(revision: str, sha: str, snapshot_id: str) -> ModelSystemSnapshot:
    member = model(revision, sha)
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
    member = RevisionMemberChange(
        member_id="authority",
        operation="replace",
        base_instance_fingerprint=base.model_instances[0].fingerprint,
        candidate_instance_fingerprint=candidate.model_instances[0].fingerprint,
        changed_element_ids=("state:authority",),
    )
    closure_ids = ("model:authority",)
    required = RevisionEvidenceRef(
        receipt_id="receipt:store",
        receipt_fingerprint=SHA_C,
        owner_route="model_test_alignment",
        subject_fingerprint=candidate.fingerprint,
        obligation_ids=("obligation:store",),
        status=REVISION_EVIDENCE_REQUIRED,
        current=True,
        eligible=True,
    )
    proposed = ModelRevisionSet(
        revision_set_id="revision:store",
        task_id="task:store",
        expected_head_fingerprint=head.fingerprint,
        base_snapshot_fingerprint=base.fingerprint,
        candidate_snapshot_fingerprint=candidate.fingerprint,
        members=(member,),
        affected_closure_ids=closure_ids,
        affected_closure_fingerprint=derive_affected_closure_fingerprint(
            affected_closure_ids=closure_ids,
            members=(member,),
        ),
        required_evidence_refs=(required,),
    )
    return proposed.accept(
        (
            replace(
                required,
                status=REVISION_EVIDENCE_PASS,
            ),
        ),
        reason="store evidence passed",
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

            report = audit_model_authority(root)

            self.assertTrue(report.ok)
            self.assertEqual("pass", report.status)
            self.assertEqual(base.fingerprint, report.observed_snapshot_fingerprint)

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
