"""Mermaid preserves distinct node identities, dependencies, flows and target marks without importing models."""
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
import re
from flowguard import FunctionResult,Invariant,Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport,Fact
MODEL_ID='read_mermaid'
PARENT='read_command'
IMPLEMENTED_BY={'Mermaid':'flowguard/map/views.py:render_mermaid'}
USES={'Facets':'flowguard/map/facets.py:component_facets'}
OUTPUTS={'diagram':('drawn','unknown')}
TESTED_BY = {'mermaid_view_imports_no_model': ['tests/test_map_views.py:test_mermaid_draws_dependencies_and_flows'], 'one_node_per_component_and_model': ['tests/test_map_views.py:test_mermaid_export_has_one_node_per_component_and_model'], 'dependencies_and_flows_drawn': ['tests/test_map_views.py:test_mermaid_draws_dependencies_and_flows'], 'target_changes_marked': ['tests/test_flowguard_target.py:test_read_target_added_removed_flows_and_mermaid_use_real_node_identity']}
@dataclass(frozen=True)
class State:
    diagram:str='drawn'
    imported:bool=False
    identities:bool=True
    flows:bool=True
    marks:bool=True
class Draw:
    name='Draw'
    reads=()
    writes=('diagram','imported','identities','flows','marks')
    def __init__(self,defect=''):self.defect=defect
    def apply(self,event,state):
        result=State('unknown' if event=='unknown' else 'drawn',self.defect=='mermaid_view_imports_a_model',not (event=='collision' and self.defect=='merges_sanitized_names'),not (event=='flows' and self.defect=='drops_flow_steps'),not (event=='target' and self.defect=='marks_by_sanitized_name'))
        return (FunctionResult(result.diagram,result),)
RULES=(
 Invariant('mermaid_view_imports_no_model','drawing imports no project model',lambda s,t:not s.imported),
 Invariant('one_node_per_component_and_model','sanitized names retain distinct identities',lambda s,t:s.identities),
 Invariant('dependencies_and_flows_drawn','dependencies and every flow step are drawn',lambda s,t:s.flows),
 Invariant('target_changes_marked','target marks use real node identity',lambda s,t:s.marks),
)
def make(defect=''):return Explorer(Workflow((Draw(defect),)),(State(),State(diagram='unknown')),('drawn','unknown','collision','flows','target'),invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer():return make()
def broken_variants():return {name:make(name) for name in ('mermaid_view_imports_a_model','merges_sanitized_names','drops_flow_steps','marks_by_sanitized_name')}
def conformance():
    from _read_dispatch_fixture import fixture,answers,call,imported
    from _target_fixture import write_json
    facts=[]
    with TemporaryDirectory(prefix='fg-mermaid-') as directory:
        root=Path(directory);data=fixture(root)
        for value,valid,text in answers(root,'mermaid'):facts.append(Fact(value,valid and not imported(root),text))
        code,text=call(root,'--mermaid')
        facts.append(Fact('flows',code==0 and 'c_cli -.-> c_loans' in text and 'f_borrow -->|"1"| c_cli' in text and 'f_borrow -->|"2"| c_loans' in text,text))
        # IDs that sanitize alike still each get a separate definition.
        for cid in ('a-b','a.b'):
            data['components'].append(dict(id=cid,layer='interface',summary=cid,responsibilities=[],files=[],tests=[],depends_on=[],status='draft'))
        write_json(root/'.flowguard/map.json',data)
        code,text=call(root,'--mermaid')
        nodes=re.findall(r'^\s*(c_a_b\w*)\[',text,re.M)
        facts.append(Fact('collision',code==0 and len(nodes)==len(set(nodes))==2,text))
        path=root/'.flowguard/target';path.mkdir()
        write_json(path/'map.json',dict(schema='flowguard.target.v1',goal='replace a collision node',components=[dict(id='a_b',layer='interface',summary='new',responsibilities=['show new collision node'],files=[],tests=[],depends_on=[])],flows=[],remove=['component:a-b']))
        code,text=call(root,'--target','--mermaid')
        facts.append(Fact('target',code==0 and re.search(r'class c_a_b\w* removed',text) is not None and re.search(r'class c_a_b\w* added',text) is not None and not imported(root),text))
    return CodeFactsReport(tuple(facts))
