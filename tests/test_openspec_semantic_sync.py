from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_openspec_semantic_sync.py"


def _load_checker():
    name = "test_check_openspec_semantic_sync"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CHECKER = _load_checker()


def _main_spec(name: str = "Original", *, second_scenario: bool = False) -> str:
    extra = (
        "\n#### Scenario: Existing second\n"
        "- **WHEN** second\n"
        "- **THEN** preserved\n"
        if second_scenario
        else ""
    )
    return (
        "# demo Specification\n\n"
        "## Purpose\n"
        "Fixture.\n\n"
        "## Requirements\n"
        f"### Requirement: {name}\n"
        "The system SHALL retain exact behavior.\n\n"
        "#### Scenario: Existing\n"
        "- **WHEN** the behavior is used\n"
        "- **THEN** it remains exact\n"
        f"{extra}"
    )


def _write_change(
    root: Path,
    change: str,
    delta: str,
    *,
    capability: str = "demo",
) -> Path:
    path = root / "openspec" / "changes" / change / "specs" / capability / "spec.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(delta, encoding="utf-8")
    return path


class DeltaProjectionTests(unittest.TestCase):
    def test_exact_modification_replaces_block_and_preserves_scenarios(self) -> None:
        current = _main_spec(second_scenario=True)
        delta = (
            "## MODIFIED Requirements\n\n"
            "### Requirement: Original\n"
            "The system SHALL use the revised exact behavior.\n\n"
            "#### Scenario: Existing\n"
            "- **WHEN** the behavior is used\n"
            "- **THEN** it remains exact\n\n"
            "#### Scenario: Existing second\n"
            "- **WHEN** second\n"
            "- **THEN** preserved\n"
        )

        projected, counts = CHECKER.apply_delta_projection(
            current,
            delta,
            capability="demo",
            change_id="change",
        )

        self.assertIn("revised exact behavior", projected)
        self.assertEqual(
            {"added": 0, "modified": 1, "removed": 0, "renamed": 0},
            counts,
        )

    def test_modification_cannot_drop_a_current_scenario(self) -> None:
        delta = (
            "## MODIFIED Requirements\n\n"
            "### Requirement: Original\n"
            "Revised.\n\n"
            "#### Scenario: Existing\n"
            "- **WHEN** used\n"
            "- **THEN** exact\n"
        )

        with self.assertRaisesRegex(
            CHECKER.SemanticSyncError,
            "would drop current scenario",
        ):
            CHECKER.apply_delta_projection(
                _main_spec(second_scenario=True),
                delta,
                capability="demo",
                change_id="change",
            )

    def test_explicit_rename_then_modify_uses_new_header(self) -> None:
        delta = (
            "## RENAMED Requirements\n\n"
            "- FROM: `Original`\n"
            "- TO: `Current name`\n\n"
            "## MODIFIED Requirements\n\n"
            "### Requirement: Current name\n"
            "The system SHALL use the current name.\n\n"
            "#### Scenario: Existing\n"
            "- **WHEN** the behavior is used\n"
            "- **THEN** it remains exact\n"
        )

        projected, counts = CHECKER.apply_delta_projection(
            _main_spec(),
            delta,
            capability="demo",
            change_id="change",
        )

        self.assertIn("### Requirement: Current name", projected)
        self.assertNotIn("### Requirement: Original", projected)
        self.assertEqual(1, counts["renamed"])
        self.assertEqual(1, counts["modified"])

    def test_rename_preserves_requirement_position(self) -> None:
        current = (
            _main_spec()
            + "\n### Requirement: Following\n"
            "The system SHALL preserve ordering.\n"
        )
        delta = (
            "## RENAMED Requirements\n\n"
            "- FROM: `Original`\n"
            "- TO: `Current name`\n"
        )

        projected, _ = CHECKER.apply_delta_projection(
            current,
            delta,
            capability="demo",
            change_id="change",
        )

        self.assertLess(
            projected.index("### Requirement: Current name"),
            projected.index("### Requirement: Following"),
        )

    def test_added_title_must_be_absent_even_when_block_is_identical(self) -> None:
        delta = (
            "## ADDED Requirements\n\n"
            "### Requirement: Original\n"
            "The system SHALL retain exact behavior.\n\n"
            "#### Scenario: Existing\n"
            "- **WHEN** the behavior is used\n"
            "- **THEN** it remains exact\n"
        )

        with self.assertRaisesRegex(CHECKER.SemanticSyncError, "already exists"):
            CHECKER.apply_delta_projection(
                _main_spec(),
                delta,
                capability="demo",
                change_id="change",
            )

    def test_rename_cannot_modify_old_header(self) -> None:
        delta = (
            "## RENAMED Requirements\n\n"
            "- FROM: `Original`\n"
            "- TO: `Current name`\n\n"
            "## MODIFIED Requirements\n\n"
            "### Requirement: Original\n"
            "Wrong header.\n"
        )

        with self.assertRaisesRegex(
            CHECKER.SemanticSyncError,
            "MODIFIED must use renamed target",
        ):
            CHECKER.parse_delta_spec(delta)

    def test_missing_and_ambiguous_sources_block(self) -> None:
        missing_delta = (
            "## MODIFIED Requirements\n\n"
            "### Requirement: Absent\n"
            "Missing.\n"
        )
        with self.assertRaisesRegex(CHECKER.SemanticSyncError, "source not found"):
            CHECKER.apply_delta_projection(
                _main_spec(),
                missing_delta,
                capability="demo",
                change_id="change",
            )

        ambiguous = _main_spec() + (
            "\n### Requirement: Original\n"
            "Duplicate.\n\n"
            "#### Scenario: Duplicate\n"
            "- **WHEN** duplicate\n"
            "- **THEN** block\n"
        )
        with self.assertRaisesRegex(
            CHECKER.SemanticSyncError,
            "ambiguous current requirement",
        ):
            CHECKER.apply_delta_projection(
                ambiguous,
                (
                    "## MODIFIED Requirements\n\n"
                    "### Requirement: Original\n"
                    "Modified.\n\n"
                    "#### Scenario: Existing\n"
                    "- **WHEN** the behavior is used\n"
                    "- **THEN** it remains exact\n"
                ),
                capability="demo",
                change_id="change",
            )

    def test_unmatched_delta_for_new_capability_blocks(self) -> None:
        with self.assertRaisesRegex(
            CHECKER.SemanticSyncError,
            "only ADDED is valid",
        ):
            CHECKER.apply_delta_projection(
                None,
                (
                    "## MODIFIED Requirements\n\n"
                    "### Requirement: Absent\n"
                    "Missing target.\n"
                ),
                capability="new-demo",
                change_id="change",
            )


class HistoryLedgerTests(unittest.TestCase):
    def test_pending_duplicate_and_missing_history_rows_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = (
                root
                / "openspec"
                / "changes"
                / "archive"
                / "2026-01-01-example"
                / "specs"
                / "demo"
                / "spec.md"
            )
            archive.parent.mkdir(parents=True)
            archive.write_text(
                "## ADDED Requirements\n\n"
                "### Requirement: Historical\n"
                "Historical behavior.\n",
                encoding="utf-8",
            )
            key = (
                "2026-01-01-example",
                "demo",
                "ADDED",
                "Historical",
            )
            pending = {
                "schema_version": CHECKER.LEDGER_SCHEMA_VERSION,
                "rows": [
                    {
                        "source_change": key[0],
                        "capability": key[1],
                        "operation": key[2],
                        "requirement": key[3],
                        "disposition": "pending",
                    },
                    {
                        "source_change": key[0],
                        "capability": key[1],
                        "operation": key[2],
                        "requirement": key[3],
                        "disposition": "pending",
                    },
                ],
            }

            result = CHECKER.validate_history_ledger_data(
                root,
                pending,
                expected_keys={key, ("other", "demo", "ADDED", "Missing")},
                required_counts=None,
            )

            codes = {finding["code"] for finding in result["findings"]}
            self.assertEqual("blocked", result["status"])
            self.assertIn("ledger_duplicate_key", codes)
            self.assertIn("ledger_history_key_missing", codes)
            self.assertIn("ledger_pending_or_unknown_disposition", codes)


class PrePostArchiveTests(unittest.TestCase):
    def test_skip_specs_freezes_unchanged_current_and_archived_delta_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current = root / "openspec" / "specs" / "demo" / "spec.md"
            current.parent.mkdir(parents=True)
            original = _main_spec(second_scenario=True)
            current.write_text(original, encoding="utf-8")
            delta_path = _write_change(
                root,
                "skip-change",
                (
                    "## RENAMED Requirements\n\n"
                    "- FROM: `Old pre-sync name`\n"
                    "- TO: `Original`\n\n"
                    "## MODIFIED Requirements\n\n"
                    "### Requirement: Original\n"
                    "Already synchronized current truth.\n"
                ),
            )
            before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }

            projection = CHECKER.build_pre_archive_projection(
                root,
                "skip-change",
                skip_specs=True,
            )

            after = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            self.assertEqual("pass", projection["status"], projection["findings"])
            self.assertEqual("skip_specs", projection["provider_mode"])
            self.assertEqual("openspec", projection["provider_identity"]["id"])
            self.assertFalse(projection["provider_identity"]["operation_invoked"])
            self.assertEqual(
                ["RENAMED", "REMOVED", "MODIFIED", "ADDED"],
                projection["operation_order"],
            )
            self.assertEqual(before, after)
            self.assertEqual(
                projection["capabilities"][0]["pre_raw_sha256"],
                projection["capabilities"][0]["expected_raw_sha256"],
            )
            self.assertEqual(
                {"added": 0, "modified": 0, "removed": 0, "renamed": 0},
                projection["capabilities"][0]["applied_counts"],
            )

            archived = (
                root
                / "openspec"
                / "changes"
                / "archive"
                / "2026-01-01-skip-change"
            )
            archived_delta = archived / "specs" / "demo" / "spec.md"
            archived_delta.parent.mkdir(parents=True)
            shutil.copyfile(delta_path, archived_delta)
            result = CHECKER.compare_post_archive(root, projection, archive_dir=archived)
            self.assertEqual("pass", result["status"], result["findings"])

            current.write_text(original + "\nChanged after freeze.\n", encoding="utf-8")
            mismatch = CHECKER.compare_post_archive(
                root,
                projection,
                archive_dir=archived,
            )
            self.assertEqual("blocked", mismatch["status"])
            self.assertIn(
                "post_archive_raw_mismatch",
                {finding["code"] for finding in mismatch["findings"]},
            )

    def test_skip_specs_detects_byte_only_newline_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current = root / "openspec" / "specs" / "demo" / "spec.md"
            current.parent.mkdir(parents=True)
            original = _main_spec().replace("\n", "\r\n")
            current.write_bytes(original.encode("utf-8"))
            delta_path = _write_change(
                root,
                "skip-change",
                (
                    "## MODIFIED Requirements\n\n"
                    "### Requirement: Original\n"
                    "Already synchronized current truth.\n"
                ),
            )
            projection = CHECKER.build_pre_archive_projection(
                root,
                "skip-change",
                skip_specs=True,
            )
            archived = (
                root
                / "openspec"
                / "changes"
                / "archive"
                / "2026-01-01-skip-change"
            )
            archived_delta = archived / "specs" / "demo" / "spec.md"
            archived_delta.parent.mkdir(parents=True)
            shutil.copyfile(delta_path, archived_delta)

            current.write_bytes(original.replace("\r\n", "\n").encode("utf-8"))
            mismatch = CHECKER.compare_post_archive(
                root,
                projection,
                archive_dir=archived,
            )

            codes = {finding["code"] for finding in mismatch["findings"]}
            self.assertIn("post_archive_raw_mismatch", codes)
            self.assertNotIn("post_archive_semantic_mismatch", codes)

    def test_post_archive_semantic_mismatch_is_reported_without_repair(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current = root / "openspec" / "specs" / "demo" / "spec.md"
            current.parent.mkdir(parents=True)
            current.write_text(_main_spec(), encoding="utf-8")
            delta_path = _write_change(
                root,
                "normal-change",
                (
                    "## ADDED Requirements\n\n"
                    "### Requirement: Added\n"
                    "The system SHALL add behavior.\n\n"
                    "#### Scenario: Added behavior\n"
                    "- **WHEN** invoked\n"
                    "- **THEN** added\n"
                ),
            )
            projection = CHECKER.build_pre_archive_projection(root, "normal-change")
            self.assertEqual("pass", projection["status"], projection["findings"])

            archived = (
                root
                / "openspec"
                / "changes"
                / "archive"
                / "2026-01-01-normal-change"
            )
            archived_delta = archived / "specs" / "demo" / "spec.md"
            archived_delta.parent.mkdir(parents=True)
            shutil.copyfile(delta_path, archived_delta)

            result = CHECKER.compare_post_archive(root, projection, archive_dir=archived)

            self.assertEqual("blocked", result["status"])
            codes = {finding["code"] for finding in result["findings"]}
            self.assertIn("post_archive_raw_mismatch", codes)
            self.assertIn("post_archive_semantic_mismatch", codes)
            self.assertNotIn("### Requirement: Added", current.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
