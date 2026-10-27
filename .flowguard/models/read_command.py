"""Read dispatches one view, rejects conflicts first, and returns the view's exit status."""
from dataclasses import dataclass,replace
from pathlib import Path
from tempfile import TemporaryDirectory
from flowguard import FunctionResult,Invariant,Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport,Fact
MODEL_ID='read_command'
PARENT='cli'
COMPONENTS=['cli','map-read']
IMPLEMENTED_BY={'Show':'flowguard/map/cli.py:cmd_show','Find':'flowguard/map/cli.py:cmd_find'}
USES={'Main':'flowguard/__main__.py:main'}
DISPATCH={'mode':{'show':'read_show','component':'read_component','find':'read_find','review':'read_review','field':'read_field','mermaid':'read_mermaid'}}
HANDOFF={'read_show':{'shown':'shown'},'read_component':{'component':'component'},'read_find':{'found':'found'},'read_review':{'review':'review'},'read_field':{'field':'field'},'read_mermaid':{'diagram':'diagram'}}
KEEPS=('mode','refused','exit_code')
TESTED_BY = {'one_view_per_read': ['tests/test_flowguard_target.py:test_read_target_conflicts_only_with_find'], 'missing_subject_exits_one': ['tests/test_read_command.py:test_read_unknown_component_fails_and_names_the_read_command'], 'project_without_map_is_refused': ['tests/test_flowguard_map.py:test_missing_map_points_at_scan_and_the_first_map_guide']}
FIELDS={'show':'shown','component':'component','find':'found','review':'review','field':'field','mermaid':'diagram'}
ANSWERS={'show':('complete',),'component':('shown','unknown'),'find':('owners','no_owner','location','no_symbol','test'),'review':('ranked','nothing_to_rank'),'field':('listed','unknown'),'mermaid':('drawn','unknown')}
@dataclass(frozen=True)
class Case:
    mode:str=''
    answer:str=''
    refused:str=''
CASES=tuple(Case(mode,answer) for mode,values in ANSWERS.items() for answer in values)+tuple(Case(refused=reason) for reason in ('conflict','no_map','no_target'))
@dataclass(frozen=True)
class State:
    mode:str=''
    refused:str=''
    shown:str=''
    component:str=''
    found:str=''
    review:str=''
    field:str=''
    diagram:str=''
    exit_code:int=0
class TakeFlags:
    name='TakeFlags'
    reads=()
    writes=('mode','refused')
    def __init__(self,defect=''):self.defect=defect
    def apply(self,event,state):
        mode=event.mode
        if self.defect=='conflict_runs_a_view' and event.refused=='conflict':mode='show'
        if self.defect=='reads_without_map' and event.refused=='no_map':mode='show'
        return (FunctionResult(event,replace(state,mode=mode,refused=event.refused)),)
class View:
    name='View'
    reads=('mode','refused')
    writes=('shown','component','found','review','field','diagram')
    def __init__(self,defect=''):self.defect=defect
    def apply(self,event,state):
        if not state.mode or self.defect=='mode_without_view' and state.mode=='mermaid':return (FunctionResult('',state),)
        value=event.answer or ANSWERS[state.mode][0]
        return (FunctionResult(value,replace(state,**{FIELDS[state.mode]:value}),label=value),)
class Exit:
    name='Exit'
    reads=('mode','refused','shown','component','found','review','field','diagram')
    writes=('exit_code',)
    def __init__(self,defect=''):self.defect=defect
    def apply(self,event,state):
        missing=state.refused=='no_target' or any(getattr(state,key) in ('unknown','no_owner','no_symbol') for key in FIELDS.values())
        code=2 if state.refused in ('conflict','no_map') else 1 if missing else 0
        if self.defect=='missing_subject_exits_zero' and missing:code=0
        if self.defect=='reads_without_map' and state.refused=='no_map':code=0
        return (FunctionResult(code,replace(state,exit_code=code)),)
RULES=(
 Invariant('one_view_per_read','one chosen view receives one answer; refusals receive none',lambda s,t:sum(bool(getattr(s,key)) for key in FIELDS.values())==(0 if s.refused else 1) and (not s.refused or not s.mode) and (s.refused!='conflict' or s.exit_code==2)),
 Invariant('missing_subject_exits_one','missing objects and targets exit one',lambda s,t:not (s.refused=='no_target' or any(getattr(s,key) in ('unknown','no_owner','no_symbol') for key in FIELDS.values())) or s.exit_code==1),
 Invariant('project_without_map_is_refused','a mapless project exits two before any view',lambda s,t:s.refused!='no_map' or not s.mode and s.exit_code==2),
)
def make(defect=''):return Explorer(Workflow((TakeFlags(defect),View(defect),Exit(defect))),(State(),),CASES,invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer():return make()
def broken_variants():return {name:make(name) for name in ('conflict_runs_a_view','mode_without_view','missing_subject_exits_zero','reads_without_map')}
def conformance():
    from _read_dispatch_fixture import fixture,call
    from flowguard.__main__ import _verb_parser
    facts=[]
    offered={action.dest for action in _verb_parser('read')._actions}-{'root','target','help'}|{'show'}
    declared=set(DISPATCH['mode'])
    for flag in sorted(offered-declared):
        facts.append(Fact('unlisted_'+flag,False,f'read offers --{flag}, which DISPATCH does not list; add its view model as a branch of read_command (PARENT = "read_command") and list it in DISPATCH'))
    for flag in sorted(declared-offered):facts.append(Fact('unoffered_'+flag,False,f"DISPATCH lists '{flag}', which read does not offer"))
    with TemporaryDirectory(prefix='fg-read-dispatch-') as directory:
        root=Path(directory);fixture(root)
        for mode,args,first in (('show',(),'# '),('component',('--component','loans'),'# '),('find',('--find','loans'),''),('review',('--review',),'# '),('field',('--field','answer'),''),('mermaid',('--mermaid',),'flowchart TD')):
            code,text=call(root,*args)
            facts.append(Fact(mode,code==0 and bool(text) and text.startswith(first),text.splitlines()[0] if text else 'empty'))
        for name,args,expected in (('conflict',('--find','loans','--mermaid'),2),('no_target',('--target',),1)):
            code,text=call(root,*args);facts.append(Fact(name,code==expected and not text.startswith(('# ','flowchart TD')),text))
        empty=root/'no-map';empty.mkdir()
        code,text=call(empty);facts.append(Fact('no_map',code==2 and not text.startswith('# '),text))
    return CodeFactsReport(tuple(facts))
