"""Schedule models, receive four proof verdicts, aggregate and render in registry order."""
from dataclasses import dataclass,replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from flowguard import FunctionResult,Invariant,InvariantResult,Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport,Fact
MODEL_ID='model_runs'
PARENT='map-proof'
IMPLEMENTED_BY={'RunModels':'flowguard/map/proof.py:run_models','Render':'flowguard/map/proof.py:render_results'}
USES = {'ChildPath': 'flowguard/map/common.py:child_import_path', 'Lint': 'flowguard/map/lint.py:run_lint'}
OUTPUTS={'models':('pass','fail')}
HANDOFF={'model_proof':{'outcome':'proof'},'anchor_watch':{'anchors':'anchors'},'port_checks':{'run_checks':'run_checks'},'test_binding':{'outcome':'tests'}}
KEEPS=('completion','large','status','lines','models','child_path_isolated','size_debt_used','size_debt_stale')
@dataclass(frozen=True)
class Case:
    proof:str
    anchors:str
    run_checks:str
    tests:str
    completion:tuple
    large:str
CASES=tuple(Case(p,a,c,t,o,l) for p in ('accepted','rejected') for a in ('seen','never_ran') for c in ('clean','fail','warning') for t in ('accepted','rejected') for o in (('first','second'),('second','first')) for l in ('normal','soft','hard'))
@dataclass(frozen=True)
class State:
    completion:tuple=()
    large:str='normal'
    proof:str='accepted'
    anchors:str='seen'
    run_checks:str='clean'
    tests:str='accepted'
    status:tuple=()
    lines:tuple=()
    models:str='pass'
    child_path_isolated: bool = True
    size_debt_used: bool = False
    size_debt_stale: bool = False
    @property
    def order(self):return tuple(name for name,status in self.status)
    @property
    def pass_lines(self):return max((sum(line.startswith('PASS '+name) for line in self.lines) for name,status in self.status if status=='pass'),default=1)
    @property
    def size_gate(self):
        if not self.status:return True
        verdict=dict(self.status)['first']
        healthy=self.proof=='accepted' and self.anchors=='seen' and self.run_checks!='fail' and self.tests=='accepted'
        return verdict==('pass' if healthy and self.large!='hard' else 'fail')
class Schedule:
    name='Schedule'
    reads=()
    writes = ('completion', 'large', 'child_path_isolated', 'size_debt_used')

    def __init__(self, defect=''):
        self.defect = defect

    def apply(self, event, state):
        isolated = self.defect != 'repo_root_on_child_path'
        return (FunctionResult(event, replace(state, completion=event.completion,
                                              large=event.large, child_path_isolated=isolated,
                                              size_debt_used=event.large == 'soft')),)
class Proof:
    name='Proof'
    reads=()
    writes=('proof',)
    def apply(self,event,state):return (FunctionResult(event,replace(state,proof=event.proof),label=event.proof),)
class Anchors:
    name='Anchors'
    reads=()
    writes=('anchors',)
    def apply(self,event,state):return (FunctionResult(event,replace(state,anchors=event.anchors),label=event.anchors),)
class RunChecks:
    name='RunChecks'
    reads=()
    writes=('run_checks',)
    def apply(self,event,state):return (FunctionResult(event,replace(state,run_checks=event.run_checks),label=event.run_checks),)
class Tests:
    name='Tests'
    reads=()
    writes=('tests',)
    def apply(self,event,state):return (FunctionResult(event,replace(state,tests=event.tests),label=event.tests),)
class Judge:
    name='Judge'
    reads=('proof','anchors','run_checks','tests','large','completion')
    writes=('status',)
    def __init__(self,defect=''):self.defect=defect
    def apply(self,event,state):
        checks=state.run_checks!='fail' or self.defect=='passes_failed_run_check'
        good=state.proof=='accepted' and state.anchors=='seen' and checks and state.tests=='accepted'
        size=state.large!='hard' or self.defect=='hard_pass'
        if self.defect=='time_gate' and state.large=='soft':size=False
        verdict='pass' if good and size else 'fail'
        statuses={'first':verdict,'second':'pass'}
        order=state.completion if self.defect=='order' else ('first','second')
        return (FunctionResult(event,replace(state,status=tuple((name,statuses[name]) for name in order))),)
class Render:
    name='Render'
    reads=('status','tests','size_debt_used')
    writes=('lines','models','size_debt_stale')
    def __init__(self,defect=''):self.defect=defect
    def apply(self,event,state):
        lines=tuple(status.upper()+' '+name for name,status in state.status)
        if self.defect=='rules':lines+=tuple('PASS '+name+' rules' for name,status in state.status if status=='pass')
        models='pass' if state.tests=='accepted' and all(status=='pass' for name,status in state.status) else 'fail'
        stale = not state.size_debt_used or self.defect == 'silencing_debt_called_stale'
        return (FunctionResult(models,replace(state,lines=lines,models=models,size_debt_stale=stale)),)

INVARIANTS = (
    Invariant('stale_size_debt_silences_nothing',
              'a size debt is reported stale only when removing it changes no finding of map lint and map models',
              lambda state, trace: not state.size_debt_stale or not state.size_debt_used),
    Invariant('child_path_exposes_only_flowguard',
              "a model or bound-test subprocess imports the project's own packages first and never sees the FlowGuard repository root",
              lambda state, trace: state.child_path_isolated),
Invariant("parallel_output_in_registry_order", "completion order never reorders registered models",
          lambda s, t: InvariantResult.pass_() if not s.order or s.order == ("first", "second")
          else InvariantResult.fail("registry order changed")),
Invariant("pass_is_one_line", "passing proofs have one output line", lambda s,t: s.pass_lines == 1),
Invariant("only_hard_size_limits_gate", "time and soft limits pass; more than 10000 sequences fail", lambda s,t:s.size_gate),
    Invariant('model_passes_only_when_every_verdict_passes','one failed verdict fails its model',lambda s,t:dict(s.status).get('first')!='pass' or s.proof=='accepted' and s.anchors=='seen' and s.run_checks!='fail' and s.tests=='accepted'),
)

def make(defect=''):
    return Explorer(Workflow((Schedule(defect),Proof(),Anchors(),RunChecks(),Tests(),Judge(defect),Render(defect))),(State(),State(models="fail")),CASES,invariants=INVARIANTS,max_sequence_length=1,progress_steps=0)
def build_explorer():return make()
def broken_variants():
    return {'repo_root_on_child_path': make('repo_root_on_child_path'),'orders_by_completion':make('order'),'prints_rules_on_pass':make('rules'),'large_model_gates_exit':make('time_gate'),'hard_limit_passes':make('hard_pass'),'passes_failed_run_check':make('passes_failed_run_check'),'silencing_debt_called_stale':make('silencing_debt_called_stale')}

def make_fixture(root, *, wrong_second=False, size_debt=False):
    directory = root / ".flowguard/models"
    directory.mkdir(parents=True)
    (root / "native.py").write_text(f"def first_value(): return 1\ndef second_value(): return {2 if wrong_second else 1}\n")
    for name, delay in (("first", 0.12), ("second", 0)):
        source = '''from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact, load_anchor
from pathlib import Path
import time
MODEL_ID = {name!r}
PARENT = "app"
IMPLEMENTED_BY = {{"Run": "native.py:{name}_value"}}
RULE = Invariant("one", "one is the allowed answer", lambda s,t: InvariantResult.pass_() if s == 1 else InvariantResult.fail("two"))
class Run:
    name = "Run"
    def __init__(self, value=1): self.value = value
    def apply(self, event, state): return (FunctionResult(self.value, self.value),)
def make(value): return Explorer(Workflow((Run(value),)), (1,), ("run",), invariants=(RULE,), max_sequence_length=1, progress_steps=0)
def build_explorer(): return make(1)
def broken_variants(): return {{"two": make(2)}}
def conformance():
    time.sleep({delay})
    actual = load_anchor(IMPLEMENTED_BY["Run"], root=Path.cwd())()
    return CodeFactsReport((Fact("native_value", actual == 1, repr(actual)),))
'''.format(name=name, delay=delay)
        if size_debt and name == 'first':
            source = source.replace('("run",)', '("run", "again", "last")')
            source = source.replace('max_sequence_length=1,', 'max_sequence_length=7 if value == 1 else 1,')
        (directory / (name + ".py")).write_text(source)
    comp = {"id": "app", "summary": "Two independent native values", "responsibilities": ["Compute values"],
            "files": ["native.py"], "models": [".flowguard/models/first.py", ".flowguard/models/second.py"],
            "status": "draft"}
    data = {"schema": "flowguard.map.v1", "components": [comp]}
    if size_debt:
        data['accepted_debts'] = [dict(code='large_model', component='first', contains='explored sequences',
                                      reason='one bounded native table', expires='9999-12-31')]
    (root / ".flowguard/map.json").write_text(json.dumps(data))



def conformance():
    from flowguard.map.proof import run_models, ModelResult, render_results
    from flowguard.map.lint import size_finding
    from flowguard.map.common import child_import_path
    from flowguard.map.inventory import build_inventory
    from flowguard.map.lint import run_lint
    from flowguard.map.mapfile import load_map
    import flowguard
    facts = []
    with TemporaryDirectory(prefix='fg-child-path-') as directory:
        project = Path(directory).resolve()
        paths = child_import_path(project, {'import_roots': []})
        package_parent = Path(flowguard.__file__).resolve().parent.parent
        source_checkout = (package_parent / 'pyproject.toml').is_file()
        isolated = (paths[0] == str(project)
                    and (not source_checkout or str(package_parent) not in paths))
        facts.append(Fact('child_path_exposes_only_flowguard', isolated, repr(paths)))
    with TemporaryDirectory(prefix="fg-model-runs-") as directory:
        root = Path(directory)
        make_fixture(root, wrong_second=True, size_debt=True)
        sequential = run_models(root, [], jobs=1)
        parallel = run_models(root, [], jobs=2)
        expected = [("first", "pass"), ("second", "fail"), ("system", "pass")]
        first = [(result.model, result.status) for result in sequential]
        second = [(result.model, result.status) for result in parallel]
        facts.append(Fact("registry_order", first == second == expected, repr((first, second))))
        data = load_map(root)
        lint = run_lint(root, data, build_inventory(root, [], write_cache=False), write_cache=False)
        used = (sequential[0].sequences == 3279 and not any('large_model:' in warning or 'debt_stale' in warning
                                                        for result in (sequential[0], parallel[0]) for warning in result.warnings)
                and not any(finding.code == 'debt_stale' and 'one bounded native table' in finding.message for finding in lint))
        facts.append(Fact('stale_size_debt_silences_nothing', used, repr(lint)))
    rendered = render_results([ModelResult("probe", "probe.py", rules=["one"], known_bad=["two"])])
    facts.append(Fact("single_pass_line", len([line for line in rendered.splitlines() if line and not line.startswith("models:")]) == 1, rendered))
    text = render_results([ModelResult("sized", "sized.py", seconds=0.5, advice_limit=1e-06)])
    facts.append(Fact("size_time", "INFO large_model x1:" in text and "PASS" in text, text))
    soft = size_finding("sized", "sequences", 2187)
    hard = size_finding("sized", "sequences", 21844)
    facts.append(Fact("size_soft", soft is not None and soft.level == "warn", repr(soft)))
    facts.append(Fact("size_hard", hard is not None and hard.level == "error", repr(hard)))
    return CodeFactsReport(tuple(facts))



TESTED_BY = {'stale_size_debt_silences_nothing': ['tests/test_model_runs.py:test_debt_silencing_models_warning_is_used',
                                               'tests/test_model_runs.py:test_size_debt_waits_for_its_actual_observation',
                                               'tests/test_model_runs.py:test_size_debt_retains_static_rule_and_test_file_judgments'],
 'only_hard_size_limits_gate': ['tests/test_model_runs.py:test_sequence_soft_limit_warns',
                                'tests/test_model_runs.py:test_sequence_hard_limit_fails_the_model',
                                'tests/test_model_runs.py:test_time_over_the_limit_is_one_info'],
 'parallel_output_in_registry_order': ['tests/test_model_runs.py:test_jobs_output_equals_sequential'],
 'pass_is_one_line': ['tests/test_model_runs.py:test_pass_is_one_line_fail_keeps_rules'],
 'model_passes_only_when_every_verdict_passes': ['tests/test_model_runs.py:test_model_fails_when_any_verdict_fails'],
 'child_path_exposes_only_flowguard': ['tests/test_model_proof.py:test_child_path_never_exposes_repo_root',
                                       'tests/test_model_proof.py:test_src_layout_project_imports_its_own_package']}
