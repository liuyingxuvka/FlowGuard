"""Actual pytest fixtures drive one anchor; controlled stops never pass the test."""
from dataclasses import replace
from pathlib import Path
import sys

from flowguard.intent import anchors, calibration, sites
from flowguard.intent.cells import Raised


def project(tmp_path, source, test):
    (tmp_path / 'policy.py').write_text(source)
    (tmp_path / 'test_policy.py').write_text(test)
    (tmp_path / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    return anchors.collect_sources(tmp_path, [('policy.py', 'policy')]).entries[0]


def test_pure_batch_uses_real_code_and_preserves_raised(tmp_path):
    anchor = project(tmp_path, '''# flowguard: sensor limit(x: count) -> allowed: bool
def limit(x: int) -> bool:
    if x < 0: raise ValueError('negative input')
    return x <= 3
''', '')
    previous_module = sys.modules.get('policy')
    results = calibration.execute_many(tmp_path, [(anchor, {'x': 2}), (anchor, {'x': 4}), (anchor, {'x': -1})])
    assert [r.status for r in results] == ['ok', 'ok', 'ok']
    assert [r.value for r in results[:2]] == [True, False]
    assert isinstance(results[2].value, Raised)
    assert type(results[2].value.error) is ValueError and str(results[2].value.error) == 'negative input'
    assert sys.modules.get('policy') is previous_module


def test_driver_keeps_fixture_and_imported_alias_and_finally(tmp_path):
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
    for value, expected in [(2, True), (5, False)]:
        result = calibration.execute(tmp_path, anchor, {'x': value})
        assert result.status == 'ok', result.reasons
        assert result.value is expected
    original = calibration._child(dict(operation='stage', root=str(tmp_path), anchor=__import__('dataclasses').asdict(anchor),
                                       values=calibration._encode({}), stage='zero'))
    assert original['status'] == 'ok' and original['pytest_exit'] != 0


def test_driver_actual_exception_is_raised_not_generic_grey(tmp_path):
    anchor = project(tmp_path, '''from pathlib import Path
class Denied(ValueError): pass
# flowguard: sensor limit(x: count, filename: path) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int, filename: str) -> bool:
    if x < 0: raise Denied('negative input')
    return x <= int(Path(filename).read_text())
''', '''from policy import limit
def test_native(tmp_path):
    path=tmp_path/'limit.txt';path.write_text('3')
    assert limit(2,str(path)) is True
''')
    result = calibration.execute(tmp_path, anchor, {'x': -1})
    assert result.status == 'ok', result.reasons
    assert isinstance(result.value, Raised)
    assert type(result.value.error).__module__ == 'policy'
    assert type(result.value.error).__qualname__ == 'Denied'
    assert str(result.value.error) == 'negative input'
    from flowguard.intent.api import Refused
    assert Refused(ValueError).matches(result.value.error)
    assert Refused('Denied', contains='negative').matches(result.value.error)


def test_native_probe_does_not_import_unselected_intent(tmp_path):
    anchor = project(tmp_path, '''from pathlib import Path
# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3 and not Path('never-created').exists()
''', '''from policy import limit
def test_native(): assert limit(2) is True
''')
    (tmp_path / 'pyproject.toml').write_text(
        '[tool.pytest.ini_options]\npythonpath=["."]\n'
        'addopts="-p flowguard.intent.plugin"\n')
    intent = tmp_path / 'tests' / 'intent'
    intent.mkdir(parents=True)
    marker = tmp_path / 'unselected-intent-was-imported'
    (intent / 'unselected.py').write_text(
        'from pathlib import Path\n'
        f'Path({str(marker)!r}).write_text("unselected")\n'
        'raise AssertionError("a native probe must not load unselected intent")\n')
    result = calibration.execute(tmp_path, anchor, {'x': 5})
    assert result.status == 'ok', result.reasons
    assert result.value is False
    assert not marker.exists()
    assert not (tmp_path / '.flowguard' / 'map.sqlite').exists()


def test_ambiguous_calls_and_missing_target_stay_grey(tmp_path):
    anchor = project(tmp_path, '''from pathlib import Path
# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return Path('never-created').exists() or x <= 3
''', '''from policy import limit
def test_native():
    assert limit(1)
    assert limit(2)
''')
    result = calibration.execute(tmp_path, anchor, {'x': 5})
    assert result.status == 'grey' and 'exactly once' in ' '.join(result.reasons)
    (tmp_path/'test_policy.py').write_text('def test_native(): assert True\n')
    result = calibration.execute(tmp_path, anchor, {'x': 5})
    assert result.status == 'grey'


def test_unstable_external_state_cannot_calibrate(tmp_path):
    anchor = project(tmp_path, '''import time
# flowguard: sensor stamp(x: count) -> result: float calibrated_by=test_policy.py::test_native
def stamp(x: int) -> float:
    return time.time() + x
''', '''from policy import stamp
def test_native(): assert stamp(0) > 0
''')
    result = calibration.execute(tmp_path, anchor, {'x': 1})
    assert result.status == 'grey' and 'zero-replacement' in ' '.join(result.reasons)


def test_baseline_assert_and_teardown_failures_are_not_hidden(tmp_path):
    anchor = project(tmp_path, '''from pathlib import Path
# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return Path('never-created').exists() or x <= 3
''', '''from policy import limit
def test_native(): assert limit(2) is False
''')
    result = calibration.execute(tmp_path, anchor, {'x': 5})
    assert result.status == 'red' and 'original' in ' '.join(result.reasons)


def test_constructor_none_closure_and_async_are_not_judgments(tmp_path):
    anchor = project(tmp_path, '''class Service:
    # flowguard: sensor init(x: count) -> result: None calibrated_by=test_policy.py::test_native
    def __init__(self, x: int) -> None:
        self.x=x
''', '''from policy import Service
def test_native(): assert Service(2).x == 2
''')
    result = calibration.execute(tmp_path, anchor, {'x': 5})
    assert result.status == 'grey' and 'constructor' in ' '.join(result.reasons)


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


def test_old_project_named_flowguard_uses_its_own_source(tmp_path):
    package = tmp_path/'flowguard'
    package.mkdir()
    (package/'__init__.py').write_text("VERSION='old target'\n")
    (package/'decision.py').write_text('''# flowguard: sensor limit(x: count) -> allowed: bool
def limit(x: int) -> bool:
    return x <= 2
''')
    (tmp_path/'pyproject.toml').write_text('')
    anchor = anchors.collect_sources(tmp_path, [('flowguard/decision.py', 'flowguard.decision')]).entries[0]
    actual = calibration.execute_many(tmp_path, [(anchor, {'x': 2}), (anchor, {'x': 3})])
    assert [r.status for r in actual] == ['ok', 'ok'], [r.reasons for r in actual]
    assert [r.value for r in actual] == [True, False]
    assert sys.modules['flowguard'].__file__ != str(package/'__init__.py')


def test_stale_source_and_actual_teardown_fail_stay_red(tmp_path):
    anchor = project(tmp_path, '''from pathlib import Path
# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3 and not Path('never-created').exists()
''', '''import pytest
from policy import limit
@pytest.fixture(autouse=True)
def cleanup():
    yield
    assert False, 'real cleanup failure'
def test_native(): assert limit(2)
''')
    result = calibration.execute(tmp_path, anchor, {'x': 5})
    assert result.status == 'red' and 'original' in ' '.join(result.reasons)
    (tmp_path/'policy.py').write_text((tmp_path/'policy.py').read_text().replace('x <= 3', 'x <= 4'))
    result = calibration.execute(tmp_path, anchor, {'x': 5})
    assert result.status == 'red' and 'source changed' in ' '.join(result.reasons)


def test_existing_code_instrumentation_is_never_replaced_by_fresh_source(tmp_path, monkeypatch):
    anchor = project(tmp_path, '''from pathlib import Path
# flowguard: sensor limit(x: count, filename: path) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int, filename: str) -> bool:
    return x <= int(Path(filename).read_text())
''', '''from policy import limit
def test_native(tmp_path):
    path=tmp_path/'limit.txt';path.write_text('3')
    assert limit(2,str(path)) is True
''')
    import os, subprocess, textwrap
    sdk = str(Path(calibration.__file__).resolve().parents[2])
    code = """
from pathlib import Path
import importlib
from flowguard.intent import anchors, calibration, sites
from flowguard.intent.config import load_config, setup_path
from flowguard.intent.imports import prepare
root=Path.cwd()
anchor=anchors.collect_sources(root,[('policy.py','policy')]).entries[0]
setup_path(load_config(root));prepare(root)
module=importlib.import_module('policy')
with anchors._execution_session(root), calibration._execution_session(root):
    fact=calibration._prepare(root,anchor)
    assert fact['status']=='ok',fact
    with sites.intercepted(module.limit,lambda original,bound:False):
        result=anchors.observe(root,anchor,{'x':2})
        assert result.status=='ok',result.reasons
        assert result.value is False,'installed code was replaced by fresh source'
with anchors._execution_session(root), calibration._execution_session(root):
    def refuse(request):raise AssertionError('fresh fallback')
    calibration._child=refuse
    with sites.intercepted(module.limit,lambda original,bound:False):
        result=anchors.observe(root,anchor,{'x':2})
        assert result.status=='grey' and 'prepared' in ' '.join(result.reasons)
"""
    env=os.environ.copy()
    env['PYTHONPATH']=os.pathsep.join([sdk,str(tmp_path),env.get('PYTHONPATH','')])
    result=subprocess.run([sys.executable,'-B','-c',textwrap.dedent(code)],cwd=tmp_path,env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr


def test_outcome_equality_keeps_existing_numbers_and_remote_error_identity():
    assert calibration.outcome_equal(1, 1.0)
    assert not calibration.outcome_equal(True, 1)
    original = Raised(KeyError('missing'))
    remote = calibration._decode(calibration._encode(original))
    assert str(remote.error) == str(original.error)
    assert calibration.outcome_equal(original, remote)


def test_private_probe_is_real_registered_driver_and_not_a_skip_switch(tmp_path):
    anchor = project(tmp_path, '''from pathlib import Path
# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3 or Path('never-created').exists()
''', '''from flowguard.intent.calibration import probe_context
from policy import limit
def test_native(request):
    assert probe_context(request.config)
    assert limit(2)
''')
    result = calibration.execute(tmp_path, anchor, {'x': 5})
    assert result.status == 'ok' and result.value is False, result.reasons
    from types import SimpleNamespace
    assert calibration.probe_context(SimpleNamespace(_flowguard_calibration_probe=True)) is False


def test_skipped_original_test_is_never_a_calibration_pass(tmp_path):
    anchor = project(tmp_path, '''from pathlib import Path
# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3 or Path('never-created').exists()
''', '''import pytest
from policy import limit
def test_native():
    value=limit(2)
    pytest.skip('not a passing baseline')
''')
    result = calibration.execute(tmp_path, anchor, {'x': 5})
    assert result.status == 'red' and 'original' in ' '.join(result.reasons)


def test_driver_cannot_hide_source_parameter_or_output_type_mismatch(tmp_path):
    anchor = project(tmp_path, '''from pathlib import Path
# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return 'wrong' if x == 5 else not Path('never-created').exists()
''', '''from policy import limit
def test_native(): assert limit(2) is True
''')
    wrong_input = calibration.execute(tmp_path, anchor, {'x': 'not-int'})
    assert wrong_input.status == 'red' and 'parameter type' in ' '.join(wrong_input.reasons)
    wrong_output = calibration.execute(tmp_path, anchor, {'x': 5})
    assert wrong_output.status == 'red' and wrong_output.value == 'wrong'


def test_driver_reads_current_source_with_same_mtime_and_length(tmp_path):
    anchor = project(tmp_path, '''from pathlib import Path
# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3 and not Path('never-created').exists()
''', '''from policy import limit
def test_native(): assert limit(2) is True
''')
    assert calibration.execute(tmp_path, anchor, {'x': 4}).value is False
    import os, py_compile
    source=tmp_path/'policy.py'
    py_compile.compile(str(source), doraise=True, invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
    stat=source.stat()
    source.write_text(source.read_text().replace('x <= 3', 'x <= 4'))
    os.utime(source, ns=(stat.st_atime_ns,stat.st_mtime_ns))
    assert source.stat().st_size == stat.st_size
    fresh=anchors.collect_sources(tmp_path,[('policy.py','policy')]).entries[0]
    actual=calibration.execute(tmp_path,fresh,{'x':4})
    assert actual.status=='ok' and actual.value is True, actual.reasons


def test_old_flowguard_src_package_keeps_its_own_namespace(tmp_path):
    folder=tmp_path/'src/flowguard';folder.mkdir(parents=True)
    (folder/'__init__.py').write_text('')
    (folder/'policy.py').write_text('''# flowguard: sensor old_limit(x: count) -> allowed: bool
def old_limit(x: int) -> bool:
    return x <= 3
''')
    (tmp_path/'pyproject.toml').write_text('[tool.flowguard]\nroots=["src"]\n')
    anchor=anchors.collect_sources(tmp_path,[('src/flowguard/policy.py','flowguard.policy')]).entries[0]
    actual=calibration.execute(tmp_path,anchor,{'x':4})
    assert actual.status=='ok' and actual.value is False,actual.reasons


def test_distinct_native_sdk_dependency_is_not_replaced_by_the_tool(tmp_path):
    import json,os,subprocess
    root=tmp_path/'app';root.mkdir()
    fake=tmp_path/'native-sdk';(fake/'flowguard').mkdir(parents=True)
    (fake/'flowguard/__init__.py').write_text('NATIVE_ID="native-old"\n')
    anchor=project(root,'''# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3
''','''import flowguard
from policy import limit
def test_native():
    assert flowguard.NATIVE_ID == "native-old"
    assert limit(2) is True
''')
    sdk=Path(calibration.__file__).resolve().parents[1]
    script='''import importlib.util,json,sys
from pathlib import Path
sdk=Path(sys.argv[1])
spec=importlib.util.spec_from_file_location('_tool',sdk/'__init__.py',submodule_search_locations=[str(sdk)])
pkg=importlib.util.module_from_spec(spec);sys.modules[spec.name]=pkg;spec.loader.exec_module(pkg)
from _tool.intent import calibration
anchor=calibration._anchor(json.loads(sys.argv[2]))
actual=calibration.execute(Path.cwd(),anchor,{'x':4})
assert actual.status=='ok' and actual.value is False,actual.reasons
'''
    from dataclasses import asdict
    env=os.environ.copy();env['PYTHONPATH']=str(fake)
    process=subprocess.run([sys.executable,'-B','-c',script,str(sdk),json.dumps(asdict(anchor))],cwd=root,env=env,capture_output=True,text=True)
    assert process.returncode==0,process.stdout+process.stderr
