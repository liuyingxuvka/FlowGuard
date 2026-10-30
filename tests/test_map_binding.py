"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path




from _fg_helpers import (
    map_codes as codes,
    map_fill as fill,
    flowguard_map_contracts421_save,
    flowguard_map_contracts421_write,
    map_load as load,
    map_save,
    map_write,
    map_run as run,
    target_shelf_project as shelf_project,
)

def test_check_reports_unmapped_overlap_anchor_and_undeclared_dep(project, capsys):
    run(project, "scan", capsys=capsys)
    data = fill(project)
    data["components"][0]["entrypoints"] = ["shop/api.py:missing_fn"]
    data["components"][1]["depends_on"] = []  # orders really imports storage
    data["components"][2]["files"].append("shop/orders.py")  # overlap
    map_save(project, data)
    map_write(project, "shop/payments.py", "def pay():\n    return 1\n")  # new unowned file
    found = codes(project, "check", capsys)
    for expected in ("anchor_broken", "dep_undeclared", "file_multi_owner", "file_unmapped"):
        assert expected in found, found


def test_flow_steps_are_verified(project, capsys):
    run(project, "scan", capsys=capsys)
    data = fill(project)
    data["flows"][0]["steps"].append("storage:delete_everything")
    data["flows"][0]["steps"].append("billing:charge")
    map_save(project, data)
    found = codes(project, "check", capsys)
    assert "flow_step_broken" in found and "flow_step_unknown" in found


def test_check_and_change_report_duplicate_owner(tmp_path, capsys):
    """Two components claiming one state is an error in map check, change, read and system, once each."""
    import flowguard.__main__ as flowguard_cli

    root = shelf_project(tmp_path)
    data = load(root)
    next(c for c in data["components"] if c["id"] == "catalog")["state"].append("current loans")
    map_save(root, data)
    capsys.readouterr()

    def run(*args):
        code = flowguard_cli.main([*args, "--root", str(root)])
        return code, capsys.readouterr().out

    code, out = run("map", "check")
    assert code == 1 and out.count("duplicate_owner") == 1 and "ERROR duplicate_owner" in out, out
    assert "duplicate_owner" in run("change")[1]
    assert "architecture: 1 error(s)" in run("read")[1].splitlines()[0]
    assert run("map", "models", "system")[1].count("duplicate_owner catalog") == 1
    data["accepted_debts"] = [
        {
            "expires": "9999-12-31",
            "code": "duplicate_owner",
            "component": "catalog",
            "contains": "current loans",
            "reason": "the catalog mirrors loans until the split",
        }
    ]
    map_save(root, data)
    code, out = run("map", "check")
    assert code == 0 and "INFO  duplicate_owner" not in out, out
    assert (
        "(1 finding(s) covered by accepted debts not shown: python -m flowguard map lint --debts)"
        in out
    )
    assert "0 error(s), 0 warning(s), 1 info" in out
    assert "the catalog mirrors loans until the split" in run("map", "lint", "--debts")[1]


def test_map_check_binding_codes(tmp_path):
    """A declared dependency with no evidence is dep_unused; one used only through an injected object is not."""
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.check import run_check

    map_write(tmp_path, "core.py", "class Store:\n    def save(self):\n        return 1\n")
    map_write(
        tmp_path,
        "api.py",
        "class Service:\n    def __init__(self, store):\n        self.store = store\n\n"
        "    def run(self):\n        return self.store.save()\n",
    )
    map_write(
        tmp_path,
        "app.py",
        "from api import Service\nfrom core import Store\n\n\ndef main():\n    return Service(Store()).run()\n",
    )

    def component(cid, layer, depends_on):
        return {
            "id": cid,
            "layer": layer,
            "summary": cid,
            "responsibilities": [cid + " duty"],
            "files": [cid + ".py"],
            "entrypoints": [],
            "state": [],
            "side_effects": [],
            "depends_on": depends_on,
            "tests": [],
            "models": [],
            "status": "draft",
            "fingerprint": "",
        }

    data = {
        "schema": "flowguard.map.v1",
        "project": "binding",
        "layers": ["interface", "core"],
        "ignore": [],
        "components": [
            component("app", "interface", ["api", "core"]),
            component("api", "interface", ["core"]),
            component("core", "core", []),
        ],
        "flows": [],
        "accepted_debts": [],
    }

    def unused():
        inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
        return [f.component for f in run_check(tmp_path, data, inv) if f.code == "dep_unused"]

    assert unused() == []  # api reaches core only through the injected store
    map_write(
        tmp_path,
        "app.py",
        "from api import Service\nfrom core import Store\n\n\ndef main():\n    return 1\n",
    )
    assert unused() == ["api"]  # nothing passes a Store any more: the declared edge has no evidence

import json
import subprocess
from pathlib import Path
import pytest
from flowguard.__main__ import main
from flowguard.map.cli import _context
from flowguard.map.check import run_check
from flowguard.map.lint import run_lint

def test_flow_step_can_read_the_previous_steps_file(tmp_path):
    """A command that reads an earlier step's file is a `reads` step: checked as an entrypoint, not by call reach."""
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint
    from flowguard.map.views import render_mermaid, render_show

    flowguard_map_contracts421_write(
        tmp_path,
        "plan/main.py",
        "import json\n\ndef main():\n    with open('plan.json', 'w') as out:\n"
        "        json.dump({'ok': True}, out)\n",
    )
    flowguard_map_contracts421_write(
        tmp_path,
        "check/main.py",
        "import json\n\ndef main():\n    with open('plan.json') as source:\n"
        "        return json.load(source)\n",
    )

    def component(cid, entry=True):
        return {
            "id": cid,
            "summary": f"{cid} command",
            "responsibilities": [f"{cid} step"],
            "files": [f"{cid}/main.py"],
            "entrypoints": [f"{cid}/main.py:main"] if entry else [],
            "tests": [],
            "models": [],
            "depends_on": [],
            "status": "draft",
        }

    def mapped(steps, *, check_entry=True):
        data = {
            "schema": "flowguard.map.v1",
            "components": [component("plan"), component("check", check_entry)],
            "flows": [{"id": "chain", "summary": "plan then check", "steps": steps}],
        }
        flowguard_map_contracts421_save(tmp_path, data)
        data, inv = _context(tmp_path)
        return data, inv, run_check(tmp_path, data, inv), run_lint(tmp_path, data, inv)

    data, inv, checked, linted = mapped(["plan:main", "check:main reads plan.json"])
    assert not [f for f in checked if f.level == "error"], checked
    assert not [
        f for f in linted if f.code in {"flow_step_unreached", "flow_handoff_not_entrypoint"}
    ], linted
    assert "check:main reads plan.json" in render_show(
        tmp_path, data, inv, component=None, detail=False
    )
    assert "plan.json" in render_mermaid(tmp_path, data, inv)
    _, _, _, linted = mapped(["plan:main", "check:main reads plan.json"], check_entry=False)
    assert [f for f in linted if f.code == "flow_handoff_not_entrypoint"], linted
    for steps in (
        ["plan:main reads plan.json", "check:main"],
        ["plan:main", "check:main reads "],
        ["plan:main", "check reads plan.json"],
    ):
        _, _, checked, _ = mapped(steps)
        assert [f for f in checked if f.code == "flow_handoff_invalid" and f.level == "error"], (
            steps,
            checked,
        )
    _, _, _, linted = mapped(["plan:main", "check:main"])
    assert [f for f in linted if f.code == "flow_step_unreached"], linted
