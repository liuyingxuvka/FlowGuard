import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import flowguard
import flowguard.project_adoption as project_adoption
from flowguard.project_adoption import (
    FLOWGUARD_AGENTS_BEGIN,
    FLOWGUARD_AGENTS_END,
    FLOWGUARD_PROJECT_MANIFEST,
    FLOWGUARD_REQUIRED_RULE_IDS,
    adopt_project,
    audit_project_adoption,
    build_flowguard_agents_block,
    compare_versions,
    current_project_manifest_text,
    installed_flowguard_package_version,
    managed_block_semantic_hash,
    managed_rule_ids_in_block,
    update_agents_text,
)


ROOT = Path(__file__).resolve().parents[1]


def _passing_suite_evidence():
    return project_adoption._SuiteEvidence(
        True,
        "pass",
        "inventory-hash",
        "semantic-hash",
        (),
    )


def _tree_snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _remove_managed_rule(block: str, rule_id: str) -> str:
    pattern = re.compile(
        rf"<!--\s*flowguard-rule:{re.escape(rule_id)}\s*-->\s*.*?"
        rf"(?=<!--\s*flowguard-rule:|{re.escape(FLOWGUARD_AGENTS_END)})",
        re.IGNORECASE | re.DOTALL,
    )
    updated, count = pattern.subn("", block, count=1)
    if count != 1:
        raise AssertionError(f"expected one generated rule for {rule_id}, found {count}")
    return updated


class ProjectAdoptionTests(unittest.TestCase):
    def test_version_comparison_is_conservative(self):
        self.assertEqual(0, compare_versions("1.2.3", "1.2.3"))
        self.assertEqual(1, compare_versions("1.2.4", "1.2.3"))
        self.assertEqual(-1, compare_versions("1.2.3", "1.2.4"))
        self.assertIsNone(compare_versions("current", "1.2.4"))

    def test_generated_rule_set_is_current_only(self):
        block = build_flowguard_agents_block(package_version="1.2.3")
        rule_ids = managed_rule_ids_in_block(block)

        self.assertEqual(FLOWGUARD_REQUIRED_RULE_IDS, rule_ids)
        self.assertIn("runtime.current_authority_only", rule_ids)
        self.assertNotIn("runtime.latest_schema_first", rule_ids)
        self.assertIn("one current authority only", block)
        self.assertIn("Former FlowGuard skill, model, check, receipt", block)
        self.assertIn("ordinary software", block.lower())
        for forbidden in (
            "project-upgrade",
            "artifact-upgrade",
            "--records-only",
            "latest-schema-first",
        ):
            self.assertNotIn(forbidden, block)

    def test_rule_markers_do_not_change_semantic_hash(self):
        block = build_flowguard_agents_block(package_version="1.2.3")
        marker_only_change = block.replace(
            "<!-- flowguard-rule:project.scope -->",
            "<!--   flowguard-rule:project.scope   -->",
        )
        self.assertEqual(
            managed_block_semantic_hash(block),
            managed_block_semantic_hash(marker_only_change),
        )

    def test_update_agents_preserves_unmanaged_content(self):
        original = "# Project\n\nKeep this project-specific rule.\n"
        first = build_flowguard_agents_block(package_version="1.2.3")
        updated = update_agents_text(original, first)
        replacement = build_flowguard_agents_block(package_version="1.2.4")
        replaced = update_agents_text(updated, replacement)

        self.assertIn("Keep this project-specific rule.", replaced)
        self.assertIn("1.2.4", replaced)
        self.assertNotIn("1.2.3", replaced)
        self.assertEqual(1, replaced.count(FLOWGUARD_AGENTS_BEGIN))

    def test_project_adopt_writes_current_records_without_reading_former_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text("# Existing\n\nDo not remove.\n", encoding="utf-8")
            former = root / ".flowguard" / "former-runtime.json"
            former.parent.mkdir(parents=True)
            former.write_text('{"schema_version":"former"}\n', encoding="utf-8")
            former_bytes = former.read_bytes()

            with patch(
                "flowguard.project_adoption._load_suite_evidence",
                return_value=_passing_suite_evidence(),
            ):
                report = adopt_project(root)

            self.assertTrue(report.ok, report.format_text())
            self.assertEqual(former_bytes, former.read_bytes())
            agents_text = (root / "AGENTS.md").read_text(encoding="utf-8")
            manifest_text = (root / FLOWGUARD_PROJECT_MANIFEST).read_text(encoding="utf-8")
            self.assertIn("Do not remove.", agents_text)
            self.assertIn("one current authority only", agents_text)
            self.assertIn("direct_current_replacement = true", manifest_text)
            self.assertIn("former_flowguard_shapes_blocked = true", manifest_text)
            self.assertNotIn("upgrade_existing_artifacts", manifest_text)
            self.assertTrue((root / ".flowguard" / "adoption_log.jsonl").is_file())

    def test_direct_adopt_replaces_older_managed_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text(
                build_flowguard_agents_block(package_version="0.1.0"),
                encoding="utf-8",
            )
            manifest = root / FLOWGUARD_PROJECT_MANIFEST
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(
                current_project_manifest_text(package_version="0.1.0"),
                encoding="utf-8",
            )

            with patch(
                "flowguard.project_adoption._load_suite_evidence",
                return_value=_passing_suite_evidence(),
            ):
                report = adopt_project(root)

            self.assertTrue(report.ok, report.format_text())
            self.assertEqual("adopt", report.action)
            self.assertIn(
                installed_flowguard_package_version(),
                (root / FLOWGUARD_PROJECT_MANIFEST).read_text(encoding="utf-8"),
            )

    def test_audit_requires_direct_current_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text(
                build_flowguard_agents_block(package_version="0.1.0"),
                encoding="utf-8",
            )
            manifest = root / FLOWGUARD_PROJECT_MANIFEST
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                current_project_manifest_text(package_version="0.1.0"),
                encoding="utf-8",
            )

            with patch(
                "flowguard.project_adoption._load_suite_evidence",
                return_value=_passing_suite_evidence(),
            ):
                report = audit_project_adoption(root)

            categories = {finding.category for finding in report.findings}
            self.assertIn("project_flowguard_current_replacement_required", categories)
            recommendations = "\n".join(finding.recommendation for finding in report.findings)
            self.assertIn("project-adopt", recommendations)
            self.assertNotIn("project-upgrade", recommendations)
            self.assertFalse(report.ok)

    def test_adopt_rejects_ambiguous_managed_markers_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            block = build_flowguard_agents_block()
            (root / "AGENTS.md").write_text(f"{block}\n\n{block}\n", encoding="utf-8")
            before = _tree_snapshot(root)

            with patch(
                "flowguard.project_adoption._load_suite_evidence",
                return_value=_passing_suite_evidence(),
            ):
                report = adopt_project(root)

            self.assertFalse(report.ok)
            self.assertIn(
                "managed_block_cardinality_mismatch",
                {finding.category for finding in report.findings},
            )
            self.assertEqual(before, _tree_snapshot(root))

    def test_adopt_rejects_generator_rule_loss_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text("# Existing\n", encoding="utf-8")
            before = _tree_snapshot(root)
            broken = _remove_managed_rule(
                build_flowguard_agents_block(),
                "runtime.current_authority_only",
            )

            with patch(
                "flowguard.project_adoption.build_flowguard_agents_block",
                return_value=broken,
            ), patch(
                "flowguard.project_adoption._load_suite_evidence",
                return_value=_passing_suite_evidence(),
            ):
                report = adopt_project(root)

            self.assertFalse(report.ok)
            self.assertIn("governance_regression", {item.category for item in report.findings})
            self.assertEqual(before, _tree_snapshot(root))

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
            self.assertNotIn("artifact_upgrade_report", payload)

    def test_former_upgrade_commands_are_rejected(self):
        for command in ("project-upgrade", "artifact-upgrade"):
            result = subprocess.run(
                [sys.executable, "-m", "flowguard", command, "--help"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("invalid choice", result.stderr)


if __name__ == "__main__":
    unittest.main()
