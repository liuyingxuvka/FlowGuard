import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from flowguard.model_authority import (
    COVERAGE_DIMENSIONS,
    LIFECYCLE_ACTIVE,
    LIFECYCLE_CANDIDATE,
    REVISION_ACCEPTED,
    ROLLBACK_RESULT_EXACT,
    SUBJECT_NORMATIVE_TARGET,
    SUBJECT_OBSERVED_IMPLEMENTATION,
    AuthorityEndpointRef,
    CoverageDimension,
    CoverageUniverse,
    ModelAuthorityError,
    ModelAuthorityHead,
    ModelInputRef,
    ModelInstanceRef,
    ModelRelation,
    ModelRevisionSet,
    ModelRollbackContract,
    ModelRollbackEffect,
    ModelSystemSnapshot,
    RevisionEvidenceRef,
    RevisionMemberChange,
    canonical_fingerprint,
    derive_affected_closure_fingerprint,
    load_model_system_snapshot,
    validate_operational_rollback,
    validate_activation_plan,
    validate_revision_set_snapshots,
    write_content_addressed_snapshot,
)


SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
SHA_D = "sha256:" + "d" * 64
SHA_E = "sha256:" + "e" * 64
SHA_F = "sha256:" + "f" * 64


def instance(model_id: str, suffix: str) -> ModelInstanceRef:
    digit = {"a": "a", "b": "b", "c": "c"}[suffix]
    sha = "sha256:" + digit * 64
    return ModelInstanceRef(
        logical_model_id=model_id,
        model_kind="workflow",
        model_path=f".flowguard/{model_id}/model.py",
        model_sha256=sha,
        runner_path=f".flowguard/{model_id}/run_checks.py",
        runner_sha256=SHA_D,
        purpose_closure_fingerprint=SHA_E,
        subject_revision=f"git:{suffix * 40}",
        inputs=(
            ModelInputRef(f".flowguard/{model_id}/model.py", sha),
            ModelInputRef(f".flowguard/{model_id}/run_checks.py", SHA_D),
        ),
    )


def coverage(*, complete: bool = True) -> CoverageUniverse:
    dimensions = []
    for dimension_id in sorted(COVERAGE_DIMENSIONS):
        required = (f"{dimension_id}:one",)
        covered = required if complete else ()
        dimensions.append(
            CoverageDimension(
                dimension_id=dimension_id,
                required_ids=required,
                covered_ids=covered,
            )
        )
    return CoverageUniverse(
        boundary_id="flowguard-v061",
        source_inventory_fingerprint=SHA_F,
        dimensions=tuple(dimensions),
        claim_boundary=(
            "Coverage is complete only within this finite test universe and "
            "does not claim unknown software or external environments."
        ),
    )


def owner_ref() -> AuthorityEndpointRef:
    return AuthorityEndpointRef(
        endpoint_kind="behavior_commitment",
        endpoint_id="commitment:flowguard-authority",
        fingerprint=SHA_A,
        owner_route="behavior_commitment_ledger",
    )


def evidence_ref(subject: str, *, status: str) -> RevisionEvidenceRef:
    return RevisionEvidenceRef(
        receipt_id="receipt:authority",
        receipt_fingerprint=SHA_C,
        owner_route="model_test_alignment",
        subject_fingerprint=subject,
        obligation_ids=("obligation:authority",),
        status=status,
        current=True,
        eligible=True,
    )


def snapshot(
    subject_lane: str,
    lifecycle: str,
    model: ModelInstanceRef,
    *,
    snapshot_id: str,
    gaps=(),
) -> ModelSystemSnapshot:
    return ModelSystemSnapshot(
        snapshot_id=snapshot_id,
        system_id="flowguard",
        subject_lane=subject_lane,
        lifecycle=lifecycle,
        subject_revision=model.subject_revision,
        root_instance_fingerprints=(model.fingerprint,),
        model_instances=(model,),
        relations=(),
        coverage=coverage(),
        owner_artifact_refs=(owner_ref(),),
        unresolved_gap_ids=tuple(gaps),
        claim_boundary=(
            "This snapshot identifies the declared FlowGuard test system only "
            "and does not claim unenumerated production behavior."
        ),
    )


class ModelAuthorityTests(unittest.TestCase):
    def test_model_input_rejects_absolute_and_parent_paths(self):
        for value in (
            "C:\\outside\\model.py",
            "/outside/model.py",
            "\\\\server\\share\\model.py",
            "../outside/model.py",
        ):
            with self.subTest(path=value):
                with self.assertRaises(ModelAuthorityError):
                    ModelInputRef(value, SHA_A)

    def test_instance_identity_binds_resolved_inputs(self):
        base = instance("alpha", "a")
        changed = replace(
            base,
            inputs=(
                ModelInputRef(".flowguard/alpha/model.py", SHA_B),
                ModelInputRef(".flowguard/alpha/run_checks.py", SHA_D),
            ),
        )
        self.assertNotEqual(base.fingerprint, changed.fingerprint)
        self.assertNotEqual(
            base.input_inventory_fingerprint,
            changed.input_inventory_fingerprint,
        )

    def test_instance_round_trip_is_strict(self):
        value = instance("alpha", "a")
        self.assertEqual(value, ModelInstanceRef.from_dict(value.to_dict()))
        payload = value.to_dict()
        payload["unknown"] = True
        with self.assertRaises(ModelAuthorityError):
            ModelInstanceRef.from_dict(payload)

    def test_coverage_requires_set_equality_in_every_dimension(self):
        self.assertTrue(coverage().complete)
        incomplete = coverage(complete=False)
        self.assertFalse(incomplete.complete)
        self.assertEqual(
            "incomplete_within_declared_boundary",
            incomplete.status,
        )
        self.assertTrue(all(item.missing_ids for item in incomplete.dimensions))

    def test_coverage_rejects_missing_dimension(self):
        with self.assertRaises(ModelAuthorityError):
            CoverageUniverse(
                boundary_id="partial",
                source_inventory_fingerprint=SHA_A,
                dimensions=coverage().dimensions[:-1],
                claim_boundary="A sufficiently long but incomplete coverage boundary statement.",
            )

    def test_snapshot_rejects_relation_to_unknown_model(self):
        left = instance("alpha", "a")
        relation = ModelRelation(
            relation_id="alpha-depends-on-missing",
            kind="depends_on",
            source=AuthorityEndpointRef(
                endpoint_kind="model_instance",
                endpoint_id="model:alpha",
                fingerprint=left.fingerprint,
                owner_route="model_mesh_maintenance",
            ),
            target=AuthorityEndpointRef(
                endpoint_kind="model_instance",
                endpoint_id="model:missing",
                fingerprint=SHA_B,
                owner_route="model_mesh_maintenance",
            ),
        )
        with self.assertRaises(ModelAuthorityError):
            ModelSystemSnapshot(
                snapshot_id="bad-relation",
                system_id="flowguard",
                subject_lane=SUBJECT_OBSERVED_IMPLEMENTATION,
                lifecycle=LIFECYCLE_ACTIVE,
                subject_revision=left.subject_revision,
                root_instance_fingerprints=(left.fingerprint,),
                model_instances=(left,),
                relations=(relation,),
                coverage=coverage(),
                owner_artifact_refs=(owner_ref(),),
                unresolved_gap_ids=(),
                claim_boundary="A sufficiently long snapshot claim boundary for testing.",
            )

    def test_snapshot_round_trip_detects_tamper(self):
        value = snapshot(
            SUBJECT_OBSERVED_IMPLEMENTATION,
            LIFECYCLE_ACTIVE,
            instance("alpha", "a"),
            snapshot_id="observed-a",
        )
        self.assertEqual(value, ModelSystemSnapshot.from_dict(value.to_dict()))
        payload = value.to_dict()
        payload["subject_revision"] = "git:tampered"
        with self.assertRaises(ModelAuthorityError):
            ModelSystemSnapshot.from_dict(payload)

    def test_snapshot_rejects_duplicate_logical_model_and_revision_drift(self):
        first = instance("alpha", "a")
        duplicate = replace(
            instance("alpha", "b"),
            subject_revision=first.subject_revision,
        )
        with self.assertRaisesRegex(ModelAuthorityError, "logical model"):
            ModelSystemSnapshot(
                snapshot_id="duplicate-alpha",
                system_id="flowguard",
                subject_lane=SUBJECT_OBSERVED_IMPLEMENTATION,
                lifecycle=LIFECYCLE_ACTIVE,
                subject_revision=first.subject_revision,
                root_instance_fingerprints=(first.fingerprint,),
                model_instances=(first, duplicate),
                relations=(),
                coverage=coverage(),
                owner_artifact_refs=(owner_ref(),),
                unresolved_gap_ids=(),
                claim_boundary=(
                    "This duplicate fixture must fail before it can claim "
                    "one current instance for a logical model."
                ),
            )
        with self.assertRaisesRegex(ModelAuthorityError, "subject revision"):
            ModelSystemSnapshot(
                snapshot_id="revision-drift",
                system_id="flowguard",
                subject_lane=SUBJECT_OBSERVED_IMPLEMENTATION,
                lifecycle=LIFECYCLE_ACTIVE,
                subject_revision=first.subject_revision,
                root_instance_fingerprints=(first.fingerprint,),
                model_instances=(first, instance("beta", "b")),
                relations=(),
                coverage=coverage(),
                owner_artifact_refs=(owner_ref(),),
                unresolved_gap_ids=(),
                claim_boundary=(
                    "This revision drift fixture must fail before broad "
                    "model-system authority is accepted."
                ),
            )

    def test_snapshot_accepts_bound_native_owner_relation_and_rejects_unbound(self):
        model = instance("alpha", "a")
        model_endpoint = AuthorityEndpointRef(
            endpoint_kind="model_instance",
            endpoint_id="model:alpha",
            fingerprint=model.fingerprint,
            owner_route="model_mesh_maintenance",
        )
        relation = ModelRelation(
            relation_id="alpha-realizes-commitment",
            kind="realizes",
            source=model_endpoint,
            target=owner_ref(),
            evidence_fingerprints=(SHA_A,),
        )
        value = ModelSystemSnapshot(
            snapshot_id="bound-owner",
            system_id="flowguard",
            subject_lane=SUBJECT_OBSERVED_IMPLEMENTATION,
            lifecycle=LIFECYCLE_ACTIVE,
            subject_revision=model.subject_revision,
            root_instance_fingerprints=(model.fingerprint,),
            model_instances=(model,),
            relations=(relation,),
            coverage=coverage(),
            owner_artifact_refs=(owner_ref(),),
            unresolved_gap_ids=(),
            claim_boundary=(
                "This fixture proves only that typed native owner endpoints "
                "must be explicitly bound into the snapshot."
            ),
        )
        self.assertEqual((relation,), value.relations)
        with self.assertRaisesRegex(ModelAuthorityError, "unbound"):
            replace(value, owner_artifact_refs=())

    def test_content_addressed_snapshot_is_immutable(self):
        value = snapshot(
            SUBJECT_OBSERVED_IMPLEMENTATION,
            LIFECYCLE_ACTIVE,
            instance("alpha", "a"),
            snapshot_id="observed-a",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = write_content_addressed_snapshot(directory, value)
            self.assertEqual(value, load_model_system_snapshot(path))
            self.assertEqual(path, write_content_addressed_snapshot(directory, value))
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["snapshot_id"] = "tampered"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ModelAuthorityError):
                write_content_addressed_snapshot(directory, value)

    def test_snapshot_loader_rejects_duplicate_keys_and_nonfinite_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            path.write_text('{"schema":"one","schema":"two"}', encoding="utf-8")
            with self.assertRaisesRegex(ModelAuthorityError, "duplicate"):
                load_model_system_snapshot(path)
            path.write_text('{"value":NaN}', encoding="utf-8")
            with self.assertRaisesRegex(ModelAuthorityError, "non-finite"):
                load_model_system_snapshot(path)

    def _accepted_revision(
        self,
        head: ModelAuthorityHead,
        base: ModelSystemSnapshot,
        candidate: ModelSystemSnapshot,
    ) -> ModelRevisionSet:
        member = RevisionMemberChange(
            member_id="alpha",
            operation="replace",
            base_instance_fingerprint=base.model_instances[0].fingerprint,
            candidate_instance_fingerprint=(
                candidate.model_instances[0].fingerprint
            ),
            changed_element_ids=("state:alpha",),
        )
        affected_ids = ("model:alpha",)
        proposed = ModelRevisionSet(
            revision_set_id="rev-one",
            task_id="task-one",
            expected_head_fingerprint=head.fingerprint,
            base_snapshot_fingerprint=base.fingerprint,
            candidate_snapshot_fingerprint=candidate.fingerprint,
            members=(member,),
            affected_closure_ids=affected_ids,
            affected_closure_fingerprint=derive_affected_closure_fingerprint(
                affected_closure_ids=affected_ids,
                members=(member,),
            ),
            required_evidence_refs=(
                evidence_ref(candidate.fingerprint, status="required"),
            ),
        )
        return proposed.accept(
            (evidence_ref(candidate.fingerprint, status="pass"),),
            reason="all required evidence passed",
        )

    def _head(self, base: ModelSystemSnapshot) -> ModelAuthorityHead:
        return ModelAuthorityHead(
            system_id="flowguard",
            snapshot_fingerprint=base.fingerprint,
            subject_revision=base.subject_revision,
            generation=1,
            accepted_revision_set_fingerprint=SHA_A,
            previous_snapshot_fingerprint="",
            activation_receipt_fingerprint=SHA_B,
        )

    def test_revision_set_accepts_only_exact_evidence_set(self):
        base = snapshot(
            SUBJECT_OBSERVED_IMPLEMENTATION,
            LIFECYCLE_ACTIVE,
            instance("alpha", "a"),
            snapshot_id="observed-a",
        )
        candidate = snapshot(
            SUBJECT_OBSERVED_IMPLEMENTATION,
            LIFECYCLE_ACTIVE,
            instance("alpha", "b"),
            snapshot_id="observed-b",
        )
        head = self._head(base)
        proposed = replace(
            self._accepted_revision(head, base, candidate),
            status="proposed",
            completed_evidence_refs=(),
            decision_reason="",
        )
        with self.assertRaises(ModelAuthorityError):
            proposed.accept(
                (
                    evidence_ref(candidate.fingerprint, status="pass"),
                    RevisionEvidenceRef(
                        receipt_id="receipt:unrelated",
                        receipt_fingerprint=SHA_D,
                        owner_route="test_mesh_maintenance",
                        subject_fingerprint=candidate.fingerprint,
                        obligation_ids=("obligation:unrelated",),
                        status="pass",
                        current=True,
                        eligible=True,
                    ),
                ),
                reason="contains unrelated evidence",
            )

    def test_revision_set_rejects_stale_ineligible_or_wrong_subject_evidence(self):
        base = snapshot(
            SUBJECT_OBSERVED_IMPLEMENTATION,
            LIFECYCLE_ACTIVE,
            instance("alpha", "a"),
            snapshot_id="observed-a",
        )
        candidate = snapshot(
            SUBJECT_OBSERVED_IMPLEMENTATION,
            LIFECYCLE_ACTIVE,
            instance("alpha", "b"),
            snapshot_id="observed-b",
        )
        head = self._head(base)
        accepted = self._accepted_revision(head, base, candidate)
        proposed = replace(
            accepted,
            status="proposed",
            completed_evidence_refs=(),
            decision_reason="",
        )
        good = evidence_ref(candidate.fingerprint, status="pass")
        for invalid in (
            replace(good, current=False),
            replace(good, eligible=False),
            replace(good, subject_fingerprint=SHA_F),
        ):
            with self.subTest(evidence=invalid.to_dict()):
                with self.assertRaises(ModelAuthorityError):
                    proposed.accept(
                        (invalid,),
                        reason="invalid evidence must not accept revision",
                    )

    def test_revision_set_rejects_undeclared_changed_sibling(self):
        alpha_a = instance("alpha", "a")
        beta_a = replace(
            instance("beta", "a"),
            subject_revision=alpha_a.subject_revision,
        )
        alpha_b = instance("alpha", "b")
        beta_b = replace(
            instance("beta", "b"),
            subject_revision=alpha_b.subject_revision,
        )
        base = replace(
            snapshot(
                SUBJECT_OBSERVED_IMPLEMENTATION,
                LIFECYCLE_ACTIVE,
                alpha_a,
                snapshot_id="observed-a",
            ),
            model_instances=(alpha_a, beta_a),
        )
        candidate = replace(
            snapshot(
                SUBJECT_OBSERVED_IMPLEMENTATION,
                LIFECYCLE_ACTIVE,
                alpha_b,
                snapshot_id="observed-b",
            ),
            model_instances=(alpha_b, beta_b),
        )
        alpha_change = RevisionMemberChange(
            member_id="alpha",
            operation="replace",
            base_instance_fingerprint=alpha_a.fingerprint,
            candidate_instance_fingerprint=alpha_b.fingerprint,
            changed_element_ids=("state:alpha",),
        )
        revision = ModelRevisionSet(
            revision_set_id="revision:missing-beta",
            task_id="task:missing-beta",
            expected_head_fingerprint=self._head(base).fingerprint,
            base_snapshot_fingerprint=base.fingerprint,
            candidate_snapshot_fingerprint=candidate.fingerprint,
            members=(alpha_change,),
            affected_closure_ids=("model:alpha",),
            affected_closure_fingerprint=derive_affected_closure_fingerprint(
                affected_closure_ids=("model:alpha",),
                members=(alpha_change,),
            ),
            required_evidence_refs=(
                evidence_ref(candidate.fingerprint, status="required"),
            ),
        )
        with self.assertRaisesRegex(ModelAuthorityError, "model diff"):
            validate_revision_set_snapshots(base, candidate, revision)

    def test_activation_is_atomic_compare_and_swap(self):
        base = snapshot(
            SUBJECT_OBSERVED_IMPLEMENTATION,
            LIFECYCLE_ACTIVE,
            instance("alpha", "a"),
            snapshot_id="observed-a",
        )
        candidate = snapshot(
            SUBJECT_OBSERVED_IMPLEMENTATION,
            LIFECYCLE_ACTIVE,
            instance("alpha", "b"),
            snapshot_id="observed-b",
        )
        head = self._head(base)
        revision = self._accepted_revision(head, base, candidate)
        next_head, receipt = validate_activation_plan(
            head,
            base,
            candidate,
            revision,
            receipt_id="activation-one",
        )
        self.assertEqual(REVISION_ACCEPTED, revision.status)
        self.assertEqual(candidate.fingerprint, next_head.snapshot_fingerprint)
        self.assertEqual(head.snapshot_fingerprint, next_head.previous_snapshot_fingerprint)
        self.assertEqual(2, next_head.generation)
        self.assertEqual(receipt.fingerprint, next_head.activation_receipt_fingerprint)

    def test_stale_base_blocks_activation(self):
        base = snapshot(
            SUBJECT_OBSERVED_IMPLEMENTATION,
            LIFECYCLE_ACTIVE,
            instance("alpha", "a"),
            snapshot_id="observed-a",
        )
        candidate = snapshot(
            SUBJECT_OBSERVED_IMPLEMENTATION,
            LIFECYCLE_ACTIVE,
            instance("alpha", "b"),
            snapshot_id="observed-b",
        )
        head = self._head(base)
        revision = self._accepted_revision(head, base, candidate)
        advanced = replace(head, generation=2)
        with self.assertRaisesRegex(ModelAuthorityError, "rebase"):
            validate_activation_plan(
                advanced,
                base,
                candidate,
                revision,
                receipt_id="activation-stale",
            )

    def test_target_snapshot_cannot_become_observed_head(self):
        base = snapshot(
            SUBJECT_OBSERVED_IMPLEMENTATION,
            LIFECYCLE_ACTIVE,
            instance("alpha", "a"),
            snapshot_id="observed-a",
        )
        target = snapshot(
            SUBJECT_NORMATIVE_TARGET,
            LIFECYCLE_CANDIDATE,
            instance("alpha", "b"),
            snapshot_id="target-b",
        )
        head = self._head(base)
        revision = self._accepted_revision(head, base, target)
        with self.assertRaisesRegex(ModelAuthorityError, "target or experiment"):
            validate_activation_plan(
                head,
                base,
                target,
                revision,
                receipt_id="activation-target",
            )

    def test_multi_model_revision_has_one_aggregate_status(self):
        first = RevisionMemberChange(
            member_id="alpha",
            operation="replace",
            base_instance_fingerprint=SHA_A,
            candidate_instance_fingerprint=SHA_B,
            changed_element_ids=("state:alpha",),
        )
        second = RevisionMemberChange(
            member_id="beta",
            operation="replace",
            base_instance_fingerprint=SHA_C,
            candidate_instance_fingerprint=SHA_D,
            changed_element_ids=("relation:alpha-beta",),
        )
        revision = ModelRevisionSet(
            revision_set_id="multi",
            task_id="task-multi",
            expected_head_fingerprint=SHA_E,
            base_snapshot_fingerprint=SHA_A,
            candidate_snapshot_fingerprint=SHA_B,
            members=(first, second),
            affected_closure_ids=("model:alpha", "model:beta"),
            affected_closure_fingerprint=derive_affected_closure_fingerprint(
                affected_closure_ids=("model:alpha", "model:beta"),
                members=(first, second),
            ),
            required_evidence_refs=(
                RevisionEvidenceRef(
                    receipt_id="receipt:multi",
                    receipt_fingerprint=SHA_F,
                    owner_route="model_test_alignment",
                    subject_fingerprint=SHA_B,
                    obligation_ids=("obligation:multi",),
                    status="required",
                    current=True,
                    eligible=True,
                ),
            ),
        )
        self.assertEqual("proposed", revision.status)
        self.assertEqual(("alpha", "beta"), tuple(item.member_id for item in revision.members))

    def test_exact_operational_rollback_requires_restore_and_conformance(self):
        contract = ModelRollbackContract(
            contract_id="rollback-one",
            from_snapshot_fingerprint=SHA_B,
            to_snapshot_fingerprint=SHA_A,
            effects=(
                ModelRollbackEffect(
                    effect_id="source",
                    kind="code_config",
                    disposition="restore",
                    required_evidence_fingerprints=(SHA_C,),
                ),
                ModelRollbackEffect(
                    effect_id="data",
                    kind="data",
                    disposition="restore",
                    required_evidence_fingerprints=(SHA_D,),
                ),
            ),
            old_snapshot_conformance_evidence_fingerprints=(SHA_E,),
        )
        head = ModelAuthorityHead(
            system_id="flowguard",
            snapshot_fingerprint=SHA_B,
            subject_revision="git:new",
            generation=2,
            accepted_revision_set_fingerprint=SHA_C,
            previous_snapshot_fingerprint=SHA_A,
            activation_receipt_fingerprint=SHA_D,
        )
        receipt = validate_operational_rollback(
            head,
            contract,
            completed_evidence_fingerprints=(SHA_C, SHA_D, SHA_E),
            requested_result=ROLLBACK_RESULT_EXACT,
            receipt_id="rollback-receipt-one",
            reason="implementation restored and old snapshot passed",
        )
        self.assertEqual(ROLLBACK_RESULT_EXACT, receipt.result)

    def test_irreversible_effect_cannot_claim_exact_rollback(self):
        contract = ModelRollbackContract(
            contract_id="rollback-irreversible",
            from_snapshot_fingerprint=SHA_B,
            to_snapshot_fingerprint=SHA_A,
            effects=(
                ModelRollbackEffect(
                    effect_id="external",
                    kind="external_side_effect",
                    disposition="irreversible",
                    required_evidence_fingerprints=(SHA_C,),
                ),
            ),
            old_snapshot_conformance_evidence_fingerprints=(SHA_D,),
        )
        head = ModelAuthorityHead(
            system_id="flowguard",
            snapshot_fingerprint=SHA_B,
            subject_revision="git:new",
            generation=2,
            accepted_revision_set_fingerprint=SHA_C,
            previous_snapshot_fingerprint=SHA_A,
            activation_receipt_fingerprint=SHA_D,
        )
        with self.assertRaisesRegex(ModelAuthorityError, "cannot claim exact"):
            validate_operational_rollback(
                head,
                contract,
                completed_evidence_fingerprints=(SHA_C, SHA_D),
                requested_result=ROLLBACK_RESULT_EXACT,
                receipt_id="rollback-bad",
                reason="incorrect exact rollback request",
            )


if __name__ == "__main__":
    unittest.main()
