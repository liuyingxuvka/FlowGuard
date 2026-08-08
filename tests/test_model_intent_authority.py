import tempfile
from pathlib import Path

import pytest

from flowguard.model_authority import (
    LIFECYCLE_ACTIVE,
    SUBJECT_NORMATIVE_TARGET,
    SUBJECT_OBSERVED_IMPLEMENTATION,
    AuthorityEndpointRef,
    CoverageDimension,
    CoverageUniverse,
    ModelAuthorityError,
    ModelInputRef,
    ModelInstanceRef,
    ModelRelation,
    ModelSystemSnapshot,
)
from flowguard.model_authority_store import bootstrap_model_authority
from flowguard.model_intent import (
    ModelIntentContribution,
    ModelIntentDisposition,
    verify_model_intent_sources,
)
from flowguard.model_intent_authority import (
    CurrentEffectiveIntentView,
    EffectiveIntentBootstrapReceipt,
    EffectiveIntentTransition,
    LegacyIntentAuditEntry,
    LegacyIntentBootstrapDisposition,
    bootstrap_current_effective_intent_view,
    build_current_intent_bootstrap_receipt,
    derive_effective_intent_owner_bindings,
    fold_effective_intent_contributions,
    validate_legacy_intent_bootstrap_dispositions,
)
from flowguard.source_identity import source_file_fingerprint


SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
SHA_D = "sha256:" + "d" * 64


def _snapshot(
    model_ids=("alpha", "beta"),
    *,
    snapshot_id="observed-current",
    model_sha=SHA_A,
) -> ModelSystemSnapshot:
    instances = tuple(
        ModelInstanceRef(
            logical_model_id=model_id,
            model_kind="workflow",
            model_path=f".flowguard/{model_id}/model.py",
            model_sha256=model_sha,
            runner_path=f".flowguard/{model_id}/run_checks.py",
            runner_sha256=SHA_B,
            purpose_closure_fingerprint=(
                "sha256:" + f"{index:x}"[-1] * 64
            ),
            inputs=(
                ModelInputRef(
                    f".flowguard/{model_id}/model.py",
                    model_sha,
                ),
                ModelInputRef(
                    f".flowguard/{model_id}/run_checks.py",
                    SHA_B,
                ),
            ),
        )
        for index, model_id in enumerate(model_ids, 1)
    )
    purpose_refs = tuple(
        AuthorityEndpointRef(
            endpoint_kind="parent_closure",
            endpoint_id=f"purpose:{item.logical_model_id}",
            fingerprint=item.purpose_closure_fingerprint,
            owner_route="model_test_alignment",
        )
        for item in instances
    )
    relations = tuple(
        ModelRelation(
            relation_id=(
                f"relation:model-realizes-purpose:{item.logical_model_id}"
            ),
            kind="realizes",
            source=AuthorityEndpointRef(
                endpoint_kind="model_instance",
                endpoint_id=f"model:{item.logical_model_id}",
                fingerprint=item.fingerprint,
                owner_route="model_regression_manifest",
            ),
            target=purpose_ref,
            evidence_fingerprints=(item.purpose_closure_fingerprint,),
        )
        for item, purpose_ref in zip(instances, purpose_refs, strict=True)
    )
    dimensions = tuple(
        CoverageDimension(
            dimension_id=dimension_id,
            required_ids=(f"{dimension_id}:one",),
            covered_ids=(f"{dimension_id}:one",),
        )
        for dimension_id in sorted(
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
        subject_revision="git:" + "a" * 40,
        root_instance_fingerprints=(instances[0].fingerprint,),
        model_instances=instances,
        relations=relations,
        coverage=CoverageUniverse(
            boundary_id="intent-authority-test",
            source_inventory_fingerprint=SHA_C,
            dimensions=dimensions,
            claim_boundary=(
                "This finite test snapshot covers only current intent authority "
                "bindings and does not claim production software behavior."
            ),
        ),
        owner_artifact_refs=purpose_refs,
        unresolved_gap_ids=(),
        claim_boundary=(
            "This finite test snapshot exists only to exercise direct current "
            "intent ownership and no unenumerated production behavior."
        ),
    )


def _contribution(
    root: Path,
    model_id: str,
    *,
    contribution_id: str | None = None,
    text: str | None = None,
    supersedes=(),
    conflicts=(),
) -> ModelIntentContribution:
    source_label = (contribution_id or "current").replace(":", "_")
    source = root / "design" / f"{model_id}-{source_label}.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        text or f"Current design for {model_id}.\n",
        encoding="utf-8",
    )
    return ModelIntentContribution(
        contribution_id=contribution_id or f"intent:current-design:{model_id}",
        source_kind="design",
        source_ref=source.relative_to(root).as_posix(),
        source_fingerprint=source_file_fingerprint(source),
        subject_lane=SUBJECT_NORMATIVE_TARGET,
        subject_role="design",
        lifecycle_state="candidate",
        decision_state="accepted",
        logical_model_id=f"model:{model_id}",
        unresolved_owner_id="",
        supersedes_contribution_ids=tuple(supersedes),
        conflicts_with_contribution_ids=tuple(conflicts),
        target_obligation_ids=(),
        target_state_ids=(),
        target_transition_ids=(),
        target_invariant_ids=(),
        target_relation_ids=(
            f"relation:model-realizes-purpose:{model_id}",
        ),
        desired_terminal_state_ids=(),
        target_output_ids=(),
        declared_consumer_ids=(),
        effective_revision=f"current-design:{model_id}",
        rationale=(
            f"The current {model_id} design directly owns its model purpose "
            "and remains independently traceable to this exact source."
        ),
    )


def _accepted_disposition(
    contribution: ModelIntentContribution,
) -> ModelIntentDisposition:
    return ModelIntentDisposition(
        contribution_id=contribution.contribution_id,
        contribution_fingerprint=contribution.fingerprint,
        disposition="accepted",
        changed_obligation_ids=(),
        changed_state_ids=(),
        changed_transition_ids=(),
        changed_invariant_ids=(),
        changed_relation_ids=contribution.target_relation_ids,
        scoped_gap_ids=(),
        conflict_ids=(),
        unresolved_effect_ids=(),
        unreachable_terminal_state_ids=(),
        unconsumed_output_ids=(),
        reason=(
            "This revision accepts the exact current design effect with no "
            "unresolved output, conflict, or owner ambiguity."
        ),
    )


def _bootstrap_view(
    root: Path,
    base: ModelSystemSnapshot,
    candidate: ModelSystemSnapshot,
    contributions,
) -> CurrentEffectiveIntentView:
    bootstrap_model_authority(
        root,
        base,
        bootstrap_evidence_fingerprint=SHA_D,
    )
    receipt = build_current_intent_bootstrap_receipt(
        root,
        receipt_id="receipt:intent-bootstrap:test",
        candidate_snapshot=candidate,
        current_design_contributions=contributions,
        rationale=(
            "The explicit test bootstrap uses current design sources for every "
            "candidate model and does not infer current intent from old deltas."
        ),
    )
    return bootstrap_current_effective_intent_view(
        candidate,
        contributions,
        verify_model_intent_sources(root, contributions),
        receipt,
    )


def test_derives_exact_owner_denominator_and_rejects_missing_design() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        snapshot = _snapshot()
        alpha = _contribution(root, "alpha")
        beta = _contribution(root, "beta")

        bindings = derive_effective_intent_owner_bindings(
            snapshot,
            (alpha, beta),
        )

        assert tuple(item.model_owner_id for item in bindings) == (
            "model-obligation:alpha",
            "model-obligation:beta",
        )
        assert tuple(item.realization_relation_id for item in bindings) == (
            "relation:model-realizes-purpose:alpha",
            "relation:model-realizes-purpose:beta",
        )
        with pytest.raises(
            ModelAuthorityError,
            match="lack a direct current design contribution",
        ):
            derive_effective_intent_owner_bindings(snapshot, (alpha,))


def test_exact_owner_binding_scales_to_sixty_independent_models() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        model_ids = tuple(f"owner-{index:02d}" for index in range(60))
        snapshot = _snapshot(model_ids)
        contributions = tuple(
            _contribution(root, model_id) for model_id in model_ids
        )

        bindings = derive_effective_intent_owner_bindings(
            snapshot,
            contributions,
        )

        assert len(bindings) == 60
        assert len({item.model_owner_id for item in bindings}) == 60
        assert tuple(
            contribution_id
            for binding in bindings
            for contribution_id in binding.contribution_ids
        ) == tuple(item.contribution_id for item in contributions)


def test_rejects_root_or_inexact_realization_fallback() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        snapshot = _snapshot(("alpha",))
        alpha = _contribution(root, "alpha")
        relation = snapshot.relations[0]
        bad_target = AuthorityEndpointRef(
            endpoint_kind="parent_closure",
            endpoint_id="purpose:root",
            fingerprint=relation.target.fingerprint,
            owner_route=relation.target.owner_route,
        )
        bad_snapshot = ModelSystemSnapshot(
            **{
                **snapshot.identity_payload(),
                "relations": (
                    ModelRelation(
                        relation_id=relation.relation_id,
                        kind=relation.kind,
                        source=relation.source,
                        target=bad_target,
                        evidence_fingerprints=relation.evidence_fingerprints,
                    ),
                ),
                "coverage": snapshot.coverage,
                "model_instances": snapshot.model_instances,
                "owner_artifact_refs": (bad_target,),
            }
        )

        with pytest.raises(
            ModelAuthorityError,
            match="inexact or fallback purpose relation",
        ):
            derive_effective_intent_owner_bindings(bad_snapshot, (alpha,))


def test_fold_requires_explicit_retain_supersede_and_retire() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        base = _snapshot(("alpha", "beta", "gamma"), snapshot_id="observed-a")
        candidate = _snapshot(
            ("alpha", "beta", "gamma"),
            snapshot_id="observed-b",
            model_sha=SHA_B,
        )
        alpha = _contribution(root, "alpha")
        beta = _contribution(root, "beta")
        gamma = _contribution(root, "gamma")
        base_view = _bootstrap_view(root, base, candidate, (alpha, beta, gamma))
        replacement = _contribution(
            root,
            "beta",
            contribution_id="intent:current-design:beta:v2",
            supersedes=(beta.contribution_id,),
        )
        transitions = (
            EffectiveIntentTransition(
                prior_contribution_id=alpha.contribution_id,
                prior_contribution_fingerprint=alpha.fingerprint,
                action="retain",
                replacement_contribution_ids=(),
                reason="The alpha current design remains exact and unchanged.",
            ),
            EffectiveIntentTransition(
                prior_contribution_id=beta.contribution_id,
                prior_contribution_fingerprint=beta.fingerprint,
                action="supersede",
                replacement_contribution_ids=(replacement.contribution_id,),
                reason="The beta v2 design explicitly replaces the prior beta design.",
            ),
            EffectiveIntentTransition(
                prior_contribution_id=gamma.contribution_id,
                prior_contribution_fingerprint=gamma.fingerprint,
                action="retire",
                replacement_contribution_ids=(),
                reason="The gamma design is explicitly retired from current intent.",
            ),
        )

        folded = fold_effective_intent_contributions(
            base_view,
            (replacement,),
            (_accepted_disposition(replacement),),
            transitions,
        )

        assert tuple(item.contribution_id for item in folded) == (
            alpha.contribution_id,
            replacement.contribution_id,
        )
        with pytest.raises(
            ModelAuthorityError,
            match="every prior active intent requires",
        ):
            fold_effective_intent_contributions(
                base_view,
                (replacement,),
                (_accepted_disposition(replacement),),
                transitions[:-1],
            )


def test_fold_blocks_same_id_changed_content_instead_of_last_write_wins() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        base = _snapshot(("alpha",), snapshot_id="observed-a")
        candidate = _snapshot(
            ("alpha",),
            snapshot_id="observed-b",
            model_sha=SHA_B,
        )
        alpha = _contribution(root, "alpha")
        base_view = _bootstrap_view(root, base, candidate, (alpha,))
        changed = _contribution(
            root,
            "alpha",
            contribution_id=alpha.contribution_id,
            text="A changed design reusing the old id.\n",
        )
        transition = EffectiveIntentTransition(
            prior_contribution_id=alpha.contribution_id,
            prior_contribution_fingerprint=alpha.fingerprint,
            action="retain",
            replacement_contribution_ids=(),
            reason="The old alpha contribution is declared retained for this test.",
        )

        with pytest.raises(
            ModelAuthorityError,
            match="use a new id and explicit supersession",
        ):
            fold_effective_intent_contributions(
                base_view,
                (changed,),
                (_accepted_disposition(changed),),
                (transition,),
            )


def test_bootstrap_receipt_and_view_are_content_addressed_round_trips() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        base = _snapshot(("alpha",), snapshot_id="observed-a")
        candidate = _snapshot(
            ("alpha",),
            snapshot_id="observed-b",
            model_sha=SHA_B,
        )
        alpha = _contribution(root, "alpha")
        view = _bootstrap_view(root, base, candidate, (alpha,))

        assert view.bootstrap_receipt is not None
        assert view.bootstrap_receipt.source_head_generation == 1
        assert not view.bootstrap_receipt.ancestry_revision_set_fingerprints
        assert not view.bootstrap_receipt.legacy_entry_dispositions
        assert view.bootstrap_receipt.current_design_contribution_fingerprints == (
            (alpha.contribution_id, alpha.fingerprint),
        )
        assert EffectiveIntentBootstrapReceipt.from_dict(
            view.bootstrap_receipt.to_dict()
        ) == view.bootstrap_receipt
        assert CurrentEffectiveIntentView.from_dict(view.to_dict()) == view


def test_legacy_bootstrap_dispositions_cover_every_exact_ancestry_row() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        alpha = _contribution(root, "alpha")
        beta = _contribution(root, "beta")
        gamma = _contribution(root, "gamma")
        beta_v2 = _contribution(
            root,
            "beta",
            contribution_id="intent:current-design:beta:v2",
            supersedes=(beta.contribution_id,),
        )
        entries = tuple(
            LegacyIntentAuditEntry(
                generation=2,
                revision_set_fingerprint=SHA_D,
                contribution_id=item.contribution_id,
                contribution_fingerprint=item.fingerprint,
            )
            for item in (alpha, beta, gamma)
        )
        dispositions = (
            LegacyIntentBootstrapDisposition(
                generation=2,
                revision_set_fingerprint=SHA_D,
                contribution_id=alpha.contribution_id,
                contribution_fingerprint=alpha.fingerprint,
                action="retain",
                replacement_contribution_ids=(),
                reason="The exact alpha design remains the current design authority.",
            ),
            LegacyIntentBootstrapDisposition(
                generation=2,
                revision_set_fingerprint=SHA_D,
                contribution_id=beta.contribution_id,
                contribution_fingerprint=beta.fingerprint,
                action="supersede",
                replacement_contribution_ids=(beta_v2.contribution_id,),
                reason="The beta v2 design explicitly replaces this exact legacy row.",
            ),
            LegacyIntentBootstrapDisposition(
                generation=2,
                revision_set_fingerprint=SHA_D,
                contribution_id=gamma.contribution_id,
                contribution_fingerprint=gamma.fingerprint,
                action="retire",
                replacement_contribution_ids=(),
                reason="The gamma design is intentionally absent from current authority.",
            ),
        )

        assert validate_legacy_intent_bootstrap_dispositions(
            entries,
            (alpha, beta_v2),
            dispositions,
        ) == tuple(sorted(dispositions, key=lambda item: item.identity_key))
        with pytest.raises(
            ModelAuthorityError,
            match="inventory must equal the exact ancestry",
        ):
            validate_legacy_intent_bootstrap_dispositions(
                entries,
                (alpha, beta_v2),
                dispositions[:-1],
            )


def test_legacy_bootstrap_rejects_ghost_and_active_relationships() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        ghost_superseder = _contribution(
            root,
            "alpha",
            supersedes=("intent:historical:missing",),
        )
        with pytest.raises(
            ModelAuthorityError,
            match="supersedes an unknown legacy intent id",
        ):
            validate_legacy_intent_bootstrap_dispositions(
                (),
                (ghost_superseder,),
                (),
            )

        ghost_conflict = _contribution(
            root,
            "beta",
            conflicts=("intent:missing:conflict",),
        )
        with pytest.raises(
            ModelAuthorityError,
            match="conflicts with an unknown intent id",
        ):
            validate_legacy_intent_bootstrap_dispositions(
                (),
                (ghost_conflict,),
                (),
            )

        beta = _contribution(root, "beta")
        alpha = _contribution(
            root,
            "alpha",
            conflicts=(beta.contribution_id,),
        )
        with pytest.raises(
            ModelAuthorityError,
            match="unresolved active conflict",
        ):
            validate_legacy_intent_bootstrap_dispositions(
                (),
                (alpha, beta),
                (),
            )


def test_full_sixty_owner_view_round_trips_without_derived_wire_flags() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        model_ids = tuple(f"owner-{index:02d}" for index in range(60))
        base = _snapshot(model_ids, snapshot_id="observed-sixty-base")
        candidate = _snapshot(
            model_ids,
            snapshot_id="observed-sixty-candidate",
            model_sha=SHA_B,
        )
        contributions = tuple(
            _contribution(root, model_id) for model_id in model_ids
        )

        view = _bootstrap_view(root, base, candidate, contributions)
        payload = view.to_dict()

        assert "complete" not in payload
        assert len(payload["active_contributions"]) == 60
        assert len(payload["verified_source_identities"]) == 60
        assert len(payload["owner_bindings"]) == 60
        assert CurrentEffectiveIntentView.from_dict(payload) == view


def test_current_view_rejects_coerced_nested_intent_wire_values() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        base = _snapshot(("alpha",), snapshot_id="observed-wire-base")
        candidate = _snapshot(
            ("alpha",),
            snapshot_id="observed-wire-candidate",
            model_sha=SHA_B,
        )
        view = _bootstrap_view(
            root,
            base,
            candidate,
            (_contribution(root, "alpha"),),
        )
        payload = view.to_dict()
        payload["active_contributions"][0]["source_ref"] = 7

        with pytest.raises(
            ModelAuthorityError,
            match="source_ref must be a JSON string",
        ):
            CurrentEffectiveIntentView.from_dict(payload)
