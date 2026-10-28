"""Placement, composition and consumption stay distinct; hubs and ripples are computed from source."""
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from flowguard import FunctionResult,Invariant,Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport,Fact
from _relation_fixture import fixture
MODEL_ID='relation_graph'
PARENT='map-read'
IMPLEMENTED_BY={'Relations':'flowguard/map/views.py:relations'}
USES={'Show':'flowguard/map/views.py:render_show','Mermaid':'flowguard/map/views.py:render_mermaid','Review':'flowguard/map/review.py:render_review','Escalation':'flowguard/map/port.py:escalation_set'}
TESTED_BY = {'one_kind_per_edge': ['tests/test_relation_graph.py:test_three_relation_kinds_are_shown_distinctly'], 'views_show_kinds_distinctly': ['tests/test_relation_graph.py:test_three_relation_kinds_are_shown_distinctly'], 'hub_listed_at_threshold': ['tests/test_relation_graph.py:test_hubs_are_listed_at_the_thresholds', 'tests/test_relation_graph.py:test_caller_only_hubs_share_one_line'], 'ripple_is_the_escalation_set': ['tests/test_relation_graph.py:test_ripple_is_the_escalation_set']}
EXPECTED={'placed':('placement',False,0),'stage':('stage',False,1),'branch':('branch x',False,1),'two_consumers':('consumption',True,2),'many_callers':('placement',True,0),'ordinary':('placement',False,1),'reading_parent':('stage',False,4),'consumed_child':('stage',True,2)}
@dataclass(frozen=True)
class State:
    case:str=''
    kind:str=''
    hub:bool=False
    ripple:int=0
    shown:bool=True
class Classify:
    name='Relations'
    writes=('case','kind','hub','ripple','shown')
    def __init__(self,defect=''):self.defect=defect
    def apply(self,event,state):
        kind,hub,ripple=EXPECTED[event]
        if self.defect=='consumer_shown_as_child' and event=='two_consumers':kind='stage'
        if self.defect=='hub_not_listed' and event=='many_callers':hub=False
        if self.defect=='ripple_misses_the_parent' and event=='consumed_child':ripple=1
        value=State(event,kind,hub,ripple,not(self.defect=='mermaid_child_drawn_as_placement' and event=='stage'))
        return (FunctionResult(kind,value),)
RULES=(
 Invariant('one_kind_per_edge','each edge has exactly its declared relation kind',lambda s,t:not s.case or s.kind==EXPECTED[s.case][0]),
 Invariant('views_show_kinds_distinctly','read and Mermaid use distinct relation forms',lambda s,t:s.shown),
 Invariant('hub_listed_at_threshold','model hubs appear at 2 consumers or 8 callers',lambda s,t:not s.case or s.hub==EXPECTED[s.case][1]),
 Invariant('ripple_is_the_escalation_set','ripple uses the ordered escalation owner',lambda s,t:not s.case or s.ripple==EXPECTED[s.case][2]),
)
def make(defect=''):return Explorer(Workflow((Classify(defect),)),(State(),),tuple(EXPECTED),invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer():return make()
def broken_variants():return {name:make(name) for name in ('consumer_shown_as_child','mermaid_child_drawn_as_placement','hub_not_listed','ripple_misses_the_parent')}
def conformance():
    from flowguard.map import views
    from flowguard.map.review import render_review
    from flowguard.map.port import escalation_set
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.tree import build_tree
    from flowguard.map.discover import discover_inventory
    with TemporaryDirectory(prefix='fg-relations-') as directory:
        root=Path(directory);data=fixture(root);inv=build_inventory(root,DEFAULT_IGNORE,write_cache=False);tree=build_tree(root,data,inv);raw=discover_inventory(root,inv,data=data,write_cache=False)
        function=getattr(views,'relations',None);actual=function(root,data,inv,tree,raw) if function else None
        from _read_fixture import show_view
        show=show_view(root,data,inv,component=None,detail=False);mermaid=views.render_mermaid(root,data,inv);review=render_review(root,data,inv)
        ports={mid:node.contract['port'] for mid,node in tree.nodes.items()}
        ripple=escalation_set('T',tree,ports)
        facts=[Fact('views','stage children:' in show and 'branch children:' in show and 'consumes: P.value -> value' in show and 'm_desk ==> m_lending' in mermaid and 'm_cmd ==>|"x"| m_a' in mermaid and 'm_P --o|"value"| m_K1' in mermaid,show+'\n'+mermaid)]
        if actual is None:facts.append(Fact('relations',False,'relations is absent'))
        else:
            facts.extend((Fact('placement',('extra','W') in actual.placement,repr(actual.placement)),Fact('hub',actual.hub['P'] and actual.hub['Q'] and actual.hub['Q8'] and not actual.hub['R'],review),Fact('ripple',actual.ripple['T']==ripple and ripple==[('V','parent'),('KT','HANDOFF')],repr(actual.ripple)),Fact('reading_parent',len(actual.ripple['U'])==4,repr(actual.ripple['U'])),Fact('review','hubs:' in review and 'most called:' in review and 'Q8 (8 code callers' in review,review)))
        return CodeFactsReport(tuple(facts))
