import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import flowguard
from flowguard.project_adoption import (
    FLOWGUARD_AGENTS_BEGIN,
    FLOWGUARD_AGENTS_END,
    FLOWGUARD_PROJECT_MANIFEST,
    FLOWGUARD_REPOSITORY_URL,
    adopt_project,
    audit_project_adoption,
    build_flowguard_agents_block,
    compare_versions,
    current_project_manifest_text,
    installed_flowguard_package_version,
    update_agents_text,
    upgrade_project,
)


ROOT = Path(__file__).resolve().parents[1]


class ProjectAdoptionTests(unittest.TestCase):
    def test_version_comparison_is_conservative(self):
        self.assertEqual(0, compare_versions("0.31.0", "0.31"))
        self.assertEqual(1, compare_versions("0.32.0", "0.31.9"))
        self.assertEqual(-1, compare_versions("0.30.0", "0.31.0"))
        self.assertIsNone(compare_versions("0.31.0rc1", "0.31.0"))

    def test_managed_agents_block_preserves_existing_content(self):
        existing = "# Project Rules\n\nKeep this project-specific rule.\n"
        block = build_flowguard_agents_block(package_version="1.2.3")
        updated = update_agents_text(existing, block)

        self.assertIn("Keep this project-specific rule.", updated)
        self.assertIn(FLOWGUARD_AGENTS_BEGIN, updated)
        self.assertIn(FLOWGUARD_AGENTS_END, updated)
        self.assertIn(FLOWGUARD_REPOSITORY_URL, updated)

        replacement = build_flowguard_agents_block(package_version="1.2.4")
        replaced = update_agents_text(updated, replacement)
        self.assertIn("Keep this project-specific rule.", replaced)
        self.assertIn("1.2.4", replaced)
        self.assertNotIn("1.2.3", replaced)
        self.assertEqual(1, replaced.count(FLOWGUARD_AGENTS_BEGIN))

    def test_project_adopt_writes_agents_manifest_and_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text("# Existing\n\nDo not remove.\n", encoding="utf-8")

            report = adopt_project(root)

            self.assertTrue(report.ok, report.format_text())
            agents_text = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("Do not remove.", agents_text)
            self.assertIn("FlowGuard repository:", agents_text)
            self.assertIn(FLOWGUARD_REPOSITORY_URL, agents_text)
            self.assertIn("maintenance scan", agents_text)
            manifest_text = (root / FLOWGUARD_PROJECT_MANIFEST).read_text(encoding="utf-8")
            self.assertIn(f'adopted_package_version = "{installed_flowguard_package_version()}"', manifest_text)
            self.assertIn(f'schema_version = "{flowguard.SCHEMA_VERSION}"', manifest_text)
            self.assertTrue((root / ".flowguard" / "adoption_log.jsonl").exists())
            self.assertTrue((root / "docs" / "flowguard_adoption_log.md").exists())

    def test_audit_reports_newer_and_older_version_states(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text(build_flowguard_agents_block(), encoding="utf-8")
            manifest = root / FLOWGUARD_PROJECT_MANIFEST
            manifest.parent.mkdir(parents=True)
            manifest.write_text(current_project_manifest_text(package_version="0.1.0"), encoding="utf-8")

            newer_report = audit_project_adoption(root)
            categories = {finding.category for finding in newer_report.findings}
            self.assertIn("project_flowguard_upgrade_available", categories)
            self.assertTrue(newer_report.ok)

            manifest.write_text(current_project_manifest_text(package_version="9999.0.0"), encoding="utf-8")
            older_report = audit_project_adoption(root)
            categories = {finding.category for finding in older_report.findings}
            self.assertIn("installed_flowguard_older", categories)
            self.assertFalse(older_report.ok)

    def test_project_upgrade_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text(build_flowguard_agents_block(package_version="0.1.0"), encoding="utf-8")
            manifest = root / FLOWGUARD_PROJECT_MANIFEST
            manifest.parent.mkdir(parents=True)
            manifest.write_text(current_project_manifest_text(package_version="0.1.0"), encoding="utf-8")

            report = upgrade_project(root)

            self.assertTrue(report.ok, report.format_text())
            manifest_text = manifest.read_text(encoding="utf-8")
            self.assertIn(f'adopted_package_version = "{installed_flowguard_package_version()}"', manifest_text)

    def test_project_adopt_cli_outputs_json(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-m", "flowguard", "project-adopt", "--root", directory, "--json"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("flowguard_project_adoption_report", payload["artifact_type"])
            self.assertEqual("adopt", payload["action"])
            self.assertTrue(payload["ok"])
            self.assertTrue((Path(directory) / "AGENTS.md").exists())
            self.assertTrue((Path(directory) / FLOWGUARD_PROJECT_MANIFEST).exists())


if __name__ == "__main__":
    unittest.main()
