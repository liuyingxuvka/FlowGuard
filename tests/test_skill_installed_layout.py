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
                        ".skillguard/compiled-contract.json",
                        ".skillguard/check-manifest.json",
                    ):
                        self.assertTrue((skill / relative).is_file(), relative)
                    self.assertEqual(
                        {"contract-source.json", "compiled-contract.json", "check-manifest.json"},
                        {path.name for path in (skill / ".skillguard").iterdir()},
                    )
                    source = json.loads(
                        (skill / ".skillguard" / "contract-source.json").read_text(encoding="utf-8")
                    )
                    self.assertEqual("skillguard.contract_source.v2", source["schema_version"])
                    self.assertEqual("skillguard.depth_profile.v2", source["depth_profile"]["schema_version"])
                    self.assertNotIn("v1_runtime_authority", source)
                    compiled = json.loads(
                        (skill / ".skillguard" / "compiled-contract.json").read_text(encoding="utf-8")
                    )
                    v2_manifest = json.loads(
                        (skill / ".skillguard" / "check-manifest.json").read_text(encoding="utf-8")
                    )
                    self.assertEqual("skillguard.compiled_contract.v2", compiled["schema_version"])
                    self.assertEqual("skillguard.check_manifest.v2", v2_manifest["schema_version"])
                    self.assertEqual(source["model_id"], compiled["model_id"])
                    self.assertEqual(source["depth_profile"], compiled["depth_profile"])
                    self.assertEqual(compiled["contract_hash"], v2_manifest["contract_hash"])

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
