"""Real finite parent/child ports: source reading, writes, receipts and dispatch."""
from dataclasses import fields, is_dataclass, replace
from pathlib import Path
import json
import runpy

from flowguard.map.common import DEFAULT_IGNORE
from flowguard.map.inventory import build_inventory
from flowguard.map.mapfile import load_map
from flowguard.map.port import model_port, port_findings, upward
from flowguard.map.tree import build_tree


def helpers():
    directory = Path(__file__).parents[1] / ".flowguard/models"
    path = directory / "_target_fixture.py"
    if not path.exists():
        path = directory.parent / "target/models/_target_fixture.py"
    return runpy.run_path(str(path))


def project(root, case="valid"):
    h = helpers()
    data = h["make_port_project"](root, case)
    return data, build_inventory(root, DEFAULT_IGNORE, write_cache=False)


def probe(root, model="desk"):
    return helpers()["probe_port_model"](root, model)


def errors(root, data, inv):
    return {finding.code for finding in build_tree(root, data, inv).findings if finding.level == "error"}


def rewrite(root, model, old, new):
    path = root / ".flowguard/models" / (model + ".py")
    source = path.read_text()
    assert old in source
    path.write_text(source.replace(old, new, 1))


def test_model_port_reads_state_blocks_and_literals(tmp_path):
    data, inv = project(tmp_path)
    source = (tmp_path / ".flowguard/models/desk.py").read_text()
    port = model_port(source)
    assert port.state == ("request", "answer", "reply")
    assert set(port.blocks) == {"Receive", "Reply"} and not port.approximate
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


def test_undeclared_write_and_output_checks(tmp_path):
    for case, model, code, warning in (("undeclared_write", "desk", "undeclared_write", False),
            ("undeclared_output", "lending", "output_undeclared", False),
            ("unreached_output", "lending", "output_unreached", True)):
        root = tmp_path / case
        project(root, case)
        result = probe(root, model)
        assert result.status == ("pass" if warning else "fail"), result
        assert any(code in line for line in (result.warnings if warning else result.problems)), result
    from flowguard.map.port import changed_fields
    assert changed_fields(0, 1) == ()
    assert changed_fields({"a": 1}, {"a": 1, "b": []}) == ("b",)
    root = tmp_path / "no_declared_writes"
    project(root, "undeclared_write")
    rewrite(root, "desk", '    writes=("request",)\n', '')
    # A block without writes has no C1 promise; its parent still gets static S0c.
    assert not any("undeclared_write:" in line for line in probe(root).problems)


def test_handoff_value_must_be_received_as_an_event(tmp_path):
    root = tmp_path / "good"
    project(root)
    assert probe(root).status == "pass"
    for case in ("missing_receipt", "wrong_receiving_field"):
        root = tmp_path / case
        project(root, case)
        result = probe(root)
        assert result.status == "fail" and any("handoff_output_unhandled:" in p for p in result.problems), result
    # A new value's presence in a different invocation cannot supply its missing renamed receipt.
    root = tmp_path / "renamed"
    project(root)
    rewrite(root, "lending", '("lent","refused")}', '("lent","refused","waitlisted")}')
    rewrite(root, "desk", '"answer":"answer"', '"answer":("answer",{"lent":"lent","refused":"refused","waitlisted":"refused"})')
    result = probe(root)
    assert any("waitlisted" in p and "handoff_output_unhandled" in p for p in result.problems), result


def test_keeps_classes_and_parent_outputs(tmp_path):
    from flowguard.map.port import keeps_classes
    root = tmp_path / "good"
    project(root)
    rewrite(root, "desk", "max_sequence_length=1", "max_sequence_length=3")
    result = probe(root)
    assert result.status == "pass", result
    kinds = keeps_classes("desk")
    assert kinds["request"] == "input" and kinds["reply"] == "aggregate", kinds
    for case, code in (("domain_keeps", "keeps_not_orchestration"), ("parent_output", "parent_output_not_from_child")):
        root = tmp_path / case
        project(root, case)
        result = probe(root)
        assert result.status == "fail" and any(code in p for p in result.problems), result


def test_each_static_edge_mistake_has_its_code(tmp_path):
    for case, code in (("drops_child_value", "handoff_drops_child_value"),
            ("missing_parent_input", "child_input_unprovided"), ("uncovered_parent_field", "parent_field_uncovered"),
            ("overlapping_receipts", "sibling_outputs_overlap"), ("consumer_receipts", "sibling_outputs_overlap"), ("no_child_output", "child_unconnected")):
        root = tmp_path / case
        data, inv = project(root, case)
        assert errors(root, data, inv) == {code}
    mutations = (
        ("unreadable", "desk", '@dataclass(frozen=True)', '', {"port_unreadable"}),
        ("writes", "desk", '    writes=("request","answer")\n', '', {"parent_writes_undeclared"}),
        ("unhandled", "lending", 'OUTPUTS = {"answer":("lent","refused")}',
         'OUTPUTS = {"answer":("lent","refused"),"request":("lend_request",)}', {"handoff_output_unhandled"}),
        ("unknown_into", "desk", '"answer":"answer"', '"answer":"ghost"', {"handoff_into_unknown", "parent_field_uncovered"}),
    )
    for case, model, old, new, codes in mutations:
        root = tmp_path / case
        data, inv = project(root)
        rewrite(root, model, old, new)
        assert errors(root, data, build_inventory(root, DEFAULT_IGNORE, write_cache=False)) == codes
    root = tmp_path / "kit_parent"
    data, inv = project(root)
    (root / ".flowguard/models/desk.py").write_text('from flowguard.kit import feature_explorer\nMODEL_ID="desk"\nPARENT="cli"\nIMPLEMENTED_BY={"Serve":"shelf/cli.py:main"}\nHANDOFF={"lending":{"answer":"outcome"}}\nKEEPS=("features","codes","plain_outcome","plain_codes")\ndef build_explorer(): return feature_explorer(())\n')
    rewrite(root, "lending", 'READS_PARENT = ("request",)', 'READS_PARENT = ()')
    assert errors(root, data, build_inventory(root, DEFAULT_IGNORE, write_cache=False)) == {"kit_model_parent"}
    root = tmp_path / "output_not_state"
    data, inv = project(root)
    rewrite(root, "lending", 'OUTPUTS = {"answer":("lent","refused")}', 'OUTPUTS = {"answer":("lent","refused"),"ghost":("boo",)}')
    rewrite(root, "desk", '"answer":"answer"', '"answer":"answer","ghost":"extra"')
    rewrite(root, "desk", '    reply: str = ""', '    reply: str = ""\n    extra: str = ""')
    assert errors(root, data, build_inventory(root, DEFAULT_IGNORE, write_cache=False)) == {"outputs_not_state"}
    root = tmp_path / "duplicate"
    data, inv = project(root)
    rewrite(root, "lending", 'PARENT = "desk"', 'PARENT = "loans"')
    rewrite(root, "lending", '"shelf/loans.py:borrow"', '"shelf/cli.py:main"')
    rewrite(root, "lending", 'COMPONENTS = ["loans"]', 'COMPONENTS = ["loans","cli"]')
    assert errors(root, data, build_inventory(root, DEFAULT_IGNORE, write_cache=False)) == {"duplicate_child_owner"}
    # Cousins under sibling components and component/descendant placements also collide.
    data["components"] += [dict(id=cid, parent="cli", layer="interface", summary=cid, responsibilities=[], files=[], tests=[], models=[], depends_on=[], status="draft") for cid in ("left","right")]
    (root / ".flowguard/map.json").write_text(json.dumps(data))
    path = root / ".flowguard/models/desk.py"
    path.write_text(path.read_text()+'\nCOMPONENTS=["cli"]\n')
    rewrite(root, "desk", 'PARENT = "cli"', 'PARENT = "left"')
    rewrite(root, "lending", 'PARENT = "loans"', 'PARENT = "right"')
    assert errors(root, data, build_inventory(root, DEFAULT_IGNORE, write_cache=False)) == {"duplicate_child_owner"}
    rewrite(root, "desk", 'PARENT = "left"', 'PARENT = "cli"')
    rewrite(root, "lending", 'PARENT = "right"', 'PARENT = "left"')
    assert errors(root, data, build_inventory(root, DEFAULT_IGNORE, write_cache=False)) == {"duplicate_child_owner"}
    rewrite(root, "lending", 'PARENT = "left"', 'PARENT = "desk"')
    assert not errors(root, data, build_inventory(root, DEFAULT_IGNORE, write_cache=False))
    # A read-only duplicate never acquires ownership.
    rewrite(root, "lending", '"shelf/cli.py:main"', '"shelf/loans.py:borrow"')
    path = root / ".flowguard/models/lending.py"
    path.write_text(path.read_text().replace('PARENT = "desk"', 'PARENT = "loans"')+'\nUSES={"Serve":"shelf/cli.py:main"}\n')
    assert not errors(root, data, build_inventory(root, DEFAULT_IGNORE, write_cache=False))


def test_clearing_an_into_field_is_not_a_receipt(tmp_path):
    root = tmp_path
    project(root, "domain_keeps")
    rewrite(root, "desk", 'writes=("extra",)', 'writes=("extra","answer")')
    rewrite(root, "desk", 'extra=not state.extra', 'extra=not state.extra,answer=""')
    result = probe(root)
    assert result.status == "fail" and any("keeps_not_orchestration" in p for p in result.problems), result


def dispatch_project(root, kind="valid"):
    data, inv = project(root)
    models = root / ".flowguard/models"
    (models / "desk.py").unlink()
    (models / "lending.py").unlink()
    (root / "shelf/loans.py").write_text('def borrow(value): return "left"\ndef second(value): return "right"\n')
    (root / "shelf/cli.py").write_text('from .loans import borrow,second\ndef main(mode): return borrow(mode) if mode=="x" else second(mode)\n')
    head = '''from dataclasses import dataclass,replace
from pathlib import Path
from flowguard import FunctionResult,Invariant,Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport,Fact,load_anchor
'''
    cmd = head + '''MODEL_ID="cmd"
PARENT="cli"
IMPLEMENTED_BY={"Serve":"shelf/cli.py:main"}
HANDOFF={"a":{"answer":"a"},"b":{"answer":"b"}}
KEEPS=("mode",)
DISPATCH={"mode":{"x":"a","y":"b"}}
@dataclass(frozen=True)
class Command:
    mode:str=""
    a:str=""
    b:str=""
class Choose:
    name="Choose"
    reads=()
    writes=("mode","a","b")
    def __init__(self,bad=False): self.bad=bad
    def apply(self,event,state):
        mode=event
        a="left" if event=="x" else ""
        b="right" if event=="y" else ""
        if KIND=="unknown" and event=="x": mode="z"
        if KIND in ("wrong_branch","no_dispatch"): a,b=b and "left",a and "right"
        if KIND=="two_branches" and event=="x": a,b="left","right"
        if self.bad: a,b="hidden","hidden"
        result=Command(mode,a,b)
        return (FunctionResult((a,b),result,label="selected"),)
RULE=Invariant("visible","branch results stay visible",lambda s,t:s.a!="hidden" and s.b!="hidden")
def make(bad=False): return Explorer(Workflow((Choose(bad),)),(Command(),),("x","y"),invariants=(RULE,),max_sequence_length=1,progress_steps=0)
def build_explorer(): return make()
def broken_variants(): return {"hidden":make(True)}
def conformance():
    main=load_anchor(IMPLEMENTED_BY["Serve"],root=Path.cwd())
    return CodeFactsReport((Fact("x",main("x")=="left"),Fact("y",main("y")=="right")))
'''
    cmd += '\nKIND='+repr(kind)+'\n'
    if kind == "no_dispatch":
        cmd = cmd.replace('DISPATCH={"mode":{"x":"a","y":"b"}}', '')
    if kind == "unknown_selector":
        cmd = cmd.replace('DISPATCH={"mode"', 'DISPATCH={"ghost"')
    (models / "cmd.py").write_text(cmd)
    for name, symbol, value in (("a", "borrow", "left"), ("b", "second", "right")):
        source = head + f'''MODEL_ID={name!r}
PARENT="cmd"
COMPONENTS=["loans"]
IMPLEMENTED_BY={{"Result":"shelf/loans.py:{symbol}"}}
OUTPUTS={{"answer":({value!r},)}}
@dataclass(frozen=True)
class ResultState:
    answer:str=""
class Produce:
    name="Produce"
    writes=("answer",)
    def __init__(self,bad=False): self.bad=bad
    def apply(self,event,state): return (FunctionResult(event,ResultState("bad" if self.bad else event)),)
RULE=Invariant("result","the result is retained",lambda s,t:s.answer in ("",{value!r}))
def make(bad=False): return Explorer(Workflow((Produce(bad),)),(ResultState(),),({value!r},),invariants=(RULE,),max_sequence_length=1,progress_steps=0)
def build_explorer(): return make()
def broken_variants(): return {{"bad":make(True)}}
def conformance(): return CodeFactsReport((Fact("native",load_anchor(IMPLEMENTED_BY["Result"],root=Path.cwd())("x")=={value!r}),))
'''
        if name == "a" and kind == "nonchild":
            source = source.replace('PARENT="cmd"', 'PARENT="loans"')
        (models / (name+".py")).write_text(source)
    return data, build_inventory(root, DEFAULT_IGNORE, write_cache=False)


def test_dispatch_parent_checks(tmp_path):
    for kind in ("valid", "no_dispatch"):
        root = tmp_path / kind
        data, inv = dispatch_project(root, kind)
        result = probe(root, "cmd")
        assert not errors(root, data, inv), errors(root, data, inv)
        assert result.status == "pass", result
    for kind, code in (("unknown", "dispatch_without_child"), ("wrong_branch", "dispatch_branch_not_received"),
                       ("two_branches", "dispatch_two_branches")):
        root = tmp_path / kind
        dispatch_project(root, kind)
        result = probe(root, "cmd")
        assert result.status == "fail" and any(code in p for p in result.problems), result
    for kind, code in (("nonchild", "dispatch_without_child"), ("unknown_selector", "dispatch_field_unknown")):
        root = tmp_path / kind
        data, inv = dispatch_project(root, kind)
        assert errors(root, data, inv) == {code}

def escalation_model():
    import sys
    root = Path(__file__).parents[1] / '.flowguard'
    current, target = root/'models', root/'target/models'
    source = target/'port_escalation.py' if (target/'port_escalation.py').exists() else current/'port_escalation.py'
    sys.path.insert(0, str(current))
    try:
        return runpy.run_path(str(source))
    finally:
        sys.path.pop(0)


def test_rule_edit_selects_the_child_only(tmp_path):
    impact, text = escalation_model()['native_case'](tmp_path, 'rule')
    assert impact.model_ids == ['lending']
    assert 'port: lending unchanged (this model only)' in text


def test_output_change_selects_parent_not_grandparent(tmp_path):
    impact, text = escalation_model()['native_case'](tmp_path, 'output')
    assert impact.model_ids == ['consumer', 'desk', 'lending']
    assert 'out +waitlisted -> verify desk (parent), consumer (HANDOFF)' in text
    assert 'grand' not in impact.model_ids


def test_reads_parent_change_selects_parent(tmp_path):
    impact, text = escalation_model()['native_case'](tmp_path, 'reads')
    assert impact.model_ids == ['desk', 'lending']
    assert 'reads +answer -> verify desk (parent)' in text


def _select_ports(tmp_path, mid, old, new):
    from flowguard.map.port import model_port, port_selection
    data, inv = project(tmp_path)
    tree = build_tree(tmp_path, data, inv)
    ports = {key: node.contract['port'] for key,node in tree.nodes.items()}
    ports[mid] = new
    return port_selection(mid, old, new, tree, ports)


def test_handoff_edit_is_not_an_upward_change(tmp_path):
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
    source = 'OUTPUTS={"answer":("lent","refused")}\n'
    selected,text,_ = _select_ports(tmp_path,'lending',model_port(source),model_port(source.replace('"lent","refused"','"refused","lent"')))
    assert not selected and text == 'port: lending unchanged (this model only)'


def test_missing_outputs_is_uncertain(tmp_path):
    selected,text,_ = _select_ports(tmp_path,'lending',model_port('OUTPUTS={}'),model_port(''))
    assert selected == [('desk','parent')]
    assert text == 'UNCERTAIN port: lending declares no OUTPUTS; parent desk selected'


def test_port_lines_without_git(tmp_path):
    from flowguard.map.target import check_target, render_target_report
    data, inv = project(tmp_path)
    call = helpers()['call_target']
    assert call(tmp_path,'start','clarify lending rule') == 0
    assert call(tmp_path,'add','lending') == 0
    path=tmp_path/'.flowguard/target/models/lending.py'
    path.write_text(path.read_text().replace('the lending result is finite','the lending result stays finite'))
    assert 'port: lending unchanged (this model only)' in render_target_report(check_target(tmp_path,models=False))
    path.write_text(path.read_text().replace('("lent","refused")}','("lent","refused","waitlisted")}'))
    report = check_target(tmp_path,models=False)
    assert 'port changed: lending out +waitlisted -> verify desk (parent)' in render_target_report(report)
    assert any(f.code=='port_changed_parent_missing' for f in report.errors)


def test_dispatch_edit_is_not_an_upward_change(tmp_path):
    from flowguard.map.target import check_target, render_target_report
    data, inv = dispatch_project(tmp_path)
    call = helpers()['call_target']
    assert call(tmp_path,'start','add a command choice') == 0
    assert call(tmp_path,'add','cmd') == 0
    path=tmp_path/'.flowguard/target/models/cmd.py'
    path.write_text(path.read_text().replace('"x":"a","y":"b"','"x":"a","y":"b","z":"z"'))
    report=check_target(tmp_path,models=False)
    assert 'port: cmd unchanged (this model only); dispatch +z (edge checked by map check)' in render_target_report(report)
    assert any(f.code=='dispatch_without_child' for f in report.errors)
    source=(tmp_path/'.flowguard/models/a.py').read_text().replace("MODEL_ID='a'", 'MODEL_ID="z"').replace('shelf/loans.py:borrow','shelf/loans.py:third')
    (tmp_path/'.flowguard/target/models/z.py').write_text(source)
    with (tmp_path/'shelf/loans.py').open('a') as f: f.write('def third(value): return "left"\n')
    assert not any(f.code=='dispatch_without_child' for f in check_target(tmp_path,models=False).errors)


def test_escalation_set_orders_parent_handoff_child_input():
    from flowguard.map.port import Port, escalation_set
    from flowguard.map.tree import ModelNode, ModelTree
    nodes={mid:ModelNode(mid,mid+'.py','contract',parent,kind,'PARENT') for mid,parent,kind in (('m','p','model'),('p','system','component'),('k','system','component'),('c','m','model'))}
    ports={'m':Port(outputs={'x':('v',)}),'p':Port(),'k':Port(handoff={'m':{'x':'seen'}}),'c':Port(reads_parent=('f',))}
    assert escalation_set('m',ModelTree(nodes,{}),ports)==[('p','parent'),('k','HANDOFF'),('c','child input')]


def test_escalation_state_and_uncertainty_are_conservative():
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
