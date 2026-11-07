"""Diagnostic reporting cannot replace an already computed model outcome."""
import builtins
import io
import json
from types import SimpleNamespace

import pytest

from flowguard.intent import diagnostics, plugin
from flowguard.intent.diagnostics import EventLog


def session(tmp_path):
    state = plugin.Session.__new__(plugin.Session)
    state.previous_session = plugin._CURRENT
    state.process_calls, state.import_environment = [], {}
    state.owns_host = state.owns_root = False
    state.folder = SimpleNamespace(cleanup=lambda: None)
    state.diagnostics = EventLog(tmp_path / 'anchor-events.jsonl')
    state.owns_diagnostics = True
    state.diagnostic_scope = 1, id(state)
    state.diagnostic_issues = []
    state.diagnostic_models = [dict(grey=[], runtime=dict(unclaimed_relations=0), info=[])]
    state.results = dict(model=dict(verdict='red'))
    return state


@pytest.mark.parametrize('output', ['stdout', 'stderr'])
def test_reporting_io_failure_preserves_model_and_records_unavailability(tmp_path, monkeypatch, output):
    state = session(tmp_path)
    closed = io.StringIO()
    closed.close()
    class BrokenFlush:
        def write(self, value):
            return len(value)
        def flush(self):
            raise OSError('diagnostic flush failed')
    if output == 'stderr':
        state.diagnostic_issues.append('diagnostics unavailable: earlier diagnostic failure')
    def report(*args, **kwargs):
        text = str(args[0]) if args else ''
        selected = (output == 'stdout' and text.startswith('FlowGuard anchor diagnostics:')
                    or output == 'stderr' and text.startswith('FlowGuard diagnostics unavailable:'))
        if selected:
            assert kwargs.get('flush') is True
            kwargs['file'] = closed if output == 'stdout' else BrokenFlush()
        return builtins.print(*args, **kwargs)
    monkeypatch.setattr(diagnostics, 'print', report, raising=False)
    state.close()
    assert state.results == dict(model=dict(verdict='red'))
    assert state.closed and state.diagnostics.saved is None
    rows = [json.loads(line) for line in state.diagnostics.path.read_text().splitlines()]
    failed = [row for row in rows if row.get('kind') == 'diagnostic-unavailable']
    assert failed and all(row['output'] == output for row in failed)
    assert any(output + ' reporting raised' in issue for issue in state.diagnostics.issues)
    assert rows[-1]['kind'] == 'closed'


def test_reporting_does_not_swallow_keyboard_interrupt(tmp_path, monkeypatch):
    state = session(tmp_path)
    def interrupted(*args, **kwargs):
        if args and str(args[0]).startswith('FlowGuard anchor diagnostics:'):
            raise KeyboardInterrupt()
        return builtins.print(*args, **kwargs)
    monkeypatch.setattr(diagnostics, 'print', interrupted, raising=False)
    try:
        with pytest.raises(KeyboardInterrupt):
            state.close()
        assert state.results == dict(model=dict(verdict='red'))
    finally:
        state.diagnostics.close()
