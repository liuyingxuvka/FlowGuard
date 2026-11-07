"""Counterfactual calibration readings never become ordinary coverage."""
from contextlib import ExitStack
import importlib
import sys
import uuid

import pytest

from flowguard.intent import anchors, calibration
from flowguard.intent.config import load_config, setup_path, project_code
from flowguard.intent.flow import Capture, Flow, Node, _without_ordinary_observers
from flowguard.intent.imports import prepare
from flowguard.intent.tracer import Footprint


def project(root, outer_body=None):
    module = 'probe_app_' + uuid.uuid4().hex
    test = 'test_probe_' + uuid.uuid4().hex + '.py'
    (root/'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    outer = ('    return runner()\n' if outer_body is None else
             ''.join('    '+line+'\n' for line in outer_body.splitlines()))
    (root/(module+'.py')).write_text(
        '# flowguard: sensor LIMIT(x: count) -> allowed: bool calibrated_by='+test+'::test_native\n'
        'def limit(x: int) -> bool:\n    return x <= 3\n'
        '# flowguard: event OUTER()\ndef outer():\n'+outer)
    (root/test).write_text('from '+module+' import limit\ndef test_native():\n    assert limit(2) is True\n')
    index = anchors.collect_sources(root, [(module+'.py', module)])
    anchor = next(a for a in index.entries if a.name == 'LIMIT')
    cfg = load_config(root)
    setup_path(cfg)
    prepare(root)
    app = importlib.import_module(module)
    model = Flow('ORDINARY', 'assumed: ordinary observations',
                 (Node('entry', 'OUTER', start=True), Node('done', 'OUTER', phase='return', end=True)),
                 (('entry', 'done'),))
    return cfg, index, anchor, app, model


@pytest.mark.parametrize('stage', ['baseline', 'zero', 'case'])
@pytest.mark.parametrize('order', ['private-first', 'ordinary-first'])
def test_probe_is_private_while_existing_ordinary_frame_completes(tmp_path, stage, order):
    cfg, index, anchor, app, model = project(tmp_path)
    ordinary = Capture(tmp_path, index, 'ordinary', models=[model], _ordinary=True)
    private = Capture(tmp_path, index, 'private')
    result = {}

    def runner():
        result.update(calibration._stage(tmp_path, anchor, {'x': 4} if stage == 'case' else {}, stage))
        return result['status'] == 'ok'

    app.runner = runner
    ambient = sys.gettrace()
    with ExitStack() as stack:
        for observer in ((private, ordinary) if order == 'private-first' else (ordinary, private)):
            stack.enter_context(observer)
        owned = sys.gettrace()
        with Footprint(project_code(cfg)) as footprint:
            assert app.outer() is True, result
        assert sys.gettrace() is owned
        assert not any(e.anchor == 'LIMIT' for e in ordinary.events)
        probe = [e for e in private.events if e.anchor == 'LIMIT']
        assert [(e.phase, e.values['x']) for e in probe] == [
            ('call', 4 if stage == 'case' else 2), ('return', 4 if stage == 'case' else 2)]
        assert probe[-1].result is (stage != 'case')
        assert app.limit(2) is True
    assert sys.gettrace() is ambient
    assert result['status'] == 'ok', result
    assert result['pytest_exit'] == (0 if stage == 'baseline' else 1), result
    assert [(e.phase, e.result) for e in ordinary.events if e.anchor == 'OUTER'] == [
        ('call', None), ('return', True)]
    assert [(e.phase, e.occurrence) for e in ordinary.events if e.anchor == 'LIMIT'] == [
        ('call', 1), ('return', 1)]
    assert any(qual == 'limit' for _, _, qual in footprint.entered)
    assert ordinary.issues == private.issues == []


def test_explicit_user_capture_models_retains_its_probe_observations(tmp_path):
    _, index, anchor, _, model = project(tmp_path)
    ambient = sys.gettrace()
    with Capture(tmp_path, index, 'explicit', models=[model]) as explicit:
        result = calibration._stage(tmp_path, anchor, {'x': 4}, 'case')
    assert sys.gettrace() is ambient
    assert result['status'] == 'ok' and result['pytest_exit'] == 1, result
    assert [(e.phase, e.values['x']) for e in explicit.events] == [('call', 4), ('return', 4)]
    assert explicit.events[-1].result is False and not explicit.issues


def test_external_debugger_is_not_removed_by_the_probe_boundary(tmp_path):
    _, index, anchor, _, model = project(tmp_path)
    ambient = sys.gettrace()

    def debugger(frame, event, arg):
        return debugger

    sys.settrace(debugger)
    try:
        with Capture(tmp_path, index, 'ordinary', models=[model], _ordinary=True) as ordinary:
            result = calibration._stage(tmp_path, anchor, {'x': 4}, 'case')
        assert sys.gettrace() is debugger
    finally:
        sys.settrace(ambient)
    assert result['status'] == 'grey' and any('debugger/trace' in r for r in result['reasons']), result
    assert any('debugger/trace' in issue for issue in ordinary.issues)


def test_new_foreign_trace_is_retained_and_marks_the_ordinary_scope_unknown(tmp_path):
    _, index, _, _, model = project(tmp_path)
    ambient = sys.gettrace()

    def debugger(frame, event, arg):
        return debugger

    try:
        with Capture(tmp_path, index, 'ordinary', models=[model], _ordinary=True) as ordinary:
            with _without_ordinary_observers():
                assert sys.gettrace() is None
                sys.settrace(debugger)
            assert sys.gettrace() is debugger
    finally:
        sys.settrace(ambient)
    assert any('trace hook changed during calibration probe' in issue for issue in ordinary.issues)


@pytest.mark.parametrize('value', [4, -1])
def test_private_scenario_retains_actual_return_or_refusal(tmp_path, value):
    from tests.intent_engine.test_scenario_execution import scenario
    from flowguard.intent.cells import Raised
    binding = scenario(tmp_path, refusal=True)
    ambient = sys.gettrace()
    with calibration._execution_session(tmp_path):
        assert calibration._prepare_scenario(tmp_path, binding)['status'] == 'ok'
        with Capture(tmp_path, binding.anchor_index, 'ordinary', models=[binding.flow], _ordinary=True) as ordinary:
            actual = calibration._observe_scenario_current(tmp_path, binding, {'x': value})
            assert ordinary.events == []
        assert ordinary.issues == []
    assert sys.gettrace() is ambient
    assert actual.status == 'ok', actual.reasons
    if value < 0:
        assert isinstance(actual.value, Raised) and type(actual.value.error) is ValueError
        assert str(actual.value.error) == 'native negative refusal'
    else:
        assert actual.value is False


@pytest.mark.parametrize('order', ['private-first', 'ordinary-first'])
def test_existing_ordinary_frame_retains_a_real_exception_crossing_the_boundary(tmp_path, order):
    _, index, _, app, model = project(tmp_path)
    ordinary = Capture(tmp_path, index, 'ordinary', models=[model], _ordinary=True)
    private = Capture(tmp_path, index, 'private')

    def runner():
        with _without_ordinary_observers():
            raise ValueError('real outer failure')

    app.runner = runner
    ambient = sys.gettrace()
    with ExitStack() as stack:
        for observer in ((private, ordinary) if order == 'private-first' else (ordinary, private)):
            stack.enter_context(observer)
        owned = sys.gettrace()
        with pytest.raises(ValueError, match='real outer failure'):
            app.outer()
        assert sys.gettrace() is owned
    assert sys.gettrace() is ambient
    for observer in (ordinary, private):
        events = [e for e in observer.events if e.anchor == 'OUTER']
        assert [e.phase for e in events] == ['call', 'raise'], events
        assert type(events[-1].error) is ValueError and str(events[-1].error) == 'real outer failure'
        assert observer.issues == [] and observer._frames == {}


def test_probe_preparation_is_not_ordinary_but_the_actual_root_case_is(tmp_path):
    from tests.intent_engine.test_scenario_execution import scenario
    from tests.test_anchor_self_rules import test_project_anchor_case as native_case
    import flowguard
    root = __import__('pathlib').Path(flowguard.__file__).resolve().parents[1]
    index = anchors.collect_sources(root, [
        ('flowguard/structure/paths.py', 'flowguard.structure.paths'),
        ('tests/test_anchor_self_rules.py', 'tests.test_anchor_self_rules', True)])
    model = Flow('ROOT', 'assumed: actual root readings',
                 (Node('source', 'PROJECT_SOURCE', phase='return', start=True, end=True),), ())
    binding = scenario(tmp_path)
    with calibration._execution_session(tmp_path):
        assert calibration._prepare_scenario(tmp_path, binding)['status'] == 'ok'
        ambient = sys.gettrace()
        with Capture(root, index, 'ordinary', models=[model], _ordinary=True) as ordinary:
            actual = calibration._observe_scenario_current(tmp_path, binding, {'x': 4})
            assert ordinary.events == [], ordinary.events
            native_case('source')
        assert sys.gettrace() is ambient
    assert actual.status == 'ok' and actual.value is False, actual
    source = [e for e in ordinary.events if e.anchor == 'PROJECT_SOURCE']
    assert [e.phase for e in source] == ['call', 'return']
    assert source[-1].result is True and ordinary.issues == []
    assert [e.phase for e in ordinary.events if e.anchor == 'PROJECT_CASE'] == ['call', 'return']


def test_ordinary_only_own_body_raise_is_not_a_normal_none_return(tmp_path):
    _, index, _, app, model = project(tmp_path,
        "with boundary():\n    raise ValueError('own body failure')")
    app.boundary = _without_ordinary_observers
    ambient = sys.gettrace()
    with Capture(tmp_path, index, 'ordinary', models=[model], _ordinary=True) as ordinary:
        owned = sys.gettrace()
        with pytest.raises(ValueError, match='own body failure'):
            app.outer()
        assert sys.gettrace() is owned
    assert sys.gettrace() is ambient
    assert [e.phase for e in ordinary.events] == ['call', 'raise'], ordinary.events
    assert type(ordinary.events[-1].error) is ValueError
    assert str(ordinary.events[-1].error) == 'own body failure'
    assert ordinary.issues == [] and ordinary._frames == {}


def test_audit_rejecting_pause_does_not_leave_ordinary_capture_silently_disabled(tmp_path):
    import subprocess
    import flowguard
    root = __import__('pathlib').Path(flowguard.__file__).resolve().parents[1]
    script = '''
import sys, tempfile
from pathlib import Path
sys.path.insert(0, SDK)
from tests.intent_engine.test_probe_observer_boundary import project
from flowguard.intent.flow import Capture, _without_ordinary_observers
with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    _, index, _, app, model = project(root)
    with Capture(root, index, 'ordinary', models=[model], _ordinary=True) as ordinary:
        owned = sys.gettrace()
        block = [True]
        def deny(event, args):
            if event == 'sys.settrace' and block[0]:
                block[0] = False
                raise RuntimeError('audit refuses pause')
        sys.addaudithook(deny)
        try:
            with _without_ordinary_observers():
                raise AssertionError('audit denial should prevent entry')
        except RuntimeError as error:
            assert str(error) == 'audit refuses pause'
        assert sys.gettrace() is owned and not ordinary._scope.paused
        assert app.limit(2) is True
    assert [event.phase for event in ordinary.events] == ['call', 'return']
    assert ordinary.issues == []
'''.replace('SDK', repr(str(root)))
    result = subprocess.run([sys.executable, '-I', '-c', script], cwd=tmp_path,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
