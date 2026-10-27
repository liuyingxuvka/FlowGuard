"""Find ranks the full requested symbol and the component's actual duty."""
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
QUERIES = {'duty': 'promote target', 'exact': 'find_owners'}

@dataclass(frozen=True)
class State:
    case: str = ''
    winner: str = ''
    complete: bool = True

class Rank:
    name = 'DefinedSymbols'
    reads = ()
    writes = ('case', 'winner')

    def __init__(self, defect=''):
        self.defect = defect

    def apply(self, event, state):
        if event in LOCATIONS:
            return (FunctionResult(event, state),)
        wrong = event == 'duty' and self.defect == 'bonus_per_query_word' or (event == 'exact' and self.defect == 'ignores_exact_symbol')
        return (FunctionResult(event, State(event, 'generic' if wrong else 'duty'), label=event),)
from _locate_fixture import CASES as LOCATIONS
EXPECTED_LOCATIONS = {'owned': 'owner', 'reached': 'none', 'unowned': 'none', 'bound': 'bound', 'unbound': 'unbound', 'file': 'file', 'unknown': 'unknown'}

class Locate:
    name = 'Locate'
    reads = ()
    writes = ('case', 'winner', 'complete')

    def __init__(self, defect=''):
        self.defect = defect

    def apply(self, event, state):
        if event not in LOCATIONS:
            return (FunctionResult(event, state),)
        winner = EXPECTED_LOCATIONS[event]
        if self.defect == 'deepest_reacher_first' and event in ('owned', 'reached'):
            winner = 'deeper'
        if self.defect == 'test_location_unknown_symbol' and event in ('bound', 'unbound', 'file'):
            winner = 'unknown'
        complete = False if self.defect == 'find_view_cuts_lines' else True
        return (FunctionResult(event, State(event, winner, complete)),)
BASE_RULES = (Invariant('locate_prefers_owner', 'ownership wins over a deeper reacher', lambda s, t: s.case not in ('owned', 'reached', 'unowned') or s.winner == EXPECTED_LOCATIONS[s.case]), Invariant('test_location_shows_models_and_code', 'test locations show bindings, calls and owning code', lambda s, t: s.case not in ('bound', 'unbound', 'file') or s.winner == EXPECTED_LOCATIONS[s.case]), Invariant('find_view_uncut', 'each find view prints every line it built, whole', lambda s, t: s.case not in LOCATIONS or s.complete), Invariant('find_ranks_duty_owner_first', 'an incidental single-word symbol cannot outrank the whole requested duty', lambda s, t: InvariantResult.fail('incidental symbol won') if s.case == 'duty' and s.winner != 'duty' else InvariantResult.pass_()), Invariant('find_exact_symbol_first', 'a whole symbol query ranks its actual definition first', lambda s, t: InvariantResult.fail('exact symbol lost') if s.case == 'exact' and s.winner != 'duty' else InvariantResult.pass_()))

def _native_explorer(defect=''):
    return Explorer(Workflow((Rank(defect), Locate(defect))), (State(),), tuple(QUERIES) + tuple(LOCATIONS), invariants=BASE_RULES, max_sequence_length=1, progress_steps=0)

def base_build():
    return _native_explorer()

def base_variants():
    return {name: _native_explorer(name) for name in ('bonus_per_query_word', 'ignores_exact_symbol', 'deepest_reacher_first', 'test_location_unknown_symbol', 'find_view_cuts_lines')}

def make_fixture(root):
    from flowguard.map.inventory import build_inventory
    (root / 'duty.py').write_text('def promote_target(): pass\ndef find_owners(): pass\n')
    (root / 'generic.py').write_text('class Target: pass\n')
    data = {'schema': 'flowguard.map.v1', 'components': [{'id': 'duty', 'summary': 'promote target', 'responsibilities': ['promote target'], 'files': ['duty.py'], 'status': 'draft'}, {'id': 'generic', 'summary': 'find owners', 'responsibilities': ['find owners'], 'files': ['generic.py'], 'status': 'draft'}]}
    return (data, build_inventory(root, [], write_cache=False))

def base_conformance():
    from flowguard.map.views import find_owners
    with TemporaryDirectory(prefix='fg-find-') as folder:
        data, inv = make_fixture(Path(folder))
        facts = []
        for case, query in QUERIES.items():
            hits = find_owners(data, inv, query.split())
            facts.append(Fact(case, bool(hits) and hits[0][1] == 'duty', repr(hits)))
        from _locate_fixture import fixture, observe
        project = Path(folder) / 'locations'
        fixture(project)
        for case in LOCATIONS:
            status, text = observe(project, case)
            correct = status == 1 and text.startswith('no symbol') if case == 'unknown' else status == 0 and text.startswith('locate ') and ('model owner (owned: Run)' in text) if case == 'owned' else status == 0 and text.startswith('no model owns') if case in ('reached', 'unowned') else status == 0 and 'bound to: owner (rule safe)' in text and ('api.py:owned' in text) if case == 'bound' else status == 0 and 'bound to: none (unbound; position app)' in text and ("next: bind it in owner's TESTED_BY" in text) if case == 'unbound' else status == 0 and 'bound: owner 1; unbound 2' in text
            facts.append(Fact('locate_' + case, correct, text))
        return CodeFactsReport(tuple(facts))

from _read_fixture import ReadCase, JointState, Bridge, legacy_cases, legacy_conformance, _abstract
from _read_fixture import _flows, _focused, _layer_order, _model_contract, _names, _ranked, _recipes, _relied, _static, _summary, _true_strengths, _word_forms
MODEL_ID='read_find'
PARENT = 'read_command'
IMPLEMENTED_BY = {'Find': 'flowguard/map/views.py:find_owners', 'Locate': 'flowguard/map/views.py:render_locate', 'LocateWords': 'flowguard/map/views.py:locate_words'}
USES = {
    'BuildInventory': 'flowguard/map/inventory.py:build_inventory',
    'Main': 'flowguard/__main__.py:main',
    'RenderShow': 'flowguard/map/views.py:render_show',
}
TESTED_BY = {'locate_prefers_owner': ['tests/test_read_find.py:test_locate_prefers_the_owner_over_a_deeper_reacher'], 'test_location_shows_models_and_code': ['tests/test_read_find.py:test_locate_bound_test_shows_model_rule_and_code'], 'find_view_uncut': ['tests/test_read_find.py:test_locate_output_is_complete'], 'find_ranks_duty_owner_first': ['tests/test_read_find.py:test_find_bonus_needs_the_joined_query'], 'find_exact_symbol_first': ['tests/test_read_find.py:test_find_ranks_the_component_that_defines_an_exact_symbol_first', 'tests/test_read_find.py:test_word_locate_names_the_symbol_owner'], 'find_matches_word_forms': ['tests/test_read_find.py:test_find_matches_word_forms'], 'find_view_imports_no_model': ['tests/test_read_command.py:test_find_view_imports_no_model']}
MOVED_RULES=(
Invariant('find_matches_word_forms', 'a query word matches a duty word that differs only by a common ending', lambda state, trace: _word_forms(state)),
)
RULES = BASE_RULES + MOVED_RULES + (
Invariant('find_view_imports_no_model','the view never imports a project model',lambda s,t:not s.imported),
)
FEATURE_NAMES=['inflected_query']
LEGACY_FAULTS={'exact_words_only': 'exact_words_only'}

from dataclasses import dataclass, replace
@dataclass(frozen=True,eq=False)
class ViewState(JointState):
    native:object
    legacy:object
    found:str='owners'
    imported:bool=False
    complete: bool = True
    def __eq__(self,other):
        if isinstance(other,ViewState): return (self.native,self.legacy,self.found,self.imported,self.complete)==(other.native,other.legacy,other.found,other.imported,other.complete)
        return super().__eq__(other)
    def __hash__(self): return hash((self.native,self.legacy,self.found,self.imported,self.complete))
class ReadStep(Bridge):
    reads=('native','legacy')
    writes=('native','legacy','found','imported','complete')
    def apply(self,event,state):
        if event[0]=='answer':
            answers=((event[1],state.native,state.legacy),)
        else:
            answers=tuple(('owners',item.new_state.native,item.new_state.legacy) for item in super().apply(event,state))
        return tuple(FunctionResult(answer,ViewState(native,legacy,answer,self.fault=='find_view_imports_a_model' or getattr(legacy,'imported',False),False if self.fault=='find_view_cuts_lines' else getattr(native,'complete',True)),label=answer) for answer,native,legacy in answers)

def _explorer(fault=""):
    native=base_variants().get(fault,base_build())
    events=tuple(('native',event) for event in native.external_inputs)+tuple(('legacy',case) for case in legacy_cases(FEATURE_NAMES))+tuple(('answer',value) for value in ('owners', 'no_owner', 'location', 'no_symbol', 'test'))
    return Explorer(Workflow((ReadStep(native,LEGACY_FAULTS.get(fault,fault)),)),tuple(ViewState(native.initial_states[0],_abstract(ReadCase()),value) for value in ('owners', 'no_owner')),events,invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer():return _explorer()
def _original_variants():return {'bonus_per_query_word':_explorer('bonus_per_query_word'),'ignores_exact_symbol':_explorer('ignores_exact_symbol'),'deepest_reacher_first':_explorer('deepest_reacher_first'),'test_location_unknown_symbol':_explorer('test_location_unknown_symbol'),'find_view_cuts_lines':_explorer('find_view_cuts_lines'),'exact_words_only':_explorer('exact_words_only')}
def _original_conformance():
    native=base_conformance()
    moved=legacy_conformance(FEATURE_NAMES,MOVED_RULES)
    return CodeFactsReport(tuple(native.facts)+tuple(moved.facts))

def conformance():
    from _read_dispatch_fixture import fixture,answers,imported
    facts=list(_original_conformance().facts)
    with TemporaryDirectory(prefix='fg-read-answer-') as directory:
        root=Path(directory);fixture(root)
        for value,valid,text in answers(root,'find'): facts.append(Fact(value,valid and not imported(root),text))
    return CodeFactsReport(tuple(facts))

OUTPUTS = {'found': ('owners', 'no_owner', 'location', 'no_symbol', 'test')}

def broken_variants():
    return {'bonus_per_query_word':_explorer('bonus_per_query_word'), 'ignores_exact_symbol':_explorer('ignores_exact_symbol'), 'deepest_reacher_first':_explorer('deepest_reacher_first'), 'test_location_unknown_symbol':_explorer('test_location_unknown_symbol'), 'find_view_cuts_lines':_explorer('find_view_cuts_lines'), 'exact_words_only':_explorer('exact_words_only'), 'find_view_imports_a_model':_explorer('find_view_imports_a_model')}

from _read_fixture import complete_view_facts
_previous_conformance = conformance
def conformance():
    previous = _previous_conformance()
    return CodeFactsReport(tuple(previous.facts) + complete_view_facts('find'))


_previous_word_conformance = conformance
def conformance():
    from _read_dispatch_fixture import call
    import json
    facts = list(_previous_word_conformance().facts)
    with TemporaryDirectory(prefix='fg-word-owner-') as directory:
        root = Path(directory)
        models = root / '.flowguard/models'
        models.mkdir(parents=True)
        (root / 'api.py').write_text('def add_model(): return 1\ndef promote_target(): return 2\n')
        for mid, symbol, rule, note in [('a_add','add_model','add_never_promote_target','adding a model must not promote the target'), ('z_promotion','promote_target','promote_only_clean_target','promote only a clean target')]:
            (models / (mid + '.py')).write_text(f'MODEL_ID={mid!r}\nPARENT="app"\nIMPLEMENTED_BY={{"Run":{("api.py:" + symbol)!r}}}\nRULES=(Invariant({rule!r},{note!r},None),)\ndef build_explorer(): pass\n')
        (root / '.flowguard/map.json').write_text(json.dumps(dict(schema='flowguard.map.v1', components=[dict(id='app', files=['api.py'], summary='promote target', responsibilities=['promote target'], status='draft', tests=[], models=[])])))
        code, text = call(root, '--find', 'promote', 'target')
        facts.append(Fact('words_name_symbol_owner', code == 0 and text.rstrip().endswith('locate: z_promotion'), text))
    return CodeFactsReport(tuple(facts))
