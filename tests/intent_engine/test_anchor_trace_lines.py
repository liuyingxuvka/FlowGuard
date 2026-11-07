"""Boundary observations keep their events without unused per-line dispatch."""
import sys

import pytest

from flowguard.intent.flow import Capture
from tests.intent_engine.test_flow_model import source


class CountingCapture(Capture):
    def __init__(self, *args, **kwargs):
        self.line_calls = 0
        super().__init__(*args, **kwargs)

    def _callback(self, frame, event, arg):
        if event == 'line' and id(frame) in self._frames:
            self.line_calls += 1
        return super()._callback(frame, event, arg)


def readings(capture):
    return [(e.anchor, e.phase, e.values, e.result,
             type(e.error).__name__ if e.error else None,
             str(e.error) if e.error else None,
             e.occurrence, e.sequence, e.states, e.before_states)
            for e in capture.events]


def test_nested_boundary_capture_keeps_readings_and_exceptions_without_line_callbacks(tmp_path):
    index, module = source(tmp_path, '''class Meter:
    # flowguard: states Meter.status = ready | done
    status = 'ready'
    # flowguard: event WORK(value: int)
    def work(self, value: int):
        total = 0
        for _ in range(20):
            total += value
        self.status = 'done'
        if value < 0:
            raise ValueError('native negative')
        return total
''')
    ambient = sys.gettrace()
    with CountingCapture(tmp_path, index, 'outer') as outer:
        owner = sys.gettrace()
        with CountingCapture(tmp_path, index, 'inner') as inner:
            assert module.Meter().work(4) == 80
            with pytest.raises(ValueError, match='native negative'):
                module.Meter().work(-1)
        assert sys.gettrace() is owner
    assert sys.gettrace() is ambient
    assert outer.issues == inner.issues == []
    assert readings(outer) == readings(inner)
    assert [e.phase for e in outer.events] == ['call', 'return', 'call', 'raise']
    assert [e.values['value'] for e in outer.events] == [4, 4, -1, -1]
    assert outer.events[1].result == 80
    assert outer.events[0].states == {'Meter.status': 'ready'}
    assert outer.events[1].states == {'Meter.status': 'done'}
    assert outer.events[3].before_states == {'Meter.status': 'ready'}
    assert outer.events[3].states == {'Meter.status': 'done'}
    assert outer.line_calls == inner.line_calls == 0


def test_closing_observation_inside_a_live_anchor_restores_its_line_flag(tmp_path):
    index, module = source(tmp_path, '''import sys
# flowguard: event CLOSE()
def close():
    frame = sys._getframe()
    capture.close()
    return frame.f_trace_lines
''')
    ambient = sys.gettrace()
    with Capture(tmp_path, index, 'live-close') as capture:
        module.capture = capture
        assert module.close() is True
        assert sys.gettrace() is ambient
    assert sys.gettrace() is ambient
    assert capture.issues == []
