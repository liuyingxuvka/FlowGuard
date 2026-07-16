from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from flowguard.portable_model import (
    PortableModel,
    PortableState,
    PortableTemporalObligation,
    PortableTransition,
    RefinementBinding,
    write_portable_model,
)


ROOT = Path(__file__).resolve().parents[1]


def model(model_id: str) -> PortableModel:
    return PortableModel(
        model_id=model_id,
        states=(PortableState("new"), PortableState("done")),
        transitions=(PortableTransition("complete", "new", "go", "ok", "done"),),
        initial_state_ids=("new",),
        terminal_state_ids=("done",),
        temporal_obligations=(
            PortableTemporalObligation(
                "eventually-done",
                "eventually",
                trigger_state_ids=("new",),
                target_state_ids=("done",),
            ),
        ),
    )


class PortableModelCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "flowguard", *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_validate_and_check_share_status_and_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_portable_model(model("cli-model"), Path(directory) / "model.json")
            validate = self.run_cli("portable-model-validate", str(path), "--json")
            check = self.run_cli("portable-model-check", str(path), "--json")
            self.assertEqual(0, validate.returncode, validate.stderr)
            self.assertEqual(0, check.returncode, check.stderr)
            validate_payload = json.loads(validate.stdout)
            check_payload = json.loads(check.stdout)
            self.assertEqual("pass", validate_payload["status"])
            self.assertEqual(validate_payload["model_fingerprint"], check_payload["model_fingerprint"])

    def test_human_projection_is_concise(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_portable_model(model("human-model"), Path(directory) / "model.json")
            result = self.run_cli("portable-model-check", str(path))
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("=== flowguard portable check ===", result.stdout)
            self.assertIn("status: pass", result.stdout)

    def test_invalid_artifact_is_nonzero_canonical_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"schema_version":"old"}', encoding="utf-8")
            result = self.run_cli("portable-model-validate", str(path), "--json")
            self.assertNotEqual(0, result.returncode)
            payload = json.loads(result.stdout)
            self.assertEqual("invalid", payload["status"])
            self.assertEqual("portable_artifact_invalid", payload["findings"][0]["finding_id"])

    def test_refinement_cli_uses_explicit_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = model("parent")
            child = model("child")
            parent_path = write_portable_model(parent, root / "parent.json")
            child_path = write_portable_model(child, root / "child.json")
            binding = RefinementBinding(
                parent_model_id="parent",
                child_model_id="child",
                state_mapping=(("new", "new"), ("done", "done")),
                transition_mapping=(("complete", "complete"),),
                parent_model_fingerprint=parent.fingerprint,
                child_model_fingerprint=child.fingerprint,
            )
            binding_path = root / "binding.json"
            binding_path.write_text(
                json.dumps(binding.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result = self.run_cli(
                "portable-model-refinement",
                "--parent",
                str(parent_path),
                "--child",
                str(child_path),
                "--binding",
                str(binding_path),
                "--json",
            )
            self.assertEqual(0, result.returncode, result.stderr + result.stdout)
            self.assertEqual("pass", json.loads(result.stdout)["status"])


if __name__ == "__main__":
    unittest.main()
