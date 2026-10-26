"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_read_component_never_hides_the_requested_component(tmp_path):
    """A component larger than the budget is shortened inside its block, never hidden."""
    from flowguard.map.views import render_show
    from _fg_helpers import view__component as _component
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory

    def write(relative, source):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")

    names = [f"test_case_{index:03d}" for index in range(300)]
    write("big.py", "def run(): return True\n")
    write("tests/test_big.py", "".join(f"def {name}(): pass\n" for name in names))
    bound = ", ".join(f'"tests/test_big.py:{name}"' for name in names)
    write(".flowguard/models/big_model.py", f'''"""Protect the big component."""
MODEL_ID = "big_model"
COMPONENTS = ["big"]
IMPLEMENTED_BY = {{"Run": "big.py:run"}}
TESTED_BY = {{"works": [{bound}]}}
RULES = [Invariant("works", "works", None)]
def build_explorer(): raise RuntimeError("read must not explore")
def broken_variants(): return {{"one": None}}
''')
    data = dict(project="big", layers=[], flows=[], components=[
        dict(_component("big", summary="Serve the big component " * 20, responsibilities=["serve"]),
             files=["big.py"], tests=["tests/test_big.py"])])
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, with_bodies=False, write_cache=False)
    labels = ("purpose:", "rules:", "known-bad:", "code:", "tests:")
    for budget in (8000, 600):
        output = render_show(tmp_path, data, inv, component="big", detail=False, budget=budget)
        assert len(output) <= budget
        assert "## big" in output and "not shown: big" not in output
        assert all(any(line.lstrip().startswith(label) for line in output.splitlines()) for label in labels)
    assert "+297 more" in render_show(tmp_path, data, inv, component="big", detail=False, budget=8000)
    full = render_show(tmp_path, data, inv, component="big", detail=False, budget=200000)
    assert all(f"tests/test_big.py:{name}" in full for name in names[:3])
    assert "+297 more" in full and names[3] not in full.split("model big_model", 1)[1]


def test_static_rules_follow_helpers_and_wrappers(tmp_path):
    from flowguard.map.views import render_show
    from _fg_helpers import view__static_project as _static_project, view__assert_static_equals_runtime as _assert_static_equals_runtime, view__HELPER_SPLIT_MODELS as _HELPER_SPLIT_MODELS
    data, inv = _static_project(tmp_path, _HELPER_SPLIT_MODELS)
    overview = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    assert "model probe_child: Probe. (2 rules, 1 known-bad, 1 tests)" in overview
    assert "model probe_parent: Probe. (2 rules, 1 known-bad, 0 tests +1 in children)" in overview
    assert "model probe_wrapper: Probe. (2 rules, 2 known-bad, 0 tests)" in overview
    _assert_static_equals_runtime(tmp_path, data, inv)


def test_static_known_bad_follow_loops_and_tuple_targets(tmp_path):
    from flowguard.map.views import render_show
    from _fg_helpers import view__PROBE_HEAD as _PROBE_HEAD, view__static_project as _static_project, view__assert_static_equals_runtime as _assert_static_equals_runtime
    explorer = 'def _explorer(kind=""):\n    return Explorer(Workflow(()), (0,), (), invariants=RULES)\n'
    data, inv = _static_project(tmp_path, {
        ".flowguard/models/probe_tuple.py": _PROBE_HEAD + (
            'MODEL_ID = "probe_tuple"\nIMPLEMENTED_BY = {"Run": "app.py:run"}\n'
            'RULES = (Invariant("t_rule", "t holds", lambda state, trace: True),)\n' + explorer +
            'def build_explorer(): return _explorer()\n'
            'def broken_variants():\n'
            '    return {name: _explorer(kind) for name, kind in (("a_bad", "a"), ("b_bad", "b"))}\n'),
        ".flowguard/models/probe_loop.py": _PROBE_HEAD + (
            'MODEL_ID = "probe_loop"\nIMPLEMENTED_BY = {"Run": "app.py:run"}\n'
            'RULES = (Invariant("l_rule", "l holds", lambda state, trace: True),)\n'
            'FEATURES = {"one": ("x", "m_one", 1), "two": ("y", "m_two", 2)}\nEXPECTED = {"alpha": 1, "beta": 2}\n'
            + explorer + 'def build_explorer(): return _explorer()\n'
            'def broken_variants():\n    result = {}\n'
            '    for _, mutation, _ in FEATURES.values():\n        result[mutation] = _explorer(mutation)\n'
            '    for case in EXPECTED:\n        result[f"ignore_{case}"] = _explorer(case)\n    return result\n'),
        ".flowguard/models/probe_items.py": _PROBE_HEAD + (
            'MODEL_ID = "probe_items"\nIMPLEMENTED_BY = {"Run": "app.py:run"}\n'
            'RULES = (Invariant("i_rule", "i holds", lambda state, trace: True),)\n' + explorer +
            'def build_explorer(): return _explorer()\n'
            'def broken_variants():\n    bad = {"p_bad": 1, "q_bad": 2}\n'
            '    return {**{name: _explorer() for name, _ in bad.items()}, "r_bad": _explorer()}\n'),
    })
    overview = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    assert "model probe_loop: Probe. (1 rules, 4 known-bad, 0 tests)" in overview
    assert "model probe_tuple: Probe. (1 rules, 2 known-bad, 0 tests)" in overview
    assert "model probe_items: Probe. (1 rules, 3 known-bad, 0 tests)" in overview
    _assert_static_equals_runtime(tmp_path, data, inv)


def test_kit_model_facets_are_static_and_complete(tmp_path):
    """Feature-kit rules, known-bad and the defect/benign case table are read without importing."""
    from flowguard.map.views import render_show
    from _fg_helpers import view__assert_kit_matches_runtime as _assert_kit_matches_runtime, view__static_project as _static_project
    import sys
    data, inv = _static_project(tmp_path, {".flowguard/models/probe_kit.py": '''"""Probe."""
from pathlib import Path
Path(__file__).parents[2].joinpath("model_import.marker").write_text("imported")
from flowguard.kit import Feature, feature_explorer, feature_variants
MODEL_ID = "probe_kit"
IMPLEMENTED_BY = {"Run": "app.py:run"}
FEATURES = (Feature("d_one", True, ("c1",), lambda plan: plan), Feature("d_two", True, ("c2",), lambda plan: plan),
            Feature("b_one", False, (), lambda plan: plan))
def build_explorer(): return feature_explorer(FEATURES, codes="first")
def broken_variants(): return feature_variants(FEATURES, codes="first")
'''})
    overview = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    detail = render_show(tmp_path, data, inv, component="app", detail=False, budget=8000)
    assert not (tmp_path / "model_import.marker").exists()
    assert not any(isinstance((file := vars(module).get("__file__")), str) and "probe_kit" in file
                   for module in tuple(sys.modules.values()) if module is not None)
    assert "model probe_kit: Probe. (4 rules, 3 known-bad, 0 tests)" in overview
    assert "cases: 2 defects (d_one, d_two), 1 benign (b_one)" in detail
    assert "cases:" not in overview
    (tmp_path / "model_import.marker").unlink(missing_ok=True)
    _assert_kit_matches_runtime(tmp_path, detail)


def test_read_component_lists_the_rules_it_relies_on(tmp_path):
    """cli calls loans' LoanService.borrow, the anchor of model lending: cli relies on lending's rules."""
    from flowguard.map.views import render_show
    from _fg_helpers import target_shelf_project as shelf_project
    from flowguard.map.cli import _context

    root = shelf_project(tmp_path)
    data, inv = _context(root)
    cli = render_show(root, data, inv, component="cli", detail=False, budget=8000)
    assert "relies on: model lending (limit_respected, never_over_lent) via loans: LoanService.borrow" in cli, cli
    loans = render_show(root, data, inv, component="loans", detail=False, budget=8000)
    assert "relies on: model lending" not in loans


def test_read_component_lists_its_flows_and_their_rules(tmp_path):
    """Every component on a flow shows the flow, its step number, the flow's model and its rules."""
    import json
    from flowguard.map.views import render_show
    from _fg_helpers import target_shelf_project as shelf_project
    from flowguard.map.cli import _context

    root = shelf_project(tmp_path)
    data = json.loads((root / ".flowguard/map.json").read_text(encoding="utf-8"))
    data["flows"][0]["model"] = ".flowguard/models/lending.py"
    (root / ".flowguard/map.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    data, inv = _context(root)
    members = render_show(root, data, inv, component="members", detail=False, budget=8000)
    assert "flows: borrow (step 3 of 4; model lending: limit_respected, never_over_lent)" in members, members


def test_read_component_prints_one_port_line_per_model(tmp_path):
    from pathlib import Path
    from flowguard.map.views import render_show
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    import runpy
    directory = Path(__file__).parents[1] / ".flowguard/models"
    path = directory / "_target_fixture.py"
    if not path.exists(): path = directory.parent / "target/models/_target_fixture.py"
    helper = runpy.run_path(str(path))
    data = helper["make_port_project"](tmp_path)
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    text = render_show(tmp_path, data, inv, component="cli", detail=False, budget=8000)
    ports = [line for line in text.splitlines() if line.strip().startswith("port:")]
    models = [line for line in text.splitlines() if line.strip().startswith("model ")]
    assert len(ports) == len(models) == 2 and all(len(line) <= 200 for line in ports), text
    assert any("out answer=lent|refused -> desk.answer" in line for line in ports), text
    path = tmp_path / ".flowguard/models/lending.py"
    path.write_text(path.read_text().replace('OUTPUTS = {"answer":("lent","refused")}', ''))
    text = render_show(tmp_path, data, inv, component="cli", detail=False, budget=8000)
    assert "out ?" in text
