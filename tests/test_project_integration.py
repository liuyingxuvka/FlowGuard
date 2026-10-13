import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProjectIntegrationTests(unittest.TestCase):
    def test_pyproject_declares_check_command_wrapper(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

        self.assertIn('name = "flowguard"', text)
        self.assertIn("dependencies = []", text)
        self.assertIn('"flowguard*"', text)
        self.assertIn('flowguard = "flowguard.__main__:main"', text)

    def test_project_integration_doc_separates_skill_suite_from_check_engine(self):
        text = (ROOT / "docs" / "project_integration.md").read_text(encoding="utf-8")

        for phrase in (
            "one clean consumer surface",
            "three public lifecycle operations",
            "`$CODEX_HOME/skills/flowguard/SKILL.md`",
            "Python package supplies",
            "does not copy the author checkout",
            "`read` starts zero producers and writes",
            "per-element good, bad, and draft evidence is added only",
            "Git tags and GitHub publication remain separate transactions",
        ):
            self.assertIn(phrase, text)
        self.assertNotIn("project-adopt", text)
        self.assertNotIn("project-audit", text)
        self.assertNotIn("project-upgrade", text)
        self.assertNotIn("artifact-upgrade", text)

    def test_import_preflight_command_works_in_this_environment(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import flowguard; print(flowguard.SCHEMA_VERSION)",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertRegex(completed.stdout.strip(), r"^\d+\.\d+$")

if __name__ == "__main__":
    unittest.main()
