"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


from _fg_helpers import (
    proof__anchor_watch_helpers as _anchor_watch_helpers,
)

def test_anchor_called_only_in_explore_fails(tmp_path):
    result = _anchor_watch_helpers()["native_probe"](tmp_path, "explore")
    assert result.status == "fail", result.problems
    assert (
        "IMPLEMENTED_BY anchor native_explore.py:ping never ran and its file was never read during conformance(); "
        "call that code in conformance() or read it as code facts"
    ) in result.problems


def test_anchor_called_in_worker_thread_is_consulted(tmp_path):
    result = _anchor_watch_helpers()["native_probe"](tmp_path, "worker")
    assert result.status == "pass", result.problems


def test_audit_hook_skips_realpath_once_all_files_opened(tmp_path, monkeypatch):
    from flowguard.map import facts

    source = tmp_path / "native.py"
    source.write_text("def value(): return True\n")
    watch = facts.AnchorWatch(tmp_path, ["native.py:value"])
    monkeypatch.setattr(facts, "_ACTIVE", [watch])
    original = facts.os.path.realpath
    called = []

    def observe(path, *args, **kwargs):
        called.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(facts.os.path, "realpath", observe)
    facts._on_audit("open", (str(source), "r", 0))
    assert watch._opened == set(watch._files) and len(called) == 1
    facts._on_audit("open", (str(source), "r", 0))
    facts._on_audit("open", ("unrelated.txt", "r", 0))
    assert len(called) == 1
