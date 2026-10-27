"""Read counts real bindings and separates bound, calling and unrelated tests."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
BASE_RULES = (Invariant('coverage_counts_only_bound', 'words do not count as calls', lambda s, t: s[0] == 2), Invariant('tests_line_counts_bound_and_unbound', 'one bound, two calling and one unrelated test', lambda s, t: s[1:] == (1, 2, 1)))

class Show:
    name = 'Show'

    def __init__(self, fault=''):
        self.fault = fault

    def apply(self, event, state):
        value = (3 if self.fault == 'words' else 2, 3 if self.fault == 'binding' else 1, 2, 1)
        return (FunctionResult(value, value),)

def _native_explorer(fault=''):
    return Explorer(Workflow((Show(fault),)), ((2, 1, 2, 1),), ('show',), invariants=BASE_RULES, max_sequence_length=1, progress_steps=0)

def base_build():
    return _native_explorer()

def base_variants():
    return {'counts_docstring_mention_as_test': _native_explorer('words'), 'counts_unbound_as_bound': _native_explorer('binding')}

def make_fixture(root):
    files = {'app.py': 'def modeled(): return True\ndef called(): return True\ndef mentioned(): return True\ndef reasoned(): return True\n', 'tests/test_app.py': "from app import modeled, called\nimport unittest\ndef test_bound(): assert modeled()\ndef test_call(): assert called() and modeled()\ndef test_words():\n    '''mentioned() is only prose'''\n    assert True\nclass Base(unittest.TestCase): pass\nclass Suite(Base):\n    def test_method(self): assert called() and modeled()\n", '.flowguard/models/probe.py': '"""Probe."""\nMODEL_ID="probe"\nPARENT="app"\nIMPLEMENTED_BY={"Run":"app.py:modeled"}\nNOT_MODELED={"app.py:reasoned":"deliberate no-op"}\nTESTED_BY={"works":["tests/test_app.py:test_bound"]}\ndef build_explorer(): pass\n'}
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    data = dict(schema='flowguard.map.v1', project='fixture', components=[dict(id='app', summary='Four entrypoints', responsibilities=['Serve'], files=['app.py'], tests=['tests/test_app.py'], entrypoints=['app.py:' + name for name in ('modeled', 'called', 'mentioned', 'reasoned')], models=[], status='draft')])
    (root / '.flowguard/map.json').write_text(json.dumps(data))
    return data

def base_conformance():
    from flowguard.map.views import render_show
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    with TemporaryDirectory(prefix='fg-read-show-') as directory:
        root = Path(directory)
        data = make_fixture(root)
        inv = build_inventory(root, DEFAULT_IGNORE, write_cache=False)
        text = render_show(root, data, inv, component=None, detail=False, budget=8000)
        return CodeFactsReport((Fact('bound_coverage', 'coverage: entrypoints 2 of 4 bound (model 1, test 1), 1 by reason, 0 unlisted;' in text, text), Fact('test_counts', "tests: 4 test functions; 1 bound to a model (TESTED_BY), 2 call a model's code, 1 neither" in text, text)))

from _read_fixture import ReadCase, JointState, Bridge, legacy_cases, legacy_conformance, _abstract
from _read_fixture import _flows, _focused, _layer_order, _model_contract, _names, _ranked, _recipes, _relied, _static, _summary, _true_strengths, _word_forms
MODEL_ID='read_show'
PARENT = 'read_command'
IMPLEMENTED_BY={'Show': 'flowguard/map/views.py:render_show'}
USES={'Facets': 'flowguard/map/facets.py:component_facets'}
TESTED_BY = {'coverage_counts_only_bound': ['tests/test_map_views.py:test_coverage_counts_calls_not_words'], 'tests_line_counts_bound_and_unbound': ['tests/test_map_views.py:test_tests_line_counts_bound_calling_and_neither'], 'no_model_import': ['tests/test_map_views.py:test_read_observes_hidden_names_missing_summary_and_model_counts'], 'components_visible_or_named': ['tests/test_map_views.py:test_read_observes_hidden_names_missing_summary_and_model_counts'], 'within_budget': ['tests/test_map_views.py:test_read_observes_hidden_names_missing_summary_and_model_counts'], 'model_purpose_and_three_counts': ['tests/test_map_views.py:test_read_observes_hidden_names_missing_summary_and_model_counts'], 'missing_summary_prompt': ['tests/test_map_views.py:test_read_observes_hidden_names_missing_summary_and_model_counts'], 'components_in_layer_order': ['tests/test_map_views.py:test_read_orders_components_by_layer']}
MOVED_RULES=(
Invariant('no_model_import', 'reading never imports a model module', lambda state, trace: not state.imported),
Invariant('components_visible_or_named', 'each component is visible or explicitly named as hidden', lambda state, trace: _names(state)),
Invariant('within_budget', 'output fits the requested character budget', lambda state, trace: len(state.text) <= state.case.budget),
Invariant('model_purpose_and_three_counts', 'displayed models retain purpose and rule/bad/test counts', lambda state, trace: _model_contract(state)),
Invariant('missing_summary_prompt', 'a visible component without summary carries the purpose prompt', lambda state, trace: _summary(state)),
Invariant('components_in_layer_order', 'read lists top-level components by layer, parents before children', lambda state, trace: _layer_order(state)),
)
RULES=(
Invariant('coverage_counts_only_bound', 'words do not count as calls', lambda s, t: s[0] == 2),Invariant('tests_line_counts_bound_and_unbound', 'one bound, two calling and one unrelated test', lambda s, t: s[1:] == (1, 2, 1)),
Invariant('no_model_import', 'reading never imports a model module', lambda state, trace: not state.imported),
Invariant('components_visible_or_named', 'each component is visible or explicitly named as hidden', lambda state, trace: _names(state)),
Invariant('within_budget', 'output fits the requested character budget', lambda state, trace: len(state.text) <= state.case.budget),
Invariant('model_purpose_and_three_counts', 'displayed models retain purpose and rule/bad/test counts', lambda state, trace: _model_contract(state)),
Invariant('missing_summary_prompt', 'a visible component without summary carries the purpose prompt', lambda state, trace: _summary(state)),
Invariant('components_in_layer_order', 'read lists top-level components by layer, parents before children', lambda state, trace: _layer_order(state)),
)
FEATURE_NAMES=['small_budget', 'import_time_marker', 'missing_summary', 'late_upper_component']
LEGACY_FAULTS={'drops_a_component': 'drop_component', 'imports_a_model': 'import_model', 'exceeds_budget': 'overflow', 'drops_model_contract': 'drop_model_contract', 'drops_summary_prompt': 'drop_summary_prompt', 'map_file_order': 'map_file_order'}

from dataclasses import dataclass, replace
@dataclass(frozen=True,eq=False)
class ViewState(JointState):
    native:object
    legacy:object
    shown:str='complete'
    imported:bool=False
    size:int=200
    def __eq__(self,other):
        if isinstance(other,ViewState): return (self.native,self.legacy,self.shown,self.imported,self.size)==(other.native,other.legacy,other.shown,other.imported,other.size)
        return super().__eq__(other)
    def __hash__(self): return hash((self.native,self.legacy,self.shown,self.imported,self.size))
class ReadStep(Bridge):
    reads=('native','legacy')
    writes=('native','legacy','shown','imported','size')
    def apply(self,event,state):
        if event[0]=='answer':
            answers=((event[1],state.native,state.legacy),)
        else:
            answers=tuple(('complete',item.new_state.native,item.new_state.legacy) for item in super().apply(event,state))
        return tuple(FunctionResult(answer,ViewState(native,legacy,answer,self.fault=='show_view_imports_a_model' or getattr(legacy,'imported',False),9000 if self.fault=='show_view_exceeds_budget' else max(200,getattr(native,'size',0))),label=answer) for answer,native,legacy in answers)

def _explorer(fault=""):
    native=base_variants().get(fault,base_build())
    events=tuple(('native',event) for event in native.external_inputs)+tuple(('legacy',case) for case in legacy_cases(FEATURE_NAMES))+tuple(('answer',value) for value in ('complete', 'truncated'))
    return Explorer(Workflow((ReadStep(native,LEGACY_FAULTS.get(fault,fault)),)),tuple(ViewState(native.initial_states[0],_abstract(ReadCase()),value) for value in ('complete', 'truncated')),events,invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer():return _explorer()
def broken_variants():return {'counts_docstring_mention_as_test':_explorer('counts_docstring_mention_as_test'),'counts_unbound_as_bound':_explorer('counts_unbound_as_bound'),'drops_a_component':_explorer('drops_a_component'),'imports_a_model':_explorer('imports_a_model'),'exceeds_budget':_explorer('exceeds_budget'),'drops_model_contract':_explorer('drops_model_contract'),'drops_summary_prompt':_explorer('drops_summary_prompt'),'map_file_order':_explorer('map_file_order')}
def _original_conformance():
    native=base_conformance()
    moved=legacy_conformance(FEATURE_NAMES,MOVED_RULES)
    return CodeFactsReport(tuple(native.facts)+tuple(moved.facts))

def conformance():
    from _read_dispatch_fixture import fixture,answers,imported
    facts=list(_original_conformance().facts)
    with TemporaryDirectory(prefix='fg-read-answer-') as directory:
        root=Path(directory);fixture(root)
        for value,valid,text in answers(root,'show'): facts.append(Fact(value,valid and not imported(root),text))
    return CodeFactsReport(tuple(facts))

OUTPUTS = {'shown': ('complete', 'truncated')}
