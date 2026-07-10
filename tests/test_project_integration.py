import subprocess
import sys
import json
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

        self.assertIn("AI-agent skill suite", text)
        self.assertIn("Agent Skill Suite Setup", text)
        self.assertIn("`.agents/skills/`", text)
        self.assertIn("model-first-function-flow", text)
        self.assertIn("not the AI-agent skill install surface", text)
        self.assertIn("check-execution convenience", text)
        self.assertIn('python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"', text)
        self.assertIn("toolchain_preflight.py", text)
        self.assertIn("temporary local mini-framework", text)
        self.assertIn("one-off mini framework", text)
        self.assertIn("blocked_or_partial", text)
        self.assertIn("Model-Miss Review for non-trivial bug repairs", text)
        self.assertIn("https://github.com/liuyingxuvka/FlowGuard", text)
        self.assertIn("project-adopt", text)
        self.assertIn("project-audit", text)
        self.assertIn("project-upgrade", text)
        self.assertIn("artifact-upgrade", text)
        self.assertIn("latest-schema-first", text)
        self.assertIn(".flowguard/project.toml", text)
        self.assertLess(text.index("Agent Skill Suite Setup"), text.index("python -m pip install -e"))

    def test_skill_requires_import_preflight_and_rejects_substitute(self):
        text = (
            ROOT
            / ".agents"
            / "skills"
            / "model-first-function-flow"
            / "SKILL.md"
        ).read_text(encoding="utf-8")

        self.assertIn("FlowGuard kernel", text)
        self.assertIn("use the matching satellite directly", text)
        self.assertIn("verify adoption", text)
        self.assertIn("Verify the real FlowGuard check engine", text)
        self.assertIn("never create a fake mini-framework", text)
        self.assertIn("references/modeling_protocol.md", text)
        self.assertIn("blocked/partial", text)
        self.assertIn("AGENTS.md managed record", text)
        self.assertIn("Missing, stale, skipped", text)
        self.assertIn("cannot support broad done", text)

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
