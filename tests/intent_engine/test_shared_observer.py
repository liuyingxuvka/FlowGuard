"""Shared observers retain dynamic entries and failure/ownership boundaries."""
import importlib
from pathlib import Path
import subprocess
import sys
import uuid


from flowguard.intent.flow import Capture
from flowguard.intent.runtime import Runtime, _HUB, _PRIVATE
from flowguard.intent.tracer import Footprint
from tests.test_pure_verification_isolation import make_case


def test_footprint_discovers_module_imported_after_scope_entry(tmp_path, monkeypatch):
    name = 'late_observer_' + uuid.uuid4().hex
    source = tmp_path / (name + '.py')
    source.write_text('def late(): return 7\n')
    monkeypatch.syspath_prepend(str(tmp_path))
    with Footprint(lambda filename: filename == str(source)) as footprint:
        try:
            assert importlib.import_module(name).late() == 7
        finally:
            sys.modules.pop(name, None)
    assert (str(source), 1, 'late') in footprint.entered


def test_nested_capture_and_footprint_share_one_observer(tmp_path):
    cfg, index, _, app = make_case(tmp_path)
    ambient = sys.gettrace()
    ambient_records, ambient_tool = tuple(_HUB.records), _HUB.tool
    with Capture(tmp_path, index, 'outer') as outer:
        owner = _HUB.tool if hasattr(sys, 'monitoring') else sys.gettrace()
        with Footprint(lambda filename: filename == app.__file__) as footprint:
            with Capture(tmp_path, index, 'inner') as inner:
                assert (_HUB.tool if hasattr(sys, 'monitoring') else sys.gettrace()) is owner
                assert app.accept(True) is True
    assert sys.gettrace() is ambient
    assert len(_HUB.records) == len(ambient_records)
    assert all(actual is expected for actual, expected in zip(_HUB.records, ambient_records))
    assert _HUB.tool is ambient_tool
    assert [(e.phase, e.result) for e in outer.events] == [('call', None), ('return', True)]
    assert [(e.phase, e.result) for e in inner.events] == [('call', None), ('return', True)]
    assert any(key[2] == 'accept' for key in footprint.entered)
    assert not outer.issues and not inner.issues


def test_private_runtime_keeps_open_real_frame_completion(tmp_path):
    token = None
    def begin():
        nonlocal token
        token = _PRIVATE.set(True)
        return 7
    runtime = Runtime(tmp_path)
    try:
        with runtime.record({begin.__code__: 'BEGIN'}) as events:
            assert begin() == 7
            assert events is runtime.events
            assert [(e['phase'], e['value']) for e in runtime.events] == [('call', None), ('return', 7)]
    finally:
        if token is not None:
            _PRIVATE.reset(token)
    assert [(e['phase'], e['value']) for e in runtime.events] == [('call', None), ('return', 7)]


def test_rejected_shared_observer_is_unknown_and_can_recover(tmp_path):
    sdk = Path(__file__).resolve().parents[2]
    script = '''import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from tests.test_pure_verification_isolation import make_case
from flowguard.intent.flow import Capture
from flowguard.intent.runtime import _HUB
_,index,_,app=make_case(Path(sys.argv[2]))
block=[True]
def deny(event,args):
    forbidden='sys.monitoring.register_callback' if hasattr(sys,'monitoring') else 'sys.settrace'
    if event==forbidden and block[0]:
        block[0]=False
        raise RuntimeError('audit refuses recorder')
sys.addaudithook(deny)
with Capture(Path(sys.argv[2]),index,'rejected') as rejected:
    assert app.accept(True) is True
assert not rejected.events and any('audit refuses recorder' in issue for issue in rejected.issues)
assert not _HUB.records and _HUB.tool is None
with Capture(Path(sys.argv[2]),index,'recovered') as recovered:
    assert app.accept(False) is False
assert [(e.phase,e.result) for e in recovered.events]==[('call',None),('return',False)]
assert not recovered.issues
'''
    result = subprocess.run([sys.executable, '-I', '-c', script, str(sdk), str(tmp_path)],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_dynamic_monitor_does_not_keep_finished_code_objects(tmp_path):
    import gc
    import weakref
    source = str(tmp_path / 'transient_observer.py')
    runtime = Runtime(tmp_path)
    refs, calls = [], []
    def record(frame, event, arg):
        calls.append((frame.f_code.co_name, event))
        return record
    with runtime.record(predicate=lambda code: code.co_filename == source, callback=record, private=True):
        for value in range(8):
            namespace = {}
            exec(compile(f'def entry(): return {value}\n', source, 'exec'), namespace)
            refs.append(weakref.ref(namespace['entry'].__code__))
            assert namespace['entry']() == value
            del namespace
            gc.collect()
        assert all(ref() is None for ref in refs)
    assert calls == [(name, phase) for _ in range(8)
                     for name in ('<module>', 'entry') for phase in ('call', 'return')]
    assert not runtime.issues
