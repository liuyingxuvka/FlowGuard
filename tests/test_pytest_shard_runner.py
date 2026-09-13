from __future__ import annotations

import argparse
import json
from pathlib import Path

import scripts.run_flowguard_pytest_shards as shard_runner
from flowguard.symlink_capability import (
    CAPABILITY_PATH_ESCAPE_POSIX,
    CAPABILITY_PATH_ESCAPE_WINDOWS,
    SYMLINK_CAPABILITY_BLOCKER,
)


def _blocked_probe() -> dict[str, object]:
    return {
        "schema_version": "flowguard.symlink_capability_probe.v1",
        "probe_kind": "real-filesystem-symlink",
        "platform": "win32",
        "status": "blocked",
        "ok": False,
        "blocker": SYMLINK_CAPABILITY_BLOCKER,
        "failure_code": "WINDOWS_SYMLINK_PRIVILEGE_REQUIRED",
        "reason": "test capability block",
        "supports_posix_symlink": False,
        "supports_windows_reparse": False,
        "reparse_point": False,
    }


def test_capability_partition_keeps_core_runnable_and_path_blocked():
    core = "tests/test_core.py::test_core"
    path = "tests/test_path.py::test_path"

    result = shard_runner.partition_nodeids_by_capability(
        (core, path),
        {
            core: [],
            path: [CAPABILITY_PATH_ESCAPE_WINDOWS],
        },
        _blocked_probe(),
    )

    assert result["runnable_nodeids"] == [core]
    assert result["blocked_nodeids"] == [path]
    assert result["planned_count"] == 2
    assert result["runnable_count"] == 1
    assert result["not_run_count"] == 1
    assert CAPABILITY_PATH_ESCAPE_WINDOWS in result["blocked_reasons"][path][0]


def test_linux_posix_probe_does_not_satisfy_windows_reparse():
    posix = "tests/test_posix.py::test_posix"
    windows = "tests/test_windows.py::test_windows"
    linux_probe = {
        "platform": "linux",
        "ok": True,
        "reparse_point": False,
        "supports_posix_symlink": True,
        "supports_windows_reparse": False,
        "failure_code": "",
    }

    result = shard_runner.partition_nodeids_by_capability(
        (posix, windows),
        {
            posix: [CAPABILITY_PATH_ESCAPE_POSIX],
            windows: [CAPABILITY_PATH_ESCAPE_WINDOWS],
        },
        linux_probe,
    )

    assert result["runnable_nodeids"] == [posix]
    assert result["blocked_nodeids"] == [windows]


def test_core_scope_excludes_platform_nodes_without_needing_a_probe():
    core = "tests/test_core.py::test_core"
    path = "tests/test_path.py::test_path"

    result = shard_runner._core_scope_partition(
        (core, path),
        {
            core: [],
            path: [CAPABILITY_PATH_ESCAPE_POSIX],
        },
    )

    assert result["claim_scope"] == "scoped-core"
    assert result["runnable_nodeids"] == [core]
    assert result["excluded_nodeids"] == [path]
    assert result["excluded_reasons"][path] == [
        "core_scope_excluded:" + CAPABILITY_PATH_ESCAPE_POSIX
    ]
    assert result["source_planned_count"] == 2
    assert result["planned_count"] == 1


def test_pytest_shard_runner_runs_core_and_records_path_not_run(
    tmp_path,
    monkeypatch,
):
    output_root = tmp_path / "pytest-shards"
    monkeypatch.setenv("FLOWGUARD_PYTEST_SHARDS_DIR", str(output_root))
    monkeypatch.setattr(shard_runner, "_probe_symlink_capability", _blocked_probe)

    core = "tests/test_core.py::test_core"
    path = "tests/test_path.py::test_path"
    calls = []

    def fake_process(
        command,
        *,
        cwd,
        environment,
        stdout_path,
        stderr_path,
        timeout_seconds,
    ):
        del command, cwd, stdout_path, stderr_path, timeout_seconds
        calls.append(environment)
        if "FLOWGUARD_PYTEST_COLLECTION_NODEIDS" in environment:
            Path(environment["FLOWGUARD_PYTEST_COLLECTION_NODEIDS"]).write_text(
                json.dumps(
                    {
                        "schema_version": "flowguard.pytest_collection.v1",
                        "collected_nodeids": [core, path],
                        "selected_nodeids": [core, path],
                        "requested_nodeids": [],
                        "unknown_requested_nodeids": [],
                        "selection_error": "",
                        "node_capabilities": {
                            core: [],
                            path: [CAPABILITY_PATH_ESCAPE_WINDOWS],
                        },
                        "capability_errors": {},
                    }
                ),
                encoding="utf-8",
            )
        else:
            requested = json.loads(
                Path(environment["FLOWGUARD_PYTEST_SHARD_NODEIDS"]).read_text(
                    encoding="utf-8"
                )
            )["nodeids"]
            Path(environment["FLOWGUARD_PYTEST_SHARD_COLLECTION"]).write_text(
                json.dumps(
                    {
                        "schema_version": "flowguard.pytest_collection.v1",
                        "collected_nodeids": requested,
                        "selected_nodeids": requested,
                        "requested_nodeids": requested,
                        "unknown_requested_nodeids": [],
                        "selection_error": "",
                    }
                ),
                encoding="utf-8",
            )
            Path(environment["FLOWGUARD_PYTEST_NODEIDS"]).write_text(
                json.dumps({"nodeids": requested}),
                encoding="utf-8",
            )
            Path(environment["FLOWGUARD_PYTEST_NODEIDS"]).with_name(
                "pytest-junit.xml"
            ).write_text("<testsuite />", encoding="utf-8")
        return {
            "exit_code": 0,
            "timed_out": False,
            "cleanup_confirmed": True,
            "launch_error": "",
        }

    monkeypatch.setattr(shard_runner, "_run_process", fake_process)
    monkeypatch.setattr(
        shard_runner,
        "_pytest_junit_projection",
        lambda path, **kwargs: {
            "node_ids": [core],
            "selected": 1,
            "passed": 1,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "xfailed": 0,
            "xpassed": 0,
            "skip_details": [],
            "optional_metadata_unverified": False,
        },
    )

    args = argparse.Namespace(
        root=str(tmp_path),
        shards=1,
        collect_timeout=1.0,
        shard_timeout=1.0,
        json=True,
    )
    exit_code, payload = shard_runner.run(args)

    assert exit_code == 70
    assert payload["status"] == "blocked"
    assert payload["planned_count"] == 2
    assert payload["executed_count"] == 1
    assert payload["not_run_count"] == 1
    assert payload["capability_partition"]["blocked_nodeids"] == [path]
    assert payload["pytest_execution"]["selected"] == 1
    assert len(calls) == 2


def test_pytest_shard_runner_has_one_absolute_invocation_deadline(tmp_path, monkeypatch):
    """A spent invocation budget blocks before collection and never retries."""

    calls = []

    def unexpected_process(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("the absolute deadline must prevent a producer")

    monkeypatch.setattr(shard_runner, "_run_process", unexpected_process)
    args = argparse.Namespace(
        root=str(tmp_path),
        shards=2,
        collect_timeout=1.0,
        shard_timeout=1.0,
        run_timeout=1e-12,
        parallel_shards=2,
        json=True,
    )

    exit_code, payload = shard_runner.run(args)

    assert exit_code == 70
    assert payload["status"] == "blocked"
    assert payload["deadline"]["remaining_seconds"] == 0.0
    assert calls == []


def test_failed_or_partial_resume_rows_are_never_reused(tmp_path):
    nodeids = ("tests/test_core.py::test_core",)
    for status in ("fail", "partial", "blocked"):
        resumed = shard_runner._resume_one_shard(
            resume_root=tmp_path,
            shard_id="shard-1",
            shard_nodeids=nodeids,
            prior_row={"status": status, "exact_selection": True},
        )
        assert resumed is None
