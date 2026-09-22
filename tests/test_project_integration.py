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

    def test_skill_requires_import_preflight_and_rejects_substitute(self):
        skill = (
            ROOT
            / ".agents"
            / "skills"
            / "flowguard"
            / "SKILL.md"
        ).read_text(encoding="utf-8")
        core = (
            ROOT
            / ".agents"
            / "skills"
            / "flowguard"
            / "references"
            / "modeling_core_protocol.md"
        ).read_text(encoding="utf-8")
        evidence = (
            ROOT
            / ".agents"
            / "skills"
            / "flowguard"
            / "references"
            / "modeling_evidence_protocol.md"
        ).read_text(encoding="utf-8")

        self.assertIn("one public skill", skill)
        self.assertIn("The only public operations are `read`, `change`, and `release`", skill)
        self.assertIn("references/domains/<subject>/", skill)
        self.assertIn("No mode/fallback path is", skill)
        self.assertIn('python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"', core)
        self.assertIn("AGENTS.md managed adoption record", core)
        self.assertIn("blocked/partial", core)
        self.assertIn("never create a replacement mini-framework", core)
        self.assertIn("failed, timeout, error, or blocker", evidence)
        self.assertIn("skipped/not-run with reason", evidence)
        self.assertIn("stale or reused without current ticket/proof", evidence)
        self.assertIn("Broad done/release/archive/publish/production confidence cannot consume", evidence)

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
            / "flowguard"
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

        payload = json.loads(completed.stdout)
        self.assertEqual(2, completed.returncode, completed.stdout + completed.stderr)
        self.assertEqual("blocked", payload["status"])
        self.assertEqual("block", payload["decision"])
        self.assertEqual(0, payload["producer_count"])
        self.assertEqual("unknown operation: schema-version", payload["error"])
        self.assertEqual(["read", "change", "release"], payload["allowed_operations"])


if __name__ == "__main__":
    unittest.main()
