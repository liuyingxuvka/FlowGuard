from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flowguard.distribution_sync import _install_skill_tree


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPOSITORY_ROOT / "scripts" / "install_flowguard_skills.py"


class SkillInstallerCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source-skills"
        self.member_ids = tuple(["flowguard", "flowguard-test-mesh"] + [f"flowguard-fixture-{index:02d}" for index in range(13)])
        for member in self.member_ids:
            directory = self.source / member
            directory.mkdir(parents=True)
            (directory / "SKILL.md").write_text(f"# {member}\n", encoding="utf-8")
        self.codex_home = self.root / "codex-home"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _run(self, *args: str, env_home: bool = False) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        if env_home:
            env["CODEX_HOME"] = str(self.codex_home)
        return subprocess.run(
            [sys.executable, str(INSTALLER), *args],
            cwd=REPOSITORY_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_temporary_codex_home_install_check_uninstall_lifecycle(self) -> None:
        install = self._run("install", "--source", str(REPOSITORY_ROOT), "--json", env_home=True)
        self.assertEqual(0, install.returncode, install.stderr or install.stdout)
        install_payload = json.loads(install.stdout)
        self.assertEqual("pass", install_payload["status"])
        self.assertTrue((self.codex_home / "skills" / "flowguard" / "SKILL.md").is_file())

        check = self._run("check", "--source", str(REPOSITORY_ROOT), "--json", env_home=True)
        self.assertEqual(0, check.returncode, check.stderr or check.stdout)
        self.assertTrue(json.loads(check.stdout)["ok"])

        uninstall = self._run("uninstall", "--json", env_home=True)
        self.assertEqual(0, uninstall.returncode, uninstall.stderr or uninstall.stdout)
        self.assertFalse((self.codex_home / "skills" / "flowguard" / "SKILL.md").exists())

    def test_cli_dry_run_does_not_create_codex_home(self) -> None:
        completed = self._run("install", "--source", str(REPOSITORY_ROOT), "--dry-run", "--json", env_home=True)
        self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
        self.assertTrue(json.loads(completed.stdout)["dry_run"])
        self.assertFalse(self.codex_home.exists())

    def test_cli_parity_accepts_configured_formal_shadow_and_installed_roots(self) -> None:
        shadow = self.root / "shadow-skills"
        installed = self.root / "installed-skills"
        for target in (shadow,):
            for source_file in self.source.rglob("*"):
                if source_file.is_file():
                    destination = target / source_file.relative_to(self.source)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(source_file.read_bytes())
        install = _install_skill_tree(
            self.source,
            installed,
            member_ids=self.member_ids,
        )
        self.assertTrue(install.ok, install.to_dict())
        completed = self._run(
            "parity",
            "--source",
            str(self.source),
            "--formal",
            str(self.source),
            "--shadow",
            str(shadow),
            "--installed",
            str(installed),
            "--json",
        )
        self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
        payload = json.loads(completed.stdout)
        self.assertEqual({"source", "formal", "shadow", "installed"}, set(payload["inventories"]))
        self.assertTrue(payload["ok"])

    def test_cli_check_reports_extra_file(self) -> None:
        self._run("install", "--source", str(REPOSITORY_ROOT), "--json", env_home=True)
        extra = self.codex_home / "skills" / "flowguard-test-mesh" / "legacy.txt"
        extra.write_text("obsolete", encoding="utf-8")
        completed = self._run("check", "--source", str(REPOSITORY_ROOT), "--json", env_home=True)
        self.assertEqual(1, completed.returncode)
        payload = json.loads(completed.stdout)
        self.assertIn("flowguard-test-mesh/legacy.txt", payload["extra_files"])

    def test_cli_requires_explicit_adoption_for_old_unmanaged_install(self) -> None:
        old_file = self.codex_home / "skills" / "flowguard" / "SKILL.md"
        old_file.parent.mkdir(parents=True)
        old_file.write_text("# old unmanaged install\n", encoding="utf-8")
        protected = self._run("install", "--source", str(REPOSITORY_ROOT), "--json", env_home=True)
        self.assertEqual(1, protected.returncode)
        self.assertEqual("# old unmanaged install\n", old_file.read_text(encoding="utf-8"))

        adopted = self._run(
            "install",
            "--source",
            str(REPOSITORY_ROOT),
            "--adopt-existing",
            "--json",
            env_home=True,
        )
        self.assertEqual(0, adopted.returncode, adopted.stderr or adopted.stdout)
        payload = json.loads(adopted.stdout)
        self.assertIn("flowguard/SKILL.md", payload["adopted_files"])
        self.assertEqual(
            (REPOSITORY_ROOT / ".agents" / "skills" / "flowguard" / "SKILL.md").read_bytes(),
            old_file.read_bytes(),
        )


if __name__ == "__main__":
    unittest.main()
