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
from flowguard.distribution_sync import install_skill_suite
from flowguard.project_adoption import (
    FLOWGUARD_AGENTS_BEGIN,
    FLOWGUARD_AGENTS_END,
    FLOWGUARD_REQUIRED_RULE_IDS,
    FLOWGUARD_PROJECT_LOG,
    FLOWGUARD_PROJECT_MANIFEST,
    FLOWGUARD_REPOSITORY_URL,
    adopt_project,
    audit_project_adoption,
    build_flowguard_agents_block,
    compare_versions,
    current_project_manifest_text,
    installed_flowguard_package_version,
    managed_block_semantic_hash,
    managed_rule_ids_in_block,
    update_agents_text,
    upgrade_project,
)
from flowguard.skill_suite import FLOWGUARD_SUITE_MAP


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
    """Remove exactly one generated rule by its stable id."""

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
        self.assertEqual(0, compare_versions("0.31.0", "0.31"))
        self.assertEqual(1, compare_versions("0.32.0", "0.31.9"))
        self.assertEqual(-1, compare_versions("0.30.0", "0.31.0"))
        self.assertIsNone(compare_versions("0.31.0rc1", "0.31.0"))

    def test_generator_golden_rule_set_is_complete_and_versioned(self):
        package_version = installed_flowguard_package_version()
        block = build_flowguard_agents_block(package_version=package_version)

        self.assertEqual(FLOWGUARD_REQUIRED_RULE_IDS, managed_rule_ids_in_block(block))
        self.assertEqual(len(FLOWGUARD_REQUIRED_RULE_IDS), len(set(FLOWGUARD_REQUIRED_RULE_IDS)))
        self.assertIn(f"FlowGuard check-engine version: `{package_version}`", block)
        self.assertIn(f"FlowGuard schema version: `{flowguard.SCHEMA_VERSION}`", block)
        for required_text in (
            "latest-schema-first",
            "Default replacement means dispose the old path",
            "BehaviorCommitmentLedger",
            "path_sensitive=true",
            "Primary Path Authority",
            "FieldLifecycleMesh",
            "`product_runtime`, `agent_operation`,",
            "lightweight existing-model/commitment lookup",
            "UI runnable claims",
            "flowguard-development-process-flow",
            "post-change scan signals",
            "Do not create a fake local FlowGuard replacement",
        ):
            self.assertIn(required_text, block)

    def test_rule_markers_do_not_change_semantic_hash(self):
        block = build_flowguard_agents_block(package_version="1.2.3")
        without_markers = "\n".join(
            line for line in block.splitlines() if "flowguard-rule:" not in line
        )
        self.assertEqual(
            managed_block_semantic_hash(block),
            managed_block_semantic_hash(without_markers),
        )
        self.assertEqual((), managed_rule_ids_in_block(without_markers))

    def test_rule_id_must_match_its_complete_clause(self):
        block = build_flowguard_agents_block(package_version="1.2.3")
        relabelled = block.replace(
            "flowguard-rule:behavior.primary_path_authority",
            "flowguard-rule:behavior.commitment_ledger",
            1,
        )

        observed = managed_rule_ids_in_block(relabelled)

        self.assertNotIn("behavior.commitment_ledger", observed)
        self.assertNotIn("behavior.primary_path_authority", observed)

    def test_managed_agents_block_preserves_existing_content(self):
        existing = "# Project Rules\n\nKeep this project-specific rule.\n"
        block = build_flowguard_agents_block(package_version="1.2.3")
        updated = update_agents_text(existing, block)

        self.assertIn("Keep this project-specific rule.", updated)
        self.assertIn(FLOWGUARD_AGENTS_BEGIN, updated)
        self.assertIn(FLOWGUARD_AGENTS_END, updated)
        self.assertIn(FLOWGUARD_REPOSITORY_URL, updated)
        self.assertIn("Primary agent surface: `.agents/skills/`", updated)
        self.assertIn("Default entry skill: `.agents/skills/flowguard/SKILL.md`", updated)
        self.assertIn("not the", updated)
        self.assertIn("AI-agent skill installation surface", updated)
        self.assertIn("FlowGuard check-engine version: `1.2.3`", updated)

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
            self.assertIn("FlowGuard agent skill suite:", agents_text)
            self.assertIn("Primary agent surface: `.agents/skills/`", agents_text)
            self.assertIn("Default entry skill: `.agents/skills/flowguard/SKILL.md`", agents_text)
            self.assertIn("not the", agents_text)
            self.assertIn("AI-agent skill installation surface", agents_text)
            self.assertIn("FlowGuard check-engine version:", agents_text)
            self.assertIn("flowguard-development-process-flow", agents_text)
            self.assertIn("post-change scan signals", agents_text)
            self.assertIn("DevelopmentProcessFlow consume", agents_text)
            self.assertIn("Default replacement means dispose the old path", agents_text)
            self.assertIn("FieldLifecycleMesh", agents_text)
            manifest_text = (root / FLOWGUARD_PROJECT_MANIFEST).read_text(encoding="utf-8")
            self.assertIn(f'adopted_package_version = "{installed_flowguard_package_version()}"', manifest_text)
            self.assertIn(f'schema_version = "{flowguard.SCHEMA_VERSION}"', manifest_text)
            self.assertTrue((root / ".flowguard" / "adoption_log.jsonl").exists())
            self.assertTrue((root / "docs" / "flowguard_adoption_log.md").exists())

    def test_project_adopt_portable_revalidation_commands_in_reports_and_markdown_log(self):
        expected = (
            "python -m flowguard project-audit --root . --json",
            "python scripts/verify_skill_suite_markers.py --root . --json",
            "Rerun affected FlowGuard model checks and focused tests before broad confidence.",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory, "private project root")
            root.mkdir()
            (root / "AGENTS.md").write_text("# Existing\n", encoding="utf-8")

            adopt_report = adopt_project(root)
            audit_report = audit_project_adoption(root)
            markdown = (root / "docs" / "flowguard_adoption_log.md").read_text(
                encoding="utf-8"
            )
            absolute_root = str(root.resolve())

            self.assertTrue(adopt_report.ok, adopt_report.format_text())
            self.assertEqual(expected, adopt_report.required_revalidation)
            self.assertEqual(expected, audit_report.required_revalidation)
            self.assertEqual(list(expected), adopt_report.to_dict()["required_revalidation"])
            self.assertNotIn(absolute_root, "\n".join(adopt_report.required_revalidation))
            self.assertNotIn(absolute_root, "\n".join(audit_report.required_revalidation))
            self.assertNotIn(absolute_root, markdown)
            self.assertIn(expected[0], markdown)
            self.assertIn(expected[1], markdown)

    def test_audit_reports_newer_and_older_version_states(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text(build_flowguard_agents_block(), encoding="utf-8")
            manifest = root / FLOWGUARD_PROJECT_MANIFEST
            manifest.parent.mkdir(parents=True)
            manifest.write_text(current_project_manifest_text(package_version="0.1.0"), encoding="utf-8")

            with patch(
                "flowguard.project_adoption._load_suite_evidence",
                return_value=_passing_suite_evidence(),
            ):
                newer_report = audit_project_adoption(root)
            categories = {finding.category for finding in newer_report.findings}
            self.assertIn("project_flowguard_upgrade_available", categories)
            self.assertFalse(newer_report.ok)

            manifest.write_text(current_project_manifest_text(package_version="9999.0.0"), encoding="utf-8")
            with patch(
                "flowguard.project_adoption._load_suite_evidence",
                return_value=_passing_suite_evidence(),
            ):
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
            old_report = root / ".flowguard" / "old_report.json"
            old_report.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_type": "flowguard_test_report",
                        "payload": {"ok": True},
                    }
                ),
                encoding="utf-8",
            )

            with patch(
                "flowguard.project_adoption._load_suite_evidence",
                return_value=_passing_suite_evidence(),
            ):
                report = upgrade_project(root)

            self.assertTrue(report.ok, report.format_text())
            self.assertIsNotNone(report.artifact_upgrade_report)
            self.assertEqual(1, report.artifact_upgrade_report.upgraded_count)
            self.assertEqual(flowguard.SCHEMA_VERSION, json.loads(old_report.read_text(encoding="utf-8"))["schema_version"])
            manifest_text = manifest.read_text(encoding="utf-8")
            self.assertIn(f'adopted_package_version = "{installed_flowguard_package_version()}"', manifest_text)

    def test_project_upgrade_records_only_scopes_artifact_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text(build_flowguard_agents_block(package_version="0.1.0"), encoding="utf-8")
            manifest = root / FLOWGUARD_PROJECT_MANIFEST
            manifest.parent.mkdir(parents=True)
            manifest.write_text(current_project_manifest_text(package_version="0.1.0"), encoding="utf-8")
            old_report = root / ".flowguard" / "old_report.json"
            old_report.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "artifact_type": "flowguard_test_report",
                        "payload": {"ok": True},
                    }
                ),
                encoding="utf-8",
            )

            with patch(
                "flowguard.project_adoption._load_suite_evidence",
                return_value=_passing_suite_evidence(),
            ):
                report = upgrade_project(root, records_only=True)

            self.assertTrue(report.ok, report.format_text())
            self.assertIsNone(report.artifact_upgrade_report)
            categories = {finding.category for finding in report.findings}
            self.assertIn("artifact_upgrade_scan_scoped_out", categories)
            self.assertEqual("0.1", json.loads(old_report.read_text(encoding="utf-8"))["schema_version"])

    def test_audit_reports_stable_codes_for_missing_locked_rules(self):
        cases = (
            "behavior.commitment_ledger",
            "behavior.plane_partitioning",
            "behavior.primary_path_authority",
            "lifecycle.default_replacement",
            "runtime.latest_schema_first",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / FLOWGUARD_PROJECT_MANIFEST
            manifest.parent.mkdir(parents=True)
            package_version = installed_flowguard_package_version()
            manifest.write_text(
                current_project_manifest_text(package_version=package_version),
                encoding="utf-8",
            )
            original = build_flowguard_agents_block(package_version=package_version)

            for expected_rule_id in cases:
                with self.subTest(rule_id=expected_rule_id):
                    (root / "AGENTS.md").write_text(
                        _remove_managed_rule(original, expected_rule_id),
                        encoding="utf-8",
                    )
                    with patch(
                        "flowguard.project_adoption._load_suite_evidence",
                        return_value=_passing_suite_evidence(),
                    ):
                        report = audit_project_adoption(root)
                    rule_ids = {
                        dict(finding.metadata).get("rule_id")
                        for finding in report.findings
                        if finding.category == "missing_managed_rule"
                    }
                    self.assertIn(expected_rule_id, rule_ids, report.format_text())
                    self.assertFalse(report.ok)

    def test_audit_rejects_stale_rendered_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_version = installed_flowguard_package_version()
            (root / "AGENTS.md").write_text(
                build_flowguard_agents_block(package_version="0.1.0"),
                encoding="utf-8",
            )
            manifest = root / FLOWGUARD_PROJECT_MANIFEST
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                current_project_manifest_text(package_version=package_version),
                encoding="utf-8",
            )

            with patch(
                "flowguard.project_adoption._load_suite_evidence",
                return_value=_passing_suite_evidence(),
            ):
                report = audit_project_adoption(root)

            categories = {finding.category for finding in report.findings}
            self.assertIn("rendered_version_mismatch", categories)
            self.assertFalse(report.ok)

    def test_audit_rejects_partial_manifest_version_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_version = installed_flowguard_package_version()
            (root / "AGENTS.md").write_text(
                build_flowguard_agents_block(package_version=package_version),
                encoding="utf-8",
            )
            manifest = root / FLOWGUARD_PROJECT_MANIFEST
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                "[flowguard]\n"
                f'repository = "{FLOWGUARD_REPOSITORY_URL}"\n',
                encoding="utf-8",
            )

            with patch(
                "flowguard.project_adoption._load_suite_evidence",
                return_value=_passing_suite_evidence(),
            ):
                report = audit_project_adoption(root)

            categories = {finding.category for finding in report.findings}
            self.assertIn("manifest_package_version_missing", categories)
            self.assertIn("manifest_schema_version_missing", categories)
            self.assertFalse(report.ok)

    def test_writing_upgrade_rejects_ambiguous_managed_block_before_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_version = installed_flowguard_package_version()
            block = build_flowguard_agents_block(package_version=package_version)
            (root / "AGENTS.md").write_text(
                block + "\n\n" + block,
                encoding="utf-8",
            )
            manifest = root / FLOWGUARD_PROJECT_MANIFEST
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                current_project_manifest_text(package_version=package_version),
                encoding="utf-8",
            )
            before = _tree_snapshot(root)

            with patch(
                "flowguard.project_adoption._load_suite_evidence",
                return_value=_passing_suite_evidence(),
            ):
                report = upgrade_project(root)

            self.assertFalse(report.ok)
            self.assertIn(
                "managed_block_cardinality_mismatch",
                {item.category for item in report.findings},
            )
            self.assertEqual(before, _tree_snapshot(root))
            self.assertEqual((), report.written_files)

    def test_project_upgrade_dry_run_reports_plan_without_mutation(self):
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
            old_report = root / ".flowguard" / "old_report.json"
            old_report.write_text(
                json.dumps({"schema_version": "0.1", "artifact_type": "flowguard_test_report"}),
                encoding="utf-8",
            )
            before = _tree_snapshot(root)

            with patch(
                "flowguard.project_adoption._load_suite_evidence",
                return_value=_passing_suite_evidence(),
            ):
                report = upgrade_project(root, dry_run=True)

            self.assertTrue(report.ok, report.format_text())
            self.assertTrue(report.dry_run)
            self.assertEqual(before, _tree_snapshot(root))
            self.assertEqual((), report.written_files)
            self.assertIn(str(root / "AGENTS.md"), report.proposed_files)
            self.assertIn(str(root / FLOWGUARD_PROJECT_LOG), report.proposed_files)
            self.assertIsNotNone(report.artifact_upgrade_report)
            self.assertFalse(report.artifact_upgrade_report.apply)
            self.assertFalse((root / FLOWGUARD_PROJECT_LOG).exists())

    def test_blocked_dry_run_still_previews_artifact_upgrade_without_mutation(self):
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
            old_report = root / ".flowguard" / "old_report.json"
            old_report.write_text(
                json.dumps({"schema_version": "0.1", "artifact_type": "flowguard_test_report"}),
                encoding="utf-8",
            )
            before = _tree_snapshot(root)

            report = upgrade_project(root, dry_run=True)

            self.assertFalse(report.ok)
            self.assertIn("suite_inventory_unresolved", {item.category for item in report.findings})
            self.assertIsNotNone(report.artifact_upgrade_report)
            self.assertFalse(report.artifact_upgrade_report.apply)
            self.assertEqual(before, _tree_snapshot(root))
            self.assertEqual((), report.written_files)

    def test_writing_upgrade_blocks_older_engine_before_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text(
                build_flowguard_agents_block(package_version="9999.0.0"),
                encoding="utf-8",
            )
            manifest = root / FLOWGUARD_PROJECT_MANIFEST
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                current_project_manifest_text(package_version="9999.0.0"),
                encoding="utf-8",
            )
            before = _tree_snapshot(root)

            with patch(
                "flowguard.project_adoption._load_suite_evidence",
                return_value=_passing_suite_evidence(),
            ):
                report = upgrade_project(root)

            self.assertFalse(report.ok)
            self.assertIn("installed_flowguard_older", {item.category for item in report.findings})
            self.assertEqual(before, _tree_snapshot(root))
            self.assertEqual((), report.written_files)

    def test_writing_upgrade_blocks_generator_rule_loss_before_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_version = installed_flowguard_package_version()
            good_block = build_flowguard_agents_block(package_version=package_version)
            (root / "AGENTS.md").write_text(good_block, encoding="utf-8")
            manifest = root / FLOWGUARD_PROJECT_MANIFEST
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                current_project_manifest_text(package_version=package_version),
                encoding="utf-8",
            )
            broken_block = _remove_managed_rule(
                good_block,
                "behavior.primary_path_authority",
            )
            before = _tree_snapshot(root)

            with patch(
                "flowguard.project_adoption._load_suite_evidence",
                return_value=_passing_suite_evidence(),
            ), patch(
                "flowguard.project_adoption.build_flowguard_agents_block",
                return_value=broken_block,
            ):
                report = upgrade_project(root)

            self.assertFalse(report.ok)
            regressions = [
                item for item in report.findings if item.category == "governance_regression"
            ]
            self.assertEqual(1, len(regressions), report.format_text())
            self.assertIn(
                "behavior.primary_path_authority",
                dict(regressions[0].metadata)["missing_rule_ids"],
            )
            self.assertEqual(before, _tree_snapshot(root))

    def test_writing_upgrade_blocks_unresolved_suite_before_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_version = installed_flowguard_package_version()
            (root / "AGENTS.md").write_text(
                build_flowguard_agents_block(package_version=package_version),
                encoding="utf-8",
            )
            manifest = root / FLOWGUARD_PROJECT_MANIFEST
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                current_project_manifest_text(package_version=package_version),
                encoding="utf-8",
            )
            before = _tree_snapshot(root)

            report = upgrade_project(root)

            self.assertFalse(report.ok)
            self.assertIn("suite_inventory_unresolved", {item.category for item in report.findings})
            self.assertEqual(before, _tree_snapshot(root))
            self.assertEqual((), report.written_files)

    def test_project_upgrade_accepts_owned_mixed_root_and_rejects_reserved_extra(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill_root = root / ".agents" / "skills"
            foreign_files = {}
            for skill_id in ("skillguard", "skillguard-global-router"):
                path = skill_root / skill_id / "SKILL.md"
                path.parent.mkdir(parents=True, exist_ok=True)
                content = f"---\nname: {skill_id}\n---\n"
                path.write_text(content, encoding="utf-8")
                foreign_files[path] = content

            install_report = install_skill_suite(ROOT, skill_root)
            self.assertTrue(install_report.ok, install_report.to_dict())
            suite_map = root / FLOWGUARD_SUITE_MAP
            suite_map.parent.mkdir(parents=True, exist_ok=True)
            suite_map.write_bytes((ROOT / FLOWGUARD_SUITE_MAP).read_bytes())
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

            before_upgrade = audit_project_adoption(root)
            self.assertEqual("pass", before_upgrade.suite_status)
            self.assertFalse(before_upgrade.suite_findings)

            upgraded = upgrade_project(root, records_only=True)

            self.assertTrue(upgraded.ok, upgraded.format_text())
            self.assertEqual("pass", upgraded.suite_status)
            for path, content in foreign_files.items():
                self.assertEqual(content, path.read_text(encoding="utf-8"))
            after_upgrade = audit_project_adoption(root)
            self.assertTrue(after_upgrade.ok, after_upgrade.format_text())
            self.assertEqual("pass", after_upgrade.suite_status)

            fake = skill_root / "flowguard-unregistered" / "SKILL.md"
            fake.parent.mkdir(parents=True)
            fake.write_text("# fake FlowGuard member\n", encoding="utf-8")
            blocked = upgrade_project(root, records_only=True)

            self.assertFalse(blocked.ok)
            self.assertEqual("blocked", blocked.suite_status)
            self.assertIn(
                ("extra_discovered_member", "flowguard-unregistered"),
                {
                    (finding.get("code"), finding.get("member_id"))
                    for finding in blocked.suite_findings
                },
            )
            self.assertIn(
                "suite_inventory_unresolved",
                {finding.category for finding in blocked.findings},
            )

    def test_successful_upgrade_log_contains_before_after_hashes_and_checks(self):
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
                report = upgrade_project(root, records_only=True)

            self.assertTrue(report.ok, report.format_text())
            entry = json.loads(
                (root / FLOWGUARD_PROJECT_LOG).read_text(encoding="utf-8").splitlines()[-1]
            )
            metadata = dict(entry["metadata"])
            self.assertEqual("upgrade", metadata["actual_mode"])
            self.assertIn("before", metadata)
            self.assertIn("after", metadata)
            self.assertIn("managed_block_semantic_hash_before", metadata)
            self.assertIn("managed_block_semantic_hash_after", metadata)
            self.assertTrue(entry["has_commands"])
            self.assertEqual(3, entry["command_count"])

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

    def test_project_upgrade_cli_accepts_records_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text(build_flowguard_agents_block(package_version="0.1.0"), encoding="utf-8")
            manifest = root / FLOWGUARD_PROJECT_MANIFEST
            manifest.parent.mkdir(parents=True)
            manifest.write_text(current_project_manifest_text(package_version="0.1.0"), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "flowguard",
                    "project-upgrade",
                    "--root",
                    directory,
                    "--records-only",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertIsNone(payload["artifact_upgrade_report"])
            categories = {finding["category"] for finding in payload["findings"]}
            self.assertIn("suite_inventory_unresolved", categories)
            self.assertIn(
                "Artifact/model/test upgrade scanning was scoped out by records-only mode.",
                payload["skipped_steps"],
            )
            self.assertEqual([], payload["written_files"])

    def test_project_upgrade_cli_dry_run_is_non_mutating_when_blocked(self):
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
            before = _tree_snapshot(root)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "flowguard",
                    "project-upgrade",
                    "--root",
                    directory,
                    "--dry-run",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["dry_run"])
            self.assertEqual("blocked", payload["status"])
            self.assertIn(
                "suite_inventory_unresolved",
                {finding["category"] for finding in payload["findings"]},
            )
            self.assertEqual([], payload["written_files"])
            self.assertEqual(before, _tree_snapshot(root))


if __name__ == "__main__":
    unittest.main()
