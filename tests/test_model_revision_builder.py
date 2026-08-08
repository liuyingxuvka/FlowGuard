import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from flowguard.__main__ import _load_native_owner_evidence, main
from flowguard.evidence_receipts import fingerprint_value
from flowguard.model_authority import ModelAuthorityError, ModelRevisionSet
from flowguard.model_authority_store import (
    bootstrap_model_authority,
    load_observed_model_system,
)
from flowguard.model_intent import (
    ModelIntentContribution,
)
from flowguard.model_intent_authority import (
    build_current_intent_bootstrap_receipt,
)
from flowguard.model_purpose import (
    build_model_purpose_closure,
    file_fingerprint,
)
from flowguard.model_regressions import MANIFEST_SCHEMA, run_manifest_regressions
from flowguard.model_revision_builder import build_current_model_revision
from flowguard.model_revision_owner_evidence import (
    produce_model_revision_owner_evidence,
)
from tests.test_model_maturation import _path_quality
from flowguard.model_system_inventory import build_manifest_model_system_snapshot
from flowguard.source_identity import source_file_fingerprint


_MODEL_IDS = (
    "behavior_commitment_ledger",
    "default_replacement_field_lifecycle",
    "hierarchical_model_mesh",
    "model_test_code_alignment",
    "test_evidence_mesh",
)


class ModelRevisionBuilderTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / ".flowguard").mkdir(parents=True)
        self._write_current_model("VALUE = 1\n")
        base = build_manifest_model_system_snapshot(
            self.root,
            snapshot_id="observed-base",
        )
        bootstrap_model_authority(
            self.root,
            base,
            bootstrap_evidence_fingerprint="sha256:" + "a" * 64,
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def _write_current_model(
        self,
        source: str,
        *,
        model_source_overrides: dict[str, str] | None = None,
    ) -> None:
        source_overrides = model_source_overrides or {}
        shared_intent = self.root / "docs" / "current-design.md"
        shared_intent.parent.mkdir(parents=True, exist_ok=True)
        if not shared_intent.exists():
            shared_intent.write_text(
                "The builder fixture keeps one current design source.\n",
                encoding="utf-8",
            )
        entries = []
        for model_id in _MODEL_IDS:
            model_dir = self.root / ".flowguard" / model_id
            model_dir.mkdir(parents=True, exist_ok=True)
            model_path = model_dir / "model.py"
            runner_path = model_dir / "run_checks.py"
            model_path.write_text(
                source_overrides.get(model_id, source),
                encoding="utf-8",
            )
            runner_path.write_text(
                f"print('{model_id} checks pass')\n",
                encoding="utf-8",
            )
            purpose = build_model_purpose_closure(
                model_instance_id=f"regression:{model_id}:current",
                reusable_model_type_id=model_id,
                task_intent_id=f"flowguard-regression:{model_id}",
                guarded_purpose=(
                    f"Prevent the {model_id} model from accepting stale or "
                    "partial revision evidence as a current completed result."
                ),
                protected_failure_ids=(f"{model_id}:stale-or-partial",),
                known_good_case_id=f"native-runner:{model_id}:good",
                failure_bindings=(
                    {
                        "failure_id": f"{model_id}:stale-or-partial",
                        "known_bad_case_id": f"native-runner:{model_id}:bad",
                        "oracle_id": f"native:{model_id}:runner",
                    },
                ),
                claim_boundary=(
                    "This temporary model proves only the declared "
                    "revision-builder test boundary and no production behavior."
                ),
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
                    "absence_reason": (
                        "This fixture owner is required inside its test boundary."
                    ),
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
        (self.root / ".flowguard" / "model-regression-manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )

    def _current_parent(self, name: str = "parent"):
        return run_manifest_regressions(
            self.root,
            tier="full",
            output_dir=self.root / "outputs" / name,
        )

    def _no_intent_kwargs(self) -> dict[str, object]:
        return {
            "no_declared_intent_rationale_id": "no-intent:builder-fixture",
            "no_declared_intent_evidence_fingerprints": (
                ("fixture_manifest", file_fingerprint(
                    self.root / ".flowguard" / "model-regression-manifest.json"
                )),
            ),
            "no_declared_intent_rationale": (
                "This isolated builder fixture has no external product intent "
                "beyond exercising its declared test boundary."
            ),
        }

    def _current_design_contributions(
        self,
        *,
        source_overrides: dict[str, Path] | None = None,
    ) -> tuple[ModelIntentContribution, ...]:
        overrides = source_overrides or {}
        shared_source = self.root / "docs" / "current-design.md"
        shared_source.parent.mkdir(parents=True, exist_ok=True)
        if not shared_source.exists():
            shared_source.write_text(
                "The builder fixture keeps one current design source.\n",
                encoding="utf-8",
            )
        contributions = []
        for model_id in _MODEL_IDS:
            source = overrides.get(model_id, shared_source)
            contributions.append(
                ModelIntentContribution(
                    contribution_id=f"intent:current-design:{model_id}",
                    source_kind="design",
                    source_ref=source.relative_to(self.root).as_posix(),
                    source_fingerprint=source_file_fingerprint(source),
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
                    effective_revision="current-design:builder-fixture",
                    rationale=(
                        f"The {model_id} fixture model has one exact primary "
                        "owner record bound to this shared current design source."
                    ),
                )
            )
        result = tuple(contributions)
        manifest_path = self.root / ".flowguard" / "model-regression-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        desired_by_owner = {
            item.logical_model_id.split("model:", 1)[1]: [item.source_ref]
            for item in result
        }
        changed = False
        for row in manifest["models"]:
            desired = desired_by_owner[row["model_id"]]
            if row.get("intent_source_inputs", []) != desired:
                row["intent_source_inputs"] = desired
                changed = True
        if changed:
            manifest_path.write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
        return result

    def _intent_bootstrap_kwargs(
        self,
        snapshot_id: str,
        *,
        source_overrides: dict[str, Path] | None = None,
    ) -> dict[str, object]:
        contributions = self._current_design_contributions(
            source_overrides=source_overrides,
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
                "The builder fixture explicitly binds all five current model "
                "owners without deriving current intent from historical deltas."
            ),
        )
        return {
            "current_design_intent_contributions": contributions,
            "effective_intent_bootstrap_receipt": receipt,
        }

    def _native_owner_evidence(self, snapshot_id: str, parent_receipt: str):
        output = self.root / "outputs" / "native-owner-evidence.json"
        produce_model_revision_owner_evidence(
            self.root,
            model_parent_receipt=parent_receipt,
            snapshot_id=snapshot_id,
            output_path=output,
        )
        return _load_native_owner_evidence(output)

    def _path_quality_kwargs(
        self,
        snapshot_id: str,
        *,
        full_current: bool = False,
    ) -> dict[str, object]:
        _head, base = load_observed_model_system(self.root)
        candidate = build_manifest_model_system_snapshot(
            self.root,
            snapshot_id=snapshot_id,
            system_id=base.system_id,
            subject_lane=base.subject_lane,
            lifecycle=base.lifecycle,
        )
        from flowguard.model_revision_set import derive_revision_snapshot_diff

        diff = derive_revision_snapshot_diff(base, candidate)
        if full_current:
            rows = tuple(
                _path_quality(
                    member.logical_model_id,
                    member.fingerprint,
                    candidate.fingerprint,
                )
                for member in candidate.model_instances
            )
        else:
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
            "path_quality_subjects": tuple(subject for subject, _result in rows),
            "path_quality_results": tuple(result for _subject, result in rows),
        }

    def _write_intent_bootstrap_input(self, name: str) -> Path:
        path = self.root / f"intent-bootstrap-{name}.json"
        path.write_text(
            json.dumps(
                {
                    "schema": (
                        "flowguard.model_revision_intent_bootstrap_input.v1"
                    ),
                    "receipt_id": f"receipt:intent-bootstrap:{name}",
                    "rationale": (
                        "The CLI fixture explicitly binds every current model "
                        "owner to one exact current-design contribution."
                    ),
                    "claim_boundary": (
                        "This one-time bootstrap input proves only the finite "
                        "builder fixture and no unenumerated production behavior."
                    ),
                    "current_design_contributions": [
                        item.to_dict()
                        for item in self._current_design_contributions()
                    ],
                    "legacy_entry_dispositions": [],
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return path

    def _write_path_quality_material(
        self,
        snapshot_id: str,
        name: str,
    ) -> Path:
        material = self._path_quality_kwargs(snapshot_id)
        path = self.root / f"path-quality-{name}.json"
        path.write_text(
            json.dumps(
                {
                    "subjects": [
                        item.to_dict()
                        for item in material["path_quality_subjects"]
                    ],
                    "results": [
                        item.to_dict()
                        for item in material["path_quality_results"]
                    ],
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return path

    def test_builds_accepted_content_addressed_pair_without_activation(self):
        self._write_current_model("VALUE = 2\n")
        report = self._current_parent()
        head_before, _base = load_observed_model_system(self.root)
        contracts, receipts, verifications = self._native_owner_evidence(
            "observed-test-builder",
            report.parent_receipt_path,
        )

        built = build_current_model_revision(
            self.root,
            model_parent_receipt=report.parent_receipt_path,
            revision_set_id="revision:test-builder",
            task_id="task:test-builder",
            snapshot_id="observed-test-builder",
            native_owner_contracts=contracts,
            native_owner_receipts=receipts,
            native_owner_verification_results=verifications,
            **self._path_quality_kwargs("observed-test-builder"),
            **self._intent_bootstrap_kwargs("observed-test-builder"),
            **self._no_intent_kwargs(),
        )

        head_after, _still_base = load_observed_model_system(self.root)
        self.assertEqual(head_before, head_after)
        self.assertEqual("pass", built.status)
        candidate_path = Path(built.candidate_snapshot_path)
        revision_path = Path(built.revision_set_path)
        self.assertTrue(candidate_path.is_file())
        self.assertTrue(revision_path.is_file())
        self.assertEqual(
            built.candidate_snapshot_fingerprint.split(":", 1)[1],
            candidate_path.stem,
        )
        self.assertEqual(
            built.revision_set_fingerprint.split(":", 1)[1],
            revision_path.stem,
        )
        revision = ModelRevisionSet.from_dict(
            json.loads(revision_path.read_text(encoding="utf-8"))
        )
        self.assertEqual("accepted", revision.status)
        self.assertTrue(revision.evidence_complete)
        self.assertEqual(
            revision.affected_closure_ids,
            tuple(
                sorted(
                    affected_id
                    for item in revision.completed_evidence_refs
                    for affected_id in item.covered_affected_ids
                )
            ),
        )

    def test_builder_accepts_full_current_path_quality_superset(self):
        changed_model_id = _MODEL_IDS[0]
        self._write_current_model(
            "VALUE = 1\n",
            model_source_overrides={changed_model_id: "VALUE = 2\n"},
        )
        snapshot_id = "observed-full-current-path-quality"
        report = self._current_parent("full-current-path-quality")
        contracts, receipts, verifications = self._native_owner_evidence(
            snapshot_id,
            report.parent_receipt_path,
        )

        built = build_current_model_revision(
            self.root,
            model_parent_receipt=report.parent_receipt_path,
            revision_set_id="revision:full-current-path-quality",
            task_id="task:full-current-path-quality",
            snapshot_id=snapshot_id,
            native_owner_contracts=contracts,
            native_owner_receipts=receipts,
            native_owner_verification_results=verifications,
            **self._path_quality_kwargs(snapshot_id, full_current=True),
            **self._intent_bootstrap_kwargs(snapshot_id),
            **self._no_intent_kwargs(),
        )

        revision = ModelRevisionSet.from_dict(
            json.loads(
                Path(built.revision_set_path).read_text(encoding="utf-8")
            )
        )
        self.assertEqual("pass", built.status)
        self.assertEqual("accepted", revision.status)
        self.assertEqual(
            ((changed_model_id, "replace"),),
            tuple(
                (member.member_id, member.operation)
                for member in revision.members
            ),
        )
        self.assertEqual(
            tuple(sorted(_MODEL_IDS)),
            revision.required_path_quality_model_ids,
        )
        self.assertTrue(revision.path_quality_acceptance_ready)

    def test_parent_regression_pass_does_not_manufacture_native_owner_evidence(self):
        self._write_current_model("VALUE = 2\n")
        report = self._current_parent("parent-only")

        built = build_current_model_revision(
            self.root,
            model_parent_receipt=report.parent_receipt_path,
            revision_set_id="revision:parent-only",
            task_id="task:parent-only",
            snapshot_id="observed-parent-only",
            **self._intent_bootstrap_kwargs("observed-parent-only"),
            **self._no_intent_kwargs(),
        )

        revision = ModelRevisionSet.from_dict(
            json.loads(Path(built.revision_set_path).read_text(encoding="utf-8"))
        )
        self.assertEqual("incomplete", built.status)
        self.assertEqual("proposed", revision.status)
        self.assertFalse(revision.evidence_complete)
        self.assertEqual(
            tuple(sorted(set(dict(revision.affected_owner_bindings).values()))),
            built.missing_owner_routes,
        )

    def test_rejects_stale_intent_source_before_writing_candidate_outputs(self):
        self._write_current_model("VALUE = 2\n")
        source = self.root / "docs" / "intent.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("Current requirement.\n", encoding="utf-8")
        bootstrap_kwargs = self._intent_bootstrap_kwargs(
            "observed-stale-intent-source",
            source_overrides={_MODEL_IDS[0]: source},
        )
        report = self._current_parent("stale-intent-source")
        source.write_text("Stale requirement.\n", encoding="utf-8")
        output_root = self.root / "candidate-stale-intent-source"

        with self.assertRaisesRegex(ModelAuthorityError, "fingerprint is stale"):
            build_current_model_revision(
                self.root,
                model_parent_receipt=report.parent_receipt_path,
                revision_set_id="revision:stale-intent-source",
                task_id="task:stale-intent-source",
                snapshot_id="observed-stale-intent-source",
                output_root=output_root,
                **bootstrap_kwargs,
                **self._no_intent_kwargs(),
            )

        self.assertFalse(output_root.exists())

    def test_rejects_current_source_missing_from_exact_owner_model_input(self):
        self._write_current_model("VALUE = 2\n")
        snapshot_id = "observed-missing-intent-owner-input"
        bootstrap_kwargs = self._intent_bootstrap_kwargs(snapshot_id)
        manifest_path = self.root / ".flowguard" / "model-regression-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["models"][0]["intent_source_inputs"] = []
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        report = self._current_parent("missing-intent-owner-input")
        output_root = self.root / "candidate-missing-intent-owner-input"

        with self.assertRaisesRegex(
            ModelAuthorityError,
            "missing intent-source input: docs/current-design.md",
        ):
            build_current_model_revision(
                self.root,
                model_parent_receipt=report.parent_receipt_path,
                revision_set_id="revision:missing-intent-owner-input",
                task_id="task:missing-intent-owner-input",
                snapshot_id=snapshot_id,
                output_root=output_root,
                **bootstrap_kwargs,
                **self._no_intent_kwargs(),
            )

        self.assertFalse(output_root.exists())

    def test_rechecks_frozen_intent_source_before_publication(self):
        self._write_current_model("VALUE = 2\n")
        source = self.root / "docs" / "intent.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("Current requirement.\n", encoding="utf-8")
        snapshot_id = "observed-during-build-intent-change"
        bootstrap_kwargs = self._intent_bootstrap_kwargs(
            snapshot_id,
            source_overrides={_MODEL_IDS[0]: source},
        )
        report = self._current_parent("during-build-intent-change")
        output_root = self.root / "candidate-during-build-intent-change"
        real_builder = build_manifest_model_system_snapshot
        calls = 0

        def build_then_mutate(*args, **kwargs):
            nonlocal calls
            result = real_builder(*args, **kwargs)
            calls += 1
            if calls == 2:
                source.write_text(
                    "Changed while the candidate was being built.\n",
                    encoding="utf-8",
                )
            return result

        with patch(
            "flowguard.model_revision_builder.build_manifest_model_system_snapshot",
            side_effect=build_then_mutate,
        ):
            with self.assertRaisesRegex(
                ModelAuthorityError,
                "intent source changed before revision publication",
            ):
                build_current_model_revision(
                    self.root,
                    model_parent_receipt=report.parent_receipt_path,
                    revision_set_id="revision:during-build-intent-change",
                    task_id="task:during-build-intent-change",
                    snapshot_id=snapshot_id,
                    output_root=output_root,
                    **bootstrap_kwargs,
                    **self._no_intent_kwargs(),
                )

        self.assertGreaterEqual(calls, 2)
        self.assertFalse(output_root.exists())
        head, snapshot = load_observed_model_system(self.root)
        self.assertEqual(1, head.generation)
        self.assertEqual("observed-base", snapshot.snapshot_id)

    def test_rejects_stale_parent_before_writing_outputs(self):
        self._write_current_model("VALUE = 2\n")
        report = self._current_parent()
        self._write_current_model("VALUE = 3\n")
        output_root = self.root / "candidate-output"
        bootstrap_kwargs = self._intent_bootstrap_kwargs("observed-stale")

        with self.assertRaisesRegex(ValueError, "manifest fingerprint is stale"):
            build_current_model_revision(
                self.root,
                model_parent_receipt=report.parent_receipt_path,
                revision_set_id="revision:stale",
                task_id="task:stale",
                snapshot_id="observed-stale",
                output_root=output_root,
                **bootstrap_kwargs,
                **self._no_intent_kwargs(),
            )

        self.assertFalse(output_root.exists())
        head, snapshot = load_observed_model_system(self.root)
        self.assertEqual(1, head.generation)
        self.assertEqual("observed-base", snapshot.snapshot_id)

    def test_rejects_scoped_parent(self):
        self._write_current_model("VALUE = 2\n")
        report = run_manifest_regressions(
            self.root,
            tier="fast",
            output_dir=self.root / "outputs" / "scoped",
        )
        self.assertEqual("scoped", report.parent_claim_scope)

        with self.assertRaisesRegex(ValueError, "terminal pass with full"):
            build_current_model_revision(
                self.root,
                model_parent_receipt=report.parent_receipt_path,
                revision_set_id="revision:scoped",
                task_id="task:scoped",
                snapshot_id="observed-scoped",
                **self._intent_bootstrap_kwargs("observed-scoped"),
                **self._no_intent_kwargs(),
            )

        source = Path(report.parent_receipt_path)
        relabeled_payload = json.loads(source.read_text(encoding="utf-8"))
        relabeled_payload["claim_scope"] = "full"
        relabeled_payload["tier"] = "full"
        relabeled_payload["claim_boundary"] = (
            "Relabeled wrapper must not replace native full-parent evidence."
        )
        relabeled_identity = {
            key: value
            for key, value in relabeled_payload.items()
            if key != "parent_receipt_fingerprint"
        }
        relabeled_payload["parent_receipt_fingerprint"] = fingerprint_value(
            relabeled_identity
        )
        relabeled = self.root / "relabeled-scoped-parent.json"
        relabeled.write_text(json.dumps(relabeled_payload), encoding="utf-8")

        with self.assertRaisesRegex(
            ValueError,
            "execution receipt is not an exact-current full composition",
        ):
            build_current_model_revision(
                self.root,
                model_parent_receipt=relabeled,
                revision_set_id="revision:relabeled-scoped",
                task_id="task:relabeled-scoped",
                snapshot_id="observed-relabeled-scoped",
                **self._intent_bootstrap_kwargs(
                    "observed-relabeled-scoped"
                ),
                **self._no_intent_kwargs(),
            )

    def test_rejects_parent_that_rebinds_a_current_child(self):
        self._write_current_model("VALUE = 2\n")
        report = self._current_parent("rebound-child")
        source = Path(report.parent_receipt_path)
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload["children"][0]["receipt_id"] = "receipt:model-regression:foreign"
        payload["children"][0]["receipt_fingerprint"] = "sha256:" + "b" * 64
        identity = {
            key: value
            for key, value in payload.items()
            if key != "parent_receipt_fingerprint"
        }
        payload["parent_receipt_fingerprint"] = fingerprint_value(identity)
        rebound = self.root / "rebound-parent.json"
        rebound.write_text(json.dumps(payload), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "not the exact current receipt"):
            build_current_model_revision(
                self.root,
                model_parent_receipt=rebound,
                revision_set_id="revision:rebound",
                task_id="task:rebound",
                snapshot_id="observed-rebound",
                **self._intent_bootstrap_kwargs("observed-rebound"),
                **self._no_intent_kwargs(),
            )

    def test_cli_emits_activation_ready_paths_but_keeps_head(self):
        self._write_current_model("VALUE = 2\n")
        report = self._current_parent("cli-parent")
        head_before, _base = load_observed_model_system(self.root)
        bootstrap_input = self._write_intent_bootstrap_input("cli-builder")
        output = StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "model-revision-intent-bootstrap",
                    "--root",
                    str(self.root),
                    "--model-parent-receipt",
                    report.parent_receipt_path,
                    "--revision-set-id",
                    "revision:cli-builder",
                    "--task-id",
                    "task:cli-builder",
                    "--snapshot-id",
                    "observed-cli-builder",
                    "--intent-bootstrap-input",
                    str(bootstrap_input),
                    "--no-declared-intent-rationale-id",
                    "no-intent:builder-cli-fixture",
                    "--no-declared-intent-evidence-fingerprints",
                    json.dumps({"fixture_manifest": file_fingerprint(
                        self.root / ".flowguard" / "model-regression-manifest.json"
                    )}),
                    "--no-declared-intent-rationale",
                    (
                        "This isolated CLI fixture has no external product intent "
                        "beyond exercising its declared test boundary."
                    ),
                    "--json",
                ]
            )

        payload = json.loads(output.getvalue())
        head_after, _still_base = load_observed_model_system(self.root)
        self.assertEqual(0, exit_code)
        self.assertEqual("incomplete", payload["status"])
        self.assertTrue(Path(payload["candidate_snapshot_path"]).is_file())
        self.assertTrue(Path(payload["revision_set_path"]).is_file())
        self.assertEqual(head_before, head_after)

    def test_cli_accepts_only_exact_current_path_quality_material(self):
        snapshot_id = "observed-cli-path-quality"
        self._write_current_model("VALUE = 2\n")
        report = self._current_parent("cli-path-quality-parent")
        head_before, _base = load_observed_model_system(self.root)
        bootstrap_input = self._write_intent_bootstrap_input(
            "cli-path-quality"
        )
        owner_evidence = (
            self.root / "outputs" / "cli-native-owner-evidence.json"
        )
        produce_model_revision_owner_evidence(
            self.root,
            model_parent_receipt=report.parent_receipt_path,
            snapshot_id=snapshot_id,
            output_path=owner_evidence,
        )
        path_quality = self._write_path_quality_material(
            snapshot_id,
            "cli-path-quality",
        )
        output = StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "model-revision-intent-bootstrap",
                    "--root",
                    str(self.root),
                    "--model-parent-receipt",
                    report.parent_receipt_path,
                    "--revision-set-id",
                    "revision:cli-path-quality",
                    "--task-id",
                    "task:cli-path-quality",
                    "--snapshot-id",
                    snapshot_id,
                    "--intent-bootstrap-input",
                    str(bootstrap_input),
                    "--native-owner-evidence",
                    str(owner_evidence),
                    "--path-quality-material",
                    str(path_quality),
                    "--no-declared-intent-rationale-id",
                    "no-intent:builder-cli-path-quality-fixture",
                    "--no-declared-intent-evidence-fingerprints",
                    json.dumps(
                        {
                            "fixture_manifest": file_fingerprint(
                                self.root
                                / ".flowguard"
                                / "model-regression-manifest.json"
                            )
                        }
                    ),
                    "--no-declared-intent-rationale",
                    (
                        "This isolated CLI fixture has no external product intent "
                        "beyond exercising its exact current path-quality boundary."
                    ),
                    "--json",
                ]
            )

        payload = json.loads(output.getvalue())
        head_after, _still_base = load_observed_model_system(self.root)
        self.assertEqual(0, exit_code)
        self.assertEqual("pass", payload["status"])
        revision = ModelRevisionSet.from_dict(
            json.loads(
                Path(payload["revision_set_path"]).read_text(encoding="utf-8")
            )
        )
        self.assertEqual("accepted", revision.status)
        self.assertTrue(revision.path_quality_acceptance_ready)
        self.assertEqual(head_before, head_after)


if __name__ == "__main__":
    unittest.main()
