"""Diagnostic intervals use real high-resolution monotonic readings, including ties."""
import importlib.util
import json
import time
from types import SimpleNamespace

import pytest

from flowguard.intent import diagnostics
from flowguard.intent.anchors import collect_sources
from flowguard.intent.flow import Capture, Event


def test_short_real_call_is_measured_when_coarse_monotonic_clock_has_not_ticked(tmp_path, monkeypatch):
    source = tmp_path / 'clock_target.py'
    source.write_text('import time\n# flowguard: event WAIT()\ndef wait(): time.sleep(.01)\n')
    index = collect_sources(tmp_path, [(source.name, 'clock_target')])
    spec = importlib.util.spec_from_file_location('clock_target', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(diagnostics, 'time', SimpleNamespace(
        monotonic_ns=lambda: 100_000_000,
        perf_counter_ns=time.perf_counter_ns, time_ns=time.time_ns))
    path = tmp_path / 'events.jsonl'
    with diagnostics.EventLog(path) as log, Capture(tmp_path, index, 'short', on_event=log.event) as captured:
        module.wait()
    assert not captured.issues
    assert [event.phase for event in captured.events] == ['call', 'return']
    call, returned = [json.loads(line) for line in path.read_text().splitlines()]
    assert returned['elapsed_ns'] == returned['monotonic_ns'] - call['monotonic_ns'] > 0
    assert call['elapsed_ns'] is None
    assert type(returned['elapsed_ns']) is type(returned['monotonic_ns']) is int


@pytest.mark.parametrize('phase', ['return', 'raise'])
def test_equal_high_resolution_readings_remain_real_zero(tmp_path, monkeypatch, phase):
    coarse = iter((100_000_000, 116_000_000))
    monkeypatch.setattr(diagnostics, 'time', SimpleNamespace(
        monotonic_ns=lambda: next(coarse), perf_counter_ns=lambda: 42, time_ns=time.time_ns))
    path = tmp_path / 'events.jsonl'
    with diagnostics.EventLog(path) as log:
        call = log.event(Event('WAIT', 'call', {}))
        returned = log.event(Event('WAIT', phase, {}, error=ValueError('actual') if phase == 'raise' else None))
    assert call['monotonic_ns'] == returned['monotonic_ns'] == 42
    assert call['elapsed_ns'] is None
    assert returned['elapsed_ns'] == returned['monotonic_ns'] - call['monotonic_ns'] == 0
    assert returned['phase'] == phase
    assert returned['error'] == ('ValueError' if phase == 'raise' else None)
