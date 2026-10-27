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
from _fg_helpers import flowguard_map_contracts421_write as write, flowguard_map_contracts421_project as project, flowguard_map_contracts421_save as save, flowguard_map_contracts421_findings as findings, flowguard_map_contracts421_CONTRACT as CONTRACT, flowguard_map_contracts421__placement_port_source as _placement_port_source, flowguard_map_contracts421__fg233_parent_project as _fg233_parent_project, flowguard_map_contracts421__scope_helpers as _scope_helpers, flowguard_map_contracts421_json as json, flowguard_map_contracts421_subprocess as subprocess, flowguard_map_contracts421_Path as Path, flowguard_map_contracts421_pytest as pytest, flowguard_map_contracts421_main as main, flowguard_map_contracts421__context as _context, flowguard_map_contracts421_run_check as run_check, flowguard_map_contracts421_run_lint as run_lint
import shutil
import sys
import tempfile
import unittest
from flowguard.map.discover import component_summary, console_scripts, discover, discover_inventory, file_facts
from flowguard.map.common import DEFAULT_IGNORE
from flowguard.map.inventory import build_inventory
from flowguard.map.lint import entrypoint_coverage_findings, run_lint, scoped_architecture_findings
from flowguard.map.scan import guess_tests, new_map, propose_components
from _fg_helpers import flowguard_map_discover421_ROOT as ROOT, flowguard_map_discover421_APP as APP, flowguard_map_discover421_STORE as STORE, flowguard_map_discover421_CLI as CLI, flowguard_map_discover421_write_project as write_project, flowguard_map_discover421_map_cli as map_cli, flowguard_map_discover421__INJECTED_STORE as _INJECTED_STORE, flowguard_map_discover421__INJECTED_SERVICE as _INJECTED_SERVICE, flowguard_map_discover421__INJECTED_CLI as _INJECTED_CLI, flowguard_map_discover421__injected_project as _injected_project, flowguard_map_discover421__resolution_case as _resolution_case, flowguard_map_discover421_literal_fixture as literal_fixture, flowguard_map_discover421_json as json, flowguard_map_discover421_shutil as shutil, flowguard_map_discover421_subprocess as subprocess, flowguard_map_discover421_sys as sys, flowguard_map_discover421_tempfile as tempfile, flowguard_map_discover421_unittest as unittest, flowguard_map_discover421_Path as Path, flowguard_map_discover421_pytest as pytest, flowguard_map_discover421_component_summary as component_summary, flowguard_map_discover421_console_scripts as console_scripts, flowguard_map_discover421_discover as discover, flowguard_map_discover421_discover_inventory as discover_inventory, flowguard_map_discover421_file_facts as file_facts, flowguard_map_discover421_DEFAULT_IGNORE as DEFAULT_IGNORE, flowguard_map_discover421_build_inventory as build_inventory, flowguard_map_discover421_entrypoint_coverage_findings as entrypoint_coverage_findings, flowguard_map_discover421_run_lint as run_lint, flowguard_map_discover421_scoped_architecture_findings as scoped_architecture_findings, flowguard_map_discover421_guess_tests as guess_tests, flowguard_map_discover421_new_map as new_map, flowguard_map_discover421_propose_components as propose_components
from dataclasses import fields, is_dataclass, replace
import runpy
from flowguard.map.mapfile import load_map
from flowguard.map.port import model_port, port_findings, upward
from flowguard.map.tree import build_tree
from _fg_helpers import flowguard_port421_helpers as helpers, flowguard_port421_project as project, flowguard_port421_probe as probe, flowguard_port421_errors as errors, flowguard_port421_rewrite as rewrite, flowguard_port421_dispatch_project as dispatch_project, flowguard_port421_escalation_model as escalation_model, flowguard_port421__select_ports as _select_ports, flowguard_port421_fields as fields, flowguard_port421_is_dataclass as is_dataclass, flowguard_port421_replace as replace, flowguard_port421_Path as Path, flowguard_port421_json as json, flowguard_port421_runpy as runpy, flowguard_port421_DEFAULT_IGNORE as DEFAULT_IGNORE, flowguard_port421_build_inventory as build_inventory, flowguard_port421_load_map as load_map, flowguard_port421_model_port as model_port, flowguard_port421_port_findings as port_findings, flowguard_port421_upward as upward, flowguard_port421_build_tree as build_tree
import pytest, os, json
from _fg_helpers import map_views421_pytest as pytest, map_views421_os as os, map_views421_json as json, map_views421_Path as Path

def test_parent_literal_validation_and_sibling_loading(tmp_path):
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
    import pytest
    from flowguard.map.mapfile import model_registry, read_model_contract
    from flowguard.map.proof import _load

    project(tmp_path)
    path = tmp_path / ".flowguard/models/one.py"
    for invalid in ('""', 'None', '[]', '42'):
        write(tmp_path, ".flowguard/models/one.py", CONTRACT + f"\nPARENT = {invalid}\n")
        with pytest.raises(ValueError, match="PARENT"):
            read_model_contract(path)
        assert any(i.code == "model_contract" for i in model_registry(tmp_path).issues)
    write(tmp_path, ".flowguard/models/one.py", CONTRACT + '\nPARENT = "system"\n')
    assert read_model_contract(path)["PARENT"] == "system"
    write(tmp_path, ".flowguard/models/sibling_for_load_probe.py", "VALUE = 73\n")
    write(tmp_path, ".flowguard/models/load_probe.py", "import sibling_for_load_probe\nVALUE = sibling_for_load_probe.VALUE\n")
    original = list(sys.path)
    try:
        assert _load(tmp_path, tmp_path / ".flowguard/models/load_probe.py").VALUE == 73
        assert str(tmp_path / ".flowguard/models") in sys.path
    finally:
        sys.path[:] = original
        sys.modules.pop("sibling_for_load_probe", None)
        sys.modules.pop("_flowguard_model_load_probe", None)


@pytest.mark.parametrize("literal", ["[]", '{"Read": ""}', '{"Read": "lib.py"}', '{"Read": None}'])
def test_uses_contract_is_validated(tmp_path, literal):
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
    path = tmp_path / "model.py"
    path.write_text('MODEL_ID = "uses"\nUSES = ' + literal + '\n')
    with pytest.raises(ValueError, match="USES must map names to nonempty"):
        read_model_contract(path)


def test_model_port_reads_state_blocks_and_literals(tmp_path):
    from dataclasses import fields, is_dataclass, replace
    from pathlib import Path
    import json
    import runpy
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import load_map
    from flowguard.map.port import model_port, port_findings, upward
    from flowguard.map.tree import build_tree
    from _fg_helpers import flowguard_port421_helpers as helpers, flowguard_port421_project as project, flowguard_port421_probe as probe, flowguard_port421_errors as errors, flowguard_port421_rewrite as rewrite, flowguard_port421_dispatch_project as dispatch_project, flowguard_port421_escalation_model as escalation_model, flowguard_port421__select_ports as _select_ports, flowguard_port421_fields as fields, flowguard_port421_is_dataclass as is_dataclass, flowguard_port421_replace as replace, flowguard_port421_Path as Path, flowguard_port421_json as json, flowguard_port421_runpy as runpy, flowguard_port421_DEFAULT_IGNORE as DEFAULT_IGNORE, flowguard_port421_build_inventory as build_inventory, flowguard_port421_load_map as load_map, flowguard_port421_model_port as model_port, flowguard_port421_port_findings as port_findings, flowguard_port421_upward as upward, flowguard_port421_build_tree as build_tree
    data, inv = project(tmp_path)
    source = (tmp_path / ".flowguard/models/desk.py").read_text()
    port = model_port(source)
    assert port.state == ("request", "answer", "reply")
    assert set(port.blocks) == {"TakeRequest", "Receive", "Reply"} and not port.approximate
    assert set(port.writes) == {"request", "answer", "reply"}
    assert port.handoff == {"lending": {"answer": "answer"}} and port.keeps == ("request", "reply")
    assert model_port('PARENT="unused"\ndef build_explorer(): return feature_explorer(())').state == (
        "features", "outcome", "codes", "plain_outcome", "plain_codes")
    wrapped = source.replace('def build_explorer(): return make(Reply())',
        'def starts(): return DeskState()\ndef build_explorer(): return Explorer(Workflow((Receive(),Reply())), tuple(starts() for _ in range(1)), ("x",))')
    assert model_port(wrapped).state == port.state
    projected = source.replace('def build_explorer(): return make(Reply())',
        'def project_parent_state(p): return DeskState(p.request)\ndef build_explorer(): return Explorer(Workflow((Receive(),Reply())), reachable_states(parent.build_explorer(), project_parent_state), ("x",))')
    assert model_port(projected).state == port.state and model_port(projected).reads_parent == ("request",)
    assert model_port(projected.replace('DeskState(p.request)', 'convert(p)')).reads_parent == ("?",)
    assert upward(model_port(source + '\nOUTPUTS={"reply":("b","a")}')) == upward(model_port(source + '\nOUTPUTS={"reply":("a","b")}'))
    # Compare every real self-model's inferred state with its actual first state.
    from flowguard.map.mapfile import model_registry, read_model_contract, resolve_model_path
    from flowguard.map.proof import _load, model_namespace
    from flowguard.map.targetfile import load_target, build_target_view
    root = Path(__file__).parents[1]
    current = load_map(root)
    target = load_target(root)
    view = build_target_view(root, current, target) if target is not None else None
    mapping = view.data if view else current
    with model_namespace(view):
        for entry in model_registry(root, mapping, view=view).entries:
            path = root / entry.path
            contract = read_model_contract(resolve_model_path(root, entry.path, view=view))
            explorer = _load(root, path, view=view).build_explorer()
            first = next(iter(explorer.initial_states), None)
            actual = tuple(f.name for f in fields(first)) if is_dataclass(first) else None
            if entry.id == "job_matching_example":
                # Its INITIAL_STATE and workflow are imported from the teaching example;
                # text-only port extraction intentionally cannot inspect another file.
                assert contract["port"].state is None
            else:
                assert contract["port"].state == actual, (entry.id, contract["port"].state, actual)
    import pytest
    from flowguard.map.mapfile import read_model_contract
    invalid = ('OUTPUTS=None', 'OUTPUTS={"answer":()}', 'OUTPUTS={"answer":["lent"]}',
               'HANDOFF={"lending":None}', 'HANDOFF={"lending":{"answer":("answer",{"lent":[]})}}',
               'READS_PARENT=["request"]', 'KEEPS="reply"', 'DISPATCH={}',
               'DISPATCH={"mode":{"x":42}}', 'DISPATCH={"mode":{"x":"a"},"other":{"y":"b"}}')
    path = tmp_path / "invalid_port.py"
    for literal in invalid:
        path.write_text(source + "\n" + literal)
        with pytest.raises(ValueError):
            read_model_contract(path)
    path.unlink()
    # Shorthand is resolved from each producer's current source, not saved in the consumer.
    assert not errors(tmp_path, data, inv)
    rewrite(tmp_path, "lending", '("lent","refused")}', '("lent","refused","waitlisted")}')
    assert "handoff_output_unhandled" not in errors(tmp_path, data, build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False))


def test_handoff_edit_is_not_an_upward_change(tmp_path):
    from dataclasses import fields, is_dataclass, replace
    from pathlib import Path
    import json
    import runpy
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import load_map
    from flowguard.map.port import model_port, port_findings, upward
    from flowguard.map.tree import build_tree
    from _fg_helpers import flowguard_port421_helpers as helpers, flowguard_port421_project as project, flowguard_port421_probe as probe, flowguard_port421_errors as errors, flowguard_port421_rewrite as rewrite, flowguard_port421_dispatch_project as dispatch_project, flowguard_port421_escalation_model as escalation_model, flowguard_port421__select_ports as _select_ports, flowguard_port421_fields as fields, flowguard_port421_is_dataclass as is_dataclass, flowguard_port421_replace as replace, flowguard_port421_Path as Path, flowguard_port421_json as json, flowguard_port421_runpy as runpy, flowguard_port421_DEFAULT_IGNORE as DEFAULT_IGNORE, flowguard_port421_build_inventory as build_inventory, flowguard_port421_load_map as load_map, flowguard_port421_model_port as model_port, flowguard_port421_port_findings as port_findings, flowguard_port421_upward as upward, flowguard_port421_build_tree as build_tree
    data, inv = project(tmp_path)
    source = (tmp_path/'.flowguard/models/desk.py').read_text()
    old = model_port(source)
    new = replace(old, handoff={'lending': {'answer': ('answer', {'lent':'lent','refused':None})}})
    from flowguard.map.port import port_selection
    tree = build_tree(tmp_path,data,inv)
    ports = {key: node.contract['port'] for key,node in tree.nodes.items()}
    ports['desk'] = new
    selected, text, _ = port_selection('desk',old,new,tree,ports)
    assert not selected and text.startswith('port: desk unchanged (this model only); handoff lending')


def test_reordered_outputs_are_unchanged(tmp_path):
    from dataclasses import fields, is_dataclass, replace
    from pathlib import Path
    import json
    import runpy
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import load_map
    from flowguard.map.port import model_port, port_findings, upward
    from flowguard.map.tree import build_tree
    from _fg_helpers import flowguard_port421_helpers as helpers, flowguard_port421_project as project, flowguard_port421_probe as probe, flowguard_port421_errors as errors, flowguard_port421_rewrite as rewrite, flowguard_port421_dispatch_project as dispatch_project, flowguard_port421_escalation_model as escalation_model, flowguard_port421__select_ports as _select_ports, flowguard_port421_fields as fields, flowguard_port421_is_dataclass as is_dataclass, flowguard_port421_replace as replace, flowguard_port421_Path as Path, flowguard_port421_json as json, flowguard_port421_runpy as runpy, flowguard_port421_DEFAULT_IGNORE as DEFAULT_IGNORE, flowguard_port421_build_inventory as build_inventory, flowguard_port421_load_map as load_map, flowguard_port421_model_port as model_port, flowguard_port421_port_findings as port_findings, flowguard_port421_upward as upward, flowguard_port421_build_tree as build_tree
    source = 'OUTPUTS={"answer":("lent","refused")}\n'
    selected,text,_ = _select_ports(tmp_path,'lending',model_port(source),model_port(source.replace('"lent","refused"','"refused","lent"')))
    assert not selected and text == 'port: lending unchanged (this model only)'


def test_missing_outputs_is_uncertain(tmp_path):
    from dataclasses import fields, is_dataclass, replace
    from pathlib import Path
    import json
    import runpy
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import load_map
    from flowguard.map.port import model_port, port_findings, upward
    from flowguard.map.tree import build_tree
    from _fg_helpers import flowguard_port421_helpers as helpers, flowguard_port421_project as project, flowguard_port421_probe as probe, flowguard_port421_errors as errors, flowguard_port421_rewrite as rewrite, flowguard_port421_dispatch_project as dispatch_project, flowguard_port421_escalation_model as escalation_model, flowguard_port421__select_ports as _select_ports, flowguard_port421_fields as fields, flowguard_port421_is_dataclass as is_dataclass, flowguard_port421_replace as replace, flowguard_port421_Path as Path, flowguard_port421_json as json, flowguard_port421_runpy as runpy, flowguard_port421_DEFAULT_IGNORE as DEFAULT_IGNORE, flowguard_port421_build_inventory as build_inventory, flowguard_port421_load_map as load_map, flowguard_port421_model_port as model_port, flowguard_port421_port_findings as port_findings, flowguard_port421_upward as upward, flowguard_port421_build_tree as build_tree
    selected,text,_ = _select_ports(tmp_path,'lending',model_port('OUTPUTS={}'),model_port(''))
    assert selected == [('desk','parent')]
    assert text == 'UNCERTAIN port: lending declares no OUTPUTS; parent desk selected'


def test_escalation_set_orders_parent_handoff_child_input():
    from dataclasses import fields, is_dataclass, replace
    from pathlib import Path
    import json
    import runpy
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import load_map
    from flowguard.map.port import model_port, port_findings, upward
    from flowguard.map.tree import build_tree
    from _fg_helpers import flowguard_port421_helpers as helpers, flowguard_port421_project as project, flowguard_port421_probe as probe, flowguard_port421_errors as errors, flowguard_port421_rewrite as rewrite, flowguard_port421_dispatch_project as dispatch_project, flowguard_port421_escalation_model as escalation_model, flowguard_port421__select_ports as _select_ports, flowguard_port421_fields as fields, flowguard_port421_is_dataclass as is_dataclass, flowguard_port421_replace as replace, flowguard_port421_Path as Path, flowguard_port421_json as json, flowguard_port421_runpy as runpy, flowguard_port421_DEFAULT_IGNORE as DEFAULT_IGNORE, flowguard_port421_build_inventory as build_inventory, flowguard_port421_load_map as load_map, flowguard_port421_model_port as model_port, flowguard_port421_port_findings as port_findings, flowguard_port421_upward as upward, flowguard_port421_build_tree as build_tree
    from flowguard.map.port import Port, escalation_set
    from flowguard.map.tree import ModelNode, ModelTree
    nodes={mid:ModelNode(mid,mid+'.py','contract',parent,kind,'PARENT') for mid,parent,kind in (('m','p','model'),('p','system','component'),('k','system','component'),('c','m','model'))}
    ports={'m':Port(outputs={'x':('v',)}),'p':Port(),'k':Port(handoff={'m':{'x':'seen'}}),'c':Port(reads_parent=('f',))}
    assert escalation_set('m',ModelTree(nodes,{}),ports)==[('p','parent'),('k','HANDOFF'),('c','child input')]


def test_escalation_state_and_uncertainty_are_conservative():
    from dataclasses import fields, is_dataclass, replace
    from pathlib import Path
    import json
    import runpy
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import load_map
    from flowguard.map.port import model_port, port_findings, upward
    from flowguard.map.tree import build_tree
    from _fg_helpers import flowguard_port421_helpers as helpers, flowguard_port421_project as project, flowguard_port421_probe as probe, flowguard_port421_errors as errors, flowguard_port421_rewrite as rewrite, flowguard_port421_dispatch_project as dispatch_project, flowguard_port421_escalation_model as escalation_model, flowguard_port421__select_ports as _select_ports, flowguard_port421_fields as fields, flowguard_port421_is_dataclass as is_dataclass, flowguard_port421_replace as replace, flowguard_port421_Path as Path, flowguard_port421_json as json, flowguard_port421_runpy as runpy, flowguard_port421_DEFAULT_IGNORE as DEFAULT_IGNORE, flowguard_port421_build_inventory as build_inventory, flowguard_port421_load_map as load_map, flowguard_port421_model_port as model_port, flowguard_port421_port_findings as port_findings, flowguard_port421_upward as upward, flowguard_port421_build_tree as build_tree
    from flowguard.map.port import Port, port_delta, port_selection
    from flowguard.map.tree import ModelNode, ModelTree
    nodes={mid:ModelNode(mid,mid+'.py','contract',parent,kind,'PARENT') for mid,parent,kind in (('m','p','model'),('p','system','component'),('k','system','component'),('c','m','model'))}
    tree=ModelTree(nodes,{})
    old=Port(state=('f',),outputs={})
    new=Port(state=('f','g'),outputs={'x':('v',)})
    ports={'m':new,'p':Port(),'k':Port(handoff={'m':{'x':'seen'}}),'c':Port(reads_parent=('f',))}
    chosen,text,_=port_selection('m',old,new,tree,ports)
    assert chosen==[('p','parent'),('k','HANDOFF'),('c','child input')]
    assert text=='port changed: m out +v state +g -> verify p (parent), k (HANDOFF), c (child input)'
    assert not port_delta(Port(),Port(outputs={}))['out']
    assert port_delta(Port(),new)['out']
    unknown=replace(new,state=None,outputs={})
    chosen,text,_=port_selection('m',old,unknown,tree,{**ports,'m':unknown})
    assert chosen==[('c','child input')]
    assert text=='UNCERTAIN port: m state unreadable; children reading it c selected'
    chosen,text,_=port_selection('m',None,new,tree,ports,unavailable=True)
    assert chosen==[('p','parent')]
    assert text=='UNCERTAIN port: no git base for m; target check compared its port before promote; parent p selected'


def test_digest_captures_module_assignments_and_guarded_definitions_without_bodies(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_views421_pytest as pytest, map_views421_os as os, map_views421_json as json, map_views421_Path as Path
    from flowguard.map.views import file_outline
    (tmp_path / 'api.py').write_text('''VERSION = 3
if VERSION:
    def guarded(value):
        secret_body = value + 9
        return secret_body
try:
    class Service:
        def run(self, value):
            return value
except ImportError:
    def fallback(value):
        return value
''', encoding='utf-8')
    output = '\n'.join(file_outline(tmp_path, 'api.py'))
    assert 'VERSION = 3' in output
    assert 'guarded(value)' in output and 'class Service' in output and 'fallback(value)' in output
    assert 'secret_body' not in output and 'return value' not in output


def test_target_show_keeps_current_character_budgets_without_running_checks(tmp_path, monkeypatch):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_views421_pytest as pytest, map_views421_os as os, map_views421_json as json, map_views421_Path as Path
    from flowguard.map.views import render_show
    from _fg_helpers import view__inventory as _inventory, view__component as _component
    from flowguard.map import check, lint, proof, target
    from flowguard.map.targetfile import Target

    data = dict(project='budget-demo', layers=['domain'], components=[
        dict(_component('alpha', summary='Original purpose', responsibilities=['serve alpha']), layer='domain'),
        dict(_component('beta', summary='Unchanged purpose', responsibilities=['serve beta']), layer='domain')],
        flows=[dict(id='request', summary='request to alpha', steps=['alpha:run'])])
    replacement = dict(data['components'][0], summary='A changed purpose ' + 'x' * 12000)
    replacement.pop('status')
    replacement.pop('fingerprint')
    draft = Target('explain alpha', dict(schema='flowguard.target.v1', goal='explain alpha',
        components=[replacement], flows=[], remove=[]), {}, {'component': set(), 'flow': set(), 'model': set()})

    def forbidden(*args, **kwargs):
        raise AssertionError('a target read must not execute models or checks')

    with monkeypatch.context() as scoped:
        for name in ('run_models', 'run_model', 'run_model_in_process', '_load'):
            scoped.setattr(proof, name, forbidden)
        scoped.setattr(check, 'run_check', forbidden)
        scoped.setattr(lint, 'run_lint', forbidden)
        scoped.setattr(target, 'check_target', forbidden)
        full = render_show(tmp_path, data, _inventory(tmp_path), component=None, detail=False,
                           budget=8000, target=draft)
        assert 'target:' in full
        for budget in (0, 80, 260):
            bounded = render_show(tmp_path, data, _inventory(tmp_path), component=None, detail=False,
                                  budget=budget, target=draft)
            assert len(bounded) <= budget
            if budget == 260:
                assert 'truncated' in bounded


def test_target_snapshots_keep_their_own_inventory_classification(tmp_path, monkeypatch):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_views421_pytest as pytest, map_views421_os as os, map_views421_json as json, map_views421_Path as Path
    from flowguard.map.views import render_show
    from _fg_helpers import view__component as _component
    from flowguard.map import check, lint, proof, target
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import component_graph
    from flowguard.map.targetfile import Target

    (tmp_path / 'test_reclassified.py').write_text('def test_live():\n    raise AssertionError("read executed a test")\n')
    (tmp_path / 'resource.txt').write_text('exact code resource\n')
    component = dict(_component('alpha', summary='Own an explicit code resource', responsibilities=['serve alpha']),
                     files=['test_reclassified.py', 'resource.txt'], tests=['test_reclassified.py'])
    data = dict(project='classification', components=[component], flows=[])
    replacement = {key: value for key, value in component.items() if key not in {'status', 'fingerprint'}}
    replacement['files'] = []
    draft = Target('use the Python file as a test', dict(schema='flowguard.target.v1', goal='use the Python file as a test',
        components=[replacement], flows=[], remove=[]), {}, {'component': set(), 'flow': set(), 'model': set()})
    inventory = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    component_graph(data, inventory)
    assert len(inventory.source) == 2 and not inventory.tests

    def forbidden(*args, **kwargs):
        raise AssertionError('a target read must not execute models or checks')

    with monkeypatch.context() as scoped:
        for name in ('run_models', 'run_model', 'run_model_in_process', '_load'):
            scoped.setattr(proof, name, forbidden)
        scoped.setattr(check, 'run_check', forbidden)
        scoped.setattr(lint, 'run_lint', forbidden)
        scoped.setattr(target, 'check_target', forbidden)
        detail = render_show(tmp_path, data, inventory, component='alpha', detail=True, budget=8000, target=draft)
        assert 'tests: 1 functions here and below (bound 0, unbound 1); files: test_reclassified.py' in detail, detail
        assert 'was: 0 functions here and below (bound 0, unbound 0); files: -' in detail, detail
        system = render_show(tmp_path, data, inventory, component='system', detail=True, budget=8000, target=draft)
        assert 'code: 1 components, 1 source files' in system, system
        assert 'was: 1 components, 2 source files' in system, system
        assert 'tests: 1 files: test_reclassified.py; 1 functions, 0 bound' in system, system
        assert 'was: 0 files: -; 0 functions, 0 bound' in system, system
        assert '(+0 ~1 -0 nodes)' in system, system
    assert len(inventory.source) == 1 and inventory.tests == ['test_reclassified.py']


def test_static_facets_match_flowguard_self_models():
    """Every FlowGuard model reads statically the same rule and known-bad names it builds at run time."""
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_views421_pytest as pytest, map_views421_os as os, map_views421_json as json, map_views421_Path as Path
    from pathlib import Path
    import importlib.util
    import sys
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.facets import model_facets
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import load_map
    from flowguard.map.tree import build_tree

    root = Path(__file__).resolve().parents[1]
    data = load_map(root)
    tree = build_tree(root, data, build_inventory(root, DEFAULT_IGNORE, with_bodies=False, write_cache=False))
    models = str(root / ".flowguard/models")
    added = models not in sys.path
    if added:
        sys.path.append(models)
    try:
        checked = 0
        for mid, node in sorted(tree.nodes.items()):
            if not node.path.startswith(".flowguard/models/"):
                continue
            facets = model_facets(root, node)
            name = f"_flowguard_model_{Path(node.path).stem}"
            spec = importlib.util.spec_from_file_location(name, root / node.path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            assert facets.rules_source == "explorer", mid
            assert list(facets.rules) == sorted(rule.name for rule in module.build_explorer().invariants), mid
            assert list(facets.known_bad) == sorted(module.broken_variants()), mid
            checked += 1
        assert checked >= 13
    finally:
        if added:
            sys.path.remove(models)


def test_digest_lists_overloads_once(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_views421_pytest as pytest, map_views421_os as os, map_views421_json as json, map_views421_Path as Path
    from flowguard.map.views import file_outline
    from flowguard.map.views import file_outline

    (tmp_path / 'serializer.py').write_text(
        'from typing import overload\nimport typing\n\n\nclass Serializer:\n'
        '    @overload\n    def __init__(self, key: str) -> None: ...\n'
        '    @typing.overload\n    def __init__(self, key: bytes) -> None: ...\n'
        '    def __init__(self, key):\n        self.key = key\n\n\n'
        '@overload\ndef dumps(value: int) -> str: ...\n@overload\ndef dumps(value: str) -> str: ...\n'
        'def dumps(value):\n    return str(value)\n')
    outline = file_outline(tmp_path, 'serializer.py')
    inits = [line for line in outline if '.__init__(' in line]
    dumps = [line for line in outline if 'def dumps(' in line]
    assert len(inits) == 1 and inits[0].endswith(' (+2 overloads)'), outline
    assert len(dumps) == 1 and dumps[0].endswith(' (+2 overloads)'), outline


def test_locate_unowned_function_says_no_model_owns(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_views421_pytest as pytest, map_views421_os as os, map_views421_json as json, map_views421_Path as Path
    from _fg_helpers import view_locate_fixture as locate_fixture
    helper=locate_fixture();helper['fixture'](tmp_path)
    code,text=helper['observe'](tmp_path,'unowned')
    assert code==0 and text.splitlines()==[
        'no model owns api.py:unowned (component app); reached by: none',
        'next: add the rule to a model of app; a separate aspect gets its own model there (references/routes.md#New function)']


def test_locate_test_file_counts_per_model(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_views421_pytest as pytest, map_views421_os as os, map_views421_json as json, map_views421_Path as Path
    from _fg_helpers import view_locate_fixture as locate_fixture
    helper=locate_fixture();helper['fixture'](tmp_path)
    code,text=helper['observe'](tmp_path,'file')
    assert code==0 and text.splitlines()[1]=='bound: owner 1; unbound 2'


class DiscoveryBoundaryTests(unittest.TestCase):
    def test_scan_max_components_and_import_test_guess_preserve_unique_ownership(self) -> None:
        import json
        import shutil
        import subprocess
        import sys
        import tempfile
        import unittest
        from pathlib import Path
        import pytest
        from flowguard.map.discover import component_summary, console_scripts, discover, discover_inventory, file_facts
        from flowguard.map.common import DEFAULT_IGNORE
        from flowguard.map.inventory import build_inventory
        from flowguard.map.lint import entrypoint_coverage_findings, run_lint, scoped_architecture_findings
        from flowguard.map.scan import guess_tests, new_map, propose_components
        from _fg_helpers import flowguard_map_discover421_ROOT as ROOT, flowguard_map_discover421_APP as APP, flowguard_map_discover421_STORE as STORE, flowguard_map_discover421_CLI as CLI, flowguard_map_discover421_write_project as write_project, flowguard_map_discover421_map_cli as map_cli, flowguard_map_discover421__INJECTED_STORE as _INJECTED_STORE, flowguard_map_discover421__INJECTED_SERVICE as _INJECTED_SERVICE, flowguard_map_discover421__INJECTED_CLI as _INJECTED_CLI, flowguard_map_discover421__injected_project as _injected_project, flowguard_map_discover421__resolution_case as _resolution_case, flowguard_map_discover421_literal_fixture as literal_fixture, flowguard_map_discover421_json as json, flowguard_map_discover421_shutil as shutil, flowguard_map_discover421_subprocess as subprocess, flowguard_map_discover421_sys as sys, flowguard_map_discover421_tempfile as tempfile, flowguard_map_discover421_unittest as unittest, flowguard_map_discover421_Path as Path, flowguard_map_discover421_pytest as pytest, flowguard_map_discover421_component_summary as component_summary, flowguard_map_discover421_console_scripts as console_scripts, flowguard_map_discover421_discover as discover, flowguard_map_discover421_discover_inventory as discover_inventory, flowguard_map_discover421_file_facts as file_facts, flowguard_map_discover421_DEFAULT_IGNORE as DEFAULT_IGNORE, flowguard_map_discover421_build_inventory as build_inventory, flowguard_map_discover421_entrypoint_coverage_findings as entrypoint_coverage_findings, flowguard_map_discover421_run_lint as run_lint, flowguard_map_discover421_scoped_architecture_findings as scoped_architecture_findings, flowguard_map_discover421_guess_tests as guess_tests, flowguard_map_discover421_new_map as new_map, flowguard_map_discover421_propose_components as propose_components
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for number in range(30):
                target = root / "pkg" / f"part{number}"
                target.mkdir(parents=True)
                for child in range(10):
                    (target / f"mod{child}.py").write_text(f"def public{child}(): return {child}\n", encoding="utf-8")
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_api.py").write_text("from pkg.part0 import mod0\ndef test_api(): assert mod0.public0() == 0\n", encoding="utf-8")
            (tests / "_util.py").write_text("from pkg.part0 import mod0\n", encoding="utf-8")
            inv = build_inventory(root, DEFAULT_IGNORE)
            proposals = propose_components(inv, max_components=5)
            self.assertLessEqual(len(proposals), 5)
            from flowguard.map.mapfile import component_files
            owned = [path for component in proposals for path in component_files(component, inv)]
            self.assertEqual(set(inv.source) - set(inv.tests), set(owned))
            self.assertEqual(len(owned), len(set(owned)))
            self.assertTrue(all(len(component["_hint"]["public_symbols_sample"]) <= 8 for component in proposals))
            self.assertEqual(["tests/test_api.py"], guess_tests(["pkg/part0/mod0.py"], inv.tests, inv))
            with self.assertRaisesRegex(ValueError, "at least 1"):
                propose_components(inv, max_components=0)
