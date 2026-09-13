import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flowguard.project_adoption import (
    _SuiteEvidence,
    adopt_project,
    audit_project_adoption,
    upgrade_project,
)
from flowguard.project_layout import (
    CANONICAL_ROLE_ROOTS,
    current_layout_manifest_text,
    current_layout_readme_text,
)


class ProjectLayoutIntegrationTests(unittest.TestCase):
    def test_empty_adoption_bootstraps_only_the_current_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text("# Existing\n", encoding="utf-8")
            suite = _SuiteEvidence(True, "pass", "inventory", "semantic", ())
            with patch("flowguard.project_adoption._load_suite_evidence", return_value=suite):
                report = adopt_project(root)
            self.assertTrue(report.ok, report.format_text())
            layout = root / ".flowguard" / "layout.toml"
            self.assertEqual(current_layout_manifest_text(root), layout.read_text(encoding="utf-8"))
            self.assertEqual(
                current_layout_readme_text(),
                (root / ".flowguard" / "README.md").read_text(encoding="utf-8"),
            )
            for role_name, _role in CANONICAL_ROLE_ROOTS:
                self.assertFalse((root / ".flowguard" / role_name).exists())
            self.assertIn("project_layout_current", report.checks)

    def test_old_layout_blocks_before_model_authority_is_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            flowguard_root = root / ".flowguard"
            flowguard_root.mkdir()
            (flowguard_root / "dna_audit").mkdir()
            (flowguard_root / "dna_audit" / "old.json").write_text("{}", encoding="utf-8")
            (root / "AGENTS.md").write_text("# Existing\n", encoding="utf-8")
            suite = _SuiteEvidence(True, "pass", "inventory", "semantic", ())
            with (
                patch("flowguard.project_adoption._load_suite_evidence", return_value=suite),
                patch("flowguard.project_adoption.audit_model_authority") as authority,
            ):
                report = audit_project_adoption(root)
            self.assertFalse(report.ok)
            self.assertIn("project_layout_invalid", {finding.category for finding in report.findings})
            self.assertTrue(any("not run" in step for step in report.skipped_steps))
            authority.assert_not_called()

    def test_old_layout_blocks_upgrade_before_model_or_artifact_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            flowguard_root = root / ".flowguard"
            (flowguard_root / "dna_audit").mkdir(parents=True)
            (flowguard_root / "dna_audit" / "old.json").write_text("{}", encoding="utf-8")
            (root / "AGENTS.md").write_text("# Existing\n", encoding="utf-8")
            suite = _SuiteEvidence(True, "pass", "inventory", "semantic", ())
            with (
                patch("flowguard.project_adoption._load_suite_evidence", return_value=suite),
                patch("flowguard.project_adoption.audit_model_authority") as authority,
                patch("flowguard.project_adoption.review_artifact_upgrades") as artifact_scan,
            ):
                report = upgrade_project(root)

            self.assertFalse(report.ok, report.format_text())
            self.assertIn(
                "project_layout_invalid",
                {finding.category for finding in report.findings},
            )
            authority.assert_not_called()
            artifact_scan.assert_not_called()
            self.assertIsNone(report.artifact_upgrade_report)
            self.assertEqual((), report.written_files)

    def test_layout_cli_is_read_only_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            flowguard_root = root / ".flowguard"
            flowguard_root.mkdir()
            (flowguard_root / "tmp").mkdir()
            before = sorted(
                path.relative_to(root).as_posix()
                for path in root.rglob("*")
            )
            from flowguard.__main__ import main

            with patch("sys.argv", ["flowguard", "project-layout-audit", "--root", str(root), "--json"]):
                with patch("builtins.print") as printer:
                    code = main()
            self.assertEqual(1, code)
            payload = json.loads(printer.call_args.args[0])
            self.assertEqual("blocked", payload["status"])
            after = sorted(
                path.relative_to(root).as_posix()
                for path in root.rglob("*")
            )
            self.assertEqual(before, after)

    def test_layout_cli_runs_as_a_real_process_for_current_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            flowguard_root = root / ".flowguard"
            flowguard_root.mkdir()
            (flowguard_root / "project.toml").write_text(
                '[flowguard]\nschema_version = "1.0"\n',
                encoding="utf-8",
            )
            (flowguard_root / "adoption_log.jsonl").write_text("", encoding="utf-8")
            (flowguard_root / "README.md").write_text(
                current_layout_readme_text(),
                encoding="utf-8",
            )
            for role_name, _role in CANONICAL_ROLE_ROOTS:
                (flowguard_root / role_name).mkdir()
            (flowguard_root / "layout.toml").write_text(
                current_layout_manifest_text(root), encoding="utf-8"
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "flowguard",
                    "project-layout-audit",
                    "--root",
                    str(root),
                    "--json",
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"], payload)
            self.assertEqual("pass", payload["status"])
            self.assertEqual(3, payload["layout_version"])

    def test_layout_cli_keeps_working_artifacts_out_of_currentness(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            flowguard_root = root / ".flowguard"
            flowguard_root.mkdir()
            (flowguard_root / "project.toml").write_text(
                '[flowguard]\nschema_version = "1.0"\n',
                encoding="utf-8",
            )
            (flowguard_root / "adoption_log.jsonl").write_text("", encoding="utf-8")
            (flowguard_root / "README.md").write_text(
                current_layout_readme_text(), encoding="utf-8"
            )
            for role_name, _role in CANONICAL_ROLE_ROOTS:
                (flowguard_root / role_name).mkdir()
            (flowguard_root / "layout.toml").write_text(
                current_layout_manifest_text(root), encoding="utf-8"
            )
            cache = flowguard_root / "models" / "__pycache__"
            cache.mkdir(parents=True)
            cache_file = cache / "worker.pyc"
            cache_file.write_bytes(b"cache-bytes")
            staging = flowguard_root / "models" / "authority" / "staging"
            staging.mkdir(parents=True)
            staging_file = staging / "candidate.json"
            staging_file.write_bytes(b"candidate-bytes")
            workspace = root / "work" / "flowguard" / "task-1" / "trace.json"
            workspace.parent.mkdir(parents=True)
            workspace.write_bytes(b"trace-bytes")
            before = {
                "cache": cache_file.read_bytes(),
                "staging": staging_file.read_bytes(),
                "workspace": workspace.read_bytes(),
            }

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "flowguard",
                    "project-layout-audit",
                    "--root",
                    str(root),
                    "--json",
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"], payload)
            self.assertEqual(
                [item["code"] for item in payload["findings"]],
                ["layout_runtime_artifact"],
            )
            self.assertEqual(before["cache"], cache_file.read_bytes())
            self.assertEqual(before["staging"], staging_file.read_bytes())
            self.assertEqual(before["workspace"], workspace.read_bytes())
            self.assertFalse(list(root.parent.glob(f".{root.name}*")))


if __name__ == "__main__":
    unittest.main()
