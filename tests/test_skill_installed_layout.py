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
                    for former in (
                        ".skillguard/work-contract.json",
                        ".skillguard/check_manifest.json",
                        ".skillguard/check.py",
                        ".skillguard/skillguard_manifest.json",
                        ".skillguard/skillguard_profile.json",
                        ".skillguard/skillguard_skill_contract.json",
                        ".skillguard/skillguard_evidence_rules.json",
                        ".skillguard/skillguard_closure_policy.json",
                        ".skillguard/skillguard_progress_ledger.jsonl",
                        ".skillguard/checks",
                        ".skillguard/evidence",
                        ".skillguard/reports",
                        ".skillguard/ai_judgments",
                    ):
                        self.assertFalse((skill / former).exists(), former)
                    source = json.loads(
                        (skill / ".skillguard" / "contract-source.json").read_text(encoding="utf-8")
                    )
                    self.assertEqual("skillguard.contract_source.v2", source["schema_version"])
                    self.assertNotIn("depth_profile", source)
                    compiled = json.loads(
                        (skill / ".skillguard" / "compiled-contract.json").read_text(encoding="utf-8")
                    )
                    manifest = json.loads(
                        (skill / ".skillguard" / "check-manifest.json").read_text(encoding="utf-8")
                    )
                    self.assertEqual("skillguard.compiled_contract.v2", compiled["schema_version"])
                    self.assertEqual("skillguard.check_manifest.v2", manifest["schema_version"])
                    self.assertEqual(source["model_id"], compiled["model_id"])
                    self.assertNotIn("depth_profile", compiled)

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
