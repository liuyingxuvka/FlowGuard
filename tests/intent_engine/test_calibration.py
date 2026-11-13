"""Native same-session observations; retired RPC names are not execution paths."""
from dataclasses import replace
import importlib
from pathlib import Path
import sys

from flowguard.intent import anchors, calibration, sites
from flowguard.intent.cells import Raised
from flowguard.intent.runtime import Runtime
from tests.intent_engine._source_fixture import source_sessions
from tests.intent_engine._protocol_controls import bind_anchor

def project(tmp_path, source, test):
    (tmp_path / 'policy.py').write_text(source)
    (tmp_path / 'test_policy.py').write_text(test)
    (tmp_path / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    return anchors.collect_sources(tmp_path, [('policy.py', 'policy')]).entries[0]


def test_pure_batch_preserves_values_and_reuses_one_verified_module(tmp_path):
    anchor = project(tmp_path, '''# flowguard: sensor limit(x: count) -> allowed: bool
def limit(x: int) -> bool:
    if x < 0: raise ValueError('negative input')
    return x <= 3
''', '')
    live_tool = sys.modules['flowguard']
    results = calibration.execute_many(tmp_path, [(anchor, {'x': 2}), (anchor, {'x': 4}), (anchor, {'x': -1})])
    assert [r.status for r in results] == ['ok', 'ok', 'ok']
    assert [r.value for r in results[:2]] == [True, False]
    assert isinstance(results[2].value, Raised)
    assert type(results[2].value.error) is ValueError and str(results[2].value.error) == 'negative input'
    module = sys.modules['policy']
    alias, code = module.limit, module.limit.__code__
    assert Path(module.__file__).resolve() == (tmp_path / 'policy.py').resolve()
    again = calibration.execute(tmp_path, anchor, {'x': 4})
    assert again.status == 'ok' and again.value is False
    assert sys.modules['policy'] is module and module.limit is alias and alias.__code__ is code
    assert sys.modules['flowguard'] is live_tool


def test_side_effect_sensor_uses_only_the_real_fixture_call_and_restores_alias(tmp_path):
    anchor = project(tmp_path, '''from pathlib import Path
# flowguard: sensor limit(x: count, filename: path) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int, filename: str) -> bool:
    try:
        return x <= int(Path(filename).read_text())
    finally:
        Path(filename + '.closed').write_text('finished')
''', '''from pathlib import Path
import pytest
from policy import limit as saved_alias
@pytest.fixture
def filename(tmp_path):
    path = tmp_path / 'limit.txt'
    path.write_text('3')
    yield str(path)
    assert Path(str(path) + '.closed').read_text() == 'finished'
def test_native(filename):
    assert saved_alias(2, filename) is True
''')
    scope, item = bind_anchor(tmp_path, anchor)
    module = importlib.import_module('policy')
    alias, original = module.limit, module.limit.__code__
    # The ordinary run made the one real call, its fixture teardown passed, and the alias is the real function.
    [reading] = scope.runtime.readings
    assert reading.actual[1] is True and not reading.rows
    assert reading.sample is not None and not reading.reasons
    assert scope.runtime.outcomes == {}
    calls = []
    with scope.runtime.record(predicate=lambda code: code is original,
                              callback=lambda frame,event,arg: calls.append(event), private=True, entry_only=True):
        result = calibration.execute(tmp_path, anchor, {'x': 5})
    # Calibration performs no call of its own; explicit sealed qualification refuses this source.
    assert calls == [] and result.status == 'grey' and result.value is None, result
    assert module.limit is alias and module.limit.__code__ is original


def test_unavailable_custom_exception_is_not_masqueraded_as_a_builtin_refusal(tmp_path):
    anchor = project(tmp_path, '''class Denied(ValueError): pass
# flowguard: sensor limit(x: count, threshold: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int, threshold: int) -> bool:
    if x < 0: raise Denied('negative input')
    return x <= threshold
''', '''from policy import limit
def test_native(tmp_path):
    path = tmp_path / 'limit.txt'; path.write_text('3')
    assert limit(2, int(path.read_text())) is True
''')
    bind_anchor(tmp_path, anchor)
    result = calibration.execute(tmp_path, anchor, {'x': -1})
    assert result.status == 'grey' and result.value is None, result
    assert 'Denied' in ' '.join(result.reasons)


def test_native_probe_does_not_import_unselected_intent(tmp_path):
    anchor = project(tmp_path, '''# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3
''', '''from policy import limit
def test_native(): assert limit(2) is True
''')
    (tmp_path / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\naddopts="-p flowguard.intent.plugin"\n')
    intent = tmp_path / 'tests' / 'intent'; intent.mkdir(parents=True)
    marker = tmp_path / 'unselected-intent-was-imported'
    (intent / 'unselected.py').write_text('from pathlib import Path\n' + f'Path({str(marker)!r}).write_text("unselected")\nraise AssertionError("unselected intent")\n')
    bind_anchor(tmp_path, anchor)
    result = calibration.execute(tmp_path, anchor, {'x': 5})
    assert result.status == 'ok' and result.value is False, result.reasons
    assert not marker.exists() and not (tmp_path / '.flowguard' / 'map.sqlite').exists()


def test_ambiguous_calls_and_missing_target_stay_grey(tmp_path):
    anchor = project(tmp_path, '''# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3
''', 'from policy import limit\ndef test_native():\n    assert limit(1)\n    assert limit(2)\n')
    bind_anchor(tmp_path, anchor)
    result = calibration.execute(tmp_path, anchor, {'x': 5})
    assert result.status == 'grey' and 'exactly once' in ' '.join(result.reasons)
    (tmp_path / 'test_policy.py').write_text('def test_native(): assert True\n')
    bind_anchor(tmp_path, anchor)
    result = calibration.execute(tmp_path, anchor, {'x': 5})
    assert result.status == 'grey' and result.value is None


def test_unstable_external_state_cannot_calibrate(tmp_path):
    anchor = project(tmp_path, '''import time
# flowguard: sensor stamp(x: count) -> result: float calibrated_by=test_policy.py::test_native
def stamp(x: int) -> float:
    return time.time() + x
''', 'from policy import stamp\ndef test_native(): assert stamp(0) > 0\n')
    bind_anchor(tmp_path, anchor)
    result = calibration.execute(tmp_path, anchor, {'x': 1})
    assert result.status == 'grey' and result.value is None
    assert 'time' in ' '.join(result.reasons)


def test_a_coarse_clock_still_cannot_calibrate_a_clock_reading_sensor(tmp_path, monkeypatch):
    # A coarse clock does not make time available in the sealed environment.
    import time
    real = time.time
    monkeypatch.setattr(time, 'time', lambda: (real() * 64 // 1) / 64)
    anchor = project(tmp_path, '''import time
# flowguard: sensor stamp(x: count) -> result: float calibrated_by=test_policy.py::test_native
def stamp(x: int) -> float:
    return time.time() + x
''', 'from policy import stamp\ndef test_native(): assert stamp(0) > 0\n')
    bind_anchor(tmp_path, anchor)
    for _ in range(3):
        result = calibration.execute(tmp_path, anchor, {'x': 1})
        assert result.status == 'grey' and result.value is None
        assert 'time' in ' '.join(result.reasons)


def test_baseline_assert_and_teardown_failures_are_not_hidden(tmp_path):
    anchor = project(tmp_path, '''# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3
''', 'from policy import limit\ndef test_native(): assert limit(2) is False\n')
    bind_anchor(tmp_path, anchor)
    result = calibration.execute(tmp_path, anchor, {'x': 5})
    assert result.status == 'red' and 'did not pass' in ' '.join(result.reasons)


def test_constructor_state_write_is_not_a_replayed_sensor(tmp_path):
    anchor = project(tmp_path, '''class Service:
    # flowguard: sensor init(x: count) -> result: None calibrated_by=test_policy.py::test_native
    def __init__(self, x: int) -> None:
        self.x = x
''', 'from policy import Service\ndef test_native(): assert Service(2).x == 2\n')
    bind_anchor(tmp_path, anchor)
    result = calibration.execute(tmp_path, anchor, {'x': 5})
    assert result.status == 'grey' and result.value is None


def test_intercepted_same_function_restores_alias_and_real_final_return():
    from tests.intent_engine import _calibration_helper as helper
    alias = helper.decision
    seen = []
    def callback(original, bound):
        bound.arguments['x'] = 8
        outcome = original(*bound.args, **bound.kwargs)
        seen.append(outcome)
        return outcome
    original = alias.__code__
    with sites.intercepted(helper.decision, callback):
        assert alias is helper.decision and alias(2) == 9
    assert alias.__code__ is original and alias(2) == 3 and seen == [9]


def test_conflicting_project_sdk_namespace_is_rejected_without_replacing_the_live_tool(tmp_path):
    package = tmp_path / 'flowguard'; package.mkdir()
    (package / '__init__.py').write_text("VERSION='old target'\n")
    (package / 'decision.py').write_text('# flowguard: sensor limit(x: count) -> allowed: bool\ndef limit(x: int) -> bool:\n    return x <= 2\n')
    (tmp_path / 'pyproject.toml').write_text('')
    anchor = anchors.collect_sources(tmp_path, [('flowguard/decision.py', 'flowguard.decision')]).entries[0]
    live = sys.modules['flowguard']
    actual = calibration.execute(tmp_path, anchor, {'x': 3})
    assert actual.status in {'red', 'grey'} and actual.value is None
    assert sys.modules['flowguard'] is live and live.__file__ != str(package / '__init__.py')


def test_stale_source_and_actual_teardown_fail_stay_unavailable(tmp_path):
    anchor = project(tmp_path, '''# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3
''', '''import pytest
from policy import limit
@pytest.fixture(autouse=True)
def cleanup():
    yield
    assert False, 'real cleanup failure'
def test_native(): assert limit(2)
''')
    bind_anchor(tmp_path, anchor)
    result = calibration.execute(tmp_path, anchor, {'x': 5})
    assert result.status == 'red' and 'teardown failed' in ' '.join(result.reasons)
    path = tmp_path / 'policy.py'; path.write_text(path.read_text().replace('x <= 3', 'x <= 4'))
    result = calibration.execute(tmp_path, anchor, {'x': 5})
    assert result.status in {'red', 'grey'} and result.value is None
    assert 'source changed' in ' '.join(result.reasons)


def test_existing_code_instrumentation_is_never_replaced_by_fresh_source(tmp_path):
    import ast
    anchor = project(tmp_path, '''# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3
''', 'from policy import limit\ndef test_native(): assert type(limit(2)) is bool\n')
    bind_anchor(tmp_path, anchor)
    module = importlib.import_module('policy')
    def changed(function): function.body = [ast.Return(ast.Constant(False))]
    code = sites._recompile(module.limit, ast.NodeTransformer(), lambda: True, changed)
    original = module.limit.__code__
    with sites.installed(module.limit, code):
        result = calibration.execute(tmp_path, anchor, {'x': 2})
        assert result.status == 'grey' and result.value is None, result
        assert 'instrumentation' in ' '.join(result.reasons)
        assert module.limit.__code__ is code
        assert module.limit(2) is False
    assert module.limit.__code__ is original and module.limit(2) is True


def test_outcome_equality_keeps_numbers_and_native_error_class_identity():
    assert calibration.outcome_equal(1, 1.0)
    assert not calibration.outcome_equal(True, 1)
    original = Raised(KeyError('missing'))
    assert calibration.outcome_equal(original, Raised(KeyError('missing')))
    ForeignKeyError = type('KeyError', (KeyError,), {})
    assert not calibration.outcome_equal(original, Raised(ForeignKeyError('missing')))


def test_private_probe_is_real_current_session_not_a_boolean_skip_switch(tmp_path):
    anchor = project(tmp_path, '''# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3
''', '''from flowguard.intent.calibration import probe_context
from policy import limit
def test_native(request):
    assert probe_context(request.config)
    assert limit(2)
''')
    bind_anchor(tmp_path, anchor)
    result = calibration.execute(tmp_path, anchor, {'x': 5})
    assert result.status == 'ok' and result.value is False, result.reasons
    from types import SimpleNamespace
    assert calibration.probe_context(SimpleNamespace(_flowguard_calibration_probe=True)) is False


def test_skipped_original_test_is_never_a_calibration_pass(tmp_path):
    anchor = project(tmp_path, '''# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3
''', 'import pytest\nfrom policy import limit\ndef test_native():\n    value = limit(2)\n    pytest.skip("not a passing baseline")\n')
    bind_anchor(tmp_path, anchor)
    result = calibration.execute(tmp_path, anchor, {'x': 5})
    assert result.status == 'red' and result.value is None
    assert 'did not pass' in ' '.join(result.reasons)


def test_driver_cannot_hide_source_parameter_or_output_type_mismatch(tmp_path):
    anchor = project(tmp_path, '''# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return 'wrong' if x == 5 else True
''', 'from policy import limit\ndef test_native(): assert limit(2) is True\n')
    bind_anchor(tmp_path, anchor)
    wrong_input = calibration.execute(tmp_path, anchor, {'x': 'not-int'})
    assert wrong_input.status == 'red' and 'parameter type' in ' '.join(wrong_input.reasons)
    wrong_output = calibration.execute(tmp_path, anchor, {'x': 5})
    assert wrong_output.status == 'red' and wrong_output.value == 'wrong'


def test_driver_reads_current_source_with_same_mtime_and_length(tmp_path):
    import os, py_compile
    anchor = project(tmp_path, '''# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3
''', 'from policy import limit\ndef test_native(): assert limit(2) is True\n')
    bind_anchor(tmp_path, anchor)
    assert calibration.execute(tmp_path, anchor, {'x': 4}).value is False
    source = tmp_path / 'policy.py'
    py_compile.compile(str(source), doraise=True, invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
    stat = source.stat(); source.write_text(source.read_text().replace('x <= 3', 'x <= 4'))
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert source.stat().st_size == stat.st_size
    fresh = anchors.collect_sources(tmp_path, [('policy.py','policy')]).entries[0]
    bind_anchor(tmp_path, fresh)
    actual = calibration.execute(tmp_path, fresh, {'x': 4})
    assert actual.status == 'ok' and actual.value is True, actual.reasons


def test_old_flowguard_src_package_cannot_shadow_the_live_sdk(tmp_path):
    folder = tmp_path / 'src' / 'flowguard'; folder.mkdir(parents=True)
    (folder / '__init__.py').write_text('')
    (folder / 'policy.py').write_text('# flowguard: sensor old_limit(x: count) -> allowed: bool\ndef old_limit(x: int) -> bool:\n    return x <= 3\n')
    (tmp_path / 'pyproject.toml').write_text('[tool.flowguard]\nroots=["src"]\n')
    anchor = anchors.collect_sources(tmp_path, [('src/flowguard/policy.py','flowguard.policy')]).entries[0]
    tool = sys.modules['flowguard']
    actual = calibration.execute(tmp_path, anchor, {'x': 4})
    assert actual.status in {'red','grey'} and actual.value is None
    assert sys.modules['flowguard'] is tool


def test_native_dependency_keeps_its_identity_in_the_current_interpreter(tmp_path):
    package = tmp_path / 'domain_sdk'; package.mkdir()
    (package / '__init__.py').write_text('NATIVE_ID="native-old"\n')
    anchor = project(tmp_path, '''# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3
''', '''import domain_sdk
from policy import limit
def test_native():
    assert domain_sdk.NATIVE_ID == "native-old"
    assert limit(2) is True
''')
    bind_anchor(tmp_path, anchor)
    dependency = importlib.import_module('domain_sdk')
    actual = calibration.execute(tmp_path, anchor, {'x': 4})
    assert actual.status == 'ok' and actual.value is False, actual.reasons
    assert sys.modules['domain_sdk'] is dependency and dependency.NATIVE_ID == 'native-old'


def test_calibration_reuses_the_current_sdk_without_bootstrapping_a_second_copy(tmp_path):
    anchor = project(tmp_path, '''# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3
''', 'import flowguard\nfrom policy import limit\ndef test_native(): assert limit(2) is True\n')
    tool = sys.modules['flowguard']; before = set(sys.modules)
    bind_anchor(tmp_path, anchor)
    actual = calibration.execute(tmp_path, anchor, {'x': 5})
    assert actual.status == 'ok' and actual.value is False, actual.reasons
    assert sys.modules['flowguard'] is tool
    assert '_flowguard_execution' not in set(sys.modules) - before
