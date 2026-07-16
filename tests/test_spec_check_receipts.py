import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from flowguard.evidence_receipts import RECEIPT_STATUS_PROGRESS_ONLY, list_evidence_receipts
from flowguard.spec_check_cache import (
    SPEC_CHECK_STATE_BLOCKED,
    SPEC_CHECK_STATE_EXECUTED,
    SPEC_CHECK_STATE_NOT_RUN,
    SPEC_CHECK_STATE_REUSED_CURRENT,
    SPEC_CHECK_STATE_STALE,
    SPEC_TERMINAL_BLOCKED,
    SPEC_TERMINAL_FAIL,
    SPEC_TERMINAL_NOT_RUN_DEPENDENCY,
    SPEC_TERMINAL_TIMEOUT,
    begin_spec_session,
    _pid_alive,
    capture_spec_input_manifest,
    close_spec_session,
    discover_governed_input_paths,
    run_spec_check,
    spec_receipt_to_proof_artifact,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _package_config(change_id: str) -> dict:
    return {
        "provider_id": "openspec",
        "work_package_id": change_id,
        "task_binding_rules": [
            {"task_prefix": "1.", "obligation_ids": ["req.one"], "binding_kind": "direct"}
        ],
        "check_policies": [
            {
                "check_id": "check.one",
                "validation_obligation_ids": ["validation:one"],
                "cross_change_safe": True,
            }
        ],
    }


def _project(change_ids: tuple[str, ...] = ("change-one",)) -> tempfile.TemporaryDirectory:
    temporary = tempfile.TemporaryDirectory()
    root = Path(temporary.name)
    _write(root / "flowguard/source.py", "VALUE = 1\n")
    for change_id in change_ids:
        change = root / "openspec/changes" / change_id
        _write(change / "tasks.md", "# Tasks\n\n- [x] 1.1 Complete the work\n")
        _write(
            change / "verification-contract.yaml",
            """contract_version: '1.0'
obligations:
  - id: req.one
    source: specs/example/spec.md
    claim: One requirement.
    evidence: [check.one]
checks:
  - id: check.one
    command: python
    args: [-c, 'pass']
    covers: [req.one]
    required: true
    expected:
      exit_code: 0
""",
        )
    _write(
        root / ".flowguard/spec_provider_work_packages/bindings.json",
        json.dumps({"packages": [_package_config(value) for value in change_ids]}, indent=2) + "\n",
    )
    return temporary


def _counter_command(extra: str = "") -> tuple[str, ...]:
    code = (
        "from pathlib import Path; "
        "p=Path('counter.txt'); "
        "p.write_text(str(int(p.read_text())+1) if p.exists() else '1')"
    )
    if extra:
        code += f"; Path('tag.txt').write_text({extra!r})"
    return (sys.executable, "-c", code)


def _run(root: Path, **overrides):
    arguments = {
        "provider_id": "openspec",
        "work_package_id": "change-one",
        "check_id": "check.one",
        "semantic_id": "semantic:one",
        "command": _counter_command(),
        "validation_obligation_ids": ("validation:one",),
        "timeout_seconds": 5,
    }
    arguments.update(overrides)
    return run_spec_check(root, **arguments)


class SpecInputManifestTests(unittest.TestCase):
    def test_derived_outputs_and_mtime_do_not_enter_input_fingerprint(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        before = capture_spec_input_manifest(root)
        derived = root / ".flowguard/evidence/spec-work-packages/outputs/run/stdout.log"
        _write(derived, "derived\n")
        for path in discover_governed_input_paths(root):
            path.touch()
        after = capture_spec_input_manifest(root)

        self.assertEqual(before.fingerprint, after.fingerprint)
        self.assertNotIn(
            derived.resolve(),
            {path.resolve() for path in discover_governed_input_paths(root)},
        )

    def test_model_result_files_cannot_make_their_own_check_stale(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        result_path = root / ".flowguard/example_model/result.json"
        _write(result_path, '{"status":"old"}\n')
        begin_spec_session(root, "openspec", "change-one")
        _write(result_path, '{"status":"new"}\n')

        result = _run(root)

        self.assertEqual(result.state, SPEC_CHECK_STATE_EXECUTED)
        self.assertNotIn(
            result_path.resolve(),
            {path.resolve() for path in discover_governed_input_paths(root)},
        )

    def test_openspec_verification_receipts_are_evidence_outputs_not_inputs(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        receipt_path = (
            root
            / "openspec/changes/change-one/verification-receipts"
            / "receipt.json"
        )
        begin_spec_session(root, "openspec", "change-one")
        _write(receipt_path, '{"status":"passed"}\n')

        result = _run(root)

        self.assertEqual(SPEC_CHECK_STATE_EXECUTED, result.state)
        self.assertNotIn(
            receipt_path.resolve(),
            {path.resolve() for path in discover_governed_input_paths(root)},
        )

    def test_v1_migration_evidence_is_not_runtime_input_authority(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        legacy = root / ".agents/skills/example/.skillguard/work-contract.json"
        current = root / ".agents/skills/example/.skillguard/contract-source.json"
        _write(legacy, '{"legacy":1}\n')
        _write(current, '{"schema_version":"skillguard.contract_source.v2"}\n')
        begin_spec_session(root, "openspec", "change-one")
        _write(legacy, '{"legacy":2}\n')
        self.assertEqual(SPEC_CHECK_STATE_EXECUTED, _run(root).state)

        begin_spec_session(root, "openspec", "change-one")
        _write(current, '{"schema_version":"skillguard.contract_source.v2","changed":true}\n')
        self.assertEqual(SPEC_CHECK_STATE_STALE, _run(root).state)

    def test_real_model_or_spec_contract_change_still_invalidates_session(self) -> None:
        for relative_path in (
            ".flowguard/example_model/model.py",
            "openspec/changes/change-one/verification-contract.yaml",
        ):
            with self.subTest(path=relative_path):
                temporary = _project()
                self.addCleanup(temporary.cleanup)
                root = Path(temporary.name)
                path = root / relative_path
                if not path.exists():
                    _write(path, "VALUE = 1\n")
                begin_spec_session(root, "openspec", "change-one")
                _write(path, path.read_text(encoding="utf-8") + "# changed\n")

                result = _run(root)

                self.assertEqual(result.state, SPEC_CHECK_STATE_STALE)
                self.assertIn("session_inputs_changed_before_check", result.blockers)

    def test_begin_and_post_snapshots_close_only_when_unchanged_and_complete(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begun = begin_spec_session(root, "openspec", "change-one")
        executed = _run(root)
        closed = close_spec_session(root, "openspec", "change-one")

        self.assertTrue(begun.ok)
        self.assertTrue(executed.ok)
        self.assertTrue(closed.ok, closed.blockers)
        self.assertEqual(closed.begin_fingerprint, closed.post_fingerprint)
        self.assertTrue((root / begun.begin_record_path).is_file())
        self.assertTrue((root / closed.close_record_path).is_file())

        old_close = (root / closed.close_record_path).read_bytes()
        newer = begin_spec_session(root, "openspec", "change-one")
        self.assertNotEqual(begun.session_id, newer.session_id)
        self.assertEqual(old_close, (root / closed.close_record_path).read_bytes())

    def test_source_change_after_begin_makes_check_stale_without_execution(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        _write(root / "flowguard/source.py", "VALUE = 2\n")
        result = _run(root)

        self.assertEqual(result.state, SPEC_CHECK_STATE_STALE)
        self.assertEqual(result.terminal_status, SPEC_TERMINAL_BLOCKED)
        self.assertFalse((root / "counter.txt").exists())
        self.assertIn("session_inputs_changed_before_check", result.blockers)

    def test_peer_write_after_check_blocks_session_close(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begun = begin_spec_session(root, "openspec", "change-one")
        self.assertFalse(begun.close_record_path)
        self.assertTrue(_run(root).ok)
        _write(root / "flowguard/source.py", "VALUE = 3\n")

        closed = close_spec_session(root, "openspec", "change-one")

        self.assertFalse(closed.ok)
        self.assertEqual("blocked", closed.state)
        self.assertIn("session_inputs_changed", closed.blockers)


class SpecReceiptReuseTests(unittest.TestCase):
    def test_pid_probe_is_safe_for_the_current_process(self) -> None:
        self.assertTrue(_pid_alive(os.getpid()))
        self.assertFalse(_pid_alive(-1))

    def test_same_execution_key_runs_once_then_reuses_current_receipt(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")

        first = _run(root)
        second = _run(root)

        self.assertEqual(first.state, SPEC_CHECK_STATE_EXECUTED)
        self.assertEqual(second.state, SPEC_CHECK_STATE_REUSED_CURRENT)
        self.assertEqual(first.receipt_id, second.receipt_id)
        self.assertEqual((root / "counter.txt").read_text(), "1")

    def test_cross_change_reuse_requires_explicit_authorization(self) -> None:
        for authorized, expected_state in (
            (False, SPEC_CHECK_STATE_EXECUTED),
            (True, SPEC_CHECK_STATE_REUSED_CURRENT),
        ):
            with self.subTest(authorized=authorized):
                temporary = _project(("change-one", "change-two"))
                self.addCleanup(temporary.cleanup)
                root = Path(temporary.name)
                begin_spec_session(root, "openspec", "change-one")
                first = _run(root, cross_change_safe=authorized)
                begin_spec_session(root, "openspec", "change-two")
                second = _run(
                    root,
                    work_package_id="change-two",
                    cross_change_safe=authorized,
                )
                self.assertEqual(first.state, SPEC_CHECK_STATE_EXECUTED)
                self.assertEqual(second.state, expected_state)
                self.assertEqual((root / "counter.txt").read_text(), "1" if authorized else "2")

    def test_caller_cannot_expand_provider_cross_change_authority(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        bindings_path = root / ".flowguard/spec_provider_work_packages/bindings.json"
        payload = json.loads(bindings_path.read_text(encoding="utf-8"))
        payload["packages"][0]["check_policies"][0]["cross_change_safe"] = False
        _write(bindings_path, json.dumps(payload, indent=2) + "\n")
        begin_spec_session(root, "openspec", "change-one")

        result = _run(root, cross_change_safe=True)

        self.assertEqual(result.state, SPEC_CHECK_STATE_BLOCKED)
        self.assertIn("cross_change_safe_not_authorized_by_provider", result.blockers)

    def test_command_input_tool_or_coverage_change_cannot_reuse(self) -> None:
        # Command definition changes.
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        first = _run(root)
        command_changed = _run(root, command=_counter_command("changed"))
        self.assertEqual(first.state, SPEC_CHECK_STATE_EXECUTED)
        self.assertEqual(command_changed.state, SPEC_CHECK_STATE_EXECUTED)

        # Coverage changes.
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        _run(root, coverage=("cell:a",))
        coverage_changed = _run(root, coverage=("cell:b",))
        self.assertEqual(coverage_changed.state, SPEC_CHECK_STATE_EXECUTED)

        # Governed input changes between independently begun sessions.
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        _run(root)
        _write(root / "flowguard/source.py", "VALUE = 2\n")
        begin_spec_session(root, "openspec", "change-one")
        input_changed = _run(root)
        self.assertEqual(input_changed.state, SPEC_CHECK_STATE_EXECUTED)

        # Tool identity changes even when command text does not.
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        with patch("flowguard.spec_check_cache._tool_fingerprint", return_value=({"python": "a"}, "tool:a")):
            _run(root)
        with patch("flowguard.spec_check_cache._tool_fingerprint", return_value=({"python": "b"}, "tool:b")):
            tool_changed = _run(root)
        self.assertEqual(tool_changed.state, SPEC_CHECK_STATE_EXECUTED)

    def test_dependency_failure_is_not_run_and_inner_command_never_starts(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        result = _run(root, depends_on=("check.parent",))

        self.assertEqual(result.state, SPEC_CHECK_STATE_NOT_RUN)
        self.assertEqual(result.terminal_status, SPEC_TERMINAL_NOT_RUN_DEPENDENCY)
        self.assertFalse((root / "counter.txt").exists())

    def test_failure_timeout_and_progress_receipts_are_never_reused(self) -> None:
        # A terminal failure is executed again.
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        failing = (sys.executable, "-c", "from pathlib import Path; p=Path('counter.txt'); p.write_text(str(int(p.read_text())+1) if p.exists() else '1'); raise SystemExit(7)")
        first = _run(root, command=failing)
        second = _run(root, command=failing)
        self.assertEqual(first.terminal_status, SPEC_TERMINAL_FAIL)
        self.assertEqual(second.terminal_status, SPEC_TERMINAL_FAIL)
        self.assertEqual((root / "counter.txt").read_text(), "2")

        # A timeout is executed again rather than reused.
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        timeout_error = subprocess.TimeoutExpired(cmd=(sys.executable, "-c", "pass"), timeout=1)
        with patch("flowguard.spec_check_cache.subprocess.run", side_effect=timeout_error) as mocked:
            first = _run(root)
            second = _run(root)
        self.assertEqual(first.terminal_status, SPEC_TERMINAL_TIMEOUT)
        self.assertEqual(second.terminal_status, SPEC_TERMINAL_TIMEOUT)
        self.assertEqual(mocked.call_count, 2)

        # A stored progress-only receipt cannot be consumed as completion.
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        _run(root)
        receipt_path = next((root / ".flowguard/evidence/spec-work-packages/receipts").glob("*.json"))
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        payload["result_status"] = RECEIPT_STATUS_PROGRESS_ONLY
        receipt_path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        rerun = _run(root)
        self.assertEqual(rerun.state, SPEC_CHECK_STATE_EXECUTED)
        self.assertEqual((root / "counter.txt").read_text(), "2")

    def test_identical_concurrent_execution_is_locked(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        entered = threading.Event()
        release = threading.Event()

        def slow_run(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(timeout=3))
            return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=b"", stderr=b"")

        with patch("flowguard.spec_check_cache.subprocess.run", side_effect=slow_run), patch(
            "flowguard.spec_check_cache._pid_alive", return_value=True
        ):
            with ThreadPoolExecutor(max_workers=1) as executor:
                first_future = executor.submit(_run, root)
                self.assertTrue(entered.wait(timeout=3))
                second = _run(root)
                release.set()
                first = first_future.result(timeout=3)

        self.assertEqual(first.state, SPEC_CHECK_STATE_EXECUTED)
        self.assertEqual(second.state, SPEC_CHECK_STATE_BLOCKED)
        self.assertIn("identical spec check is already executing", second.blockers)

    def test_input_mutation_during_check_blocks_receipt(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        command = (
            sys.executable,
            "-c",
            "from pathlib import Path; Path('flowguard/source.py').write_text('VALUE = 99\\n')",
        )
        result = _run(root, command=command)

        self.assertEqual(result.state, SPEC_CHECK_STATE_BLOCKED)
        self.assertEqual(result.terminal_status, SPEC_TERMINAL_BLOCKED)
        self.assertIn("check_input_changed_during_run", result.blockers)

    def test_abandoned_execution_lock_is_recovered_with_visible_evidence(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        failing = (sys.executable, "-c", "raise SystemExit(3)")
        first = _run(root, command=failing)
        lock = root / ".flowguard/evidence/spec-work-packages/locks" / f"{first.execution_key.removeprefix('sha256:')}.lock"
        _write(lock, json.dumps({"pid": -1, "started_at": "old"}) + "\n")
        old = 1
        os.utime(lock, (old, old))

        recovered = _run(root, command=failing)

        receipts = list_evidence_receipts(
            root,
            output_directory=root / ".flowguard/evidence/spec-work-packages/receipts",
        )
        matching = next(item for item in reversed(receipts) if item.receipt_id == recovered.receipt_id)
        self.assertTrue(dict(matching.metadata).get("recovered_abandoned_lock"))

    def test_proof_projection_binds_exact_execution_session(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        result = _run(root)
        receipts = list_evidence_receipts(
            root,
            output_directory=root / ".flowguard/evidence/spec-work-packages/receipts",
        )
        receipt = next(item for item in receipts if item.receipt_id == result.receipt_id)
        proof = spec_receipt_to_proof_artifact(receipt)
        self.assertEqual(result.session_id, proof.metadata["session_id"])
        self.assertTrue(proof.artifact_fingerprints["session_begin"])
        self.assertEqual(
            proof.artifact_fingerprints["session_begin"],
            proof.artifact_fingerprints["session_post"],
        )


if __name__ == "__main__":
    unittest.main()
