"""Every test has a static position; mixed or oversized files are named."""
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from flowguard import FunctionResult,Invariant,Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport,Fact
from _testtree_fixture import fixture
MODEL_ID='test_tree'
PARENT='map-file'
IMPLEMENTED_BY={'Positions':'flowguard/map/testtree.py:test_positions','Units':'flowguard/map/testtree.py:test_units','Calls':'flowguard/map/testtree.py:test_calls','FileFindings':'flowguard/map/testtree.py:test_file_findings'}
USES = {
    'BuildInventory': 'flowguard/map/inventory.py:build_inventory',
    'BuildTree': 'flowguard/map/tree.py:build_tree',
}
TESTED_BY={'bound_test_sits_at_its_model':['tests/test_flowguard_testtree.py:test_positions_on_a_fixture_tree'],
 'unbound_test_sits_where_its_calls_go':['tests/test_flowguard_testtree.py:test_positions_on_a_fixture_tree'],
 'mixed_test_file_is_named':['tests/test_flowguard_testtree.py:test_mixed_file_and_large_file_are_named'],
 'large_test_file_is_named':['tests/test_flowguard_testtree.py:test_mixed_file_and_large_file_are_named']}
@dataclass(frozen=True)
class State:
    case:str=''
    correct:bool=True
class Classify:
    name='Positions'
    writes=('case','correct')
    def __init__(self,bad=''):self.bad=bad
    def apply(self,event,state):
        wrong={'places_bound_test_at_file_component':'bound','places_by_file_listing_only':'free','silent_on_mixed_file':'mixed','silent_on_41_functions':'big'}
        return (FunctionResult(event,State(event,wrong.get(self.bad)!=event)),)
RULES=(Invariant('bound_test_sits_at_its_model','bound tests sit at the lowest common ancestor',lambda s,t:s.case!='bound' or s.correct),
       Invariant('unbound_test_sits_where_its_calls_go','unbound tests prefer the component their calls reach',lambda s,t:s.case!='free' or s.correct),
       Invariant('mixed_test_file_is_named','mixed files get the declared finding',lambda s,t:s.case!='mixed' or s.correct),
       Invariant('large_test_file_is_named','41 test functions get a soft size finding',lambda s,t:s.case!='big' or s.correct))
def make(bad=''):return Explorer(Workflow((Classify(bad),)),(State(),),('bound','free','mixed','big'),invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer():return make()
def broken_variants():return {name:make(name) for name in ('places_bound_test_at_file_component','places_by_file_listing_only','silent_on_mixed_file','silent_on_41_functions')}
def conformance():
    from flowguard.map import testtree
    from flowguard.map.tree import build_tree
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    with TemporaryDirectory(prefix='fg-test-tree-') as directory:
        root=Path(directory);data,nodeids=fixture(root);inv=build_inventory(root,DEFAULT_IGNORE,write_cache=False);tree=build_tree(root,data,inv)
        positions=getattr(testtree,'test_positions',lambda *args:{}) (root,data,inv,tree,nodeids)
        units=getattr(testtree,'test_units',lambda *args:{}) (root,data,inv,tree,nodeids,{node:1 for node in nodeids},2)
        calls=testtree.test_calls('tests/test_tree.py',(root/'tests/test_tree.py').read_text(),inv)
        findings=getattr(testtree,'test_file_findings',lambda *args:[]) (root,data,inv,tree)
        expected=('A','A','system','other')
        return CodeFactsReport((Fact('positions',tuple(positions.get(node) for node in nodeids)==expected,repr(positions)),
            Fact('units',bool(units),repr(units)),Fact('calls','b.py:run' in calls['test_free'],repr(calls)),
            Fact('mixed',any(f.code=='test_file_mixes_models' for f in findings),repr(findings)),
            Fact('big',any(f.code=='large_test_file' and f.component=='tests/test_big.py' for f in findings),repr(findings))))
