"""Selected model bindings and actual direct test calls choose test function nodes."""
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from flowguard import FunctionResult,Invariant,Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport,Fact
from flowguard.map import impact as native
from flowguard.map.common import DEFAULT_IGNORE
from flowguard.map.inventory import build_inventory
from flowguard.map.tree import build_tree
from flowguard.map.testtree import test_calls
from _function_fixture import fixture,write
MODEL_ID='test_selection'
PARENT='map-impact'
IMPLEMENTED_BY={'SelectTests':'flowguard/map/impact.py:select_tests'}
USES={'TestCalls':'flowguard/map/testtree.py:test_calls'}
TESTED_BY = {'bound_tests_follow_selected_models': ['tests/test_test_selection.py:test_parametrized_anchor_selects_its_case_only'], 'calling_tests_selected_by_direct_call': ['tests/test_test_selection.py:test_test_calling_through_same_file_helper_is_selected'], 'half_selected_file_runs_whole': ['tests/test_test_selection.py:test_half_selected_file_runs_whole'], 'also_reached_is_counted': ['tests/test_test_selection.py:test_cli_test_reaching_through_main_is_counted_as_also_reached']}
@dataclass(frozen=True)
class Observation:
    case:str=''
    correct:bool=True
class Select:
    name='Select'
    def __init__(self,defect=''): self.defect=defect
    def apply(self,event,state):
        wrong={'runs_whole_test_files':'bound','misses_calling_test':'calling','splits_a_half_selected_file':'half','hides_indirect_tests':'indirect'}
        result=Observation(event,wrong.get(self.defect)!=event)
        return (FunctionResult(result.correct,result),)
RULES=(
 Invariant('bound_tests_follow_selected_models','bindings select actual test nodes',lambda s,t:s.case!='bound' or s.correct),
 Invariant('calling_tests_selected_by_direct_call','direct calls and one local helper are selected',lambda s,t:s.case!='calling' or s.correct),
 Invariant('half_selected_file_runs_whole','half or more of a file runs the whole file',lambda s,t:s.case!='half' or s.correct),
 Invariant('also_reached_is_counted','indirect project calls are counted separately',lambda s,t:s.case!='indirect' or s.correct),
)
def make(defect=''): return Explorer(Workflow((Select(defect),)),(Observation(),),('bound','calling','half','indirect'),invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer(): return make()
def broken_variants(): return {name:make(name) for name in ('runs_whole_test_files','misses_calling_test','splits_a_half_selected_file','hides_indirect_tests')}
def conformance():
    with TemporaryDirectory(prefix='fg-test-selection-') as directory:
        root=Path(directory);data=fixture(root)
        write(root,'core.py',(root/'core.py').read_text().replace('def other(): return 2','def other(): return own()+1'))
        write(root,'tests/test_half.py','from core import own\ndef test_one(): assert own()\ndef test_two(): pass\n')
        inv=build_inventory(root,DEFAULT_IGNORE,write_cache=False)
        calls=test_calls('tests/test_core.py',(root/'tests/test_core.py').read_text(),inv)
        select=getattr(native,'select_tests',None)
        if select is None: return CodeFactsReport((Fact('missing_select_tests',False,repr(calls)),))
        result=select(root,data,inv,build_tree(root,data,inv),{'child'},{'core.py#own'})
        nodes=result['nodes'];whole=result['whole_files']
        return CodeFactsReport((
            Fact('bound','test_bound' in nodes.get('tests/test_core.py',()),repr(result)),
            Fact('calling',{'test_call','test_help'}<=set(nodes.get('tests/test_core.py',())),repr(result)),
            Fact('half','tests/test_half.py' in whole,repr(result)),
            Fact('indirect',bool(result['also_reached']),repr(result)),
        ))
