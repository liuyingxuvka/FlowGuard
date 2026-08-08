import json
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from flowguard.__main__ import main
from flowguard.model_authority_store import (
    ModelAuthorityAuditReport,
    ModelAuthorityFinding,
)


class ModelAuthorityCliTests(unittest.TestCase):
    def _intent_bootstrap_args(self, path: Path) -> list[str]:
        return [
            "model-revision-intent-bootstrap",
            "--root",
            str(path.parent),
            "--model-parent-receipt",
            "missing-parent.json",
            "--revision-set-id",
            "revision:bootstrap-cli",
            "--task-id",
            "task:bootstrap-cli",
            "--snapshot-id",
            "snapshot:bootstrap-cli",
            "--intent-bootstrap-input",
            str(path),
            "--json",
        ]

    def test_model_revision_build_failure_is_visible(self):
        output = StringIO()
        with patch(
            "flowguard.model_revision_builder.build_current_model_revision",
            side_effect=OSError("missing-parent.json"),
        ), redirect_stdout(output):
            exit_code = main(
                [
                    "model-revision-build",
                    "--model-parent-receipt",
                    "missing-parent.json",
                    "--revision-set-id",
                    "revision:missing",
                    "--task-id",
                    "task:missing",
                    "--snapshot-id",
                    "observed-missing",
                    "--json",
                ]
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(1, exit_code)
        self.assertEqual("blocked", payload["status"])
        self.assertIn("missing-parent.json", payload["error"])

    def test_model_system_audit_fails_closed_without_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".flowguard").mkdir()
            (root / ".flowguard" / "project.toml").write_text(
                "[flowguard]\n",
                encoding="utf-8",
            )
            output = StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "model-system-audit",
                        "--root",
                        str(root),
                        "--json",
                    ]
                )

            payload = json.loads(output.getvalue())
            self.assertEqual(1, exit_code)
            self.assertEqual("blocked", payload["status"])
            self.assertFalse(payload["ok"])
            self.assertEqual(
                "model_authority_invalid",
                payload["findings"][0]["code"],
            )

    def test_model_system_audit_emits_exact_live_inventory_and_exit_code(self):
        report = ModelAuthorityAuditReport(
            root="fixture",
            status="blocked",
            observed_snapshot_fingerprint="sha256:" + "a" * 64,
            live_snapshot_fingerprint="sha256:" + "b" * 64,
            declared_model_ids=("alpha", "missing"),
            materialized_model_ids=("alpha",),
            required_model_ids=("alpha", "missing"),
            covered_model_ids=("alpha",),
            missing_model_ids=("missing",),
            findings=(
                ModelAuthorityFinding(
                    "blocked",
                    "live_model_manifest_incomplete",
                    "one declared model is missing",
                ),
            ),
        )
        output = StringIO()

        with patch(
            "flowguard.model_authority_store.audit_model_authority",
            return_value=report,
        ), redirect_stdout(output):
            exit_code = main(["model-system-audit", "--json"])

        payload = json.loads(output.getvalue())
        self.assertEqual(1, exit_code)
        self.assertEqual(["alpha", "missing"], payload["declared_model_ids"])
        self.assertEqual(["alpha"], payload["materialized_model_ids"])
        self.assertEqual(["missing"], payload["missing_model_ids"])
        self.assertEqual(
            "sha256:" + "b" * 64,
            payload["live_snapshot_fingerprint"],
        )

    def test_intent_bootstrap_rejects_duplicate_json_keys_before_any_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "bootstrap.json"
            input_path.write_text(
                """{
  "schema": "flowguard.model_revision_intent_bootstrap_input.v1",
  "schema": "flowguard.model_revision_intent_bootstrap_input.v1",
  "receipt_id": "receipt:duplicate",
  "rationale": "This deliberately duplicated fixture must fail before revision construction.",
  "claim_boundary": "This fixture proves only strict duplicate-key rejection and no build behavior.",
  "current_design_contributions": [],
  "legacy_entry_dispositions": []
}""",
                encoding="utf-8",
            )
            before = tuple(
                (path.relative_to(root).as_posix(), path.read_bytes())
                for path in sorted(root.rglob("*"))
                if path.is_file()
            )
            output = StringIO()
            with patch(
                "flowguard.model_revision_builder.build_current_model_revision"
            ) as build, redirect_stdout(output):
                exit_code = main(self._intent_bootstrap_args(input_path))

            payload = json.loads(output.getvalue())
            after = tuple(
                (path.relative_to(root).as_posix(), path.read_bytes())
                for path in sorted(root.rglob("*"))
                if path.is_file()
            )
            self.assertEqual(1, exit_code)
            self.assertEqual("blocked", payload["status"])
            self.assertIn("duplicate JSON key: schema", payload["error"])
            build.assert_not_called()
            self.assertEqual(before, after)

    def test_intent_bootstrap_rejects_unknown_aggregate_field(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "bootstrap.json"
            input_path.write_text(
                json.dumps(
                    {
                        "schema": (
                            "flowguard.model_revision_intent_bootstrap_input.v1"
                        ),
                        "receipt_id": "receipt:unknown-field",
                        "rationale": (
                            "This strict aggregate fixture contains one unknown "
                            "field and must fail before construction."
                        ),
                        "claim_boundary": (
                            "This fixture proves only exact aggregate shape "
                            "validation and no model authority result."
                        ),
                        "current_design_contributions": [],
                        "legacy_entry_dispositions": [],
                        "caller_selected_head": "forbidden",
                    }
                ),
                encoding="utf-8",
            )
            output = StringIO()
            with patch(
                "flowguard.model_revision_builder.build_current_model_revision"
            ) as build, redirect_stdout(output):
                exit_code = main(self._intent_bootstrap_args(input_path))

            payload = json.loads(output.getvalue())
            self.assertEqual(1, exit_code)
            self.assertEqual("blocked", payload["status"])
            self.assertIn("caller_selected_head", payload["error"])
            build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
