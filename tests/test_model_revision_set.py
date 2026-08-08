import tempfile
from dataclasses import replace
from pathlib import Path

import pytest

from flowguard.model_authority import (
    REVISION_EVIDENCE_PASS,
    REVISION_EVIDENCE_REQUIRED,
    ModelAuthorityError,
)
from flowguard.model_revision_set import (
    MODEL_REVISION_SET_CURRENT_SCHEMA,
    ModelRollbackContract,
    ModelRollbackEffect,
    ModelRollbackReceipt,
    ModelRevisionSet,
    RevisionEvidenceRef,
    derive_revision_affected_closure,
    derive_revision_snapshot_diff,
)
from tests.test_model_intent_authority import (
    SHA_B,
    SHA_C,
    SHA_D,
    _bootstrap_view,
    _contribution,
    _snapshot,
)
from tests.test_model_maturation import _path_quality


def _accepted_revision(
    root: Path,
    *,
    full_current_path_quality: bool = False,
) -> ModelRevisionSet:
    if full_current_path_quality:
        base = _snapshot(("alpha",), snapshot_id="observed-a")
        candidate = _snapshot(
            ("alpha", "beta"),
            snapshot_id="observed-b",
        )
    else:
        base = _snapshot(("alpha",), snapshot_id="observed-a")
        candidate = _snapshot(
            ("alpha",),
            snapshot_id="observed-b",
            model_sha=SHA_B,
        )
    contributions = tuple(
        _contribution(root, member.logical_model_id)
        for member in candidate.model_instances
    )
    view = _bootstrap_view(root, base, candidate, contributions)
    diff = derive_revision_snapshot_diff(base, candidate)
    candidate_models = {
        item.logical_model_id: item for item in candidate.model_instances
    }
    path_quality_model_ids = (
        tuple(sorted(candidate_models))
        if full_current_path_quality
        else tuple(
            member.member_id
            for member in diff.members
            if member.operation in {"add", "replace"}
        )
    )
    closure = derive_revision_affected_closure(base, candidate, diff)
    path_quality_rows = tuple(
        _path_quality(
            model_id,
            candidate_models[model_id].fingerprint,
            candidate.fingerprint,
        )
        for model_id in path_quality_model_ids
    )
    ids_by_owner: dict[str, list[str]] = {}
    for affected_id, owner_route in closure.owner_bindings:
        ids_by_owner.setdefault(owner_route, []).append(affected_id)
    required = tuple(
        RevisionEvidenceRef(
            receipt_id=f"receipt:revision-set:{index}",
            receipt_fingerprint="sha256:" + f"{index:x}"[-1] * 64,
            owner_route=owner_route,
            subject_fingerprint=candidate.fingerprint,
            obligation_ids=(f"obligation:revision-set:{index}",),
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
        revision_set_id="revision:effective-intent-v5",
        task_id="task:effective-intent-v5",
        expected_head_fingerprint=view.bootstrap_receipt.expected_head_fingerprint,
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
        current_effective_intent_view=view,
        no_declared_intent_rationale_id="no-intent:v5-fixture",
        no_declared_intent_evidence_fingerprints=(
            ("fixture_scope", candidate.fingerprint),
        ),
        no_declared_intent_rationale=(
            "This isolated revision has no additional product intent beyond "
            "testing its direct-current cumulative intent envelope."
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
        (replace(item, status=REVISION_EVIDENCE_PASS) for item in required),
        reason="The exact v5 revision fixture evidence passed.",
    )


def test_v5_revision_round_trip_embeds_one_current_effective_view() -> None:
    with tempfile.TemporaryDirectory() as directory:
        revision = _accepted_revision(Path(directory))

        restored = ModelRevisionSet.from_dict(revision.to_dict())

        assert restored == revision
        assert restored.schema == MODEL_REVISION_SET_CURRENT_SCHEMA
        assert restored.current_effective_intent_view.complete
        assert restored.intent_acceptance_ready
        assert restored.path_quality_acceptance_ready


def test_v5_accepts_full_current_path_quality_superset_for_one_added_model() -> None:
    with tempfile.TemporaryDirectory() as directory:
        revision = _accepted_revision(
            Path(directory),
            full_current_path_quality=True,
        )

        assert tuple(
            (member.member_id, member.operation) for member in revision.members
        ) == (("beta", "add"),)
        assert revision.required_path_quality_model_ids == ("alpha", "beta")
        assert tuple(
            subject.model_id for subject in revision.path_quality_subjects
        ) == ("alpha", "beta")
        assert revision.path_quality_acceptance_ready


def test_v5_full_current_path_quality_rejects_missing_changed_model() -> None:
    with tempfile.TemporaryDirectory() as directory:
        revision = _accepted_revision(
            Path(directory),
            full_current_path_quality=True,
        )
        subjects = {
            subject.model_id: subject
            for subject in revision.path_quality_subjects
        }
        results = {
            result.subject_fingerprint: result
            for result in revision.path_quality_results
        }
        alpha = subjects["alpha"]

        with pytest.raises(
            ModelAuthorityError,
            match="omits added or replaced model members: beta",
        ):
            replace(
                revision,
                required_path_quality_model_ids=(),
                path_quality_subjects=(alpha,),
                path_quality_results=(results[alpha.fingerprint],),
                path_quality_result_set_fingerprint="",
            )


def test_v5_full_current_path_quality_rejects_foreign_model() -> None:
    with tempfile.TemporaryDirectory() as directory:
        revision = _accepted_revision(
            Path(directory),
            full_current_path_quality=True,
        )
        alpha = revision.path_quality_subjects[0]
        beta = revision.path_quality_subjects[1]
        results = {
            result.subject_fingerprint: result
            for result in revision.path_quality_results
        }
        foreign = replace(alpha, model_id="foreign")
        foreign_result = replace(
            results[alpha.fingerprint],
            subject_fingerprint=foreign.fingerprint,
        )

        with pytest.raises(
            ModelAuthorityError,
            match="outside the current candidate intent-owner denominator: foreign",
        ):
            replace(
                revision,
                required_path_quality_model_ids=(),
                path_quality_subjects=(foreign, beta),
                path_quality_results=(
                    foreign_result,
                    results[beta.fingerprint],
                ),
                path_quality_result_set_fingerprint="",
            )


def test_v5_full_current_path_quality_rejects_stale_unchanged_extra() -> None:
    with tempfile.TemporaryDirectory() as directory:
        revision = _accepted_revision(
            Path(directory),
            full_current_path_quality=True,
        )
        alpha = revision.path_quality_subjects[0]
        stale_alpha_result = replace(
            next(
                result
                for result in revision.path_quality_results
                if result.subject_fingerprint == alpha.fingerprint
            ),
            current=False,
        )
        current_beta_result = next(
            result
            for result in revision.path_quality_results
            if result.subject_fingerprint
            == revision.path_quality_subjects[1].fingerprint
        )

        with pytest.raises(
            ModelAuthorityError,
            match="result is not current for its exact candidate subject: alpha",
        ):
            replace(
                revision,
                required_path_quality_model_ids=(),
                path_quality_results=(stale_alpha_result, current_beta_result),
                path_quality_result_set_fingerprint="",
            )


def test_v5_revision_rejects_missing_effective_view() -> None:
    with tempfile.TemporaryDirectory() as directory:
        revision = _accepted_revision(Path(directory))

        with pytest.raises(
            ModelAuthorityError,
            match="requires one typed current effective intent view",
        ):
            replace(
                revision,
                current_effective_intent_view=None,
            )


def test_v5_acceptance_blocks_missing_or_unresolved_path_quality() -> None:
    with tempfile.TemporaryDirectory() as directory:
        accepted = _accepted_revision(Path(directory))
        proposed = replace(
            accepted,
            completed_evidence_refs=(),
            path_quality_subjects=(),
            path_quality_results=(),
            path_quality_result_set_fingerprint="",
            status="proposed",
            decision_reason="",
        )
        assert not proposed.path_quality_acceptance_ready
        with pytest.raises(
            ModelAuthorityError,
            match="path-quality closure",
        ):
            proposed.accept(
                (
                    replace(item, status=REVISION_EVIDENCE_PASS)
                    for item in proposed.required_evidence_refs
                ),
                reason="Evidence alone cannot manufacture model path quality.",
            )

        subject = accepted.path_quality_subjects[0]
        unresolved = replace(
            accepted.path_quality_results[0],
            conclusion="unresolved",
            unresolved_ids=("missing_necessity_witness",),
        )
        unresolved_proposed = replace(
            accepted,
            completed_evidence_refs=(),
            path_quality_results=(unresolved,),
            path_quality_result_set_fingerprint="",
            status="proposed",
            decision_reason="",
        )
        assert unresolved_proposed.path_quality_subjects == (subject,)
        assert not unresolved_proposed.path_quality_acceptance_ready


def test_v5_revision_rejects_stale_path_quality_subject_and_wire_omission() -> None:
    with tempfile.TemporaryDirectory() as directory:
        revision = _accepted_revision(Path(directory))
        stale_subject = replace(
            revision.path_quality_subjects[0],
            currentness_id="snapshot:stale",
        )
        with pytest.raises(
            ModelAuthorityError,
            match="currentness must equal the candidate snapshot",
        ):
            replace(
                revision,
                path_quality_subjects=(stale_subject,),
                path_quality_result_set_fingerprint="",
            )

        payload = revision.to_dict()
        payload.pop("path_quality_results")
        with pytest.raises(ModelAuthorityError, match="missing fields"):
            ModelRevisionSet.from_dict(payload)


def test_normal_loader_rejects_v4_before_interpreting_legacy_fields() -> None:
    with tempfile.TemporaryDirectory() as directory:
        revision = _accepted_revision(Path(directory))
        payload = revision.to_dict()
        payload["schema"] = "flowguard.model_revision_set.v4"
        payload.pop("current_effective_intent_view")

        with pytest.raises(
            ModelAuthorityError,
            match=(
                "schema must be flowguard.model_revision_set.v5; legacy current "
                "authority requires explicit intent bootstrap migration"
            ),
        ):
            ModelRevisionSet.from_dict(payload)


def test_v5_wire_omits_derived_acceptance_flags_and_rejects_reinsertion() -> None:
    with tempfile.TemporaryDirectory() as directory:
        revision = _accepted_revision(Path(directory))
        payload = revision.to_dict()

        assert "evidence_complete" not in payload
        assert "intent_acceptance_ready" not in payload
        payload["evidence_complete"] = False
        with pytest.raises(ModelAuthorityError, match="unknown fields"):
            ModelRevisionSet.from_dict(payload)


def test_revision_and_rollback_wire_types_are_not_coerced() -> None:
    with tempfile.TemporaryDirectory() as directory:
        revision = _accepted_revision(Path(directory))
        payload = revision.to_dict()
        payload["required_evidence_refs"][0]["current"] = "false"
        with pytest.raises(
            ModelAuthorityError,
            match="current must be a JSON boolean",
        ):
            ModelRevisionSet.from_dict(payload)

    effect = ModelRollbackEffect(
        effect_id="effect:wire",
        kind="filesystem",
        disposition="restore",
        required_evidence_fingerprints=(SHA_B,),
    )
    contract = ModelRollbackContract(
        contract_id="rollback:wire",
        expected_head_fingerprint=SHA_B,
        originating_revision_set_fingerprint=SHA_C,
        originating_activation_receipt_fingerprint=SHA_D,
        from_snapshot_fingerprint=SHA_C,
        to_snapshot_fingerprint=SHA_D,
        effects=(effect,),
        old_snapshot_conformance_evidence_fingerprints=(SHA_C,),
    )
    contract_payload = contract.to_dict()
    contract_payload["exact_rollback_possible"] = "true"
    with pytest.raises(
        ModelAuthorityError,
        match="exact_rollback_possible must be a JSON boolean",
    ):
        ModelRollbackContract.from_dict(contract_payload)

    receipt = ModelRollbackReceipt(
        receipt_id="rollback-receipt:wire",
        contract_fingerprint=contract.fingerprint,
        reverse_revision_set_fingerprint=SHA_B,
        result="exact",
        completed_evidence_fingerprints=contract.required_evidence_fingerprints,
        reason="The exact rollback wire fixture completed its evidence set.",
    )
    receipt_payload = receipt.to_dict()
    receipt_payload["reason"] = 5
    with pytest.raises(
        ModelAuthorityError,
        match="rollback reason must be a JSON string",
    ):
        ModelRollbackReceipt.from_dict(receipt_payload)
