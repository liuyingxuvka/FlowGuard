"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_check_reports_unmapped_overlap_anchor_and_undeclared_dep(project, capsys):
    from _fg_helpers import map_write as write, map_fill as fill, map_save as save, map_run as run, map_codes as codes
    run(project, "scan", capsys=capsys)
    data = fill(project)
    data["components"][0]["entrypoints"] = ["shop/api.py:missing_fn"]
    data["components"][1]["depends_on"] = []                       # orders really imports storage
    data["components"][2]["files"].append("shop/orders.py")        # overlap
    save(project, data)
    write(project, "shop/payments.py", "def pay():\n    return 1\n")  # new unowned file
    found = codes(project, "check", capsys)
    for expected in ("anchor_broken", "dep_undeclared", "file_multi_owner", "file_unmapped"):
        assert expected in found, found


def test_flow_steps_are_verified(project, capsys):
    from _fg_helpers import map_fill as fill, map_save as save, map_run as run, map_codes as codes
    run(project, "scan", capsys=capsys)
    data = fill(project)
    data["flows"][0]["steps"].append("storage:delete_everything")
    data["flows"][0]["steps"].append("billing:charge")
    save(project, data)
    found = codes(project, "check", capsys)
    assert "flow_step_broken" in found and "flow_step_unknown" in found


def test_check_and_change_report_duplicate_owner(tmp_path, capsys):
    """Two components claiming one state is an error in map check, change, read and system, once each."""
    from _fg_helpers import map_load as load, map_save as save, map_run as run
    import flowguard.__main__ as flowguard_cli
    from _fg_helpers import target_shelf_project as shelf_project

    root = shelf_project(tmp_path)
    data = load(root)
    next(c for c in data["components"] if c["id"] == "catalog")["state"].append("current loans")
    save(root, data)
    capsys.readouterr()

    def run(*args):
        code = flowguard_cli.main([*args, "--root", str(root)])
        return code, capsys.readouterr().out

    code, out = run("map", "check")
    assert code == 1 and out.count("duplicate_owner") == 1 and "ERROR duplicate_owner" in out, out
    assert "duplicate_owner" in run("change")[1]
    assert "architecture: 1 error(s)" in run("read")[1].splitlines()[0]
    assert run("map", "models", "system")[1].count("duplicate_owner catalog") == 1
    data["accepted_debts"] = [{"code": "duplicate_owner", "component": "catalog", "contains": "current loans",
                               "reason": "the catalog mirrors loans until the split"}]
    save(root, data)
    code, out = run("map", "check")
    assert code == 0 and "INFO  duplicate_owner" in out, out


def test_map_check_binding_codes(tmp_path):
    """A declared dependency with no evidence is dep_unused; one used only through an injected object is not."""
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from _fg_helpers import map_write as write
    from flowguard.map.check import run_check

    write(tmp_path, "core.py", "class Store:\n    def save(self):\n        return 1\n")
    write(tmp_path, "api.py", "class Service:\n    def __init__(self, store):\n        self.store = store\n\n"
          "    def run(self):\n        return self.store.save()\n")
    write(tmp_path, "app.py", "from api import Service\nfrom core import Store\n\n\ndef main():\n    return Service(Store()).run()\n")

    def component(cid, layer, depends_on):
        return {"id": cid, "layer": layer, "summary": cid, "responsibilities": [cid + " duty"], "files": [cid + ".py"],
                "entrypoints": [], "state": [], "side_effects": [], "depends_on": depends_on, "tests": [], "models": [],
                "status": "draft", "fingerprint": ""}
    data = {"schema": "flowguard.map.v1", "project": "binding", "layers": ["interface", "core"], "ignore": [],
            "components": [component("app", "interface", ["api", "core"]), component("api", "interface", ["core"]),
                           component("core", "core", [])], "flows": [], "accepted_debts": []}

    def unused():
        inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
        return [f.component for f in run_check(tmp_path, data, inv) if f.code == "dep_unused"]
    assert unused() == []                       # api reaches core only through the injected store
    write(tmp_path, "app.py", "from api import Service\nfrom core import Store\n\n\ndef main():\n    return 1\n")
    assert unused() == ["api"]                  # nothing passes a Store any more: the declared edge has no evidence
