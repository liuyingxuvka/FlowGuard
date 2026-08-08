import hashlib
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flowguard.__main__ import main
from flowguard.model_authority import ModelAuthorityError
from flowguard.model_authority_store import bootstrap_model_authority
from flowguard.model_purpose import build_model_purpose_closure, file_fingerprint
from flowguard.model_regressions import MANIFEST_SCHEMA
from flowguard.model_revision_plan import preview_current_model_revision
from flowguard.model_system_inventory import build_manifest_model_system_snapshot


class ModelRevisionPlanTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / ".flowguard").mkdir(parents=True)
        self.model_ids = (
            "authoritative_model_system",
            *(f"revision_plan_fixture_{index:02d}" for index in range(1, 64)),
        )
        self._write_manifest(self.model_ids)
        base = build_manifest_model_system_snapshot(
            self.root,
            snapshot_id="observed:revision-plan-base",
        )
        bootstrap_model_authority(
            self.root,
            base,
            bootstrap_evidence_fingerprint="sha256:" + "a" * 64,
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def _entry(self, model_id: str) -> dict[str, object]:
        model_dir = self.root / ".flowguard" / model_id
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / "model.py"
        runner_path = model_dir / "run_checks.py"
        model_path.write_text(
            f"MODEL_ID = {model_id!r}\nVALUE = 1\n",
            encoding="utf-8",
        )
        runner_path.write_text(
            f"print({model_id!r} + ' checks pass')\n",
            encoding="utf-8",
        )
        purpose = build_model_purpose_closure(
            model_instance_id=f"regression:{model_id}:current",
            reusable_model_type_id=model_id,
            task_intent_id=f"flowguard-regression:{model_id}",
            guarded_purpose=(
                f"Prevent {model_id} revision planning from accepting an "
                "unknown or stale model-system denominator."
            ),
            protected_failure_ids=(f"{model_id}:stale-denominator",),
            known_good_case_id=f"native-runner:{model_id}:good",
            failure_bindings=(
                {
                    "failure_id": f"{model_id}:stale-denominator",
                    "known_bad_case_id": f"native-runner:{model_id}:bad",
                    "oracle_id": f"native:{model_id}:runner",
                },
            ),
            claim_boundary=(
                "This fixture proves only the read-only revision-plan test "
                "boundary and no production FlowGuard behavior."
            ),
            evidence_check_ids=(f"check:model-regression:{model_id}",),
            model_sha256=file_fingerprint(model_path),
            runner_sha256=file_fingerprint(runner_path),
        )
        return {
            "model_id": model_id,
            "model_path": f".flowguard/{model_id}/model.py",
            "runner": ["{python}", f".flowguard/{model_id}/run_checks.py"],
            "tier": "fast",
            "timeout_seconds": 5,
            "shard_safe": True,
            "mutation_policy": "none",
            "input_globs": [
                f".flowguard/{model_id}/model.py",
                f".flowguard/{model_id}/run_checks.py",
            ],
            "expected_artifacts": [],
            "distribution_policy": "required_public",
            "absence_reason": "This fixture owner is required in its boundary.",
            "exclusion_reason": "",
            "purpose_closure": purpose.to_dict(),
        }

    def _write_manifest(self, model_ids: tuple[str, ...]) -> None:
        manifest = {
            "schema_version": MANIFEST_SCHEMA,
            "governed_input_globs": [".flowguard/**/*.py"],
            "snapshot_only_input_globs": [],
            "shared_input_groups": [],
            "models": [self._entry(model_id) for model_id in model_ids],
        }
        (self.root / ".flowguard" / "model-regression-manifest.json").write_text(
            json.dumps(manifest, sort_keys=True),
            encoding="utf-8",
        )

    def _retire_last_four(self) -> tuple[str, ...]:
        retired = tuple(self.model_ids[-4:])
        manifest_path = self.root / ".flowguard" / "model-regression-manifest.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["models"] = [
            item for item in payload["models"] if item["model_id"] not in retired
        ]
        manifest_path.write_text(
            json.dumps(payload, sort_keys=True),
            encoding="utf-8",
        )
        for model_id in retired:
            shutil.rmtree(self.root / ".flowguard" / model_id)
        return retired

    def _tree_identity(self) -> tuple[tuple[str, str], ...]:
        rows = []
        for path in sorted(self.root.rglob("*")):
            relative = path.relative_to(self.root).as_posix()
            if path.is_dir():
                rows.append((relative + "/", "directory"))
            else:
                rows.append(
                    (
                        relative,
                        hashlib.sha256(path.read_bytes()).hexdigest(),
                    )
                )
        return tuple(rows)

    def test_exact_64_to_60_preview_and_cli_are_read_only(self):
        retired = self._retire_last_four()
        before = self._tree_identity()

        report = preview_current_model_revision(
            self.root,
            snapshot_id="candidate:revision-plan-64-to-60",
        )

        self.assertTrue(report.ok)
        payload = report.to_dict()
        self.assertEqual(64, payload["base_model_count"])
        self.assertEqual(60, payload["candidate_model_count"])
        self.assertEqual(list(retired), payload["removed_model_ids"])
        self.assertEqual([], payload["added_model_ids"])
        self.assertEqual(list(retired), payload["changed_model_ids"])
        self.assertEqual("flowguard.model_revision_plan.v2", payload["schema"])
        self.assertEqual(
            "flowguard.model_authority_bootstrap.v1",
            payload["accepted_revision_schema"],
        )
        self.assertEqual("bootstrap_required", payload["intent_mode"])
        self.assertEqual(
            "model-revision-intent-bootstrap",
            payload["required_command"],
        )
        self.assertEqual(60, payload["candidate_model_owner_count"])
        self.assertEqual(
            [f"model-obligation:{model_id}" for model_id in self.model_ids[:-4]],
            payload["candidate_model_owner_ids"],
        )
        self.assertEqual(
            60,
            len(payload["candidate_model_owners"]),
        )
        self.assertTrue(
            payload["candidate_model_owner_inventory_fingerprint"].startswith(
                "sha256:"
            )
        )
        self.assertEqual(0, payload["required_legacy_intent_entry_count"])
        self.assertEqual([], payload["required_legacy_intent_entries"])
        self.assertTrue(
            payload[
                "required_legacy_intent_entry_inventory_fingerprint"
            ].startswith("sha256:")
        )
        self.assertEqual(0, payload["required_transition_predecessor_count"])
        self.assertEqual([], payload["required_transition_predecessors"])
        self.assertEqual(
            [
                "receipt_id",
                "rationale",
                "claim_boundary",
                "current_design_contributions",
                "legacy_entry_dispositions",
            ],
            payload["required_intent_input_kinds"],
        )
        self.assertTrue(
            payload["intent_input_identity_fingerprint"].startswith("sha256:")
        )
        for model_id in retired:
            self.assertIn(
                f"model_instance:model:{model_id}",
                payload["snapshot_diff"]["removed_ids"],
            )
        self.assertTrue(payload["affected_closure"]["affected_ids"])
        self.assertTrue(payload["required_owner_routes"])
        self.assertFalse(payload["writes_performed"])
        self.assertFalse(payload["models_executed"])
        self.assertEqual(before, self._tree_identity())

        compact = report.to_compact_dict()
        for field_name in (
            "status",
            "ok",
            "base_snapshot_id",
            "base_snapshot_fingerprint",
            "candidate_snapshot_id",
            "candidate_snapshot_fingerprint",
            "base_model_count",
            "candidate_model_count",
            "accepted_revision_schema",
            "accepted_revision_fingerprint",
            "base_effective_intent_view_fingerprint",
            "intent_mode",
            "required_command",
            "candidate_model_owner_count",
            "candidate_model_owner_inventory_fingerprint",
            "required_legacy_intent_entry_count",
            "required_legacy_intent_entry_inventory_fingerprint",
            "required_transition_predecessor_count",
            "required_transition_predecessor_inventory_fingerprint",
            "required_intent_input_kinds",
            "intent_input_identity_fingerprint",
            "change_present",
            "added_model_ids",
            "removed_model_ids",
            "replaced_model_ids",
            "snapshot_diff_fingerprint",
            "affected_closure_fingerprint",
            "required_owner_routes",
            "blockers",
            "writes_performed",
            "models_executed",
            "claim_boundary",
        ):
            self.assertEqual(payload[field_name], compact[field_name])
        for omitted_detail in (
            "base_model_ids",
            "candidate_model_ids",
            "candidate_model_owner_ids",
            "candidate_model_owners",
            "required_legacy_intent_entries",
            "required_transition_predecessors",
            "changed_model_ids",
            "changed_entity_ids",
            "snapshot_diff",
            "affected_closure",
        ):
            self.assertNotIn(omitted_detail, compact)
        self.assertLess(
            len(json.dumps(compact)),
            len(json.dumps(payload)) // 10,
        )
        self.assertEqual(before, self._tree_identity())

        output = StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    "model-revision-plan",
                    "--root",
                    str(self.root),
                    "--snapshot-id",
                    "candidate:revision-plan-64-to-60",
                    "--json",
                ]
            )
        self.assertEqual(0, exit_code)
        cli_payload = json.loads(output.getvalue())
        self.assertEqual(payload, cli_payload)
        self.assertEqual(before, self._tree_identity())

        compact_output = StringIO()
        with redirect_stdout(compact_output):
            compact_exit_code = main(
                [
                    "model-revision-plan",
                    "--root",
                    str(self.root),
                    "--snapshot-id",
                    "candidate:revision-plan-64-to-60",
                    "--compact",
                    "--json",
                ]
            )
        self.assertEqual(0, compact_exit_code)
        self.assertEqual(compact, json.loads(compact_output.getvalue()))
        self.assertEqual(before, self._tree_identity())

    def test_stale_live_manifest_is_blocked_without_writes(self):
        stale_path = (
            self.root
            / ".flowguard"
            / "authoritative_model_system"
            / "model.py"
        )
        stale_path.write_text(
            "MODEL_ID = 'changed-without-manifest-renewal'\n",
            encoding="utf-8",
        )
        before = self._tree_identity()

        report = preview_current_model_revision(
            self.root,
            snapshot_id="candidate:stale-manifest",
        )

        self.assertFalse(report.ok)
        self.assertEqual("blocked", report.status)
        self.assertEqual("live_candidate_unavailable", report.blockers[0].code)
        self.assertIn("not authoritative", report.blockers[0].message)
        self.assertEqual("bootstrap_required", report.intent_mode)
        self.assertEqual(
            "model-revision-intent-bootstrap",
            report.required_command,
        )
        self.assertEqual(0, len(report.candidate_model_owners))
        self.assertEqual("", report.intent_input_identity_fingerprint)
        self.assertEqual(before, self._tree_identity())

    def test_unreadable_intent_authority_stays_a_visible_blocker(self):
        before = self._tree_identity()

        with patch(
            "flowguard.model_revision_plan._accepted_revision_schema",
            side_effect=OSError("accepted revision cannot be read"),
        ):
            report = preview_current_model_revision(
                self.root,
                snapshot_id="candidate:unreadable-intent-authority",
            )

        self.assertFalse(report.ok)
        self.assertEqual("blocked", report.status)
        self.assertEqual(
            "current_intent_plan_unavailable",
            report.blockers[0].code,
        )
        self.assertIn("cannot be read", report.blockers[0].message)
        self.assertEqual("", report.accepted_revision_schema)
        self.assertEqual(before, self._tree_identity())

    def test_current_v5_authority_requires_refinement_transitions(self):
        self._retire_last_four()
        view = SimpleNamespace(
            fingerprint="sha256:" + "e" * 64,
            active_contributions=(
                SimpleNamespace(
                    contribution_id="intent:current:beta",
                    fingerprint="sha256:" + "b" * 64,
                ),
                SimpleNamespace(
                    contribution_id="intent:current:alpha",
                    fingerprint="sha256:" + "a" * 64,
                ),
            ),
        )
        revision = SimpleNamespace(current_effective_intent_view=view)

        with patch(
            "flowguard.model_revision_plan._accepted_revision_schema",
            return_value="flowguard.model_revision_set.v5",
        ), patch(
            "flowguard.model_revision_plan.load_current_accepted_revision_set",
            return_value=revision,
        ):
            report = preview_current_model_revision(
                self.root,
                snapshot_id="candidate:refine-current-intent",
            )

        self.assertTrue(report.ok)
        payload = report.to_dict()
        self.assertEqual("refine", payload["intent_mode"])
        self.assertEqual("model-revision-build", payload["required_command"])
        self.assertEqual(view.fingerprint, payload[
            "base_effective_intent_view_fingerprint"
        ])
        self.assertEqual(2, payload["required_transition_predecessor_count"])
        self.assertEqual(
            ["intent:current:alpha", "intent:current:beta"],
            [
                item["prior_contribution_id"]
                for item in payload["required_transition_predecessors"]
            ],
        )
        self.assertEqual(
            [
                "contributions",
                "dispositions",
                "effective_intent_transitions",
            ],
            payload["required_intent_input_kinds"],
        )
        self.assertEqual(0, payload["required_legacy_intent_entry_count"])
        self.assertTrue(payload["intent_input_identity_fingerprint"])

    def test_unknown_affected_owner_is_blocked_without_writes(self):
        self._retire_last_four()
        before = self._tree_identity()

        with patch(
            "flowguard.model_revision_plan.derive_revision_affected_closure",
            side_effect=ModelAuthorityError(
                "affected id has no native owner route: future:item"
            ),
        ):
            report = preview_current_model_revision(
                self.root,
                snapshot_id="candidate:unknown-owner",
            )

        self.assertFalse(report.ok)
        self.assertEqual(
            "affected_closure_unavailable",
            report.blockers[0].code,
        )
        self.assertIn("no native owner route", report.blockers[0].message)
        self.assertEqual(before, self._tree_identity())


class ModelRevisionPlanMissingAuthorityTests(unittest.TestCase):
    def test_missing_observed_authority_is_visibly_blocked(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            before = tuple(root.rglob("*"))

            report = preview_current_model_revision(
                root,
                snapshot_id="candidate:no-authority",
            )

            self.assertFalse(report.ok)
            self.assertEqual(
                "observed_authority_unavailable",
                report.blockers[0].code,
            )
            self.assertEqual(before, tuple(root.rglob("*")))

            output = StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "model-revision-plan",
                        "--root",
                        str(root),
                        "--snapshot-id",
                        "candidate:no-authority",
                        "--compact",
                        "--json",
                    ]
                )
            self.assertEqual(1, exit_code)
            cli_payload = json.loads(output.getvalue())
            self.assertEqual("blocked", cli_payload["status"])
            self.assertEqual(
                "observed_authority_unavailable",
                cli_payload["blockers"][0]["code"],
            )
            self.assertNotIn("snapshot_diff", cli_payload)
            self.assertNotIn("affected_closure", cli_payload)
            self.assertFalse(cli_payload["writes_performed"])
            self.assertFalse(cli_payload["models_executed"])
            self.assertEqual(before, tuple(root.rglob("*")))


if __name__ == "__main__":
    unittest.main()
