"""Tests grouped by their model or native component."""
from __future__ import annotations

import pytest, os, json
from pathlib import Path
from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path

def test_missing_import_root_is_a_warning(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    from flowguard.map.inventory import build_inventory
    from flowguard.map.check import run_check
    data = {"schema": "flowguard.map.v1", "components": [], "import_roots": ["library"]}
    inv = build_inventory(tmp_path, [], write_cache=False, import_roots=("library",))
    findings = [f for f in run_check(tmp_path, data, inv, strict=True) if f.code == "import_root_missing"]
    assert len(findings) == 1 and findings[0].level == "warn"
    (tmp_path / "library").mkdir()
    assert not [f for f in run_check(tmp_path, data, inv) if f.code == "import_root_missing"]
