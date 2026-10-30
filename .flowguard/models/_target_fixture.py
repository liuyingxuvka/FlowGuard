"""Shared native shelf fixtures; no model, rules or reusable proof results."""
from contextlib import chdir, redirect_stderr, redirect_stdout
from io import StringIO
import json
from flowguard.map import target as native
from flowguard.map.proof import run_model_in_process

REGULAR_CONTRACT = '''from pathlib import Path
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact, load_anchor
MODEL_ID = "shelf_rule"
PARENT = "loans"
IMPLEMENTED_BY = {"Advance": "shelf/loans.py:advance"}
NOT_MODELED = {
    "flowguard/map/target.py:main": "Argument parsing only; it calls start_target, add_to_target, check_target, "
                                    "promote_target and drop_target, which this model anchors.",
}
TESTED_BY = {}
class Advance:
    name = "Advance"
    def __init__(self, delta=1): self.delta = delta
    def apply(self, event, state):
        return (FunctionResult(self.delta, self.delta, label="advanced"),)
RULE = Invariant("one_loan_step", "one loan step advances by one", lambda s,t:
    InvariantResult.pass_() if s in (0,1) else InvariantResult.fail("wrong loan step"))
def make(delta):
    return Explorer(Workflow((Advance(delta),)), (0,), ("advance",),
                    invariants=(RULE,), max_sequence_length=1, progress_steps=0)
def build_explorer(): return make(1)
def broken_variants(): return {"advance_twice": make(2)}
def conformance():
    actual = load_anchor(IMPLEMENTED_BY["Advance"], root=Path.cwd())(0)
    return CodeFactsReport((Fact("native_loan_step", actual == 1, repr(actual)),))
'''

def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

def make_project(root):
    """Fresh small shelf fixture only; no prior check/proof result is reused."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "shelf").mkdir()
    (root / "tests").mkdir()
    (root / ".flowguard/models").mkdir(parents=True)
    (root / "shelf/__init__.py").write_text("", encoding="utf-8")
    (root / "shelf/catalog.py").write_text("def capacity():\n    return 1\n", encoding="utf-8")
    (root / "shelf/loans.py").write_text(
        "from shelf.catalog import capacity\n\ndef advance(value):\n    return value + capacity()\n",
        encoding="utf-8")
    (root / "tests/test_shelf.py").write_text(
        "from shelf.loans import advance\ndef test_advance():\n    assert advance(0) == 1\n",
        encoding="utf-8")
    components = []
    for cid, layer, files, anchor, deps, state in (
        ("loans", "lending", ["shelf/loans.py"], "shelf/loans.py:advance", ["catalog"], ["active loans"]),
        ("catalog", "records", ["shelf/catalog.py", "shelf/__init__.py"], "shelf/catalog.py:capacity", [], ["stock count"]),
    ):
        components.append(dict(id=cid, layer=layer, summary="Own " + cid,
                               responsibilities=["maintain " + cid], files=files,
                               entrypoints=[anchor], state=state, side_effects=[],
                               depends_on=deps, tests=["tests/test_shelf.py"] if cid == "loans" else [],
                               models=[".flowguard/models/shelf_rule.py"] if cid == "loans" else [],
                               status="draft"))
    data = dict(schema="flowguard.map.v1", project="small-shelf", layers=["lending", "records"],
                ignore=[], test_command="python -m pytest -q", components=components,
                flows=[dict(id="borrow", summary="borrow one book", steps=["loans:advance"])],
                accepted_debts=[])
    write_json(root / ".flowguard/map.json", data)
    (root / ".flowguard/models/shelf_rule.py").write_text(REGULAR_CONTRACT, encoding="utf-8")
    return root

def call_target(root, *arguments):
    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        return native.main([*arguments, "--root", str(root)])

def stage_target(root, *, with_model=True):
    assert call_target(root, "start", "extend the shelf") == 0
    assert call_target(root, "add", "component:loans") == 0
    if with_model:
        assert call_target(root, "add", "model:shelf_rule") == 0
        path = root / ".flowguard/target/models/shelf_rule.py"
        # A real (non-comment) revision, so the target is not a no-op copy.
        path.write_text(path.read_text(encoding="utf-8") + "\nTARGET_REVISION = 2  # revised target shelf contract\n",
                        encoding="utf-8")

def reached_failure_target(root):
    """Two valid consumers share capacity; only the target's consumer adopts its change."""
    import subprocess
    from flowguard.map.cli import main as map_main
    from flowguard.map.mapfile import load_map, model_digests
    root = make_project(root)
    (root / "shelf/renew.py").write_text(
        "from shelf.catalog import capacity\n\ndef renew(value):\n    return value + capacity()\n", encoding="utf-8")
    renewal = REGULAR_CONTRACT.replace('MODEL_ID = "shelf_rule"', 'MODEL_ID = "renew_rule"')
    renewal = renewal.replace('PARENT = "loans"', 'PARENT = "renew"')
    renewal = renewal.replace("shelf/loans.py:advance", "shelf/renew.py:renew")
    (root / ".flowguard/models/renew_rule.py").write_text(renewal, encoding="utf-8")
    data = load_map(root)
    data["components"].append(dict(
        id="renew", layer="lending", summary="Renew an existing loan", responsibilities=["renew loans"],
        files=["shelf/renew.py"], entrypoints=["shelf/renew.py:renew"], depends_on=["catalog"],
        tests=[], models=[".flowguard/models/renew_rule.py"], state=[], side_effects=[], status="draft"))
    data["model_digests"] = model_digests(root)
    write_json(root / ".flowguard/map.json", data)
    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        assert map_main(["confirm", "all", "--root", str(root)]) == 0

    def git(*arguments):
        subprocess.run(["git", "-c", "user.name=Guard", "-c", "user.email=guard@example.invalid",
                        "-c", "commit.gpgsign=false", "-C", str(root), *arguments], check=True, capture_output=True)

    git("init", "-q")
    git("add", "--", "shelf", "tests", ".flowguard/map.json", ".flowguard/models")
    git("commit", "-qm", "valid two-consumer baseline")
    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        stage_target(root)
    path = root / ".flowguard/target/models/shelf_rule.py"
    source = path.read_text(encoding="utf-8")
    source = source.replace("s in (0,1)", "s in (0,2)")
    source = source.replace("one loan step advances by one", "one loan step advances by two")
    source = source.replace("return make(1)", "return make(2)")
    source = source.replace('{"advance_twice": make(2)}', '{"advance_thrice": make(3)}')
    source = source.replace("actual == 1", "actual == 2")
    path.write_text(source, encoding="utf-8")
    (root / "shelf/catalog.py").write_text("def capacity():\n    return 2\n", encoding="utf-8")
    test = root / "tests/test_shelf.py"
    test.write_text(test.read_text(encoding="utf-8").replace("advance(0) == 1", "advance(0) == 2"), encoding="utf-8")
    return root


def probe_regular_model(root, logical_model, *, view):
    """Fresh finite fixture proof using the real engine and its model namespace.

    Keep Path.cwd()-based fixture conformance equivalent to run_model's child
    process, and restore the caller even when the actual proof raises.
    """
    with chdir(root):
        return run_model_in_process(root, logical_model, view=view)


def make_port_project(root, case="valid"):
    """Copy the runnable shelf port example, then apply one finite real defect."""
    import shutil,json
    from pathlib import Path
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    source=next(parent.parent for parent in Path(__file__).resolve().parents if parent.name=='.flowguard')/'examples/shelf'
    shutil.copytree(source,root,dirs_exist_ok=True,ignore=shutil.ignore_patterns('target','after','__pycache__','cache','.git','README.md'))
    data=json.loads((root/'.flowguard/map.json').read_text())
    desk=(root/'.flowguard/models/desk.py').read_text()
    lending=(root/'.flowguard/models/lending.py').read_text()
    files={'shelf/loans.py':(root/'shelf/loans.py').read_text()}
    head='from dataclasses import dataclass, replace\nfrom pathlib import Path\nfrom flowguard import FunctionResult, Invariant, Workflow\nfrom flowguard.explorer import Explorer\nfrom flowguard.map.facts import CodeFactsReport, Fact, load_anchor\n'
    if case == "undeclared_write":
        desk=desk.replace('writes=("request","answer")','writes=("request",)')
    elif case == "undeclared_output":
        lending=lending.replace('OUTPUTS = {"answer":("lent","refused")}','OUTPUTS = {"answer":("lent",)}')
    elif case == "missing_receipt":
        desk=desk.replace('FunctionResult(event,replace(state,request=event.request))','FunctionResult(event.request,replace(state,request=event.request))').replace('FunctionResult(event.answer,replace(state,answer=event.answer),label=event.answer)','FunctionResult("ok",replace(state,answer="refused"),label="received")').replace('FunctionResult(reply,replace','FunctionResult("ok",replace')
    elif case == "wrong_receiving_field":
        desk=desk.replace('"answer":"answer"','"answer":"request"').replace('KEEPS = ("request","reply")','KEEPS = ("request","reply","answer")')
    elif case == "unreached_output":
        lending=lending.replace('OUTPUTS = {"answer":("lent","refused")}','OUTPUTS = {"answer":("lent","refused","waitlisted")}')
    elif case in ("domain_keeps","parent_output"):
        desk=desk.replace('    reply: str = ""','    reply: str = ""\n    extra: bool = False' if case=="domain_keeps" else '    reply: str = ""\n    extra: str = ""')
        desk=desk.replace('KEEPS = ("request","reply")','KEEPS = ("request","reply","extra")')
        block='''class Compute:
    name="Compute"
    reads=("extra",)
    writes=("extra",)
    def apply(self,value,state):
        return (FunctionResult(value,replace(state,extra=EXTRA)),)
'''.replace('EXTRA','not state.extra' if case=="domain_keeps" else '"computed"')
        desk=desk.replace('RULE = Invariant',block+'RULE = Invariant').replace('Workflow((TakeRequest(),Receive(),block))','Workflow((TakeRequest(),Receive(),block,Compute()))')
        if case=="domain_keeps":
            desk=desk.replace('max_sequence_length=1','max_sequence_length=2')
        else:
            desk += '\nOUTPUTS = {"extra":("computed",)}\n'
            files['shelf/consumer.py']='def consume(value): return value\n'
            files['.flowguard/models/consumer.py']=head+'''MODEL_ID="consumer"
PARENT="cli"
IMPLEMENTED_BY={"Consume":"shelf/consumer.py:consume"}
HANDOFF={"desk":{"extra":"seen"}}
@dataclass(frozen=True)
class ConsumerState:
    seen:str=""
class Consume:
    name="Consume"
    writes=("seen",)
    def __init__(self,bad=False): self.bad=bad
    def apply(self,event,state): return (FunctionResult(event,ConsumerState("bad" if self.bad else event)),)
RULE=Invariant("received","the receipt is retained",lambda s,t:s.seen in ("","computed"))
def make(bad=False): return Explorer(Workflow((Consume(bad),)),(ConsumerState(),),("computed",),invariants=(RULE,),max_sequence_length=1,progress_steps=0)
def build_explorer(): return make()
def broken_variants(): return {"lost":make(True)}
def conformance(): return CodeFactsReport((Fact("native",load_anchor(IMPLEMENTED_BY["Consume"],root=Path.cwd())("computed")=="computed"),))
'''
    elif case == "short_consumer":
        lending = lending.replace('PARENT = "desk"', 'PARENT = "loans"')
        files["shelf/consumer.py"] = "def consume(value): return value\n"
        files[".flowguard/models/consumer.py"] = head + 'MODEL_ID="consumer"\nPARENT="cli"\nIMPLEMENTED_BY={"Consume":"shelf/consumer.py:consume"}\nHANDOFF={"lending":{"answer":"seen"}}\n@dataclass(frozen=True)\nclass ConsumerState:\n    seen:str=""\nclass Consume:\n    name="Consume"\n    writes=("seen",)\n    def __init__(self,bad=False):self.bad=bad\n    def apply(self,event,state):return (FunctionResult(event,ConsumerState("bad" if self.bad else event)),)\nRULE=Invariant("received","the receipt is retained",lambda s,t:s.seen in ("","lent","refused"))\ndef make(bad=False):return Explorer(Workflow((Consume(bad),)),(ConsumerState(),),("lent","refused"),invariants=(RULE,),max_sequence_length=1,progress_steps=0)\ndef build_explorer():return make()\ndef broken_variants():return {"lost":make(True)}\ndef conformance():return CodeFactsReport((Fact("native",all(load_anchor(IMPLEMENTED_BY["Consume"],root=Path.cwd())(value)==value for value in ("lent","refused"))),))\n'
    elif case == "drops_child_value":
        desk=desk.replace('"answer":"answer"','"answer":("answer",{"lent":"lent","refused":None})')
    elif case == "missing_parent_input":
        lending=lending.replace('READS_PARENT = ("request",)','READS_PARENT = ("missing",)')
    elif case == "uncovered_parent_field":
        desk=desk.replace('    reply: str = ""','    reply: str = ""\n    abandoned: str = ""')
    elif case == "overlapping_receipts":
        lending=lending.replace('OUTPUTS = {"answer":("lent","refused")}','OUTPUTS = {"answer":("lent","refused"),"request":("lend_request","deny_request")}')
        desk=desk.replace('"lending":{"answer":"answer"}','"lending":{"answer":"answer","request":"answer"}')
    elif case == "consumer_receipts":
        desk=desk.replace('"lending":{"answer":"answer"}', '"lending":{"answer":"answer"},"other":{"answer":"answer"}')
        other=lending.replace('MODEL_ID = "lending"','MODEL_ID = "other"').replace('PARENT = "desk"','PARENT = "loans"').replace('shelf/loans.py:LoanService.borrow','shelf/loans.py:borrow_other')
        files['shelf/loans.py']+='\ndef borrow_other(request): return request\n'
        other=other.replace('\"GiveBack\": \"shelf/loans.py:LoanService.give_back\"', '\"GiveBack\": \"shelf/loans.py:give_back_other\"')
        files['shelf/loans.py']+='\ndef give_back_other(request): return request\n'
        files['.flowguard/models/other.py']=other
    elif case == "no_child_output":
        lending=lending.replace('OUTPUTS = {"answer":("lent","refused")}','OUTPUTS = {}')
        desk=desk.replace('HANDOFF = {"lending":{"answer":"answer"}}','HANDOFF = {}').replace('KEEPS = ("request","reply")','KEEPS = ("request","reply","answer")')
    files['tests/test_port.py'] = 'from shelf.loans import LoanService\ndef test_borrow():\n    service=LoanService()\n    service.members.join("ann")\n    service.catalog.add("book",1)\n    assert service.borrow("ann","book")=="lent"\n    assert service.borrow("missing","book")=="refused"\n'
    files['.flowguard/models/desk.py']=desk
    files['.flowguard/models/lending.py']=lending
    for path,text in files.items():
        target=root/path; target.parent.mkdir(parents=True,exist_ok=True); target.write_text(text,encoding="utf-8")
    for component in data['components']:
        if component['id']=='loans' and 'tests/test_port.py' not in component['tests']:component['tests'].append('tests/test_port.py')
        if component['id']=='cli' and case in ('parent_output','short_consumer'):component['files'].append('shelf/consumer.py')
    write_json(root/'.flowguard/map.json',data)
    return data


def probe_port_model(root, model):
    """Fresh real in-process proof; restore project imports and paths even after a failure."""
    import sys
    names={name for name in sys.modules if name=='shelf' or name.startswith('shelf.') or name.startswith('_flowguard_model_') and name.rsplit('_',1)[-1] in ('desk','lending','consumer')}
    saved={name:sys.modules.pop(name) for name in names}; paths=list(sys.path)
    try:
        with chdir(root):
            return run_model_in_process(root, root/'.flowguard/models'/f'{model}.py')
    finally:
        sys.path[:]=paths
        for name in list(sys.modules):
            if name=='shelf' or name.startswith('shelf.') or name.startswith('_flowguard_model_') and name.rsplit('_',1)[-1] in ('desk','lending','consumer'):
                sys.modules.pop(name,None)
        sys.modules.update(saved)

def slicing_project(root, reads_field=False):
    """An actual new parent value, with a sibling projecting only the old step."""
    make_project(root)
    source = root / 'shelf/loans.py'
    source.write_text(source.read_text() + '\ndef gate(value): return value\ndef check(value): return value\ndef publish(value): return value\n')
    head = '''from dataclasses import dataclass
from pathlib import Path
from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact, load_anchor
'''
    gate = head + '''MODEL_ID = "gate"
PARENT = "loans"
IMPLEMENTED_BY = {"Gate": "shelf/loans.py:gate"}
HANDOFF = {"check": {"flag": "flag"}, "publish": {"step": "step"}}
KEEPS = ("step",)
VALUES = ("ok", "bad")
@dataclass(frozen=True)
class State:
    step: str = "start"
    flag: str = ""
class Gate:
    name = "Gate"
    reads = ("step",)
    writes = ("step", "flag")
    def __init__(self, wrong=False): self.wrong = wrong
    def apply(self, event, state):
        if event in ("start", "ready"):
            return (FunctionResult(event, State(event, state.flag)),)
        return (FunctionResult(event, State("lost" if self.wrong else "ready", event)),)
RULE = Invariant("gate_step", "a gate retains one received decision", lambda s,t: s.step in ("start", "ready") and s.flag in ("",) + VALUES)
def make(wrong=False): return Explorer(Workflow((Gate(wrong),)), (State(),), VALUES + ("ready",), invariants=(RULE,), max_sequence_length=1, progress_steps=0)
def build_explorer(): return make()
def broken_variants(): return {"lost_step": make(True)}
def conformance(): return CodeFactsReport((Fact("native_gate", load_anchor(IMPLEMENTED_BY["Gate"], root=Path.cwd())("ok") == "ok"),))
'''
    check = head + '''MODEL_ID = "check"
PARENT = "gate"
IMPLEMENTED_BY = {"Check": "shelf/loans.py:check"}
OUTPUTS = {"flag": ("ok", "bad")}
VALUES = ("ok", "bad")
@dataclass(frozen=True)
class State:
    flag: str = ""
class Check:
    name = "Check"
    reads = ()
    writes = ("flag",)
    def __init__(self, wrong=False): self.wrong = wrong
    def apply(self, event, state): return (FunctionResult(event, State("lost" if self.wrong else event)),)
RULE = Invariant("decision_received", "a decision is one declared flag", lambda s,t: s.flag in ("",) + VALUES)
def make(wrong=False): return Explorer(Workflow((Check(wrong),)), (State(),), VALUES, invariants=(RULE,), max_sequence_length=1, progress_steps=0)
def build_explorer(): return make()
def broken_variants(): return {"lost_flag": make(True)}
def conformance(): return CodeFactsReport((Fact("native_check", load_anchor(IMPLEMENTED_BY["Check"], root=Path.cwd())("ok") == "ok"),))
'''
    publish = head + '''from flowguard.kit import reachable_states
from gate import build_explorer as parent_explorer
MODEL_ID = "publish"
PARENT = "gate"
IMPLEMENTED_BY = {"Publish": "shelf/loans.py:publish"}
OUTPUTS = {"step": ("ready",)}
@dataclass(frozen=True)
class State:
    step: str = "start"
def project_parent_state(state):
    return State(state.step)
class Publish:
    name = "Publish"
    reads = ("step",)
    writes = ("step",)
    def __init__(self, wrong=False): self.wrong = wrong
    def apply(self, event, state): return (FunctionResult("ready", State("lost" if self.wrong else "ready")),)
RULE = Invariant("step_retained", "publication retains a gate step", lambda s,t: s.step in ("start", "ready"))
def make(wrong=False): return Explorer(Workflow((Publish(wrong),)), reachable_states(parent_explorer(), project_parent_state), ("publish",), invariants=(RULE,), max_sequence_length=1, progress_steps=0)
def build_explorer(): return make()
def broken_variants(): return {"lost_step": make(True)}
def conformance(): return CodeFactsReport((Fact("native_publish", load_anchor(IMPLEMENTED_BY["Publish"], root=Path.cwd())(1) == 1),))
'''
    if reads_field:
        publish = publish.replace('    return State(state.step)', '    if state.flag == "held":\n        return None\n    return State(state.step)')
    for name, text in (('gate', gate), ('check', check), ('publish', publish)):
        (root / '.flowguard/models' / (name + '.py')).write_text(text)
    path = root / '.flowguard/map.json'
    data = json.loads(path.read_text())
    data['components'][0]['models'].append('.flowguard/models/gate.py')
    write_json(path, data)
    assert call_target(root, 'start', 'a received decision gains held') == 0
    assert call_target(root, 'add', 'check') == 0
    assert call_target(root, 'add', 'gate') == 0
    for name in ('check', 'gate'):
        path = root / '.flowguard/target/models' / (name + '.py')
        path.write_text(path.read_text().replace('("ok", "bad")', '("ok", "bad", "held")'))
    return root
