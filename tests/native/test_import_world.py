"""Only bounded dependency initialization may temporarily change child environment."""
import hashlib
import json
import os
from pathlib import Path

import pytest

from flowguard.native import session
from flowguard.native.inputs import footprint_evidence

KEY = 'FLOWGUARD_IMPORT_CONTROL'


def world(tmp_path, dependency, operation='return 3'):
    root = tmp_path / 'subject'
    root.mkdir()
    library = tmp_path / 'dependency'
    library.mkdir()
    (library / 'guard_dependency.py').write_text(dependency)
    (root / 'program.py').write_text(f'''import sys
sys.path.insert(0, {str(library)!r})
import guard_dependency
class Program:
    def __init__(self): self.value = 0
    def run(self):
        {operation}
''')
    return {'root': str(root), 'system': 'program:Program', 'classes': ['program:Program']}


def test_foreign_import_temporary_environment_is_keyed_and_secret_free(tmp_path, monkeypatch):
    secret = 'private-control-value'
    monkeypatch.setenv(KEY, secret)
    spec = world(tmp_path, f'''import os
original = os.environ[{KEY!r}]
os.putenv({KEY!r}, 'temporary')
os.putenv({KEY!r}, original)
''')
    result = session.replay(spec, [{'name': 'run'}])
    footprint = result['footprint']
    assert result['steps'][0]['outcome'] == 'success'
    assert footprint['environment'][KEY] == {'sha256': hashlib.sha256(secret.encode()).hexdigest()}
    assert secret not in json.dumps(footprint)
    events = footprint['environment_events']
    assert [event['event'] for event in events] == ['os.putenv', 'os.putenv']
    assert all(event['phase'] == 'import' and event['module'] == 'guard_dependency' for event in events)
    assert os.environ[KEY] == secret
    assert footprint_evidence(footprint).status == 'current'
    monkeypatch.setenv(KEY, 'changed-control-value')
    assert footprint_evidence(footprint).status == 'stale'


@pytest.mark.parametrize('initial', [None, ''])
def test_absence_and_empty_import_inputs_are_distinct(tmp_path, monkeypatch, initial):
    monkeypatch.delenv(KEY, raising=False)
    if initial is not None:
        monkeypatch.setenv(KEY, initial)
    spec = world(tmp_path, f'''import os
original = os.environ.get({KEY!r})
os.putenv({KEY!r}, 'temporary')
if original is None: os.unsetenv({KEY!r})
else: os.putenv({KEY!r}, original)
''')
    result = session.replay(spec, [])
    stamp = result['footprint']['environment'][KEY]
    assert stamp == ({'missing': True} if initial is None else {'sha256': hashlib.sha256(b'').hexdigest()})
    assert footprint_evidence(result['footprint']).status == 'current'
    monkeypatch.setenv(KEY, 'changed')
    assert footprint_evidence(result['footprint']).status == 'stale'


def test_read_without_mutation_and_worker_owned_home_have_honest_provenance(tmp_path, monkeypatch):
    monkeypatch.setenv(KEY, 'original')
    spec = world(tmp_path, f'''import os
observed = os.environ.get({KEY!r})
owned = [os.environ.get(key) for key in ('HOME', 'TMPDIR', 'TEMP', 'TMP', 'PYTHONPATH', 'PYTHONDONTWRITEBYTECODE', 'PYTHONHASHSEED')]
''')
    footprint = session.replay(spec, [])['footprint']
    assert footprint['environment_events'] == []
    assert footprint['environment']['HOME'] == {'owned': 'native-arena-home'}
    monkeypatch.setenv('HOME', '/different-parent-home')
    assert footprint_evidence(footprint).status == 'current'
    monkeypatch.setenv(KEY, 'changed')
    assert footprint_evidence(footprint).status == 'stale'


@pytest.mark.parametrize('operation', [
    "__import__('os').putenv('FLOWGUARD_RUNTIME_CONTROL', 'value')",
    "__import__('os').unsetenv('FLOWGUARD_RUNTIME_CONTROL')",
    "__import__('os').environ.__setitem__('FLOWGUARD_RUNTIME_CONTROL', 'value')",
    "guard_dependency.mutate()",
])
def test_runtime_environment_writes_remain_explicit_unknown(tmp_path, operation):
    spec = world(tmp_path, "import os\ndef mutate(): os.putenv('FLOWGUARD_RUNTIME_CONTROL', 'value')\n", operation)
    with pytest.raises(session.UnsupportedWorld, match=r'os\.(putenv|unsetenv).*phase=execution'):
        session.replay(spec, [{'name': 'run'}])


def test_caught_runtime_environment_violation_cannot_publish_success(tmp_path):
    spec = world(tmp_path, '', "try: __import__('os').putenv('FLOWGUARD_RUNTIME_CONTROL', 'value')\n        except Exception: return 3")
    with pytest.raises(session.UnsupportedWorld, match='os.putenv'):
        session.replay(spec, [{'name': 'run'}])


def test_persistent_import_environment_is_outside_the_supported_world(tmp_path):
    spec = world(tmp_path, "import os\nos.putenv('FLOWGUARD_IMPORT_PERSISTENT', 'value')\n")
    with pytest.raises(session.UnsupportedWorld, match='not restored.*phase=import'):
        session.replay(spec, [])


@pytest.mark.parametrize('body,reason', [
    ("__import__('subprocess').run(['true'])", 'subprocess.Popen'),
    ("__import__('socket').socket().connect(('127.0.0.1', 9))", 'socket.connect'),
    ("open('/tmp/flowguard-outside-import-control', 'w')", 'write outside'),
])
def test_import_environment_permission_keeps_other_arena_guards(tmp_path, body, reason):
    spec = world(tmp_path, body)
    with pytest.raises(session.UnsupportedWorld, match=reason):
        session.replay(spec, [])


def test_source_import_is_not_a_dependency_environment_permit(tmp_path):
    spec = world(tmp_path, '')
    path = Path(spec['root']) / 'program.py'
    path.write_text("import os\nos.putenv('FLOWGUARD_SOURCE_IMPORT_CONTROL', 'value')\n" + path.read_text())
    with pytest.raises(session.UnsupportedWorld, match='os.putenv.*phase=import.*source='):
        session.replay(spec, [])


def test_persistent_owned_environment_change_is_not_hidden_by_owned_stamp(tmp_path):
    spec = world(tmp_path, "import os\nos.environ['HOME'] = '/changed-child-home'\n")
    with pytest.raises(session.UnsupportedWorld, match='not restored.*phase=import'):
        session.replay(spec, [])


def test_cached_dependency_import_survives_real_session_reconstruction(tmp_path, monkeypatch):
    spec = world(tmp_path, f"import os\nos.putenv({KEY!r}, 'temporary')\nos.unsetenv({KEY!r})\n")
    monkeypatch.delenv(KEY, raising=False)
    original = session.run_isolated_process
    def repeated(command, **kwargs):
        command = list(command)
        command[2] = '''from flowguard.native import session as native
reset = native._Session.reset
def repeated_reset(self, *args, **kwargs):
    before = reset(self, *args, **kwargs)
    after = reset(self, *args, **kwargs)
    assert before == after
    return after
native._Session.reset = repeated_reset
''' + command[2]
        return original(command, **kwargs)
    monkeypatch.setattr(session, 'run_isolated_process', repeated)
    result = session.replay(spec, [{'name': 'run'}])
    assert result['steps'][0]['outcome'] == 'success'
    assert len(result['footprint']['environment_events']) == 2


def test_environment_observer_bug_is_an_engine_error_even_when_caught(tmp_path, monkeypatch):
    spec = world(tmp_path, '', "try: __import__('os').putenv('FLOWGUARD_RUNTIME_CONTROL', 'value')\n        except Exception: return 3")
    original = session.run_isolated_process
    def controlled(command, **kwargs):
        command = list(command)
        command[2] = '''from flowguard.native import session as native
def broken(self, event, args, caller): raise RuntimeError('injected environment capture bug')
native._Inputs.environment_mutation = broken
''' + command[2]
        return original(command, **kwargs)
    monkeypatch.setattr(session, 'run_isolated_process', controlled)
    with pytest.raises(session.NativeEngineError, match='injected environment capture bug'):
        session.replay(spec, [{'name': 'run'}])


@pytest.mark.parametrize('fault,refusal', [('UnsupportedWorld', 'ValueError'), ('NativeEngineError', 'RuntimeError')])
def test_constructor_observation_errors_are_not_declared_sut_refusals(tmp_path, monkeypatch, fault, refusal):
    spec = world(tmp_path, '')
    spec['refusal'] = ['builtins:' + refusal]
    original = session.run_isolated_process
    def controlled(command, **kwargs):
        command = list(command)
        command[2] = f'''from flowguard.native import session as native
capture = native._ObservedState.capture
def unavailable(self, frame):
    if frame.f_code.co_name == '__init__': raise native.{fault}('constructor observation unavailable')
    return capture(self, frame)
native._ObservedState.capture = unavailable
''' + command[2]
        return original(command, **kwargs)
    monkeypatch.setattr(session, 'run_isolated_process', controlled)
    with pytest.raises(getattr(session, fault), match='constructor observation unavailable') as observed:
        session.replay(spec, [])
    assert 'declared construction refusal' not in str(observed.value)


def test_import_must_restore_python_mapping_as_well_as_native_environment(tmp_path, monkeypatch):
    monkeypatch.delenv(KEY, raising=False)
    spec = world(tmp_path, f"import os\nos.putenv({KEY!r}, 'native')\nos.environ[{KEY!r}] = 'mapping'\nos.unsetenv({KEY!r})\n")
    with pytest.raises(session.UnsupportedWorld, match='not restored'):
        session.replay(spec, [])


def test_foreign_import_cannot_license_an_intervening_subject_callback(tmp_path):
    spec = world(tmp_path, 'import program\nprogram.change()\n')
    path = Path(spec['root']) / 'program.py'
    path.write_text("import os\ndef change():\n    os.putenv('FLOWGUARD_SUBJECT_CALLBACK', 'value')\n    os.unsetenv('FLOWGUARD_SUBJECT_CALLBACK')\n" + path.read_text())
    with pytest.raises(session.UnsupportedWorld, match='os.putenv.*phase=import'):
        session.replay(spec, [])


def test_invalid_environment_key_remains_an_actual_sut_exception(tmp_path):
    spec = world(tmp_path, '', "return __import__('os').environ.get(5)")
    result = session.replay(spec, [{'name': 'run'}])
    assert result['steps'][0]['outcome'] == 'crash'
    assert result['steps'][0]['exception']['type'] == 'builtins:TypeError'
