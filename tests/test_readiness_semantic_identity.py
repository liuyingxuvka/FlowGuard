"""Readiness gate identity ignores timing diagnostics, not meaning."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from flowguard import _completion_readiness_impl as readiness


def _result(stdout: str, *, elapsed: float = 1.0):
    return SimpleNamespace(
        exit_code=0,
        cleanup_confirmed=True,
        timed_out=False,
        cancelled=False,
        interrupted=False,
        terminal_reason="process_exit",
        stdout=stdout,
        stderr="diagnostic\n",
        started_at_epoch=100.0,
        finished_at_epoch=100.0 + elapsed,
    )


def _gate_payload(*, duration: int = 12, status: str = "pass", input_sha: str = "sha256:a") -> str:
    return (
        '{"status":%r,"ok":true,"subject":{"input_sha":%r},'
        '"items":[{"id":"R1","valid":true,"durationMs":%d}]}'
        % (status, input_sha, duration)
    ).replace("'", '"')


def test_duration_and_raw_format_are_diagnostics_not_gate_identity(tmp_path: Path):
    first = _result(_gate_payload(duration=12), elapsed=1.0)
    second = _result(
        '{\n  "items": [{"durationMs": 999, "valid": true, "id": "R1"}], '
        '"subject": {"input_sha": "sha256:a"}, "ok": true, "status": "pass"\n}',
        elapsed=9.0,
    )
    with patch.object(readiness, "run_supervised", side_effect=(first, second)):
        left = readiness._run_gate(tmp_path, "openspec", ("tool",), timeout=5)
        right = readiness._run_gate(tmp_path, "openspec", ("tool",), timeout=5)
    assert left["gate_fingerprint"] == right["gate_fingerprint"]
    assert left["diagnostics"]["stdout_sha256"] != right["diagnostics"]["stdout_sha256"]
    assert left["diagnostics"]["elapsed_seconds"] != right["diagnostics"]["elapsed_seconds"]


def test_semantic_status_and_input_identity_change_gate_fingerprint(tmp_path: Path):
    first = _result(_gate_payload(input_sha="sha256:a"))
    changed = _result(_gate_payload(input_sha="sha256:b"))
    with patch.object(readiness, "run_supervised", side_effect=(first, changed)):
        left = readiness._run_gate(tmp_path, "project-audit", ("tool",), timeout=5)
        right = readiness._run_gate(tmp_path, "project-audit", ("tool",), timeout=5)
    assert left["gate_fingerprint"] != right["gate_fingerprint"]


def test_invalid_or_failed_gate_output_is_rejected(tmp_path: Path):
    with patch.object(readiness, "run_supervised", return_value=_result("not-json")):
        with pytest.raises(readiness.CompletionReadinessError):
            readiness._run_gate(tmp_path, "openspec", ("tool",), timeout=5)
    with patch.object(
        readiness,
        "run_supervised",
        return_value=_result('{"status":"blocked","ok":false}'),
    ):
        with pytest.raises(readiness.CompletionReadinessError):
            readiness._run_gate(tmp_path, "openspec", ("tool",), timeout=5)
