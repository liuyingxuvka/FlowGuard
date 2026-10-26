"""Function ownership narrows edits; unknown source and missing git remain conservative."""
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from flowguard import FunctionResult,Invariant,Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport,Fact
from _function_fixture import native_case
MODEL_ID='function_selection'
PARENT='map-inventory'
COMPONENTS=['map-inventory','map-impact','map-discover']
IMPLEMENTED_BY={'SelectModels':'flowguard/map/discover.py:select_model_functions','Digests':'flowguard/map/inventory.py:function_digests','NoGit':'flowguard/map/impact.py:_no_git_changes'}
USES={'Impact':'flowguard/map/impact.py:compute_impact'}
TESTED_BY={
 'function_edit_selects_the_owner':['tests/test_flowguard_map.py:test_owned_edit_does_not_select_composing_parent'],
 'binding_change_follows_importers':['tests/test_flowguard_map.py:test_module_binding_change_selects_importer_functions'],
 'uncertain_edit_falls_back_broad':['tests/test_flowguard_map.py:test_removed_function_is_uncertain'],
 'no_git_uses_stale_components':['tests/test_flowguard_map.py:test_no_git_uses_stale_components'],
}
@dataclass(frozen=True)
class Observation:
    case:str=''
    correct:bool=True
class Select:
    name='Select'
    def __init__(self,defect=''): self.defect=defect
    def apply(self,event,state):
        wrong={'selects_whole_component':'body','selects_composing_parent':'helper','ignores_importer_of_changed_name':'binding','removed_symbol_selects_nothing':'removed','no_git_selects_every_test_file':'no_git'}
        result=Observation(event,wrong.get(self.defect)!=event)
        return (FunctionResult(result.correct,result),)
RULES=(
 Invariant('function_edit_selects_the_owner','owned edits and reachable helpers select the closest model',lambda s,t:s.case not in ('body','helper') or s.correct),
 Invariant('binding_change_follows_importers','changed module bindings select importer functions',lambda s,t:s.case!='binding' or s.correct),
 Invariant('uncertain_edit_falls_back_broad','deletion is explicitly uncertain and conservatively selected',lambda s,t:s.case!='removed' or s.correct),
 Invariant('no_git_uses_stale_components','without git use stale component files, not every test',lambda s,t:s.case!='no_git' or s.correct),
)
CASES=('body','helper','binding','removed','no_git')
def make(defect=''): return Explorer(Workflow((Select(defect),)),(Observation(),),CASES,invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer(): return make()
def broken_variants(): return {name:make(name) for name in ('selects_whole_component','selects_composing_parent','ignores_importer_of_changed_name','removed_symbol_selects_nothing','no_git_selects_every_test_file')}
def conformance():
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
