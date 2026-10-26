"""Only changed interfaces escalate a model edit to its direct consumers."""
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
from flowguard.map.common import DEFAULT_IGNORE
from flowguard.map.inventory import build_inventory
from flowguard.map.impact import compute_impact, render_impact
from _target_fixture import make_port_project

MODEL_ID = "port_escalation"
PARENT = 'change_selection'
IMPLEMENTED_BY = {"PortDelta": "flowguard/map/port.py:port_delta", "Escalation": "flowguard/map/port.py:escalation_set"}
USES = {"Impact": "flowguard/map/impact.py:compute_impact"}
TESTED_BY = {'port_unchanged_selects_child_only': ['tests/test_flowguard_port.py:test_rule_edit_selects_the_child_only'], 'output_change_selects_parent_and_consumers': ['tests/test_flowguard_port.py:test_output_change_selects_parent_not_grandparent'], 'reads_parent_change_selects_parent': ['tests/test_flowguard_port.py:test_reads_parent_change_selects_parent'], 'model_importers_selected': ['tests/test_port_escalation.py:test_change_selects_importers_and_ancestors_of_a_changed_model']}
CASES = ("rule", "output", "reads")
EXPECTED = {"rule": ("lending",), "output": ("consumer", "desk", "lending"), "reads": ("desk", "lending")}
@dataclass(frozen=True)
class Selection:
    case: str = ""
    models: tuple = ()
    port: str = 'none'
    @property
    def event(self): return self.case
    @property
    def selected_models(self): return self.models
class Select:
    name = 'Select'
    reads=()
    writes=('case','models','port')
    def __init__(self, defect=""): self.defect = defect
    def apply(self, event, state):
        models = EXPECTED[event] if event in EXPECTED else ('child','parent','review') if event in ('child','helper') else ()
        if self.defect == "selects_all_ancestors" and event == "rule": models = ("desk", "lending")
        if self.defect == "misses_handoff_consumer" and event == "output": models = ("desk", "lending")
        if self.defect == "ignores_reads_parent_change" and event == "reads": models = ("lending",)
        if self.defect=='ignore_importers' and event in ('child','helper'): models=tuple(x for x in models if x!='parent')
        port='unchanged' if event=='rule' else 'escalated' if event in ('output','reads','child','helper') else 'uncertain' if event=='uncertain' else 'none'
        return (FunctionResult(port, Selection(event, models, port)),)
def _rule(name, relevant, predicate, message):
    from flowguard import InvariantResult
    return Invariant(name, message, lambda state, trace:
                     InvariantResult.pass_() if state.event not in relevant or predicate(state)
                     else InvariantResult.fail(message))
RULES = (
    Invariant("port_unchanged_selects_child_only", "a rule edit stays in its model", lambda s,t: s.case != "rule" or s.models == EXPECTED["rule"]),
    Invariant("output_change_selects_parent_and_consumers", "output edits select the parent and every HANDOFF consumer", lambda s,t: s.case != "output" or s.models == EXPECTED["output"]),
    Invariant("reads_parent_change_selects_parent", "changed parent reads select the parent", lambda s,t: s.case != "reads" or s.models == EXPECTED["reads"]),
    _rule("model_importers_selected", {"child", "helper"}, lambda state: "parent" in state.selected_models,
          "the importing parent was omitted"),
)


def make(defect=""):
    return Explorer(Workflow((Select(defect),)), (Selection(),Selection(port='unchanged')), CASES+("child","helper","uncertain","none"), invariants=RULES, max_sequence_length=1, progress_steps=0)
def build_explorer(): return make()
def broken_variants(): return {name: make(name) for name in ("selects_all_ancestors", "misses_handoff_consumer", "ignores_reads_parent_change", "ignore_importers")}

def native_case(root, case):
    """Fresh git baseline; change the actual model bytes and run the real selector."""
    data = make_port_project(root)
    models = root / ".flowguard/models"
    consumer = models / "consumer.py"
    consumer.write_text('MODEL_ID="consumer"\nPARENT="cli"\nHANDOFF={"lending":{"answer":"seen"}}\ndef build_explorer(): pass\n')
    desk = models / "desk.py"
    desk.write_text(desk.read_text().replace('PARENT = "cli"', 'PARENT = "grand"'))
    (models / "grand.py").write_text('MODEL_ID="grand"\nPARENT="cli"\nOUTPUTS={}\ndef build_explorer(): pass\n')
    # A second consumer makes omission of HANDOFF detectable independently of PARENT.
    for args in (("init", "-q"), ("add", "."), ("-c", "user.name=FlowGuard", "-c", "user.email=model@example.invalid", "commit", "-qm", "baseline")):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
    path = models / "lending.py"
    source = path.read_text()
    source = source.replace('the lending result is finite', 'the lending result stays finite') if case == "rule" else source.replace('("lent","refused")}', '("lent","refused","waitlisted")}') if case == "output" else source.replace('READS_PARENT = ("request",)', 'READS_PARENT = ("request","answer")')
    path.write_text(source)
    impact = compute_impact(root, data, build_inventory(root, DEFAULT_IGNORE, write_cache=False), [".flowguard/models/lending.py"], base="HEAD")
    return impact, render_impact(impact)

def _original_conformance():
    facts = []
    for case in CASES:
        with TemporaryDirectory(prefix="fg-port-selection-") as directory:
            impact, text = native_case(Path(directory), case)
            expected_line = "port: lending unchanged (this model only)" if case == "rule" else "port changed: lending out +waitlisted -> verify desk (parent), consumer (HANDOFF)" if case == "output" else "port changed: lending reads +answer -> verify desk (parent)"
            facts.append(Fact(case, tuple(impact.model_ids) == EXPECTED[case] and expected_line in text, text))
    return CodeFactsReport(tuple(facts))





def conformance():
    from _selection_fixture import observe_case, EXPECTED as SOURCE_EXPECTED
    facts=list(_original_conformance().facts)
    for event in ('child','helper'):
        with TemporaryDirectory(prefix='fg-importers-') as directory:
            result=observe_case(Path(directory),event)
            facts.append(Fact(event,result.selected_models==SOURCE_EXPECTED[event][0],repr(result)))
    return CodeFactsReport(tuple(facts))

COMPONENTS = ['map-file']

OUTPUTS = {'port': ('unchanged', 'escalated', 'uncertain', 'none')}
