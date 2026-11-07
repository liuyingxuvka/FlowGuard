"""Optional diagnostics retain real events and never decide model outcomes."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import uuid

from flowguard.intent import diagnostics
from flowguard.intent.anchors import collect_sources
from flowguard.intent.diagnostics import EventLog
from flowguard.intent.flow import Capture, Event, Flow, Node, runtime_check


def project(root, body=None):
    name = 'diagnostic_case_' + uuid.uuid4().hex
    path = root / (name + '.py')
    path.write_text(body or '''# flowguard: event begin(value: int)
def begin(value: int): return value
# flowguard: event save(value: int)
def save(value: int): return value
# flowguard: event finish(value: int)
def finish(value: int): return value
''')
    index = collect_sources(root, [(path.name, name)])
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    model = Flow('ORDER', 'assumed: save before finish',
                 (Node('begin'), Node('save', phase='return'), Node('finish', phase='return')),
                 (('begin', 'save'), ('save', 'finish')))
    return index, module, model


def test_disabled_diagnostics_have_no_clock_or_file(tmp_path, monkeypatch):
    def forbidden():
        raise AssertionError('disabled diagnostics requested a clock')
    monkeypatch.setattr(diagnostics, 'time', SimpleNamespace(monotonic_ns=forbidden, time_ns=forbidden))
    index, module, model = project(tmp_path)
    with Capture(tmp_path, index, 'one') as captured:
        module.begin(3); module.save(3); module.finish(3)
    assert runtime_check(model, captured.events, index)['verdict'] == 'ok'
    assert not (tmp_path / 'anchor-events.jsonl').exists()


def test_optional_sink_keeps_exact_events_and_flushes_actual_readings(tmp_path):
    index, module, model = project(tmp_path)
    def exercise(after_begin=lambda: None):
        module.begin(3)
        after_begin()
        module.save(3); module.finish(3)
    with Capture(tmp_path, index, 'one') as off:
        exercise()
    path = tmp_path / 'anchor-events.jsonl'
    def inspect_live():
        live = [json.loads(line) for line in path.read_text().splitlines()]
        assert [row['phase'] for row in live] == ['call', 'return']
    with EventLog(path) as log, Capture(tmp_path, index, 'one', on_event=log.event) as on:
        exercise(inspect_live)
    assert on.events == off.events
    assert runtime_check(model, on.events, index) == runtime_check(model, off.events, index)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [row['monotonic_ns'] for row in rows] == sorted(row['monotonic_ns'] for row in rows)
    assert all(row['elapsed_ns'] >= 0 for row in rows if row['phase'] == 'return')
    assert rows[0]['inputs'] == {'value': 3} and rows[1]['result'] == 3
    assert rows[0]['file'] == on.events[0].file and rows[0]['source_digest'] == on.events[0].source_digest
    assert all(row['case'] == 'one' and row['pid'] > 0 for row in rows)


def test_broken_diagnostic_callback_keeps_original_red_capture(tmp_path):
    index, module, model = project(tmp_path)
    def broken(event):
        raise OSError('diagnostic storage unavailable')
    with Capture(tmp_path, index, 'one', on_event=broken) as captured:
        module.begin(3); module.finish(3); module.save(3)
    assert len(captured.events) == 6 and not captured.issues
    assert captured.diagnostic_issues == ['diagnostics unavailable: callback raised OSError']
    assert runtime_check(model, captured.events, index)['verdict'] == 'red'


def test_writer_failure_is_reported_without_raising_or_losing_real_event(tmp_path):
    class Broken:
        def write(self, value):
            raise OSError('full disk')
        def close(self):
            pass
    log = EventLog(tmp_path / 'anchor-events.jsonl')
    log.saved.close()
    log.saved = Broken()
    event = Event('START', 'call', {'value': 3})
    log.event(event)
    assert len(log.issues) == 1 and 'OSError' in log.issues[0]
    assert log.saved is None
    log.event(event)
    log.close()
    assert len(log.issues) == 1


def test_diagnostic_readings_do_not_execute_repr_or_copy_large_payload(tmp_path):
    class Opaque:
        def __repr__(self):
            raise AssertionError('diagnostics must not execute arbitrary repr')
    path = tmp_path / 'anchor-events.jsonl'
    with EventLog(path) as log:
        log.event(Event('START', 'call', {'opaque': Opaque(), 'large': 'private' * 100_000}))
    row = json.loads(path.read_text())
    assert row['inputs']['opaque'] == {'omitted': 'Opaque'}
    assert row['inputs']['large'] == {'omitted': 'long str', 'characters': 700_000}
    assert path.stat().st_size < 1000 and 'private' not in path.read_text()


def test_actual_state_readings_are_visible_without_recomputing_them(tmp_path):
    index, module, _ = project(tmp_path, '''class Job:
    # flowguard: states Job.status = new | saved
    status = 'new'
    # flowguard: event save(value: int)
    def save(self, value: int):
        self.status = 'saved'
        return value
''')
    path = tmp_path / 'anchor-events.jsonl'
    with EventLog(path) as log, Capture(tmp_path, index, 'state', on_event=log.event) as captured:
        assert module.Job().save(3) == 3
    row = [json.loads(line) for line in path.read_text().splitlines()][-1]
    assert captured.events[-1].before_states == row['before_states'] == {'Job.status': 'new'}
    assert captured.events[-1].states == row['states'] == {'Job.status': 'saved'}
