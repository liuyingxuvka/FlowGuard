"""The public skill: one entry, one short protocol per capability, real commands only."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "flowguard"
CAPABILITIES = (
    "existing-model", "behavior-commitment", "architecture-reduction", "code-structure",
    "contract-exhaustion", "development-process", "field-lifecycle", "model-mesh", "model-miss",
    "model-test", "topology-hazard", "structure-mesh", "test-mesh", "ui-flow",
)
SECTIONS = ("## Use when", "## Do not use when", "## Inputs", "## Steps", "## What blocks", "## Done when", "## Limits")


class SkillPackageTests(unittest.TestCase):
    def test_entry_lists_every_capability_once(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for name in CAPABILITIES:
            self.assertEqual(1, len(re.findall(rf"^\| {re.escape(name)} \|", text, re.M)), name)

    def test_every_capability_has_a_short_complete_protocol(self) -> None:
        for name in CAPABILITIES:
            path = SKILL / "references" / "domains" / name / "protocol.md"
            with self.subTest(name=name):
                text = path.read_text(encoding="utf-8")
                self.assertLessEqual(len(text.splitlines()), 140)
                for section in SECTIONS:
                    self.assertIn(section, text)

    def test_template_names_in_protocols_exist(self) -> None:
        listed = subprocess.run([sys.executable, "-m", "flowguard", "template", "--list"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.split()
        for path in (SKILL / "references" / "domains").glob("*/protocol.md"):
            for name in re.findall(r"python -m flowguard template ([a-z][a-z-]+)", path.read_text(encoding="utf-8")):
                with self.subTest(protocol=path.parent.name, template=name):
                    self.assertIn(name, listed)

    def test_installer_copies_the_skill(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = lambda *extra: subprocess.run([sys.executable, "scripts/install_skill.py", "--target", directory, *extra],
                                                cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(0, run().returncode)
            check = run("--check")
            self.assertEqual(0, check.returncode, check.stdout)
            self.assertTrue((Path(directory) / "flowguard" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
