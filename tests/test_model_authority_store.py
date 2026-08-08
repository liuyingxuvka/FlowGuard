import tempfile
import unittest
from unittest.mock import patch
from dataclasses import replace
import json
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
    ModelActivationReceipt,
    ModelAuthorityError,
    ModelAuthorityHead,
    ModelInputRef,
    ModelInstanceRef,
    ModelRelation,
    ModelRevisionSet,
    ModelRollbackContract,
    ModelRollbackEffect,
    ModelRollbackReceipt,
    ModelSystemSnapshot,
    RevisionEvidenceRef,
    RevisionMemberChange,
    canonical_fingerprint,
)
from flowguard.model_revision_set import (
    MODEL_REVISION_SET_CURRENT_SCHEMA,
    derive_revision_affected_closure,
    derive_revision_snapshot_diff,
)
from flowguard.model_authority_store import (
    activate_model_revision_set,
    audit_model_authority,
    bootstrap_model_authority,
    load_current_accepted_revision_set,
    load_observed_model_system,
    rollback_observed_model_system,
)
from flowguard.model_intent import (
    ModelIntentContribution,
    ModelIntentDisposition,
    verify_model_intent_sources,
)
from flowguard.model_intent_authority import (
    CurrentEffectiveIntentView,
    EffectiveIntentTransition,
    LEGACY_CURRENT_REVISION_SCHEMA,
    _bootstrap_source_audit,
    bootstrap_current_effective_intent_view,
    build_current_effective_intent_view,
    build_current_intent_bootstrap_receipt,
)
from flowguard.existing_model_preflight import (
    existing_model_preflight_from_project,
    review_existing_model_preflight,
)
from flowguard.project_manifest import project_manifest_lock
from flowguard.model_system_inventory import ManifestModelInventory
from flowguard.source_identity import source_file_fingerprint
from tests.test_model_maturation import _path_quality


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
    purpose_ref = AuthorityEndpointRef(
        endpoint_kind="parent_closure",
        endpoint_id="purpose:authority",
        fingerprint=member.purpose_closure_fingerprint,
        owner_route="model_test_alignment",
    )
    realization = ModelRelation(
        relation_id="relation:model-realizes-purpose:authority",
        kind="realizes",
        source=AuthorityEndpointRef(
            endpoint_kind="model_instance",
            endpoint_id="model:authority",
            fingerprint=member.fingerprint,
            owner_route="model_regression_manifest",
        ),
        target=purpose_ref,
        evidence_fingerprints=(member.purpose_closure_fingerprint,),
    )
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
        relations=(realization,),
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
            purpose_ref,
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


def _current_intent(root: Path) -> ModelIntentContribution:
    source = root / "docs" / "authority-current-design.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        source.write_text(
            "The authority model owns the durable pointer transaction.\n",
            encoding="utf-8",
        )
    return ModelIntentContribution(
        contribution_id="intent:current-design:authority",
        source_kind="design",
        source_ref=source.relative_to(root).as_posix(),
        source_fingerprint=source_file_fingerprint(source),
        subject_lane="normative_target",
        subject_role="design",
        lifecycle_state="candidate",
        decision_state="accepted",
        logical_model_id="model:authority",
        unresolved_owner_id="",
        supersedes_contribution_ids=(),
        conflicts_with_contribution_ids=(),
        target_obligation_ids=(),
        target_state_ids=(),
        target_transition_ids=(),
        target_invariant_ids=(),
        target_relation_ids=("relation:model-realizes-purpose:authority",),
        desired_terminal_state_ids=(),
        target_output_ids=(),
        declared_consumer_ids=(),
        effective_revision="current-design:authority",
        rationale=(
            "The durable authority transaction is owned by this exact model "
            "and remains traceable to one current design source."
        ),
    )


def revision(root: Path, head, base, candidate) -> ModelRevisionSet:
    if head.generation == 1:
        active_contributions = (_current_intent(root),)
        bootstrap_receipt = build_current_intent_bootstrap_receipt(
            root,
            receipt_id=f"receipt:intent-bootstrap:{candidate.snapshot_id}",
            candidate_snapshot=candidate,
            current_design_contributions=active_contributions,
            rationale=(
                "The store fixture explicitly binds its one current model owner "
                "to the exact current design without inferring historical intent."
            ),
        )
        current_effective_intent_view = bootstrap_current_effective_intent_view(
            candidate,
            active_contributions,
            verify_model_intent_sources(root, active_contributions),
            bootstrap_receipt,
        )
    else:
        current_revision = load_current_accepted_revision_set(
            root,
            head=head,
            snapshot=base,
        )
        if current_revision is None:
            raise AssertionError("current v5 revision fixture is missing")
        base_view = current_revision.current_effective_intent_view
        transitions = tuple(
            EffectiveIntentTransition(
                prior_contribution_id=item.contribution_id,
                prior_contribution_fingerprint=item.fingerprint,
                action="retain",
                replacement_contribution_ids=(),
                reason=(
                    "The exact current store design remains active across this "
                    "fixture revision without semantic replacement."
                ),
            )
            for item in base_view.active_contributions
        )
        current_effective_intent_view = build_current_effective_intent_view(
            base_view,
            candidate,
            base_view.active_contributions,
            verify_model_intent_sources(root, base_view.active_contributions),
            transitions,
        )
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
        current_effective_intent_view=current_effective_intent_view,
        no_declared_intent_rationale_id="no-intent:store-fixture",
        no_declared_intent_evidence_fingerprints=(
            ("fixture_scope", candidate.fingerprint),
        ),
        no_declared_intent_rationale=(
            "This isolated durable-store fixture has no external product intent "
            "beyond exercising its declared transaction boundary."
        ),
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
            accepted = revision(root, head, base, candidate)

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

    def test_historical_typed_transition_replay_skips_new_candidate_binding_gate(self):
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
            accepted = revision(root, head, base, candidate)
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ):
                next_head, _ = activate_model_revision_set(
                    root,
                    candidate,
                    accepted,
                    receipt_id="activation:frozen-binding-replay",
                )

            regression_manifest = (
                root / ".flowguard" / "model-regression-manifest.json"
            )
            regression_manifest.write_text("{}\n", encoding="utf-8")
            with patch(
                "flowguard.model_regressions.ModelRegressionManifest.load",
                side_effect=AssertionError(
                    "historical replay must not consult the live candidate manifest"
                ),
            ) as live_manifest_load, patch(
                "flowguard.model_authority_store."
                "validate_candidate_intent_source_input_bindings"
            ) as frozen_binding_check:
                loaded = load_current_accepted_revision_set(
                    root,
                    head=next_head,
                    snapshot=candidate,
                )

            self.assertEqual(accepted, loaded)
            live_manifest_load.assert_not_called()
            frozen_binding_check.assert_not_called()

    def test_new_activation_still_checks_live_candidate_manifest_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            (root / ".flowguard" / "model-regression-manifest.json").write_text(
                "{}\n",
                encoding="utf-8",
            )
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted = revision(root, head, base, candidate)

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ), patch(
                "flowguard.model_regressions.ModelRegressionManifest.load",
                return_value=object(),
            ) as live_manifest_load, patch(
                "flowguard.model_regressions.audit_intent_source_input_bindings",
                return_value=(),
            ) as live_binding_audit, patch(
                "flowguard.model_authority_store."
                "validate_candidate_intent_source_input_bindings"
            ) as frozen_binding_check:
                activate_model_revision_set(
                    root,
                    candidate,
                    accepted,
                    receipt_id="activation:live-binding-check",
                )

            self.assertGreaterEqual(live_manifest_load.call_count, 1)
            self.assertEqual(
                live_manifest_load.call_count,
                live_binding_audit.call_count,
            )
            self.assertEqual(
                live_manifest_load.call_count,
                frozen_binding_check.call_count,
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
            accepted = revision(root, head, base, candidate)
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

    def test_activation_replays_lineage_instead_of_trusting_base_fingerprint(self):
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
            first = revision(root, initial_head, base, candidate)
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ):
                current_head, _receipt = activate_model_revision_set(
                    root,
                    candidate,
                    first,
                    receipt_id="activation:lineage-base",
                )

            next_candidate = snapshot(
                "git:" + "c" * 40,
                SHA_C,
                "observed-c",
            )
            valid_next = revision(
                root,
                current_head,
                candidate,
                next_candidate,
            )
            valid_view = valid_next.current_effective_intent_view
            forged_view = CurrentEffectiveIntentView(
                system_id=valid_view.system_id,
                subject_lane=valid_view.subject_lane,
                candidate_snapshot_fingerprint=(
                    valid_view.candidate_snapshot_fingerprint
                ),
                base_effective_intent_view_fingerprint=(
                    valid_view.base_effective_intent_view_fingerprint
                ),
                active_contributions=valid_view.active_contributions,
                verified_source_identities=valid_view.verified_source_identities,
                model_owner_ids=valid_view.model_owner_ids,
                owner_bindings=valid_view.owner_bindings,
                transitions=(),
            )
            forged_revision = replace(
                valid_next,
                current_effective_intent_view=forged_view,
            )
            before = manifest.read_bytes()

            with self.assertRaisesRegex(
                ModelAuthorityError,
                "every prior active intent requires",
            ):
                activate_model_revision_set(
                    root,
                    next_candidate,
                    forged_revision,
                    receipt_id="activation:lineage-bypass",
                )

            self.assertEqual(before, manifest.read_bytes())

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
            accepted = revision(root, head, base, candidate)
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
            accepted = revision(root, head, base, candidate)
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
            accepted = revision(root, head, base, candidate)
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
            revision_b = revision(root, head, base, candidate_b)
            revision_c = replace(
                revision(root, head, base, candidate_c),
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
            forward = revision(root, initial_head, base, candidate)
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
                revision(root, current_head, candidate, base),
                revision_set_id="revision:reverse-store",
                rollback_contract_fingerprint=contract.fingerprint,
                originating_revision_set_fingerprint=forward.fingerprint,
                originating_activation_receipt_fingerprint=(
                    activation.fingerprint
                ),
            )

            wrong_base_view = replace(
                reverse.current_effective_intent_view,
                base_effective_intent_view_fingerprint=SHA_D,
            )
            wrong_base_reverse = replace(
                reverse,
                current_effective_intent_view=wrong_base_view,
            )
            with self.assertRaisesRegex(
                ModelAuthorityError,
                "exact current base view",
            ):
                rollback_observed_model_system(
                    root,
                    contract,
                    base,
                    wrong_base_reverse,
                    completed_evidence_fingerprints=(SHA_C, SHA_D),
                    requested_result=ROLLBACK_RESULT_EXACT,
                    receipt_id="rollback:wrong-base",
                    reason="This reverse revision intentionally binds the wrong base.",
                )

            rollback_observations = 0

            def restore_then_peer_write(*_args, **_kwargs):
                nonlocal rollback_observations
                rollback_observations += 1
                if rollback_observations == 2:
                    manifest.write_text(
                        manifest.read_text(encoding="utf-8")
                        + '\n[rollback_peer]\nmarker = "preserved"\n',
                        encoding="utf-8",
                    )
                return base

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                side_effect=restore_then_peer_write,
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
            self.assertIn(
                '[rollback_peer]\nmarker = "preserved"',
                manifest.read_text(encoding="utf-8"),
            )
            self.assertEqual(
                reverse,
                load_current_accepted_revision_set(
                    root,
                    head=loaded_head,
                    snapshot=loaded_snapshot,
                ),
            )
            rollback_path = (
                root
                / ".flowguard"
                / "model-mesh"
                / "rollbacks"
                / f"{rollback_receipt.fingerprint.split(':', 1)[1]}.json"
            )
            rollback_path.unlink()
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=base,
            ), patch(
                "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                return_value=manifest_inventory(),
            ):
                missing_receipt_report = audit_model_authority(root)
            self.assertIn(
                "current_authority_transition_invalid",
                {finding.code for finding in missing_receipt_report.findings},
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
            accepted = revision(root, head, base, candidate)

            with project_manifest_lock(manifest):
                with self.assertRaisesRegex(Exception, "locked"):
                    activate_model_revision_set(
                        root,
                        candidate,
                        accepted,
                        receipt_id="activation:locked",
                    )

    def test_generation_one_audit_requires_explicit_intent_bootstrap(self):
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

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=base,
            ), patch(
                "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                return_value=manifest_inventory(),
            ):
                report = audit_model_authority(root)

            self.assertFalse(report.ok)
            self.assertEqual("blocked", report.status)
            self.assertEqual(base.fingerprint, report.observed_snapshot_fingerprint)
            self.assertEqual(
                "flowguard.model_authority_bootstrap.v1",
                report.accepted_revision_schema,
            )
            self.assertEqual(
                head.accepted_revision_set_fingerprint,
                report.accepted_revision_fingerprint,
            )
            self.assertEqual("bootstrap_required", report.intent_mode)
            self.assertEqual(0, report.active_intent_contribution_count)
            self.assertIn(
                "current_effective_intent_bootstrap_required",
                {finding.code for finding in report.findings},
            )

    def test_legacy_v4_audit_rejects_unproved_ancestry_before_bootstrap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "observed-a")
            bootstrap_head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            legacy_head = replace(
                bootstrap_head,
                generation=52,
                accepted_revision_set_fingerprint=SHA_B,
                activation_receipt_fingerprint=SHA_C,
            )

            with patch(
                "flowguard.model_authority_store.load_observed_model_system",
                return_value=(legacy_head, base),
            ), patch(
                "flowguard.model_authority_store._accepted_revision_schema",
                return_value=LEGACY_CURRENT_REVISION_SCHEMA,
            ), patch(
                "flowguard.model_authority_store._load_accepted_revision_set",
            ) as load_revision, patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=base,
            ), patch(
                "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                return_value=manifest_inventory(),
            ):
                report = audit_model_authority(root)

            load_revision.assert_not_called()
            self.assertFalse(report.ok)
            self.assertEqual("blocked", report.status)
            self.assertEqual(
                LEGACY_CURRENT_REVISION_SCHEMA,
                report.accepted_revision_schema,
            )
            self.assertEqual("blocked", report.intent_mode)
            self.assertEqual(0, report.active_intent_contribution_count)
            self.assertIn(
                "legacy_authority_ancestry_invalid",
                {finding.code for finding in report.findings},
            )
            self.assertNotIn(
                "accepted_revision_invalid",
                {finding.code for finding in report.findings},
            )

    def test_legacy_ancestry_uses_exact_heads_and_traverses_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text("[flowguard]\n", encoding="utf-8")
            base = snapshot("git:" + "a" * 40, SHA_A, "legacy-base")
            bootstrap_head = bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint=SHA_D,
            )
            candidate_one = snapshot(
                "git:" + "b" * 40,
                SHA_B,
                "legacy-one",
            )
            candidate_two = snapshot(
                "git:" + "c" * 40,
                SHA_C,
                "legacy-two",
            )
            prototype = revision(root, bootstrap_head, base, candidate_one)

            def write_artifact(category, fingerprint, payload):
                path = (
                    root
                    / ".flowguard"
                    / "model-mesh"
                    / category
                    / f"{fingerprint.split(':', 1)[1]}.json"
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(payload, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )

            def legacy_revision_payload(
                revision_id,
                expected_head,
                base_fingerprint,
                candidate_fingerprint,
                *,
                rollback_contract_fingerprint="",
                origin_revision_fingerprint="",
                origin_receipt_fingerprint="",
            ):
                payload = prototype.to_dict()
                payload["schema"] = LEGACY_CURRENT_REVISION_SCHEMA
                payload["revision_set_id"] = revision_id
                payload["expected_head_fingerprint"] = expected_head.fingerprint
                payload["base_snapshot_fingerprint"] = base_fingerprint
                payload["candidate_snapshot_fingerprint"] = candidate_fingerprint
                payload["rollback_contract_fingerprint"] = (
                    rollback_contract_fingerprint
                )
                payload["originating_revision_set_fingerprint"] = (
                    origin_revision_fingerprint
                )
                payload["originating_activation_receipt_fingerprint"] = (
                    origin_receipt_fingerprint
                )
                payload.pop("current_effective_intent_view")
                payload.pop("required_path_quality_model_ids")
                payload.pop("path_quality_subjects")
                payload.pop("path_quality_results")
                payload.pop("path_quality_result_set_fingerprint")
                payload["evidence_complete"] = True
                payload["intent_acceptance_ready"] = True
                identity = {
                    key: value
                    for key, value in payload.items()
                    if key
                    not in {
                        "fingerprint",
                        "evidence_complete",
                        "intent_acceptance_ready",
                    }
                }
                payload["fingerprint"] = canonical_fingerprint(identity)
                write_artifact("revisions", payload["fingerprint"], payload)
                return payload["fingerprint"]

            for item in (candidate_one, candidate_two):
                write_artifact("snapshots", item.fingerprint, item.to_dict())

            revision_one = legacy_revision_payload(
                "revision:legacy-one",
                bootstrap_head,
                base.fingerprint,
                candidate_one.fingerprint,
            )
            activation_one = ModelActivationReceipt(
                receipt_id="activation:legacy-one",
                system_id=base.system_id,
                revision_set_fingerprint=revision_one,
                expected_head_fingerprint=bootstrap_head.fingerprint,
                previous_snapshot_fingerprint=base.fingerprint,
                candidate_snapshot_fingerprint=candidate_one.fingerprint,
                subject_revision=candidate_one.subject_revision,
                next_generation=2,
            )
            write_artifact(
                "activations",
                activation_one.fingerprint,
                {**activation_one.to_dict(), "fingerprint": activation_one.fingerprint},
            )
            head_one = ModelAuthorityHead(
                system_id=base.system_id,
                snapshot_fingerprint=candidate_one.fingerprint,
                subject_revision=candidate_one.subject_revision,
                generation=2,
                accepted_revision_set_fingerprint=revision_one,
                previous_snapshot_fingerprint=base.fingerprint,
                activation_receipt_fingerprint=activation_one.fingerprint,
            )
            revision_two = legacy_revision_payload(
                "revision:legacy-two",
                head_one,
                candidate_one.fingerprint,
                candidate_two.fingerprint,
            )
            activation_two = ModelActivationReceipt(
                receipt_id="activation:legacy-two",
                system_id=base.system_id,
                revision_set_fingerprint=revision_two,
                expected_head_fingerprint=head_one.fingerprint,
                previous_snapshot_fingerprint=candidate_one.fingerprint,
                candidate_snapshot_fingerprint=candidate_two.fingerprint,
                subject_revision=candidate_two.subject_revision,
                next_generation=3,
            )
            write_artifact(
                "activations",
                activation_two.fingerprint,
                {**activation_two.to_dict(), "fingerprint": activation_two.fingerprint},
            )
            head_two = ModelAuthorityHead(
                system_id=base.system_id,
                snapshot_fingerprint=candidate_two.fingerprint,
                subject_revision=candidate_two.subject_revision,
                generation=3,
                accepted_revision_set_fingerprint=revision_two,
                previous_snapshot_fingerprint=candidate_one.fingerprint,
                activation_receipt_fingerprint=activation_two.fingerprint,
            )

            orphan = replace(
                activation_one,
                receipt_id="activation:unrelated-orphan",
            )
            write_artifact(
                "activations",
                orphan.fingerprint,
                {**orphan.to_dict(), "fingerprint": orphan.fingerprint},
            )
            activation_audit = _bootstrap_source_audit(
                root,
                head_two,
                candidate_two,
            )
            self.assertEqual(2, len(activation_audit.ancestry_revision_set_fingerprints))

            contract = ModelRollbackContract(
                contract_id="rollback:legacy-chain",
                expected_head_fingerprint=head_two.fingerprint,
                originating_revision_set_fingerprint=revision_two,
                originating_activation_receipt_fingerprint=activation_two.fingerprint,
                from_snapshot_fingerprint=candidate_two.fingerprint,
                to_snapshot_fingerprint=candidate_one.fingerprint,
                effects=(
                    ModelRollbackEffect(
                        effect_id="legacy-source",
                        kind="code_config",
                        disposition="restore",
                        required_evidence_fingerprints=(SHA_C,),
                    ),
                ),
                old_snapshot_conformance_evidence_fingerprints=(SHA_D,),
            )
            write_artifact(
                "rollback-contracts",
                contract.fingerprint,
                {**contract.to_dict(), "fingerprint": contract.fingerprint},
            )
            reverse_revision = legacy_revision_payload(
                "revision:legacy-reverse",
                head_two,
                candidate_two.fingerprint,
                candidate_one.fingerprint,
                rollback_contract_fingerprint=contract.fingerprint,
                origin_revision_fingerprint=revision_two,
                origin_receipt_fingerprint=activation_two.fingerprint,
            )
            rollback_receipt = ModelRollbackReceipt(
                receipt_id="rollback-receipt:legacy-chain",
                contract_fingerprint=contract.fingerprint,
                reverse_revision_set_fingerprint=reverse_revision,
                result=ROLLBACK_RESULT_EXACT,
                completed_evidence_fingerprints=(SHA_C, SHA_D),
                reason="The legacy rollback restored and reconformed the prior snapshot.",
            )
            write_artifact(
                "rollbacks",
                rollback_receipt.fingerprint,
                {
                    **rollback_receipt.to_dict(),
                    "fingerprint": rollback_receipt.fingerprint,
                },
            )
            rollback_head = ModelAuthorityHead(
                system_id=base.system_id,
                snapshot_fingerprint=candidate_one.fingerprint,
                subject_revision=candidate_one.subject_revision,
                generation=4,
                accepted_revision_set_fingerprint=reverse_revision,
                previous_snapshot_fingerprint=candidate_two.fingerprint,
                activation_receipt_fingerprint=rollback_receipt.fingerprint,
            )

            rollback_audit = _bootstrap_source_audit(
                root,
                rollback_head,
                candidate_one,
            )
            self.assertEqual(3, len(rollback_audit.ancestry_revision_set_fingerprints))
            self.assertEqual(
                rollback_receipt.fingerprint,
                rollback_audit.ancestry_activation_receipt_fingerprints[0],
            )

    def test_audit_validates_the_exact_accepted_revision_after_activation(self):
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
            accepted = revision(root, head, base, candidate)
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ):
                activate_model_revision_set(
                    root,
                    candidate,
                    accepted,
                    receipt_id="activation:audit-current-revision",
                )

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ), patch(
                "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                return_value=manifest_inventory(),
            ):
                report = audit_model_authority(root)

            self.assertTrue(report.ok, report.to_dict())
            self.assertEqual("pass", report.status)
            self.assertEqual(
                MODEL_REVISION_SET_CURRENT_SCHEMA,
                report.accepted_revision_schema,
            )
            self.assertEqual(
                accepted.fingerprint,
                report.accepted_revision_fingerprint,
            )
            self.assertEqual(
                accepted.current_effective_intent_view.fingerprint,
                report.current_effective_intent_view_fingerprint,
            )
            self.assertEqual("refine", report.intent_mode)
            self.assertEqual(1, report.active_intent_contribution_count)
            self.assertEqual(1, report.model_owner_denominator_count)
            self.assertEqual(1, report.owner_binding_count)

    def test_audit_blocks_when_current_transition_receipt_is_missing(self):
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
            accepted = revision(root, head, base, candidate)
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ):
                current_head, receipt = activate_model_revision_set(
                    root,
                    candidate,
                    accepted,
                    receipt_id="activation:audit-missing-receipt",
                )
            next_candidate = snapshot(
                "git:" + "c" * 40,
                SHA_C,
                "observed-c",
            )
            next_revision = revision(
                root,
                current_head,
                candidate,
                next_candidate,
            )
            receipt_path = (
                root
                / ".flowguard"
                / "model-mesh"
                / "activations"
                / f"{receipt.fingerprint.split(':', 1)[1]}.json"
            )
            receipt_path.unlink()

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=next_candidate,
            ), self.assertRaisesRegex(
                ModelAuthorityError,
                "exactly one typed transition receipt",
            ):
                activate_model_revision_set(
                    root,
                    next_candidate,
                    next_revision,
                    receipt_id="activation:must-validate-current-producer",
                )

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ), patch(
                "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                return_value=manifest_inventory(),
            ):
                report = audit_model_authority(root)

            self.assertEqual(current_head.fingerprint, report.head_fingerprint)
            self.assertIn(
                "current_authority_transition_invalid",
                {finding.code for finding in report.findings},
            )

    def test_audit_reports_current_intent_source_staleness_separately(self):
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
            accepted = revision(root, head, base, candidate)
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ):
                activate_model_revision_set(
                    root,
                    candidate,
                    accepted,
                    receipt_id="activation:audit-stale-source",
                )
            source = root / "docs" / "authority-current-design.md"
            source.write_text(
                "The accepted design source changed after activation.\n",
                encoding="utf-8",
            )

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ), patch(
                "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                return_value=manifest_inventory(),
            ):
                report = audit_model_authority(root)

            codes = {finding.code for finding in report.findings}
            self.assertIn("current_intent_source_stale", codes)
            self.assertNotIn("accepted_revision_invalid", codes)

    def test_activation_replays_supersession_before_rechecking_current_sources(self):
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
            candidate_one = snapshot("git:" + "b" * 40, SHA_B, "observed-b")
            accepted_one = revision(root, head, base, candidate_one)
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate_one,
            ):
                current_head, _receipt = activate_model_revision_set(
                    root,
                    candidate_one,
                    accepted_one,
                    receipt_id="activation:source-replacement-base",
                )

            candidate_two = snapshot("git:" + "c" * 40, SHA_C, "observed-c")
            retained_revision = revision(
                root,
                current_head,
                candidate_one,
                candidate_two,
            )
            current_revision = load_current_accepted_revision_set(
                root,
                head=current_head,
                snapshot=candidate_one,
            )
            self.assertIsNotNone(current_revision)
            base_view = current_revision.current_effective_intent_view
            prior = base_view.active_contributions[0]
            source = root / prior.source_ref
            source.write_text(
                "The authority model now owns a revised durable pointer transaction.\n",
                encoding="utf-8",
            )

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate_two,
            ), self.assertRaisesRegex(
                ModelAuthorityError,
                "intent source fingerprint is stale",
            ):
                activate_model_revision_set(
                    root,
                    candidate_two,
                    retained_revision,
                    receipt_id="activation:stale-retain-must-block",
                )

            replacement = replace(
                prior,
                contribution_id="intent:current-design:authority:v2",
                source_fingerprint=source_file_fingerprint(source),
                supersedes_contribution_ids=(prior.contribution_id,),
                effective_revision="current-design:authority:v2",
                rationale=(
                    "The exact changed design source explicitly supersedes its prior "
                    "contribution before the candidate inventory is reverified."
                ),
            )
            transition = EffectiveIntentTransition(
                prior_contribution_id=prior.contribution_id,
                prior_contribution_fingerprint=prior.fingerprint,
                action="supersede",
                replacement_contribution_ids=(replacement.contribution_id,),
                reason=(
                    "Replace the stale prior source identity with its exact current "
                    "successor before validating the folded active inventory."
                ),
            )
            candidate_view = build_current_effective_intent_view(
                base_view,
                candidate_two,
                (replacement,),
                verify_model_intent_sources(root, (replacement,)),
                (transition,),
            )
            disposition = ModelIntentDisposition(
                contribution_id=replacement.contribution_id,
                contribution_fingerprint=replacement.fingerprint,
                disposition="accepted",
                changed_obligation_ids=(),
                changed_state_ids=(),
                changed_transition_ids=(),
                changed_invariant_ids=(),
                changed_relation_ids=retained_revision.changed_relation_ids,
                scoped_gap_ids=(),
                conflict_ids=(),
                unresolved_effect_ids=(),
                unreachable_terminal_state_ids=(),
                unconsumed_output_ids=(),
                reason=(
                    "Accept the exact replacement because it owns the complete changed "
                    "relation set and leaves no unresolved intent effect."
                ),
            )
            replacement_revision = replace(
                retained_revision,
                revision_set_id="revision:store:source-replacement",
                intent_contributions=(replacement,),
                intent_dispositions=(disposition,),
                current_effective_intent_view=candidate_view,
                intent_contribution_inventory_fingerprint="",
                intent_conflict_ids=(),
                intent_unresolved_ids=(),
                no_declared_intent_rationale_id="",
                no_declared_intent_evidence_fingerprints=(),
                no_declared_intent_rationale="",
            )
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate_two,
            ):
                replacement_head, _receipt = activate_model_revision_set(
                    root,
                    candidate_two,
                    replacement_revision,
                    receipt_id="activation:current-source-replacement",
                )

            self.assertEqual(3, replacement_head.generation)
            self.assertEqual(
                candidate_two.fingerprint,
                replacement_head.snapshot_fingerprint,
            )

    def test_audit_distinguishes_missing_and_invalid_current_intent_sources(self):
        for mutation, expected_code in (
            ("missing", "current_intent_source_missing"),
            ("directory", "current_intent_source_invalid"),
        ):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
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
                accepted = revision(root, head, base, candidate)
                with patch(
                    "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                    return_value=candidate,
                ):
                    activate_model_revision_set(
                        root,
                        candidate,
                        accepted,
                        receipt_id=f"activation:audit-source-{mutation}",
                    )
                source = root / "docs" / "authority-current-design.md"
                source.unlink()
                if mutation == "directory":
                    source.mkdir()

                with patch(
                    "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                    return_value=candidate,
                ), patch(
                    "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                    return_value=manifest_inventory(),
                ):
                    report = audit_model_authority(root)

                codes = {finding.code for finding in report.findings}
                self.assertIn(expected_code, codes)
                self.assertNotIn("accepted_revision_invalid", codes)

    def test_activation_final_reread_preserves_peer_manifest_section(self):
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
            accepted = revision(root, head, base, candidate)
            calls = 0

            def observe_then_peer_write(*_args, **_kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    manifest.write_text(
                        manifest.read_text(encoding="utf-8")
                        + '\n[peer_agent]\nmarker = "preserved"\n',
                        encoding="utf-8",
                    )
                return candidate

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                side_effect=observe_then_peer_write,
            ):
                activate_model_revision_set(
                    root,
                    candidate,
                    accepted,
                    receipt_id="activation:peer-preserve",
                )

            self.assertIn(
                '[peer_agent]\nmarker = "preserved"',
                manifest.read_text(encoding="utf-8"),
            )

    def test_activation_final_cas_rejects_peer_authority_change(self):
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
            accepted = revision(root, head, base, candidate)
            calls = 0

            def observe_then_change_authority(*_args, **_kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    text = manifest.read_text(encoding="utf-8")
                    manifest.write_text(
                        text.replace(
                            "generation = 1",
                            "generation = 9",
                        ),
                        encoding="utf-8",
                    )
                return candidate

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                side_effect=observe_then_change_authority,
            ):
                with self.assertRaisesRegex(
                    ModelAuthorityError,
                    "authority section changed",
                ):
                    activate_model_revision_set(
                        root,
                        candidate,
                        accepted,
                        receipt_id="activation:authority-cas",
                    )

    def test_audit_keeps_leaf_reuse_and_live_staleness_as_parallel_blockers(self):
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
            accepted = revision(root, head, base, candidate)
            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=candidate,
            ):
                activate_model_revision_set(
                    root,
                    candidate,
                    accepted,
                    receipt_id="activation:audit-leaf-reuse",
                )

            revision_path = (
                root
                / ".flowguard"
                / "model-mesh"
                / "revisions"
                / f"{accepted.fingerprint.split(':', 1)[1]}.json"
            )
            payload = json.loads(revision_path.read_text(encoding="utf-8"))
            for key in ("required_evidence_refs", "completed_evidence_refs"):
                refs = payload[key]
                self.assertGreaterEqual(len(refs), 2)
                refs[1]["receipt_id"] = refs[0]["receipt_id"]
                refs[1]["receipt_fingerprint"] = refs[0][
                    "receipt_fingerprint"
                ]
            revision_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            tampered_bytes = revision_path.read_bytes()
            stale_live = replace(
                candidate,
                claim_boundary=(
                    "This live re-observation intentionally differs from the "
                    "stored snapshot so both independent blockers stay visible."
                ),
            )

            with patch(
                "flowguard.model_system_inventory.build_manifest_model_system_snapshot",
                return_value=stale_live,
            ), patch(
                "flowguard.model_system_inventory.inspect_manifest_model_inventory",
                return_value=manifest_inventory(),
            ):
                report = audit_model_authority(root)

            self.assertFalse(report.ok)
            codes = {finding.code for finding in report.findings}
            self.assertIn("accepted_revision_invalid", codes)
            self.assertIn("observed_source_inventory_stale", codes)
            accepted_finding = next(
                finding
                for finding in report.findings
                if finding.code == "accepted_revision_invalid"
            )
            self.assertIn(
                "leaf receipt cannot be reused across native owners",
                accepted_finding.message,
            )
            self.assertEqual(tampered_bytes, revision_path.read_bytes())

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

    def test_existing_model_preflight_does_not_use_observed_root_as_owner_fallback(self):
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

            self.assertFalse(report.ok, report.format_text())
            self.assertEqual("blocked", preflight.authority_status)
            self.assertEqual("", preflight.authority_snapshot_fingerprint)
            self.assertEqual((), preflight.relevant_models)
            self.assertIn(
                "modeled_current_owner_unresolved",
                {finding.code for finding in report.findings},
            )


if __name__ == "__main__":
    unittest.main()
