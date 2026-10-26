"""Strict edges receive every child value, supply its inputs and give every parent field an owner."""
from pathlib import Path
from tempfile import TemporaryDirectory
from dataclasses import dataclass
from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
from _target_fixture import make_port_project, probe_port_model
MODEL_ID='edge_coverage'
PARENT="map-file"
IMPLEMENTED_BY={'EdgeChecks': 'flowguard/map/port.py:port_findings'}
USES={}
TESTED_BY = {'child_value_received': ['tests/test_flowguard_port.py:test_each_static_edge_mistake_has_its_code'], 'child_input_provided': ['tests/test_flowguard_port.py:test_each_static_edge_mistake_has_its_code'], 'parent_fields_covered': ['tests/test_flowguard_port.py:test_each_static_edge_mistake_has_its_code'], 'siblings_do_not_overlap': ['tests/test_flowguard_port.py:test_each_static_edge_mistake_has_its_code'], 'child_hands_a_value_up': ['tests/test_flowguard_port.py:test_each_static_edge_mistake_has_its_code']}
@dataclass(frozen=True)
class Observation:
    case: str = ""
    correct: bool = True
class Check:
    name="Check"
    reads=()
    writes=("case","correct")
    def __init__(self,fault=""): self.fault=fault
    def apply(self,event,state):
        value=Observation(event,event!=self.fault)
        return (FunctionResult(value.correct,value),)
RULES=(
    Invariant('child_value_received', 'child value received', lambda s,t: s.case != 'drops_child_value' or s.correct),
    Invariant('child_input_provided', 'child input provided', lambda s,t: s.case != 'missing_parent_input' or s.correct),
    Invariant('parent_fields_covered', 'parent fields covered', lambda s,t: s.case != 'uncovered_parent_field' or s.correct),
    Invariant('siblings_do_not_overlap', 'siblings do not overlap', lambda s,t: s.case != 'overlapping_receipts' or s.correct),
    Invariant('child_hands_a_value_up', 'child hands a value up', lambda s,t: s.case != 'no_child_output' or s.correct),
)
def make(fault=""):
    return Explorer(Workflow((Check(fault),)),(Observation(),),('drops_child_value', 'missing_parent_input', 'uncovered_parent_field', 'overlapping_receipts', 'no_child_output'),invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer(): return make()
def broken_variants(): return {name:make(case) for name,case in (('accepts_value_mapped_to_none', 'drops_child_value'), ('accepts_missing_parent_field', 'missing_parent_input'), ('ignores_uncovered_parent_field', 'uncovered_parent_field'), ('accepts_two_children_one_field', 'overlapping_receipts'), ('accepts_child_without_outputs', 'no_child_output'))}
def conformance():
    from flowguard.map.tree import build_tree
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    facts=[]
    for case,code in CASES:
        with TemporaryDirectory(prefix="fg-port-edge-") as directory:
            root=Path(directory);data=make_port_project(root,case)
            inv=build_inventory(root,DEFAULT_IGNORE,write_cache=False)
            tree=build_tree(root,data,inv)
            facts.append(Fact(case,any(f.code==code and f.level=="error" for f in tree.findings),repr(tree.findings)))
    return CodeFactsReport(tuple(facts))
CASES=(('drops_child_value', 'handoff_drops_child_value'), ('missing_parent_input', 'child_input_unprovided'), ('uncovered_parent_field', 'parent_field_uncovered'), ('overlapping_receipts', 'sibling_outputs_overlap'), ('no_child_output', 'child_unconnected'))
