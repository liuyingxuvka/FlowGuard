"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_change_selects_a_child_that_imports_its_parent_in_a_function(impact_project):
    """The documented split style imports the parent inside a function; editing the parent selects it."""
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from _fg_helpers import map_write as write, map_impact_of as impact_of, map_git as git
    from flowguard.map.tree import build_tree
    root, data = impact_project
    write(root, ".flowguard/models/parent.py", 'MODEL_ID = "parent"\nCOMPONENTS = ["storage"]\nLIMIT = 1\n'
          'IMPLEMENTED_BY = {"save": "shop/storage.py:save"}\ndef build_explorer(): pass\ndef conformance(): pass\n')
    write(root, ".flowguard/models/child.py", 'MODEL_ID = "child"\nPARENT = "parent"\n'
          'def _starts():\n    import parent\n    return parent.LIMIT\n'
          'def build_explorer(): pass\ndef conformance(): pass\n')
    git(root, "add", "-A")
    git(root, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "parent and child")
    path = root / ".flowguard/models/parent.py"
    original = path.read_text(encoding="utf-8")
    path.write_text(original.replace("LIMIT = 1", "LIMIT = 2"), encoding="utf-8")
    impact = impact_of(root, data, [".flowguard/models/parent.py"], base="HEAD")
    assert {"parent", "child"} <= set(impact.model_ids) and not impact.blocked
    path.write_text(original + "# only a comment\n", encoding="utf-8")
    assert impact_of(root, data, [".flowguard/models/parent.py"], base="HEAD").model_ids == []
    tree = build_tree(root, data, build_inventory(root, DEFAULT_IGNORE))
    assert (tree.nodes["child"].parent, tree.nodes["child"].parent_kind) == ("parent", "model")
    assert tree.nodes["child"].local_import_files == {".flowguard/models/parent.py"}
    assert not [f for f in tree.findings if f.code == "parent_import_mismatch"]

import json
import subprocess
from pathlib import Path
import pytest
from flowguard.__main__ import main
from flowguard.map.cli import _context
from flowguard.map.check import run_check
from flowguard.map.lint import run_lint
from _fg_helpers import flowguard_map_contracts421_write as write, flowguard_map_contracts421_project as project, flowguard_map_contracts421_save as save, flowguard_map_contracts421_findings as findings, flowguard_map_contracts421_CONTRACT as CONTRACT, flowguard_map_contracts421__placement_port_source as _placement_port_source, flowguard_map_contracts421__fg233_parent_project as _fg233_parent_project, flowguard_map_contracts421__scope_helpers as _scope_helpers, flowguard_map_contracts421_json as json, flowguard_map_contracts421_subprocess as subprocess, flowguard_map_contracts421_Path as Path, flowguard_map_contracts421_pytest as pytest, flowguard_map_contracts421_main as main, flowguard_map_contracts421__context as _context, flowguard_map_contracts421_run_check as run_check, flowguard_map_contracts421_run_lint as run_lint
import pytest, os, json
from _fg_helpers import map_views421_pytest as pytest, map_views421_os as os, map_views421_json as json, map_views421_Path as Path

def test_model_tree_parent_defaults_and_nesting_warnings(tmp_path):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint
    from _fg_helpers import flowguard_map_contracts421_write as write, flowguard_map_contracts421_project as project, flowguard_map_contracts421_save as save, flowguard_map_contracts421_findings as findings, flowguard_map_contracts421_CONTRACT as CONTRACT, flowguard_map_contracts421__placement_port_source as _placement_port_source, flowguard_map_contracts421__fg233_parent_project as _fg233_parent_project, flowguard_map_contracts421__scope_helpers as _scope_helpers, flowguard_map_contracts421_json as json, flowguard_map_contracts421_subprocess as subprocess, flowguard_map_contracts421_Path as Path, flowguard_map_contracts421_pytest as pytest, flowguard_map_contracts421_main as main, flowguard_map_contracts421__context as _context, flowguard_map_contracts421_run_check as run_check, flowguard_map_contracts421_run_lint as run_lint
    from flowguard.map.mapfile import read_model_contract

    data = project(tmp_path)
    parent = CONTRACT.replace('"one"', '"parent"') + "\nimport child\nimport _shared\n" + _placement_port_source(child="child")
    child = CONTRACT.replace('"one"', '"child"') + "\nfrom _shared import VALUE\n" + _placement_port_source()
    write(tmp_path, ".flowguard/models/parent.py", parent)
    write(tmp_path, ".flowguard/models/child.py", child)
    write(tmp_path, ".flowguard/models/_shared.py", "PARENT = None\nimport _leaf\nVALUE = 1\n")
    write(tmp_path, ".flowguard/models/_leaf.py", "import _shared\n")
    contract = read_model_contract(tmp_path / ".flowguard/models/parent.py")
    assert contract.get("imports") == ["_shared", "child", "dataclasses", "flowguard"]
    from flowguard.map.tree import build_tree

    def tree():
        current, inv = _context(tmp_path)
        return build_tree(tmp_path, current, inv)

    current = tree()
    assert (current.nodes["child"].parent, current.nodes["child"].source) == ("parent", "import")
    assert (current.nodes["parent"].parent, current.nodes["parent"].source) == ("app", "COMPONENTS")
    assert current.nodes["child"].home == "app"
    assert current.importers(".flowguard/models/_shared.py") == {"parent", "child"}
    assert current.importers(".flowguard/models/_leaf.py") == {"parent", "child"}
    assert current.ancestors("child") == ["parent"]
    assert [n.id for n in current.children("parent", "model")] == ["child"]
    assert not current.findings

    write(tmp_path, ".flowguard/models/child.py", child + '\nPARENT = "nope"\n')
    assert next(f.level for f in tree().findings if f.code == "parent_unknown") == "error"
    assert main(["map", "--root", str(tmp_path), "check"]) == 1
    assert main(["release", "--root", str(tmp_path)]) == 1
    assert main(["read", "--root", str(tmp_path)]) == 0
    assert tree().nodes["child"].parent == "parent"
    write(tmp_path, ".flowguard/models/child.py", child + '\nPARENT = "app"\n')
    assert next(f.level for f in tree().findings if f.code == "parent_import_mismatch") == "error"
    assert main(["map", "--root", str(tmp_path), "check"]) == 1
    write(tmp_path, ".flowguard/models/parent.py", parent + '\nPARENT = "child"\n')
    write(tmp_path, ".flowguard/models/child.py", child + '\nPARENT = "parent"\n')
    current = tree()
    assert next(f.level for f in current.findings if f.code == "parent_cycle") == "error"
    assert main(["map", "--root", str(tmp_path), "check"]) == 1
    assert main(["release", "--root", str(tmp_path)]) == 1
    assert main(["read", "--root", str(tmp_path)]) == 0
    assert all(node.parent_kind != "model" for node in current.nodes.values())
    assert not current.ancestors("child")

    write(tmp_path, "other.py", "def run(): return False\n")
    data["components"].append({"id": "other", "files": ["other.py"], "status": "draft"})
    save(tmp_path, data)
    write(tmp_path, ".flowguard/models/parent.py", parent)
    write(tmp_path, ".flowguard/models/child.py", child.replace("app.py:run", "other.py:run"))
    current = tree()
    assert "anchor_outside_home" in {f.code for f in current.findings}
    assert next(f.level for f in current.findings if f.code == "anchor_outside_home") == "error"
    assert "anchor_outside_home" in {f.code for f in findings(tmp_path)}
    assert main(["map", "--root", str(tmp_path), "check"]) == 1
    write(tmp_path, ".flowguard/models/child.py", child)
    write(tmp_path, ".flowguard/models/second.py", child.replace('"child"', '"second"') + '\nPARENT = "parent"\n')
    assert next(f.level for f in tree().findings if f.code == "duplicate_child_owner") == "error"
    assert main(["map", "--root", str(tmp_path), "check"]) == 1
    write(tmp_path, ".flowguard/models/second.py", child.replace('"child"', '"system"'))
    assert "model_contract" in {f.code for f in findings(tmp_path)}


def test_model_tree_anchor_components_and_root_defaults(tmp_path):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint
    from _fg_helpers import flowguard_map_contracts421_write as write, flowguard_map_contracts421_project as project, flowguard_map_contracts421_save as save, flowguard_map_contracts421_findings as findings, flowguard_map_contracts421_CONTRACT as CONTRACT, flowguard_map_contracts421__placement_port_source as _placement_port_source, flowguard_map_contracts421__fg233_parent_project as _fg233_parent_project, flowguard_map_contracts421__scope_helpers as _scope_helpers, flowguard_map_contracts421_json as json, flowguard_map_contracts421_subprocess as subprocess, flowguard_map_contracts421_Path as Path, flowguard_map_contracts421_pytest as pytest, flowguard_map_contracts421_main as main, flowguard_map_contracts421__context as _context, flowguard_map_contracts421_run_check as run_check, flowguard_map_contracts421_run_lint as run_lint
    from flowguard.map.tree import build_tree

    data = project(tmp_path)
    write(tmp_path, ".flowguard/models/anchored.py", CONTRACT.replace('"one"', '"anchored"').replace('COMPONENTS = ["app"]', 'COMPONENTS = []'))
    write(tmp_path, ".flowguard/models/rooted.py", 'MODEL_ID = "rooted"\nIMPLEMENTED_BY = {"Probe": "tests/test_app.py:test_run"}\ndef build_explorer(): pass\ndef conformance(): pass\n')
    native = ".flowguard/models/native.py"
    write(tmp_path, "app.py", "def run(): return True\ndef native(): return True\n")
    write(tmp_path, native, CONTRACT.replace('"one"', '"native"').replace("app.py:run", "app.py:native") + '\ndef conformance(): pass\n')
    data["components"][0]["models"] = [native]
    save(tmp_path, data)
    current, inv = _context(tmp_path)
    tree = build_tree(tmp_path, current, inv)
    assert (tree.nodes["anchored"].parent, tree.nodes["anchored"].source) == ("app", "anchor")
    assert (tree.nodes["native"].parent, tree.nodes["native"].source) == ("app", "COMPONENTS")
    assert (tree.nodes["rooted"].parent, tree.nodes["rooted"].source) == ("system", "default")
    assert not tree.findings


def test_child_import_of_its_explicit_parent_preserves_tree_and_impact(tmp_path, capsys):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint
    from _fg_helpers import flowguard_map_contracts421_write as write, flowguard_map_contracts421_project as project, flowguard_map_contracts421_save as save, flowguard_map_contracts421_findings as findings, flowguard_map_contracts421_CONTRACT as CONTRACT, flowguard_map_contracts421__placement_port_source as _placement_port_source, flowguard_map_contracts421__fg233_parent_project as _fg233_parent_project, flowguard_map_contracts421__scope_helpers as _scope_helpers, flowguard_map_contracts421_json as json, flowguard_map_contracts421_subprocess as subprocess, flowguard_map_contracts421_Path as Path, flowguard_map_contracts421_pytest as pytest, flowguard_map_contracts421_main as main, flowguard_map_contracts421__context as _context, flowguard_map_contracts421_run_check as run_check, flowguard_map_contracts421_run_lint as run_lint
    from flowguard.map.tree import build_tree
    from flowguard.map.impact import compute_impact

    data = project(tmp_path)
    parent = CONTRACT.replace('MODEL_ID = "one"', 'MODEL_ID = "parent"')
    parent += '\ndef conformance():\n    from app import run\n    return run()\n'
    child = parent.replace('MODEL_ID = "parent"', 'MODEL_ID = "child"') + '\nPARENT="parent"\nimport parent\n'
    write(tmp_path, '.flowguard/models/parent.py', parent)
    write(tmp_path, '.flowguard/models/child.py', child)
    current, inv = _context(tmp_path)
    tree = build_tree(tmp_path, current, inv)
    assert tree.nodes['parent'].parent_kind == 'component'
    assert (tree.nodes['child'].parent, tree.nodes['child'].parent_kind) == ('parent', 'model')
    assert not {'parent_cycle', 'parent_import_mismatch'} & {f.code for f in tree.findings}
    assert tree.imports['.flowguard/models/child.py'] == {'.flowguard/models/parent.py'}
    impact = compute_impact(tmp_path, current, inv, ['.flowguard/models/parent.py'])
    assert {'parent', 'child'} <= set(impact.model_ids)
    assert main(['read', '--root', str(tmp_path), '--component', 'app']) == 0
    lines = capsys.readouterr().out.splitlines()
    p = next(line for line in lines if 'model parent:' in line)
    c = next(line for line in lines if 'model child:' in line)
    assert len(c) - len(c.lstrip()) == len(p) - len(p.lstrip()) + 2
    write(tmp_path, '.flowguard/models/parent.py', parent + '\nPARENT="child"\n')
    assert 'parent_cycle' in {f.code for f in findings(tmp_path)}


def test_old_mesh_mistakes_are_tree_errors(tmp_path, capsys):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint
    from _fg_helpers import flowguard_map_contracts421_write as write, flowguard_map_contracts421_project as project, flowguard_map_contracts421_save as save, flowguard_map_contracts421_findings as findings, flowguard_map_contracts421_CONTRACT as CONTRACT, flowguard_map_contracts421__placement_port_source as _placement_port_source, flowguard_map_contracts421__fg233_parent_project as _fg233_parent_project, flowguard_map_contracts421__scope_helpers as _scope_helpers, flowguard_map_contracts421_json as json, flowguard_map_contracts421_subprocess as subprocess, flowguard_map_contracts421_Path as Path, flowguard_map_contracts421_pytest as pytest, flowguard_map_contracts421_main as main, flowguard_map_contracts421__context as _context, flowguard_map_contracts421_run_check as run_check, flowguard_map_contracts421_run_lint as run_lint
    data = project(tmp_path)
    write(tmp_path, "app.py", "def run():\n    return True\n\ndef finish():\n    return False\n")
    write(tmp_path, "tests/test_app.py", "from app import run, finish\n\ndef test_run():\n    assert run() is True\n    assert finish() is False\n")
    source = '''from dataclasses import dataclass,replace
from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
COMPONENTS = ["app"]
TESTED_BY = {"boolean_result": ["tests/test_app.py:test_run"]}
@dataclass(frozen=True)
class ResultState:
    value: bool = EXPECTED
    borrow_value: bool = True
    returning_value: bool = False
OUTPUTS = {"value": (EXPECTED,)}
KEEPS = ("value", "borrow_value", "returning_value")
class Result:
    name = "Result"
    writes = ("value", "borrow_value", "returning_value")
    def __init__(self, bad=False): self.bad = bad
    def apply(self, inp, state):
        value = not EXPECTED if self.bad else EXPECTED
        return [FunctionResult(value, replace(state, value=value))]
def explorer(bad=False):
    return Explorer(Workflow((Result(bad),)), initial_states=(ResultState(),), external_inputs=(0,),
                    max_sequence_length=1, progress_steps=0,
                    invariants=(Invariant("boolean_result", "preserve the promised result", lambda s, t: s.value == EXPECTED),))
def build_explorer(): return explorer()
def broken_variants(): return {"wrong_result": explorer(True)}
def conformance():
    from app import run, finish
    return CodeFactsReport((Fact("run", run() is True), Fact("finish", finish() is False)))
'''
    def model(mid, anchors, expected, parent=None):
        contract = f"MODEL_ID = {mid!r}\nIMPLEMENTED_BY = {anchors!r}\nEXPECTED = {expected!r}\n"
        if parent is not None:
            contract += f"PARENT = {parent!r}\n"
        # The coarse model receives each child's boolean into its own field.
        port = ('\nOUTPUTS={}\nHANDOFF={"borrow":{"value":"borrow_value"},"returning":{"value":"returning_value"}}\n' if mid == "lending" else '')
        write(tmp_path, f".flowguard/models/{mid}.py", contract + source.replace('OUTPUTS = {"value": (EXPECTED,)}', f'OUTPUTS = {{"value": ({expected!r},)}}') + port)

    model("lending", {"Run": "app.py:run", "Finish": "app.py:finish"}, True)
    model("borrow", {"Run": "app.py:run"}, True, "lending")
    model("returning", {"Run": "app.py:run"}, True, "lending")
    data["components"][0]["models"] = [f".flowguard/models/{mid}.py" for mid in ("lending", "borrow", "returning")]
    save(tmp_path, data)
    errors = [f for f in findings(tmp_path) if f.code == "duplicate_child_owner"]
    assert errors and all(f.level == "error" for f in errors)
    assert main(["map", "check", "--root", str(tmp_path)]) == 1
    capsys.readouterr()
    model("returning", {"Finish": "app.py:finish"}, False, "lendng")
    current = findings(tmp_path)
    assert any(f.code == "duplicate_child_owner" for f in current)  # the unknown parent leaves independent overlapping owners
    errors = [f for f in current if f.code == "parent_unknown"]
    assert len(errors) == 1 and errors[0].level == "error" and "lendng" in errors[0].message
    assert main(["map", "check", "--root", str(tmp_path)]) == 1
    capsys.readouterr()
    model("returning", {"Finish": "app.py:finish"}, False, "lending")
    assert not any(f.code in {"duplicate_child_owner", "parent_unknown"} for f in findings(tmp_path))
    assert main(["map", "check", "--root", str(tmp_path)]) == 0
    capsys.readouterr()


def test_component_parent_mistakes_are_errors(tmp_path, capsys):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint
    from _fg_helpers import flowguard_map_contracts421_write as write, flowguard_map_contracts421_project as project, flowguard_map_contracts421_save as save, flowguard_map_contracts421_findings as findings, flowguard_map_contracts421_CONTRACT as CONTRACT, flowguard_map_contracts421__placement_port_source as _placement_port_source, flowguard_map_contracts421__fg233_parent_project as _fg233_parent_project, flowguard_map_contracts421__scope_helpers as _scope_helpers, flowguard_map_contracts421_json as json, flowguard_map_contracts421_subprocess as subprocess, flowguard_map_contracts421_Path as Path, flowguard_map_contracts421_pytest as pytest, flowguard_map_contracts421_main as main, flowguard_map_contracts421__context as _context, flowguard_map_contracts421_run_check as run_check, flowguard_map_contracts421_run_lint as run_lint
    import sys

    data, marker = _fg233_parent_project(tmp_path)
    assert main(['map', '--root', str(tmp_path), 'check']) == 0
    output = capsys.readouterr().out
    assert '0 error(s)' in output
    # This real model names the parent but anchors a child's directly owned source.
    assert 'anchor_outside_home' not in output and 'file_multi_owner' not in output

    # COMPONENTS names the whole protected subsystem; placement alone does not.
    from flowguard.map.impact import compute_impact
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import ignore_patterns

    path = tmp_path / '.flowguard/models/parent233_rules.py'
    scope_source = path.read_text(encoding='utf-8')
    assert scope_source.count('MODEL_ID="parent233_rules"') == 1
    assert scope_source.count('PARENT="records"') == 1
    scope_source = scope_source.replace('MODEL_ID="parent233_rules"', 'MODEL_ID="parent233_scope"').replace(
        'PARENT="records"', 'COMPONENTS=["records"]')
    write(tmp_path, '.flowguard/models/parent233_scope.py', scope_source)
    inv = build_inventory(tmp_path, ignore_patterns(data), write_cache=False)
    changed = compute_impact(tmp_path, data, inv, ['parent233_catalog.py'])
    assert changed.direct == ['catalog']
    assert changed.models == ['.flowguard/models/parent233_scope.py']
    assert '.flowguard/models/parent233_rules.py' not in changed.models

    # A map-only reparent changes verification scope too, including the old group.
    import subprocess

    git = ['git', '-C', str(tmp_path)]
    subprocess.run([*git, 'init', '-q'], check=True)
    subprocess.run([*git, 'add', '--', '.flowguard/map.json', '.flowguard/models',
                    'parent233_loans.py', 'parent233_catalog.py', 'tests/test_parent233.py'], check=True)
    subprocess.run([*git, '-c', 'user.name=FlowGuard test', '-c', 'user.email=test@example.invalid',
                    '-c', 'commit.gpgsign=false', 'commit', '-qm', 'parent scope baseline'], check=True)
    data['components'][2].pop('parent')
    save(tmp_path, data)
    inv = build_inventory(tmp_path, ignore_patterns(data), write_cache=False)
    moved = compute_impact(tmp_path, data, inv, ['.flowguard/map.json'], base='HEAD')
    assert moved.direct == ['catalog']
    assert moved.models == ['.flowguard/models/parent233_scope.py']
    assert '.flowguard/models/parent233_rules.py' not in moved.models
    assert 'catalog' not in moved.map_review
    data['components'][2]['parent'] = 'records'
    save(tmp_path, data)

    def _fg233_assert_error(code):
        save(tmp_path, data)
        assert main(['map', '--root', str(tmp_path), 'check']) == 1
        output = capsys.readouterr().out
        assert any(line.split()[:2] == ['ERROR', code] for line in output.splitlines()), output
        assert not marker.exists()

    data['components'][1]['parent'] = 'missing'
    _fg233_assert_error('component_parent_unknown')
    data['components'][1]['parent'] = 'records'
    data['components'][0]['parent'] = 'loans'
    _fg233_assert_error('component_parent_cycle')
    data['components'][0].pop('parent')
    data['components'][1]['layer'] = 'other'
    _fg233_assert_error('component_parent_layer')
    data['components'][1]['layer'] = 'records'
    data['components'][0]['depends_on'] = ['loans']
    _fg233_assert_error('dep_unused')
    data['components'][0]['depends_on'] = []
    data['components'][0]['files'] = ['missing.py']
    _fg233_assert_error('component_empty')
    assert not marker.exists()
    assert not any(name.startswith('parent233_') for name in sys.modules)


def test_component_parent_nests_and_rolls_up(tmp_path, capsys):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_views421_pytest as pytest, map_views421_os as os, map_views421_json as json, map_views421_Path as Path
    from flowguard.map.views import render_show
    from _fg_helpers import view__fg233_nested_project as _fg233_nested_project
    import re
    import sys
    from flowguard.__main__ import main
    from flowguard.map.views import render_mermaid

    data, inv, marker = _fg233_nested_project(tmp_path)
    assert main(['map', '--root', str(tmp_path), 'check']) == 0
    output = capsys.readouterr().out
    assert '0 error(s)' in output and 'component_empty' not in output
    overview = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
    headings = [line for line in overview.splitlines() if line.lstrip().startswith('## ')]
    ids = [line.lstrip().split()[1] for line in headings]
    parent_index = ids.index('records')
    assert set(ids[parent_index + 1:parent_index + 3]) == {'catalog', 'loans'}
    parent_line = headings[parent_index]
    assert parent_line.startswith('## records ')
    assert all(line.startswith('  ## ') for line in headings[parent_index + 1:parent_index + 3])
    child_paths = ('view232_catalog.py', 'view232_loans.py')
    expected_loc = sum(inv.loc[path] for path in child_paths)
    assert f'2 files/{expected_loc} loc' in parent_line and ', 3 rules' in parent_line
    assert ('coverage: entrypoints 3 of 5 bound (model 2, test 1), 1 by reason, 0 unlisted; '
            'state writers 1 of 2 bound (model 1, test 0), 0 by reason') in overview
    assert 'truncated' not in overview

    focused = render_show(tmp_path, data, inv, component='records', detail=False, budget=8000)
    assert '## records ' in focused and '  ## catalog ' in focused and '  ## loans ' in focused
    assert '## subject ' not in focused and 'model borrow_contract:' in focused
    parent_block = focused.split('## records ', 1)[1].split('  ## ', 1)[0]
    assert '1 functions here and below' in parent_block and 'tests/test_parent233_loans.py' in parent_block
    diagram = render_mermaid(tmp_path, data, inv, component='records')
    assert 'subgraph sg_c_records["records"]' in diagram
    start = diagram.index('subgraph sg_c_records["records"]')
    # Both children are leaves, so the next subgraph end closes records.
    subsystem = re.split(r'\n\s*end(?:\n|$)', diagram[start:], maxsplit=1)[0]
    assert all(re.search(r'\bc_' + name + r'\[', subsystem) for name in ('records', 'catalog', 'loans'))
    assert not marker.exists()
    assert not any(name.startswith('view232_') for name in sys.modules)


def test_build_tree_memo_is_not_mutated(tmp_path, monkeypatch, capsys):
    import copy
    from flowguard.__main__ import main
    from flowguard.map import tree
    from _fg_helpers import target_shelf_project
    root = target_shelf_project(tmp_path)
    original = tree._build_tree
    snapshots = []
    def built(root, data, inv, **kwargs):
        result = original(root, data, inv, **kwargs)
        snapshots.append((root, copy.deepcopy(data), inv, dict(kwargs), result))
        return result
    monkeypatch.setattr(tree, '_build_tree', built)
    assert main(['read', '--root', str(root)]) == 0
    assert main(['target', 'start', 'readonly tree', '--root', str(root)]) == 0
    assert main(['target', 'add', 'lending', '--root', str(root)]) == 0
    # A noop target still traverses native current and target tree views.
    assert main(['target', 'check', '--root', str(root)]) == 1
    capsys.readouterr()
    assert snapshots
    def projection(value):
        return {mid: (node.path, node.parent, node.parent_kind, node.contract,
                      tuple(child.id for child in value.children(mid, 'model')))
                for mid, node in value.nodes.items()}
    for root, data, inv, kwargs, memoized in snapshots:
        assert projection(memoized) == projection(original(root, data, inv, **kwargs))
