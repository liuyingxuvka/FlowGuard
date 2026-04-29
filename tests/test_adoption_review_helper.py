import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flowguard.review import review_scenarios


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "flowguard_adoption_review_helper.py"
MODEL = ROOT / "examples" / "adoption_review_helper" / "model.py"
RUN_REVIEW = ROOT / "examples" / "adoption_review_helper" / "run_review.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class AdoptionReviewHelperModelTests(unittest.TestCase):
    def test_model_classification_rules_match_expected_outcomes(self):
        model = _load_module(MODEL, "test_adoption_review_helper_model")
        report = review_scenarios(model.scenarios())

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(5, report.total_scenarios)
        self.assertEqual(5, report.passed)

    def test_model_runner_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(RUN_REVIEW)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("adoption review helper model", result.stdout)


class AdoptionReviewHelperScriptTests(unittest.TestCase):
    def test_discovers_and_classifies_projects(self):
        helper = _load_module(HELPER, "test_flowguard_adoption_review_helper")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            complete = root / "CompleteProject"
            (complete / ".flowguard").mkdir(parents=True)
            (complete / "docs").mkdir()
            (complete / ".flowguard" / "adoption_log.jsonl").write_text(
                json.dumps(
                    {
                        "project": "CompleteProject",
                        "task_id": "t1",
                        "task_summary": "model retry behavior",
                        "status": "completed",
                        "ok": True,
                        "commands": [{"command": "python run_checks.py", "ok": True}],
                        "findings": ["repeated input is deduplicated"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (complete / "docs" / "flowguard_adoption_log.md").write_text("done", encoding="utf-8")

            pending = root / "PendingProject"
            (pending / ".flowguard" / "ui_flow").mkdir(parents=True)
            (pending / ".flowguard" / "ui_flow" / "model.py").write_text("# model", encoding="utf-8")
            (pending / "docs").mkdir()
            (pending / "docs" / "flowguard_adoption_log.md").write_text("notes", encoding="utf-8")

            fallback = root / "FallbackProject"
            (fallback / ".flowguard").mkdir(parents=True)
            (fallback / ".flowguard" / "adoption_log.jsonl").write_text(
                json.dumps(
                    {
                        "project": "FallbackProject",
                        "task_id": "t2",
                        "task_summary": "historical model",
                        "status": "completed",
                        "ok": True,
                        "commands": [{"command": "python model.py", "ok": True}],
                        "findings": ["temporary mini-framework fallback exposed a workflow issue"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            report = helper.build_report((root,), max_depth=4)
            classifications = {
                project["project"]: project["classification"]
                for project in report["projects"]
            }

            self.assertEqual("complete", classifications["CompleteProject"])
            self.assertEqual("in_progress", classifications["PendingProject"])
            self.assertEqual("historical_fallback", classifications["FallbackProject"])

    def test_completed_entries_with_skips_are_visibly_classified(self):
        helper = _load_module(HELPER, "test_flowguard_adoption_review_helper_skips")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "CompleteWithSkips"
            (project / ".flowguard").mkdir(parents=True)
            (project / ".flowguard" / "adoption_log.jsonl").write_text(
                json.dumps(
                    {
                        "project": "CompleteWithSkips",
                        "task_id": "t1",
                        "task_summary": "model visual flow",
                        "status": "completed",
                        "ok": True,
                        "commands": [{"command": "python run_checks.py", "ok": True}],
                        "findings": ["model passed"],
                        "skipped_steps": ["pixel-perfect replay skipped with reason"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            report = helper.build_report((root,), max_depth=3)

            self.assertEqual("complete_with_skips", report["projects"][0]["classification"])

    def test_flags_current_stale_fallback_model(self):
        helper = _load_module(HELPER, "test_flowguard_adoption_review_helper_stale_fallback")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "StaleFallback"
            (project / ".flowguard").mkdir(parents=True)
            (project / ".flowguard" / "khaos_brain_function_flow.py").write_text(
                "flowguard_package_available = False\n# fallback explorer\n",
                encoding="utf-8",
            )

            report = helper.build_report((root,), max_depth=3)
            project_report = report["projects"][0]

            self.assertIn("stale_fallback_model", project_report["flags"])
            self.assertEqual("pass_with_gaps", project_report["adoption_audit_status"])
            self.assertTrue(
                any("stale_fallback_model" in finding for finding in project_report["adoption_audit_findings"])
            )

    def test_cli_outputs_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "OneProject"
            (project / ".flowguard").mkdir(parents=True)
            (project / ".flowguard" / "adoption_log.jsonl").write_text(
                json.dumps(
                    {
                        "project": "OneProject",
                        "task_id": "t1",
                        "status": "completed",
                        "commands": [{"command": "python run_checks.py", "ok": True}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(HELPER), "--root", str(root), "--max-depth", "3"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(1, data["project_count"])
            self.assertEqual("complete", data["projects"][0]["classification"])


if __name__ == "__main__":
    unittest.main()
