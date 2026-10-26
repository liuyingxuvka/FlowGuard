"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_lint_reports_private_names_used_across_components(tmp_path):
    """A `_private` name owned by another component is a WARN; own files, dunders and tests are not."""
    import json
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from _fg_helpers import map_write as write
    from flowguard.map.lint import run_lint
    from flowguard.map.views import render_show

    write(tmp_path, "a/__init__.py", "")
    write(tmp_path, "a/x.py", "from b.y import _helper, __version__\nimport b.z as zed\n\n"
          "def run():\n    return _helper() + zed._other()\n")
    write(tmp_path, "b/__init__.py", "")
    write(tmp_path, "b/y.py", "__version__ = '1'\n\ndef _helper():\n    return 1\n")
    write(tmp_path, "b/z.py", "from b.y import _helper\n\ndef _other():\n    return _helper()\n")
    write(tmp_path, "tests/test_x.py", "from b.y import _helper\n\ndef test_helper():\n    assert _helper() == 1\n")

    def component(cid, depends_on=()):
        return {"id": cid, "summary": cid, "responsibilities": [f"{cid} work"], "files": [f"{cid}/*.py"],
                "entrypoints": [], "tests": ["tests/test_x.py"] if cid == "a" else [], "models": [],
                "depends_on": list(depends_on), "status": "draft"}
    data = {"schema": "flowguard.map.v1", "components": [component("a", ["b"]), component("b")], "flows": []}
    write(tmp_path, ".flowguard/map.json", json.dumps(data))
    inv = build_inventory(tmp_path, DEFAULT_IGNORE)
    found = [f for f in run_lint(tmp_path, data, inv) if f.code == "private_cross_component_use"]
    assert {(f.level, f.component) for f in found} == {("warn", "a")}, found
    messages = " ".join(f.message for f in found)
    assert "_helper" in messages and "_other" in messages and "a/x.py:1" in messages, messages
    assert "__version__" not in messages and "b/z.py" not in messages and "tests/" not in messages
    debt = {"code": "private_cross_component_use", "component": "a", "contains": "_helper", "reason": "migration"}
    found = [f for f in run_lint(tmp_path, {**data, "accepted_debts": [debt]}, inv)
             if f.code == "private_cross_component_use"]
    assert any(f.level == "info" and "_helper" in f.message for f in found), found
    shown = render_show(tmp_path, data, inv, component="a", detail=False, budget=8000)
    assert "_helper (private)" in next(line for line in shown.splitlines() if "uses b:" in line), shown
