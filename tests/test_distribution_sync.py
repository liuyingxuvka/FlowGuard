from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from flowguard.distribution_sync import (
    DEFAULT_EXCLUSION_RULES,
    OWNERSHIP_MANIFEST_NAME,
    check_skill_suite,
    compare_configured_skill_trees,
    install_skill_suite,
    inventory_skill_tree,
    semantic_hash_bytes,
    uninstall_skill_suite,
)


class DistributionFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "formal" / ".agents" / "skills"
        self.target = self.root / "codex" / "skills"
        self.members = ("model-first-function-flow", "flowguard-test-mesh")
        for member in self.members:
            (self.source / member / "agents").mkdir(parents=True)
            (self.source / member / "SKILL.md").write_text(f"# {member}\n", encoding="utf-8")
            (self.source / member / "agents" / "openai.yaml").write_text("name: fixture\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()


class TreeInventoryTests(DistributionFixture):
    def test_inventory_records_raw_and_semantic_hash_for_complete_tree(self) -> None:
        report = inventory_skill_tree(self.source, member_ids=self.members)
        self.assertTrue(report.ok)
        self.assertEqual(4, len(report.files))
        self.assertEqual(64, len(report.raw_tree_hash))
        self.assertEqual(64, len(report.semantic_tree_hash))
        self.assertTrue(all(len(item.raw_hash) == 64 for item in report.files))
        self.assertTrue(all(len(item.semantic_hash) == 64 for item in report.files))

    def test_semantic_hash_normalizes_newlines_but_raw_gate_does_not(self) -> None:
        unix = b"one\ntwo\n"
        windows = b"one\r\ntwo\r\n"
        self.assertEqual(
            semantic_hash_bytes(unix, relative_path="SKILL.md"),
            semantic_hash_bytes(windows, relative_path="SKILL.md"),
        )

    def test_current_run_receipt_is_explicitly_excluded(self) -> None:
        receipt = self.source / self.members[0] / ".skillguard" / "evidence" / "current.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text("{}", encoding="utf-8")
        report = inventory_skill_tree(self.source, member_ids=self.members)
        self.assertNotIn(receipt.relative_to(self.source).as_posix(), {item.relative_path for item in report.files})
        exclusion = next(item for item in report.excluded_files if item.relative_path.endswith("current.json"))
        self.assertEqual("current_evidence", exclusion.rule_id)
        self.assertTrue(exclusion.reason)
        self.assertIn(exclusion.pattern, {rule.pattern for rule in DEFAULT_EXCLUSION_RULES})

    def test_configured_parity_rejects_partial_file_copy_and_reports_exclusions(self) -> None:
        install_skill_suite(self.source, self.target, member_ids=self.members)
        (self.target / self.members[0] / "SKILL.md").unlink()
        report = compare_configured_skill_trees(
            {"source": self.source, "formal": self.source, "installed": self.target},
            member_ids=self.members,
        )
        self.assertFalse(report.ok)
        self.assertTrue(report.comparisons["formal"].ok)
        self.assertIn(f"{self.members[0]}/SKILL.md", report.comparisons["installed"].missing_files)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support is unavailable")
    def test_symlink_is_never_treated_as_an_owned_regular_file(self) -> None:
        external = self.root / "outside.txt"
        external.write_text("outside", encoding="utf-8")
        link = self.source / self.members[0] / "escape.txt"
        try:
            os.symlink(external, link)
        except OSError:
            self.skipTest("symlink creation is not permitted")
        report = inventory_skill_tree(self.source, member_ids=self.members)
        self.assertFalse(report.ok)
        self.assertIn(f"{self.members[0]}/escape.txt", report.unsafe_paths)


class DistributionLifecycleTests(DistributionFixture):
    def test_install_is_idempotent_and_manifest_owns_every_installed_file(self) -> None:
        first = install_skill_suite(self.source, self.target, member_ids=self.members)
        self.assertTrue(first.ok, first.to_dict())
        manifest_path = self.target / OWNERSHIP_MANIFEST_NAME
        first_manifest = manifest_path.read_bytes()
        second = install_skill_suite(self.source, self.target, member_ids=self.members)
        self.assertTrue(second.ok, second.to_dict())
        self.assertEqual((), second.copied_files)
        self.assertEqual(4, len(second.unchanged_files))
        self.assertEqual(first_manifest, manifest_path.read_bytes())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(4, len(manifest["files"]))
        self.assertTrue(all(row["raw_hash"] and row["semantic_hash"] for row in manifest["files"]))

    def test_check_is_strictly_read_only(self) -> None:
        install_skill_suite(self.source, self.target, member_ids=self.members)
        before = {
            path.relative_to(self.target).as_posix(): path.read_bytes()
            for path in self.target.rglob("*")
            if path.is_file()
        }
        report = check_skill_suite(self.source, self.target, member_ids=self.members)
        after = {
            path.relative_to(self.target).as_posix(): path.read_bytes()
            for path in self.target.rglob("*")
            if path.is_file()
        }
        self.assertTrue(report.ok, report.to_dict())
        self.assertEqual(before, after)

    def test_dry_run_does_not_create_target_or_manifest(self) -> None:
        report = install_skill_suite(self.source, self.target, member_ids=self.members, dry_run=True)
        self.assertTrue(report.ok, report.to_dict())
        self.assertEqual(4, len(report.copied_files))
        self.assertFalse(self.target.exists())

    def test_install_updates_unchanged_owned_file_when_source_changes(self) -> None:
        install_skill_suite(self.source, self.target, member_ids=self.members)
        source_file = self.source / self.members[0] / "SKILL.md"
        target_file = self.target / self.members[0] / "SKILL.md"
        source_file.write_text("# upgraded\n", encoding="utf-8")
        report = install_skill_suite(self.source, self.target, member_ids=self.members)
        self.assertTrue(report.ok, report.to_dict())
        self.assertIn(f"{self.members[0]}/SKILL.md", report.copied_files)
        self.assertEqual(source_file.read_bytes(), target_file.read_bytes())

    def test_user_modified_file_is_preserved_as_conflict(self) -> None:
        install_skill_suite(self.source, self.target, member_ids=self.members)
        target_file = self.target / self.members[0] / "SKILL.md"
        target_file.write_text("# user modification\n", encoding="utf-8")
        source_file = self.source / self.members[0] / "SKILL.md"
        source_file.write_text("# upstream modification\n", encoding="utf-8")
        report = install_skill_suite(self.source, self.target, member_ids=self.members)
        self.assertFalse(report.ok)
        self.assertIn(f"{self.members[0]}/SKILL.md", report.conflict_files)
        self.assertEqual("# user modification\n", target_file.read_text(encoding="utf-8"))

    def test_explicit_adoption_replaces_existing_canonical_file_and_establishes_ownership(self) -> None:
        target_file = self.target / self.members[0] / "SKILL.md"
        target_file.parent.mkdir(parents=True)
        target_file.write_text("# old unmanaged install\n", encoding="utf-8")
        report = install_skill_suite(
            self.source,
            self.target,
            member_ids=self.members,
            adopt_existing=True,
        )
        relative = f"{self.members[0]}/SKILL.md"
        self.assertTrue(report.ok, report.to_dict())
        self.assertEqual("pass_with_gaps", report.status)
        self.assertIn(relative, report.adopted_files)
        self.assertEqual((self.source / relative).read_bytes(), target_file.read_bytes())
        finding = next(item for item in report.findings if item.relative_path == relative)
        self.assertEqual("existing_file_adopted", finding.code)
        self.assertEqual("replace_and_adopt", finding.metadata["disposition"])
        manifest = json.loads((self.target / OWNERSHIP_MANIFEST_NAME).read_text(encoding="utf-8"))
        self.assertIn(relative, {row["relative_path"] for row in manifest["files"]})

    def test_explicit_adoption_dry_run_reports_takeover_without_writing(self) -> None:
        target_file = self.target / self.members[0] / "SKILL.md"
        target_file.parent.mkdir(parents=True)
        target_file.write_text("# old unmanaged install\n", encoding="utf-8")
        before = target_file.read_bytes()
        report = install_skill_suite(
            self.source,
            self.target,
            member_ids=self.members,
            adopt_existing=True,
            dry_run=True,
        )
        self.assertIn(f"{self.members[0]}/SKILL.md", report.adopted_files)
        self.assertEqual(before, target_file.read_bytes())
        self.assertFalse((self.target / OWNERSHIP_MANIFEST_NAME).exists())

    def test_explicit_adoption_never_changes_unowned_extra_or_unrelated_skill(self) -> None:
        target_file = self.target / self.members[0] / "SKILL.md"
        target_file.parent.mkdir(parents=True)
        target_file.write_text("# old unmanaged install\n", encoding="utf-8")
        extra = self.target / self.members[0] / "private-notes.txt"
        extra.write_text("keep canonical-member extra", encoding="utf-8")
        unrelated = self.target / "unrelated-skill" / "SKILL.md"
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text("# unrelated\n", encoding="utf-8")
        report = install_skill_suite(
            self.source,
            self.target,
            member_ids=self.members,
            adopt_existing=True,
        )
        self.assertFalse(report.ok)
        self.assertIn(f"{self.members[0]}/private-notes.txt", report.extra_files)
        self.assertEqual("keep canonical-member extra", extra.read_text(encoding="utf-8"))
        self.assertEqual("# unrelated\n", unrelated.read_text(encoding="utf-8"))

    def test_extra_obsolete_file_is_reported_and_never_silently_deleted(self) -> None:
        install_skill_suite(self.source, self.target, member_ids=self.members)
        extra = self.target / self.members[0] / "legacy.txt"
        extra.write_text("legacy", encoding="utf-8")
        report = check_skill_suite(self.source, self.target, member_ids=self.members)
        self.assertFalse(report.ok)
        self.assertIn(f"{self.members[0]}/legacy.txt", report.extra_files)
        self.assertTrue(extra.is_file())

    def test_uninstall_removes_only_unchanged_owned_files_and_keeps_manifest_for_conflict(self) -> None:
        install_skill_suite(self.source, self.target, member_ids=self.members)
        changed = self.target / self.members[0] / "SKILL.md"
        changed.write_text("# user modification\n", encoding="utf-8")
        report = uninstall_skill_suite(self.target)
        self.assertFalse(report.ok)
        self.assertTrue(changed.is_file())
        self.assertTrue((self.target / OWNERSHIP_MANIFEST_NAME).is_file())
        manifest = json.loads((self.target / OWNERSHIP_MANIFEST_NAME).read_text(encoding="utf-8"))
        self.assertEqual([f"{self.members[0]}/SKILL.md"], [row["relative_path"] for row in manifest["files"]])
        self.assertFalse((self.target / self.members[1] / "SKILL.md").exists())

    def test_clean_uninstall_removes_manifest_but_preserves_unowned_extra(self) -> None:
        install_skill_suite(self.source, self.target, member_ids=self.members)
        extra = self.target / self.members[0] / "user.txt"
        extra.write_text("user", encoding="utf-8")
        report = uninstall_skill_suite(self.target)
        self.assertTrue(report.ok, report.to_dict())
        self.assertEqual("pass_with_gaps", report.status)
        self.assertTrue(extra.is_file())
        self.assertFalse((self.target / OWNERSHIP_MANIFEST_NAME).exists())

    def test_manifest_path_traversal_blocks_uninstall(self) -> None:
        self.target.mkdir(parents=True)
        payload = {
            "schema_version": "flowguard.skill_distribution_ownership.v1",
            "files": [{"relative_path": "../outside", "raw_hash": "X", "semantic_hash": "X", "size": 1}],
        }
        (self.target / OWNERSHIP_MANIFEST_NAME).write_text(json.dumps(payload), encoding="utf-8")
        report = uninstall_skill_suite(self.target)
        self.assertFalse(report.ok)
        self.assertEqual("ownership_manifest_unavailable", report.findings[0].code)


if __name__ == "__main__":
    unittest.main()
