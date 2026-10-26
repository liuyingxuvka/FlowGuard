"""Focused component reads show one concise port line for each model."""
from pathlib import Path
from tempfile import TemporaryDirectory
from dataclasses import dataclass
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
PARENT="map-read"
IMPLEMENTED_BY={'Facets': 'flowguard/map/facets.py:component_facets'}
USES={'Show': 'flowguard/map/views.py:render_show'}
TESTED_BY = {'port_line_shown': ['tests/test_read_component.py:test_read_component_prints_one_port_line_per_model'], 'focused_component_visible': ['tests/test_read_component.py:test_read_component_never_hides_the_requested_component'], 'relied_rules_shown': ['tests/test_read_component.py:test_read_component_lists_the_rules_it_relies_on'], 'component_flows_shown': ['tests/test_read_component.py:test_read_component_lists_its_flows_and_their_rules'], 'static_rules_match_model': ['tests/test_read_component.py:test_static_rules_follow_helpers_and_wrappers', 'tests/test_read_component.py:test_static_known_bad_follow_loops_and_tuple_targets', 'tests/test_read_component.py:test_kit_model_facets_are_static_and_complete']}
NOT_MODELED={'flowguard/map/modelstatic.py:StaticModel._module': 'memoizes one parsed helper file per read; the names it yields are what static_rules_match_model checks on real render_show output', 'flowguard/map/modelstatic.py:StaticModel.explorer_rules': 'remembers the kit case table found while reading rules; the cases line is checked by static_rules_match_model through the kit probe', 'flowguard/map/modelstatic.py:StaticModel._defined': "records the AST of each rule's defining call so goal rules can compare versions; tests/test_flowguard_target.py:test_behaviour_target_without_a_rule_is_untied checks that line", 'flowguard/map/modelstatic.py:StaticModel.bad_keys': 'collects known-bad names written by loops and comprehensions; tests/test_map_views.py:test_static_known_bad_follow_loops_and_tuple_targets checks them'}
MOVED_RULES=(
Invariant('static_rules_match_model', "static rule and known-bad names and counts equal the model's explorer and variants", lambda state, trace: _static(state)),
Invariant('relied_rules_shown', "read --component X lists the other components' model rules X's code calls", lambda state, trace: _relied(state)),
Invariant('component_flows_shown', 'read --component X lists the flows that have a step in X, with model and rules', lambda state, trace: _flows(state)),
Invariant('focused_component_visible', "read --component X fits the budget and always shows X's heading and five facets", lambda state, trace: _focused(state) and len(state.text) <= state.case.budget),
)
RULES=(
Invariant('port_line_shown', 'one concise port per model', lambda s, t: s),
Invariant('static_rules_match_model', "static rule and known-bad names and counts equal the model's explorer and variants", lambda state, trace: _static(state)),
Invariant('relied_rules_shown', "read --component X lists the other components' model rules X's code calls", lambda state, trace: _relied(state)),
Invariant('component_flows_shown', 'read --component X lists the flows that have a step in X, with model and rules', lambda state, trace: _flows(state)),
Invariant('focused_component_visible', "read --component X fits the budget and always shows X's heading and five facets", lambda state, trace: _focused(state) and len(state.text) <= state.case.budget),
)
FEATURE_NAMES=['large_component', 'relied_component', 'component_in_flow', 'helper_split_model', 'wrapper_rule_model', 'loop_built_variants_model', 'kit_model']
LEGACY_FAULTS={'hides_focused_component': 'hide_focused', 'counts_tested_by_keys': 'tested_by_keys', 'kit_known_bad_hidden': 'kit_hidden', 'hides_relied_rules': 'hide_relied', 'hides_component_flows': 'hide_flows'}

from dataclasses import dataclass
@dataclass(frozen=True,eq=False)
class ViewState(JointState):
    native:object
    legacy:object
class ReadStep(Bridge):
    reads=('native','legacy')
    writes=('native','legacy')

def _explorer(fault=""):
    native=base_variants().get(fault,base_build())
    events=tuple(('native',event) for event in native.external_inputs)+tuple(('legacy',case) for case in legacy_cases(FEATURE_NAMES))
    return Explorer(Workflow((ReadStep(native,LEGACY_FAULTS.get(fault,'')),)),(ViewState(native.initial_states[0],_abstract(ReadCase())),),events,invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer():return _explorer()
def broken_variants():return {'hides_port_line':_explorer('hides_port_line'),'hides_focused_component':_explorer('hides_focused_component'),'counts_tested_by_keys':_explorer('counts_tested_by_keys'),'kit_known_bad_hidden':_explorer('kit_known_bad_hidden'),'hides_relied_rules':_explorer('hides_relied_rules'),'hides_component_flows':_explorer('hides_component_flows')}
def conformance():
    native=base_conformance()
    moved=legacy_conformance(FEATURE_NAMES,MOVED_RULES)
    return CodeFactsReport(tuple(native.facts)+tuple(moved.facts))
