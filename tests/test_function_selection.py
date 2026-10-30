"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


from _fg_helpers import (
    map_function_fixture as function_fixture,
    map_git as git,
    map_impact_of as impact_of,
    map_save as save,
    target_shelf_project as shelf_project,
    map_write as write,
)

def test_owned_edit_does_not_select_composing_parent(tmp_path):
    helper = function_fixture()
    for case in ("body", "helper"):
        root = tmp_path / case
        root.mkdir()
        impact = helper["native_case"](root, case)
        assert impact.model_ids == ["child"]
        assert "parent" not in impact.model_ids


def test_module_binding_change_selects_importer_functions(tmp_path):
    from flowguard.map.impact import render_impact

    impact = function_fixture()["native_case"](tmp_path, "binding")
    assert "importer" in impact.model_ids
    assert "api.py:call" in impact.changed_functions
    assert "UNCERTAIN: core.py" not in render_impact(impact)
    assert impact.model_source_causes["importer"] == {"core.py": ["reference"]}


def test_removed_function_is_uncertain(tmp_path):
    from flowguard.map.impact import render_impact

    impact = function_fixture()["native_case"](tmp_path, "removed")
    assert impact.model_ids and impact.uncertain_files["core.py"]
    assert "UNCERTAIN: core.py:" in render_impact(impact)
    assert impact.model_source_causes == {mid: {"core.py": ["conservative"]} for mid in impact.model_ids}


@pytest.mark.parametrize("boundary", ["terminal", "depth"])
def test_source_origin_does_not_cross_an_existing_selection_boundary(tmp_path, boundary):
    from flowguard.map.impact import compute_impact
    from flowguard.map.inventory import build_inventory

    facade = ("import importlib\n_TABLE = {'pkg.source': ('VALUE',)}\n"
              "def __getattr__(name): return importlib.import_module('pkg.source')\n"
              "def direct(): return 1\n" if boundary == "terminal" else
              "from pkg.source import VALUE\ndef direct(): return VALUE\n")
    write(tmp_path, "pkg/__init__.py", facade)
    write(tmp_path, "pkg/source.py", "VALUE = 1\n")
    write(tmp_path, "consumer.py", "from pkg import direct\ndef use(): return direct()\n")
    components = []
    for cid, files, dependencies in (("a_source", ["pkg/source.py"], []),
                                      ("b_facade", ["pkg/__init__.py"], ["a_source"]),
                                      ("c_client", ["consumer.py"], ["b_facade"])):
        components.append(dict(id=cid, summary=cid, responsibilities=[cid], files=files,
                               depends_on=dependencies, tests=[], models=[], status="draft"))
    for mid, parent, anchor in (("facade_contract", "b_facade", "pkg/__init__.py:direct"),
                                ("client_contract", "c_client", "consumer.py:use")):
        write(tmp_path, ".flowguard/models/" + mid + ".py",
              f'MODEL_ID={mid!r}\nPARENT={parent!r}\nIMPLEMENTED_BY={{"Run": {anchor!r}}}\ndef build_explorer(): pass\n')
    data = dict(schema="flowguard.map.v1", components=components)
    save(tmp_path, data)
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "-A")
    git(tmp_path, "-c", "user.name=Guard", "-c", "user.email=guard@example.invalid", "commit", "-qm", "origin boundary")
    write(tmp_path, "pkg/source.py", "VALUE = 2\n")
    data["components"][1]["entrypoints"] = ["pkg/__init__.py:direct"]  # Independent map-only seed.
    save(tmp_path, data)
    impact = compute_impact(tmp_path, data, build_inventory(tmp_path, [], write_cache=False),
                            ["pkg/source.py", ".flowguard/map.json"], base="HEAD", broad=True,
                            depth=1 if boundary == "depth" else None)
    assert {"facade_contract", "client_contract"} <= set(impact.model_ids)
    assert "pkg/source.py" in impact.model_source_causes["facade_contract"]
    assert not impact.model_source_causes.get("client_contract")


def test_no_git_uses_stale_components(tmp_path):
    from flowguard.map.impact import render_impact

    impact = function_fixture()["native_case"](tmp_path, "no_git")
    assert impact.tests == ["tests/test_core.py"]
    assert impact.changed == ["core.py"]
    assert "NO GIT: changed files = the files of 1 component(s)" in render_impact(impact)
    assert "a test file edited alone is not seen: run it by path" in render_impact(impact)


def test_change_selects_models_whose_anchors_the_edit_calls(tmp_path, capsys):
    """Editing a file that calls another component's anchored code selects that model and its tests."""
    import flowguard.__main__ as flowguard_cli

    root = shelf_project(tmp_path)
    capsys.readouterr()
    path = root / "shelf/cli.py"
    original = path.read_text(encoding="utf-8")
    path.write_text(original + "X = 1\n", encoding="utf-8")
    flowguard_cli.main(["change", "--root", str(root)])
    output = capsys.readouterr().out
    assert "relies on: lending via loans:LoanService.borrow" in output, output
    assert "models to run: -" in output, output
    path.write_text(original + "# a comment only\n", encoding="utf-8")
    flowguard_cli.main(["change", "--root", str(root)])
    assert "models to run: -" in capsys.readouterr().out



def test_change_selects_the_model_of_a_flow_whose_step_changed(impact_project):
    """A flow's model protects every step: editing a step's file selects it, a comment does not."""
    root, data = impact_project
    write(root, "shop/jobs.py", "def run():\n    return 'done'\n")
    write(
        root,
        ".flowguard/models/journey.py",
        'MODEL_ID = "journey"\nCOMPONENTS = ["storage"]\n'
        'IMPLEMENTED_BY = {"save": "shop/storage.py:save"}\ndef build_explorer(): pass\ndef conformance(): pass\n',
    )
    data["components"].append(
        {
            "id": "jobs",
            "summary": "jobs",
            "responsibilities": ["run jobs"],
            "files": ["shop/jobs.py"],
            "entrypoints": ["shop/jobs.py:run"],
            "depends_on": [],
            "tests": [],
            "models": [],
            "status": "draft",
            "layer": data["components"][0].get("layer", ""),
        }
    )
    data.setdefault("flows", []).append(
        {
            "id": "chain",
            "summary": "store then run the job",
            "steps": ["storage:save", "jobs:run reads out.json"],
            "model": ".flowguard/models/journey.py",
        }
    )
    save(root, data)
    git(root, "add", "-A")
    git(root, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "flow chain")
    from flowguard.map.impact import render_impact

    path = root / "shop/jobs.py"
    path.write_text("def run():\n    return 'finished'\n", encoding="utf-8")
    impact = impact_of(root, data, ["shop/jobs.py"], base="HEAD")
    assert "journey" in impact.model_ids, impact
    assert "flow chain: step 2 changed; model journey" in render_impact(impact)
    path.write_text("def run():\n    return 'done'\n# a comment\n", encoding="utf-8")
    assert "journey" not in impact_of(root, data, ["shop/jobs.py"], base="HEAD").model_ids



def test_change_lists_unexplained_functions_of_changed_files(tmp_path, capsys):
    """A real edit lists the edited file's unexplained entrypoints; the exit code does not change."""
    import flowguard.__main__ as flowguard_cli

    root = shelf_project(tmp_path)
    capsys.readouterr()
    path = root / "shelf/members.py"
    original = path.read_text(encoding="utf-8")
    path.write_text(
        original + "\nLIMIT_NOTE = 'members may borrow up to the limit'\n", encoding="utf-8"
    )
    code = flowguard_cli.main(["change", "--root", str(root)])
    output = capsys.readouterr().out
    assert "UNEXPLAINED members: shelf/members.py:Members.may_borrow (entrypoint)" in output, output
    path.write_text(original + "# a comment only\n", encoding="utf-8")
    comment_code = flowguard_cli.main(["change", "--root", str(root)])
    assert "UNEXPLAINED" not in capsys.readouterr().out
    assert code == comment_code


def test_flow_model_needs_the_static_path(tmp_path):
    from flowguard.map.inventory import build_inventory
    from flowguard.map.discover import discover_inventory, select_model_functions
    from flowguard.map.tree import build_tree

    (tmp_path / ".flowguard/models").mkdir(parents=True)
    (tmp_path / "app.py").write_text(
        "def entry(): return unrelated() + bridge()\ndef unrelated(): return 1\ndef bridge(): return middle()\ndef middle(): return finish()\ndef finish(): return 1\n"
    )
    (tmp_path / ".flowguard/models/journey.py").write_text(
        'MODEL_ID="journey"\nPARENT="app"\nIMPLEMENTED_BY={"Final":"app.py:finish"}\ndef build_explorer(): pass\ndef conformance(): pass\n'
    )
    data = dict(
        schema="flowguard.map.v1",
        components=[
            dict(
                id="app",
                files=["app.py"],
                tests=[],
                models=[],
                summary="Run the chain",
                responsibilities=["run chain"],
                status="draft",
            )
        ],
        flows=[
            dict(
                id="chain",
                model=".flowguard/models/journey.py",
                steps=["app:entry", "app:middle", "app:finish"],
            )
        ],
    )
    inv = build_inventory(tmp_path, [], write_cache=False)
    tree = build_tree(tmp_path, data, inv)
    raw = discover_inventory(tmp_path, inv, data=data, write_cache=False)

    def selected(symbol):
        return select_model_functions(data, inv, tree, raw, {"app.py#" + symbol})

    assert selected("unrelated")[0] == set()
    assert selected("unrelated")[2] == []
    assert selected("bridge")[0] == {"journey"}
    assert "flow chain: step 1 changed; model journey" in selected("bridge")[2]
    assert selected("middle")[0] == {"journey"}
    data["flows"][0]["steps"][1] = "app:middle reads payload.json"
    assert selected("bridge")[0] == set()
