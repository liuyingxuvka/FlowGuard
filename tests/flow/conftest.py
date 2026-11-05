"""Fixtures of the flow engine tests; project builders have one explicit owner."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from _flow_project import Project


@pytest.fixture
def project(tmp_path):
    proj = Project(tmp_path / "proj")
    yield proj
    _end_workers(proj.root)


def _end_workers(root: Path) -> None:
    """No worker outlives its test (#7): a test that returned RUNNING last, or failed half
    way, would leave one waiting for a resume for up to --keep seconds."""
    from checkrun import kill
    for info in (root / ".flowguard" / "cache" / "flow" / "jobs").glob("*/*/worker.json"):
        try:
            pid = json.loads(info.read_text())["pid"]
            kill(pid, whole_group=True)
        except (ValueError, KeyError, ProcessLookupError, PermissionError, OSError):
            pass


@pytest.fixture(autouse=True)
def _no_mv(monkeypatch):
    monkeypatch.delenv("MV", raising=False)          # e7_mach_sonnet1_R9 reads it
