"""Ports check actual writes, outputs, receipts and orchestration in the model own traces."""
from pathlib import Path
from tempfile import TemporaryDirectory
from dataclasses import dataclass
from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
from _target_fixture import make_port_project, probe_port_model
MODEL_ID='port_checks'
PARENT = 'model_runs'
IMPLEMENTED_BY={'RunChecks': 'flowguard/map/port.py:run_findings'}
USES={'RunModel': 'flowguard/map/proof.py:run_model_in_process'}
TESTED_BY = {'undeclared_write_fails': ['tests/test_flowguard_port.py:test_undeclared_write_and_output_checks'], 'output_undeclared_fails': ['tests/test_flowguard_port.py:test_undeclared_write_and_output_checks'], 'handoff_value_received_into_field': ['tests/test_flowguard_port.py:test_handoff_value_must_be_received_as_an_event'], 'keeps_are_orchestration': ['tests/test_flowguard_port.py:test_keeps_classes_and_parent_outputs'], 'parent_output_from_child': ['tests/test_flowguard_port.py:test_keeps_classes_and_parent_outputs'], 'unreached_output_is_warned': ['tests/test_flowguard_port.py:test_undeclared_write_and_output_checks']}
@dataclass(frozen=True)
class Observation:
    case: str = ""
    correct: bool = True
    run_checks: str = "clean"
class Check:
    name="Check"
    reads=()
    writes=("case","correct","run_checks")
    def __init__(self,fault=""): self.fault=fault
    def apply(self,event,state):
        value=Observation(event,event!=self.fault and not (self.fault=="missing_receipt" and event=="wrong_receiving_field"),"clean" if event=="valid" else "warning" if event=="unreached_output" else "fail")
        return (FunctionResult(value.run_checks,value),)
RULES=(
    Invariant('undeclared_write_fails', 'undeclared write fails', lambda s,t: s.case != 'undeclared_write' or s.correct),
    Invariant('output_undeclared_fails', 'output undeclared fails', lambda s,t: s.case != 'undeclared_output' or s.correct),
    Invariant('handoff_value_received_into_field', 'handoff value received into field', lambda s,t: s.case not in ('missing_receipt','wrong_receiving_field') or s.correct),
    Invariant('keeps_are_orchestration', 'keeps are orchestration', lambda s,t: s.case != 'domain_keeps' or s.correct),
    Invariant('parent_output_from_child', 'parent output from child', lambda s,t: s.case != 'parent_output' or s.correct),
    Invariant('unreached_output_is_warned', 'unreached output is warned', lambda s,t: s.case != 'unreached_output' or s.correct),
)
def make(fault=""):
    return Explorer(Workflow((Check(fault),)),(Observation(),Observation(run_checks="fail")),('valid', 'undeclared_write', 'undeclared_output', 'missing_receipt', 'wrong_receiving_field', 'domain_keeps', 'parent_output', 'unreached_output'),invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer(): return make()
def broken_variants(): return {name:make(case) for name,case in (('trusts_declared_writes', 'undeclared_write'), ('accepts_undeclared_output', 'undeclared_output'), ('accepts_atom_anywhere_in_state', 'missing_receipt'), ('accepts_domain_field_in_keeps', 'domain_keeps'), ('accepts_parent_computed_output', 'parent_output'), ('silent_on_unreached_output', 'unreached_output'))}
def conformance():
    facts=[]
    for case,mid,code,warning in CASES:
        with TemporaryDirectory(prefix="fg-port-runtime-") as directory:
            root=Path(directory); make_port_project(root,case)
            result=probe_port_model(root,mid)
            lines=result.warnings if warning else result.problems
            facts.append(Fact(case, any(code in line for line in lines) and (result.status=="pass" if warning else result.status=="fail"),repr(result)))
    return CodeFactsReport(tuple(facts))
CASES=(('undeclared_write', 'desk', 'undeclared_write', False), ('undeclared_output', 'lending', 'output_undeclared', False), ('missing_receipt', 'desk', 'handoff_output_unhandled', False), ('domain_keeps', 'desk', 'keeps_not_orchestration', False), ('parent_output', 'desk', 'parent_output_not_from_child', False), ('unreached_output', 'lending', 'output_unreached', True))

CASES = CASES + (("wrong_receiving_field","desk","handoff_output_unhandled",False),)

COMPONENTS = ['map-file']

OUTPUTS = {'run_checks': ('clean', 'fail', 'warning')}
