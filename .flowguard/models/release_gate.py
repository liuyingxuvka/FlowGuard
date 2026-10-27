"""Release warns on an open target, checks every gate and runs shards only after clean gates."""
from dataclasses import dataclass,replace
from contextlib import redirect_stdout,redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from flowguard import FunctionResult,Invariant,Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport,Fact
MODEL_ID='release_gate'
PARENT='cli'
IMPLEMENTED_BY={'Verify':'flowguard/map/cli.py:cmd_verify'}
USES={'Main':'flowguard/__main__.py:main'}
HANDOFF={'map_check':{'check':('check',{'error':'error','stale':None,'clean':'clean'})},'model_runs':{'models':'models'},'shard_suite':{'suite':'suite'}}
TESTED_BY = {'release_passes_only_when_every_gate_passes': ['tests/test_flowguard_map_proof.py:test_strict_check_and_verify_gate'], 'suite_runs_only_after_clean_gates': ['tests/test_pytest_shard_runner.py:test_release_runs_the_whole_suite_in_shards'], 'open_target_is_warned': ['tests/test_cli_main.py:test_release_warns_first_but_runs_the_same_current_models']}
@dataclass(frozen=True)
class Case:
    target_open:bool
    shards:bool
    lint:str
    check:str
    models:str
    suite:str
CASES=tuple(Case(target,shards,lint,check,models,suite) for target in (False,True) for lint in ('clean','error') for check in ('clean','error') for models in ('pass','fail') for shards,suites in ((False,('pass',)),(True,('pass','fail','partial','blocked'))) for suite in suites)
@dataclass(frozen=True)
class State:
    target_open:bool=False
    shards:bool=False
    lint:str='clean'
    check:str='clean'
    models:str='pass'
    suite:str='pass'
    suite_ran:bool=False
    warned:bool=False
    verdict:str='pass'
    exit_code:int=0
class TakeRequest:
    name='TakeRequest'
    reads=()
    writes=('target_open','shards','lint')
    def apply(self,event,state):return (FunctionResult(event,replace(state,target_open=event.target_open,shards=event.shards,lint=event.lint)),)
class Warn:
    name='Warn'
    reads=('target_open',)
    writes=('warned',)
    def __init__(self,defect=''):self.defect=defect
    def apply(self,event,state):return (FunctionResult(event,replace(state,warned=state.target_open and self.defect!='silent_on_open_target')),)
class CheckGate:
    name='CheckGate'
    reads=()
    writes=('check',)
    def apply(self,event,state):return (FunctionResult(event,replace(state,check=event.check),label=event.check),)
class ModelsGate:
    name='ModelsGate'
    reads=()
    writes=('models',)
    def apply(self,event,state):return (FunctionResult(event,replace(state,models=event.models),label=event.models),)
class Suite:
    name='Suite'
    reads=('shards','lint','check','models')
    writes=('suite','suite_ran')
    def __init__(self,defect=''):self.defect=defect
    def apply(self,event,state):
        ran=state.shards and (state.lint==state.check=='clean' and state.models=='pass' or self.defect=='runs_suite_after_failure')
        if not ran:return (FunctionResult(event,replace(state,suite_ran=False),label='not run'),)
        return (FunctionResult(event,replace(state,suite=event.suite,suite_ran=True),label=event.suite),)
class Verdict:
    name='Verdict'
    reads=('lint','check','models','shards','suite')
    writes=('verdict','exit_code')
    def __init__(self,defect=''):self.defect=defect
    def apply(self,event,state):
        passed=state.lint==state.check=='clean' and (state.models=='pass' or self.defect=='ignores_failed_model') and (not state.shards or not state.suite_ran or state.suite=='pass')
        return (FunctionResult(int(not passed),replace(state,verdict='pass' if passed else 'fail',exit_code=int(not passed))),)
RULES=(
 Invariant('release_passes_only_when_every_gate_passes','release reflects checks, lint, model proof and requested suite',lambda s,t:(s.verdict=='pass')==(s.check==s.lint=='clean' and s.models=='pass' and (not s.shards or s.suite=='pass')) and s.exit_code==int(s.verdict!='pass')),
 Invariant('suite_runs_only_after_clean_gates','a suite starts only after every earlier gate passes',lambda s,t:not s.suite_ran or s.shards and s.check==s.lint=='clean' and s.models=='pass'),
 Invariant('open_target_is_warned','the current tree release names any open target first',lambda s,t:not s.target_open or s.warned),
)
def make(defect=''):return Explorer(Workflow((TakeRequest(),Warn(defect),CheckGate(),ModelsGate(),Suite(defect),Verdict(defect))),(State(),),CASES,invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer():return make()
def broken_variants():return {name:make(name) for name in ('ignores_failed_model','runs_suite_after_failure','silent_on_open_target')}
def conformance():
    from flowguard.__main__ import main
    from flowguard.map.cli import main as map_main
    from _target_fixture import make_project,call_target
    facts=[]
    for case in ('clean','failed','target','suite_blocked'):
        with TemporaryDirectory(prefix='fg-release-gate-') as directory:
            root=make_project(Path(directory))
            if case in ('failed','suite_blocked'):
                p=root/'shelf/loans.py';p.write_text(p.read_text().replace('value + capacity()','value + capacity() + 1'))
            with redirect_stdout(StringIO()):map_main(['confirm','all','--root',str(root)])
            if case=='target':call_target(root,'start','open plan')
            args=['release','--root',str(root)]
            if case=='suite_blocked':args+=['--shards','2']
            out=StringIO()
            with redirect_stdout(out),redirect_stderr(out):code=main(args)
            text=out.getvalue()
            valid=code==int(case in ('failed','suite_blocked')) and ('verify: FAIL' if case in ('failed','suite_blocked') else 'verify: PASS') in text
            if case=='target':valid &= text.startswith('warning: target "open plan" exists:')
            if case=='suite_blocked':valid &= 'suite: not run' in text
            facts.append(Fact(case,bool(valid),text))
    return CodeFactsReport(tuple(facts))
