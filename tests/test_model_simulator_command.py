from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from flowguard.__main__ import main


class ModelSimulatorCommandTests(unittest.TestCase):
    @property
    def repository(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def invoke(self, *arguments: str) -> tuple[int, dict[str, object]]:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(["simulator", "--root", str(self.repository), *arguments, "--json"])
        return exit_code, json.loads(stdout.getvalue())

    def test_list_audits_one_canonical_manifest(self) -> None:
        exit_code, payload = self.invoke("--list")

        self.assertEqual(0, exit_code)
        self.assertEqual("pass", payload["status"])
        self.assertEqual(61, len(payload["models"]))
        self.assertTrue(payload["manifest_audit"]["ok"])

    def test_execution_scope_is_required(self) -> None:
        exit_code, payload = self.invoke()

        self.assertEqual(3, exit_code)
        self.assertEqual("invalid_input", payload["status"])
        self.assertIn("--model", payload["message"])

    def test_unmatched_selector_is_not_empty_success(self) -> None:
        exit_code, payload = self.invoke("--model", "does-not-exist")

        self.assertEqual(3, exit_code)
        self.assertEqual("invalid_input", payload["status"])
        self.assertIn("matched no", payload["message"])

    def test_selected_model_runs_through_native_runner_with_bounded_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "run"
            exit_code, payload = self.invoke(
                "--model",
                "architecture_reduction",
                "--tier",
                "focused",
                "--output-dir",
                str(output),
            )

            self.assertEqual(0, exit_code)
            self.assertEqual("pass", payload["status"])
            self.assertEqual("flowguard-simulator", payload["command"])
            self.assertEqual(["architecture_reduction"], payload["selected_model_ids"])
            self.assertNotIn("model.py", " ".join(payload["results"][0]["command"]))
            self.assertEqual("gzip", payload["results"][0]["stdout"]["compression"])
            self.assertTrue((output / "evidence-run.json").is_file())
            self.assertTrue((output.parent / "CURRENT.json").is_file())


if __name__ == "__main__":
    unittest.main()
