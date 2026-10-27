"""Tests grouped by their model or native component."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
import pytest
from flowguard.__main__ import main
from flowguard.map.cli import _context
from flowguard.map.check import run_check
from flowguard.map.lint import run_lint
import pytest, os, json

from _fg_helpers import (
    view__component as _component,
    view__fg232_count_discovery as _fg232_count_discovery,
    view__fg232_view_project as _fg232_view_project,
    view__inventory as _inventory,
    view__quiet_fixture as _quiet_fixture,
    view__review_project as _review_project,
    flowguard_map_contracts421_project as project,
    view__fg232_view_project,
)

def test_read_unknown_component_fails_and_names_the_read_command(tmp_path, capsys):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint

    project(tmp_path)
    assert main(["read", "--root", str(tmp_path), "--component", "nope"]) == 1
    assert "python -m flowguard read" in capsys.readouterr().out


def test_mermaid_export_has_one_node_per_component_and_model(tmp_path, capsys):
    import pytest, os, json
    from pathlib import Path
    import json
    from flowguard.map.views import render_show
    import json
    import re
    import pytest
    from flowguard.__main__ import main
    from flowguard.map import cli
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.views import render_mermaid

    directory = tmp_path / ".flowguard/models"
    directory.mkdir(parents=True)
    (tmp_path / "one.py").write_text("def run(): return True\n")
    (tmp_path / "two.py").write_text("def run(): return False\n")
    (directory / "parent.py").write_text(
        'MODEL_ID="audit.current"\nCOMPONENTS=["a-b"]\nIMPLEMENTED_BY={"One":"one.py:run"}\ndef conformance(): pass\nimport child\ndef build_explorer(): pass\n'
    )
    (directory / "child.py").write_text(
        'MODEL_ID="audit-current"\nCOMPONENTS=["a.b"]\nIMPLEMENTED_BY={"Run":"two.py:run"}\ndef conformance(): pass\ndef build_explorer(): pass\n'
    )
    data = dict(
        schema="flowguard.map.v1",
        project='demo "quoted"',
        layers=['entry "tier"', "empty layer"],
        components=[
            dict(_component("a-b"), files=["one.py"], layer='entry "tier"'),
            dict(_component("a.b"), files=["two.py"]),
        ],
    )
    (tmp_path / ".flowguard/map.json").write_text(json.dumps(data))
    inv = build_inventory(tmp_path, DEFAULT_IGNORE)
    text = render_mermaid(tmp_path, data, inv)
    assert text.startswith("flowchart TD\n")
    definitions = re.findall(r"^\s*([A-Za-z0-9_]+)(?:\[|\(\[)", text, re.M)
    assert len(definitions) == len(set(definitions)) == 5
    assert sum(name.startswith("c_") for name in definitions) == 2
    assert sum(name.startswith("m_") for name in definitions) == 2
    assert all(re.fullmatch("[A-Za-z0-9_]+", name) for name in definitions)
    assert text.count("subgraph ") == len(re.findall(r"^\s*end$", text, re.M)) == 3
    assert "unlayered" in text
    assert "audit.current" in text and "audit-current" in text
    # Sanitized-name collisions cannot merge component or model nodes.
    models = re.findall(r'^\s*(m_\w+)\(\["model ([^"]+)<br/>[^\"]+"\]\)', text, re.M)
    model_ids = {label: node for node, label in models}
    assert f"{model_ids['audit.current']} ==> {model_ids['audit-current']}" in text
    limited = render_mermaid(tmp_path, data, inv, component="a-b")
    assert "a.b" not in limited and "audit.current" in limited and "audit-current" in limited
    assert limited.count("subgraph ") == 1
    assert "empty layer" not in limited and "unlayered" not in limited
    assert cli.main(["--root", str(tmp_path), "show", "--mermaid"]) == 0
    assert capsys.readouterr().out.startswith("flowchart TD\n")
    assert main(["read", "--root", str(tmp_path), "--mermaid", "--component", "a-b"]) == 0
    assert capsys.readouterr().out == limited + "\n"
    with pytest.raises(SystemExit) as error:
        main(["read", "--mermaid", "--find", "run"])
    assert error.value.code == 2

    # A real component named system is distinct from the reserved root node.
    from flowguard.map.tree import build_tree

    (tmp_path / "system_code.py").write_text("def run(): pass\n")
    data["components"].append(dict(_component("system"), files=["system_code.py"]))
    (directory / "local.py").write_text(
        'MODEL_ID="local"\nCOMPONENTS=["system"]\nIMPLEMENTED_BY={"Run":"system_code.py:run"}\ndef conformance(): pass\ndef build_explorer(): pass\n'
    )
    (directory / "rooted.py").write_text(
        'MODEL_ID="rooted"\nPARENT="system"\nIMPLEMENTED_BY={"Run":"one.py:run"}\ndef conformance(): pass\ndef build_explorer(): pass\n'
    )
    inv = build_inventory(tmp_path, DEFAULT_IGNORE)
    tree = build_tree(tmp_path, data, inv)
    assert {n.id for n in tree.models_for_component("system")} == {"local"}
    full = render_show(tmp_path, data, inv, component=None, detail=False)
    assert full.count("model local:") == full.count("model rooted:") == 1
    focused = render_mermaid(tmp_path, data, inv, component="system")
    assert "model local" in focused and "model rooted" not in focused


def test_read_component_names_the_symbols_used_on_each_edge(tmp_path, monkeypatch):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.views import render_show
    import sys

    data, inv, marker = _fg232_view_project(tmp_path)
    calls = _fg232_count_discovery(monkeypatch)
    focused = render_show(tmp_path, data, inv, component="loans", detail=False)
    assert len(calls) == 1
    lines = [line.strip() for line in focused.splitlines()]
    assert (
        "uses catalog: Catalog, Catalog.alpha, Catalog.beta, Catalog.delta, "
        "Catalog.epsilon, Catalog.eta (+3 more)"
    ) in lines
    assert any(line.startswith("uses members: ") and "Members.may_borrow" in line for line in lines)
    assert "uses utils: (module import only)" in lines
    calls.clear()
    overview = render_show(tmp_path, data, inv, component=None, detail=False)
    assert len(calls) == 1
    assert "uses: catalog, members, utils" in overview and "uses catalog:" not in overview
    assert next(line for line in overview.splitlines() if "> flow audit:" in line).endswith(
        " (no model)"
    )
    assert not marker.exists()
    assert not any(name.startswith("view232_") for name in sys.modules)


def test_mermaid_draws_dependencies_and_flows(tmp_path, monkeypatch):
    import pytest, os, json
    from pathlib import Path
    import json
    import json
    import sys
    from flowguard.map.targetfile import load_target
    from flowguard.map.views import render_mermaid

    data, inv, marker = _fg232_view_project(tmp_path)
    calls = _fg232_count_discovery(monkeypatch)
    diagram = render_mermaid(tmp_path, data, inv)
    assert len(calls) == 1
    assert "c_loans -.-> c_catalog" in diagram and "c_loans -.-> c_members" in diagram
    assert 'f_borrow["flow borrow<br/>model borrow_contract"]' in diagram
    assert 'f_audit["flow audit<br/>no model"]' in diagram
    assert 'f_borrow -->|"1"| c_loans' in diagram
    assert 'f_borrow -->|"2"| c_members' in diagram
    assert 'f_borrow -->|"3"| c_catalog' in diagram
    assert "f_borrow --> m_borrow_contract" in diagram

    path = tmp_path / ".flowguard/target/map.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            dict(
                schema="flowguard.target.v1",
                goal="plan a future audit",
                components=[],
                flows=[
                    dict(
                        id="future",
                        summary="Future audit",
                        steps=["loans:LoanService.inventory", "catalog:Catalog.alpha"],
                    )
                ],
                remove=[],
            )
        ),
        encoding="utf-8",
    )
    target = load_target(tmp_path)
    assert target is not None
    calls.clear()
    merged = render_mermaid(tmp_path, data, inv, target=target)
    assert len(calls) == 1
    future = next(line for line in merged.splitlines() if "flow future" in line)
    assert "no model" in future
    assert 'f_future -->|"1"| c_loans' in merged and 'f_future -->|"2"| c_catalog' in merged
    calls.clear()
    current = render_mermaid(tmp_path, data, inv)
    assert len(calls) == 1 and current == diagram
    assert "flow future" not in current
    assert not marker.exists()
    assert not any(name.startswith("view232_") for name in sys.modules)

    # A logical filename can retire its old identity and contain the replacement.
    # An active flow uses the new model; the removed flow keeps the old node.
    draft = json.loads(path.read_text(encoding="utf-8"))
    draft["remove"] = ["flow:borrow", "model:borrow_contract"]
    draft["flows"][0]["model"] = ".flowguard/models/borrow_contract.py"
    path.write_text(json.dumps(draft), encoding="utf-8")
    model = tmp_path / ".flowguard/target/models/borrow_contract.py"
    model.parent.mkdir(parents=True)
    original_model = (tmp_path / ".flowguard/models/borrow_contract.py").read_text(encoding="utf-8")
    assert original_model.count('MODEL_ID = "borrow_contract"') == 1
    model.write_text(
        original_model.replace('MODEL_ID = "borrow_contract"', 'MODEL_ID = "borrow_contract_v2"'),
        encoding="utf-8",
    )
    calls.clear()
    replacement = render_mermaid(tmp_path, data, inv, target=load_target(tmp_path))
    assert len(calls) == 1
    assert 'f_future["flow future<br/>model borrow_contract_v2"]' in replacement
    assert 'f_borrow["flow borrow<br/>model borrow_contract"]' in replacement
    edges = {line.strip() for line in replacement.splitlines()}
    assert "f_future --> m_borrow_contract_v2" in edges
    assert "f_future --> m_borrow_contract" not in edges
    assert "f_borrow --> m_borrow_contract" in edges
    assert "f_borrow --> m_borrow_contract_v2" not in edges
    assert "class m_borrow_contract removed" in replacement
    assert not marker.exists()
    assert not any(name.startswith("view232_") for name in sys.modules)


def test_read_observes_hidden_names_missing_summary_and_model_counts(tmp_path):
    """Valid adversarial read inputs preserve names, purpose and no-import promises."""
    import pytest, os, json
    from pathlib import Path
    from pathlib import Path
    from flowguard.map.views import render_show
    import sys
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory

    def write(relative, source):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")

    write("alpha.py", "def run(): return True\n")
    write("beta.py", "def run(): return True\n")
    write("tests/test_alpha.py", "def test_run(): pass\n")
    write(
        ".flowguard/models/read_probe.py",
        '''"""Explain read probe behavior."""
from pathlib import Path
Path(__file__).parents[2].joinpath("model_import.marker").write_text("imported")
MODEL_ID = "read_probe"
COMPONENTS = ["alpha"]
IMPLEMENTED_BY = {"Run": "alpha.py:run"}
TESTED_BY = {"works": ["tests/test_alpha.py:test_run"]}
RULES = [Invariant("works", "works", None), Invariant("stable", "stable", None)]
def build_explorer(): return Explorer(Workflow(()), (0,), (), invariants=RULES)
def broken_variants(): return {"one": None, "two": None}
''',
    )
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, with_bodies=False, write_cache=False)
    for missing in (False, True):
        components = [
            dict(
                _component(cid, summary=("Serve " + cid) * 30),
                files=[cid + ".py"],
                tests=["tests/test_alpha.py"] if cid == "alpha" else [],
                models=[],
            )
            for cid in ("alpha", "beta")
        ]
        if missing:
            components[0].pop("summary")
        data = dict(project="read fixture", layers=[], components=components, flows=[])
        output = render_show(tmp_path, data, inv, component=None, detail=False)
        assert "## alpha [" in output and "## beta [" in output and "truncated" not in output
        assert (
            "model read_probe: Explain read probe behavior. (2 rules, 2 known-bad, 1 tests)"
            in output
        )
        if missing:
            assert "(no summary yet)" in output.split("## alpha [", 1)[1].split("\n## beta [", 1)[0]
        assert not (tmp_path / "model_import.marker").exists()
        model_dir = (tmp_path / ".flowguard/models").resolve()
        assert not any(
            isinstance((file := vars(module).get("__file__")), str)
            and Path(file).resolve().is_relative_to(model_dir)
            for module in tuple(sys.modules.values())
            if module is not None
        )


def test_read_orders_components_by_layer(tmp_path):
    """Top-level components are listed top-down by layer, keeping map order inside a layer."""
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.views import render_show

    data = dict(
        project="layers",
        layers=["upper", "middle", "lower"],
        flows=[],
        components=[
            dict(_component("low", summary="Low"), layer="lower"),
            dict(_component("mid", summary="Mid"), layer="middle"),
            dict(_component("low_child", summary="Child"), layer="lower", parent="low"),
            dict(_component("top", summary="Top"), layer="upper"),
        ],
    )
    output = render_show(tmp_path, data, _inventory(tmp_path), component=None, detail=False)
    headings = [
        line.strip().split(" [", 1)[0][3:]
        for line in output.splitlines()
        if line.strip().startswith("## ")
    ]
    assert headings == ["top", "mid", "low", "low_child"], output
    assert "\n\n\n" not in output


def test_review_ranks_defects_and_states_true_strengths(tmp_path):
    import pytest, os, json
    from pathlib import Path
    import sys
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.review import render_review

    data = _review_project(tmp_path)
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, with_bodies=False, write_cache=False)
    text = render_review(tmp_path, data, inv)
    lines = text.splitlines()
    assert lines[0].startswith(
        "# demo review: 9 components, 2 models (with system), 1 flows; architecture: 1 error(s)"
    )
    strengths = next(line for line in lines if line.startswith("strengths: "))
    assert "no dependency cycles" not in strengths and "every flow has a model" not in strengths
    assert "every state writer explained" not in strengths and "no layer violations" in strengths
    assert any(line.startswith("  ERROR dependency_cycle x1: ") for line in lines)
    steps = lines[lines.index("optimise next:") + 1 :]
    numbered = [line for line in steps if line.lstrip()[:2].rstrip(".").isdigit()]
    assert numbered[0].startswith("  1. fix dependency_cycle ")
    split = next(
        index
        for index, line in enumerate(numbered)
        if "split hub: hub (used by 3, uses 3, 7 duties" in line
    )
    explain = next(index for index, line in enumerate(numbered) if "explain lib1" in line)
    assert split < explain
    assert all("references/" in line or "python -m flowguard" in line for line in numbered)
    assert steps[-1].startswith("declined: ")
    assert text.count("optimise next:") == 1
    assert not (tmp_path / "model_import.marker").exists()
    assert not any(
        getattr(module, "__file__", None) and str(tmp_path) in str(module.__file__)
        for module in list(sys.modules.values())
    )


def test_closing_debt_hides_one_suggestion(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.review import render_review
    from flowguard.map.lint import run_lint
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE

    data = _quiet_fixture("read_review")["make_fixture"](tmp_path)
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    before = render_review(tmp_path, {**data, "accepted_debts": []}, inv)
    assert "model app:" in before
    after = render_review(tmp_path, data, inv)
    assert "model app:" not in after
    assert after.splitlines()[-1] == "declined: 1 (accepted debts; 0 no longer arise)"
    assert not any(f.code == "debt_stale" for f in run_lint(tmp_path, data, inv))
    data["components"][0].pop("state")
    assert "declined: 1 (accepted debts; 1 no longer arise)" in render_review(tmp_path, data, inv)


def test_coverage_counts_calls_not_words(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.views import render_show
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE

    data = _quiet_fixture("read_show")["make_fixture"](tmp_path)
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    text = render_show(tmp_path, data, inv, component=None, detail=False)
    assert (
        text.splitlines()[1]
        == "coverage: entrypoints 2 of 4 bound (model 1, test 1), 1 by reason, 0 unlisted; state writers 0 of 0 bound (model 0, test 0), 0 by reason"
    )
    assert "unexplained: app.py:mentioned" in render_show(
        tmp_path, data, inv, component="app", detail=False
    )


def test_tests_line_counts_bound_calling_and_neither(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.inventory import PyInfo
    from flowguard.map.views import render_show
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.testtree import test_functions, resolve_test_anchor, test_calls

    data = _quiet_fixture("read_show")["make_fixture"](tmp_path)
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    path = tmp_path / "tests/test_app.py"
    functions = test_functions(path.read_text())
    assert set(functions) == {"test_bound", "test_call", "test_words", "Suite.test_method"}
    assert resolve_test_anchor(path, "test_method[x]") == "Suite.test_method"
    assert resolve_test_anchor(path, "test_bound") == "test_bound"
    calls = test_calls("tests/test_app.py", path.read_text(), inv)
    assert calls["test_words"] == set()
    assert "app.py:modeled" in calls["Suite.test_method"]
    from flowguard.map.inventory import PyInfo

    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg/__init__.py").write_text("# export fixture; never imported\n")
    inv.py["pkg/__init__.py"] = PyInfo("pkg", lazy_exports={"modeled": "app"})
    inv.mod_to_path["pkg"] = "pkg/__init__.py"
    aliases = "from pkg import modeled as public\nimport pkg as p\ndef test_public(): assert public() and p.modeled()\n"
    assert test_calls("tests/test_app.py", aliases, inv)["test_public"] == {"app.py:modeled"}
    (tmp_path / "app.py").write_text(
        (tmp_path / "app.py").read_text()
        + "\nclass Service:\n    def touch(self): return True\ndef wrapper():\n    def hidden(): return True\n    return None\n"
    )
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    constructors = "from app import Service, wrapper\ndef test_construct(): Service(); wrapper()\n"
    values = test_calls("tests/test_app.py", constructors, inv)["test_construct"]
    assert {"app.py:Service", "app.py:Service.touch", "app.py:wrapper"} <= values
    assert "app.py:wrapper.hidden" not in values
    helpers = "from app import modeled as f\nimport app as m\ndef helper(): return f()\ndef deeper(): return helper()\ndef test_helper(): assert helper()\ndef test_deep(): assert deeper()\n"
    calls = test_calls("tests/test_app.py", helpers, inv)
    assert calls["test_helper"] == {"app.py:modeled"}
    assert calls["test_deep"] == set()
    extra = "import unittest\nclass Base(unittest.IsolatedAsyncioTestCase): pass\nclass AsyncSuite(Base):\n    async def test_async(self): pass\nclass Helper:\n    def test_fake(self): pass\nasync def test_top(): pass\n"
    assert set(test_functions(extra)) == {"AsyncSuite.test_async", "test_top"}
    text = render_show(tmp_path, data, inv, component=None, detail=False)
    assert (
        text.splitlines()[2]
        == "tests: 4 test functions; 1 bound to a model (TESTED_BY), 2 call a model's code, 1 neither (python -m flowguard read --find <test path>)"
    )


def test_find_view_imports_no_model(tmp_path, monkeypatch):
    import pytest, os, json
    from pathlib import Path
    import sys
    from flowguard.__main__ import main

    data, inv, marker = view__fg232_view_project(tmp_path)
    assert main(["read", "--root", str(tmp_path), "--find", "loans"]) == 0
    assert (
        main(["read", "--root", str(tmp_path), "--find", "view232_loans.py:LoanService.borrow"])
        == 0
    )
    assert not marker.exists()
    assert not any(name.startswith("view232_") for name in sys.modules)


def _complete_read_project(root):
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE

    models = root / ".flowguard/models"
    models.mkdir(parents=True)
    components = []
    for cid, parent in [("group", None), ("own", "group"), ("sibling", "group"), ("remote", None)]:
        (root / (cid + ".py")).write_text("def run(): return True\n")
        component = dict(
            id=cid,
            summary="Serve " + cid,
            responsibilities=[cid + "_ownership"],
            files=[cid + ".py"],
            tests=[],
            models=[],
            depends_on=[],
            status="draft",
        )
        if parent:
            component["parent"] = parent
        components.append(component)
    for mid, parent, home in [
        ("parent", "own", "own"),
        ("a", "parent", "own"),
        ("b", "parent", "own"),
        ("c", "parent", "own"),
        ("sibling_model", "sibling", "sibling"),
        ("remote_model", "remote", "remote"),
    ]:
        (models / (mid + ".py")).write_text(
            f'"""Protect {mid}."""\nMODEL_ID={mid!r}\nPARENT={parent!r}\nCOMPONENTS={[home, "own"] if mid == "remote_model" else [home]!r}\nIMPLEMENTED_BY={{"Run":{(home + ".py:run")!r}}}\nRULES=(Invariant("safe","stay safe",None),)\ndef build_explorer(): raise RuntimeError("read must stay static")\ndef broken_variants(): return {{"bad": None}}\n'
        )
    data = dict(schema="flowguard.map.v1", project="complete read", components=components)
    (root / ".flowguard/map.json").write_text(json.dumps(data))
    return data, build_inventory(root, DEFAULT_IGNORE, write_cache=False)


def test_read_is_complete_and_folds_children(tmp_path):
    from flowguard.map.views import render_show

    data, inv = _complete_read_project(tmp_path)
    text = render_show(tmp_path, data, inv, component=None, detail=False)
    assert "+3 stage children: a, b, c" in text
    assert all("## " + component["id"] + " [" in text for component in data["components"])
    assert all(name in text for name in ("parent", "a", "b", "c", "sibling_model", "remote_model"))
    assert "truncated" not in text and "shortened" not in text
