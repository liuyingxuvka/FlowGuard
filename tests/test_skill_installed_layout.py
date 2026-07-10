from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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
                        ".skillguard/contract-source.json",
                        ".skillguard/work-contract.json",
                        ".skillguard/check_manifest.json",
                        ".skillguard/check.py",
                    ):
                        self.assertTrue((skill / relative).is_file(), relative)
                    source = json.loads(
                        (skill / ".skillguard" / "contract-source.json").read_text(encoding="utf-8")
                    )
                    for reference in source["direct_references"]:
                        self.assertTrue((skill / reference).is_file(), reference)
                    manifest = json.loads(
                        (skill / ".skillguard" / "check_manifest.json").read_text(encoding="utf-8")
                    )
                    self.assertEqual(5, len(manifest["checks"]))
                    self.assertTrue(
                        all(".skillguard/check.py" in row["command"] for row in manifest["checks"])
                    )

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
