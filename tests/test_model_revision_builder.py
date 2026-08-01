import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from flowguard.__main__ import main
from flowguard.evidence_receipts import fingerprint_value
from flowguard.model_authority import ModelRevisionSet
from flowguard.model_authority_store import (
    bootstrap_model_authority,
    load_observed_model_system,
)
from flowguard.model_purpose import (
    build_model_purpose_closure,
    file_fingerprint,
)
from flowguard.model_regressions import MANIFEST_SCHEMA, run_manifest_regressions
from flowguard.model_revision_builder import build_current_model_revision
from flowguard.model_system_inventory import build_manifest_model_system_snapshot


class ModelRevisionBuilderTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.model_dir = self.root / ".flowguard" / "authority"
        self.model_dir.mkdir(parents=True)
        (self.model_dir / "run_checks.py").write_text(
            "print('authority checks pass')\n",
            encoding="utf-8",
        )
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

    def _write_current_model(self, source: str) -> None:
        model_path = self.model_dir / "model.py"
        runner_path = self.model_dir / "run_checks.py"
        model_path.write_text(source, encoding="utf-8")
        purpose = build_model_purpose_closure(
            model_instance_id="regression:authority:current",
            reusable_model_type_id="authority",
            task_intent_id="flowguard-regression:authority",
            guarded_purpose=(
                "Prevent the authority model from accepting stale or partial "
                "revision evidence as a current completed result."
            ),
            protected_failure_ids=("authority:stale-or-partial",),
            known_good_case_id="native-runner:authority:good",
            failure_bindings=(
                {
                    "failure_id": "authority:stale-or-partial",
                    "known_bad_case_id": "native-runner:authority:bad",
                    "oracle_id": "native:authority:runner",
                },
            ),
            claim_boundary=(
                "This temporary model proves only the declared revision-builder "
                "test boundary and no production behavior."
            ),
            evidence_check_ids=("check:authority",),
            model_sha256=file_fingerprint(model_path),
            runner_sha256=file_fingerprint(runner_path),
        )
        manifest = {
            "schema_version": MANIFEST_SCHEMA,
            "governed_input_globs": [".flowguard/**/*.py"],
            "snapshot_only_input_globs": [],
            "shared_input_groups": [],
            "models": [
                {
                    "model_id": "authority",
                    "model_path": ".flowguard/authority/model.py",
                    "runner": ["{python}", ".flowguard/authority/run_checks.py"],
                    "tier": "fast",
                    "timeout_seconds": 5,
                    "shard_safe": True,
                    "mutation_policy": "none",
                    "input_globs": [
                        ".flowguard/authority/model.py",
                        ".flowguard/authority/run_checks.py",
                    ],
                    "expected_artifacts": [],
                    "distribution_policy": "required_public",
                    "absence_reason": (
                        "This fixture owner is required inside its test boundary."
                    ),
                    "exclusion_reason": "",
                    "purpose_closure": purpose.to_dict(),
                }
            ],
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

    def test_builds_accepted_content_addressed_pair_without_activation(self):
        self._write_current_model("VALUE = 2\n")
        report = self._current_parent()
        head_before, _base = load_observed_model_system(self.root)

        built = build_current_model_revision(
            self.root,
            model_parent_receipt=report.parent_receipt_path,
            revision_set_id="revision:test-builder",
            task_id="task:test-builder",
            snapshot_id="observed-test-builder",
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

    def test_rejects_stale_parent_before_writing_outputs(self):
        self._write_current_model("VALUE = 2\n")
        report = self._current_parent()
        self._write_current_model("VALUE = 3\n")
        output_root = self.root / "candidate-output"

        with self.assertRaisesRegex(ValueError, "manifest fingerprint is stale"):
            build_current_model_revision(
                self.root,
                model_parent_receipt=report.parent_receipt_path,
                revision_set_id="revision:stale",
                task_id="task:stale",
                snapshot_id="observed-stale",
                output_root=output_root,
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
            )

    def test_cli_emits_activation_ready_paths_but_keeps_head(self):
        self._write_current_model("VALUE = 2\n")
        report = self._current_parent("cli-parent")
        head_before, _base = load_observed_model_system(self.root)
        output = StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "model-revision-build",
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
                    "--json",
                ]
            )

        payload = json.loads(output.getvalue())
        head_after, _still_base = load_observed_model_system(self.root)
        self.assertEqual(0, exit_code)
        self.assertEqual("pass", payload["status"])
        self.assertTrue(Path(payload["candidate_snapshot_path"]).is_file())
        self.assertTrue(Path(payload["revision_set_path"]).is_file())
        self.assertEqual(head_before, head_after)


if __name__ == "__main__":
    unittest.main()
