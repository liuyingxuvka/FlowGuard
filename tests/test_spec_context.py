from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import flowguard
from flowguard.spec_context import (
    discover_openspec_contexts,
    read_openspec_context,
    read_spec_context,
    review_spec_context,
)


ROOT = Path(__file__).resolve().parents[1]


def write_change(root: Path, change_id: str = "change-one") -> Path:
    change = root / "openspec" / "changes" / change_id
    (change / "specs" / "feature").mkdir(parents=True)
    (change / "proposal.md").write_text("# Why\n\nDo the thing.\n", encoding="utf-8")
    (change / "design.md").write_text("# Design\n\nKeep it small.\n", encoding="utf-8")
    (change / "tasks.md").write_text("- [x] 1. Read\n- [ ] 2. Build\n", encoding="utf-8")
    (change / "specs" / "feature" / "spec.md").write_text(
        "# Requirement\n\nThe system SHALL work.\n",
        encoding="utf-8",
    )
    return change


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


class SpecContextTests(unittest.TestCase):
    def test_reads_only_official_openspec_authoring_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_change(root)
            before = snapshot(root)

            context = read_openspec_context(root, "change-one")
            review = review_spec_context(context)

            self.assertTrue(review.ok, review.to_dict())
            self.assertEqual("openspec", context.provider_id)
            self.assertEqual("read_only_external", context.provider_role)
            self.assertTrue(context.read_only)
            self.assertEqual("in-progress", context.status)
            self.assertEqual(2, context.task_count)
            self.assertEqual(1, context.completed_task_count)
            self.assertEqual(
                {"proposal", "design", "tasks", "specification", "status"},
                {item.artifact_kind for item in context.artifacts},
            )
            self.assertEqual(
                len(context.artifacts),
                len({item.artifact_id for item in context.artifacts}),
            )
            self.assertEqual(before, snapshot(root))
            self.assertFalse((root / ".flowguard").exists())

    def test_completed_tasks_project_complete_status_without_provider_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            change = write_change(root)
            (change / "tasks.md").write_text("- [x] 1. Read\n- [x] 2. Build\n", encoding="utf-8")

            context = read_spec_context(root, "change-one")

            self.assertEqual("complete", context.status)
            payload = context.to_dict()
            text = json.dumps(payload).casefold()
            for forbidden in ("session_id", "receipt_id", "check_owner", "cache_path"):
                self.assertNotIn(forbidden, text)

    def test_missing_material_is_visible_and_never_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            change = root / "openspec" / "changes" / "partial"
            change.mkdir(parents=True)
            (change / "proposal.md").write_text("# Why\n", encoding="utf-8")
            before = snapshot(root)

            review = review_spec_context(read_openspec_context(root, "partial"))

            self.assertFalse(review.ok)
            self.assertIn("openspec_design_missing", review.finding_codes)
            self.assertIn("openspec_tasks_missing", review.finding_codes)
            self.assertIn("openspec_specification_missing", review.finding_codes)
            self.assertEqual(before, snapshot(root))

    def test_provider_and_change_boundaries_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_change(root)
            with self.assertRaisesRegex(ValueError, "unsupported_spec_provider"):
                read_spec_context(root, "change-one", provider_id="speckit")
            for unsafe in ("../change-one", "nested/change-one", ""):
                with self.subTest(unsafe=unsafe):
                    with self.assertRaises(ValueError):
                        read_openspec_context(root, unsafe)

    def test_discovery_returns_only_current_change_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_change(root, "change-b")
            write_change(root, "change-a")
            (root / "openspec" / "changes" / ".hidden").mkdir()

            contexts = discover_openspec_contexts(root)

            self.assertEqual(("change-a", "change-b"), tuple(item.change_id for item in contexts))

    def test_nested_specifications_have_distinct_stable_artifact_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            change = write_change(root)
            second = change / "specs" / "other" / "spec.md"
            second.parent.mkdir(parents=True)
            second.write_text("# Requirement\n\nThe other system SHALL work.\n", encoding="utf-8")

            first = read_openspec_context(root, "change-one")
            second_read = read_openspec_context(root, "change-one")
            specification_ids = tuple(
                item.artifact_id
                for item in first.artifacts
                if item.artifact_kind == "specification"
            )

            self.assertEqual(2, len(specification_ids))
            self.assertEqual(2, len(set(specification_ids)))
            self.assertEqual(
                tuple(item.artifact_id for item in first.artifacts),
                tuple(item.artifact_id for item in second_read.artifacts),
            )

    def test_public_api_exposes_context_and_removes_execution_bridge(self) -> None:
        self.assertTrue(flowguard.SPEC_CONTEXT_API)
        self.assertIn("read_openspec_context", flowguard.SPEC_CONTEXT_API)
        for retired in (
            "SPEC_WORK_PACKAGE_API",
            "begin_spec_session",
            "close_spec_session",
            "run_spec_check",
            "SpecWorkPackage",
        ):
            self.assertFalse(hasattr(flowguard, retired), retired)

    def test_cli_emits_read_only_context_and_retired_commands_are_absent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_change(root)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "flowguard",
                    "spec-context",
                    "--root",
                    str(root),
                    "--change",
                    "change-one",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["context"]["read_only"])

            help_result = subprocess.run(
                [sys.executable, "-m", "flowguard", "--help"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, help_result.returncode)
            for retired in (
                "spec-session-begin",
                "spec-session-close",
                "spec-check-run",
                "spec-work-package-audit",
            ):
                self.assertNotIn(retired, help_result.stdout)


if __name__ == "__main__":
    unittest.main()
