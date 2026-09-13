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
from flowguard.completion_epoch import CompletionEpochReadiness
from flowguard.process_supervision import (
    SupervisedCommandResult,
    _attest_supervised_result,
)
from flowguard.validation_ownership import (
    GitQueryTimeout,
    build_validation_owner_plan,
    build_validation_parent_current,
    observe_validation_owners,
    release_tree_manifest,
)
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

    def _with_completion_readiness(self, args: argparse.Namespace) -> argparse.Namespace:
        # Full validation intentionally requires a positive, plan-bound
        # readiness receipt.  The fixture supplies one so the composition
        # tests exercise owner execution/reuse rather than the production
        # missing-readiness blocker.
        planning_args = argparse.Namespace(**vars(args))
        # `run_full_validation` replaces the requested output with its actual
        # run directory immediately before constructing child specs; mirror
        # that identity here so the readiness test-inventory fingerprint is
        # byte-for-byte the same as the execution plan.
        planning_args.output_dir = str(args.output_dir)
        specs = suite_command._full_child_specs(planning_args, self.root)
        contracts = suite_command._owner_contracts(specs)
        receipt_root = self.root / ".flowguard" / "evidence" / "validation-owners"
        required_external = {
            component_id: fingerprint
            for contract in contracts
            for component_id, fingerprint in contract.external_component_bindings
        }
        observation = observe_validation_owners(
            self.root,
            contracts,
            receipt_root=receipt_root,
        )
        owner_plan = build_validation_owner_plan(
            self.root,
            contracts,
            receipt_root=receipt_root,
            required_external_components=required_external,
            observation=observation,
        )
        if owner_plan.blocked:
            # Some negative tests intentionally tamper with a persisted owner
            # receipt.  Preserve the production owner-plan blocker and do not
            # attempt to manufacture a readiness object for a plan that can
            # never become a parent current.
            return args
        parent_current = build_validation_parent_current(
            self.root,
            owner_plan,
            frozen_validation_manifest=owner_plan.validation_input_manifest,
            frozen_release_tree_manifest=owner_plan.release_tree_manifest,
        )
        completion_plan = suite_command._completion_epoch_plan(
            args=args,
            root=self.root,
            specs=specs,
            owner_plan=owner_plan,
            parent_current=parent_current,
            planning_observation=observation,
        )
        args.completion_readiness = CompletionEpochReadiness.for_plan(
            completion_plan,
            openspec_terminal_receipt_fingerprint="sha256:" + "8" * 64,
            external_roots_sync_receipt_fingerprint="sha256:" + "9" * 64,
            formal_shadow_installed_sync_receipt_fingerprint="sha256:" + "a" * 64,
            reverse_input_acceptance_receipt_fingerprint="sha256:" + "b" * 64,
            owner_dag_freeze_receipt_fingerprint="sha256:" + "c" * 64,
        )
        return args

    def args(self) -> argparse.Namespace:
        args = suite_command.build_parser().parse_args(
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
        return self._with_completion_readiness(args)

    def test_symlink_capability_is_owned_by_pytest_child_not_parent_admission(self):
        shard_script = self.root / "scripts" / "run_flowguard_pytest_shards.py"
        shard_script.write_text("# governed shard fixture\n", encoding="utf-8")
        args = suite_command.build_parser().parse_args(
            [
                "--scope",
                "full",
                "--root",
                str(self.root),
                "--shadow-root",
                str(self.shadow),
            ]
        )
        with patch.object(
            suite_command,
            "_load_completion_run_manifest",
            return_value=(None, None, "", ()),
        ), patch.object(
            suite_command,
            "observe_validation_owners",
            side_effect=AssertionError("owner observation reached"),
        ) as observe:
            with self.assertRaisesRegex(AssertionError, "owner observation reached"):
                suite_command.run_full_validation(args)
        observe.assert_called_once()

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

    def test_parent_current_projects_frozen_owner_manifests_without_rescanning(self):
        calls = []
        original = suite_command.build_validation_parent_current

        def capture(root, owner_plan, **kwargs):
            calls.append(kwargs)
            return original(root, owner_plan, **kwargs)

        with patch.object(
            suite_command,
            "build_validation_parent_current",
            side_effect=capture,
        ), patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor(),
        ):
            result = suite_command.run_full_validation(self.args())

        self.assertEqual("pass", result.status)
        self.assertGreaterEqual(len(calls), 3)
        self.assertTrue(
            all(
                tuple(kwargs.get("frozen_validation_manifest", ()))
                and tuple(kwargs.get("frozen_release_tree_manifest", ()))
                for kwargs in calls
            )
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
        if (
            "check_flowguard_skill_suite.py" in joined
            or "check_flowguard_author_skill_assurance.py" in joined
        ):
            return "skill_suite_light"
        if "check_flowguard_self_governance.py" in joined:
            return "skill_self_governance"
        if "run_flowguard_skill_native_checks.py" in joined:
            return "skill_native_checks"
        if "run_flowguard_model_regressions.py" in joined:
            return "model_regressions_full"
        if "run_flowguard_pytest_shards.py" in joined:
            return "pytest"
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

    def test_default_scope_is_light(self):
        args = suite_command.build_parser().parse_args([])
        self.assertEqual("light", args.scope)
        with patch.object(suite_command, "run_light_suite", return_value={"ok": True, "passed_members": 15, "total_members": 15, "blockers": [], "members": []}) as run:
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
                    f'".flowguard/models/authority/snapshots/{snapshot_digest}.json"',
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
            f".flowguard/models/authority/snapshots/{snapshot_digest}.json",
            f".flowguard/models/authority/snapshots/{previous_digest}.json",
            f".flowguard/models/authority/revisions/{revision_digest}.json",
            f".flowguard/models/authority/activations/{activation_digest}.json",
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

    def test_light_skillguard_currentness_does_not_start_skillguard_producers(self):
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
            members=(SimpleNamespace(skill_id="target", ok=True),),
            inventory_hash="INVENTORY",
            semantic_hash="SEMANTIC",
            to_dict=lambda: {"ok": True},
        )
        compiler = SimpleNamespace(
            ok=True,
            compiler_version="current",
            route_registry_hash="ROUTES",
            contract_hashes={"target": "CONTRACT"},
            findings=(),
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
            result = suite_command.run_light_suite(self.root)

        self.assertTrue(result["ok"])
        self.assertEqual([], commands)
        self.assertEqual(0, result["author_subprocess_count"])
        self.assertEqual(0, result["native_producer_count"])
        self.assertEqual(
            ["layout_shape", "adoption_pointer", "contract_parity"],
            result["checks_run"],
        )
        self.assertIn("author_check_skill", result["checks_not_run"])

    def test_full_pass_retains_independent_child_artifacts(self):
        with patch.object(suite_command, "_execute_command", side_effect=self.executor()):
            result = suite_command.run_full_validation(self.args())

        self.assertTrue(result.broad_success)
        self.assertEqual(10, len(result.children))
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
        self.assertEqual(10, len(parent["children"]))
        self.assertNotIn("result", parent["children"][0]["payload"])
        self.assertTrue((self.output / "evidence-run.json").is_file())
        self.assertTrue((self.output.parent / "CURRENT.json").is_file())
        parent_head = json.loads((self.output.parent / "CURRENT.json").read_text(encoding="utf-8"))
        self.assertEqual("parent", parent_head["authority_kind"])
        self.assertTrue(gzip.decompress(Path(model_child.artifact_paths[0]).read_bytes()))

    def test_full_run_uses_one_shared_freshness_boundary_and_terminal_epoch(self):
        with patch.object(suite_command, "_execute_command", side_effect=self.executor()):
            result = suite_command.run_full_validation(self.args())

        self.assertEqual("pass", result.status)
        counters = result.progress_summary["metrics"]["counters"]
        self.assertEqual(1, counters["source_manifest_builds"])
        self.assertEqual(1, counters["source_freshness_checks"])
        self.assertEqual(1, counters["receipt_batch_refreshes"])
        self.assertEqual(0, counters["per_leaf_source_current_rebuild_count"])
        self.assertEqual(0, counters["per_leaf_receipt_store_scan_count"])
        self.assertEqual(
            "terminal_pass",
            result.progress_summary["completion_epoch_ledger_status"],
        )
        self.assertTrue(
            Path(result.progress_summary["completion_epoch_ledger_path"]).is_file()
        )

    def test_light_child_publishes_only_child_authority(self):
        child_run = Path(self.temporary.name) / "parent-run" / "light-suite"
        suite_command._write_light_result(
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

    def test_local_validation_omits_release_tree_placeholder_owners(self):
        args = self.args()
        args.claim_scope = "local_validation"
        specs = {
            item.child_id: item
            for item in suite_command._full_child_specs(args, self.root)
        }

        self.assertNotIn("distribution_check", specs)
        self.assertNotIn("distribution_parity", specs)
        self.assertEqual(
            {
                "skill_native_checks",
                "model_regressions_full",
                "pytest",
            },
            set(specs),
        )

    def test_local_validation_completion_budget_matches_functional_owner_set(self):
        args = self.args()
        args.claim_scope = "local_validation"
        specs = suite_command._full_child_specs(args, self.root)
        self.assertEqual(
            tuple(spec.child_id for spec in specs),
            suite_command._required_child_ids(specs),
        )
        self.assertNotIn("distribution_check", suite_command._required_child_ids(specs))
        self.assertNotIn("distribution_parity", suite_command._required_child_ids(specs))

    def test_model_receipt_store_is_stable_and_shared_across_run_outputs(self):
        args = self.args()
        first_specs = {
            item.child_id: item
            for item in suite_command._full_child_specs(args, self.root)
        }
        stable_root = self.root / ".flowguard" / "evidence" / "model-owner-receipts"
        model_command = first_specs["model_regressions_full"].command
        blueprint_command = first_specs["self_maintenance_review"].command
        self.assertEqual("child", model_command[model_command.index("--authority-kind") + 1])
        self.assertEqual("full-validation", model_command[model_command.index("--parent-scope") + 1])
        self.assertEqual(
            stable_root,
            Path(model_command[model_command.index("--receipt-dir") + 1]),
        )
        self.assertEqual(
            stable_root,
            Path(blueprint_command[blueprint_command.index("--model-receipt-dir") + 1]),
        )

        args.model_receipt_dir = str(self.root / "stable-model-store")
        args.output_dir = str(Path(self.temporary.name) / "artifacts-second")
        second_specs = {
            item.child_id: item
            for item in suite_command._full_child_specs(args, self.root)
        }
        second_model = second_specs["model_regressions_full"].command
        second_blueprint = second_specs["self_maintenance_review"].command
        explicit_root = Path(args.model_receipt_dir).resolve()
        self.assertEqual(
            explicit_root,
            Path(second_model[second_model.index("--receipt-dir") + 1]),
        )
        self.assertEqual(
            explicit_root,
            Path(second_blueprint[second_blueprint.index("--model-receipt-dir") + 1]),
        )
        self.assertNotEqual(
            explicit_root,
            Path(args.output_dir).resolve() / "model-owner-receipts",
        )

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
        contracts["skill_suite_light"].resource_keys,
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
        self.assertIn("skill_suite_light", executed)
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

    def test_failed_native_run_requires_explicit_typed_repair_before_replay(self):
        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor({"skill_native_checks": "fail"}),
        ):
            first = suite_command.run_full_validation(self.args())
        second_args = self.args()
        second_args.output_dir = str(Path(self.temporary.name) / "artifacts-second")
        second_args = self._with_completion_readiness(second_args)
        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor(),
        ) as execute:
            second = suite_command.run_full_validation(second_args)

        # The failed native owner also blocks its dependent self-governance
        # owner.  A second invocation without the persisted typed repair link
        # must not spend another producer attempt or silently reopen the
        # finite completion cycle.
        self.assertEqual("blocked", first.status)
        self.assertEqual("blocked", second.status)
        execute.assert_not_called()
        self.assertTrue(
            any(
                "completion_cycle_attempt_already_consumed" in blocker["code"]
                or "completion_cycle_initial_attempt_already_consumed" in blocker["code"]
                or "completion_epoch_terminal_already_recorded" in blocker["code"]
                for blocker in second.blockers
            ),
            second.blockers,
        )

    def test_full_pytest_timeout_covers_the_observed_release_suite_runtime(self):
        specs = {
            item.child_id: item
            for item in suite_command._full_child_specs(self.args(), self.root)
        }

        self.assertEqual(3600.0, specs["pytest"].timeout_seconds)
        self.assertEqual(900.0, specs["openspec_strict"].timeout_seconds)

    def test_git_timeout_does_not_launch_validation_owner(self):
        args = suite_command.build_parser().parse_args(
            [
                "--scope",
                "full",
                "--root",
                str(self.root),
                "--output-dir",
                str(self.output),
                "--shadow-root",
                str(self.shadow),
            ]
        )
        timeout = GitQueryTimeout(
            code="git_query_timeout",
            query_category="ls-files",
            elapsed_seconds=30.0,
            cleanup_confirmed=True,
            terminal_reason="timeout",
        )
        with (
            patch.object(
                suite_command,
                "observe_validation_owners",
                side_effect=timeout,
            ),
            patch.object(suite_command, "_execute_command") as execute,
        ):
            with self.assertRaisesRegex(ValueError, "git_query_timeout"):
                suite_command.run_full_validation(args)

        execute.assert_not_called()

    def test_light_owner_declares_self_maintenance_route_registry_input(self):
        specs = {
            item.child_id: item
            for item in suite_command._full_child_specs(self.args(), self.root)
        }

        self.assertIn("flowguard/self_maintenance.py", specs["skill_suite_light"].input_patterns)

    def test_self_maintenance_review_publishes_compact_projection(self):
        specs = {
            item.child_id: item
            for item in suite_command._full_child_specs(self.args(), self.root)
        }

        spec = specs["self_maintenance_review"]
        self.assertIn("--compact", spec.command)
        # The full parent consumes the complete self-maintenance audit.  The
        # stricter architecture-cleanup gate remains available on the
        # standalone command, but proofless candidates are intentionally
        # visible as unresolved/risky-keep and must not deadlock the broader
        # model/test/release validation epoch.
        self.assertNotIn("--require-cleanup-release-ready", spec.command)
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
        dependency_bindings = proof["child"]["payload"]["dependency_receipt_bindings"]
        self.assertEqual(1, len(dependency_bindings))
        self.assertEqual("model_regressions_full", dependency_bindings[0]["owner_id"])
        self.assertTrue(dependency_bindings[0]["receipt_id"])
        self.assertTrue(dependency_bindings[0]["receipt_fingerprint"].startswith("sha256:"))

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
        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor(),
        ) as first_execute:
            first = suite_command.run_full_validation(self.args())
        second_args = self.args()
        second_args.output_dir = str(Path(self.temporary.name) / "artifacts-second")
        second_args = self._with_completion_readiness(second_args)
        with patch.object(suite_command, "_execute_command") as second_execute:
            second = suite_command.run_full_validation(second_args)

        self.assertTrue(first.broad_success)
        self.assertTrue(second.broad_success)
        self.assertEqual(10, first_execute.call_count)
        second_execute.assert_not_called()
        self.assertEqual(10, second.counts["reused"])
        self.assertEqual(0, second.counts["executed"])
        self.assertEqual(0, second.progress_summary["producer_invocations"])
        self.assertEqual(10, second.progress_summary["avoided_producer_invocations"])
        self.assertEqual(1.0, second.progress_summary["estimated_work_avoided_fraction"])
        self.assertGreaterEqual(second.progress_summary["elapsed_seconds"], 0.0)

    def test_exact_parent_reuse_does_not_require_a_second_readiness_receipt(self):
        """A settled exact parent is a no-op even when readiness is omitted."""

        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor(),
        ) as first_execute:
            first = suite_command.run_full_validation(self.args())
        second_args = self.args()
        second_args.output_dir = str(Path(self.temporary.name) / "artifacts-second")
        # Deliberately leave completion_readiness unset.  The exact-current
        # parent and its terminal ledger are sufficient output evidence.
        with patch.object(suite_command, "_execute_command") as second_execute:
            second = suite_command.run_full_validation(second_args)

        self.assertTrue(first.broad_success)
        self.assertTrue(second.broad_success)
        self.assertEqual(10, first_execute.call_count)
        second_execute.assert_not_called()
        self.assertEqual(10, second.counts["reused"])
        self.assertEqual(0, second.progress_summary["producer_invocations"])

    def test_explicit_reuse_only_reuses_same_parent_without_any_producer(self):
        """A same-parent reuse pass must not reopen a source completion epoch."""

        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor(),
        ) as first_execute:
            first = suite_command.run_full_validation(self.args())

        second_args = self.args()
        second_args.output_dir = str(
            Path(self.temporary.name) / "reuse-only-artifacts"
        )
        # The exact-current terminal parent is sufficient for an explicit
        # reuse-only read.  No second readiness producer is needed.
        second_args.completion_readiness = None
        second_args.reuse_only = True
        with patch.object(suite_command, "_execute_command") as second_execute:
            second = suite_command.run_full_validation(second_args)

        self.assertTrue(first.broad_success)
        self.assertEqual("pass", second.status, second.blockers)
        self.assertEqual(
            first.progress_summary["completion_epoch_id"],
            second.progress_summary["completion_epoch_id"],
        )
        self.assertEqual(
            first.progress_summary["parent_receipt_id"],
            second.progress_summary["parent_receipt_id"],
        )
        self.assertEqual(
            first.progress_summary["parent_receipt_fingerprint"],
            second.progress_summary["parent_receipt_fingerprint"],
        )
        self.assertEqual(10, first_execute.call_count)
        second_execute.assert_not_called()
        self.assertEqual(10, second.counts["reused"])
        self.assertEqual(0, second.counts["executed"])
        self.assertEqual(0, second.progress_summary["producer_invocations"])
        self.assertEqual(10, second.progress_summary["avoided_producer_invocations"])
        self.assertFalse(Path(second_args.output_dir).exists())

    def test_one_changed_input_does_not_reset_consumed_completion_cycle(self):
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
        second_args = self._with_completion_readiness(second_args)
        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor(),
        ) as execute:
            second = suite_command.run_full_validation(second_args)

        self.assertTrue(first.broad_success)
        self.assertEqual("blocked", second.status)
        execute.assert_not_called()
        self.assertTrue(
            any(
                "completion_cycle_attempt_already_consumed" in blocker["code"]
                or "completion_cycle_initial_attempt_already_consumed" in blocker["code"]
                or "completion_epoch_terminal_already_recorded" in blocker["code"]
                for blocker in second.blockers
            ),
            second.blockers,
        )

    def test_failed_parent_does_not_replay_without_explicit_typed_repair(self):
        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor({"distribution_parity": "fail"}),
        ):
            first = suite_command.run_full_validation(self.args())
        second_args = self.args()
        second_args.output_dir = str(Path(self.temporary.name) / "artifacts-second")
        second_args = self._with_completion_readiness(second_args)
        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor(),
        ) as execute:
            second = suite_command.run_full_validation(second_args)

        self.assertEqual("fail", first.status)
        self.assertEqual("blocked", second.status)
        execute.assert_not_called()
        self.assertTrue(
            any(
                "completion_cycle_attempt_already_consumed" in blocker["code"]
                or "completion_cycle_initial_attempt_already_consumed" in blocker["code"]
                or "completion_epoch_terminal_already_recorded" in blocker["code"]
                for blocker in second.blockers
            ),
            second.blockers,
        )

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
        ledger_path = Path(
            result.progress_summary["completion_epoch_ledger_path"]
        )
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        self.assertEqual(
            set(ledger["terminal_action_ids"])
            - {"distribution_parity"},
            set(ledger["completed_terminal_action_ids"]),
        )

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
