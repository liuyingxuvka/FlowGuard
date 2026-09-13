import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flowguard.completion_run_manifest import (
    CompletionRunManifestError,
    build_manifest,
    compare_manifest,
    invocation_projection,
    load_manifest,
    validate_manifest,
    write_manifest,
)
from flowguard.validation_owner_execution import canonical_semantic_command
from scripts import check_flowguard_skill_suite as suite_command


class CompletionRunManifestTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "repo"
        self.root.mkdir()
        self.receipt_root = self.root / "receipts"
        self.args = SimpleNamespace(
            output_dir=str(self.root / "run-a"),
            model_receipt_dir=str(self.root / "model-receipts"),
            completion_objective_change="close-runtime-evidence-and-task-map",
            formal_root=str(self.root / "formal"),
            shadow_root=str(self.root / "shadow"),
            installed_root=str(self.root / "installed"),
            model_jobs=4,
            model_timeout=900.0,
            gate_timeout=900.0,
            require_executed_evidence=True,
            skillguard="all",
            completion_repair_link=str(self.root / "repair-link.json"),
        )
        self.specs = (
            SimpleNamespace(
                child_id="child-a",
                command=("python", "-m", "child", "--output-dir", "run-a"),
            ),
        )
        self.owner_plan = SimpleNamespace(plan_fingerprint="sha256:" + "1" * 64)
        self.epoch = SimpleNamespace(
            epoch_id="epoch:test",
            completion_cycle_id="cycle:test",
            completion_objective_fingerprint="sha256:" + "2" * 64,
            source_observation_fingerprint="sha256:" + "3" * 64,
            release_tree_fingerprint="sha256:" + "4" * 64,
            toolchain_environment_fingerprint="sha256:" + "5" * 64,
            owner_dag_fingerprint="sha256:" + "6" * 64,
            model_authority_fingerprint="sha256:" + "7" * 64,
            test_inventory_fingerprint="sha256:" + "8" * 64,
            required_terminal_action_ids=("child-a",),
            remaining_governed_write_ids=(),
            repair_link=None,
        )

    def manifest(
        self,
        *,
        output_dir: str | None = None,
        model_jobs: int | None = None,
        command_output: str = "run-a",
    ):
        args = SimpleNamespace(**vars(self.args))
        if output_dir is not None:
            args.output_dir = output_dir
        if model_jobs is not None:
            args.model_jobs = model_jobs
        specs = (
            SimpleNamespace(
                child_id="child-a",
                command=("python", "-m", "child", "--output-dir", command_output),
            ),
        )
        return build_manifest(
            args=args,
            root=self.root,
            receipt_root=self.receipt_root,
            specs=specs,
            owner_plan=self.owner_plan,
            completion_epoch=self.epoch,
            canonicalize_command=canonical_semantic_command,
            readiness_fingerprint="sha256:" + "9" * 64,
        )

    def test_output_directory_is_not_part_of_frozen_identity(self):
        first = self.manifest(
            output_dir=str(self.root / "run-a"),
            command_output=str(self.root / "run-a"),
        )
        second = self.manifest(
            output_dir=str(self.root / "run-b"),
            command_output=str(self.root / "run-b"),
        )
        self.assertEqual(first["manifest_fingerprint"], second["manifest_fingerprint"])
        self.assertEqual((), compare_manifest(first, second))

    def test_resource_timeout_value_is_not_part_of_functional_command_identity(self):
        first = canonical_semantic_command(
            ("python", "-m", "child", "--run-timeout", "900"),
            resource_options=("--run-timeout",),
        )
        second = canonical_semantic_command(
            ("python", "-m", "child", "--run-timeout", "6000"),
            resource_options=("--run-timeout",),
        )
        self.assertEqual(first, second)
        self.assertIn("<RESOURCE_POLICY>", first)

    def test_unregistered_timeout_remains_functional_command_identity(self):
        first = canonical_semantic_command(
            ("python", "-m", "child", "--timeout", "2")
        )
        second = canonical_semantic_command(
            ("python", "-m", "child", "--timeout", "5")
        )
        self.assertNotEqual(first, second)
        self.assertNotIn("<RESOURCE_POLICY>", first)

    def test_semantic_invocation_change_is_field_addressable(self):
        first = self.manifest()
        second = self.manifest(model_jobs=8)
        differences = compare_manifest(
            first,
            second,
            ignore_fields=("manifest_fingerprint",),
        )
        self.assertEqual(("invocation.model_jobs",), tuple(item["field"] for item in differences))

    def test_model_receipt_directory_is_part_of_frozen_invocation(self):
        first = self.manifest()
        args = SimpleNamespace(**vars(self.args))
        args.model_receipt_dir = str(self.root / "model-receipts-2")
        changed = build_manifest(
            args=args,
            root=self.root,
            receipt_root=self.receipt_root,
            specs=self.specs,
            owner_plan=self.owner_plan,
            completion_epoch=self.epoch,
            canonicalize_command=canonical_semantic_command,
            readiness_fingerprint="sha256:" + "9" * 64,
        )
        differences = compare_manifest(
            first,
            changed,
            ignore_fields=("manifest_fingerprint",),
        )
        self.assertEqual(
            ("invocation.model_receipt_dir",),
            tuple(item["field"] for item in differences),
        )

    def test_work_id_and_claim_scope_are_frozen_with_the_epoch(self):
        args = SimpleNamespace(**vars(self.args))
        args.completion_work_id = "work:manifest-bound"
        args.claim_scope = "local_validation"
        epoch = SimpleNamespace(**vars(self.epoch))
        epoch.completion_work_id = "work:manifest-bound"
        epoch.claim_scope = "local_validation"
        manifest = build_manifest(
            args=args,
            root=self.root,
            receipt_root=self.receipt_root,
            specs=self.specs,
            owner_plan=self.owner_plan,
            completion_epoch=epoch,
            canonicalize_command=canonical_semantic_command,
            readiness_fingerprint="sha256:" + "9" * 64,
        )
        self.assertEqual(
            "work:manifest-bound",
            manifest["invocation"]["completion_work_id"],
        )
        self.assertEqual("local_validation", manifest["plan"]["claim_scope"])

        mismatched = SimpleNamespace(**vars(args))
        mismatched.completion_work_id = "work:other"
        with self.assertRaises(CompletionRunManifestError):
            build_manifest(
                args=mismatched,
                root=self.root,
                receipt_root=self.receipt_root,
                specs=self.specs,
                owner_plan=self.owner_plan,
                completion_epoch=epoch,
                canonicalize_command=canonical_semantic_command,
                readiness_fingerprint="sha256:" + "9" * 64,
            )

    def test_write_load_is_idempotent_and_tamper_evident(self):
        path = self.root / "run-a" / "completion-run-manifest.json"
        manifest = self.manifest()
        self.assertEqual(path, write_manifest(path, manifest))
        self.assertEqual(manifest, load_manifest(path))
        self.assertEqual(path, write_manifest(path, manifest))

        tampered = json.loads(path.read_text(encoding="utf-8"))
        tampered["invocation"]["model_jobs"] = 99
        with self.assertRaises(CompletionRunManifestError):
            validate_manifest(tampered)

    def test_missing_cli_manifest_blocks_before_owner_observation(self):
        args = suite_command.build_parser().parse_args(
            [
                "--scope",
                "full",
                "--root",
                str(self.root),
                "--shadow-root",
                str(self.root),
                "--completion-readiness",
                str(self.root / "readiness.json"),
                "--completion-run-manifest",
                str(self.root / "missing-manifest.json"),
            ]
        )
        with patch.object(
            suite_command,
            "observe_validation_owners",
            side_effect=AssertionError("owner observation must not start"),
        ) as observe:
            result = suite_command.run_full_validation(args)
        self.assertEqual("blocked", result.status)
        self.assertEqual("completion_run_manifest_missing", result.blockers[0]["code"])
        observe.assert_not_called()

    def test_invocation_mismatch_blocks_before_owner_observation(self):
        manifest_path = self.root / "completion-run-manifest.json"
        write_manifest(manifest_path, self.manifest())
        args = suite_command.build_parser().parse_args(
            [
                "--scope",
                "full",
                "--root",
                str(self.root),
                "--formal-root",
                str(self.root / "formal"),
                "--shadow-root",
                str(self.root / "shadow"),
                "--installed-root",
                str(self.root / "installed"),
                "--receipt-dir",
                str(self.receipt_root),
                "--model-jobs",
                "8",
                "--model-timeout",
                "900",
                "--gate-timeout",
                "900",
                "--require-executed-evidence",
                "--completion-objective-change",
                self.args.completion_objective_change,
                "--completion-readiness",
                str(self.root / "readiness.json"),
                "--completion-run-manifest",
                str(manifest_path),
            ]
        )
        with patch.object(
            suite_command,
            "observe_validation_owners",
            side_effect=AssertionError("owner observation must not start"),
        ) as observe:
            result = suite_command.run_full_validation(args)
        self.assertEqual("blocked", result.status)
        self.assertEqual(
            "completion_run_manifest_invocation_mismatch",
            result.blockers[0]["code"],
        )
        self.assertIn(
            "invocation.model_jobs",
            [item["field"] for item in result.blockers[0]["differences"]],
        )
        observe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
