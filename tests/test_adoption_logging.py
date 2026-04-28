import json
import tempfile
import unittest
from pathlib import Path

from flowguard.adoption import (
    ADOPTION_STATUSES,
    AdoptionCommandResult,
    AdoptionTimer,
    append_jsonl,
    append_markdown_log,
    make_adoption_log_entry,
)
from flowguard.templates import adoption_template_files


class AdoptionLoggingTests(unittest.TestCase):
    def test_adoption_entry_exports_json_and_markdown(self):
        entry = make_adoption_log_entry(
            task_id="task-1",
            project="demo",
            task_summary="Add idempotent retry handling",
            trigger_reason="retry and side-effect workflow",
            started_at="2026-04-28T10:00:00+00:00",
            ended_at="2026-04-28T10:00:03+00:00",
            duration_seconds=3.2,
            model_files=("flowguard_model/model.py",),
            commands=(
                AdoptionCommandResult(
                    "python -m flowguard scenario-review",
                    True,
                    duration_seconds=1.25,
                    summary="scenario review passed",
                ),
            ),
            findings=("No duplicate side effect observed.",),
            counterexamples=("none",),
            friction_points=("adapter projection needed a raw-state check",),
            skipped_steps=("conformance replay skipped: production code not present",),
            next_actions=("implement production code",),
        )

        data = entry.to_dict()
        self.assertEqual("flowguard_adoption_log_entry", data["artifact_type"])
        self.assertEqual("task-1", data["task_id"])
        self.assertEqual("completed", data["status"])
        self.assertTrue(data["ok"])
        self.assertTrue(data["complete"])
        self.assertTrue(data["has_commands"])
        self.assertEqual(1, data["command_count"])
        self.assertEqual("python -m flowguard scenario-review", data["commands"][0]["command"])
        self.assertEqual(data, json.loads(entry.to_json_text()))

        markdown = entry.format_markdown()
        self.assertIn("Add idempotent retry handling", markdown)
        self.assertIn("Status: completed", markdown)
        self.assertIn("Duration seconds: 3.200", markdown)
        self.assertIn("adapter projection", markdown)

    def test_jsonl_and_markdown_append_create_parent_directories(self):
        entry = make_adoption_log_entry(
            task_id="task-2",
            project="demo",
            task_summary="Check duplicate records",
            trigger_reason="deduplication risk",
            commands=(AdoptionCommandResult("python -m flowguard benchmark", True),),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jsonl_path = root / ".flowguard" / "adoption_log.jsonl"
            markdown_path = root / "docs" / "flowguard_adoption_log.md"

            append_jsonl(jsonl_path, entry)
            append_markdown_log(markdown_path, entry)

            json_lines = jsonl_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(1, len(json_lines))
            self.assertEqual("task-2", json.loads(json_lines[0])["task_id"])
            self.assertIn("Check duplicate records", markdown_path.read_text(encoding="utf-8"))

    def test_timer_builds_non_negative_entry(self):
        timer = AdoptionTimer(
            task_id="task-3",
            project="demo",
            task_summary="Model cache behavior",
            trigger_reason="cache consistency risk",
        )
        entry = timer.finish(commands=(AdoptionCommandResult("python -m flowguard coverage", True),))
        self.assertGreaterEqual(entry.duration_seconds, 0)
        self.assertEqual("used_flowguard", entry.skill_decision)
        self.assertEqual("completed", entry.status)
        self.assertTrue(entry.ok)

    def test_status_distinguishes_in_progress_blocked_and_failed(self):
        self.assertIn("in_progress", ADOPTION_STATUSES)
        in_progress = make_adoption_log_entry(
            task_id="task-4",
            project="demo",
            task_summary="Model still running",
            trigger_reason="active adoption session",
            status="in_progress",
        )
        self.assertEqual("in_progress", in_progress.to_dict()["status"])
        self.assertFalse(in_progress.to_dict()["complete"])

        blocked = make_adoption_log_entry(
            task_id="task-5",
            project="demo",
            task_summary="Toolchain blocked",
            trigger_reason="flowguard import failed",
            status="blocked_or_partial",
            skipped_steps=("formal flowguard package unavailable",),
        )
        self.assertEqual("blocked", blocked.status)
        self.assertFalse(blocked.complete)

        failed = make_adoption_log_entry(
            task_id="task-6",
            project="demo",
            task_summary="Model check failed",
            trigger_reason="scenario violation",
            commands=(AdoptionCommandResult("python model.py", False),),
        )
        self.assertEqual("failed", failed.status)
        self.assertFalse(failed.ok)

    def test_invalid_status_is_rejected(self):
        with self.assertRaises(ValueError):
            make_adoption_log_entry(
                task_id="task-bad",
                project="demo",
                task_summary="Bad status",
                trigger_reason="schema validation",
                status="almost_done",
            )

    def test_adoption_templates_are_available_without_file_writes(self):
        files = adoption_template_files()
        paths = {item.path for item in files}
        self.assertIn("docs/flowguard_adoption_log.md", paths)
        self.assertIn("docs/flowguard_model_notes.md", paths)
        for item in files:
            self.assertTrue(item.content.strip())


if __name__ == "__main__":
    unittest.main()
