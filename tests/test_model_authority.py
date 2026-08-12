import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from tests.test_model_maturation import _path_quality

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
    load_model_system_snapshot,
    validate_operational_rollback,
    validate_activation_plan,
    validate_revision_set_snapshots,
    write_content_addressed_snapshot,
)
from flowguard.model_revision_set import (
    RevisionRemovalDisposition,
    derive_affected_closure_fingerprint,
    derive_revision_affected_closure,
    derive_revision_snapshot_diff,
    _native_owner_route_for_affected_id,
)
from flowguard.model_intent import (
    ModelIntentContribution,
    ModelIntentSourceIdentity,
)
from flowguard.model_intent_authority import (
    CurrentEffectiveIntentView,
    EffectiveIntentOwnerBinding,
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


def intent_purpose_ref(model: ModelInstanceRef) -> AuthorityEndpointRef:
    return AuthorityEndpointRef(
        endpoint_kind="parent_closure",
        endpoint_id=f"purpose:{model.logical_model_id}",
        fingerprint=model.purpose_closure_fingerprint,
        owner_route="model_test_alignment",
    )


def intent_realization_relation(model: ModelInstanceRef) -> ModelRelation:
    purpose = intent_purpose_ref(model)
    return ModelRelation(
        relation_id=f"relation:model-realizes-purpose:{model.logical_model_id}",
        kind="realizes",
        source=AuthorityEndpointRef(
            endpoint_kind="model_instance",
            endpoint_id=f"model:{model.logical_model_id}",
            fingerprint=model.fingerprint,
            owner_route="model_regression_manifest",
        ),
        target=purpose,
        evidence_fingerprints=(model.purpose_closure_fingerprint,),
    )


def evidence_ref(
    subject: str,
    *,
    status: str,
    candidate_snapshot_fingerprint: str,
    affected_closure_fingerprint: str,
    covered_affected_ids: tuple[str, ...],
    receipt_id: str = "receipt:authority",
    receipt_fingerprint: str = SHA_C,
    owner_route: str = "model_test_alignment",
) -> RevisionEvidenceRef:
    return RevisionEvidenceRef(
        receipt_id=receipt_id,
        receipt_fingerprint=receipt_fingerprint,
        owner_route=owner_route,
        subject_fingerprint=subject,
        obligation_ids=("obligation:authority",),
        affected_closure_fingerprint=affected_closure_fingerprint,
        covered_affected_ids=covered_affected_ids,
        candidate_snapshot_fingerprint=candidate_snapshot_fingerprint,
        toolchain_fingerprint=SHA_D,
        environment_fingerprint=SHA_E,
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
    subject_revision: str | None = None,
    gaps=(),
) -> ModelSystemSnapshot:
    revision = subject_revision or (
        "source-inventory:"
        + model.input_inventory_fingerprint.split(":", 1)[1]
    )
    purpose = intent_purpose_ref(model)
    realization = intent_realization_relation(model)
    return ModelSystemSnapshot(
        snapshot_id=snapshot_id,
        system_id="flowguard",
        subject_lane=subject_lane,
        lifecycle=lifecycle,
        subject_revision=revision,
        root_instance_fingerprints=(model.fingerprint,),
        model_instances=(model,),
        relations=(realization,),
        coverage=coverage(),
        owner_artifact_refs=(owner_ref(), purpose),
        unresolved_gap_ids=tuple(gaps),
        claim_boundary=(
            "This snapshot identifies the declared FlowGuard test system only "
            "and does not claim unenumerated production behavior."
        ),
    )


def current_intent_view(
    candidate: ModelSystemSnapshot,
) -> CurrentEffectiveIntentView:
    contributions = tuple(
        ModelIntentContribution(
            contribution_id=f"intent:authority-fixture:{item.logical_model_id}",
            source_kind="design",
            source_ref=f"design/{item.logical_model_id}.md",
            source_fingerprint=SHA_F,
            subject_lane=SUBJECT_NORMATIVE_TARGET,
            subject_role="design",
            lifecycle_state=LIFECYCLE_CANDIDATE,
            decision_state="accepted",
            logical_model_id=f"model:{item.logical_model_id}",
            unresolved_owner_id="",
            supersedes_contribution_ids=(),
            conflicts_with_contribution_ids=(),
            target_obligation_ids=(),
            target_state_ids=(),
            target_transition_ids=(),
            target_invariant_ids=(),
            target_relation_ids=(
                f"relation:model-realizes-purpose:{item.logical_model_id}",
            ),
            desired_terminal_state_ids=(),
            target_output_ids=(),
            declared_consumer_ids=(),
            effective_revision="authority-fixture:current",
            rationale=(
                "This pure authority fixture binds one current design to its "
                "exact candidate model without claiming an external source file."
            ),
        )
        for item in candidate.model_instances
    )
    sources = tuple(
        ModelIntentSourceIdentity(
            contribution_id=item.contribution_id,
            authority_kind="project_file",
            source_ref=item.source_ref,
            source_fingerprint=item.source_fingerprint,
            resolved_project_ref=item.source_ref,
        )
        for item in contributions
    )
    relation_by_id = {
        relation.relation_id: relation for relation in candidate.relations
    }
    bindings = tuple(
        EffectiveIntentOwnerBinding(
            model_owner_id=f"model-obligation:{item.logical_model_id}",
            logical_model_id=item.logical_model_id,
            realization_relation_id=(
                f"relation:model-realizes-purpose:{item.logical_model_id}"
            ),
            realization_relation_fingerprint=canonical_fingerprint(
                relation_by_id[
                    f"relation:model-realizes-purpose:{item.logical_model_id}"
                ].to_dict()
            ),
            contribution_ids=(
                f"intent:authority-fixture:{item.logical_model_id}",
            ),
        )
        for item in candidate.model_instances
    )
    return CurrentEffectiveIntentView(
        system_id=candidate.system_id,
        subject_lane=candidate.subject_lane,
        candidate_snapshot_fingerprint=candidate.fingerprint,
        base_effective_intent_view_fingerprint=SHA_E,
        active_contributions=contributions,
        verified_source_identities=sources,
        model_owner_ids=tuple(item.model_owner_id for item in bindings),
        owner_bindings=bindings,
        transitions=(),
    )


def detached_current_intent_view(
    candidate_snapshot_fingerprint: str,
    *logical_model_ids: str,
) -> CurrentEffectiveIntentView:
    contributions = tuple(
        ModelIntentContribution(
            contribution_id=f"intent:detached-fixture:{logical_model_id}",
            source_kind="design",
            source_ref=f"design/{logical_model_id}.md",
            source_fingerprint=SHA_F,
            subject_lane=SUBJECT_NORMATIVE_TARGET,
            subject_role="design",
            lifecycle_state=LIFECYCLE_CANDIDATE,
            decision_state="accepted",
            logical_model_id=f"model:{logical_model_id}",
            unresolved_owner_id="",
            supersedes_contribution_ids=(),
            conflicts_with_contribution_ids=(),
            target_obligation_ids=(),
            target_state_ids=(),
            target_transition_ids=(),
            target_invariant_ids=(),
            target_relation_ids=(
                f"relation:model-realizes-purpose:{logical_model_id}",
            ),
            desired_terminal_state_ids=(),
            target_output_ids=(),
            declared_consumer_ids=(),
            effective_revision="detached-fixture:current",
            rationale=(
                "This detached transaction fixture supplies the typed current "
                "intent identity required by the revision wire contract."
            ),
        )
        for logical_model_id in logical_model_ids
    )
    sources = tuple(
        ModelIntentSourceIdentity(
            contribution_id=item.contribution_id,
            authority_kind="project_file",
            source_ref=item.source_ref,
            source_fingerprint=item.source_fingerprint,
            resolved_project_ref=item.source_ref,
        )
        for item in contributions
    )
    bindings = tuple(
        EffectiveIntentOwnerBinding(
            model_owner_id=f"model-obligation:{logical_model_id}",
            logical_model_id=logical_model_id,
            realization_relation_id=(
                f"relation:model-realizes-purpose:{logical_model_id}"
            ),
            realization_relation_fingerprint=SHA_D,
            contribution_ids=(
                f"intent:detached-fixture:{logical_model_id}",
            ),
        )
        for logical_model_id in logical_model_ids
    )
    return CurrentEffectiveIntentView(
        system_id="flowguard",
        subject_lane=SUBJECT_OBSERVED_IMPLEMENTATION,
        candidate_snapshot_fingerprint=candidate_snapshot_fingerprint,
        base_effective_intent_view_fingerprint=SHA_E,
        active_contributions=contributions,
        verified_source_identities=sources,
        model_owner_ids=tuple(item.model_owner_id for item in bindings),
        owner_bindings=bindings,
        transitions=(),
    )


class ModelAuthorityTests(unittest.TestCase):
    def test_subject_revision_is_snapshot_identity_not_local_instance_identity(self):
        model = instance("alpha", "a")
        original = snapshot(
            SUBJECT_OBSERVED_IMPLEMENTATION,
            LIFECYCLE_ACTIVE,
            model,
            snapshot_id="observed-a",
            subject_revision="source-inventory:" + "a" * 64,
        )
        changed_revision = replace(
            original,
            subject_revision="source-inventory:" + "f" * 64,
        )

        self.assertEqual(model.fingerprint, original.model_instances[0].fingerprint)
        self.assertEqual(
            model.fingerprint,
            changed_revision.model_instances[0].fingerprint,
        )
        self.assertNotEqual(original.fingerprint, changed_revision.fingerprint)
        self.assertNotIn("subject_revision", model.to_dict())
        self.assertEqual(
            changed_revision.subject_revision,
            changed_revision.to_dict()["subject_revision"],
        )

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
        self.assertEqual("flowguard.model_instance_ref.v2", value.schema)
        self.assertEqual(value, ModelInstanceRef.from_dict(value.to_dict()))
        payload = value.to_dict()
        payload["unknown"] = True
        with self.assertRaises(ModelAuthorityError):
            ModelInstanceRef.from_dict(payload)

    def test_v1_authority_payloads_are_rejected_without_compatibility_reader(self):
        model = instance("alpha", "a")
        old_instance = model.to_dict()
        old_instance["schema"] = "flowguard.model_instance_ref.v1"
        with self.assertRaisesRegex(ModelAuthorityError, "schema"):
            ModelInstanceRef.from_dict(old_instance)

        old_field_instance = model.to_dict()
        old_field_instance["subject_revision"] = "git:" + "a" * 40
        with self.assertRaisesRegex(ModelAuthorityError, "fields"):
            ModelInstanceRef.from_dict(old_field_instance)

        current_snapshot = snapshot(
            SUBJECT_OBSERVED_IMPLEMENTATION,
            LIFECYCLE_ACTIVE,
            model,
            snapshot_id="observed-a",
        )
        old_snapshot = current_snapshot.to_dict()
        old_snapshot["schema"] = "flowguard.model_system_snapshot.v1"
        with self.assertRaisesRegex(ModelAuthorityError, "schema"):
            ModelSystemSnapshot.from_dict(old_snapshot)

        current_head = self._head(current_snapshot)
        old_head = current_head.to_dict()
        old_head["schema"] = "flowguard.model_authority_head.v1"
        with self.assertRaisesRegex(ModelAuthorityError, "schema"):
            ModelAuthorityHead.from_dict(old_head)

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
                subject_revision="source-inventory:" + "a" * 64,
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

    def test_snapshot_rejects_duplicate_logical_model(self):
        first = instance("alpha", "a")
        duplicate = instance("alpha", "b")
        with self.assertRaisesRegex(ModelAuthorityError, "logical model"):
            ModelSystemSnapshot(
                snapshot_id="duplicate-alpha",
                system_id="flowguard",
                subject_lane=SUBJECT_OBSERVED_IMPLEMENTATION,
                lifecycle=LIFECYCLE_ACTIVE,
                subject_revision="source-inventory:" + "a" * 64,
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
            subject_revision="source-inventory:" + "a" * 64,
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
        diff = derive_revision_snapshot_diff(base, candidate)
        closure = derive_revision_affected_closure(base, candidate, diff)
        path_quality_rows = tuple(
            _path_quality(
                member.member_id,
                member.candidate_instance_fingerprint,
                candidate.fingerprint,
            )
            for member in diff.members
            if member.operation in {"add", "replace"}
        )
        ids_by_owner: dict[str, list[str]] = {}
        for affected_id, owner_route in closure.owner_bindings:
            ids_by_owner.setdefault(owner_route, []).append(affected_id)
        required = tuple(
            evidence_ref(
                candidate.fingerprint,
                status="required",
                candidate_snapshot_fingerprint=candidate.fingerprint,
                affected_closure_fingerprint=closure.fingerprint,
                covered_affected_ids=tuple(ids_by_owner[owner_route]),
                receipt_id=f"receipt:authority:{index}",
                receipt_fingerprint=canonical_fingerprint(
                    {"receipt": f"authority:{index}"}
                ),
                owner_route=owner_route,
            )
            for index, owner_route in enumerate(sorted(ids_by_owner), 1)
        )
        proposed = ModelRevisionSet(
            revision_set_id="rev-one",
            task_id="task-one",
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
            removal_dispositions=tuple(
                RevisionRemovalDisposition(
                    removed_id=removed_id,
                    disposition="retire",
                    reason=(
                        "The governed identity is intentionally retired by "
                        "this exact revision."
                    ),
                )
                for removed_id in diff.removed_ids
                if not removed_id.startswith("unresolved_gap:")
            ),
            no_declared_intent_rationale_id="no-intent:authority-fixture",
            no_declared_intent_evidence_fingerprints=(
                ("fixture_scope", candidate.fingerprint),
            ),
            no_declared_intent_rationale=(
                "This isolated authority transaction fixture has no external "
                "product intent beyond exercising its declared test boundary."
            ),
            current_effective_intent_view=current_intent_view(candidate),
            required_evidence_refs=required,
            required_path_quality_model_ids=tuple(
                subject.model_id for subject, _result in path_quality_rows
            ),
            path_quality_subjects=tuple(
                subject for subject, _result in path_quality_rows
            ),
            path_quality_results=tuple(
                result for _subject, result in path_quality_rows
            ),
        )
        return proposed.accept(
            tuple(replace(item, status="pass") for item in required),
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

    def test_removed_governed_ids_require_exact_dispositions(self):
        alpha = instance("alpha", "a")
        beta = instance("beta", "b")
        base = ModelSystemSnapshot(
            snapshot_id="observed-alpha-beta",
            system_id="flowguard",
            subject_lane=SUBJECT_OBSERVED_IMPLEMENTATION,
            lifecycle=LIFECYCLE_ACTIVE,
            subject_revision="source-inventory:" + "a" * 64,
            root_instance_fingerprints=(
                alpha.fingerprint,
                beta.fingerprint,
            ),
            model_instances=(alpha, beta),
            relations=(
                intent_realization_relation(alpha),
                intent_realization_relation(beta),
            ),
            coverage=coverage(),
            owner_artifact_refs=(
                owner_ref(),
                intent_purpose_ref(alpha),
                intent_purpose_ref(beta),
            ),
            unresolved_gap_ids=(),
            claim_boundary=(
                "This base fixture represents two governed model identities "
                "before one of them is deliberately retired."
            ),
        )
        candidate = ModelSystemSnapshot(
            snapshot_id="candidate-alpha-only",
            system_id="flowguard",
            subject_lane=SUBJECT_OBSERVED_IMPLEMENTATION,
            lifecycle=LIFECYCLE_CANDIDATE,
            subject_revision="source-inventory:" + "b" * 64,
            root_instance_fingerprints=(alpha.fingerprint,),
            model_instances=(alpha,),
            relations=(intent_realization_relation(alpha),),
            coverage=coverage(),
            owner_artifact_refs=(owner_ref(), intent_purpose_ref(alpha)),
            unresolved_gap_ids=(),
            claim_boundary=(
                "This candidate fixture deliberately retires beta while "
                "keeping alpha as the sole governed model identity."
            ),
        )

        accepted = self._accepted_revision(
            self._head(base),
            base,
            candidate,
        )
        self.assertEqual(
            tuple(
                item_id
                for item_id in accepted.removed_ids
                if not item_id.startswith("unresolved_gap:")
            ),
            tuple(
                item.removed_id
                for item in accepted.removal_dispositions
            ),
        )
        self.assertEqual(
            accepted,
            ModelRevisionSet.from_dict(accepted.to_dict()),
        )
        validate_revision_set_snapshots(base, candidate, accepted)
        with self.assertRaisesRegex(
            ModelAuthorityError,
            "removed governed id",
        ):
            replace(accepted, removal_dispositions=())

    def _accepted_reverse_revision(
        self,
        head: ModelAuthorityHead,
        contract: ModelRollbackContract,
    ) -> ModelRevisionSet:
        affected_ids = ("model_instance:model:rollback",)
        owner_bindings = (
            ("model_instance:model:rollback", "model_test_alignment"),
        )
        closure_fingerprint = derive_affected_closure_fingerprint(
            affected_closure_ids=affected_ids,
            affected_edge_ids=(),
            affected_owner_bindings=owner_bindings,
        )
        member = RevisionMemberChange(
            member_id="rollback",
            operation="replace",
            base_instance_fingerprint=contract.from_snapshot_fingerprint,
            candidate_instance_fingerprint=contract.to_snapshot_fingerprint,
            changed_element_ids=affected_ids,
        )
        required = RevisionEvidenceRef(
            receipt_id="receipt:reverse",
            receipt_fingerprint=SHA_F,
            owner_route="model_test_alignment",
            subject_fingerprint=contract.to_snapshot_fingerprint,
            obligation_ids=("obligation:reverse",),
            affected_closure_fingerprint=closure_fingerprint,
            covered_affected_ids=affected_ids,
            candidate_snapshot_fingerprint=contract.to_snapshot_fingerprint,
            toolchain_fingerprint=SHA_D,
            environment_fingerprint=SHA_E,
            status="required",
            current=True,
            eligible=True,
        )
        path_subject, path_result = _path_quality(
            "rollback",
            contract.to_snapshot_fingerprint,
            contract.to_snapshot_fingerprint,
        )
        proposed = ModelRevisionSet(
            revision_set_id="revision:reverse",
            task_id="task:reverse",
            expected_head_fingerprint=head.fingerprint,
            base_snapshot_fingerprint=contract.from_snapshot_fingerprint,
            candidate_snapshot_fingerprint=contract.to_snapshot_fingerprint,
            members=(member,),
            affected_closure_ids=affected_ids,
            affected_closure_fingerprint=closure_fingerprint,
            affected_edge_ids=(),
            affected_owner_bindings=owner_bindings,
            snapshot_diff_fingerprint=SHA_F,
            required_evidence_refs=(required,),
            rollback_contract_fingerprint=contract.fingerprint,
            originating_revision_set_fingerprint=(
                contract.originating_revision_set_fingerprint
            ),
            originating_activation_receipt_fingerprint=(
                contract.originating_activation_receipt_fingerprint
            ),
            no_declared_intent_rationale_id="no-intent:rollback-fixture",
            no_declared_intent_evidence_fingerprints=(
                ("rollback_contract", contract.fingerprint),
            ),
            no_declared_intent_rationale=(
                "This isolated rollback fixture has no external product intent "
                "beyond verifying the declared reverse transaction."
            ),
            current_effective_intent_view=detached_current_intent_view(
                contract.to_snapshot_fingerprint,
                "rollback",
            ),
            required_path_quality_model_ids=("rollback",),
            path_quality_subjects=(path_subject,),
            path_quality_results=(path_result,),
        )
        return proposed.accept(
            (replace(required, status="pass"),),
            reason="restoration and reverse evidence passed",
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
            good = replace(
                proposed.required_evidence_refs[0],
                status="pass",
            )
            proposed.accept(
                (
                    good,
                    replace(
                        good,
                        receipt_id="receipt:unrelated",
                        receipt_fingerprint=SHA_D,
                        owner_route="test_mesh_maintenance",
                        obligation_ids=("obligation:unrelated",),
                    ),
                ),
                reason="contains unrelated evidence",
            )

    def test_revision_set_v5_round_trip_rejects_legacy_revision_shape(self):
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
        accepted = self._accepted_revision(self._head(base), base, candidate)
        self.assertEqual("flowguard.model_revision_set.v5", accepted.schema)
        self.assertEqual(
            accepted,
            ModelRevisionSet.from_dict(accepted.to_dict()),
        )
        legacy = accepted.to_dict()
        legacy["schema"] = "flowguard.model_revision_set.v4"
        for evidence_list in (
            legacy["required_evidence_refs"],
            legacy["completed_evidence_refs"],
        ):
            for evidence in evidence_list:
                evidence["schema"] = "flowguard.model_revision_evidence.v1"
                evidence.pop("affected_closure_fingerprint")
                evidence.pop("covered_affected_ids")
                evidence.pop("candidate_snapshot_fingerprint")
                evidence.pop("toolchain_fingerprint")
                evidence.pop("environment_fingerprint")

        with self.assertRaises(ModelAuthorityError):
            ModelRevisionSet.from_dict(legacy)

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
        good = replace(
            proposed.required_evidence_refs[0],
            status="pass",
        )
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
        beta_a = instance("beta", "a")
        alpha_b = instance("alpha", "b")
        beta_b = instance("beta", "b")
        base = replace(
            snapshot(
                SUBJECT_OBSERVED_IMPLEMENTATION,
                LIFECYCLE_ACTIVE,
                alpha_a,
                snapshot_id="observed-a",
            ),
            model_instances=(alpha_a, beta_a),
            relations=(
                intent_realization_relation(alpha_a),
                intent_realization_relation(beta_a),
            ),
            owner_artifact_refs=(
                owner_ref(),
                intent_purpose_ref(alpha_a),
                intent_purpose_ref(beta_a),
            ),
        )
        candidate = replace(
            snapshot(
                SUBJECT_OBSERVED_IMPLEMENTATION,
                LIFECYCLE_ACTIVE,
                alpha_b,
                snapshot_id="observed-b",
            ),
            model_instances=(alpha_b, beta_b),
            relations=(
                intent_realization_relation(alpha_b),
                intent_realization_relation(beta_b),
            ),
            owner_artifact_refs=(
                owner_ref(),
                intent_purpose_ref(alpha_b),
                intent_purpose_ref(beta_b),
            ),
        )
        valid = self._accepted_revision(self._head(base), base, candidate)
        alpha_change = next(
            item for item in valid.members if item.member_id == "alpha"
        )
        alpha_subject = next(
            item
            for item in valid.path_quality_subjects
            if item.model_id == "alpha"
        )
        alpha_result = next(
            item
            for item in valid.path_quality_results
            if item.subject_fingerprint == alpha_subject.fingerprint
        )
        revision = replace(
            valid,
            members=(alpha_change,),
            required_path_quality_model_ids=("alpha",),
            path_quality_subjects=(alpha_subject,),
            path_quality_results=(alpha_result,),
            path_quality_result_set_fingerprint="",
            status="proposed",
            completed_evidence_refs=(),
            decision_reason="",
        )
        with self.assertRaisesRegex(ModelAuthorityError, "members"):
            validate_revision_set_snapshots(base, candidate, revision)

    def test_revision_set_rejects_undeclared_changed_source_surface(self):
        alpha_a = instance("alpha", "a")
        alpha_b = instance("alpha", "b")
        base = replace(
            snapshot(
                SUBJECT_OBSERVED_IMPLEMENTATION,
                LIFECYCLE_ACTIVE,
                alpha_a,
                snapshot_id="observed-a",
            ),
            owner_artifact_refs=(
                AuthorityEndpointRef(
                    endpoint_kind="external_surface",
                    endpoint_id="surface:alpha",
                    fingerprint=SHA_A,
                    owner_route="behavior_commitment_ledger",
                ),
                intent_purpose_ref(alpha_a),
            ),
        )
        candidate = replace(
            snapshot(
                SUBJECT_OBSERVED_IMPLEMENTATION,
                LIFECYCLE_ACTIVE,
                alpha_b,
                snapshot_id="observed-b",
            ),
            owner_artifact_refs=(
                AuthorityEndpointRef(
                    endpoint_kind="external_surface",
                    endpoint_id="surface:alpha",
                    fingerprint=SHA_B,
                    owner_route="behavior_commitment_ledger",
                ),
                intent_purpose_ref(alpha_b),
            ),
        )
        valid = self._accepted_revision(self._head(base), base, candidate)
        revision = replace(
            valid,
            changed_source_surface_ids=(),
            status="proposed",
            completed_evidence_refs=(),
            decision_reason="",
        )

        with self.assertRaisesRegex(
            ModelAuthorityError,
            "changed_source_surface_ids",
        ):
            validate_revision_set_snapshots(base, candidate, revision)

    def test_full_snapshot_diff_covers_root_owner_coverage_and_gap_changes(self):
        alpha_a = instance("alpha", "a")
        alpha_b = instance("alpha", "b")
        base = snapshot(
            SUBJECT_OBSERVED_IMPLEMENTATION,
            LIFECYCLE_ACTIVE,
            alpha_a,
            snapshot_id="observed-a",
        )
        candidate = replace(
            snapshot(
                SUBJECT_OBSERVED_IMPLEMENTATION,
                LIFECYCLE_ACTIVE,
                alpha_b,
                snapshot_id="observed-b",
            ),
            coverage=coverage(complete=False),
            owner_artifact_refs=(
                replace(owner_ref(), fingerprint=SHA_B),
                intent_purpose_ref(alpha_b),
            ),
            unresolved_gap_ids=("gap:new",),
        )

        diff = derive_revision_snapshot_diff(base, candidate)

        self.assertEqual(("alpha",), tuple(x.member_id for x in diff.members))
        self.assertEqual(("root:model:alpha",), diff.changed_root_ids)
        self.assertIn(
            "behavior_commitment:commitment:flowguard-authority",
            diff.changed_owner_artifact_ids,
        )
        self.assertTrue(diff.changed_coverage_ids)
        self.assertEqual(("gap:new",), diff.changed_gap_ids)
        self.assertIn(
            "system_property:subject_revision",
            diff.changed_system_property_ids,
        )

    def test_model_mesh_owns_only_explicit_revision_accounting_categories(self):
        for affected_id in (
            "root:model:alpha",
            "model_relation:relation:test",
            "coverage:model_instances:alpha",
            "unresolved_gap:gap:test",
            "system_property:subject_revision",
        ):
            with self.subTest(affected_id=affected_id):
                self.assertEqual(
                    "model_mesh_maintenance",
                    _native_owner_route_for_affected_id(affected_id, {}),
                )

        self.assertEqual(
            "behavior_commitment_ledger",
            _native_owner_route_for_affected_id(
                "behavior_commitment:commitment:test",
                {
                    "behavior_commitment:commitment:test": (
                        "behavior_commitment_ledger"
                    )
                },
            ),
        )

    def test_unknown_affected_id_category_cannot_fall_back_to_model_mesh(self):
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
        diff = replace(
            derive_revision_snapshot_diff(base, candidate),
            changed_system_property_ids=("future_affected_category:item",),
        )

        with self.assertRaisesRegex(
            ModelAuthorityError,
            "affected id has no native owner route: future_affected_category:item",
        ):
            derive_revision_affected_closure(base, candidate, diff)

    def test_owner_only_revision_requires_no_fake_model_member(self):
        model_value = instance("alpha", "a")
        base = snapshot(
            SUBJECT_OBSERVED_IMPLEMENTATION,
            LIFECYCLE_ACTIVE,
            model_value,
            snapshot_id="observed-a",
        )
        candidate = replace(
            snapshot(
                SUBJECT_OBSERVED_IMPLEMENTATION,
                LIFECYCLE_ACTIVE,
                model_value,
                snapshot_id="observed-b",
            ),
            owner_artifact_refs=(
                replace(owner_ref(), fingerprint=SHA_B),
                intent_purpose_ref(model_value),
            ),
        )
        diff = derive_revision_snapshot_diff(base, candidate)
        closure = derive_revision_affected_closure(base, candidate, diff)
        required = RevisionEvidenceRef(
            receipt_id="receipt:owner-only",
            receipt_fingerprint=SHA_C,
            owner_route="behavior_commitment_ledger",
            subject_fingerprint=candidate.fingerprint,
            obligation_ids=("obligation:owner-only",),
            affected_closure_fingerprint=closure.fingerprint,
            covered_affected_ids=closure.affected_ids,
            candidate_snapshot_fingerprint=candidate.fingerprint,
            toolchain_fingerprint=SHA_D,
            environment_fingerprint=SHA_E,
            status="required",
            current=True,
            eligible=True,
        )
        revision = ModelRevisionSet(
            revision_set_id="revision:owner-only",
            task_id="task:owner-only",
            expected_head_fingerprint=self._head(base).fingerprint,
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
            current_effective_intent_view=current_intent_view(candidate),
            required_evidence_refs=(required,),
        )

        self.assertFalse(revision.members)
        validate_revision_set_snapshots(base, candidate, revision)

    def test_fixed_point_closure_does_not_fan_parent_to_unchanged_sibling(self):
        alpha_a = instance("alpha", "a")
        alpha_b = instance("alpha", "b")
        beta = instance("beta", "a")
        parent = AuthorityEndpointRef(
            endpoint_kind="parent_closure",
            endpoint_id="system:test",
            fingerprint=SHA_F,
            owner_route="model_mesh_maintenance",
        )

        def contains(model_value: ModelInstanceRef) -> ModelRelation:
            return ModelRelation(
                relation_id=(
                    f"relation:contains:{model_value.logical_model_id}"
                ),
                kind="contains",
                source=parent,
                target=AuthorityEndpointRef(
                    endpoint_kind="model_instance",
                    endpoint_id=f"model:{model_value.logical_model_id}",
                    fingerprint=model_value.fingerprint,
                    owner_route="model_regression_manifest",
                ),
            )

        base = replace(
            snapshot(
                SUBJECT_OBSERVED_IMPLEMENTATION,
                LIFECYCLE_ACTIVE,
                alpha_a,
                snapshot_id="observed-a",
            ),
            model_instances=(alpha_a, beta),
            relations=(contains(alpha_a), contains(beta)),
            owner_artifact_refs=(parent,),
        )
        candidate = replace(
            snapshot(
                SUBJECT_OBSERVED_IMPLEMENTATION,
                LIFECYCLE_ACTIVE,
                alpha_b,
                snapshot_id="observed-b",
            ),
            model_instances=(alpha_b, beta),
            relations=(contains(alpha_b), contains(beta)),
            owner_artifact_refs=(parent,),
        )

        closure = derive_revision_affected_closure(base, candidate)

        self.assertIn("model_instance:model:alpha", closure.affected_ids)
        self.assertIn("parent_closure:system:test", closure.affected_ids)
        self.assertNotIn("model_instance:model:beta", closure.affected_ids)

    def test_two_receipts_may_collectively_cover_the_exact_closure(self):
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
        accepted = self._accepted_revision(self._head(base), base, candidate)
        required = accepted.required_evidence_refs
        self.assertEqual(2, len(required))
        proposed = replace(
            accepted,
            required_evidence_refs=required,
            completed_evidence_refs=(),
            status="proposed",
            decision_reason="",
        )

        result = proposed.accept(
            tuple(replace(item, status="pass") for item in required),
            reason="two native owners close the exact affected set",
        )

        self.assertTrue(result.evidence_complete)

    def test_evidence_receipt_list_cannot_hide_uncovered_affected_ids(self):
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
        accepted = self._accepted_revision(self._head(base), base, candidate)
        template = accepted.required_evidence_refs[0]
        incomplete = replace(
            template,
            covered_affected_ids=template.covered_affected_ids[:1],
        )
        with self.assertRaisesRegex(ModelAuthorityError, "merged reference"):
            replace(
                accepted,
                required_evidence_refs=(incomplete,),
                completed_evidence_refs=(),
                status="proposed",
                decision_reason="",
            )

    def test_evidence_covered_ids_require_their_native_owner_route(self):
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
        accepted = self._accepted_revision(self._head(base), base, candidate)
        required = accepted.required_evidence_refs
        wrong = replace(
            required[0],
            owner_route=(
                "test_mesh_maintenance"
                if required[0].owner_route != "test_mesh_maintenance"
                else "model_mesh_maintenance"
            ),
        )

        with self.assertRaisesRegex(ModelAuthorityError, "native owner"):
            replace(
                accepted,
                required_evidence_refs=(wrong, *required[1:]),
                completed_evidence_refs=(),
                status="proposed",
                decision_reason="",
            )

    def test_one_leaf_receipt_cannot_be_reused_across_native_owner_routes(self):
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
        accepted = self._accepted_revision(self._head(base), base, candidate)
        required = accepted.required_evidence_refs
        self.assertGreaterEqual(len(required), 2)
        reused = replace(
            required[1],
            receipt_id=required[0].receipt_id,
            receipt_fingerprint=required[0].receipt_fingerprint,
        )

        with self.assertRaisesRegex(ModelAuthorityError, "leaf receipt"):
            replace(
                accepted,
                required_evidence_refs=(required[0], reused, *required[2:]),
                completed_evidence_refs=(),
                status="proposed",
                decision_reason="",
            )

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
            live_candidate_snapshot=candidate,
            receipt_id="activation-one",
        )
        self.assertEqual(REVISION_ACCEPTED, revision.status)
        self.assertEqual(candidate.fingerprint, next_head.snapshot_fingerprint)
        self.assertEqual(head.snapshot_fingerprint, next_head.previous_snapshot_fingerprint)
        self.assertEqual(2, next_head.generation)
        self.assertEqual(receipt.fingerprint, next_head.activation_receipt_fingerprint)

    def test_activation_blocks_same_head_when_live_candidate_drifted(self):
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
        drifted = replace(
            candidate,
            claim_boundary=(
                "This freshly rebuilt candidate intentionally differs from "
                "the accepted candidate and cannot move authority."
            ),
        )

        with self.assertRaisesRegex(ModelAuthorityError, "live candidate"):
            validate_activation_plan(
                head,
                base,
                candidate,
                revision,
                live_candidate_snapshot=drifted,
                receipt_id="activation:live-drift",
            )

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
                live_candidate_snapshot=candidate,
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
                live_candidate_snapshot=target,
                receipt_id="activation-target",
            )

    def test_multi_model_revision_has_one_aggregate_status(self):
        first = RevisionMemberChange(
            member_id="alpha",
            operation="replace",
            base_instance_fingerprint=SHA_A,
            candidate_instance_fingerprint=SHA_B,
            changed_element_ids=("model_instance:model:alpha",),
        )
        second = RevisionMemberChange(
            member_id="beta",
            operation="replace",
            base_instance_fingerprint=SHA_C,
            candidate_instance_fingerprint=SHA_D,
            changed_element_ids=("model_instance:model:beta",),
        )
        affected_ids = (
            "model_instance:model:alpha",
            "model_instance:model:beta",
        )
        owner_bindings = tuple(
            (affected_id, "model_test_alignment")
            for affected_id in affected_ids
        )
        closure_fingerprint = derive_affected_closure_fingerprint(
            affected_closure_ids=affected_ids,
            affected_edge_ids=(),
            affected_owner_bindings=owner_bindings,
        )
        revision = ModelRevisionSet(
            revision_set_id="multi",
            task_id="task-multi",
            expected_head_fingerprint=SHA_E,
            base_snapshot_fingerprint=SHA_A,
            candidate_snapshot_fingerprint=SHA_B,
            members=(first, second),
            affected_closure_ids=affected_ids,
            affected_closure_fingerprint=closure_fingerprint,
            affected_edge_ids=(),
            affected_owner_bindings=owner_bindings,
            snapshot_diff_fingerprint=SHA_F,
            current_effective_intent_view=detached_current_intent_view(
                SHA_B,
                "alpha",
                "beta",
            ),
            required_evidence_refs=(
                RevisionEvidenceRef(
                    receipt_id="receipt:multi",
                    receipt_fingerprint=SHA_F,
                    owner_route="model_test_alignment",
                    subject_fingerprint=SHA_B,
                    obligation_ids=("obligation:multi",),
                    affected_closure_fingerprint=closure_fingerprint,
                    covered_affected_ids=affected_ids,
                    candidate_snapshot_fingerprint=SHA_B,
                    toolchain_fingerprint=SHA_C,
                    environment_fingerprint=SHA_D,
                    status="required",
                    current=True,
                    eligible=True,
                ),
            ),
        )
        self.assertEqual("proposed", revision.status)
        self.assertEqual(("alpha", "beta"), tuple(item.member_id for item in revision.members))

    def test_exact_operational_rollback_requires_restore_and_conformance(self):
        head = ModelAuthorityHead(
            system_id="flowguard",
            snapshot_fingerprint=SHA_B,
            subject_revision="git:new",
            generation=2,
            accepted_revision_set_fingerprint=SHA_C,
            previous_snapshot_fingerprint=SHA_A,
            activation_receipt_fingerprint=SHA_D,
        )
        contract = ModelRollbackContract(
            contract_id="rollback-one",
            expected_head_fingerprint=head.fingerprint,
            originating_revision_set_fingerprint=SHA_C,
            originating_activation_receipt_fingerprint=SHA_D,
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
        reverse_revision = self._accepted_reverse_revision(head, contract)
        receipt = validate_operational_rollback(
            head,
            contract,
            reverse_revision,
            completed_evidence_fingerprints=(SHA_C, SHA_D, SHA_E),
            requested_result=ROLLBACK_RESULT_EXACT,
            receipt_id="rollback-receipt-one",
            reason="implementation restored and old snapshot passed",
        )
        self.assertEqual(ROLLBACK_RESULT_EXACT, receipt.result)

    def test_irreversible_effect_cannot_claim_exact_rollback(self):
        head = ModelAuthorityHead(
            system_id="flowguard",
            snapshot_fingerprint=SHA_B,
            subject_revision="git:new",
            generation=2,
            accepted_revision_set_fingerprint=SHA_C,
            previous_snapshot_fingerprint=SHA_A,
            activation_receipt_fingerprint=SHA_D,
        )
        contract = ModelRollbackContract(
            contract_id="rollback-irreversible",
            expected_head_fingerprint=head.fingerprint,
            originating_revision_set_fingerprint=SHA_C,
            originating_activation_receipt_fingerprint=SHA_D,
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
        reverse_revision = self._accepted_reverse_revision(head, contract)
        with self.assertRaisesRegex(ModelAuthorityError, "cannot claim exact"):
            validate_operational_rollback(
                head,
                contract,
                reverse_revision,
                completed_evidence_fingerprints=(SHA_C, SHA_D),
                requested_result=ROLLBACK_RESULT_EXACT,
                receipt_id="rollback-bad",
                reason="incorrect exact rollback request",
            )

    def test_old_rollback_contract_cannot_replay_at_later_same_snapshot(self):
        old_head = ModelAuthorityHead(
            system_id="flowguard",
            snapshot_fingerprint=SHA_B,
            subject_revision="git:new",
            generation=2,
            accepted_revision_set_fingerprint=SHA_C,
            previous_snapshot_fingerprint=SHA_A,
            activation_receipt_fingerprint=SHA_D,
        )
        contract = ModelRollbackContract(
            contract_id="rollback:old-head",
            expected_head_fingerprint=old_head.fingerprint,
            originating_revision_set_fingerprint=SHA_C,
            originating_activation_receipt_fingerprint=SHA_D,
            from_snapshot_fingerprint=SHA_B,
            to_snapshot_fingerprint=SHA_A,
            effects=(
                ModelRollbackEffect(
                    effect_id="source",
                    kind="code_config",
                    disposition="restore",
                    required_evidence_fingerprints=(SHA_C,),
                ),
            ),
            old_snapshot_conformance_evidence_fingerprints=(SHA_E,),
        )
        reverse_revision = self._accepted_reverse_revision(
            old_head,
            contract,
        )
        later_head = replace(
            old_head,
            generation=4,
            accepted_revision_set_fingerprint=SHA_E,
            activation_receipt_fingerprint=SHA_F,
        )

        with self.assertRaisesRegex(ModelAuthorityError, "advanced"):
            validate_operational_rollback(
                later_head,
                contract,
                reverse_revision,
                completed_evidence_fingerprints=(SHA_C, SHA_E),
                requested_result=ROLLBACK_RESULT_EXACT,
                receipt_id="rollback:replay",
                reason="an old head contract must not replay",
            )


if __name__ == "__main__":
    unittest.main()
