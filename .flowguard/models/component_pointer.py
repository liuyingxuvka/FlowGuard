"""A component's description is never reported current after its code changed.

The fingerprint written by ``confirm`` is the component's "current pointer".
Protected failures:
  * check reports a confirmed component as clean although its files changed
  * confirm accepts a component that has no description
Conformance replays model traces against the real flowguard.map implementation
in a throw-away project directory.
"""
from __future__ import annotations
import io
import json
import shutil
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, replace
from pathlib import Path
from flowguard import FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace, select_covering_traces
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer
MODEL_ID = 'component_pointer'
PARENT = 'map-file'
COMPONENTS = ['map-file', 'cli']
IMPLEMENTED_BY = {'Confirm': 'flowguard/map/cli.py:cmd_confirm', 'Fingerprint': 'flowguard/map/mapfile.py:fingerprint'}
USES = {'Check': 'flowguard/map/check.py:run_check'}
TESTED_BY = {'clean_means_current': ['tests/test_flowguard_map.py:test_stale_after_owned_file_changes_and_confirm_clears_it'], 'confirmed_means_described': ['tests/test_flowguard_map.py:test_filled_map_checks_clean_after_confirm']}
NOT_MODELED = {'flowguard/__main__.py:main': 'CLI dispatcher; command and encoding integration are covered by CLI tests, not a modeled business transition.', 'flowguard/map/cli.py:main': 'Map command dispatcher; integration tests cover argument dispatch and statuses.', 'flowguard/map/inventory.py:build_inventory': 'Static source inventory writes disposable cache; encoding/cache and impact regressions cover it.', 'flowguard/templates.py:write_template_files': 'Explicit template file writer; generated template and overwrite tests cover the filesystem integration.'}
MAX_EDITS = 2

@dataclass(frozen=True)
class Event:
    kind: str

@dataclass(frozen=True)
class State:
    status: str = 'draft'
    described: bool = False
    code_version: int = 0
    confirmed_version: int = -1
    model_edited: bool = False
    last_report: str = ''

class Step:
    """Intended behavior of edit / describe / confirm / check."""
    name = 'Step'
    reads = ('status', 'described', 'code_version', 'confirmed_version', 'model_edited')
    writes = ('status', 'described', 'code_version', 'confirmed_version', 'last_report', 'model_edited')

    def confirm_allowed(self, state: State) -> bool:
        return state.described

    def report(self, state: State) -> str:
        if state.model_edited:
            return 'model_edited_outside_target'
        if state.status == 'draft':
            return 'draft'
        return 'clean' if state.confirmed_version == state.code_version else 'stale'

    def apply(self, event: Event, state: State):
        if event.kind == 'edit_model':
            return (FunctionResult('model_edited', replace(state, model_edited=True, last_report=''), label='edit_model'),)
        if event.kind == 'edit':
            if state.code_version >= MAX_EDITS:
                return (FunctionResult('edit_limit', state, label='edit_limit'),)
            return (FunctionResult('edited', replace(state, code_version=state.code_version + 1, last_report=''), label='edit'),)
        if event.kind == 'describe':
            return (FunctionResult('described', replace(state, described=True), label='describe'),)
        if event.kind == 'confirm':
            if not self.confirm_allowed(state):
                return (FunctionResult('refused', state, label='confirm_refused'),)
            return (FunctionResult('confirmed', replace(state, status='confirmed', confirmed_version=state.code_version), label='confirm'),)
        report = self.report(state)
        return (FunctionResult(report, replace(state, last_report=report), label=f'check_{report}'),)

class ConfirmWithoutDescription(Step):
    """Known-bad: confirm does not require a description."""

    def confirm_allowed(self, state: State) -> bool:
        return True

class CheckIgnoresChanges(Step):
    """Known-bad: check reports every confirmed component as clean."""

    def report(self, state: State) -> str:
        return 'draft' if state.status == 'draft' else 'clean'

def _clean_means_current(state: State, trace) -> InvariantResult:
    if state.last_report == 'clean' and state.confirmed_version != state.code_version:
        return InvariantResult.fail('check reported clean after the owned file changed')
    return InvariantResult.pass_()

def _confirmed_means_described(state: State, trace) -> InvariantResult:
    if state.status == 'confirmed' and (not state.described):
        return InvariantResult.fail('a component without description was confirmed')
    return InvariantResult.pass_()

class IgnoreModelEdit(Step):

    def report(self, state):
        return super().report(replace(state, model_edited=False))
INVARIANTS = (Invariant('clean_means_current', 'clean is reported only when the code is unchanged since confirm', _clean_means_current), Invariant('confirmed_means_described', 'confirm requires summary and responsibilities', _confirmed_means_described))
EVENTS = tuple((Event(kind) for kind in ('edit', 'describe', 'confirm', 'check')))

def _explorer(step: Step) -> Explorer:
    return Explorer(workflow=Workflow((step,)), initial_states=(State(),), external_inputs=EVENTS, invariants=INVARIANTS, max_sequence_length=5, progress_steps=0)

def build_explorer() -> Explorer:
    return _explorer(Step())

def broken_variants() -> dict:
    return {'confirm_without_description': _explorer(ConfirmWithoutDescription()), 'check_ignores_changes': _explorer(CheckIgnoresChanges())}

class _RealMap:
    """Drives the real flowguard.map code in a temporary project with one component."""

    def reset(self, initial_state: State) -> None:
        from flowguard.map import cli
        self.cli = cli
        self.root = Path(tempfile.mkdtemp(prefix='fg-pointer-'))
        (self.root / 'app').mkdir()
        self.code_version = 0
        self.version_of: dict[str, int] = {}
        self._write_code()
        self._run('scan')
        data = self._map()
        data['components'] = [dict(data['components'][0], id='app', files=['app/*.py'], summary='', responsibilities=[], depends_on=[], tests=[])]
        self._save(data)
        self.last_report = ''
        self.model_edited = False
        model = self.root / '.flowguard/models/presence.py'
        model.parent.mkdir(parents=True, exist_ok=True)
        model.write_text(PRESENCE_MODEL)
        from flowguard.map.common import content_digest
        data = self._map()
        data['components'][0]['models'] = ['.flowguard/models/presence.py']
        data['model_digests'] = {'.flowguard/models/presence.py': content_digest(model)}
        self._save(data)

    def close(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _write_code(self) -> None:
        (self.root / 'app' / 'core.py').write_text(f'VERSION = {self.code_version}\n\ndef current_version(): return VERSION\n', encoding='utf-8')
        from flowguard.map.mapfile import fingerprint
        self.version_of[fingerprint(self.root, ['app/core.py'])] = self.code_version

    def _run(self, *argv: str) -> int:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return self.cli.main(['--root', str(self.root), *argv])

    def _map(self) -> dict:
        return json.loads((self.root / '.flowguard' / 'map.json').read_text(encoding='utf-8'))

    def _save(self, data: dict) -> None:
        (self.root / '.flowguard' / 'map.json').write_text(json.dumps(data), encoding='utf-8')

    def apply_step(self, step) -> ReplayObservation:
        kind = step.function_input.kind
        if kind == 'edit_model':
            model = self.root / '.flowguard/models/presence.py'
            model.write_text(model.read_text() + '\n# an in-place edit\n')
            self.model_edited, self.last_report = (True, '')
            output = 'model_edited'
        elif kind == 'edit':
            if self.code_version >= MAX_EDITS:
                output = 'edit_limit'
            else:
                self.code_version += 1
                self._write_code()
                self.last_report = ''
                output = 'edited'
        elif kind == 'describe':
            data = self._map()
            data['components'][0].update(summary='the app', responsibilities=['run the app'])
            self._save(data)
            output = 'described'
        elif kind == 'confirm':
            output = 'confirmed' if self._run('confirm', 'app') == 0 else 'refused'
        else:
            from flowguard.map.check import run_check
            from flowguard.map.inventory import build_inventory
            from flowguard.map.mapfile import ignore_patterns, load_map
            data = load_map(self.root)
            codes = {f.code for f in run_check(self.root, data, build_inventory(self.root, ignore_patterns(data)))}
            output = 'model_edited_outside_target' if 'model_edited_outside_target' in codes else 'draft' if 'draft' in codes else 'stale' if {'stale', 'fingerprint_migrate'} & codes else 'clean'
            self.last_report = output
        return ReplayObservation(function_name=step.function_name, observed_output=output, observed_state=self.observe_state())

    def observe_state(self) -> State:
        comp = self._map()['components'][0]
        confirmed = comp['status'] == 'confirmed'
        return State(status=comp['status'], described=bool(comp.get('summary') and comp.get('responsibilities')), code_version=self.code_version, confirmed_version=self.version_of.get(comp.get('fingerprint', ''), -1) if confirmed else -1, last_report=self.last_report, model_edited=self.model_edited)

    def observe_output(self):
        return None

def conformance():
    """Replay traces covering every modeled transition against the real implementation."""
    from flowguard.map import mapfile
    from flowguard.map.facts import CodeFactsReport, Fact
    if 'model_digests' not in mapfile.TOP_KEYS:
        return CodeFactsReport((Fact('model_edited_outside_target_is_named', False, 'model digest tracking is not implemented'),))
    last = None
    for trace in select_covering_traces(build_explorer().explore().traces):
        adapter = _RealMap()
        try:
            last = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS, rules=(projected_state_matches(), projected_output_matches()))
        finally:
            adapter.close()
        if not last.ok:
            return last
    return last
PRESENCE_MODEL = 'from pathlib import Path\nfrom flowguard import FunctionResult, Invariant, InvariantResult, Workflow\nfrom flowguard.explorer import Explorer\nfrom flowguard.map.facts import CodeFactsReport, Fact\nMODEL_ID = "presence"\nPARENT = "app"\nIMPLEMENTED_BY = {"Read": "app/core.py:current_version"}\nRULE = Invariant("present", "source exists", lambda s,t: InvariantResult.pass_() if s else InvariantResult.fail("missing"))\nclass Read:\n    name = "Read"\n    def __init__(self, value=True): self.value = value\n    def apply(self,event,state): return (FunctionResult(self.value,self.value),)\ndef make(value): return Explorer(Workflow((Read(value),)), (True,), ("read",), invariants=(RULE,), max_sequence_length=1,progress_steps=0)\ndef build_explorer(): return make(True)\ndef broken_variants(): return {"missing": make(False)}\ndef conformance():\n    data = (Path.cwd()/"app/core.py").read_bytes()\n    return CodeFactsReport((Fact("native_source", bool(data), repr(data)),))\n'
