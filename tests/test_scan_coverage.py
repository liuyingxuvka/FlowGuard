"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_first_map_covers_finite_sources_once_within_budget(tmp_path):
    """Native new_map handles nested, ignored, test and malformed source files together."""
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from _fg_helpers import map_write as write
    from collections import Counter
    from flowguard.map.mapfile import component_files
    from flowguard.map.scan import new_map

    files = {
        "api.py": "def run(): return True\n",
        "service/core.py": "def save(): return True\n",
        "pkg/__init__.py": "",
        "pkg/nested/__init__.py": "",
        "pkg/nested/tool.py": "def tool(): return True\n",
        "broken/bad.py": "def broken(:\n",
        "skip/hidden.py": "raise RuntimeError('ignored')\n",
        "tests/test_api.py": "def test_run(): pass\n",
    }
    for relative, source in files.items():
        write(tmp_path, relative, source)
    expected = {"api.py", "service/core.py", "pkg/__init__.py", "pkg/nested/__init__.py",
                "pkg/nested/tool.py", "broken/bad.py"}
    inv = build_inventory(tmp_path, [*DEFAULT_IGNORE, "skip/**"], with_bodies=False, write_cache=False)
    assert set(inv.source) - set(inv.tests) == expected
    assert inv.tests == ["tests/test_api.py"]
    assert inv.py["broken/bad.py"].parse_error
    for limit in (1, 2):
        actual = new_map(tmp_path, inv, max_components=limit)
        components = actual["components"]
        assert 1 <= len(components) <= limit
        owned = [path for component in components for path in component_files(component, inv)]
        assert Counter(owned) == Counter(expected)
        assert "skip/hidden.py" not in owned and "tests/test_api.py" not in owned
        assert all(component["status"] == "draft" for component in components)
