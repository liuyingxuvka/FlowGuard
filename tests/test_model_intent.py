from __future__ import annotations

from dataclasses import replace
import unittest

from flowguard.model_authority import (
    ModelAuthorityError,
    ModelRevisionSet,
    RevisionEvidenceRef,
    RevisionMemberChange,
    canonical_fingerprint,
    derive_affected_closure_fingerprint,
)
from flowguard.model_intent import (
    ModelIntentContribution,
    ModelIntentDisposition,
    ModelIntentReview,
    model_intent_inventory_fingerprint,
    review_model_intent_inventory,
)


SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
SHA_D = "sha256:" + "d" * 64
SHA_E = "sha256:" + "e" * 64
SHA_F = "sha256:" + "f" * 64


def contribution(
    contribution_id: str,
    *,
    source_kind: str = "requirement",
    decision_state: str = "accepted",
    logical_model_id: str = "model:planner",
    unresolved_owner_id: str = "",
    supersedes: tuple[str, ...] = (),
    conflicts_with: tuple[str, ...] = (),
) -> ModelIntentContribution:
    return ModelIntentContribution(
        contribution_id=contribution_id,
        source_kind=source_kind,
        source_ref=f"docs/{contribution_id}.md",
        source_fingerprint=canonical_fingerprint(
            {"source": contribution_id}
        ),
        subject_lane="normative_target",
        subject_role="requirement",
        lifecycle_state="candidate",
        decision_state=decision_state,
        logical_model_id=logical_model_id,
        unresolved_owner_id=unresolved_owner_id,
        supersedes_contribution_ids=supersedes,
        conflicts_with_contribution_ids=conflicts_with,
        target_obligation_ids=("obligation:planner",),
        target_state_ids=(),
        target_transition_ids=(),
        target_invariant_ids=(),
        target_relation_ids=(),
        desired_terminal_state_ids=(),
        target_output_ids=(),
        declared_consumer_ids=(),
        effective_revision="candidate:planner-v2",
        rationale=(
            "This contribution states the exact planner behavior expected "
            "from the candidate revision."
        ),
    )


def disposition(
    item: ModelIntentContribution,
    state: str,
    *,
    changed_obligation_ids: tuple[str, ...] = (),
    scoped_gap_ids: tuple[str, ...] = (),
    conflict_ids: tuple[str, ...] = (),
    unresolved_effect_ids: tuple[str, ...] = (),
    unreachable_terminal_state_ids: tuple[str, ...] = (),
    unconsumed_output_ids: tuple[str, ...] = (),
) -> ModelIntentDisposition:
    return ModelIntentDisposition(
        contribution_id=item.contribution_id,
        contribution_fingerprint=item.fingerprint,
        disposition=state,
        changed_obligation_ids=changed_obligation_ids,
        changed_state_ids=(),
        changed_transition_ids=(),
        changed_invariant_ids=(),
        changed_relation_ids=(),
        scoped_gap_ids=scoped_gap_ids,
        conflict_ids=conflict_ids,
        unresolved_effect_ids=unresolved_effect_ids,
        unreachable_terminal_state_ids=unreachable_terminal_state_ids,
        unconsumed_output_ids=unconsumed_output_ids,
        reason=(
            "The revision owner records the exact current disposition and "
            "its modeled effect."
        ),
    )


def proposed_revision(
    contributions: tuple[ModelIntentContribution, ...],
    dispositions: tuple[ModelIntentDisposition, ...],
) -> tuple[ModelRevisionSet, RevisionEvidenceRef]:
    affected_ids = ("obligation:planner",)
    owner_bindings = (
        ("obligation:planner", "model_test_alignment"),
    )
    closure_fingerprint = derive_affected_closure_fingerprint(
        affected_closure_ids=affected_ids,
        affected_edge_ids=(),
        affected_owner_bindings=owner_bindings,
    )
    required = RevisionEvidenceRef(
        receipt_id="receipt:intent",
        receipt_fingerprint=SHA_C,
        owner_route="model_test_alignment",
        subject_fingerprint=SHA_B,
        obligation_ids=("obligation:intent",),
        affected_closure_fingerprint=closure_fingerprint,
        covered_affected_ids=affected_ids,
        candidate_snapshot_fingerprint=SHA_B,
        toolchain_fingerprint=SHA_D,
        environment_fingerprint=SHA_E,
        status="required",
        current=True,
        eligible=True,
    )
    revision = ModelRevisionSet(
        revision_set_id="revision:intent",
        task_id="task:intent",
        expected_head_fingerprint=SHA_F,
        base_snapshot_fingerprint=SHA_A,
        candidate_snapshot_fingerprint=SHA_B,
        members=(
            RevisionMemberChange(
                member_id="planner",
                operation="replace",
                base_instance_fingerprint=SHA_A,
                candidate_instance_fingerprint=SHA_B,
                changed_element_ids=affected_ids,
            ),
        ),
        affected_closure_ids=affected_ids,
        affected_closure_fingerprint=closure_fingerprint,
        affected_edge_ids=(),
        affected_owner_bindings=owner_bindings,
        snapshot_diff_fingerprint=SHA_F,
        required_evidence_refs=(required,),
        intent_contributions=contributions,
        intent_dispositions=dispositions,
    )
    return revision, required


class ModelIntentTests(unittest.TestCase):
    def test_contribution_is_content_addressed_and_strict_current(self) -> None:
        item = contribution("intent:requirement")

        self.assertEqual(item, ModelIntentContribution.from_dict(item.to_dict()))
        changed = replace(item, source_fingerprint=SHA_A)
        self.assertNotEqual(item.fingerprint, changed.fingerprint)
        payload = item.to_dict()
        payload["legacy_alias"] = "forbidden"
        with self.assertRaises(ModelAuthorityError):
            ModelIntentContribution.from_dict(payload)

    def test_contribution_requires_one_logical_model_or_unresolved_owner(self) -> None:
        with self.assertRaisesRegex(ModelAuthorityError, "logical model"):
            contribution(
                "intent:no-owner",
                logical_model_id="",
                unresolved_owner_id="",
            )
        with self.assertRaisesRegex(ModelAuthorityError, "logical model"):
            contribution(
                "intent:two-owners",
                logical_model_id="model:planner",
                unresolved_owner_id="owner:unknown",
            )

    def test_supersession_keeps_both_identities_and_only_new_intent_active(self) -> None:
        older = contribution("intent:spark", source_kind="spark")
        newer = contribution(
            "intent:user-decision",
            source_kind="user_decision",
            supersedes=(older.contribution_id,),
        )
        rows = (
            disposition(older, "superseded"),
            disposition(
                newer,
                "accepted",
                changed_obligation_ids=("obligation:planner",),
            ),
        )

        report = review_model_intent_inventory((older, newer), rows)

        self.assertTrue(report.ok, report.to_dict())
        self.assertEqual(report, ModelIntentReview.from_dict(report.to_dict()))
        self.assertEqual((newer.contribution_id,), report.accepted_contribution_ids)
        self.assertEqual(
            model_intent_inventory_fingerprint((older, newer), rows),
            report.inventory_fingerprint,
        )

    def test_missing_supersession_and_active_conflict_are_explicit(self) -> None:
        older = contribution("intent:older")
        newer = contribution(
            "intent:newer",
            conflicts_with=(older.contribution_id,),
        )
        report = review_model_intent_inventory(
            (older, newer),
            (
                disposition(
                    older,
                    "superseded",
                ),
                disposition(
                    newer,
                    "accepted",
                    changed_obligation_ids=("obligation:planner",),
                ),
            ),
        )
        self.assertIn(
            "intent_superseded_without_replacement",
            report.finding_codes,
        )

        active_conflict = review_model_intent_inventory(
            (older, newer),
            (
                disposition(
                    older,
                    "accepted",
                    changed_obligation_ids=("obligation:planner",),
                ),
                disposition(
                    newer,
                    "accepted",
                    changed_obligation_ids=("obligation:planner",),
                ),
            ),
        )
        self.assertIn("intent_active_conflict", active_conflict.finding_codes)
        self.assertTrue(active_conflict.conflict_ids)

    def test_rejected_and_deferred_remain_traceable_but_unresolved_blocks(self) -> None:
        rejected = contribution("intent:rejected", decision_state="rejected")
        deferred = contribution("intent:deferred", decision_state="deferred")
        unresolved = contribution(
            "intent:unresolved",
            decision_state="unresolved",
            logical_model_id="",
            unresolved_owner_id="owner:requirements",
        )
        report = review_model_intent_inventory(
            (rejected, deferred, unresolved),
            (
                disposition(rejected, "rejected"),
                disposition(deferred, "deferred"),
                disposition(unresolved, "unresolved"),
            ),
        )

        self.assertEqual(
            ("intent:deferred", "intent:rejected", "intent:unresolved"),
            tuple(item.contribution_id for item in report.dispositions),
        )
        self.assertIn("intent_disposition_unresolved", report.finding_codes)

    def test_hazards_on_rejected_contribution_do_not_become_active_effects(self) -> None:
        item = contribution("intent:declined", decision_state="rejected")
        row = disposition(
            item,
            "rejected",
            conflict_ids=("conflict:declined",),
            unresolved_effect_ids=("effect:declined",),
            unreachable_terminal_state_ids=("state:declined",),
            unconsumed_output_ids=("output:declined",),
        )

        report = review_model_intent_inventory((item,), (row,))

        self.assertTrue(report.ok, report.to_dict())
        self.assertEqual((), report.conflict_ids)
        self.assertEqual((), report.unresolved_ids)

    def test_revision_accepts_only_connected_exact_inventory(self) -> None:
        item = contribution("intent:connected")
        row = disposition(
            item,
            "accepted",
            changed_obligation_ids=("obligation:planner",),
        )
        revision, required = proposed_revision((item,), (row,))

        accepted = revision.accept(
            (replace(required, status="pass"),),
            reason="The exact intent and evidence closures are complete.",
        )

        self.assertTrue(accepted.intent_acceptance_ready)
        self.assertEqual(
            model_intent_inventory_fingerprint((item,), (row,)),
            accepted.intent_contribution_inventory_fingerprint,
        )
        self.assertEqual(
            accepted,
            ModelRevisionSet.from_dict(accepted.to_dict()),
        )
        legacy = accepted.to_dict()
        legacy["schema"] = "flowguard.model_revision_set.v2"
        with self.assertRaises(ModelAuthorityError):
            ModelRevisionSet.from_dict(legacy)

    def test_revision_blocks_disconnected_or_unknown_accepted_effect(self) -> None:
        item = contribution("intent:disconnected")
        for row, code in (
            (
                disposition(item, "accepted"),
                "intent_contribution_disconnected",
            ),
            (
                disposition(
                    item,
                    "accepted",
                    changed_obligation_ids=("obligation:not-changed",),
                ),
                "intent_changed_target_unknown",
            ),
        ):
            revision, required = proposed_revision((item,), (row,))
            self.assertIn(code, revision.intent_review.finding_codes)
            with self.assertRaisesRegex(ModelAuthorityError, "intent"):
                revision.accept(
                    (replace(required, status="pass"),),
                    reason="Evidence alone cannot close disconnected intent.",
                )

    def test_nontrivial_revision_requires_intent_or_evidence_bound_no_intent(self) -> None:
        revision, required = proposed_revision((), ())
        completed = (replace(required, status="pass"),)

        with self.assertRaisesRegex(ModelAuthorityError, "intent"):
            revision.accept(
                completed,
                reason="Evidence without intent lineage is not enough.",
            )

        no_intent = replace(
            revision,
            no_declared_intent_rationale_id="no-intent:isolated-fixture",
            no_declared_intent_evidence_fingerprints=(("fixture_scope", SHA_A),),
            no_declared_intent_rationale=(
                "The exact isolated fixture declares no external product intent."
            ),
        )
        accepted = no_intent.accept(
            completed,
            reason="The exact evidence-bound no-intent scope is complete.",
        )
        self.assertTrue(accepted.intent_acceptance_ready)
        self.assertEqual(accepted, ModelRevisionSet.from_dict(accepted.to_dict()))

    def test_no_intent_rationale_is_complete_and_exclusive(self) -> None:
        revision, _required = proposed_revision((), ())
        with self.assertRaisesRegex(ModelAuthorityError, "requires identity"):
            replace(
                revision,
                no_declared_intent_rationale_id="no-intent:partial",
            )

        item = contribution("intent:exclusive")
        row = disposition(
            item,
            "accepted",
            changed_obligation_ids=("obligation:planner",),
        )
        with_intent, _required = proposed_revision((item,), (row,))
        with self.assertRaisesRegex(ModelAuthorityError, "exclusive"):
            replace(
                with_intent,
                no_declared_intent_rationale_id="no-intent:conflict",
                no_declared_intent_evidence_fingerprints=(
                    ("fixture_scope", SHA_A),
                ),
                no_declared_intent_rationale=(
                    "An intent-bearing revision cannot also claim no intent."
                ),
            )

    def test_revision_blocks_conflict_unreachable_terminal_and_unconsumed_output(self) -> None:
        item = contribution("intent:hazard")
        row = disposition(
            item,
            "accepted",
            changed_obligation_ids=("obligation:planner",),
            conflict_ids=("conflict:invariant",),
            unreachable_terminal_state_ids=("state:done",),
            unconsumed_output_ids=("output:plan",),
        )
        revision, required = proposed_revision((item,), (row,))

        self.assertEqual(("conflict:invariant",), revision.intent_conflict_ids)
        self.assertIn("intent_terminal_unreachable", revision.intent_review.finding_codes)
        self.assertIn("intent_output_without_consumer", revision.intent_review.finding_codes)
        with self.assertRaisesRegex(ModelAuthorityError, "intent"):
            revision.accept(
                (replace(required, status="pass"),),
                reason="Unrelated evidence cannot close intent hazards.",
            )


if __name__ == "__main__":
    unittest.main()
