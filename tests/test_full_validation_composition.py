import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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

        def fake(command, cwd):
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
                    "depth_classification": "contract-depth-pass",
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
        parent = json.loads(Path(result.artifact_paths[0]).read_text(encoding="utf-8"))
        self.assertEqual("pass", parent["status"])
        self.assertEqual(8, len(parent["children"]))

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
        self.assertEqual("fail", parity.payload["result"]["status"])
        self.assertFalse(result.broad_success)

    def test_missing_required_script_is_a_blocked_child_with_artifacts(self):
        (self.root / "scripts/check_flowguard_self_governance.py").unlink()
        with patch.object(suite_command, "_execute_command", side_effect=self.executor()):
            result = suite_command.run_full_validation(self.args())

        self.assertEqual("blocked", result.status)
        child = next(item for item in result.children if item.child_id == "skill_self_governance")
        self.assertEqual("blocked", child.status)
        self.assertIn("required", child.summary)
        self.assertTrue(all(Path(path).is_file() for path in child.artifact_paths))
        self.assertTrue(any(item.check_id == child.child_id for item in result.skipped_checks))

    def test_pass_with_gaps_is_partial_not_broad_success(self):
        with patch.object(
            suite_command,
            "_execute_command",
            side_effect=self.executor({"project_audit": "pass_with_gaps"}),
        ):
            result = suite_command.run_full_validation(self.args())

        project = next(child for child in result.children if child.child_id == "project_audit")
        self.assertEqual("partial", project.status)
        self.assertEqual("partial", result.status)
        self.assertFalse(result.broad_success)
        self.assertTrue(any(item["child_id"] == "project_audit" for item in result.blockers))

    def test_required_skip_inside_nominal_pass_is_not_flattened(self):
        normal = self.executor()

        def with_required_skip(command, cwd):
            outcome = normal(command, cwd)
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

        child = next(item for item in result.children if item.child_id == "distribution_parity")
        self.assertEqual("blocked", child.status)
        self.assertIn("--shadow-root", child.summary)

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
