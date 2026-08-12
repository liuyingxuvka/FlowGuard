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

from flowguard.evidence_receipts import fingerprint_value
from flowguard.process_supervision import (
    SupervisedCommandResult,
    _attest_supervised_result,
)
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
            "scripts/run_flowguard_skill_native_checks.py",
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
        if "flowguard-self-blueprint-check" in command:
            if "--include-architecture-reduction" in command:
                return "self_maintenance_review"
            return "self_blueprint"
        if "project-audit" in command:
            return "project_audit"
        if "check_flowguard_skill_suite.py" in joined:
            return "skill_suite_static"
        if "check_flowguard_self_governance.py" in joined:
            return "skill_self_governance"
        if "run_flowguard_skill_native_checks.py" in joined:
            return "skill_native_checks"
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
            override = overrides.get(child_id, "pass")
            raw_status = (
                str(override.get("status", "pass"))
                if isinstance(override, dict)
                else str(override)
            )
            payload = {
                "status": raw_status,
                "ok": raw_status == "pass",
                "claim_boundary": f"fixture boundary for {child_id}",
                "receipt_id": f"receipt-{child_id}",
            }
            if child_id == "self_maintenance_review":
                reduction = {
                    "projection_kind": "reduction",
                    "review_fingerprint": "sha256:" + "a" * 64,
                }
                reduction["projection_fingerprint"] = fingerprint_value(reduction)
                payload["architecture_reduction_review"] = reduction
            if isinstance(override, dict):
                payload.update(override)
            exit_code = 0 if raw_status in {"pass", "pass_with_gaps"} else 1
            supervision = _attest_supervised_result(
                SupervisedCommandResult(
                    command=tuple(command),
                    cwd=str(Path(cwd).resolve()),
                    episode_token=f"episode:fixture:{child_id}:{raw_status}",
                    started_at_epoch=1.0,
                    finished_at_epoch=2.0,
                    exit_code=exit_code,
                    stdout=json.dumps(payload),
                    stderr=f"trace for {child_id}\n",
                    terminal_reason="process_exit",
                    timed_out=False,
                    cancelled=False,
                    interrupted=False,
                    termination_stage="none",
                    cleanup_confirmed=True,
                    descendant_process_ids=(),
                    root_process_id=None,
                    root_process_running=False,
                    containment_query_succeeded=True,
                    contained_process_ids_before_cleanup=(),
                )
            )
            return suite_command.CommandOutcome(
                tuple(command),
                exit_code,
                stdout=json.dumps(payload),
                stderr=f"trace for {child_id}\n",
                payload=payload,
                supervision=supervision,
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

    def test_release_tree_rehashes_only_an_unstaged_worktree_change(self):
        source = self.root / "changed.txt"
        source.write_text("staged\n", encoding="utf-8")
        subprocess.run(
            ("git", "add", "changed.txt"),
            cwd=self.root,
            check=True,
        )
        staged_blob = subprocess.check_output(
            ("git", "ls-files", "--stage", "--", "changed.txt"),
            cwd=self.root,
            text=True,
        ).split()[1]
        source.write_text("unstaged\n", encoding="utf-8")

        row = next(
            item
            for item in release_tree_manifest(self.root)
            if item["path"] == "changed.txt"
        )

        self.assertNotEqual(staged_blob, row["blob_id"])
        self.assertEqual(
            subprocess.check_output(
                (
                    "git",
                    "hash-object",
                    "--path=changed.txt",
                    "--",
                    "changed.txt",
                ),
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
<<<<<<< HEAD
        self.assertEqual(10, len(result.children))
=======
        self.assertEqual(9, len(result.children))
>>>>>>> agent/harden-currentness-validation
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
<<<<<<< HEAD
        self.assertEqual(10, len(parent["children"]))
=======
        self.assertEqual(9, len(parent["children"]))
>>>>>>> agent/harden-currentness-validation
        self.assertNotIn("result", parent["children"][0]["payload"])
        self.assertTrue((self.output / "evidence-run.json").is_file())
        self.assertTrue((self.output.parent / "CURRENT.json").is_file())
        parent_head = json.loads((self.output.parent / "CURRENT.json").read_text(encoding="utf-8"))
        self.assertEqual("parent", parent_head["authority_kind"])
        self.assertTrue(gzip.decompress(Path(model_child.artifact_paths[0]).read_bytes()))

    def test_static_child_publishes_only_child_authority(self):
        child_run = Path(self.temporary.name) / "parent-run" / "static-suite"
        suite_command._write_static_result(
            {"status": "pass"},
            str(child_run),
            authority_kind="child",
            parent_scope="full-validation",
        )

        child_head = json.loads(
            (child_run.parent / "CURRENT.json").read_text(encoding="utf-8")
        )
        self.assertEqual("child", child_head["authority_kind"])
        self.assertEqual("full-validation", child_head["parent_scope"])
        self.assertFalse((child_run.parent.parent / "CURRENT.json").exists())

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

<<<<<<< HEAD
    def test_native_receipts_use_a_store_separate_from_validation_lifecycle(self):
        specs = {
            item.child_id: item
            for item in suite_command._full_child_specs(self.args(), self.root)
        }
        native = specs["skill_native_checks"].command
        parent = specs["skill_self_governance"].command
        native_root = Path(native[native.index("--output-dir") + 1])
        parent_root = Path(parent[parent.index("--output-directory") + 1])

        self.assertIn("--resume", native)
        self.assertEqual(native_root, parent_root)
        self.assertEqual(
            self.root / ".flowguard" / "evidence" / "skill-native-receipts",
            native_root,
        )
        self.assertNotEqual(self.output.parent, native_root)

    def test_owner_graph_contains_only_receipt_consumption_edges(self):
        specs = tuple(suite_command._full_child_specs(self.args(), self.root))
        contracts = {
            item.owner_id: item
            for item in suite_command._owner_contracts(specs)
        }
        self.assertEqual(
            ("skill_native_checks",),
            contracts["skill_self_governance"].dependency_owner_ids,
        )
        self.assertEqual(
            ("model_regressions_full",),
            contracts["self_maintenance_review"].dependency_owner_ids,
        )
        for owner_id, contract in contracts.items():
            if owner_id not in {"skill_self_governance", "self_maintenance_review"}:
                self.assertEqual((), contract.dependency_owner_ids)
            self.assertTrue(contract.resource_keys)
        self.assertEqual(
            contracts["skill_native_checks"].resource_keys,
            contracts["skill_self_governance"].resource_keys,
        )
        self.assertNotEqual(
            contracts["project_audit"].resource_keys,
            contracts["skill_suite_static"].resource_keys,
        )

    def test_project_audit_failure_does_not_block_unrelated_owners(self):
        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor({"project_audit": "fail"}),
        ) as execute:
            result = suite_command.run_full_validation(self.args())

        self.assertEqual("blocked", result.status)
        executed = {self.child_id(call.args[0]) for call in execute.call_args_list}
        self.assertIn("project_audit", executed)
        self.assertIn("skill_suite_static", executed)
        self.assertIn("pytest", executed)
        self.assertEqual(10, len(executed))

    def test_native_failure_only_blocks_self_governance(self):
        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor({"skill_native_checks": "fail"}),
        ) as execute:
            result = suite_command.run_full_validation(self.args())

        self.assertEqual("blocked", result.status)
        native = next(item for item in result.children if item.child_id == "skill_native_checks")
        self_governance = next(item for item in result.children if item.child_id == "skill_self_governance")
        self.assertEqual("fail", native.status)
        self.assertEqual("blocked", self_governance.status)
        executed = {self.child_id(call.args[0]) for call in execute.call_args_list}
        self.assertIn("model_regressions_full", executed)
        self.assertIn("self_maintenance_review", executed)

    def test_model_failure_only_blocks_self_maintenance(self):
        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor({"model_regressions_full": "fail"}),
        ) as execute:
            result = suite_command.run_full_validation(self.args())

        self.assertEqual("blocked", result.status)
        model = next(item for item in result.children if item.child_id == "model_regressions_full")
        maintenance = next(item for item in result.children if item.child_id == "self_maintenance_review")
        self.assertEqual("fail", model.status)
        self.assertEqual("blocked", maintenance.status)
        executed = {self.child_id(call.args[0]) for call in execute.call_args_list}
        self.assertIn("skill_native_checks", executed)
        self.assertIn("skill_self_governance", executed)

    def test_failed_native_run_reuses_unaffected_owner_receipts(self):
        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor({"skill_native_checks": "fail"}),
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

        # The failed native owner also blocks its dependent self-governance
        # owner, so the release parent is blocked rather than claiming a
        # complete failure-only outcome.
        self.assertEqual("blocked", first.status)
        self.assertTrue(second.broad_success)
        self.assertEqual({"skill_native_checks", "skill_self_governance"}, {
            self.child_id(call.args[0]) for call in execute.call_args_list
        })
        self.assertEqual(8, second.counts["reused"])

    def test_full_pytest_timeout_covers_the_observed_release_suite_runtime(self):
        specs = {
            item.child_id: item
            for item in suite_command._full_child_specs(self.args(), self.root)
        }

        self.assertEqual(3600.0, specs["pytest"].timeout_seconds)
        self.assertEqual(900.0, specs["openspec_strict"].timeout_seconds)

    def test_static_owner_declares_self_maintenance_route_registry_input(self):
        specs = {
            item.child_id: item
            for item in suite_command._full_child_specs(self.args(), self.root)
        }

        self.assertIn("flowguard/self_maintenance.py", specs["skill_suite_static"].input_patterns)

    def test_self_maintenance_review_publishes_compact_projection(self):
        specs = {
            item.child_id: item
            for item in suite_command._full_child_specs(self.args(), self.root)
        }

        spec = specs["self_maintenance_review"]
        self.assertIn("--compact", spec.command)
        self.assertIn("--require-cleanup-release-ready", spec.command)
        requirement = spec.result_identity_requirement
        self.assertIsNotNone(requirement)
        self.assertEqual(
            ("architecture_reduction_review",),
            requirement.source_path,
        )
        self.assertEqual(
            ("review_fingerprint", "projection_fingerprint"),
            requirement.fingerprint_fields,
        )
        contracts = {
            item.owner_id: item
            for item in suite_command._owner_contracts(tuple(specs.values()))
        }
        self.assertIn(
            ("result_identity_requirement", requirement.fingerprint),
            contracts["self_maintenance_review"].projected_inputs,
        )

    def test_self_maintenance_owner_receipt_exposes_both_verified_identities(self):
        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor(),
        ):
            result = suite_command.run_full_validation(self.args())

        self.assertTrue(result.broad_success)
        receipt_root = (
            self.root / ".flowguard" / "evidence" / "validation-owners"
        )
        receipt = next(
            json.loads(path.read_text(encoding="utf-8"))
            for path in receipt_root.glob("*.json")
            if json.loads(path.read_text(encoding="utf-8")).get("subject_id")
            == "validation-owner:self_maintenance_review"
        )
        proof = json.loads(
            (receipt_root / receipt["metadata"]["proof_relpath"]).read_text(
                encoding="utf-8"
            )
        )
        identity = proof["child"]["payload"]["result_identity_projection"]
        self.assertEqual("sha256:" + "a" * 64, identity["review_fingerprint"])
        self.assertTrue(identity["projection_fingerprint"].startswith("sha256:"))

    def test_self_maintenance_identity_missing_blocks_green_owner_receipt(self):
        invalid_review = {
            "status": "pass",
            "architecture_reduction_review": {
                "review_fingerprint": "sha256:" + "a" * 64,
            },
        }
        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor(
                {"self_maintenance_review": invalid_review}
            ),
        ):
            result = suite_command.run_full_validation(self.args())

        self.assertFalse(result.broad_success)
        child = next(
            item
            for item in result.children
            if item.child_id == "self_maintenance_review"
        )
        self.assertEqual("internal_error", child.status)
        self.assertIn(
            "validation_owner_result_identity_missing:"
            "architecture_reduction_review.projection_fingerprint",
            child.summary,
        )
        receipt_root = (
            self.root / ".flowguard" / "evidence" / "validation-owners"
        )
        self.assertFalse(
            any(
                json.loads(path.read_text(encoding="utf-8")).get("subject_id")
                == "validation-owner:self_maintenance_review"
                for path in receipt_root.glob("*.json")
            )
        )

    def test_identical_second_full_request_reuses_all_ten_owners(self):
=======
    def test_identical_second_full_request_reuses_all_nine_owners(self):
>>>>>>> agent/harden-currentness-validation
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
<<<<<<< HEAD
        self.assertEqual(10, first_execute.call_count)
        second_execute.assert_not_called()
        self.assertEqual(10, second.counts["reused"])
        self.assertEqual(0, second.counts["executed"])
        self.assertEqual(0, second.progress_summary["producer_invocations"])
        self.assertEqual(10, second.progress_summary["avoided_producer_invocations"])
=======
        self.assertEqual(9, first_execute.call_count)
        second_execute.assert_not_called()
        self.assertEqual(9, second.counts["reused"])
        self.assertEqual(0, second.counts["executed"])
        self.assertEqual(0, second.progress_summary["producer_invocations"])
        self.assertEqual(9, second.progress_summary["avoided_producer_invocations"])
>>>>>>> agent/harden-currentness-validation
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
        self.assertEqual(2, execute.call_count)
        self.assertEqual(
            {
                "openspec_strict",
                "self_maintenance_review",
            },
            {
                self.child_id(call.args[0])
                for call in execute.call_args_list
            },
        )
        self.assertEqual(8, second.counts["reused"])
<<<<<<< HEAD
        self.assertEqual(2, second.counts["executed"])
        self.assertEqual(2, second.progress_summary["producer_invocations"])
        self.assertEqual(8, second.progress_summary["avoided_producer_invocations"])
        self.assertEqual(0.8, second.progress_summary["estimated_work_avoided_fraction"])
=======
        self.assertEqual(1, second.counts["executed"])
        self.assertEqual(1, second.progress_summary["producer_invocations"])
        self.assertEqual(8, second.progress_summary["avoided_producer_invocations"])
        self.assertEqual(0.889, second.progress_summary["estimated_work_avoided_fraction"])
>>>>>>> agent/harden-currentness-validation

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
<<<<<<< HEAD
        self.assertEqual(9, second.counts["reused"])
=======
        self.assertEqual(8, second.counts["reused"])
>>>>>>> agent/harden-currentness-validation

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
