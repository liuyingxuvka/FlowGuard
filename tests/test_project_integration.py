import subprocess
import sys
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProjectIntegrationTests(unittest.TestCase):
    def test_pyproject_declares_installable_standard_library_package(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

        self.assertIn('name = "flowguard"', text)
        self.assertIn("dependencies = []", text)
        self.assertIn('"flowguard*"', text)
        self.assertIn('flowguard = "flowguard.__main__:main"', text)

    def test_project_integration_doc_requires_real_toolchain(self):
        text = (ROOT / "docs" / "project_integration.md").read_text(encoding="utf-8")

        self.assertIn('python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"', text)
        self.assertIn("pip install -e", text)
        self.assertIn("toolchain_preflight.py", text)
        self.assertIn("temporary local mini-framework", text)
        self.assertIn("one-off mini framework", text)
        self.assertIn("blocked_or_partial", text)

    def test_skill_requires_import_preflight_and_rejects_substitute(self):
        text = (
            ROOT
            / ".agents"
            / "skills"
            / "model-first-function-flow"
            / "SKILL.md"
        ).read_text(encoding="utf-8")

        self.assertIn('python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"', text)
        self.assertIn("do not write a temporary mini-framework", text)
        self.assertIn("assets/toolchain_preflight.py", text)
        self.assertIn("blocked/partial", text)

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

    def test_skill_toolchain_preflight_helper_runs(self):
        helper = (
            ROOT
            / ".agents"
            / "skills"
            / "model-first-function-flow"
            / "assets"
            / "toolchain_preflight.py"
        )
        completed = subprocess.run(
            [sys.executable, str(helper), "--source", str(ROOT), "--json"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertIn(payload["mode"], {"installed", "pythonpath_available"})

    def test_module_wrapper_exposes_schema_version(self):
        completed = subprocess.run(
            [sys.executable, "-m", "flowguard", "schema-version"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertRegex(completed.stdout.strip(), r"^\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
