from __future__ import annotations

import inspect
import json
import sys
import tempfile
import time
import unittest
from unittest import mock
from pathlib import Path

import flowguard.validation_ownership as ownership
from flowguard.process_supervision import (
    SupervisedCommandResult,
    _confirmed_windows_process_ids,
    _descendant_process_ids,
    run_supervised,
    run_supervised_bytes,
    write_terminal_artifact,
)


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
        self.assertFalse(result.root_process_running)
        self.assertTrue(result.containment_query_succeeded)

    def test_requested_interpreter_identity_is_preserved(self) -> None:
        source = (
            "import json,sys;"
            "print(json.dumps({'executable':sys.executable,'prefix':sys.prefix}))"
        )
        result = run_supervised(
            (sys.executable, "-c", source),
            cwd=Path.cwd(),
            timeout_seconds=5,
        )

        self.assertTrue(result.ok, result.to_dict())
        payload = json.loads(result.stdout)
        self.assertEqual(
            Path(sys.executable).resolve(),
            Path(payload["executable"]).resolve(),
        )
        self.assertEqual(sys.prefix, payload["prefix"])

    def test_unknown_process_tree_query_blocks_cleanup(self) -> None:
        with mock.patch(
            "flowguard.process_supervision._windows_process_tree_observation",
            return_value=None,
        ):
            result = run_supervised(
                (sys.executable, "-c", "pass"),
                cwd=Path.cwd(),
                timeout_seconds=5,
                grace_seconds=0.01,
            )

        self.assertFalse(result.ok)
        self.assertFalse(result.cleanup_confirmed)
        self.assertFalse(result.containment_query_succeeded)
        self.assertEqual("cleanup_unconfirmed", result.terminal_reason)

    def test_transient_process_tree_query_failure_does_not_poison_final_cleanup(
        self,
    ) -> None:
        # The launch observation may race a short-lived Windows launcher.  A
        # later confirmed empty containment/tree observation is authoritative
        # for cleanup; only an unknown final observation remains blocking.
        with mock.patch(
            "flowguard.process_supervision._windows_process_tree_observation",
            side_effect=[None, {}, {}, {}],
        ):
            result = run_supervised(
                (sys.executable, "-c", "pass"),
                cwd=Path.cwd(),
                timeout_seconds=5,
                grace_seconds=0.01,
            )

        self.assertTrue(result.ok, result.to_dict())
        self.assertTrue(result.cleanup_confirmed)
        self.assertTrue(result.containment_query_succeeded)

    def test_pid_reuse_is_not_confirmed_as_the_original_descendant(self) -> None:
        snapshot = {
            41: (7, "python.exe", 200),
            42: (7, "python.exe", 300),
        }
        self.assertEqual(
            (42,),
            _confirmed_windows_process_ids(snapshot, {41: 100, 42: 300}),
        )
        self.assertEqual(
            (),
            _confirmed_windows_process_ids(snapshot, {42: 300}, (42,)),
        )

    def test_transient_exited_root_pid_is_not_a_descendant(self) -> None:
        self.assertEqual((), _descendant_process_ids((321,), 321))
        self.assertEqual((654,), _descendant_process_ids((321, 654), 321))
        self.assertIsNone(_descendant_process_ids(None, 321))

    def test_green_looking_value_with_descendants_is_not_success(self) -> None:
        result = SupervisedCommandResult(
            command=(sys.executable, "-c", "pass"),
            cwd=str(Path.cwd().resolve()),
            episode_token="episode:caller",
            started_at_epoch=1.0,
            finished_at_epoch=2.0,
            exit_code=0,
            stdout="",
            stderr="",
            terminal_reason="process_exit",
            timed_out=False,
            cancelled=False,
            interrupted=False,
            termination_stage="none",
            cleanup_confirmed=True,
            descendant_process_ids=(999,),
        )

        self.assertFalse(result.ok)

    def test_unknown_containment_query_blocks_deterministically(self) -> None:
        with mock.patch(
            "flowguard.process_supervision._contained_process_ids",
            return_value=None,
        ):
            result = run_supervised(
                (sys.executable, "-c", "pass"),
                cwd=Path.cwd(),
                timeout_seconds=5,
                grace_seconds=0.01,
            )

        self.assertFalse(result.ok)
        self.assertFalse(result.cleanup_confirmed)
        self.assertFalse(result.containment_query_succeeded)
        self.assertEqual("cleanup_unconfirmed", result.terminal_reason)

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

    def test_supervised_bytes_preserves_nul_and_non_utf8_output(self) -> None:
        source = (
            "import sys;"
            "data=sys.stdin.buffer.read();"
            "sys.stdout.buffer.write(data+b'\\x00\\xff');"
            "sys.stderr.buffer.write(b'\\x00\\xfe')"
        )
        result = run_supervised_bytes(
            (sys.executable, "-c", source),
            cwd=Path.cwd(),
            input_bytes=b"input\x00\xff",
            timeout_seconds=5,
        )

        self.assertTrue(result.ok, result.to_dict())
        self.assertIsInstance(result.stdout, bytes)
        self.assertIsInstance(result.stderr, bytes)
        self.assertEqual(b"input\x00\xff\x00\xff", result.stdout)
        self.assertEqual(b"\x00\xfe", result.stderr)

    def test_git_query_timeout_cleans_descendants(self) -> None:
        source = (
            "import subprocess,sys,time;"
            "subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
            "time.sleep(60)"
        )
        started = time.monotonic()
        result = run_supervised_bytes(
            (sys.executable, "-c", source),
            cwd=Path.cwd(),
            timeout_seconds=0.2,
            grace_seconds=0.2,
        )
        elapsed = time.monotonic() - started

        self.assertTrue(result.timed_out, result.to_dict())
        self.assertTrue(result.cleanup_confirmed, result.to_dict())
        self.assertEqual((), result.descendant_process_ids)
        self.assertLess(elapsed, 0.2 + 0.2 + 5.0)

    def test_git_observation_has_one_total_deadline(self) -> None:
        calls: list[float] = []
        clock = [0.0]

        class Completed:
            timed_out = False
            cleanup_confirmed = True
            exit_code = 0
            terminal_reason = "process_exit"
            stdout = b""
            stderr = b""

        def fake_query(*args, **kwargs):
            calls.append(float(kwargs["timeout_seconds"]))
            clock[0] += 0.6
            return Completed()

        with (
            mock.patch.object(ownership.time, "monotonic", side_effect=lambda: clock[0]),
            mock.patch.object(ownership, "run_supervised_bytes", side_effect=fake_query),
            ownership.git_observation_budget(timeout_seconds=1.0),
        ):
            ownership._git_bytes(Path.cwd(), "first")
            ownership._git_bytes(Path.cwd(), "second")
            with self.assertRaises(ownership.GitQueryTimeout) as raised:
                ownership._git_bytes(Path.cwd(), "third")

        self.assertEqual(2, len(calls))
        self.assertEqual("source_observation_timeout", raised.exception.code)
        self.assertEqual("third", raised.exception.query_category)

    def test_git_query_timeout_does_not_fallback_to_filesystem_walk(self) -> None:
        class TimedOut:
            timed_out = True
            cleanup_confirmed = True
            exit_code = None
            terminal_reason = "timeout"
            stdout = b""
            stderr = b""
            cancelled = False
            interrupted = False

        with (
            mock.patch.object(ownership, "run_supervised_bytes", return_value=TimedOut()),
            mock.patch.object(
                Path,
                "glob",
                side_effect=AssertionError("unbounded filesystem fallback"),
            ),
        ):
            with self.assertRaises(ownership.GitQueryTimeout) as raised:
                ownership.resolve_input_manifest(Path.cwd(), ("flowguard/**/*.py",))

        self.assertEqual("git_query_timeout", raised.exception.code)

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
