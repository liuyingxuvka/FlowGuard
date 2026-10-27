"""Focused component reads show one concise port line for each model."""
from pathlib import Path
from tempfile import TemporaryDirectory
from dataclasses import dataclass, replace
from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
from _target_fixture import make_port_project, probe_port_model
BASE_RULES = (Invariant('port_line_shown', 'one concise port per model', lambda s, t: s),)

class Read:
    name = 'Read'

    def __init__(self, bad=False):
        self.bad = bad

    def apply(self, event, state):
        return (FunctionResult(not self.bad, not self.bad),)

def _native_explorer(bad=False):
    return Explorer(Workflow((Read(bad),)), (True,), ('read',), invariants=BASE_RULES, max_sequence_length=1, progress_steps=0)

def base_build():
    return _native_explorer()

def base_variants():
    return {'hides_port_line': _native_explorer(True)}

def base_conformance():
    from flowguard.map.inventory import build_inventory
    from flowguard.map.views import render_show
    from flowguard.map.common import DEFAULT_IGNORE
    with TemporaryDirectory(prefix='fg-component-port-') as directory:
        root = Path(directory)
        data = make_port_project(root)
        inv = build_inventory(root, DEFAULT_IGNORE, write_cache=False)
        text = render_show(root, data, inv, component='cli', detail=False, budget=8000)
        ports = [line.strip() for line in text.splitlines() if line.strip().startswith('port:')]
        models = [line for line in text.splitlines() if line.strip().startswith('model ')]
        return CodeFactsReport((Fact('ports_shown', len(ports) == len(models) and len(ports) >= 2 and all((len(line) <= 200 for line in ports)), text),))

from _read_fixture import ReadCase, JointState, Bridge, legacy_cases, legacy_conformance, _abstract
from _read_fixture import _flows, _focused, _layer_order, _model_contract, _names, _ranked, _recipes, _relied, _static, _summary, _true_strengths, _word_forms
MODEL_ID='read_component'
PARENT = 'read_command'
IMPLEMENTED_BY={'Facets': 'flowguard/map/facets.py:component_facets'}
USES={'Show': 'flowguard/map/views.py:render_show'}
TESTED_BY = {'port_line_shown': ['tests/test_read_component.py:test_read_component_prints_one_port_line_per_model'], 'focused_component_visible': ['tests/test_read_component.py:test_read_component_never_hides_the_requested_component'], 'relied_rules_shown': ['tests/test_read_component.py:test_read_component_lists_the_rules_it_relies_on'], 'component_flows_shown': ['tests/test_read_component.py:test_read_component_lists_its_flows_and_their_rules'], 'static_rules_match_model': ['tests/test_read_component.py:test_static_rules_follow_helpers_and_wrappers', 'tests/test_read_component.py:test_static_known_bad_follow_loops_and_tuple_targets', 'tests/test_read_component.py:test_kit_model_facets_are_static_and_complete'], 'component_view_imports_no_model': ['tests/test_read_command.py:test_read_component_names_the_symbols_used_on_each_edge'], 'component_view_within_budget': ['tests/test_read_component.py:test_read_component_never_hides_the_requested_component']}
NOT_MODELED={'flowguard/map/modelstatic.py:StaticModel._module': 'memoizes one parsed helper file per read; the names it yields are what static_rules_match_model checks on real render_show output', 'flowguard/map/modelstatic.py:StaticModel.explorer_rules': 'remembers the kit case table found while reading rules; the cases line is checked by static_rules_match_model through the kit probe', 'flowguard/map/modelstatic.py:StaticModel._defined': "records the AST of each rule's defining call so goal rules can compare versions; tests/test_flowguard_target.py:test_behaviour_target_without_a_rule_is_untied checks that line", 'flowguard/map/modelstatic.py:StaticModel.bad_keys': 'collects known-bad names written by loops and comprehensions; tests/test_map_views.py:test_static_known_bad_follow_loops_and_tuple_targets checks them'}
MOVED_RULES=(
Invariant('static_rules_match_model', "static rule and known-bad names and counts equal the model's explorer and variants", lambda state, trace: _static(state)),
Invariant('relied_rules_shown', "read --component X lists the other components' model rules X's code calls", lambda state, trace: _relied(state)),
Invariant('component_flows_shown', 'read --component X lists the flows that have a step in X, with model and rules', lambda state, trace: _flows(state)),
Invariant('focused_component_visible', "read --component X fits the budget and always shows X's heading and five facets", lambda state, trace: _focused(state) and len(state.text) <= state.case.budget),
)
RULES = (
Invariant('port_line_shown', 'one concise port per model', lambda s, t: s),
Invariant('static_rules_match_model', "static rule and known-bad names and counts equal the model's explorer and variants", lambda state, trace: _static(state)),
Invariant('relied_rules_shown', "read --component X lists the other components' model rules X's code calls", lambda state, trace: _relied(state)),
Invariant('component_flows_shown', 'read --component X lists the flows that have a step in X, with model and rules', lambda state, trace: _flows(state)),
Invariant('focused_component_visible', "read --component X fits the budget and always shows X's heading and five facets", lambda state, trace: _focused(state) and len(state.text) <= state.case.budget),
Invariant('component_view_imports_no_model','the view never imports a project model',lambda s,t:not s.imported),
Invariant('component_view_within_budget','the view fits its requested budget',lambda s,t:s.size<=8000)
)
FEATURE_NAMES=['large_component', 'relied_component', 'component_in_flow', 'helper_split_model', 'wrapper_rule_model', 'loop_built_variants_model', 'kit_model']
LEGACY_FAULTS={'hides_focused_component': 'hide_focused', 'counts_tested_by_keys': 'tested_by_keys', 'kit_known_bad_hidden': 'kit_hidden', 'hides_relied_rules': 'hide_relied', 'hides_component_flows': 'hide_flows'}

from dataclasses import dataclass, replace
@dataclass(frozen=True,eq=False)
class ViewState(JointState):
    native:object
    legacy:object
    component:str='shown'
    imported:bool=False
    size:int=200
    def __eq__(self,other):
        if isinstance(other,ViewState): return (self.native,self.legacy,self.component,self.imported,self.size)==(other.native,other.legacy,other.component,other.imported,other.size)
        return super().__eq__(other)
    def __hash__(self): return hash((self.native,self.legacy,self.component,self.imported,self.size))
class ReadStep(Bridge):
    reads=('native','legacy')
    writes=('native','legacy','component','imported','size')
    def apply(self,event,state):
        if event[0]=='answer':
            answers=((event[1],state.native,state.legacy),)
        else:
            answers=tuple(('shown',item.new_state.native,item.new_state.legacy) for item in super().apply(event,state))
        return tuple(FunctionResult(answer,ViewState(native,legacy,answer,self.fault=='component_view_imports_a_model' or getattr(legacy,'imported',False),9000 if self.fault=='component_view_exceeds_budget' else max(200,getattr(native,'size',0))),label=answer) for answer,native,legacy in answers)

def _explorer(fault=""):
    native=base_variants().get(fault,base_build())
    events=tuple(('native',event) for event in native.external_inputs)+tuple(('legacy',case) for case in legacy_cases(FEATURE_NAMES))+tuple(('answer',value) for value in ('shown', 'unknown'))
    return Explorer(Workflow((ReadStep(native,LEGACY_FAULTS.get(fault,fault)),)),tuple(ViewState(native.initial_states[0],_abstract(ReadCase()),value) for value in ('shown', 'unknown')),events,invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer():return _explorer()
def _original_variants():return {'hides_port_line':_explorer('hides_port_line'),'hides_focused_component':_explorer('hides_focused_component'),'counts_tested_by_keys':_explorer('counts_tested_by_keys'),'kit_known_bad_hidden':_explorer('kit_known_bad_hidden'),'hides_relied_rules':_explorer('hides_relied_rules'),'hides_component_flows':_explorer('hides_component_flows')}
def _original_conformance():
    native=base_conformance()
    moved=legacy_conformance(FEATURE_NAMES,MOVED_RULES)
    return CodeFactsReport(tuple(native.facts)+tuple(moved.facts))

def conformance():
    from _read_dispatch_fixture import fixture,answers,imported
    facts=list(_original_conformance().facts)
    with TemporaryDirectory(prefix='fg-read-answer-') as directory:
        root=Path(directory);fixture(root)
        for value,valid,text in answers(root,'component'): facts.append(Fact(value,valid and not imported(root),text))
    return CodeFactsReport(tuple(facts))

OUTPUTS = {'component': ('shown', 'unknown')}

def broken_variants():
    return {'hides_port_line':_explorer('hides_port_line'), 'hides_focused_component':_explorer('hides_focused_component'), 'counts_tested_by_keys':_explorer('counts_tested_by_keys'), 'kit_known_bad_hidden':_explorer('kit_known_bad_hidden'), 'hides_relied_rules':_explorer('hides_relied_rules'), 'hides_component_flows':_explorer('hides_component_flows'), 'component_view_imports_a_model':_explorer('component_view_imports_a_model'), 'component_view_exceeds_budget':_explorer('component_view_exceeds_budget')}
