"""Combine source receipts in order into one conservative change selection."""
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
MODEL_ID='change_selection'
PARENT='map-impact'
IMPLEMENTED_BY={'Impact':'flowguard/map/impact.py:compute_impact'}
OUTPUTS={'selection':('selected','broad','blocked','nothing')}
HANDOFF={'literal_consumers':{'literals':'literals'},'function_selection':{'code':'code'},'test_selection':{'tests':'tests'},'port_escalation':{'port':'port'}}
KEEPS=('edit','selection')
@dataclass(frozen=True)
class Case:
    edit:str
    literals:str='none'
    code:str='none'
    tests:str='none'
    port:str='none'
CASES=(Case('comment'),Case('code',code='functions',tests='functions'),Case('code','sites','functions','functions'),Case('code','too_common','uncertain','whole_files'),Case('code',code='uncertain',tests='whole_files'),Case('code',code='unreached'),Case('code',tests='functions'),Case('model',port='unchanged',tests='functions'),Case('model',port='escalated',tests='functions'),Case('model',port='uncertain',tests='whole_files'),Case('helper',code='functions',tests='functions',port='escalated'),Case('helper'),Case('missing_model'),Case('test_file',tests='functions'),Case('test_file',tests='whole_files'))
@dataclass(frozen=True)
class State:
    edit:str=''
    literals:str='none'
    code:str='none'
    tests:str='none'
    port:str='none'
    selection:str='nothing'
class TakeEdit:
    name='TakeEdit'
    reads=()
    writes=('edit',)
    def apply(self,event,state): return (FunctionResult(event,replace(state,edit=event.edit)),)
class SourceLiterals:
    name='SourceLiterals'
    reads=('edit',)
    writes=('literals',)
    def apply(self,event,state):
        return (FunctionResult(event,replace(state,literals=event.literals),label=event.literals),) if state.edit!='comment' else (FunctionResult(event,state,label='skipped'),)
class SourceCode:
    name='SourceCode'
    reads=('edit','literals')
    writes=('code',)
    def apply(self,event,state):
        return (FunctionResult(event,replace(state,code=event.code),label=event.code),) if state.edit!='comment' else (FunctionResult(event,state,label='skipped'),)
class SourceTests:
    name='SourceTests'
    reads=('edit','code')
    writes=('tests',)
    def apply(self,event,state):
        return (FunctionResult(event,replace(state,tests=event.tests),label=event.tests),) if state.edit!='comment' else (FunctionResult(event,state,label='skipped'),)
class SourcePort:
    name='SourcePort'
    reads=('edit',)
    writes=('port',)
    def apply(self,event,state):
        return (FunctionResult(event,replace(state,port=event.port),label=event.port),) if state.edit!='comment' else (FunctionResult(event,state,label='skipped'),)
class Select:
    name='Select'
    reads=('edit','literals','code','tests','port')
    writes=('selection',)
    def __init__(self,defect=''):self.defect=defect
    def apply(self,event,state):
        uncertain=state.code=='uncertain' or state.port=='uncertain' or state.literals=='too_common'
        selected=state.code=='functions' or state.tests!='none' or state.port in ('escalated','unchanged')
        value='nothing' if state.edit=='comment' else 'blocked' if state.edit=='missing_model' else 'broad' if uncertain else 'selected' if selected else 'nothing'
        if self.defect=='select_comments' and state.edit=='comment':value='selected'
        if self.defect=='block_helper' and state.edit=='helper':value='blocked'
        if self.defect=='ignores_uncertain_source' and uncertain:value='selected'
        if self.defect=='runs_missing_model' and state.edit=='missing_model':value='selected'
        return (FunctionResult(value,replace(state,selection=value)),)
RULES=(
 Invariant('comments_select_no_checks','a comment-only edit selects no checks',lambda s,t:s.edit!='comment' or s.selection=='nothing'),
 Invariant('underscore_helper_not_blocked','an underscore helper is not blocked',lambda s,t:s.edit!='helper' or s.selection!='blocked'),
 Invariant('literal_sites_reach_function_selection','literal receipts precede function selection',lambda s,t:all(step.function_name!='SourceCode' or step.old_state.edit=='comment' or step.old_state.literals==step.function_input.literals for step in t.steps)),
 Invariant('uncertain_source_broadens_selection','uncertainty broadens selection',lambda s,t:s.edit in ('comment','missing_model') or not (s.code=='uncertain' or s.port=='uncertain' or s.literals=='too_common') or s.selection=='broad'),
 Invariant('missing_selected_model_blocks','a missing selected model blocks execution',lambda s,t:s.edit!='missing_model' or s.selection=='blocked'),
)
def make(defect=''):
    sources=(SourceCode(),SourceLiterals(),SourceTests(),SourcePort()) if defect=='selects_functions_before_sites' else (SourceLiterals(),SourceCode(),SourceTests(),SourcePort())
    return Explorer(Workflow((TakeEdit(),*sources,Select(defect))),(State(),),CASES,invariants=RULES,max_sequence_length=2,progress_steps=0)
def build_explorer():return make()
def broken_variants():return {name:make(name) for name in ('select_comments','block_helper','selects_functions_before_sites','ignores_uncertain_source','runs_missing_model')}
def conformance():
    from _selection_fixture import observe_case, EXPECTED
    facts=[]
    for event,(models,tests) in EXPECTED.items():
        with TemporaryDirectory(prefix='fg-source-union-') as directory:
            result=observe_case(Path(directory),event)
            actual='blocked' if result.blocked else 'selected' if result.selected_models or result.selected_tests else 'nothing'
            expected='selected' if models or tests else 'nothing'
            facts.append(Fact(event,actual==expected and result.selected_models==models and result.selected_tests==tests,repr(result)))
    return CodeFactsReport(tuple(facts))

TESTED_BY = {'comments_select_no_checks': ['tests/test_change_selection.py:test_comment_only_edit_keeps_review_but_selects_no_checks'], 'underscore_helper_not_blocked': ['tests/test_change_selection.py:test_impact_shared_test_binding_and_unknown_helper'], 'literal_sites_reach_function_selection': ['tests/test_change_selection.py:test_removed_literal_sites_reach_function_selection'], 'uncertain_source_broadens_selection': ['tests/test_change_selection.py:test_uncertain_source_broadens_selection'], 'missing_selected_model_blocks': ['tests/test_change_selection.py:test_missing_selected_model_is_blocked']}
