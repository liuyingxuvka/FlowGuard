from __future__ import annotations

import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path

from flowguard.process_supervision import run_supervised, write_terminal_artifact


class ProcessSupervisionTests(unittest.TestCase):
    def test_public_configuration_defaults_remain_exact(self) -> None:
        signature = inspect.signature(run_supervised)

        self.assertIs(inspect.Parameter.empty, signature.parameters["cwd"].default)
        self.assertIs(
            inspect.Parameter.empty,
            signature.parameters["timeout_seconds"].default,
        )
        self.assertEqual(3.0, signature.parameters["grace_seconds"].default)
        self.assertIsNone(signature.parameters["environment"].default)
        self.assertIsNone(signature.parameters["cancel_event"].default)

    def test_success_requires_zero_contained_processes(self) -> None:
        result = run_supervised(
            (sys.executable, "-c", "print('ok')"),
            cwd=Path.cwd(),
            timeout_seconds=5,
        )
        self.assertTrue(result.ok, result.to_dict())
        self.assertTrue(result.cleanup_confirmed)
        self.assertEqual((), result.descendant_process_ids)

    def test_normal_exit_preserves_exact_stream_and_status_parity(self) -> None:
        source = (
            "import sys;"
            "print('stdout-value');"
            "print('stderr-value', file=sys.stderr);"
            "raise SystemExit(7)"
        )
        command = (sys.executable, "-c", source)

        result = run_supervised(
            command,
            cwd=Path.cwd(),
            timeout_seconds=5,
        )

        self.assertEqual(command, result.command)
        self.assertEqual(str(Path.cwd().resolve()), result.cwd)
        self.assertEqual(7, result.exit_code)
        self.assertEqual("stdout-value\n", result.stdout)
        self.assertEqual("stderr-value\n", result.stderr)
        self.assertEqual("process_exit", result.terminal_reason)
        self.assertEqual("none", result.termination_stage)
        self.assertTrue(result.cleanup_confirmed)
        self.assertFalse(result.ok)

    def test_timeout_terminates_spawned_grandchild(self) -> None:
        source = (
            "import subprocess,sys,time;"
            "subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
            "time.sleep(60)"
        )
        result = run_supervised(
            (sys.executable, "-c", source),
            cwd=Path.cwd(),
            timeout_seconds=0.5,
            grace_seconds=0.2,
        )
        self.assertTrue(result.timed_out, result.to_dict())
        self.assertTrue(result.cleanup_confirmed, result.to_dict())
        self.assertEqual((), result.descendant_process_ids)
        self.assertFalse(result.ok)

    def test_root_exit_with_detached_grandchild_is_cleaned_but_not_passed(
        self,
    ) -> None:
        source = (
            "import subprocess,sys;"
            "child=subprocess.Popen("
            "[sys.executable,'-c','import time;time.sleep(60)'],"
            "stdin=subprocess.DEVNULL,"
            "stdout=subprocess.DEVNULL,"
            "stderr=subprocess.DEVNULL);"
            "print(child.pid)"
        )

        result = run_supervised(
            (sys.executable, "-c", source),
            cwd=Path.cwd(),
            timeout_seconds=5,
            grace_seconds=0.2,
        )

        self.assertEqual(0, result.exit_code)
        self.assertEqual("descendants_after_root_exit", result.terminal_reason)
        self.assertIn(result.termination_stage, {"terminate", "force_kill"})
        self.assertTrue(result.cleanup_confirmed, result.to_dict())
        self.assertEqual((), result.descendant_process_ids)
        self.assertFalse(result.ok)

    def test_terminal_artifact_is_complete_json(self) -> None:
        result = run_supervised(
            (sys.executable, "-c", "raise SystemExit(3)"),
            cwd=Path.cwd(),
            timeout_seconds=5,
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = write_terminal_artifact(
                Path(temporary) / "terminal.json",
                result,
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(3, payload["exit_code"])
        self.assertTrue(payload["cleanup_confirmed"])
        self.assertEqual("blocked", payload["status"])


if __name__ == "__main__":
    unittest.main()
