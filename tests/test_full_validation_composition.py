import argparse
import contextlib
import gzip
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flowguard.validation_ownership import release_tree_manifest
from scripts import check_flowguard_skill_suite as suite_command


class FullValidationCompositionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "formal"
        self.shadow = Path(self.temporary.name) / "shadow"
        self.installed = Path(self.temporary.name) / "installed"
        self.output = Path(self.temporary.name) / "artifacts"
        (self.root / "scripts").mkdir(parents=True)
        self.shadow.mkdir()
        self.installed.mkdir()
        for relative in (
            "scripts/check_flowguard_self_governance.py",
            "scripts/run_flowguard_model_regressions.py",
            "scripts/install_flowguard_skills.py",
        ):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# fixture\n", encoding="utf-8")
        subprocess.run(("git", "init", "-q"), cwd=self.root, check=True)
        subprocess.run(
            ("git", "config", "user.email", "fixture@example.invalid"),
            cwd=self.root,
            check=True,
        )
        subprocess.run(
            ("git", "config", "user.name", "FlowGuard Fixture"),
            cwd=self.root,
            check=True,
        )
        subprocess.run(("git", "add", "."), cwd=self.root, check=True)
        subprocess.run(
            ("git", "commit", "-q", "-m", "fixture"),
            cwd=self.root,
            check=True,
        )

    def args(self) -> argparse.Namespace:
        return suite_command.build_parser().parse_args(
            [
                "--scope",
                "full",
                "--root",
                str(self.root),
                "--output-dir",
                str(self.output),
                "--formal-root",
                str(self.root),
                "--shadow-root",
                str(self.shadow),
                "--installed-root",
                str(self.installed),
                "--model-jobs",
                "3",
                "--model-timeout",
                "19",
            ]
        )

    def test_external_consumer_fingerprint_ignores_unrelated_installed_skills(self):
        initial = suite_command._external_tree_fingerprint(self.installed)
        unrelated = self.installed / "unrelated-plugin" / "large.bin"
        unrelated.parent.mkdir(parents=True)
        unrelated.write_bytes(b"x" * 4096)

        self.assertEqual(
            initial,
            suite_command._external_tree_fingerprint(self.installed),
        )

        managed = self.installed / "flowguard" / "SKILL.md"
        managed.parent.mkdir(parents=True)
        managed.write_text("# current FlowGuard\n", encoding="utf-8")
        self.assertNotEqual(
            initial,
            suite_command._external_tree_fingerprint(self.installed),
        )

    @staticmethod
    def child_id(command):
        joined = " ".join(command)
        if "project-audit" in command:
            return "project_audit"
        if "check_flowguard_skill_suite.py" in joined:
            return "skill_suite_static"
        if "check_flowguard_self_governance.py" in joined:
            return "skill_self_governance"
        if "run_flowguard_model_regressions.py" in joined:
            return "model_regressions_full"
        if tuple(command[1:3]) == ("-m", "pytest"):
            return "pytest"
        if Path(command[0]).stem.lower().startswith("openspec"):
            return "openspec_strict"
        if "install_flowguard_skills.py" in joined and "parity" in command:
            return "distribution_parity"
        if "install_flowguard_skills.py" in joined and "check" in command:
            return "distribution_check"
        raise AssertionError(f"unknown fixture command: {command}")

    def executor(self, overrides=None):
        overrides = overrides or {}

        def fake(command, cwd, timeout_seconds=900.0):
            child_id = self.child_id(command)
            raw_status = overrides.get(child_id, "pass")
            payload = {
                "status": raw_status,
                "ok": raw_status == "pass",
                "claim_boundary": f"fixture boundary for {child_id}",
                "receipt_id": f"receipt-{child_id}",
            }
            exit_code = 0 if raw_status in {"pass", "pass_with_gaps"} else 1
            return suite_command.CommandOutcome(
                tuple(command),
                exit_code,
                stdout=json.dumps(payload),
                stderr=f"trace for {child_id}\n",
                payload=payload,
            )

        return fake

    def test_default_scope_remains_static(self):
        args = suite_command.build_parser().parse_args([])
        self.assertEqual("static", args.scope)
        with patch.object(suite_command, "run_static_suite", return_value={"ok": True, "passed_members": 15, "total_members": 15, "blockers": [], "members": []}) as run:
            with patch("builtins.print"):
                exit_code = suite_command.main(["--root", str(self.root)])
        self.assertEqual(0, exit_code)
        run.assert_called_once()

    def test_release_tree_blocks_ignored_model_authority_until_tracked(self):
        snapshot_digest = "1" * 64
        previous_digest = "2" * 64
        revision_digest = "3" * 64
        activation_digest = "4" * 64
        project_manifest = self.root / ".flowguard" / "project.toml"
        project_manifest.parent.mkdir(parents=True)
        project_manifest.write_text(
            "\n".join(
                (
                    "[flowguard]",
                    'adopted_package_version = "0.64.0"',
                    "",
                    "[model_authority]",
                    'system_id = "fixture"',
                    "observed_snapshot_path = "
                    f'".flowguard/model-mesh/snapshots/{snapshot_digest}.json"',
                    "observed_snapshot_fingerprint = "
                    f'"sha256:{snapshot_digest}"',
                    'subject_revision = "source-inventory:fixture"',
                    'coverage_status = "complete_within_declared_boundary"',
                    "generation = 2",
                    "accepted_revision_set_fingerprint = "
                    f'"sha256:{revision_digest}"',
                    "previous_snapshot_fingerprint = "
                    f'"sha256:{previous_digest}"',
                    "activation_receipt_fingerprint = "
                    f'"sha256:{activation_digest}"',
                    'head_fingerprint = "sha256:' + "5" * 64 + '"',
                    "",
                )
            ),
            encoding="utf-8",
        )
        required = (
            f".flowguard/model-mesh/snapshots/{snapshot_digest}.json",
            f".flowguard/model-mesh/snapshots/{previous_digest}.json",
            f".flowguard/model-mesh/revisions/{revision_digest}.json",
            f".flowguard/model-mesh/activations/{activation_digest}.json",
        )
        (self.root / ".gitignore").write_text(".flowguard/\n", encoding="utf-8")
        subprocess.run(
            ("git", "add", ".gitignore"),
            cwd=self.root,
            check=True,
        )
        subprocess.run(
            ("git", "add", "-f", ".flowguard/project.toml"),
            cwd=self.root,
            check=True,
        )
        for relative in required:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = (
                '{"model_instances":[]}\n'
                if relative == required[0]
                else "{}\n"
            )
            path.write_text(payload, encoding="utf-8")

        with self.assertRaisesRegex(
            ValueError,
            "required public model authority paths are not tracked",
        ):
            release_tree_manifest(self.root)

        subprocess.run(
            ("git", "add", "-f", *required),
            cwd=self.root,
            check=True,
        )
        paths = {row["path"] for row in release_tree_manifest(self.root)}
        self.assertTrue(set(required).issubset(paths))

    def test_release_tree_applies_git_clean_filters_to_worktree_content(self):
        attributes = self.root / ".gitattributes"
        source = self.root / "filtered.txt"
        attributes.write_text("*.txt text eol=lf\n", encoding="utf-8")
        source.write_bytes(b"first\r\nsecond\r\n")
        subprocess.run(
            ("git", "add", ".gitattributes", "filtered.txt"),
            cwd=self.root,
            check=True,
        )
        staged_blob = subprocess.check_output(
            ("git", "ls-files", "--stage", "--", "filtered.txt"),
            cwd=self.root,
            text=True,
        ).split()[1]

        row = next(
            item
            for item in release_tree_manifest(self.root)
            if item["path"] == "filtered.txt"
        )

        self.assertEqual(staged_blob, row["blob_id"])
        self.assertNotEqual(
            subprocess.check_output(
                ("git", "hash-object", "--no-filters", "filtered.txt"),
                cwd=self.root,
                text=True,
            ).strip(),
            row["blob_id"],
        )

    def test_v2_contract_projection_reuses_exact_depth_parity_hash(self):
        compiler = SimpleNamespace(ok=True, contract_hashes={"target": "ABC123"})
        depth = {
            "exit_code": 0,
            "payload": {
                "decision": "pass",
                "authority_decision": "current",
                "contract_hash": "ABC123",
                "manifest_hash": "MANIFEST",
            },
        }

        projected = suite_command._v2_contract_projection("target", compiler, depth)

        self.assertEqual(0, projected["exit_code"])
        self.assertEqual("pass", projected["payload"]["decision"])
        self.assertEqual("shared-v2-parity", projected["execution_mode"])

        stale = dict(depth)
        stale["payload"] = dict(depth["payload"], contract_hash="OLD")
        rejected = suite_command._v2_contract_projection("target", compiler, stale)
        self.assertEqual(1, rejected["exit_code"])
        self.assertEqual("fail", rejected["payload"]["decision"])

    def test_static_skillguard_check_binds_non_self_target_to_repository(self):
        skill = self.root / ".agents" / "skills" / "target"
        (skill / ".skillguard").mkdir(parents=True)
        (skill / ".skillguard" / "contract-source.json").write_text(
            json.dumps({"schema_version": "skillguard.contract_source.v2"}),
            encoding="utf-8",
        )
        cli = self.root / "skillguard.py"
        cli.write_text("# fixture\n", encoding="utf-8")
        inventory = SimpleNamespace(
            ok=True,
            declared_member_ids=("target",),
            inventory_hash="INVENTORY",
            semantic_hash="SEMANTIC",
            to_dict=lambda: {"ok": True},
        )
        compiler = SimpleNamespace(
            ok=True,
            compiler_version="current",
            route_registry_hash="ROUTES",
            contract_hashes={"target": "CONTRACT"},
            to_dict=lambda: {"ok": True},
        )
        commands = []

        def fake_run(command, cwd):
            commands.append(tuple(command))
            if "check-depth" in command:
                payload = {
                    "decision": "pass",
                    "authority_decision": "current",
                    "contract_hash": "CONTRACT",
                    "manifest_hash": "MANIFEST",
                    "depth_classification": "declared-contract-current",
                }
            else:
                payload = {"decision": "pass"}
            return {"exit_code": 0, "payload": payload, "stdout": "", "stderr": ""}

        with (
            patch.object(suite_command, "validate_skill_suite", return_value=inventory),
            patch.object(suite_command, "compile_skill_suite", return_value=compiler),
            patch.object(suite_command, "_skillguard_cli", return_value=cli),
            patch.object(suite_command, "_run_json_command", side_effect=fake_run),
        ):
            result = suite_command.run_static_suite(self.root)

        self.assertTrue(result["ok"])
        static = next(command for command in commands if "check-skill" in command)
        self.assertIn("--repository-root", static)
        self.assertEqual(str(self.root), static[static.index("--repository-root") + 1])

    def test_full_pass_retains_independent_child_artifacts(self):
        with patch.object(suite_command, "_execute_command", side_effect=self.executor()):
            result = suite_command.run_full_validation(self.args())

        self.assertTrue(result.broad_success)
        self.assertEqual(8, len(result.children))
        model_child = next(child for child in result.children if child.child_id == "model_regressions_full")
        self.assertIn("--jobs", model_child.payload["command"])
        self.assertIn("3", model_child.payload["command"])
        self.assertIn("--timeout", model_child.payload["command"])
        for child in result.children:
            self.assertEqual(3, len(child.artifact_paths))
            self.assertTrue(all(Path(path).is_file() for path in child.artifact_paths))
            result_artifact = json.loads(Path(child.artifact_paths[2]).read_text(encoding="utf-8"))
            self.assertEqual(child.child_id, result_artifact["child_id"])
            self.assertEqual(child.status, result_artifact["status"])
            self.assertNotIn("payload", result_artifact)
            self.assertEqual("gzip", result_artifact["stdout"]["compression"])
            self.assertEqual("gzip", result_artifact["stderr"]["compression"])
        parent = json.loads(Path(result.artifact_paths[0]).read_text(encoding="utf-8"))
        self.assertEqual("pass", parent["status"])
        self.assertEqual(8, len(parent["children"]))
        self.assertNotIn("result", parent["children"][0]["payload"])
        self.assertTrue((self.output / "evidence-run.json").is_file())
        self.assertTrue((self.output.parent / "CURRENT.json").is_file())
        self.assertTrue(gzip.decompress(Path(model_child.artifact_paths[0]).read_bytes()))

    def test_plan_only_executes_no_producer_and_writes_no_evidence(self):
        args = self.args()
        args.plan_only = True
        with patch.object(suite_command, "_execute_command") as execute:
            result = suite_command.run_full_validation(args)

        execute.assert_not_called()
        self.assertEqual("full-plan-only", result.scope)
        self.assertEqual(0, result.progress_summary["completed"])
        self.assertEqual((), result.artifact_paths)
        self.assertFalse(self.output.exists())
        self.assertFalse((self.output.parent / "CURRENT.json").exists())

    def test_identical_second_full_request_reuses_all_eight_owners(self):
        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor(),
        ) as first_execute:
            first = suite_command.run_full_validation(self.args())
        second_args = self.args()
        second_args.output_dir = str(Path(self.temporary.name) / "artifacts-second")
        with patch.object(suite_command, "_execute_command") as second_execute:
            second = suite_command.run_full_validation(second_args)

        self.assertTrue(first.broad_success)
        self.assertTrue(second.broad_success)
        self.assertEqual(8, first_execute.call_count)
        second_execute.assert_not_called()
        self.assertEqual(8, second.counts["reused"])
        self.assertEqual(0, second.counts["executed"])
        self.assertEqual(0, second.progress_summary["producer_invocations"])
        self.assertEqual(8, second.progress_summary["avoided_producer_invocations"])
        self.assertEqual(1.0, second.progress_summary["estimated_work_avoided_fraction"])
        self.assertGreaterEqual(second.progress_summary["elapsed_seconds"], 0.0)

    def test_one_changed_input_executes_only_its_declared_owner(self):
        openspec = self.root / "openspec" / "changes" / "fixture"
        openspec.mkdir(parents=True)
        source = openspec / "spec.md"
        source.write_text("# v1\n", encoding="utf-8")
        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor(),
        ):
            first = suite_command.run_full_validation(self.args())
        source.write_text("# v2\n", encoding="utf-8")
        second_args = self.args()
        second_args.output_dir = str(Path(self.temporary.name) / "artifacts-second")
        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor(),
        ) as execute:
            second = suite_command.run_full_validation(second_args)

        self.assertTrue(first.broad_success)
        self.assertTrue(second.broad_success)
        self.assertEqual(1, execute.call_count)
        self.assertEqual(
            "openspec_strict",
            self.child_id(execute.call_args.args[0]),
        )
        self.assertEqual(7, second.counts["reused"])
        self.assertEqual(1, second.counts["executed"])
        self.assertEqual(1, second.progress_summary["producer_invocations"])
        self.assertEqual(7, second.progress_summary["avoided_producer_invocations"])
        self.assertEqual(0.875, second.progress_summary["estimated_work_avoided_fraction"])

    def test_failed_parent_preserves_successful_children_for_next_run(self):
        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor({"distribution_parity": "fail"}),
        ):
            first = suite_command.run_full_validation(self.args())
        second_args = self.args()
        second_args.output_dir = str(Path(self.temporary.name) / "artifacts-second")
        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor(),
        ) as execute:
            second = suite_command.run_full_validation(second_args)

        self.assertEqual("fail", first.status)
        self.assertTrue(second.broad_success)
        self.assertEqual(1, execute.call_count)
        self.assertEqual(
            "distribution_parity",
            self.child_id(execute.call_args.args[0]),
        )
        self.assertEqual(7, second.counts["reused"])

    def test_tampered_owner_receipt_blocks_before_any_producer_starts(self):
        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor(),
        ):
            first = suite_command.run_full_validation(self.args())
        self.assertTrue(first.broad_success)
        receipt_root = (
            self.root / ".flowguard" / "evidence" / "validation-owners"
        )
        target = None
        for path in receipt_root.glob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("subject_id") == "validation-owner:openspec_strict":
                target = path
                payload["claim_boundary"] = "tampered"
                path.write_text(json.dumps(payload), encoding="utf-8")
                break
        self.assertIsNotNone(target)
        second_args = self.args()
        second_args.output_dir = str(Path(self.temporary.name) / "artifacts-second")
        with patch.object(suite_command, "_execute_command") as execute:
            second = suite_command.run_full_validation(second_args)

        execute.assert_not_called()
        self.assertEqual("blocked", second.status)
        self.assertFalse(second.children)
        blocked = next(
            item
            for item in second.blockers
            if item["child_id"] == "openspec_strict"
        )
        self.assertIn("content address mismatch", blocked["message"])
        self.assertFalse(Path(second_args.output_dir).exists())

    def test_large_child_payload_is_retained_once_as_compressed_evidence(self):
        child = self.output / "01-large"
        large_value = "x" * 1_000_000
        outcome = suite_command.CommandOutcome(
            ("fixture",),
            0,
            stdout=json.dumps({"value": large_value}),
            stderr="",
            payload={"value": large_value},
        )

        paths = suite_command._write_child_artifacts(
            child,
            child_id="large",
            status="pass",
            outcome=outcome,
        )

        result = json.loads(Path(paths[2]).read_text(encoding="utf-8"))
        self.assertNotIn("payload", result)
        self.assertNotIn(large_value, Path(paths[2]).read_text(encoding="utf-8"))
        stored_bytes = sum(path.stat().st_size for path in self.output.rglob("*") if path.is_file())
        self.assertLess(stored_bytes, 25_000)
        self.assertEqual(outcome.stdout.encode("utf-8"), gzip.decompress(Path(paths[0]).read_bytes()))

    def test_one_child_failure_is_preserved_and_blocks_full(self):
        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor({"distribution_parity": "fail"}),
        ):
            result = suite_command.run_full_validation(self.args())

        self.assertEqual("fail", result.status)
        parity = next(child for child in result.children if child.child_id == "distribution_parity")
        self.assertEqual("fail", parity.status)
        self.assertTrue(parity.payload["payload_sha256"].startswith("sha256:"))
        self.assertFalse(result.broad_success)

    def test_missing_tracked_required_script_blocks_during_parent_freeze(self):
        (self.root / "scripts/check_flowguard_self_governance.py").unlink()
        with self.assertRaisesRegex(ValueError, "release tree path is deleted"):
            suite_command.run_full_validation(self.args())
        self.assertFalse(self.output.exists())

    def test_pass_with_gaps_is_partial_not_broad_success(self):
        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor({"project_audit": "pass_with_gaps"}),
        ):
            result = suite_command.run_full_validation(self.args())

        project = next(child for child in result.children if child.child_id == "project_audit")
        self.assertEqual("partial", project.status)
        self.assertEqual("blocked", result.status)
        self.assertFalse(result.broad_success)
        self.assertTrue(any(item["child_id"] == "project_audit" for item in result.blockers))

    def test_required_skip_inside_nominal_pass_is_not_flattened(self):
        normal = self.executor()

        def with_required_skip(command, cwd, timeout_seconds=900.0):
            outcome = normal(command, cwd, timeout_seconds)
            if self.child_id(command) != "project_audit":
                return outcome
            payload = dict(outcome.payload)
            payload["skipped_checks"] = [
                {"check_id": "managed_rules", "reason": "fixture", "required": True}
            ]
            return suite_command.CommandOutcome(
                outcome.command,
                outcome.exit_code,
                stdout=json.dumps(payload),
                stderr=outcome.stderr,
                payload=payload,
            )

        with patch.object(suite_command, "_execute_command", side_effect=with_required_skip):
            result = suite_command.run_full_validation(self.args())

        project = next(child for child in result.children if child.child_id == "project_audit")
        self.assertEqual("partial", project.status)
        self.assertFalse(result.broad_success)

    def test_shadow_configuration_is_required_for_full_parity(self):
        args = self.args()
        args.shadow_root = None
        with patch.object(suite_command, "_execute_command", side_effect=self.executor()):
            result = suite_command.run_full_validation(args)

        self.assertEqual("blocked", result.status)
        self.assertEqual((), result.children)
        blocker = next(
            item
            for item in result.blockers
            if item["child_id"] == "distribution_parity"
        )
        self.assertIn("--shadow-root", blocker["message"])

    def test_invalid_full_configuration_uses_canonical_status_and_exit(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = suite_command.main(
                ["--scope", "full", "--model-jobs", "0", "--json"]
            )
        payload = json.loads(stdout.getvalue())
        self.assertEqual("invalid_input", payload["status"])
        self.assertEqual(3, exit_code)
        self.assertEqual(exit_code, payload["exit_code"])


if __name__ == "__main__":
    unittest.main()
