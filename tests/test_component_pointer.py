"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_filled_map_checks_clean_after_confirm(project, capsys):
    from _fg_helpers import map_fill as fill, map_run as run, map_codes as codes
    run(project, "scan", capsys=capsys)
    fill(project)
    assert run(project, "confirm", "api", "orders", "storage", "web", capsys=capsys)[0] == 0
    assert codes(project, "check", capsys) == []


def test_stale_after_owned_file_changes_and_confirm_clears_it(project, capsys):
    from _fg_helpers import map_write as write, map_fill as fill, map_run as run, map_codes as codes
    run(project, "scan", capsys=capsys)
    fill(project)
    run(project, "confirm", "api", "orders", "storage", "web", capsys=capsys)
    write(project, "shop/storage.py", "DB = {}\n\ndef save(x):\n    DB[x] = 1\n    return x\n")
    assert codes(project, "check", capsys) == ["stale"]
    run(project, "confirm", "storage", capsys=capsys)
    assert codes(project, "check", capsys) == []
