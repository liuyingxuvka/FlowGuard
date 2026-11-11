"""Native same-session reports replace the retired controlled-stop protocol."""
from pathlib import Path

import pytest

from flowguard.intent import anchors, calibration
from flowguard.intent.cells import Raised
from flowguard.intent.runtime import Runtime
from tests.intent_engine._protocol_controls import bind_anchor
from tests.intent_engine._source_fixture import source_sessions


def native_project(tmp_path, extra='', body='assert limit(2) is True', *, refusal=False):
    (tmp_path/'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    source = '''# flowguard: sensor REPORT_LIMIT(x: count) -> allowed: bool calibrated_by=test_native_stop.py::test_native
def limit(x: int) -> bool:
'''
    if refusal:
        source += '    if x < 0: raise ValueError("native negative refusal")\n'
    (tmp_path/'policy_stop_reporting.py').write_text(source + '    return x <= 3\n')
    text = 'from policy_stop_reporting import limit\nimport pytest\n' + extra
    text += 'def test_native():\n' + ''.join('    ' + line + '\n' for line in body.splitlines())
    (tmp_path/'test_native_stop.py').write_text(text)
    return anchors.collect_sources(tmp_path, [('policy_stop_reporting.py','policy_stop_reporting')]).entries[0]


def test_requested_inputs_run_sealed_from_the_recorded_call_without_running_the_test_again(tmp_path, monkeypatch):
    log = tmp_path / 'runs.log'
    anchor = native_project(tmp_path, body=f'open({str(log)!r}, "a").write("run\\n")\nassert limit(2) is True')
    scope, item = bind_anchor(tmp_path, anchor)
    def no_nested_session(*args, **kwargs):
        raise AssertionError('the collected pytest session must be reused')
    monkeypatch.setattr(pytest, 'main', no_nested_session)
    readings = [calibration.execute(tmp_path, anchor, values) for values in ({}, {'x': 5}, {'x': 1})]
    assert [reading.status for reading in readings] == ['ok', 'ok', 'ok'], readings
    assert [reading.value for reading in readings] == [True, False, True]
    # The named test ran once, in its ordinary run. Each requested input is evaluated sealed with that run's
    # recorded call as its context; no point runs the test again, so no controlled stop exists either.
    assert log.read_text().split() == ['run']
    assert not hasattr(Runtime, 'replay') and not hasattr(calibration, '_Stop')
    assert calibration._context(tmp_path, anchor.calibrated_by) == (scope, item)


def test_native_refusal_is_not_a_harness_failure(tmp_path):
    anchor = native_project(tmp_path, refusal=True)
    bind_anchor(tmp_path, anchor)
    actual = calibration.execute(tmp_path, anchor, {'x': -1})
    assert actual.status == 'ok', actual.reasons
    assert isinstance(actual.value, Raised)
    # The requested point runs sealed: its exception comes back as its type and message (JSON), not a traceback.
    assert type(actual.value.error) is ValueError and str(actual.value.error) == 'native negative refusal'


def test_swallowing_baseexception_cannot_supply_an_absent_anchor_reading(tmp_path):
    anchor = native_project(tmp_path, body='try:\n    raise ValueError("swallowed harness failure")\nexcept BaseException:\n    pass')
    bind_anchor(tmp_path, anchor)
    actual = calibration.execute(tmp_path, anchor, {'x': 5})
    assert actual.status == 'grey' and actual.value is None
    assert 'actual anchor exactly once' in ' '.join(actual.reasons)


@pytest.mark.parametrize('phase', ['setup','teardown'])
def test_real_fixture_failures_still_fail_and_keep_the_original_message(tmp_path, monkeypatch, phase):
    extra = ('@pytest.fixture(autouse=True)\ndef fixture():\n' +
             ('    yield\n' if phase == 'teardown' else '') +
             '    raise AssertionError("real ' + phase + ' failure")\n')
    anchor = native_project(tmp_path, extra)
    scope, item = bind_anchor(tmp_path, anchor)
    # The ordinary run's own report of the failed phase keeps the original exception.
    [(when, outcome, error)] = scope.runtime.outcomes[item.nodeid]
    assert (when, outcome, type(error), str(error)) == (phase, 'failed', AssertionError, 'real ' + phase + ' failure')
    actual = calibration.execute(tmp_path, anchor, {'x': 5})
    assert actual.status == 'red' and actual.value is None, actual
    assert not isinstance(actual.value, Raised)
    assert actual.reasons == ('real calibration test did not pass completely: ' + phase + ' failed',), actual.reasons


def test_real_body_failure_is_red_with_the_original_exception_and_no_second_run(tmp_path):
    log = tmp_path / 'runs.log'
    anchor = native_project(tmp_path, body=f'open({str(log)!r}, "a").write("run\\n")\nassert limit(2) is True\n'
                                           'raise AssertionError("real scenario body failure")')
    scope, item = bind_anchor(tmp_path, anchor)
    [(when, outcome, error)] = scope.runtime.outcomes[item.nodeid]
    assert (when, outcome, type(error), str(error)) == ('call', 'failed', AssertionError, 'real scenario body failure')
    actual = calibration.execute(tmp_path, anchor, {'x': 5})
    assert actual.status == 'red' and not isinstance(actual.value, Raised)
    assert actual.reasons == ('real calibration test did not pass completely: call failed',), actual.reasons
    assert log.read_text().split() == ['run']


def test_collection_failure_keeps_its_native_error_and_source_not_a_refusal(tmp_path):
    anchor = native_project(tmp_path)
    test = tmp_path / 'test_native_stop.py'
    test.write_text(test.read_text() + 'raise AssertionError("real collection failure")\n')
    with pytest.raises(AssertionError, match='real collection failure') as native:
        bind_anchor(tmp_path, anchor)
    assert type(native.value) is AssertionError
    assert Path(native.traceback[-1].path).resolve() == test.resolve()
