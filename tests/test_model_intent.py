from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import subprocess
import tempfile
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
    verify_model_intent_sources,
)
from flowguard.source_identity import source_file_fingerprint
from flowguard.work_context import read_project_work_contexts
from tests.test_model_maturation import _path_quality
from tests.test_model_authority import detached_current_intent_view


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
    source_ref: str | None = None,
    source_fingerprint: str | None = None,
    work_context_id: str = "",
    work_context_fingerprint: str = "",
    native_owner_id: str = "",
) -> ModelIntentContribution:
    return ModelIntentContribution(
        contribution_id=contribution_id,
        source_kind=source_kind,
        source_ref=(
            f"docs/{contribution_id}.md"
            if source_ref is None
            else source_ref
        ),
        source_fingerprint=(
            canonical_fingerprint({"source": contribution_id})
            if source_fingerprint is None
            else source_fingerprint
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
        work_context_id=work_context_id,
        work_context_fingerprint=work_context_fingerprint,
        native_owner_id=native_owner_id,
    )


def disposition(
    item: ModelIntentContribution,
    state: str,
    *,
    changed_obligation_ids: tuple[str, ...] = (),
    changed_state_ids: tuple[str, ...] = (),
    changed_relation_ids: tuple[str, ...] = (),
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
        changed_state_ids=changed_state_ids,
        changed_transition_ids=(),
        changed_invariant_ids=(),
        changed_relation_ids=changed_relation_ids,
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
    *,
    affected_ids: tuple[str, ...] = ("obligation:planner",),
    member_changed_ids: tuple[str, ...] | None = None,
    changed_root_ids: tuple[str, ...] = (),
    changed_relation_ids: tuple[str, ...] = (),
    changed_test_ids: tuple[str, ...] = (),
    changed_system_property_ids: tuple[str, ...] = (),
    changed_coverage_ids: tuple[str, ...] = (),
    added_ids: tuple[str, ...] = (),
    fingerprint_changed_ids: tuple[str, ...] = (),
) -> tuple[ModelRevisionSet, RevisionEvidenceRef]:
    owner_bindings = tuple(
        (affected_id, "model_test_alignment")
        for affected_id in affected_ids
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
    path_subject, path_result = _path_quality("planner", SHA_B, SHA_B)
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
                changed_element_ids=(
                    affected_ids
                    if member_changed_ids is None
                    else member_changed_ids
                ),
            ),
        ),
        affected_closure_ids=affected_ids,
        affected_closure_fingerprint=closure_fingerprint,
        affected_edge_ids=(),
        affected_owner_bindings=owner_bindings,
        snapshot_diff_fingerprint=SHA_F,
        changed_root_ids=changed_root_ids,
        changed_relation_ids=changed_relation_ids,
        changed_test_ids=changed_test_ids,
        changed_system_property_ids=changed_system_property_ids,
        changed_coverage_ids=changed_coverage_ids,
        added_ids=added_ids,
        fingerprint_changed_ids=fingerprint_changed_ids,
        required_evidence_refs=(required,),
        required_path_quality_model_ids=("planner",),
        path_quality_subjects=(path_subject,),
        path_quality_results=(path_result,),
        intent_contributions=contributions,
        intent_dispositions=dispositions,
        current_effective_intent_view=detached_current_intent_view(
            SHA_B,
            "planner",
        ),
    )
    return revision, required


class ModelIntentTests(unittest.TestCase):
    @staticmethod
    def _write_declared_work_context(root: Path) -> Path:
        source = root / "docs" / "planner" / "requirement.md"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"Planner requirement.\r\n")
        manifest = root / ".flowguard" / "project.toml"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(
            """
[[work_context.sources]]
source_id = "planner-source"
adapter_id = "declared-files"
native_work_id = "planner"
native_owner_id = "planner-owner"
context_root = "docs/planner"
required = true
required_artifact_roles = ["requirement"]
native_metadata = { status = "provider-pass" }

[[work_context.sources.artifacts]]
artifact_id = "planner:requirement"
path = "requirement.md"
artifact_role = "requirement"
""".strip()
            + "\n",
            encoding="utf-8",
        )
        return source

    def test_direct_intent_source_is_current_bounded_and_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            outer = Path(directory)
            root = outer / "project"
            source = root / "docs" / "intent.md"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"Current requirement.\r\n")
            current = contribution(
                "intent:current-source",
                source_ref="docs/intent.md",
                source_fingerprint=source_file_fingerprint(source),
            )

            frozen = verify_model_intent_sources(root, (current,))

            self.assertEqual(1, len(frozen))
            self.assertEqual("project_file", frozen[0].authority_kind)
            self.assertEqual("docs/intent.md", frozen[0].resolved_project_ref)

            source.write_text("Changed requirement.\n", encoding="utf-8")
            with self.assertRaisesRegex(ModelAuthorityError, "fingerprint is stale"):
                verify_model_intent_sources(root, (current,))

            missing = replace(current, source_ref="docs/missing.md")
            with self.assertRaisesRegex(ModelAuthorityError, "missing"):
                verify_model_intent_sources(root, (missing,))

            absolute = replace(current, source_ref=str(source.resolve()))
            with self.assertRaisesRegex(ModelAuthorityError, "relative project path"):
                verify_model_intent_sources(root, (absolute,))

            outside = outer / "outside.md"
            outside.write_text("outside\n", encoding="utf-8")
            escaping = replace(
                current,
                source_ref="../outside.md",
                source_fingerprint=source_file_fingerprint(outside),
            )
            with self.assertRaisesRegex(ModelAuthorityError, "escapes project root"):
                verify_model_intent_sources(root, (escaping,))

            directory_source = root / "docs" / "directory"
            directory_source.mkdir()
            nonregular = replace(current, source_ref="docs/directory")
            with self.assertRaisesRegex(ModelAuthorityError, "regular file"):
                verify_model_intent_sources(root, (nonregular,))

    def test_direct_intent_source_rejects_external_link(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            outer = Path(directory)
            root = outer / "project"
            target_dir = outer / "external"
            target_dir.mkdir()
            target = target_dir / "external.md"
            target.write_text("external\n", encoding="utf-8")
            linked = root / "docs" / "linked.md"
            linked.parent.mkdir(parents=True)
            try:
                os.symlink(target, linked)
            except (NotImplementedError, OSError) as exc:
                if os.name != "nt":
                    self.skipTest(f"external-link creation unavailable: {exc}")
                linked_dir = root / "docs" / "linked-external"
                completed = subprocess.run(
                    [
                        "cmd",
                        "/c",
                        "mklink",
                        "/J",
                        str(linked_dir),
                        str(target_dir),
                    ],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if completed.returncode != 0:
                    self.skipTest(
                        "external link and junction creation unavailable: "
                        f"{exc}; {completed.stderr or completed.stdout}"
                    )
                linked = linked_dir / target.name
            item = contribution(
                "intent:external-link",
                source_ref=linked.relative_to(root).as_posix(),
                source_fingerprint=source_file_fingerprint(target),
            )

            with self.assertRaisesRegex(ModelAuthorityError, "external link"):
                verify_model_intent_sources(root, (item,))

    def test_work_context_intent_source_requires_exact_current_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._write_declared_work_context(root)
            review = read_project_work_contexts(root)
            self.assertTrue(review.ok, review.to_dict())
            context = review.contexts[0]
            artifact = context.artifacts[0]
            item = contribution(
                "intent:work-context",
                source_ref=artifact.source_ref,
                source_fingerprint=artifact.content_fingerprint,
                work_context_id=context.context_id,
                work_context_fingerprint=context.context_fingerprint,
                native_owner_id=context.native_owner_id,
            )

            frozen = verify_model_intent_sources(root, (item,))

            self.assertEqual("work_context", frozen[0].authority_kind)
            self.assertEqual(artifact.artifact_id, frozen[0].work_context_artifact_id)

            stale_context = replace(item, work_context_fingerprint=SHA_A)
            with self.assertRaisesRegex(ModelAuthorityError, "fingerprint.*stale"):
                verify_model_intent_sources(root, (stale_context,))

            foreign_context = replace(item, work_context_id="context:foreign")
            with self.assertRaisesRegex(ModelAuthorityError, "not declared"):
                verify_model_intent_sources(root, (foreign_context,))

            foreign_owner = replace(item, native_owner_id="foreign-owner")
            with self.assertRaisesRegex(ModelAuthorityError, "native owner"):
                verify_model_intent_sources(root, (foreign_owner,))

            # CRLF makes the direct canonical file identity intentionally differ
            # from the WorkContext artifact's raw-byte identity.  Complete
            # WorkContext provenance must stay on the WorkContext branch.
            wrong_identity_scheme = replace(
                item,
                source_fingerprint=source_file_fingerprint(source),
            )
            self.assertNotEqual(
                artifact.content_fingerprint,
                wrong_identity_scheme.source_fingerprint,
            )
            with self.assertRaisesRegex(ModelAuthorityError, "artifact fingerprint"):
                verify_model_intent_sources(root, (wrong_identity_scheme,))

            source.write_text("Changed provider material.\n", encoding="utf-8")
            with self.assertRaisesRegex(ModelAuthorityError, "stale"):
                verify_model_intent_sources(root, (item,))

    def test_work_context_intent_source_rejects_undeclared_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.mkdir(exist_ok=True)
            item = contribution(
                "intent:undeclared-context",
                source_ref="provider/requirement.md",
                source_fingerprint=SHA_A,
                work_context_id="context:missing",
                work_context_fingerprint=SHA_B,
                native_owner_id="provider-owner",
            )

            with self.assertRaisesRegex(
                ModelAuthorityError,
                "WorkContext declarations are invalid",
            ):
                verify_model_intent_sources(root, (item,))

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

    def test_changed_target_coverage_is_complete_strict_and_union_based(self) -> None:
        requirement = contribution("intent:requirement")
        design = contribution("intent:design", source_kind="design")
        requirement_row = disposition(
            requirement,
            "accepted",
            changed_obligation_ids=("obligation:planner",),
        )
        design_row = disposition(
            design,
            "accepted",
            changed_state_ids=("state:planner-ready",),
        )

        incomplete = review_model_intent_inventory(
            (requirement, design),
            (requirement_row, replace(design_row, changed_state_ids=())),
            changed_model_ids=(
                "obligation:planner",
                "state:planner-ready",
            ),
            enforce_changed_targets=True,
        )

        self.assertIn(
            "intent_changed_target_unmapped",
            incomplete.finding_codes,
        )
        self.assertIn("state:planner-ready", incomplete.unresolved_ids)
        self.assertEqual(
            incomplete,
            ModelIntentReview.from_dict(incomplete.to_dict()),
        )

        complete = review_model_intent_inventory(
            (requirement, design),
            (requirement_row, design_row),
            changed_model_ids=(
                "obligation:planner",
                "state:planner-ready",
            ),
            enforce_changed_targets=True,
        )
        self.assertTrue(complete.ok, complete.to_dict())
        self.assertEqual(
            complete,
            ModelIntentReview.from_dict(complete.to_dict()),
        )

    def test_revision_acceptance_blocks_unmapped_change_and_accepts_union(self) -> None:
        requirement = contribution("intent:requirement")
        design = contribution("intent:design", source_kind="design")
        requirement_row = disposition(
            requirement,
            "accepted",
            changed_obligation_ids=("obligation:planner",),
        )
        design_row = disposition(
            design,
            "accepted",
            changed_state_ids=("state:planner-ready",),
        )
        affected_ids = ("obligation:planner", "state:planner-ready")

        incomplete, required = proposed_revision(
            (requirement, design),
            (requirement_row, replace(design_row, changed_state_ids=())),
            affected_ids=affected_ids,
        )
        self.assertIn(
            "intent_changed_target_unmapped",
            incomplete.intent_review.finding_codes,
        )
        with self.assertRaisesRegex(ModelAuthorityError, "intent"):
            incomplete.accept(
                (replace(required, status="pass"),),
                reason="Evidence cannot close an unmapped revision change.",
            )

        complete, required = proposed_revision(
            (requirement, design),
            (requirement_row, design_row),
            affected_ids=affected_ids,
        )
        accepted = complete.accept(
            (replace(required, status="pass"),),
            reason="Every exact revision change has accepted intent coverage.",
        )
        self.assertTrue(accepted.intent_acceptance_ready)
        self.assertEqual(
            accepted,
            ModelRevisionSet.from_dict(accepted.to_dict()),
        )

    def test_revision_intent_coverage_uses_raw_semantics_not_diff_wrappers(self) -> None:
        requirement = contribution("intent:production-requirement")
        design = contribution(
            "intent:production-design",
            source_kind="design",
        )
        requirement_row = disposition(
            requirement,
            "accepted",
            changed_obligation_ids=("obligation:planner",),
            changed_state_ids=("state:planner-ready",),
        )
        design_row = disposition(
            design,
            "accepted",
            changed_relation_ids=(
                "relation:planner-to-test",
                "relation:test-to-release",
            ),
        )
        semantic_ids = (
            "obligation:planner",
            "relation:planner-to-test",
            "relation:test-to-release",
            "state:planner-ready",
        )
        production_shape = {
            "affected_ids": semantic_ids,
            "member_changed_ids": (
                "model_instance:model:planner",
                "obligation:planner",
                "state:planner-ready",
                "coverage:model:planner",
                "fingerprint:model:planner",
            ),
            "changed_root_ids": (
                "root:model-system",
                "system:model-system",
            ),
            "changed_relation_ids": (
                "model_relation:planner-to-test",
                "relation:planner-to-test",
                "relation:test-to-release",
            ),
            "changed_test_ids": ("test:planner",),
            "changed_system_property_ids": ("system_property:planner",),
            "changed_coverage_ids": ("coverage:planner",),
            "added_ids": ("model_instance:model:planner:new",),
            "fingerprint_changed_ids": ("fingerprint:model:planner",),
        }

        complete, required = proposed_revision(
            (requirement, design),
            (requirement_row, design_row),
            **production_shape,
        )
        self.assertEqual(semantic_ids, complete.intent_review.changed_model_ids)
        self.assertNotIn(
            "intent_changed_target_unmapped",
            complete.intent_review.finding_codes,
        )
        accepted = complete.accept(
            (replace(required, status="pass"),),
            reason="Every raw semantic change has accepted intent coverage.",
        )
        self.assertTrue(accepted.intent_acceptance_ready)

        incomplete, required = proposed_revision(
            (requirement, design),
            (
                requirement_row,
                replace(
                    design_row,
                    changed_relation_ids=("relation:planner-to-test",),
                ),
            ),
            **production_shape,
        )
        self.assertIn(
            "intent_changed_target_unmapped",
            incomplete.intent_review.finding_codes,
        )
        self.assertIn(
            "relation:test-to-release",
            incomplete.intent_review.unresolved_ids,
        )
        with self.assertRaisesRegex(ModelAuthorityError, "intent"):
            incomplete.accept(
                (replace(required, status="pass"),),
                reason="Wrapper freshness cannot hide one unmapped relation.",
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
