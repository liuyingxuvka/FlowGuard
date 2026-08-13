import json
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from flowguard.__main__ import _load_native_owner_evidence, main
from flowguard.evidence_receipts import (
    RECEIPT_STATUS_PASS,
    ReceiptVerificationResult,
    build_environment_fingerprint,
    fingerprint_value,
    receipt_path,
    save_evidence_receipt,
)
from flowguard.model_authority import ModelRevisionSet
from flowguard.model_authority_store import (
    bootstrap_model_authority,
    load_observed_model_system,
)
from flowguard.model_intent import ModelIntentContribution
from flowguard.model_intent_authority import (
    build_current_intent_bootstrap_receipt,
)
from flowguard.model_purpose import build_model_purpose_closure, file_fingerprint
from flowguard.model_regressions import MANIFEST_SCHEMA, run_manifest_regressions
from flowguard.model_revision_builder import build_current_model_revision
from flowguard.model_revision_owner_evidence import (
    NATIVE_OWNER_BINDINGS_RELATIVE_PATH,
    NATIVE_OWNER_BINDINGS_SCHEMA,
    NativeOwnerModelBinding,
    NativeOwnerModelEvidencePlan,
    produce_model_revision_owner_evidence,
)
import flowguard.model_revision_owner_evidence as owner_evidence_module
from flowguard.model_revision_set import (
    derive_revision_affected_closure,
    derive_revision_snapshot_diff,
)
from flowguard.model_system_inventory import build_manifest_model_system_snapshot
from flowguard.source_identity import source_file_fingerprint
from flowguard.validation_ownership import _content_addressed_receipt_id
from tests.test_model_maturation import _path_quality


_MODEL_IDS = (
    "behavior_commitment_ledger",
    "default_replacement_field_lifecycle",
    "hierarchical_model_mesh",
    "model_test_code_alignment",
    "test_evidence_mesh",
)


class ModelRevisionOwnerEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / ".flowguard").mkdir(parents=True)
        self._write_models(1)
        base = build_manifest_model_system_snapshot(
            self.root,
            snapshot_id="observed-owner-evidence-base",
        )
        bootstrap_model_authority(
            self.root,
            base,
            bootstrap_evidence_fingerprint="sha256:" + "a" * 64,
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _write_models(
        self,
        value: int,
        *,
        root: Path | None = None,
        model_ids: tuple[str, ...] = _MODEL_IDS,
    ) -> None:
        target_root = root or self.root
        current_design = target_root / "docs" / "current-design.md"
        current_design.parent.mkdir(parents=True, exist_ok=True)
        if not current_design.exists():
            current_design.write_text(
                "The owner-evidence fixture keeps one current design source.\n",
                encoding="utf-8",
            )
        entries = []
        for model_id in model_ids:
            model_dir = target_root / ".flowguard" / model_id
            model_dir.mkdir(parents=True, exist_ok=True)
            model_path = model_dir / "model.py"
            runner_path = model_dir / "run_checks.py"
            model_path.write_text(f"VALUE = {value}\n", encoding="utf-8")
            runner_path.write_text(
                f"print('{model_id} checks pass')\n",
                encoding="utf-8",
            )
            purpose = build_model_purpose_closure(
                model_instance_id=f"regression:{model_id}:current",
                reusable_model_type_id=model_id,
                task_intent_id=f"flowguard-regression:{model_id}",
                guarded_purpose=f"Protect the {model_id} fixture boundary.",
                protected_failure_ids=(f"{model_id}:stale",),
                known_good_case_id=f"native-runner:{model_id}:good",
                failure_bindings=(
                    {
                        "failure_id": f"{model_id}:stale",
                        "known_bad_case_id": f"native-runner:{model_id}:bad",
                        "oracle_id": f"native:{model_id}:runner",
                    },
                ),
                claim_boundary="Only this isolated owner-evidence fixture.",
                evidence_check_ids=(f"check:model-regression:{model_id}",),
                model_sha256=file_fingerprint(model_path),
                runner_sha256=file_fingerprint(runner_path),
            )
            entries.append(
                {
                    "model_id": model_id,
                    "model_path": f".flowguard/{model_id}/model.py",
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
                    "intent_source_inputs": ["docs/current-design.md"],
                    "expected_artifacts": [],
                    "distribution_policy": "required_public",
                    "absence_reason": "Required by this fixture.",
                    "exclusion_reason": "",
                    "purpose_closure": purpose.to_dict(),
                }
            )
        manifest = {
            "schema_version": MANIFEST_SCHEMA,
            "governed_input_globs": [".flowguard/**/*.py"],
            "snapshot_only_input_globs": [],
            "shared_input_groups": [],
            "models": entries,
        }
        (
            target_root / ".flowguard" / "model-regression-manifest.json"
        ).write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        bindings = {
            "schema": NATIVE_OWNER_BINDINGS_SCHEMA,
            "system_id": "flowguard",
            "candidate_model_ids": list(model_ids),
            "bindings": [
                {
                    "owner_route": "model_mesh_maintenance",
                    "model_ids": [model_ids[0]],
                    "protected_failure_ids": [f"{model_ids[0]}:stale"],
                },
                {
                    "owner_route": "model_test_alignment",
                    "model_ids": [model_ids[1]],
                    "protected_failure_ids": [f"{model_ids[1]}:stale"],
                },
            ],
            "claim_boundary": "Only this isolated owner-evidence fixture.",
        }
        (target_root / NATIVE_OWNER_BINDINGS_RELATIVE_PATH).write_text(
            json.dumps(bindings), encoding="utf-8"
        )

    def _current_parent(self):
        self._write_models(2)
        return run_manifest_regressions(
            self.root,
            tier="full",
            jobs=1,
            output_dir=self.root / "runs" / "full",
        )

    def _affected_owner_routes(self, snapshot_id: str) -> tuple[str, ...]:
        _head, base = load_observed_model_system(self.root)
        candidate = build_manifest_model_system_snapshot(
            self.root,
            snapshot_id=snapshot_id,
            system_id=base.system_id,
            subject_lane=base.subject_lane,
            lifecycle=base.lifecycle,
        )
        diff = derive_revision_snapshot_diff(base, candidate)
        closure = derive_revision_affected_closure(base, candidate, diff)
        return tuple(sorted({owner for _affected_id, owner in closure.owner_bindings}))

    def _changed_model_ids(self, snapshot_id: str) -> tuple[str, ...]:
        _head, base = load_observed_model_system(self.root)
        candidate = build_manifest_model_system_snapshot(
            self.root,
            snapshot_id=snapshot_id,
            system_id=base.system_id,
            subject_lane=base.subject_lane,
            lifecycle=base.lifecycle,
        )
        diff = derive_revision_snapshot_diff(base, candidate)
        return tuple(sorted(member.member_id for member in diff.members))

    def _no_intent_kwargs(self) -> dict[str, object]:
        return {
            "no_declared_intent_rationale_id": (
                "no-intent:owner-evidence-fixture"
            ),
            "no_declared_intent_evidence_fingerprints": (
                (
                    "fixture_manifest",
                    file_fingerprint(
                        self.root
                        / ".flowguard"
                        / "model-regression-manifest.json"
                    ),
                ),
            ),
            "no_declared_intent_rationale": (
                "This isolated fixture has no external product intent."
            ),
        }

    def _intent_bootstrap_kwargs(self, snapshot_id: str) -> dict[str, object]:
        source = self.root / "docs" / "current-design.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        if not source.exists():
            source.write_text(
                "The owner-evidence fixture keeps one current design source.\n",
                encoding="utf-8",
            )
        source_ref = source.relative_to(self.root).as_posix()
        source_fingerprint = source_file_fingerprint(source)
        contributions = tuple(
            ModelIntentContribution(
                contribution_id=f"intent:owner-evidence:{model_id}",
                source_kind="design",
                source_ref=source_ref,
                source_fingerprint=source_fingerprint,
                subject_lane="normative_target",
                subject_role="design",
                lifecycle_state="candidate",
                decision_state="accepted",
                logical_model_id=f"model:{model_id}",
                unresolved_owner_id="",
                supersedes_contribution_ids=(),
                conflicts_with_contribution_ids=(),
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
                effective_revision="owner-evidence-fixture:current",
                rationale=(
                    f"The {model_id} fixture model is bound to one exact "
                    "current design source."
                ),
            )
            for model_id in _MODEL_IDS
        )
        _head, base = load_observed_model_system(self.root)
        candidate = build_manifest_model_system_snapshot(
            self.root,
            snapshot_id=snapshot_id,
            system_id=base.system_id,
            subject_lane=base.subject_lane,
            lifecycle=base.lifecycle,
        )
        receipt = build_current_intent_bootstrap_receipt(
            self.root,
            receipt_id=f"receipt:intent-bootstrap:{snapshot_id}",
            candidate_snapshot=candidate,
            current_design_contributions=contributions,
            rationale=(
                "The owner-evidence fixture explicitly binds every current "
                "model owner before constructing its first v5 revision."
            ),
        )
        return {
            "current_design_intent_contributions": contributions,
            "effective_intent_bootstrap_receipt": receipt,
        }

    def _path_quality_kwargs(self, snapshot_id: str) -> dict[str, object]:
        _head, base = load_observed_model_system(self.root)
        candidate = build_manifest_model_system_snapshot(
            self.root,
            snapshot_id=snapshot_id,
            system_id=base.system_id,
            subject_lane=base.subject_lane,
            lifecycle=base.lifecycle,
        )
        diff = derive_revision_snapshot_diff(base, candidate)
        rows = tuple(
            _path_quality(
                member.member_id,
                member.candidate_instance_fingerprint,
                candidate.fingerprint,
            )
            for member in diff.members
            if member.operation in {"add", "replace"}
        )
        return {
            "path_quality_subjects": tuple(
                subject for subject, _result in rows
            ),
            "path_quality_results": tuple(
                result for _subject, result in rows
            ),
        }

    def _produce_bundle(self, snapshot_id: str):
        parent = self._current_parent()
        output = self.root / "owner-evidence.json"
        produce_model_revision_owner_evidence(
            self.root,
            model_parent_receipt=parent.parent_receipt_path,
            snapshot_id=snapshot_id,
            output_path=output,
        )
        return parent, _load_native_owner_evidence(output)

    def _content_addressed_receipt(self, receipt):
        owner_route = receipt.subject_id.removeprefix("validation-owner:")
        return replace(
            receipt,
            receipt_id=_content_addressed_receipt_id(
                f"receipt:validation-owner:{owner_route}",
                receipt,
            ),
        )

    def _forged_pass(self, receipt) -> ReceiptVerificationResult:
        return ReceiptVerificationResult(
            receipt_id=receipt.receipt_id,
            receipt_fingerprint=receipt.fingerprint,
            current=True,
            eligible=True,
            status=RECEIPT_STATUS_PASS,
            findings=(),
            satisfied_obligations=receipt.covered_obligations,
            minimum_revalidation=(),
        )

    def _build_with_bundle(
        self,
        *,
        parent,
        snapshot_id: str,
        contracts,
        receipts,
        verifications,
        suffix: str,
    ):
        return build_current_model_revision(
            self.root,
            model_parent_receipt=parent.parent_receipt_path,
            revision_set_id=f"revision:owner-evidence:{suffix}",
            task_id=f"task:owner-evidence:{suffix}",
            snapshot_id=snapshot_id,
            native_owner_contracts=contracts,
            native_owner_receipts=receipts,
            native_owner_verification_results=verifications,
            **self._intent_bootstrap_kwargs(snapshot_id),
            **self._path_quality_kwargs(snapshot_id),
            **self._no_intent_kwargs(),
        )

    def test_produces_distinct_child_bound_owner_receipts_accepted_by_builder(self) -> None:
        parent = self._current_parent()
        snapshot_id = "candidate:owner-evidence"
        output = self.root / "owner-evidence.json"

        with patch(
            "flowguard.model_revision_owner_evidence._collect_mapped_model_children",
            wraps=owner_evidence_module._collect_mapped_model_children,
        ) as collect_children:
            report = produce_model_revision_owner_evidence(
                self.root,
                model_parent_receipt=parent.parent_receipt_path,
                snapshot_id=snapshot_id,
                output_path=output,
            )

        self.assertEqual(1, collect_children.call_count)

        self.assertEqual("pass", report.status)
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(
            {"contracts", "receipts", "verification_results"},
            set(payload),
        )
        affected_owners = self._affected_owner_routes(snapshot_id)
        self.assertEqual(
            affected_owners,
            tuple(row["owner_id"] for row in payload["contracts"]),
        )
        receipt_ids = [row["receipt_id"] for row in payload["receipts"]]
        receipt_fingerprints = [
            fingerprint_value(row) for row in payload["receipts"]
        ]
        self.assertEqual(len(affected_owners), len(set(receipt_ids)))
        self.assertEqual(len(affected_owners), len(set(receipt_fingerprints)))
        self.assertTrue(
            all(row["required_child_receipts"] for row in payload["receipts"])
        )
        self.assertTrue(
            all(row["consumed_child_receipts"] for row in payload["receipts"])
        )
        for row in payload["receipts"]:
            required = {
                item["receipt_id"]: item["expected_receipt_fingerprint"]
                for item in row["required_child_receipts"]
            }
            consumed = {
                item["receipt_id"]: item["receipt_fingerprint"]
                for item in row["consumed_child_receipts"]
            }
            self.assertEqual(required, consumed)

        parent_payload = json.loads(
            Path(parent.parent_receipt_path).read_text(encoding="utf-8")
        )
        parent_child_ids = {
            row["model_id"]: row["receipt_id"]
            for row in parent_payload["children"]
        }
        changed_child_ids = {
            parent_child_ids[model_id]
            for model_id in self._changed_model_ids(snapshot_id)
        }
        receipts_by_owner = {
            row["subject_id"].removeprefix("validation-owner:"): row
            for row in payload["receipts"]
        }
        for owner_route in (
            "model_mesh_maintenance",
            "model_test_alignment",
        ):
            self.assertEqual(
                changed_child_ids,
                {
                    item["receipt_id"]
                    for item in receipts_by_owner[owner_route][
                        "required_child_receipts"
                    ]
                },
            )

        contracts, receipts, verifications = _load_native_owner_evidence(output)
        with patch(
            "flowguard.model_revision_owner_evidence.verify_model_revision_owner_evidence_bundle",
            wraps=(
                owner_evidence_module.verify_model_revision_owner_evidence_bundle
            ),
        ) as verify_bundle:
            built = build_current_model_revision(
                self.root,
                model_parent_receipt=parent.parent_receipt_path,
                revision_set_id="revision:owner-evidence",
                task_id="task:owner-evidence",
                snapshot_id=snapshot_id,
                native_owner_contracts=contracts,
                native_owner_receipts=receipts,
                native_owner_verification_results=verifications,
                **self._intent_bootstrap_kwargs(snapshot_id),
                **self._path_quality_kwargs(snapshot_id),
                **self._no_intent_kwargs(),
            )
        self.assertEqual(1, verify_bundle.call_count)
        revision = ModelRevisionSet.from_dict(
            json.loads(Path(built.revision_set_path).read_text(encoding="utf-8"))
        )
        self.assertEqual("pass", built.status)
        self.assertEqual("accepted", revision.status)

    def test_removed_model_is_accounted_without_requiring_absent_current_child(
        self,
    ) -> None:
        historical_model_id = "historical_retired_model"
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / ".flowguard").mkdir(parents=True)
            self._write_models(
                1,
                root=root,
                model_ids=(*_MODEL_IDS, historical_model_id),
            )
            base = build_manifest_model_system_snapshot(
                root,
                snapshot_id="observed-with-historical-model",
            )
            bootstrap_model_authority(
                root,
                base,
                bootstrap_evidence_fingerprint="sha256:" + "b" * 64,
            )

            self._write_models(2, root=root)
            retired_dir = root / ".flowguard" / historical_model_id
            for path in retired_dir.iterdir():
                path.unlink()
            retired_dir.rmdir()
            parent = run_manifest_regressions(
                root,
                tier="full",
                jobs=1,
                output_dir=root / "runs" / "removed-model-parent",
            )
            snapshot_id = "candidate:removed-model-owner-evidence"
            frozen = owner_evidence_module._freeze_revision_inputs(
                root,
                snapshot_id,
            )
            plans = owner_evidence_module._derive_native_owner_model_plans(
                frozen,
                owner_evidence_module._bindings_by_owner(
                    frozen.candidate_snapshot, root=root
                ),
            )
            plans_naming_removed = tuple(
                plan
                for plan in plans.values()
                if historical_model_id in plan.removed_referenced_model_ids
            )
            self.assertTrue(plans_naming_removed)
            self.assertTrue(
                all(
                    historical_model_id not in plan.required_model_ids
                    for plan in plans_naming_removed
                )
            )

            output = root / "removed-model-owner-evidence.json"
            report = produce_model_revision_owner_evidence(
                root,
                model_parent_receipt=parent.parent_receipt_path,
                snapshot_id=snapshot_id,
                output_path=output,
            )

            self.assertEqual("pass", report.status)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["receipts"])
            self.assertTrue(
                all(
                    historical_model_id
                    not in child["subject_id"]
                    for receipt in payload["receipts"]
                    for child in receipt["required_child_receipts"]
                )
            )

    def test_builder_rejects_readdressed_stale_or_incomplete_owner_receipts(
        self,
    ) -> None:
        snapshot_id = "candidate:reject-forged-owner-evidence"
        parent, bundle = self._produce_bundle(snapshot_id)
        contracts, receipts, verifications = bundle
        original = receipts[0]
        original_snapshot = original.input_snapshots[0]
        stale_environment_metadata = dict(original.environment_metadata)
        stale_environment_metadata["flowguard_version"] = "stale-toolchain"
        stale_environment = build_environment_fingerprint(
            stale_environment_metadata
        )
        missing_proof_metadata = dict(original.metadata)
        missing_proof_metadata["proof_relpath"] = "proofs/missing-proof.json"
        missing_child_metadata = dict(original.metadata)
        missing_child_metadata["child_receipt_ids"] = list(
            missing_child_metadata["child_receipt_ids"]
        )[1:]
        mutations = (
            (
                "contract-hash",
                replace(original, contract_hash="sha256:" + "b" * 64),
            ),
            (
                "input",
                replace(
                    original,
                    input_snapshots=(
                        replace(
                            original_snapshot,
                            raw_sha256="sha256:" + "c" * 64,
                            semantic_sha256="sha256:" + "c" * 64,
                        ),
                    ),
                ),
            ),
            (
                "command",
                replace(original, command=(*original.command, "--stale")),
            ),
            (
                "toolchain",
                replace(
                    original,
                    producer_version=original.producer_version + ".stale",
                ),
            ),
            (
                "environment",
                replace(
                    original,
                    environment_metadata=stale_environment.metadata,
                    environment_fingerprint=stale_environment.fingerprint,
                ),
            ),
            (
                "proof-missing",
                replace(original, metadata=missing_proof_metadata),
            ),
            (
                "result-missing-or-stale",
                replace(
                    original,
                    result_fingerprint="sha256:" + "d" * 64,
                ),
            ),
            (
                "child-binding-missing",
                replace(
                    original,
                    required_child_receipts=original.required_child_receipts[1:],
                    consumed_child_receipts=original.consumed_child_receipts[1:],
                    metadata=missing_child_metadata,
                ),
            ),
        )
        receipt_root = (
            self.root / ".flowguard" / "evidence" / "model-owner-receipts"
        )
        for suffix, mutation in mutations:
            with self.subTest(suffix=suffix):
                tampered = self._content_addressed_receipt(mutation)
                # Re-address and persist the altered object so canonical-store
                # presence and a matching caller fingerprint cannot make it green.
                save_evidence_receipt(
                    tampered,
                    self.root,
                    output_directory=receipt_root,
                )
                forged = self._forged_pass(tampered)
                changed_receipts = (tampered, *receipts[1:])
                changed_verifications = (forged, *verifications[1:])
                with self.assertRaises(ValueError):
                    self._build_with_bundle(
                        parent=parent,
                        snapshot_id=snapshot_id,
                        contracts=contracts,
                        receipts=changed_receipts,
                        verifications=changed_verifications,
                        suffix=suffix,
                    )

    def test_builder_rejects_noncanonical_receipt_and_forged_green_projection(
        self,
    ) -> None:
        snapshot_id = "candidate:reject-noncanonical-owner-evidence"
        parent, bundle = self._produce_bundle(snapshot_id)
        contracts, receipts, verifications = bundle
        noncanonical = self._content_addressed_receipt(
            replace(receipts[0], contract_hash="sha256:" + "e" * 64)
        )

        with self.assertRaisesRegex(ValueError, "canonical store"):
            self._build_with_bundle(
                parent=parent,
                snapshot_id=snapshot_id,
                contracts=contracts,
                receipts=(noncanonical, *receipts[1:]),
                verifications=(self._forged_pass(noncanonical), *verifications[1:]),
                suffix="noncanonical",
            )

        forged_projection = replace(
            verifications[0],
            current=True,
            eligible=True,
            status=RECEIPT_STATUS_PASS,
            minimum_revalidation=("forged-current-pass",),
        )
        with self.assertRaisesRegex(ValueError, "independently derived result"):
            self._build_with_bundle(
                parent=parent,
                snapshot_id=snapshot_id,
                contracts=contracts,
                receipts=receipts,
                verifications=(forged_projection, *verifications[1:]),
                suffix="forged-projection",
            )

        with self.assertRaisesRegex(ValueError, "incomplete or malformed"):
            self._build_with_bundle(
                parent=parent,
                snapshot_id=snapshot_id,
                contracts=contracts,
                receipts=receipts,
                verifications=verifications[1:],
                suffix="missing-verification-result",
            )

    def test_builder_rejects_missing_canonical_model_child_receipt(self) -> None:
        snapshot_id = "candidate:missing-canonical-child"
        parent, bundle = self._produce_bundle(snapshot_id)
        contracts, receipts, verifications = bundle
        child_id = receipts[0].required_child_receipts[0].receipt_id
        child_path = receipt_path(
            child_id,
            self.root,
            output_directory=(
                self.root / ".flowguard" / "evidence" / "model-owner-receipts"
            ),
        )
        child_path.unlink()

        with self.assertRaises(ValueError):
            self._build_with_bundle(
                parent=parent,
                snapshot_id=snapshot_id,
                contracts=contracts,
                receipts=receipts,
                verifications=verifications,
                suffix="missing-child",
            )

    def test_builder_rejects_aggregate_deleted_during_independent_verification(
        self,
    ) -> None:
        snapshot_id = "candidate:aggregate-deleted-during-verification"
        parent, bundle = self._produce_bundle(snapshot_id)
        contracts, receipts, verifications = bundle
        receipt_root = (
            self.root / ".flowguard" / "evidence" / "model-owner-receipts"
        )
        aggregate_path = receipt_path(
            receipts[0].receipt_id,
            self.root,
            output_directory=receipt_root,
        )
        original_assert = owner_evidence_module._assert_frozen_revision_inputs
        deleted = False

        def delete_after_source_freeze(root, candidate_snapshot_id, frozen):
            nonlocal deleted
            original_assert(root, candidate_snapshot_id, frozen)
            if not deleted:
                aggregate_path.unlink()
                deleted = True

        with patch(
            "flowguard.model_revision_owner_evidence._assert_frozen_revision_inputs",
            side_effect=delete_after_source_freeze,
        ):
            with self.assertRaises(ValueError):
                self._build_with_bundle(
                    parent=parent,
                    snapshot_id=snapshot_id,
                    contracts=contracts,
                    receipts=receipts,
                    verifications=verifications,
                    suffix="aggregate-deleted-during-verification",
                )

    def test_builder_rejects_child_deleted_during_independent_verification(
        self,
    ) -> None:
        snapshot_id = "candidate:child-deleted-during-verification"
        parent, bundle = self._produce_bundle(snapshot_id)
        contracts, receipts, verifications = bundle
        receipt_root = (
            self.root / ".flowguard" / "evidence" / "model-owner-receipts"
        )
        child_path = receipt_path(
            receipts[0].required_child_receipts[0].receipt_id,
            self.root,
            output_directory=receipt_root,
        )
        original_assert = owner_evidence_module._assert_frozen_revision_inputs
        deleted = False

        def delete_after_source_freeze(root, candidate_snapshot_id, frozen):
            nonlocal deleted
            original_assert(root, candidate_snapshot_id, frozen)
            if not deleted:
                child_path.unlink()
                deleted = True

        with patch(
            "flowguard.model_revision_owner_evidence._assert_frozen_revision_inputs",
            side_effect=delete_after_source_freeze,
        ):
            with self.assertRaises(ValueError):
                self._build_with_bundle(
                    parent=parent,
                    snapshot_id=snapshot_id,
                    contracts=contracts,
                    receipts=receipts,
                    verifications=verifications,
                    suffix="child-deleted-during-verification",
                )

    def test_blocks_unknown_owner_mapping_without_writing_bundle(self) -> None:
        parent = self._current_parent()
        output = self.root / "blocked-owner-evidence.json"
        with patch(
            "flowguard.model_revision_owner_evidence._load_native_owner_model_bindings",
            return_value={
                "model_test_alignment": NativeOwnerModelBinding(
                    owner_route="model_test_alignment",
                    model_ids=(_MODEL_IDS[1],),
                    protected_failure_ids=(f"{_MODEL_IDS[1]}:stale",),
                )
            },
        ):
            with self.assertRaisesRegex(ValueError, "missing native owner model mapping"):
                produce_model_revision_owner_evidence(
                    self.root,
                    model_parent_receipt=parent.parent_receipt_path,
                    snapshot_id="candidate:missing-owner-map",
                    output_path=output,
                )

        self.assertFalse(output.exists())

    def test_current_candidate_route_universe_has_explicit_inventory_bindings(
        self,
    ) -> None:
        project_root = Path(__file__).resolve().parents[1]
        snapshot = build_manifest_model_system_snapshot(
            project_root,
            snapshot_id="candidate:owner-route-universe-regression",
        )
        routes = owner_evidence_module._candidate_native_owner_route_universe(
            snapshot
        )
        bindings = owner_evidence_module._bindings_by_owner(
            snapshot, root=project_root
        )

        self.assertEqual(
            ("authoritative_model_system",),
            bindings["affected_authority_inventory"].model_ids,
        )
        self.assertEqual(
            ("authoritative_model_system",),
            bindings["authoritative_model_system"].model_ids,
        )
        self.assertEqual((), tuple(sorted(set(routes).difference(bindings))))

    def test_future_candidate_route_blocks_before_bundle_write(self) -> None:
        parent = self._current_parent()
        output = self.root / "future-route-owner-evidence.json"
        original = owner_evidence_module._candidate_native_owner_route_universe

        def add_future_route(snapshot):
            return tuple(sorted((*original(snapshot), "future_owner_route")))

        with patch(
            "flowguard.model_revision_owner_evidence._candidate_native_owner_route_universe",
            side_effect=add_future_route,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "native owner declaration route set is not exact.*future_owner_route",
            ):
                produce_model_revision_owner_evidence(
                    self.root,
                    model_parent_receipt=parent.parent_receipt_path,
                    snapshot_id="candidate:future-owner-route",
                    output_path=output,
                )

        self.assertFalse(output.exists())

    def test_foreign_mapped_model_blocks_before_bundle_write(self) -> None:
        parent = self._current_parent()
        output = self.root / "foreign-model-owner-evidence.json"
        with patch(
            "flowguard.model_revision_owner_evidence._load_native_owner_model_bindings",
            return_value={
                "model_mesh_maintenance": NativeOwnerModelBinding(
                    owner_route="model_mesh_maintenance",
                    model_ids=("future_nonexistent_model",),
                    protected_failure_ids=("future:stale",),
                ),
                "model_test_alignment": NativeOwnerModelBinding(
                    owner_route="model_test_alignment",
                    model_ids=(_MODEL_IDS[1],),
                    protected_failure_ids=(f"{_MODEL_IDS[1]}:stale",),
                ),
            },
        ):
            with self.assertRaisesRegex(
                ValueError,
                "mapped model is absent from the current full manifest.*future_nonexistent_model",
            ):
                produce_model_revision_owner_evidence(
                    self.root,
                    model_parent_receipt=parent.parent_receipt_path,
                    snapshot_id="candidate:foreign-owner-model",
                    output_path=output,
                )

        self.assertFalse(output.exists())

    def test_blocks_duplicate_or_foreign_mapping_before_writing_bundle(self) -> None:
        parent = self._current_parent()
        output = self.root / "duplicate-owner-evidence.json"
        with patch(
            "flowguard.model_revision_owner_evidence._load_native_owner_model_bindings",
            side_effect=ValueError("unique native owner routes"),
        ):
            with self.assertRaisesRegex(ValueError, "unique native owner routes"):
                produce_model_revision_owner_evidence(
                    self.root,
                    model_parent_receipt=parent.parent_receipt_path,
                    snapshot_id="candidate:duplicate-owner-map",
                    output_path=output,
                )

        self.assertFalse(output.exists())

    def test_blocks_owner_plan_that_omits_one_referenced_changed_model(self) -> None:
        parent = self._current_parent()
        output = self.root / "incomplete-owner-model-plan.json"
        original = owner_evidence_module._derive_native_owner_model_plans

        def omit_one_changed_model(frozen, bindings):
            plans = original(frozen, bindings)
            owner_route = "model_mesh_maintenance"
            plan = plans[owner_route]
            omitted = next(
                model_id
                for model_id in plan.referenced_changed_model_ids
                if model_id not in plan.semantic_model_ids
            )
            referenced = tuple(
                model_id
                for model_id in plan.referenced_changed_model_ids
                if model_id != omitted
            )
            plans[owner_route] = NativeOwnerModelEvidencePlan(
                owner_route=owner_route,
                affected_ids=plan.affected_ids,
                semantic_model_ids=plan.semantic_model_ids,
                referenced_changed_model_ids=referenced,
                removed_referenced_model_ids=(
                    plan.removed_referenced_model_ids
                ),
                required_model_ids=tuple(
                    sorted(set(plan.semantic_model_ids) | set(referenced))
                ),
            )
            return plans

        with patch(
            "flowguard.model_revision_owner_evidence._derive_native_owner_model_plans",
            side_effect=omit_one_changed_model,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "does not bind every affected model instance",
            ):
                produce_model_revision_owner_evidence(
                    self.root,
                    model_parent_receipt=parent.parent_receipt_path,
                    snapshot_id="candidate:omitted-changed-model",
                    output_path=output,
                )

        self.assertFalse(output.exists())

    def test_blocks_stale_parent_and_does_not_write_bundle(self) -> None:
        parent = self._current_parent()
        output = self.root / "stale-owner-evidence.json"
        self._write_models(3)

        with self.assertRaisesRegex(ValueError, "manifest fingerprint is stale"):
            produce_model_revision_owner_evidence(
                self.root,
                model_parent_receipt=parent.parent_receipt_path,
                snapshot_id="candidate:stale-owner-evidence",
                output_path=output,
            )

        self.assertFalse(output.exists())

    def test_cli_writes_strict_bundle_and_reports_frozen_identities(self) -> None:
        parent = self._current_parent()
        output = self.root / "cli-owner-evidence.json"
        stdout = StringIO()

        with redirect_stdout(stdout):
            exit_code = main(
                [
                    "model-revision-owner-evidence",
                    "--root",
                    str(self.root),
                    "--model-parent-receipt",
                    parent.parent_receipt_path,
                    "--snapshot-id",
                    "candidate:cli-owner-evidence",
                    "--output",
                    str(output),
                    "--json",
                ]
            )

        report = json.loads(stdout.getvalue())
        self.assertEqual(0, exit_code)
        self.assertEqual("pass", report["status"])
        self.assertEqual(str(output.resolve()), report["output_path"])
        for name in (
            "observed_head_fingerprint",
            "candidate_snapshot_fingerprint",
            "snapshot_diff_fingerprint",
            "affected_closure_fingerprint",
            "parent_receipt_fingerprint",
        ):
            self.assertRegex(report[name], r"^sha256:[0-9a-f]{64}$")
        _load_native_owner_evidence(output)


if __name__ == "__main__":
    unittest.main()
