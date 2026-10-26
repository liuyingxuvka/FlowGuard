"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_anchor_called_only_in_explore_fails(tmp_path):
    from _fg_helpers import proof__anchor_watch_helpers as _anchor_watch_helpers
    result = _anchor_watch_helpers()["native_probe"](tmp_path, "explore")
    assert result.status == "fail", result.problems
    assert ("IMPLEMENTED_BY anchor native_explore.py:ping never ran and its file was never read during conformance(); "
            "call that code in conformance() or read it as code facts") in result.problems


def test_anchor_called_in_worker_thread_is_consulted(tmp_path):
    from _fg_helpers import proof__anchor_watch_helpers as _anchor_watch_helpers
    result = _anchor_watch_helpers()["native_probe"](tmp_path, "worker")
    assert result.status == "pass", result.problems
