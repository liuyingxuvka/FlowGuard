"""Formatting an intentional stop never makes a calibration test pass."""
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from flowguard.intent import anchors, calibration


def decision(x):
    return x <= 3


def body():
    assert decision(2) is True


def broken_body():
    raise AssertionError('real scenario body failure')


def driver(kind):
    cls = calibration._Driver if kind == 'point' else calibration._ScenarioDriver
    instance = cls.__new__(cls)
    instance.running, instance.stage, instance.values = False, 'zero', {}
    instance.anchor = SimpleNamespace(parameters=() if kind == 'scenario' else (SimpleNamespace(name='x'),))
    instance.outcomes, instance.entries, instance.verifier_codes = [], [], ()
    return instance


def captured_call(instance, function):
    arguments = inspect.signature(function).bind(*((2,) if function is decision else ()))
    try:
        instance._call(function, arguments)
    except BaseException:
        return pytest.ExceptionInfo.from_current()
    raise AssertionError('expected a real driver exception')


@pytest.mark.parametrize('kind', ['point', 'scenario'])
def test_only_owned_stop_framework_frames_are_hidden(kind):
    info = captured_call(driver(kind), decision if kind == 'point' else body)
    assert type(info.value) is calibration._Stop
    assert 'calibration.py' not in str(info.getrepr(style='short'))
    assert '_Stop' in str(info.getrepr(style='short'))
    assert 'calibration.py' in str(info.getrepr(style='short', tbfilter=False))
    instance = driver(kind)
    instance.running = True
    failure = captured_call(instance, decision if kind == 'point' else body)
    assert type(failure.value) is calibration._Unsupported
    assert 'calibration.py' in str(failure.getrepr(style='short'))


def test_real_scenario_failure_keeps_its_original_message_and_frames():
    info = captured_call(driver('scenario'), broken_body)
    rendered = str(info.getrepr(style='short'))
    assert type(info.value) is AssertionError
    assert 'real scenario body failure' in rendered
    assert 'calibration.py' in rendered and 'broken_body' in rendered


def native_project(tmp_path, extra=''):
    (tmp_path/'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    (tmp_path/'policy_stop_reporting.py').write_text('''# flowguard: sensor REPORT_LIMIT(x: count) -> allowed: bool calibrated_by=test_native_stop.py::test_native
def limit(x: int) -> bool:
    return x <= 3
''')
    (tmp_path/'test_native_stop.py').write_text('from policy_stop_reporting import limit\nimport pytest\n'+extra+
        'def test_native():\n    assert limit(2) is True\n')
    return anchors.collect_sources(tmp_path, [('policy_stop_reporting.py','policy_stop_reporting')]).entries[0]


def test_actual_pytest_baseline_zero_and_case_keep_zero_one_one(tmp_path, monkeypatch):
    anchor = native_project(tmp_path)
    real_main = pytest.main
    reports = []
    class Recorder:
        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_makereport(self, item, call):
            outcome = yield
            report = outcome.get_result()
            reports.append((report.when, report.outcome, str(report.longrepr)))
    def recorded(args, plugins):
        return real_main(args, plugins=[*plugins, Recorder()])
    monkeypatch.setattr(pytest, 'main', recorded)
    results = [calibration._stage(tmp_path, anchor, values, stage)
               for stage, values in [('baseline',{}),('zero',{}),('case',{'x':5})]]
    assert [result['status'] for result in results] == ['ok','ok','ok'], results
    assert [result['pytest_exit'] for result in results] == [0,1,1]
    assert [result['outcome'] for result in results] == [calibration._encode(v) for v in (True,True,False)]
    stops = [text for phase, outcome, text in reports if phase == 'call' and outcome == 'failed']
    assert len(stops) == 2 and all('_Stop' in text for text in stops)


def test_caught_stop_remains_unverified(tmp_path):
    anchor = native_project(tmp_path)
    (tmp_path/'test_native_stop.py').write_text('''from policy_stop_reporting import limit
def test_native():
    try:
        assert limit(2) is True
    except BaseException:
        pass
''')
    result = calibration._stage(tmp_path, anchor, {}, 'zero')
    assert result['status'] == 'grey' and 'controlled stop did not escape' in ' '.join(result['reasons'])


@pytest.mark.parametrize('phase', ['setup','teardown'])
def test_real_fixture_failures_still_fail_and_keep_the_original_message(tmp_path, monkeypatch, phase):
    extra = ('@pytest.fixture(autouse=True)\ndef fixture():\n'+
             ('    yield\n' if phase == 'teardown' else '')+
             '    raise AssertionError("real '+phase+' failure")\n')
    anchor = native_project(tmp_path, extra)
    real_main = pytest.main
    reports = []
    class Recorder:
        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_makereport(self, item, call):
            outcome = yield
            report = outcome.get_result()
            reports.append((report.when, report.outcome, str(report.longrepr)))
    def recorded(args, plugins):
        return real_main(args, plugins=[*plugins, Recorder()])
    monkeypatch.setattr(pytest, 'main', recorded)
    result = calibration._stage(tmp_path, anchor, {}, 'zero')
    assert result['status'] == ('grey' if phase == 'setup' else 'red'), result
    assert any(p == phase and outcome == 'failed' and 'real '+phase+' failure' in text
               for p, outcome, text in reports), reports
