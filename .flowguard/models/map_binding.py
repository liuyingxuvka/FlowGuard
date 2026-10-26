"""Map check reports broken anchors, unowned files, undeclared or unused imports, two owners and bad flow steps.

The base project has four components (app uses api and core; api uses core; util is free) and one flow.
Each event makes one edit to a copy; the state is the set of binding codes that
the real run_check reports (and run_lint, for the private-name event).
"""
from dataclasses import dataclass, replace
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import shutil
import tempfile
from flowguard import FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace, select_covering_traces
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer
from flowguard.map.check import run_check
from flowguard.map.inventory import build_inventory
from flowguard.map.lint import run_lint
MODEL_ID = 'map_binding'
PARENT = 'map-check'
COMPONENTS = ['map-check', 'map-file', 'cli']
IMPLEMENTED_BY = {'Check': 'flowguard/map/check.py:run_check', 'Lint': 'flowguard/map/lint.py:run_lint', 'Owners': 'flowguard/map/lint.py:duplicate_owner_findings'}
TESTED_BY = {'missing_anchor_is_broken': ['tests/test_map_binding.py:test_check_reports_unmapped_overlap_anchor_and_undeclared_dep'], 'unowned_file_is_unmapped': ['tests/test_map_binding.py:test_check_reports_unmapped_overlap_anchor_and_undeclared_dep'], 'one_owner_per_file': ['tests/test_map_binding.py:test_check_reports_unmapped_overlap_anchor_and_undeclared_dep'], 'undeclared_import_is_reported': ['tests/test_map_binding.py:test_check_reports_unmapped_overlap_anchor_and_undeclared_dep'], 'unused_dependency_is_reported': ['tests/test_map_binding.py:test_map_check_binding_codes'], 'injected_dependency_is_evidence': ['tests/test_map_binding.py:test_map_check_binding_codes'], 'one_owner_per_claim': ['tests/test_map_binding.py:test_check_and_change_report_duplicate_owner'], 'flow_steps_resolve': ['tests/test_map_binding.py:test_flow_steps_are_verified', 'tests/test_flowguard_map_contracts.py:test_flow_step_can_read_the_previous_steps_file']}
CODES = ('anchor_broken', 'file_unmapped', 'file_multi_owner', 'dep_undeclared', 'dep_unused', 'duplicate_owner', 'flow_step_broken', 'flow_handoff_invalid', 'private_cross_component_use')
EXPECTED = {'rename_anchor': ('anchor_broken',), 'add_unowned_file': ('file_unmapped',), 'two_owners_one_file': ('file_multi_owner',), 'import_undeclared': ('dep_undeclared',), 'drop_import': ('dep_unused',), 'inject_dependency': (), 'duplicate_state': ('duplicate_owner',), 'bad_flow_step': ('flow_step_broken',), 'bad_flow_handoff': ('flow_handoff_invalid',), 'private_name_use': ('private_cross_component_use',)}
DEFECTS = {'skips_anchor_check': ('rename_anchor', '-anchor_broken'), 'ignores_unowned_file': ('add_unowned_file', '-file_unmapped'), 'allows_two_file_owners': ('two_owners_one_file', '-file_multi_owner'), 'ignores_undeclared_import': ('import_undeclared', '-dep_undeclared'), 'keeps_unused_dependency': ('drop_import', '-dep_unused'), 'drops_injected_dependency': ('inject_dependency', '+dep_unused'), 'misses_duplicate_owner': ('duplicate_state', '-duplicate_owner'), 'accepts_bad_flow_step': ('bad_flow_step', '-flow_step_broken')}

@dataclass(frozen=True)
class State:
    event: str = ''
    codes: tuple = ()

class Check:
    name = 'Check'

    def __init__(self, defect=''):
        self.defect = defect

    def apply(self, event, state):
        codes = set(EXPECTED[event])
        if self.defect:
            target, change = DEFECTS[self.defect]
            if target == event:
                codes = codes - {change[1:]} if change[0] == '-' else codes | {change[1:]}
        return (FunctionResult(event, State(event, tuple(sorted(codes))), label=event),)

def _rule(name, events, predicate, message):
    return Invariant(name, message, lambda state, trace: InvariantResult.pass_() if state.event not in events or predicate(state) else InvariantResult.fail(message))
INVARIANTS = (_rule('missing_anchor_is_broken', {'rename_anchor'}, lambda state: 'anchor_broken' in state.codes, 'a renamed entrypoint was not reported as anchor_broken'), _rule('unowned_file_is_unmapped', {'add_unowned_file'}, lambda state: 'file_unmapped' in state.codes, 'a source file without an owner was not reported'), _rule('one_owner_per_file', {'two_owners_one_file'}, lambda state: 'file_multi_owner' in state.codes, 'a file owned by two components was accepted'), _rule('undeclared_import_is_reported', {'import_undeclared'}, lambda state: 'dep_undeclared' in state.codes, 'an import of an undeclared component was accepted'), _rule('unused_dependency_is_reported', {'drop_import'}, lambda state: 'dep_unused' in state.codes, 'a declared dependency with no evidence was accepted'), _rule('injected_dependency_is_evidence', {'inject_dependency'}, lambda state: 'dep_unused' not in state.codes, 'a dependency used only through an injected object was called unused'), _rule('one_owner_per_claim', {'duplicate_state'}, lambda state: 'duplicate_owner' in state.codes, 'two components claiming one state were accepted by map check'), _rule('flow_steps_resolve', {'bad_flow_step', 'bad_flow_handoff'}, lambda state: {'bad_flow_step': 'flow_step_broken', 'bad_flow_handoff': 'flow_handoff_invalid'}[state.event] in state.codes, 'a flow step naming a missing symbol was accepted'))

def _explorer(defect=''):
    return Explorer(Workflow((Check(defect),)), (State(),), tuple(EXPECTED), invariants=INVARIANTS, max_sequence_length=1, progress_steps=0)

def build_explorer():
    return _explorer()

def broken_variants():
    return {name: _explorer(name) for name in DEFECTS}

def _write(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding='utf-8')
API = 'from core import work\n\n\ndef handle():\n    return work()\n'
CORE = 'class Store:\n    def save(self):\n        return 1\n\n\ndef work():\n    return 1\n\n\ndef extra():\n    return 2\n\n\ndef _secret():\n    return 3\n'

def _component(cid, layer, files, entrypoints, depends_on):
    return {'id': cid, 'layer': layer, 'summary': cid + ' code', 'responsibilities': [cid + ' duty'], 'files': files, 'entrypoints': entrypoints, 'state': [], 'side_effects': [], 'depends_on': depends_on, 'tests': [], 'models': [], 'status': 'draft', 'fingerprint': ''}

def _build_base(root):
    _write(root, 'api.py', API)
    _write(root, 'core.py', CORE)
    _write(root, 'util.py', 'def helper():\n    return 0\n')
    _write(root, 'app.py', 'from api import handle\nfrom core import work\n\n\ndef main():\n    return handle() + work()\n')
    data = {'schema': 'flowguard.map.v1', 'project': 'binding', 'layers': ['interface', 'core'], 'ignore': [], 'components': [_component('api', 'interface', ['api.py'], ['api.py:handle'], ['core']), _component('core', 'core', ['core.py'], ['core.py:work', 'core.py:extra'], []), _component('util', 'core', ['util.py'], [], []), _component('app', 'interface', ['app.py'], ['app.py:main'], ['api', 'core'])], 'flows': [{'id': 'chain', 'summary': 'handle then work', 'steps': ['api:handle', 'core:work']}], 'accepted_debts': []}
    _write(root, '.flowguard/map.json', json.dumps(data))
    from flowguard.map import cli
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        cli.main(['--root', str(root), 'confirm', 'api', 'core', 'util', 'app'])

def _edit(root, event):
    data = json.loads((root / '.flowguard/map.json').read_text(encoding='utf-8'))
    comps = {c['id']: c for c in data['components']}
    if event == 'rename_anchor':
        _write(root, 'core.py', CORE.replace('def extra():', 'def extra_renamed():'))
    elif event == 'add_unowned_file':
        _write(root, 'orphan.py', 'def lonely():\n    return 0\n')
    elif event == 'two_owners_one_file':
        comps['util']['files'].append('core.py')
    elif event == 'import_undeclared':
        _write(root, 'api.py', 'from util import helper\n' + API.replace('return work()', 'return work() + helper()'))
    elif event == 'drop_import':
        _write(root, 'api.py', 'def handle():\n    return 1\n')
    elif event == 'inject_dependency':
        _write(root, 'api.py', 'class Service:\n    def __init__(self, store):\n        self.store = store\n\n    def run(self):\n        return self.store.save()\n\n\ndef handle():\n    return 1\n')
        _write(root, 'app.py', 'from api import Service, handle\nfrom core import Store, work\n\n\ndef main():\n    return Service(Store()).run() + handle() + work()\n')
    elif event == 'duplicate_state':
        comps['api']['state'] = ['orders table']
        comps['core']['state'] = ['orders table']
    elif event == 'bad_flow_step':
        data['flows'][0]['steps'][1] = 'core:missing'
    elif event == 'bad_flow_handoff':
        data['flows'][0]['steps'] = ['api:handle reads out.json', 'core:work']
    elif event == 'private_name_use':
        _write(root, 'api.py', 'from core import _secret, work\n\n\ndef handle():\n    return work() + _secret()\n')
    (root / '.flowguard/map.json').write_text(json.dumps(data), encoding='utf-8')
    return data

class RealCheck:

    def __init__(self, base):
        self.base = base

    def reset(self, initial_state):
        self.state = initial_state

    def apply_step(self, step):
        event = step.function_input
        with tempfile.TemporaryDirectory(prefix='flowguard-binding-') as directory:
            root = Path(shutil.copytree(self.base, Path(directory) / 'project'))
            data = _edit(root, event)
            inv = build_inventory(root, [], write_cache=False)
            findings = run_check(root, data, inv)
            if event == 'private_name_use':
                findings += run_lint(root, data, inv, write_cache=False)
        self.state = State(event, tuple(sorted({f.code for f in findings} & set(CODES))))
        return ReplayObservation(function_name=step.function_name, observed_output=event, observed_state=self.state)

    def observe_state(self):
        return self.state

def conformance():
    last = None
    with tempfile.TemporaryDirectory(prefix='flowguard-binding-base-') as directory:
        base = Path(directory)
        _build_base(base)
        for trace in select_covering_traces(build_explorer().explore().traces):
            last = replay_trace(trace=trace, adapter=RealCheck(base), invariants=INVARIANTS, rules=(projected_state_matches(), projected_output_matches()))
            if not last.ok:
                return last
    return last
