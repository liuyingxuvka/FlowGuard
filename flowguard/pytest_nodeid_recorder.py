"""Minimal pytest plugin for exact run-local node-id evidence.

The built-in JUnit reporter does not require a ``nodeid`` attribute.  Full
FlowGuard validation therefore loads this plugin for the child invocation so
the executed collection is recorded from pytest's own ``report.nodeid``
values.  The suite parser consumes the resulting ordered list; it never
reconstructs an identity from a display classname/name pair in governed mode.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


_NODEIDS: list[str] = []


def pytest_runtest_logreport(report: Any) -> None:
    # Setup failures do not always produce a call-phase report, while a
    # teardown report can repeat the same node.  The first report for each
    # node is the exact execution order used by the JUnit projection.
    nodeid = str(getattr(report, "nodeid", "")).strip()
    if nodeid and nodeid not in _NODEIDS:
        _NODEIDS.append(nodeid)


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    target_text = str(os.environ.get("FLOWGUARD_PYTEST_NODEIDS", "")).strip()
    if not target_text:
        return
    target = Path(target_text).expanduser().resolve()
    if target.exists() and target.is_symlink():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "flowguard.pytest_nodeids.v1",
        "nodeids": list(_NODEIDS),
        "exit_status": int(exitstatus),
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )
