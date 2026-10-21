from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import pytest
from pathlib import Path

import flowguard.pytest_shards_cli as shard_runner
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


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group cleanup")
@pytest.mark.parametrize("parent_exits", [False, True])
def test_process_owner_cleans_children_even_after_parent_exit(tmp_path, parent_exits):
    pidfile = tmp_path / "child.pid"
    script = (
        "import subprocess,sys,time; from pathlib import Path; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
        f"Path({str(pidfile)!r}).write_text(str(child.pid)); "
        + ("sys.exit(0)" if parent_exits else "time.sleep(30)")
    )
    result = shard_runner._run_process(
        [sys.executable, "-c", script], cwd=tmp_path, environment=dict(os.environ),
        stdout_path=tmp_path / "stdout", stderr_path=tmp_path / "stderr",
        timeout_seconds=.5,
    )
    pid = int(pidfile.read_text())
    try:
        if Path(f"/proc/{pid}/stat").exists():
            assert Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] == "Z"
        else:
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)
        if parent_exits:
            assert result["exit_code"] == 0 and result["lingering_killed"] is True
        else:
            assert result["exit_code"] != 0
        assert result["timed_out"] is not parent_exits
        assert result["cleanup_confirmed"] is True
    finally:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def test_resume_requires_current_input_bytes_and_execution_identity(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    source = root / "answer.py"
    source.write_text("def answer(): return 1\n")
    (root / "test_answer.py").write_text(
        "from answer import answer\ndef test_answer(): assert answer() == 1\n"
    )
    monkeypatch.setenv("PYTHONPATH", str(Path(shard_runner.__file__).resolve().parents[1]))
    args = shard_runner.build_parser().parse_args([
        "--root", str(root), "--shards", "1", "--parallel-shards", "1",
    ])
    def run(name, previous=""):
        monkeypatch.setenv("FLOWGUARD_PYTEST_SHARDS_DIR", str(tmp_path / name))
        args.resume_output = str(tmp_path / previous) if previous else ""
        return shard_runner.run(args)
    code, first = run("first")
    assert code == 0, first
    code, same = run("same", "first")
    assert code == 0 and same["shard_execution"]["resumed_shards"] == 1, same
    monkeypatch.setenv("FLOWGUARD_REGRESSION_INPUT", "changed")
    code, environment_changed = run("environment", "first")
    assert code == 0 and environment_changed["shard_execution"]["resumed_shards"] == 0
    monkeypatch.delenv("FLOWGUARD_REGRESSION_INPUT")
    source.write_text("def answer(): return 2\n")
    code, changed = run("changed", "first")
    assert code == 1 and changed["status"] == "fail", changed
    assert changed["shard_execution"]["resumed_shards"] == 0
    assert changed["pytest_execution"]["failed"] == 1
    source.write_text("def answer(): return 1\n")
    request = tmp_path / "first" / "shard-01" / "requested.json"
    legacy = json.loads(request.read_text())
    del legacy["execution_identity"]
    request.write_text(json.dumps(legacy))
    code, unknown = run("legacy", "first")
    assert code == 0 and unknown["shard_execution"]["resumed_shards"] == 0, unknown


def test_unknown_capability_preserves_typed_block_and_aggregate(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    (root / "test_cap.py").write_text(
        "import pytest\n@pytest.mark.flowguard_capability('unknown-native-capability')\n"
        "def test_cap(): assert True\n"
    )
    output = tmp_path / "evidence"
    monkeypatch.setenv("PYTHONPATH", str(Path(shard_runner.__file__).resolve().parents[1]))
    monkeypatch.setenv("FLOWGUARD_PYTEST_SHARDS_DIR", str(output))
    args = shard_runner.build_parser().parse_args(["--root", str(root)])
    code, payload = shard_runner.run(args)
    assert code == 70 and payload["status"] == "blocked"
    node = "test_cap.py::test_cap"
    partition = payload["capability_partition"]
    assert partition["blocked_nodeids"] == [node]
    assert "unknown-native-capability" in partition["blocked_reasons"][node]
    assert json.loads((output / "aggregate.json").read_text()) == payload
    assert "UnboundLocalError" not in json.dumps(payload)


@pytest.mark.skipif(os.name == "nt", reason="POSIX session ownership")
@pytest.mark.parametrize("case", ["normal", "outer_timeout", "inner_timeout", "orphan_nested"])
def test_nested_process_helpers_share_one_finite_owner(tmp_path, case):
    from flowguard.map.runner import run_isolated_process
    record = tmp_path / "inner.json"
    delay = 0 if case == "normal" else 30
    inner = ("import json,os,time;from pathlib import Path;"
             f"Path({str(record)!r}).write_text(json.dumps([os.getpid(),os.getpgrp()]));"
             f"print('nested-ok',flush=True);time.sleep({delay})")
    outer = ("import os,sys;from pathlib import Path;"
             "from flowguard.map.runner import run_isolated_process;"
             f"p,t,c=run_isolated_process([sys.executable,'-c',{inner!r}],"
             "cwd=Path.cwd(),env=dict(os.environ),"
             f"timeout={.3 if case == 'inner_timeout' else 20});"
             "raise SystemExit(p.returncode)")
    if case == "orphan_nested":
        worker = "import time;time.sleep(.15);" + outer
        outer = "import subprocess,sys;subprocess.Popen([sys.executable,'-c'," + repr(worker) + "])"
    env = dict(os.environ, PYTHONPATH=str(Path(shard_runner.__file__).resolve().parents[1]))
    # A foreign/stale marker must not make this outside coordinator join or
    # kill its caller's group. The bootstrap installs the actual child owner.
    env["_FLOWGUARD_PROCESS_OWNER"] = "1:1:1"
    result, timed_out, cleaned = run_isolated_process(
        [sys.executable, "-c", outer], cwd=tmp_path, env=env,
        timeout=.8 if case in {"outer_timeout", "orphan_nested"} else 3,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pid, group = json.loads(record.read_text())
    assert group != pid  # inner helper did not create a detached session
    assert cleaned
    assert timed_out == (case in {"outer_timeout", "orphan_nested"})
    assert (result.returncode == 0) == (case == "normal")
    try:
        assert Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] in {"Z", "X"}
    except FileNotFoundError:
        pass


@pytest.mark.skipif(os.name == "nt", reason="POSIX session ownership")
def test_nested_timeout_kills_only_its_own_child(tmp_path):
    from flowguard.map.runner import run_isolated_process
    outer = ("import os,sys;from pathlib import Path;"
             "from flowguard.map.runner import run_isolated_process;"
             "p,t,c=run_isolated_process([sys.executable,'-c','import time;time.sleep(30)'],"
             "cwd=Path.cwd(),env=dict(os.environ),timeout=.3);"
             "print('outer-survived',p.returncode,t,flush=True)")
    env = dict(os.environ, PYTHONPATH=str(Path(shard_runner.__file__).resolve().parents[1]))
    result, timed_out, cleaned = run_isolated_process(
        [sys.executable, "-c", outer], cwd=tmp_path, env=env, timeout=10,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert not timed_out and cleaned
    assert result.returncode == 0 and "outer-survived 124 True" in result.stdout


def test_inaccessible_process_inventory_does_not_claim_cleanup(monkeypatch):
    from flowguard.map import runner
    monkeypatch.setattr(runner.sys, "platform", "linux")
    monkeypatch.setattr(runner.Path, "iterdir", lambda self: (_ for _ in ()).throw(PermissionError()))
    monkeypatch.setattr(runner.os, "killpg", lambda *args: None)
    assert runner._group_active(12345)
