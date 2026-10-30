"""Confirmation describes the pointer; comparison consumes its fingerprint verdict.

The temporary model-file guard rejoins this small pointer model. It retains its
own real checker anchor, known-bad and regression rather than losing a promise.
"""
from contextlib import redirect_stdout
from dataclasses import dataclass, replace
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
from _pointer_fixture import model_edit_cases

MODEL_ID = 'component_pointer'
PARENT = 'map-file'
COMPONENTS = ['map-file', 'cli', 'map-check']
IMPLEMENTED_BY = {'Confirm': 'flowguard/map/cli.py:cmd_confirm', 'ModelEdits': 'flowguard/map/check.py:model_edit_findings'}
USES = {
    'ComponentState': 'flowguard/map/mapfile.py:component_state',
    'Main': 'flowguard/map/cli.py:main',
    'RunCheck': 'flowguard/map/check.py:run_check',
    'TargetAdd': 'flowguard/map/target.py:add_to_target',
    'TargetMain': 'flowguard/map/target.py:main',
}
HANDOFF = {'release_neutral_fingerprint': {'fingerprint': 'fingerprint'}}
TESTED_BY = {'clean_means_current': ['tests/test_component_pointer.py:test_stale_after_owned_file_changes_and_confirm_clears_it'], 'confirmed_means_described': ['tests/test_component_pointer.py:test_filled_map_checks_clean_after_confirm'], 'model_edited_outside_target_is_named': ['tests/test_model_edits.py:test_map_check_names_model_edited_outside_target', 'tests/test_model_edits.py:test_in_place_edit_of_staged_model_refused']}
NOT_MODELED = {'flowguard/__main__.py:main': 'CLI dispatch; command tests cover it.',
               'flowguard/map/cli.py:main': 'Map dispatch; command tests cover it.',
               'flowguard/map/inventory.py:build_inventory': 'Static inventory, covered by encoding and cache regressions.',
               'flowguard/templates.py:write_template_files': 'Template writing, covered by generation and overwrite tests.'}

@dataclass(frozen=True)
class State:
    status: str = 'draft'
    described: bool = False
    model_edit: bool = False
    fingerprint: str = 'current'
    freshness: str = ''
    named: bool = False
    action: str = ''
    staged: bool = False
    @property
    def model_edited(self): return self.model_edit
    @property
    def last_report(self):
        if self.action != 'check': return ''
        return 'model_edited_outside_target' if self.named else self.freshness

@dataclass(frozen=True)
class ConfirmEvent:
    kind: str = 'confirm'
@dataclass(frozen=True)
class CompareEvent:
    kind: str
@dataclass(frozen=True)
class ReportEvent:
    kind: str

class Confirm:
    name = 'Confirm'
    accepted_input_type = ConfirmEvent
    reads = ('described', 'status')
    writes = ('status', 'action')
    def __init__(self, defect=''): self.defect = defect
    def apply(self, event, state):
        allowed = state.described or self.defect == 'confirm_without_description'
        return (FunctionResult('confirmed' if allowed else 'refused', replace(state,
                status='confirmed' if allowed else state.status, action='confirm')),)

class Compare:
    name = 'Compare'
    accepted_input_type = CompareEvent
    reads = ()
    writes = ('fingerprint', 'action')
    def apply(self, event, state):
        return (FunctionResult(event.kind, replace(state, fingerprint=event.kind, action='compare'),
                               label='fingerprint:'+event.kind),)

class Report:
    name = 'Report'
    accepted_input_type = ReportEvent
    reads = ('status', 'fingerprint', 'model_edit', 'staged')
    writes = ('described', 'model_edit', 'freshness', 'named', 'action', 'staged')
    def __init__(self, defect=''): self.defect = defect
    def apply(self, event, state):
        if event.kind == 'describe':
            return (FunctionResult('described', replace(state, described=True, action='describe')),)
        if event.kind == 'edit_model':
            return (FunctionResult('edited', replace(state, model_edit=True, action='edit_model')),)
        if event.kind == 'edit_staged_model':
            return (FunctionResult('edited', replace(state, model_edit=True, staged=True, action='edit_staged_model')),)
        if event.kind == 'target':
            return (FunctionResult('owned_by_target', replace(state, model_edit=False, staged=False, action='target')),)
        freshness = 'draft' if state.status == 'draft' else 'clean' if state.fingerprint == 'current' else state.fingerprint
        if self.defect == 'check_ignores_changes' and state.status == 'confirmed': freshness = 'clean'
        named = state.model_edit and self.defect != 'ignores_in_place_model_edit'
        if state.staged and self.defect == 'staged_edit_invisible':
            named = False
        return (FunctionResult((freshness, 'model_edited_outside_target' if named else ''),
                replace(state, freshness=freshness, named=named, action='check')),)

def _clean_means_current(state, trace):
    if state.action == 'check' and state.freshness == 'clean' and state.fingerprint != 'current':
        return InvariantResult.fail('clean requires a current fingerprint verdict')
    return InvariantResult.pass_()

def _confirmed_means_described(state: State, trace) -> InvariantResult:
    if state.status == 'confirmed' and (not state.described):
        return InvariantResult.fail('a component without description was confirmed')
    return InvariantResult.pass_()

INVARIANTS = (
    Invariant('clean_means_current', 'clean is reported only when the code is unchanged since confirm', _clean_means_current),
    Invariant('confirmed_means_described', 'confirm requires summary and responsibilities', _confirmed_means_described),
    Invariant("model_edited_outside_target_is_named", "model edits need their own target and cannot be silently cleared by confirm",
              lambda s,t: InvariantResult.fail("unplanned model edit was hidden") if s.model_edited and s.last_report
              and s.last_report != "model_edited_outside_target" else InvariantResult.pass_()),
)
EVENTS = (ConfirmEvent(), CompareEvent('current'), CompareEvent('stale'), CompareEvent('migrate'),
          ReportEvent('describe'), ReportEvent('edit_model'), ReportEvent('edit_staged_model'), ReportEvent('target'), ReportEvent('check'))

def make(defect=''):
    return Explorer(Workflow((Confirm(defect), Compare(), Report(defect)), mode='choice'),
                    (State(), State(status='confirmed', described=True)), EVENTS,
                    invariants=INVARIANTS, max_sequence_length=3, progress_steps=0)
def build_explorer(): return make()
def broken_variants():
    return {name: make(name) for name in ('confirm_without_description', 'check_ignores_changes', 'ignores_in_place_model_edit', 'staged_edit_invisible')}

def conformance():
    from types import SimpleNamespace
    from flowguard.map.cli import cmd_confirm
    from flowguard.map.check import run_check
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import component_state, load_map, ignore_patterns
    from flowguard.map.common import content_digest
    facts = []
    with TemporaryDirectory(prefix='fg-pointer-') as directory:
        root = Path(directory); path = root/'app.py'; path.write_text('def run(): return True\n')
        version = root/'pkg/__init__.py'; version.parent.mkdir(); version.write_text('__version__="1.0.0"\n')
        data = dict(schema='flowguard.map.v1', fingerprint_format=2, components=[dict(
            id='app', summary='', responsibilities=[], files=['app.py', 'pkg/__init__.py'], tests=[], models=[],
            entrypoints=[], depends_on=[], state=[], side_effects=[], status='draft')])
        target = root/'.flowguard/map.json'; target.parent.mkdir(); target.write_text(json.dumps(data))
        with redirect_stdout(StringIO()): refused = cmd_confirm(root, SimpleNamespace(ids=['app']))
        facts.append(Fact('description_required', refused == 1 and load_map(root)['components'][0]['status'] == 'draft'))
        data['components'][0].update(summary='Compute one value', responsibilities=['compute the value'])
        target.write_text(json.dumps(data))
        with redirect_stdout(StringIO()): confirmed = cmd_confirm(root, SimpleNamespace(ids=['app']))
        data = load_map(root); inv = build_inventory(root, ignore_patterns(data), write_cache=False)
        facts.append(Fact('described_pointer', confirmed == 0 and data['components'][0]['status'] == 'confirmed'))
        for case in ('current', 'stale', 'migrate'):
            if case == 'stale': path.write_text('def run(): return False\n')
            probe = json.loads(json.dumps(data))
            if case == 'migrate':
                legacy = sha256()
                for rel in ('app.py', 'pkg/__init__.py'): legacy.update((rel+'\0'+content_digest(root/rel)+'\n').encode())
                probe['components'][0]['fingerprint'] = 'sha256:'+legacy.hexdigest(); probe['fingerprint_format'] = 1
            inv = build_inventory(root, ignore_patterns(data), write_cache=False)
            received = component_state(root, probe['components'][0], inv, probe)
            findings = run_check(root, probe, inv)
            codes = {f.code for f in findings if f.component == 'app'}
            reported = 'draft' if 'draft' in codes else 'migrate' if 'fingerprint_migrate' in codes else 'stale' if 'stale' in codes else 'clean'
            facts.append(Fact(case, received == case and reported == ('clean' if case == 'current' else case), repr((received,codes))))
    guarded = model_edit_cases()
    facts.append(Fact('model_file_target_guard', guarded.ok, guarded.format_text()))
    return CodeFactsReport(tuple(facts))
