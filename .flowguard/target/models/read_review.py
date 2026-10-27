"""Review closes one explained suggestion and counts the accepted decision."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
BASE_RULES = (Invariant('closed_suggestion_is_counted', 'the closed suggestion disappears and the decision is counted', lambda s, t: s == (False, 1)),)

class Review:
    name = 'Review'

    def __init__(self, bad=False):
        self.bad = bad

    def apply(self, event, state):
        observed = (self.bad, 0 if self.bad else 1)
        return (FunctionResult(observed, observed),)

def _native_explorer(bad=False):
    return Explorer(Workflow((Review(bad),)), ((False, 1),), ('review',), invariants=BASE_RULES, max_sequence_length=1, progress_steps=0)

def base_build():
    return _native_explorer()

def base_variants():
    return {'closed_suggestion_reappears': _native_explorer(True)}

def make_fixture(root):
    (root / 'app.py').write_text('def run(): return True\n')
    (root / '.flowguard').mkdir(exist_ok=True)
    data = dict(schema='flowguard.map.v1', project='review', components=[dict(id='app', summary='Text templates', responsibilities=['Serve templates'], files=['app.py'], state=['text'], models=[], tests=[], status='draft')], accepted_debts=[dict(code='unmodeled_owner', component='app', reason='static text; no state to explore')])
    (root / '.flowguard/map.json').write_text(json.dumps(data))
    return data

def base_conformance():
    from flowguard.map.review import render_review
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    with TemporaryDirectory(prefix='fg-read-review-') as folder:
        root = Path(folder)
        data = make_fixture(root)
        inv = build_inventory(root, DEFAULT_IGNORE, write_cache=False)
        text = render_review(root, data, inv)
        return CodeFactsReport((Fact('closed_count', 'model app:' not in text and 'declined: 1 (accepted debts; 0 no longer arise)' in text, text),))

from _read_fixture import ReadCase, JointState, Bridge, legacy_cases, legacy_conformance, _abstract
from _read_fixture import _flows, _focused, _layer_order, _model_contract, _names, _ranked, _recipes, _relied, _static, _summary, _true_strengths, _word_forms
MODEL_ID='read_review'
PARENT = 'read_command'
IMPLEMENTED_BY={'Review': 'flowguard/map/review.py:render_review'}
USES = {
    'Facets': 'flowguard/map/facets.py:component_facets',
    'Main': 'flowguard/__main__.py:main',
    'RenderShow': 'flowguard/map/views.py:render_show',
}
TESTED_BY = {'closed_suggestion_is_counted': ['tests/test_read_command.py:test_closing_debt_hides_one_suggestion'], 'review_ranks_errors_first': ['tests/test_read_command.py:test_review_ranks_defects_and_states_true_strengths'], 'review_strengths_are_true': ['tests/test_read_command.py:test_review_ranks_defects_and_states_true_strengths'], 'review_steps_name_a_recipe': ['tests/test_read_command.py:test_review_ranks_defects_and_states_true_strengths'], 'review_view_imports_no_model': ['tests/test_read_command.py:test_review_ranks_defects_and_states_true_strengths'], 'review_view_complete': ['tests/test_read_command.py:test_review_ranks_defects_and_states_true_strengths']}
MOVED_RULES=(
Invariant('review_ranks_errors_first', 'every ERROR finding is in optimise next, before every non-ERROR step', lambda state, trace: _ranked(state)),
Invariant('review_strengths_are_true', 'every strength read --review claims holds on the project', lambda state, trace: _true_strengths(state)),
Invariant('review_steps_name_a_recipe', 'every optimise next step names a references recipe or a flowguard command', lambda state, trace: _recipes(state)),
)
RULES = BASE_RULES + MOVED_RULES + (
Invariant('review_view_imports_no_model','the view never imports a project model',lambda s,t:not s.imported),
Invariant('review_view_complete','every component row is shown',lambda s,t:s.complete),
)
FEATURE_NAMES=['review_fixture']
LEGACY_FAULTS={'review_hides_error': 'review_hides_error', 'review_claims_false_strength': 'review_false_strength', 'review_step_without_recipe': 'review_no_recipe'}

from dataclasses import dataclass, replace
@dataclass(frozen=True,eq=False)
class ViewState(JointState):
    native:object
    legacy:object
    review:str='ranked'
    imported:bool=False
    complete: bool = True
    def __eq__(self,other):
        if isinstance(other,ViewState): return (self.native,self.legacy,self.review,self.imported,self.complete)==(other.native,other.legacy,other.review,other.imported,other.complete)
        return super().__eq__(other)
    def __hash__(self): return hash((self.native,self.legacy,self.review,self.imported,self.complete))
class ReadStep(Bridge):
    reads=('native','legacy')
    writes=('native','legacy','review','imported','complete')
    def apply(self,event,state):
        if event[0]=='answer':
            answers=((event[1],state.native,state.legacy),)
        else:
            answers=tuple(('ranked',item.new_state.native,item.new_state.legacy) for item in super().apply(event,state))
        return tuple(FunctionResult(answer,ViewState(native,legacy,answer,self.fault=='review_view_imports_a_model' or getattr(legacy,'imported',False),False if self.fault=='review_view_hides_components' else getattr(native,'complete',True)),label=answer) for answer,native,legacy in answers)

def _explorer(fault=""):
    native=base_variants().get(fault,base_build())
    events=tuple(('native',event) for event in native.external_inputs)+tuple(('legacy',case) for case in legacy_cases(FEATURE_NAMES))+tuple(('answer',value) for value in ('ranked', 'nothing_to_rank'))
    return Explorer(Workflow((ReadStep(native,LEGACY_FAULTS.get(fault,fault)),)),tuple(ViewState(native.initial_states[0],_abstract(ReadCase()),value) for value in ('ranked', 'nothing_to_rank')),events,invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer():return _explorer()
def _original_variants():return {'closed_suggestion_reappears':_explorer('closed_suggestion_reappears'),'review_hides_error':_explorer('review_hides_error'),'review_claims_false_strength':_explorer('review_claims_false_strength'),'review_step_without_recipe':_explorer('review_step_without_recipe')}
def _original_conformance():
    native=base_conformance()
    moved=legacy_conformance(FEATURE_NAMES,MOVED_RULES)
    return CodeFactsReport(tuple(native.facts)+tuple(moved.facts))

def conformance():
    from _read_dispatch_fixture import fixture,answers,imported
    facts=list(_original_conformance().facts)
    with TemporaryDirectory(prefix='fg-read-answer-') as directory:
        root=Path(directory);fixture(root)
        for value,valid,text in answers(root,'review'): facts.append(Fact(value,valid and not imported(root),text))
    return CodeFactsReport(tuple(facts))

OUTPUTS = {'review': ('ranked', 'nothing_to_rank')}

def broken_variants():
    return {'closed_suggestion_reappears':_explorer('closed_suggestion_reappears'), 'review_hides_error':_explorer('review_hides_error'), 'review_claims_false_strength':_explorer('review_claims_false_strength'), 'review_step_without_recipe':_explorer('review_step_without_recipe'), 'review_view_imports_a_model':_explorer('review_view_imports_a_model'), 'review_view_hides_components':_explorer('review_view_hides_components')}

from _read_fixture import complete_view_facts
_previous_conformance = conformance
def conformance():
    previous = _previous_conformance()
    return CodeFactsReport(tuple(previous.facts) + complete_view_facts('review'))
