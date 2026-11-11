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


def recorded_replays(monkeypatch):
    actual = Runtime.replay
    results = []
    def recorded(self, item, **kwargs):
        result = actual(self, item, **kwargs)
        results.append(result)
        return result
    monkeypatch.setattr(Runtime, 'replay', recorded)
    return results


def test_requested_inputs_run_sealed_at_the_real_call_without_a_nested_session(tmp_path, monkeypatch):
    anchor = native_project(tmp_path)
    scope, item = bind_anchor(tmp_path, anchor)
    results = recorded_replays(monkeypatch)
    def no_nested_session(*args, **kwargs):
        raise AssertionError('the collected pytest session must be reused')
    monkeypatch.setattr(pytest, 'main', no_nested_session)
    readings = [calibration.execute(tmp_path, anchor, values) for values in ({}, {'x': 5}, {'x': 1})]
    assert [reading.status for reading in readings] == ['ok', 'ok', 'ok'], readings
    assert [reading.value for reading in readings] == [True, False, True]
    assert len(results) == 3
    # The actual inputs run the whole named test natively; a requested input is evaluated sealed once the
    # real call agrees with the sealed source, and that replay ends at the real call: its only failure is
    # FlowGuard's own stop there, never a project failure (the complete run was already prepared).
    assert results[0]['status'] == 'ok' and all(report.passed for report in results[0]['reports'])
    for result in results[1:]:
        assert [type(error).__name__ for _, error in result['errors']] == ['_Stop'], result['errors']
        assert [report.when for report in result['reports'] if not report.passed] == ['call'], result['reports']
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
    replay = scope.runtime.replay(item, nextitem=scope.nextitem)
    assert replay['status'] == 'grey'
    failures = [report for report in replay['reports'] if report.failed]
    assert any(report.when == phase and 'real ' + phase + ' failure' in str(report.longrepr) for report in failures)
    assert any(when == phase and type(error) is AssertionError and str(error) == 'real ' + phase + ' failure'
               for when, error in replay['errors'])
    actual = calibration.execute(tmp_path, anchor, {'x': 5})
    assert actual.status == 'red' and actual.value is None, actual
    assert not isinstance(actual.value, Raised)


def test_real_body_failure_keeps_original_source_and_message_for_each_traceback_style(tmp_path, monkeypatch, request):
    anchor = native_project(tmp_path, body='assert limit(2) is True\nraise AssertionError("real scenario body failure")')
    scope, item = bind_anchor(tmp_path, anchor)
    failures = []
    for style in ('short', 'line'):
        monkeypatch.setattr(request.config.option, 'tbstyle', style)
        replay = scope.runtime.replay(item, nextitem=scope.nextitem)
        report = next(report for report in replay['reports'] if report.when == 'call')
        assert report.failed and 'real scenario body failure' in str(report.longrepr)
        assert Path(report.longrepr.reprcrash.path).resolve() == (tmp_path / 'test_native_stop.py').resolve()
        assert '_Stop' not in str(report.longrepr)
        error = next(error for phase, error in replay['errors'] if phase == 'call')
        assert type(error) is AssertionError and str(error) == 'real scenario body failure'
        failures.append([(entry.when, entry.outcome) for entry in replay['reports']])
    assert failures[0] == failures[1]
    actual = calibration.execute(tmp_path, anchor, {'x': 5})
    assert actual.status == 'red' and not isinstance(actual.value, Raised)


def test_collection_failure_keeps_its_native_error_and_source_not_a_refusal(tmp_path):
    anchor = native_project(tmp_path)
    test = tmp_path / 'test_native_stop.py'
    test.write_text(test.read_text() + 'raise AssertionError("real collection failure")\n')
    with pytest.raises(AssertionError, match='real collection failure') as native:
        bind_anchor(tmp_path, anchor)
    assert type(native.value) is AssertionError
    assert Path(native.traceback[-1].path).resolve() == test.resolve()
