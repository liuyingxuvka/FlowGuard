from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flowguard.skill_suite import validate_skill_suite


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_flowguard_skills.py"
SUITE_MAP = ROOT / ".skillguard" / "flowguard-suite" / "suite-map.json"


class SkillInstalledLayoutTests(unittest.TestCase):
    def test_real_seventeen_skill_tree_resolves_every_direct_reference_after_install(self) -> None:
        suite = json.loads(SUITE_MAP.read_text(encoding="utf-8"))
        members = tuple(member["name"] for member in suite["included_skills"])
        self.assertEqual(17, len(members))

        with tempfile.TemporaryDirectory() as directory:
            installed_root = Path(directory) / "skills"
            install = subprocess.run(
                [
                    sys.executable,
                    str(INSTALLER),
                    "install",
                    "--source",
                    str(ROOT),
                    "--target",
                    str(installed_root),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, install.returncode, install.stderr or install.stdout)
            self.assertTrue(json.loads(install.stdout)["ok"])

            for skill_id in members:
                skill = installed_root / skill_id
                with self.subTest(skill=skill_id):
                    for relative in (
                        "SKILL.md",
                        "agents/openai.yaml",
                        "consumer-release.json",
                    ):
                        self.assertTrue((skill / relative).is_file(), relative)
                    self.assertFalse((skill / ".skillguard").exists())
                    manifest = json.loads(
                        (skill / "consumer-release.json").read_text(encoding="utf-8")
                    )
                    self.assertEqual(
                        "consumer.skill_distribution.current",
                        manifest["schema_version"],
                    )
                    self.assertTrue(manifest["author_control_excluded"])
                    self.assertEqual(skill_id, manifest["skill_id"])
                    consumer_text = (
                        (skill / "SKILL.md").read_text(encoding="utf-8")
                        + (skill / "agents/openai.yaml").read_text(encoding="utf-8")
                    ).casefold()
                    self.assertNotIn("skillguard", consumer_text)

            suite_report = validate_skill_suite(ROOT, skill_root=installed_root)
            self.assertTrue(suite_report.ok, suite_report.to_json_text())

            check = subprocess.run(
                [
                    sys.executable,
                    str(INSTALLER),
                    "check",
                    "--source",
                    str(ROOT),
                    "--target",
                    str(installed_root),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, check.returncode, check.stderr or check.stdout)
            self.assertTrue(json.loads(check.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
