from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from flowguard.portable_model import (
    PortableModel,
    PortableModelError,
    PortableState,
    PortableTemporalObligation,
    PortableTransition,
    RefinementBinding,
    load_portable_model,
    validate_portable_model,
    write_portable_model,
)
from flowguard.portable_checker import check_portable_model, check_refinement


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

    def assert_retired_operation(self, result: subprocess.CompletedProcess[str], operation: str) -> None:
        self.assertEqual(2, result.returncode, result.stderr + result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual("blocked", payload["status"])
        self.assertEqual("block", payload["decision"])
        self.assertEqual(0, payload["producer_count"])
        self.assertEqual(f"unknown operation: {operation}", payload["error"])
        self.assertEqual(["read", "change", "release"], payload["allowed_operations"])

    def test_validate_and_check_share_status_and_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_portable_model(model("cli-model"), Path(directory) / "model.json")
            current = load_portable_model(path)
            self.assertEqual((), validate_portable_model(current))
            direct = check_portable_model(current)
            self.assertEqual("pass", direct.status)
            self.assertEqual(current.fingerprint, direct.model_fingerprint)
            validate = self.run_cli("portable-model-validate", str(path), "--json")
            check = self.run_cli("portable-model-check", str(path), "--json")
            self.assert_retired_operation(validate, "portable-model-validate")
            self.assert_retired_operation(check, "portable-model-check")

    def test_human_projection_is_concise(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_portable_model(model("human-model"), Path(directory) / "model.json")
            projection = check_portable_model(load_portable_model(path)).format_text()
            self.assertIn("=== flowguard portable check ===", projection)
            self.assertIn("status: pass", projection)
            result = self.run_cli("portable-model-check", str(path))
            self.assert_retired_operation(result, "portable-model-check")

    def test_invalid_artifact_is_nonzero_canonical_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"schema_version":"old"}', encoding="utf-8")
            with self.assertRaises(PortableModelError):
                load_portable_model(path)
            result = self.run_cli("portable-model-validate", str(path), "--json")
            self.assert_retired_operation(result, "portable-model-validate")

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
            self.assertEqual("pass", check_refinement(parent, child, binding).status)
            self.assert_retired_operation(result, "portable-model-refinement")


if __name__ == "__main__":
    unittest.main()
