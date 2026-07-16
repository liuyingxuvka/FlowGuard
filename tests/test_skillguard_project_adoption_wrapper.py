import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import check_skillguard_project_adoption as wrapper


class SkillGuardProjectAdoptionWrapperTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "repo"
        self.root.mkdir()
        self.cli = Path(self.temporary.name) / "skillguard.py"
        self.cli.write_text("# fixture\n", encoding="utf-8")

    def test_installed_cli_resolution_uses_codex_home(self):
        codex_home = Path(self.temporary.name) / "codex-home"
        self.assertEqual(
            codex_home.resolve() / "skills" / "skillguard" / "scripts" / "skillguard.py",
            wrapper.resolve_skillguard_cli("all", codex_home=codex_home),
        )

    def test_pass_projects_authoritative_payload_and_read_only_command(self):
        payload = {
            "schema_version": "skillguard.project_audit_result.v1",
            "status": "pass",
            "ok": True,
            "findings": [],
            "runtime_authorities": [{"authority": "current", "ok": True}],
            "claim_boundary": "fixture boundary",
        }
        calls = []

        def fake_runner(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

        result, exit_code, stderr = wrapper.run_project_audit(
            self.root,
            skillguard=str(self.cli),
            runner=fake_runner,
        )

        self.assertEqual(payload, result)
        self.assertEqual(0, exit_code)
        self.assertEqual("", stderr)
        command, kwargs = calls[0]
        self.assertEqual("project-audit", command[2])
        self.assertEqual(["--root", str(self.root.resolve())], command[3:])
        self.assertFalse(kwargs["check"])
        self.assertNotIn("shell", kwargs)

    def test_unparseable_child_output_blocks_without_echoing_it(self):
        def fake_runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, "not-json", "diagnostic")

        result, exit_code, stderr = wrapper.run_project_audit(
            self.root,
            skillguard=str(self.cli),
            runner=fake_runner,
        )

        self.assertEqual(1, exit_code)
        self.assertEqual(["skillguard_project_audit_unparseable"], result["findings"])
        self.assertEqual("diagnostic", stderr)
        self.assertNotIn("not-json", json.dumps(result))

    def test_frozen_snapshot_preserves_manifest_project_identity_for_official_audit(self):
        frozen = Path(self.temporary.name) / "openspec-frozen-fixture"
        frozen.mkdir()
        (frozen / "AGENTS.md").write_text("# fixture\n", encoding="utf-8")
        (frozen / ".skillguard").mkdir()
        (frozen / ".skillguard" / "project.json").write_text(
            json.dumps({"project_id": "FlowGuard_20260427"}),
            encoding="utf-8",
        )
        skill = frozen / ".agents" / "skills" / "demo"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("# demo\n", encoding="utf-8")
        payload = {
            "schema_version": "skillguard.project_audit_result.v1",
            "status": "pass",
            "ok": True,
            "findings": [],
            "runtime_authorities": [],
            "claim_boundary": "fixture boundary",
        }
        staged_roots = []

        def fake_runner(command, **kwargs):
            audit_root = Path(command[-1])
            staged_roots.append(audit_root)
            self.assertEqual("FlowGuard_20260427", audit_root.name)
            self.assertEqual(str(audit_root), kwargs["cwd"])
            self.assertTrue((audit_root / "AGENTS.md").is_file())
            self.assertTrue((audit_root / ".skillguard" / "project.json").is_file())
            self.assertTrue((audit_root / ".agents" / "skills" / "demo" / "SKILL.md").is_file())
            return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

        result, exit_code, stderr = wrapper.run_project_audit(
            frozen,
            skillguard=str(self.cli),
            runner=fake_runner,
        )

        self.assertEqual(payload, result)
        self.assertEqual(0, exit_code)
        self.assertEqual("", stderr)
        self.assertEqual(1, len(staged_roots))
        self.assertFalse(staged_roots[0].exists())

    def test_frozen_snapshot_rejects_unsafe_manifest_project_identity(self):
        frozen = Path(self.temporary.name) / "openspec-frozen-fixture"
        frozen.mkdir()
        (frozen / ".skillguard").mkdir()
        (frozen / ".skillguard" / "project.json").write_text(
            json.dumps({"project_id": "../outside"}),
            encoding="utf-8",
        )

        result, exit_code, stderr = wrapper.run_project_audit(
            frozen,
            skillguard=str(self.cli),
        )

        self.assertEqual(1, exit_code)
        self.assertEqual(["frozen_project_id_invalid"], result["findings"])
        self.assertEqual("", stderr)

    def test_official_block_payload_is_preserved_and_returns_nonzero(self):
        payload = {
            "schema_version": "skillguard.project_audit_result.v1",
            "status": "blocked",
            "ok": False,
            "findings": ["runtime_authority_blocked"],
            "runtime_authorities": [],
            "claim_boundary": "fixture boundary",
        }

        def fake_runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 1, json.dumps(payload), "")

        result, exit_code, stderr = wrapper.run_project_audit(
            self.root,
            skillguard=str(self.cli),
            runner=fake_runner,
        )

        self.assertEqual(payload, result)
        self.assertEqual(1, exit_code)
        self.assertEqual("", stderr)

    def test_main_emits_one_canonical_json_document(self):
        payload = {
            "schema_version": "skillguard.project_audit_result.v1",
            "status": "pass",
            "ok": True,
            "findings": [],
            "runtime_authorities": [],
            "claim_boundary": "fixture boundary",
        }
        stream = io.StringIO()
        with patch.object(wrapper, "run_project_audit", return_value=(payload, 0, "")):
            with contextlib.redirect_stdout(stream):
                exit_code = wrapper.main(["--root", str(self.root), "--json"])

        self.assertEqual(0, exit_code)
        self.assertEqual(payload, json.loads(stream.getvalue()))
        self.assertEqual(1, len(stream.getvalue().splitlines()))


if __name__ == "__main__":
    unittest.main()
