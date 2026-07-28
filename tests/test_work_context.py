from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import flowguard
from flowguard.work_context import (
    WorkContext,
    discover_work_contexts,
    read_work_context,
    read_project_work_contexts,
    registered_work_context_adapter_ids,
    review_work_context,
)
from flowguard.work_context_adapters.declared_files import (
    DECLARED_FILES_ADAPTER_ID,
)
from flowguard.work_context_adapters.openspec import OPEN_SPEC_ADAPTER_ID


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


def declared_profile(root: Path, name: str) -> dict[str, object]:
    docs = root / "docs" / name
    docs.mkdir(parents=True)
    (docs / "requirements.md").write_text("Requirements\n", encoding="utf-8")
    (docs / "design.md").write_text("Design\n", encoding="utf-8")
    (docs / "plan.md").write_text("Plan\n", encoding="utf-8")
    return {
        "native_work_id": name,
        "native_owner_id": name,
        "context_root": f"docs/{name}",
        "required_artifact_roles": ("requirement", "design", "plan"),
        "artifacts": (
            {"path": "requirements.md", "artifact_role": "requirement"},
            {"path": "design.md", "artifact_role": "design"},
            {"path": "plan.md", "artifact_role": "plan"},
        ),
    }


class WorkContextTests(unittest.TestCase):
    def test_review_rereads_source_bytes_and_detects_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_change(root)
            context = read_work_context(
                root,
                "change-one",
                adapter_id=OPEN_SPEC_ADAPTER_ID,
            )
            (root / "openspec" / "changes" / "change-one" / "proposal.md").write_text(
                "mutated after context read\n",
                encoding="utf-8",
            )
            review = review_work_context(context)
            self.assertFalse(review.ok)
            self.assertIn(
                "work_context_artifact_source_changed",
                review.finding_codes,
            )

    def test_openspec_adapter_reads_artifacts_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_change(root)
            before = snapshot(root)

            context = read_work_context(
                root,
                "change-one",
                adapter_id=OPEN_SPEC_ADAPTER_ID,
            )
            review = review_work_context(context)

            self.assertTrue(review.ok, review.to_dict())
            self.assertEqual(OPEN_SPEC_ADAPTER_ID, context.adapter_id)
            self.assertEqual("official-openspec", context.native_owner_id)
            self.assertTrue(context.read_only)
            self.assertEqual(
                {"scope", "design", "requirement", "task", "status"},
                {item.artifact_role for item in context.artifacts},
            )
            self.assertEqual("in-progress", context.native_metadata["status"])
            self.assertEqual(before, snapshot(root))
            self.assertFalse((root / ".flowguard").exists())

    def test_declared_files_supports_spec_kit_and_superpowers_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contexts = tuple(
                read_work_context(
                    root,
                    provider,
                    adapter_id=DECLARED_FILES_ADAPTER_ID,
                    declaration=declared_profile(root, provider),
                )
                for provider in ("spec-kit", "superpowers")
            )

            self.assertEqual(2, len(contexts))
            self.assertEqual(
                {"spec-kit", "superpowers"},
                {item.native_owner_id for item in contexts},
            )
            self.assertTrue(all(review_work_context(item).ok for item in contexts))
            self.assertEqual(
                ("declared-files", "openspec"),
                registered_work_context_adapter_ids(),
            )

    def test_missing_required_role_and_provider_authority_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = declared_profile(root, "planner")
            profile["required_artifact_roles"] = ("requirement", "acceptance")
            profile["native_metadata"] = {"receipt_id": "provider-receipt"}
            context = read_work_context(
                root,
                "planner",
                adapter_id=DECLARED_FILES_ADAPTER_ID,
                declaration=profile,
            )

            review = review_work_context(context)

            self.assertFalse(review.ok)
            self.assertIn("work_context_required_role_missing", review.finding_codes)
            self.assertIn(
                "work_context_provider_authority_forbidden",
                review.finding_codes,
            )

    def test_unknown_adapter_and_unbounded_paths_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "adapter_unregistered"):
                read_work_context(root, "work", adapter_id="unknown")
            outside = root.parent / "outside-work-context.md"
            outside.write_text("outside", encoding="utf-8")
            try:
                with self.assertRaisesRegex(ValueError, "escapes project root"):
                    read_work_context(
                        root,
                        "work",
                        adapter_id=DECLARED_FILES_ADAPTER_ID,
                        declaration={
                            "context_root": "..",
                            "artifacts": (
                                {
                                    "path": outside.name,
                                    "artifact_role": "requirement",
                                },
                            ),
                        },
                    )
            finally:
                outside.unlink(missing_ok=True)

    def test_discovery_ignores_archive_and_hidden_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_change(root, "change-b")
            write_change(root, "change-a")
            (root / "openspec" / "changes" / ".hidden").mkdir()
            (root / "openspec" / "changes" / "archive").mkdir()

            contexts = discover_work_contexts(
                root,
                adapter_id=OPEN_SPEC_ADAPTER_ID,
            )

            self.assertEqual(
                ("change-a", "change-b"),
                tuple(item.native_work_id for item in contexts),
            )

    def test_stale_fingerprint_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = declared_profile(root, "planner")
            context = read_work_context(
                root,
                "planner",
                adapter_id=DECLARED_FILES_ADAPTER_ID,
                declaration=profile,
            )
            stale = WorkContext(
                **{
                    **{
                        key: value
                        for key, value in context.__dict__.items()
                        if key != "context_fingerprint"
                    },
                    "context_fingerprint": "sha256:" + "0" * 64,
                }
            )

            self.assertIn(
                "work_context_fingerprint_stale",
                review_work_context(stale).finding_codes,
            )

    def test_project_manifest_declares_required_peer_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = declared_profile(root, "superpowers")
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text(
                """
[[work_context.sources]]
source_id = "superpowers-plan"
adapter_id = "declared-files"
native_work_id = "superpowers"
native_owner_id = "superpowers"
context_root = "docs/superpowers"
required = true
required_artifact_roles = ["requirement", "design", "plan"]

[[work_context.sources.artifacts]]
artifact_id = "superpowers:requirement"
path = "requirements.md"
artifact_role = "requirement"

[[work_context.sources.artifacts]]
artifact_id = "superpowers:design"
path = "design.md"
artifact_role = "design"

[[work_context.sources.artifacts]]
artifact_id = "superpowers:plan"
path = "plan.md"
artifact_role = "plan"
""".strip()
                + "\n",
                encoding="utf-8",
            )

            review = read_project_work_contexts(root)

            self.assertTrue(review.ok, review.to_dict())
            self.assertEqual(("superpowers",), tuple(
                item.native_work_id for item in review.contexts
            ))
            self.assertTrue(
                review.declaration_fingerprint.startswith("sha256:")
            )

    def test_required_declared_source_that_discovers_nothing_is_visible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".flowguard" / "project.toml"
            manifest.parent.mkdir()
            manifest.write_text(
                """
[[work_context.sources]]
source_id = "required-empty"
adapter_id = "declared-files"
required = true
""".strip()
                + "\n",
                encoding="utf-8",
            )

            review = read_project_work_contexts(root)

            self.assertFalse(review.ok)
            self.assertIn(
                "required_work_context_source_empty",
                {finding.code for finding in review.findings},
            )

    def test_public_api_and_cli_expose_only_current_work_context_surface(self) -> None:
        self.assertTrue(flowguard.WORK_CONTEXT_API)
        self.assertIn("read_work_context", flowguard.WORK_CONTEXT_API)
        for retired in (
            "SPEC_CONTEXT_API",
            "SpecContext",
            "read_spec_context",
            "SPEC_WORK_PACKAGE_API",
            "SpecWorkPackage",
        ):
            self.assertFalse(hasattr(flowguard, retired), retired)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_change(root)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "flowguard",
                    "work-context",
                    "--root",
                    str(root),
                    "--adapter",
                    "openspec",
                    "--work-id",
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
            self.assertNotIn("spec-context", help_result.stdout)
            self.assertIn("work-context", help_result.stdout)


if __name__ == "__main__":
    unittest.main()
