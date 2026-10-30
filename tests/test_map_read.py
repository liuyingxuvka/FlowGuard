"""Tests grouped by their model or native component."""
from __future__ import annotations

import pytest, os, json
from pathlib import Path

from _fg_helpers import (
    view__HELPER_SPLIT_MODELS as _HELPER_SPLIT_MODELS,
    view__component as _component,
    view__coverage_project as _coverage_project,
    view__inventory as _inventory,
    view__static_project as _static_project,
)

def test_show_keeps_flows_and_every_component(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.views import render_show

    data = dict(
        project="demo",
        components=[_component("alpha", summary="a" * 200), _component("beta", summary="b" * 200)],
        flows=[dict(id="checkout", summary="request to result", steps=["alpha:run"])],
    )
    inv = _inventory(tmp_path)
    full = render_show(tmp_path, data, inv, component=None, detail=False)
    assert "> flow checkout" in full and "truncated" not in full
    assert all("## " + component["id"] + " [" in full for component in data["components"])
    assert "shortened" not in full


def test_find_responsibility_breaks_equal_summary_score(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.views import find_owners

    data = dict(
        components=[
            _component("alpha", summary="impact selection"),
            _component("records", responsibilities=["impact selection"]),
        ]
    )
    scores = find_owners(data, _inventory(tmp_path), ["impact", "selection"])
    assert scores[0][1] == "records"
    assert scores[0][0] == scores[1][0]


def test_read_component_prints_five_facets_for_component_and_models(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.views import render_show
    import sys
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.views import render_mermaid

    def write(path, text):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    write(
        "facet_app.py",
        'raise RuntimeError("user code must not import")\ndef run(): return True\ndef side(): pass\n',
    )
    write("store.py", "def save(): pass\n")
    write(
        "tests/test_app.py",
        """test_not_a_function = True
def test_run(): pass
def test_extra(): pass
class TestA:
    def test_same(self): pass
class TestB:
    def test_same(self): pass
""",
    )
    parent = '''"""Protect app behavior.
The second purpose line is not the purpose summary.
"""
raise RuntimeError("model must not import")
import facet_child
MODEL_ID = "parent"
COMPONENTS = ["app"]
IMPLEMENTED_BY = {"Run": "facet_app.py:run"}
NOT_MODELED = {"facet_app.py:side": "Separate integration check"}
TESTED_BY = {"a": ["tests/test_app.py:test_run", "tests/test_app.py:TestA.test_same"]}
RULES = [Invariant("a", "rule a", None), Invariant(name="b", description="rule b", predicate=None)]
def build_explorer(): return Explorer(Workflow(()), (0,), (), invariants=RULES)
def broken_variants():
    metadata = {"not_a_variant": 1}
    return {"x": metadata, "y": {"also_not_a_variant": 2}}
'''
    child = """raise RuntimeError("child must not import")
MODEL_ID = "child"
COMPONENTS = ["app"]
IMPLEMENTED_BY = {"Run": "facet_app.py:run"}
TESTED_BY = {"child_rule": ["tests/test_app.py:test_extra"], "ambiguous": ["tests/test_app.py:test_same"]}
def build_explorer(): raise RuntimeError("no exploration in read")
def broken_variants():
    metadata = {"not_a_variant": 1}
    return {name: metadata for name in ("dynamic",)}
"""
    write(".flowguard/models/facet_parent.py", parent)
    write(".flowguard/models/facet_child.py", child)
    data = dict(
        project="facets",
        layers=["entry", "domain"],
        components=[
            dict(
                _component(
                    "app", summary="Handle app requests", responsibilities=["handle requests"]
                ),
                files=["facet_app.py"],
                tests=["tests/test_app.py"],
                layer="domain",
            ),
            dict(
                _component("store", summary="Save data", responsibilities=["save data"]),
                files=["store.py"],
                layer="entry",
            ),
        ],
    )
    inv = build_inventory(tmp_path, DEFAULT_IGNORE)
    detail = render_show(tmp_path, data, inv, component="app", detail=False)
    for label in ("purpose:", "rules:", "known-bad:", "code:", "tests:"):
        assert (
            sum(
                line.lstrip().startswith(label)
                for line in detail.splitlines()
                if line.startswith(" ")
            )
            == 3
        )
    assert (
        "rules: a: rule a; b: rule b" in detail
        and "known-bad: x, y" in detail
        and "untested: b" in detail
    )
    assert (
        "rules: not readable statically; python -m flowguard map models child prints them" in detail
    )
    assert (
        "known-bad: x, y" in detail
        and "not_a_variant" not in detail
        and "from TESTED_BY" not in detail
    )
    assert "4 functions here and below (bound 3, unbound 1)" in detail
    from flowguard.map.views import render_locate

    assert "none (unbound; position app)" in render_locate(
        tmp_path, data, inv, "tests/test_app.py::TestB::test_same"
    )
    assert "test_not_a_function" not in detail
    assert "not modeled: 1" in detail and "Run -> facet_app.py:run" in detail
    assert "app_imports_store" in detail and "(generated by the system model)" in detail
    assert "test_run (not nested)" not in detail
    overview = render_show(tmp_path, data, inv, component=None, detail=False)
    assert (
        ", 1 rules" in overview
        and "model parent: Protect app behavior. (2 rules, 2 known-bad, 2 tests +2 in children)"
        in overview
    )
    diagram = render_mermaid(tmp_path, data, inv)
    assert "app<br/>1 rules" in diagram and "model parent<br/>2 rules, 2 known-bad" in diagram
    root = render_show(tmp_path, data, inv, component="system", detail=False)
    assert "purpose: facets: 2 components" in root and "no unaccepted dependency cycle" in root
    assert "4 functions, 3 bound" in root
    write(
        ".flowguard/models/facet_child.py",
        child.replace(
            'TESTED_BY = {"child_rule": ["tests/test_app.py:test_extra"], "ambiguous": ["tests/test_app.py:test_same"]}\n',
            "",
        ),
    )
    unknown = render_show(tmp_path, data, inv, component="app", detail=False)
    assert "(? rules, 1 known-bad, 0 tests)" in unknown
    assert not {
        "facet_app",
        "facet_parent",
        "facet_child",
        "_flowguard_model_facet_parent",
        "_flowguard_model_facet_child",
    } & set(sys.modules)


def test_parent_model_rolls_up_child_tests(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.views import render_show

    data, inv = _static_project(tmp_path, _HELPER_SPLIT_MODELS)
    overview = render_show(tmp_path, data, inv, component=None, detail=False)
    assert "+1 in children" in next(
        line for line in overview.splitlines() if "model probe_parent:" in line
    )
    detail = render_show(tmp_path, data, inv, component="app", detail=False)
    lines = detail.splitlines()
    at = next(index for index, line in enumerate(lines) if "model probe_parent:" in line)
    tests = next(line for line in lines[at + 1 : at + 7] if line.strip().startswith("tests:"))
    assert "children: 1 tests in probe_child" in tests


def test_rules_never_come_from_tested_by_keys(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.views import render_show

    data, inv = _static_project(
        tmp_path,
        {".flowguard/models/opaque.py": '''"""Opaque rules."""
MODEL_ID = "opaque"
IMPLEMENTED_BY = {"Run": "app.py:run"}
TESTED_BY = {"keyed_rule": ["tests/test_app.py:test_run"]}
def build_explorer(): return make_explorer()
def broken_variants(): return make_variants()
'''},
    )
    overview = render_show(tmp_path, data, inv, component=None, detail=False)
    assert "model opaque: Opaque rules. (? rules, ? known-bad, 1 tests)" in overview
    detail = render_show(tmp_path, data, inv, component="app", detail=False)
    assert (
        "rules: not readable statically; python -m flowguard map models opaque prints them"
        in detail
    )
    assert "from TESTED_BY" not in detail and "rules: keyed_rule" not in detail


def test_coverage_line_counts_by_source(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.views import render_show

    data, inv = _coverage_project(tmp_path)
    overview = render_show(tmp_path, data, inv, component=None, detail=False)
    assert overview.splitlines()[1].startswith(
        "coverage: entrypoints 2 of 4 bound (model 1, test 1), 1 by reason, 0 unlisted; "
        "state writers 0 of 0 bound (model 0, test 0), 0 by reason"
    ), overview
    detail = render_show(tmp_path, data, inv, component="app", detail=False)
    code = next(line for line in detail.splitlines() if line.strip().startswith("code:"))
    assert (
        "unexplained: app.py:loose" in code
        and "(explain: add it to a model's IMPLEMENTED_BY" in code
    ), code


def test_tests_facet_lists_bindable_tests(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.views import render_show

    data, inv = _coverage_project(tmp_path)
    detail = render_show(tmp_path, data, inv, component="app", detail=False)
    tests = next(
        line
        for line in detail.splitlines()
        if line.startswith(" ") and line.strip().startswith("tests:") and "functions" in line
    )
    assert (
        "tests: 2 functions here and below (bound 0, unbound 2); files: tests/test_app.py" in tests
    ), tests
    assert "bindable:" not in detail and "unbound:" not in detail


def test_read_header_keeps_size_advice_out_of_warning_count(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.views import render_show

    busy = _component("busy", responsibilities=[f"duty {n}" for n in range(9)], summary="Busy")
    busy["tests"] = ["tests/test_busy.py"]
    data = dict(project="demo", components=[busy], flows=[])
    inv = _inventory(tmp_path)
    head = render_show(tmp_path, data, inv, component=None, detail=False).splitlines()[0]
    assert "0 warning(s), 0 accepted debt(s)" in head, head
    data["accepted_debts"] = [
        dict(code="too_many_responsibilities", component="busy", reason="one table of duties")
    ]
    head = render_show(tmp_path, data, inv, component=None, detail=False).splitlines()[0]
    assert "0 warning(s), 1 accepted debt(s)" in head, head
    from flowguard.map.lint import apply_accepted_debts, shape_findings

    findings, used = apply_accepted_debts(
        shape_findings(data, inv, {"busy": set()}), data["accepted_debts"]
    )
    assert not used
    assert any(finding.code == "too_many_responsibilities" and finding.level == "info"
               and "(advice, not a gate)" in finding.message for finding in findings)
    assert all("accepted debt:" not in finding.message for finding in findings)
