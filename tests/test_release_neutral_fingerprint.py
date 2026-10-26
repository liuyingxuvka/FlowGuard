"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


@pytest.mark.parametrize("filename", ["pkg/__init__.py", "pyproject.toml", "VERSION"])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_version_only_bump_keeps_components_current(tmp_path, filename, newline):
    from flowguard.map.inventory import build_inventory
    from _fg_helpers import map__release_project as _release_project
    from flowguard.map.mapfile import component_state
    from flowguard.map.check import run_check
    data, comp = _release_project(tmp_path)
    path = tmp_path / filename
    path.write_bytes(path.read_text().replace("1.0.0", "1.0.1").replace("\n", newline).encode())
    inv = build_inventory(tmp_path, [])
    assert component_state(tmp_path, comp, inv, data) == "current"
    assert not [f for f in run_check(tmp_path, data, inv, strict=True) if f.level == "error"]


@pytest.mark.parametrize("filename,old,new", [("pkg/__init__.py", "X = 1", "X = 2"),
    ("pyproject.toml", '"app"', '"other"'), ("pyproject.toml", '"stable"', '"changed"')])
def test_non_version_edit_in_version_file_is_stale(tmp_path, filename, old, new):
    from flowguard.map.inventory import build_inventory
    from _fg_helpers import map__release_project as _release_project
    from flowguard.map.mapfile import component_state
    data, comp = _release_project(tmp_path)
    path = tmp_path / filename
    path.write_text(path.read_text().replace(old, new))
    assert component_state(tmp_path, comp, build_inventory(tmp_path, []), data) == "stale"


def test_format1_map_migrates_once(tmp_path):
    from flowguard.map import cli
    from flowguard.map.inventory import build_inventory
    from _fg_helpers import map__release_project as _release_project
    from flowguard.map.check import run_check
    from flowguard.map.mapfile import component_state, load_map
    data, comp = _release_project(tmp_path, legacy=True)
    inv = build_inventory(tmp_path, [])
    assert component_state(tmp_path, comp, inv, data) == "migrate"
    findings = [f for f in run_check(tmp_path, data, inv, strict=True) if f.code == "fingerprint_migrate"]
    assert len(findings) == 1 and findings[0].level == "error"
    assert cli.main(["confirm", "app", "--root", str(tmp_path)]) == 0
    current = load_map(tmp_path)
    assert current["fingerprint_format"] == 2
    assert component_state(tmp_path, current["components"][0], inv, current) == "current"


def test_format2_map_with_format1_value_is_stale(tmp_path):
    from flowguard.map.inventory import build_inventory
    from _fg_helpers import map__release_project as _release_project
    from flowguard.map.mapfile import component_state
    data, comp = _release_project(tmp_path, legacy=True)
    data["fingerprint_format"] = 2
    assert component_state(tmp_path, comp, build_inventory(tmp_path, []), data) == "stale"
