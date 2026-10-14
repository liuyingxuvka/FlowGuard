"""Minimal pytest plugin for exact run-local node-id evidence.

The built-in JUnit reporter does not require a ``nodeid`` attribute.  Full
FlowGuard validation therefore loads this plugin for the child invocation so
the executed collection is recorded from pytest's own ``report.nodeid``
values.  It also records each node's own outcome, so a consumer never has to
join this file with a JUnit file from a possibly different run.
"""

from __future__ import annotations

import hashlib
import json
import pytest
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from flowguard.pytest_junit import pytest_alignment_input_digest as _digest
from flowguard.pytest_junit import worktree_input_paths as _worktree_paths


_NODEIDS: list[str] = []
_STATUSES: dict[str, str] = {}
_RANK = {"passed": 0, "xfailed": 1, "skipped": 2, "xpassed": 3, "failed": 4, "error": 5}


def _record(nodeid: str, status: str) -> None:
    if nodeid not in _NODEIDS:
        _NODEIDS.append(nodeid)
    if _RANK[status] >= _RANK[_STATUSES.get(nodeid, "passed")]:
        _STATUSES[nodeid] = status


def pytest_runtest_logreport(report: Any) -> None:
    # Setup failures do not always produce a call-phase report, while a
    # teardown report can repeat the same node.  The first report for each
    # node is the exact execution order used by the JUnit projection; the
    # worst phase outcome is the node's status.
    nodeid = str(getattr(report, "nodeid", "")).strip()
    if not nodeid:
        return
    if hasattr(report, "wasxfail"):
        status = "xfailed" if report.skipped else ("failed" if report.failed else "xpassed")
    elif report.failed:
        status = "failed" if report.when == "call" else "error"
    elif report.skipped:
        status = "skipped"
    else:
        status = "passed"
    _record(nodeid, status)


def pytest_collectreport(report: Any) -> None:
    # A module-level skip/import error has no runtest report but does get a
    # JUnit testcase; record it so both views stay the same length.
    if not report.passed and str(getattr(report, "nodeid", "")).strip():
        _record(report.nodeid, "skipped" if report.skipped else "error")


_RUN: dict[str, Any] = {}


def _inputs_digest(root: Path) -> tuple[list[str], str]:
    paths = list(_worktree_paths(root))
    return paths, _digest(root, paths)


def pytest_sessionstart(session: Any) -> None:
    if hasattr(session.config, "workerinput") or not os.environ.get("FLOWGUARD_PYTEST_NODEIDS", "").strip():
        return
    _NODEIDS.clear()
    _STATUSES.clear()
    _RUN.clear()
    root = Path(str(session.config.rootpath)).resolve()
    _RUN["run_id"] = uuid.uuid4().hex
    try:
        _RUN["input_paths"], _RUN["input_digest_before"] = _inputs_digest(root)
    except (OSError, ValueError):
        _RUN["input_paths"], _RUN["input_digest_before"] = [], ""
    _RUN["root"] = root
    _RUN["command"] = " ".join(["python -m pytest", *sys.argv[1:]])


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    if hasattr(session.config, "workerinput"):
        return  # pytest-xdist worker: only the controller writes the record
    target_text = str(os.environ.get("FLOWGUARD_PYTEST_NODEIDS", "")).strip()
    if not target_text:
        return
    after = ""
    if _RUN.get("input_paths"):
        try:
            after = _digest(_RUN["root"], _worktree_paths(_RUN["root"]))
        except (OSError, ValueError):
            after = ""
    target = Path(target_text).expanduser().resolve()
    if target.exists() and target.is_symlink():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    junit_digest = None
    junit_path = getattr(session.config.option, "xmlpath", None)
    if junit_path:
        try:
            junit_digest = hashlib.sha256(Path(junit_path).expanduser().read_bytes()).hexdigest()
        except OSError:
            pass
    payload = {
        "schema_version": "flowguard.pytest_nodeids.v2",
        "run_id": _RUN.get("run_id", ""),
        "project_root": str(_RUN.get("root", "")),
        "junit_digest": junit_digest,
        "nodeids": list(_NODEIDS),
        "statuses": dict(_STATUSES),
        "exit_status": int(exitstatus),
        "exit_code": int(exitstatus),
        "command": _RUN.get("command", ""),
        "input_paths": list(_RUN.get("input_paths", [])),
        "input_digest_before": _RUN.get("input_digest_before", ""),
        "input_digest_after": after,
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )
