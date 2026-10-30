"""Change checks and selects before running; its exit and next action follow receipts."""
from dataclasses import dataclass, replace
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
MODEL_ID='change_command'
PARENT='cli'
IMPLEMENTED_BY={'Change':'flowguard/map/cli.py:cmd_change','Run':'flowguard/map/cli.py:_run_selected'}
USES = {
    'CmdConfirm': 'flowguard/map/cli.py:cmd_confirm',
    'Main': 'flowguard/__main__.py:main',
}
HANDOFF={'change_selection':{'selection':'selection'},'map_check':{'check':'check'}}
TESTED_BY = {'errors_skip_the_run': ['tests/test_packaged_cli_surface.py:test_change_run_skips_when_check_has_errors'], 'exit_follows_check_selection_and_run': ['tests/test_packaged_cli_surface.py:test_change_run_runs_the_selected_checks'], 'stale_component_names_confirm': ['tests/test_packaged_cli_surface.py:test_change_run_ends_with_map_confirm_for_stale_components']}
@dataclass(frozen=True)
class Case:
    run:bool
    check:str
    selection:str
    tests:str='pass'
CASES=tuple(Case(run,check,selection,tests) for run in (False,True) for check in ('clean','error','stale') for selection in ('selected','broad','blocked','nothing') for tests in (('pass','fail') if run and check!='error' and selection!='blocked' else ('pass',)))
@dataclass(frozen=True)
class State:
    run:bool=False
    check:str='clean'
    selection:str='nothing'
    tests:str='pass'
    ran:str='not_asked'
    next_confirm:bool=False
    exit_code:int=0
class TakeRequest:
    name='TakeRequest'
    reads=()
    writes=('run','tests')
    def apply(self,event,state):return (FunctionResult(event,replace(state,run=event.run,tests=event.tests)),)
class Check:
    name='Check'
    reads=()
    writes=('check',)
    def apply(self,event,state):return (FunctionResult(event,replace(state,check=event.check),label=event.check),)
class Select:
    name='Select'
    reads=()
    writes=('selection',)
    def apply(self,event,state):return (FunctionResult(event,replace(state,selection=event.selection),label=event.selection),)
class Run:
    name='Run'
    reads=('run','check','selection')
    writes=('ran',)
    def __init__(self,defect=''):self.defect=defect
    def apply(self,event,state):
        blocked=state.check=='error' or state.selection=='blocked'
        ran='not_asked' if not state.run else 'skipped' if blocked and self.defect!='runs_despite_errors' else 'ran'
        return (FunctionResult(event,replace(state,ran=ran)),)
class Exit:
    name='Exit'
    reads=('check','selection','ran','tests')
    writes=('exit_code','next_confirm')
    def __init__(self,defect=''):self.defect=defect
    def apply(self,event,state):
        failed=state.check=='error' or state.selection=='blocked' or state.ran=='ran' and state.tests=='fail' and self.defect!='ignores_failed_run'
        confirm=state.run and state.ran=='ran' and state.check=='stale' and self.defect!='omits_confirm_line'
        return (FunctionResult(int(failed),replace(state,exit_code=int(failed),next_confirm=confirm)),)
RULES=(
 Invariant('errors_skip_the_run','errors block the requested run',lambda s,t:not s.run or s.check!='error' and s.selection!='blocked' or s.ran=='skipped'),
 Invariant('exit_follows_check_selection_and_run','exit reflects checks, blocked selection and the selected run',lambda s,t:s.exit_code==int(s.check=='error' or s.selection=='blocked' or s.ran=='ran' and s.tests=='fail')),
 Invariant('stale_component_names_confirm','a completed stale run names confirmation',lambda s,t:not (s.run and s.ran=='ran' and s.check=='stale') or s.next_confirm),
)
def make(defect=''):return Explorer(Workflow((TakeRequest(),Check(),Select(),Run(defect),Exit(defect))),(State(),),CASES,invariants=RULES,max_sequence_length=2,progress_steps=0)
def build_explorer():return make()
def broken_variants():return {name:make(name) for name in ('runs_despite_errors','ignores_failed_run','omits_confirm_line')}
def conformance():
    from flowguard.__main__ import main
    from flowguard.map.cli import cmd_confirm
    from types import SimpleNamespace
    from _target_fixture import make_port_project
    facts=[]
    for case in ('clean','anchor','missing','stale','failing_test'):
        with TemporaryDirectory(prefix='fg-change-command-') as directory:
            root=Path(directory);make_port_project(root)
            with redirect_stdout(StringIO()):cmd_confirm(root,SimpleNamespace(ids=['cli','loans']))
            for args in (('init','-q'),('add','.'),('-c','user.name=FlowGuard','-c','user.email=model@example.invalid','commit','-qm','baseline')):
                subprocess.run(['git','-c','maintenance.auto=false','-c','gc.auto=0',*args],cwd=root,check=True,capture_output=True)
            p=root/'shelf/loans.py'
            if case=='anchor':p.write_text(p.read_text().replace('def borrow(', 'def renamed('))
            elif case=='missing':(root/'.flowguard/models/lending.py').unlink()
            elif case=='failing_test':
                p=root/'tests/test_port.py';p.parent.mkdir(exist_ok=True);p.write_text('def test_selected_failure(): assert False\n')
            else:p.write_text(p.read_text().replace('return "lent"','return str("lent")'))
            args=['change','--root',str(root)]
            if case in ('anchor','missing','stale','failing_test'):args+=['--run']
            out=StringIO()
            with redirect_stdout(out),redirect_stderr(out):code=main(args)
            text=out.getvalue()
            valid=(code==0 if case in ('clean','stale') else code==1)
            if case in ('anchor','missing'):valid &= 'RAN: skipped' in text
            elif case=='stale':
                import shlex
                line = next((line for line in text.splitlines() if line.startswith('next[confirm]: ')), '')
                command = shlex.split(line.partition(': ')[2])
                valid &= (command[:5] == ['python', '-m', 'flowguard', 'map', 'confirm']
                          and '--root' in command and command[command.index('--root') + 1] == str(root.resolve()))
            elif case=='failing_test':valid &= 'RAN FAIL' in text
            facts.append(Fact(case,bool(valid),text))
    return CodeFactsReport(tuple(facts))
