"""Function ownership narrows edits; unknown source and missing git remain conservative."""
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from flowguard import FunctionResult,Invariant,Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport,Fact
from _function_fixture import native_case
from _selection_fixture import ALL
MODEL_ID='function_selection'
PARENT = 'change_selection'
COMPONENTS = ['map-inventory']
IMPLEMENTED_BY = {'Digests': 'flowguard/map/inventory.py:function_digests'}
USES={'Impact':'flowguard/map/impact.py:compute_impact'}
TESTED_BY = {'function_edit_selects_the_owner': ['tests/test_function_selection.py:test_owned_edit_does_not_select_composing_parent'], 'binding_change_follows_importers': ['tests/test_function_selection.py:test_module_binding_change_selects_importer_functions'], 'uncertain_edit_falls_back_broad': ['tests/test_function_selection.py:test_removed_function_is_uncertain'], 'no_git_uses_stale_components': ['tests/test_function_selection.py:test_no_git_uses_stale_components'], 'relied_models_selected': ['tests/test_function_selection.py:test_change_selects_models_whose_anchors_the_edit_calls'], 'flow_models_selected': ['tests/test_function_selection.py:test_change_selects_the_model_of_a_flow_whose_step_changed'], 'unexplained_functions_listed': ['tests/test_function_selection.py:test_change_lists_unexplained_functions_of_changed_files']}
@dataclass(frozen=True)
class Observation:
    case:str=''
    correct:bool=True
    literals:str='none'
    code:str='none'
    selected_models:tuple=()
    relied:tuple=()
    unexplained:tuple=()
    @property
    def event(self): return self.case
class Select:
    name='Select'
    reads=('literals',)
    writes=('case','correct','code','selected_models','relied','unexplained')
    def __init__(self,defect=''): self.defect=defect
    def apply(self,event,state):
        wrong={'selects_whole_component':'body','selects_composing_parent':'helper','ignores_importer_of_changed_name':'binding','removed_symbol_selects_nothing':'removed','no_git_selects_every_test_file':'no_git'}
        models=('child',) if event in ('caller_edit','flow_step_edit') else ()
        relied=tuple(mid+' via core:work' for mid in ALL) if event=='caller_edit' else ()
        unexplained=('jobs: jobs.py:run (entrypoint)',) if event=='flow_step_edit' else ()
        if self.defect=='ignore_relied_models' and event=='caller_edit': relied=()
        if self.defect=='ignore_flow_models' and event=='flow_step_edit': models=()
        if self.defect=='hides_unexplained' and event=='flow_step_edit': unexplained=()
        code='uncertain' if event in ('removed','no_git') else 'unreached' if event=='unreached' else 'none' if event=='none' else 'functions'
        result=replace(state,case=event,correct=wrong.get(self.defect)!=event,code=code,selected_models=models,relied=relied,unexplained=unexplained)
        return (FunctionResult(result.code,result),)
def _rule(name, relevant, predicate, message):
    from flowguard import InvariantResult
    return Invariant(name, message, lambda state, trace:
                     InvariantResult.pass_() if state.event not in relevant or predicate(state)
                     else InvariantResult.fail(message))
RULES = (
    Invariant('function_edit_selects_the_owner','owned edits and reachable helpers select the closest model',lambda s,t:s.case not in ('body','helper') or s.correct),
    Invariant('binding_change_follows_importers','changed module bindings select importer functions',lambda s,t:s.case!='binding' or s.correct),
    Invariant('uncertain_edit_falls_back_broad','deletion is explicitly uncertain and conservatively selected',lambda s,t:s.case!='removed' or s.correct),
    Invariant('no_git_uses_stale_components','without git use stale component files, not every test',lambda s,t:s.case!='no_git' or s.correct),
    _rule("relied_models_selected", {"caller_edit"}, lambda state: state.selected_models == ("child",) and set(mid+" via core:work" for mid in ALL) <= set(state.relied),
          "relied models are printed; only the directly edited flow selects child"),
    _rule("flow_models_selected", {"flow_step_edit"}, lambda state: "child" in state.selected_models,
          "the model of a flow whose step changed was omitted"),
    _rule("unexplained_functions_listed", {"flow_step_edit"},
          lambda state: "jobs: jobs.py:run (entrypoint)" in state.unexplained,
          "an unexplained entrypoint of the changed file was not listed"),
)

CASES=('body','helper','binding','removed','no_git')
EXTRA_CASES=('caller_edit','flow_step_edit','unreached','none')
def make(defect=''): return Explorer(Workflow((Select(defect),)),tuple(Observation(literals=x,code=y) for x in ('sites','too_common','none') for y in ('none','functions')),CASES+EXTRA_CASES,invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer(): return make()
def broken_variants(): return {name:make(name) for name in ('selects_whole_component','selects_composing_parent','ignores_importer_of_changed_name','removed_symbol_selects_nothing','no_git_selects_every_test_file','ignore_relied_models','ignore_flow_models','hides_unexplained')}
def _original_conformance():
    from flowguard.map import inventory
    from flowguard.map.impact import render_impact
    facts=[]
    for case in CASES:
        with TemporaryDirectory(prefix='fg-function-') as directory:
            try:
                result=native_case(Path(directory),case)
            except RuntimeError as exc:
                if case!='no_git': raise
                facts.append(Fact(case,False,str(exc)));continue
            text=render_impact(result)
            correct=(result.model_ids==['child'] if case in ('body','helper') else 'importer' in result.model_ids if case=='binding' else bool(result.model_ids) and 'UNCERTAIN:' in text if case=='removed' else 'NO GIT:' in text and result.tests==['tests/test_core.py'])
            if case=='body':
                digests=getattr(inventory,'function_digests',None)
                correct=correct and digests is not None and bool(digests('def f(): return 1'))
            facts.append(Fact(case,correct,text))
    return CodeFactsReport(tuple(facts))










def conformance():
    from _selection_fixture import observe_case, EXPECTED
    facts=list(_original_conformance().facts)
    for event in ('caller_edit','flow_step_edit'):
        with TemporaryDirectory(prefix='fg-function-source-') as directory:
            result=observe_case(Path(directory),event)
            valid=result.selected_models==EXPECTED[event][0]
            valid &= (set(mid+' via core:work' for mid in ALL)<=set(result.relied) if event=='caller_edit' else 'jobs: jobs.py:run (entrypoint)' in result.unexplained)
            facts.append(Fact(event,bool(valid),repr(result)))
    return CodeFactsReport(tuple(facts))

OUTPUTS = {'code': ('functions', 'uncertain', 'unreached', 'none')}

READS_PARENT = ('literals',)
