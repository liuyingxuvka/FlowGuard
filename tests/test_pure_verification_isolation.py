"""Pure verifier readings are private; real calls and dependency evidence survive."""
import importlib
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

from flowguard.intent import anchors
from flowguard.intent.config import load_config, setup_path, project_code
from flowguard.intent.flow import Capture, Flow, Node, runtime_check
from flowguard.intent.imports import prepare
from flowguard.intent.tracer import Footprint


def make_case(root):
    module = 'pure_boundary_' + uuid.uuid4().hex
    (root / 'pyproject.toml').write_text('[tool.flowguard]\n')
    (root / (module + '.py')).write_text(
        '# flowguard: sensor FLAG(flag: bool) -> answer: bool\n'
        'def accept(flag: bool) -> bool:\n    return flag\n')
    index = anchors.collect_sources(root, [(module + '.py', module)])
    assert not index.issues, index.issues
    anchor = next(a for a in index.entries if a.name == 'FLAG')
    cfg = load_config(root)
    setup_path(cfg)
    prepare(root)
    return cfg, index, anchor, importlib.import_module(module)


def flag_events(capture):
    return [(e.phase, e.values['flag'], e.occurrence)
            for e in capture.events if e.anchor == 'FLAG']


@pytest.mark.parametrize('entry', ['observe', '_observe_current'])
def test_pure_verifier_cannot_supply_ordinary_coverage_or_advance_occurrences(tmp_path, entry):
    _, index, anchor, app = make_case(tmp_path)
    model = Flow('ONE', 'assumed: actual source observation',
                 (Node('reading', 'FLAG', phase='return', start=True, end=True),), ())
    ambient = sys.gettrace()
    with anchors._execution_session(tmp_path):
        with Capture(tmp_path, index, 'probe-only', models=[model], _ordinary=True) as empty:
            with Capture(tmp_path, index, 'private') as private:
                owned = sys.gettrace()
                with Footprint(project_code(load_config(tmp_path))) as footprint:
                    result = getattr(anchors, entry)(tmp_path, anchor, {'flag': True})
                assert result.status == 'ok' and result.value is True
                assert sys.gettrace() is owned
            assert flag_events(private) == [('call', True, 1), ('return', True, 1)]
            assert any(qual == 'accept' for _, _, qual in footprint.entered)
            assert private.issues == []
        assert empty.events == [], empty.events
        assert runtime_check(model, empty, index)['verdict'] == 'grey'
        with Capture(tmp_path, index, 'real-calls', models=[model], _ordinary=True) as ordinary:
            assert app.accept(False) is False
            result = getattr(anchors, entry)(tmp_path, anchor, {'flag': True})
            assert result.status == 'ok' and result.value is True
            assert app.accept(True) is True
    assert sys.gettrace() is ambient
    assert flag_events(ordinary) == [
        ('call', False, 1), ('return', False, 1),
        ('call', True, 2), ('return', True, 2)]
    assert empty.issues == ordinary.issues == []


def test_c_profiler_keeps_footprint_and_private_pure_boundary(tmp_path):
    # A fresh real interpreter isolates the existing profiler from pytest's own
    # observer. Python 3.11 exercises the SDK's trace fallback naturally.
    sdk = Path(__file__).resolve().parents[1]
    script = '''import cProfile,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from tests.test_pure_verification_isolation import make_case,flag_events
from flowguard.intent import anchors,tracer
from flowguard.intent.config import project_code
from flowguard.intent.flow import Capture
from flowguard.intent.tracer import Footprint
root=Path(sys.argv[2])
cfg,index,anchor,app=make_case(root)
ambient=sys.gettrace()
with anchors._execution_session(root),Capture(root,index,'ordinary',_ordinary=True) as ordinary:
    assert app.accept(False) is False
    profiler=cProfile.Profile();profiler.enable();original=sys.getprofile()
    try:
        with Footprint(project_code(cfg)) as footprint:
            head=sys.gettrace()
            if not hasattr(sys,'monitoring'):
                from flowguard.intent.runtime import _HUB
                assert head is _HUB.trace
            observed=anchors._observe_current(root,anchor,{'flag':True})
            assert observed.status=='ok' and observed.value is True
            assert sys.gettrace() is head
        assert sys.getprofile() is original
    finally:
        profiler.disable()
    assert app.accept(True) is True
assert sys.gettrace() is ambient
assert flag_events(ordinary)==[('call',False,1),('return',False,1),('call',True,2),('return',True,2)],flag_events(ordinary)
assert any(qual=='accept' for _,_,qual in footprint.entered)
assert ordinary.issues==[]
print('real profiler preserved; pure verifier remained private')
'''
    result = subprocess.run([sys.executable, '-I', '-c', script, str(sdk), str(tmp_path)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'real profiler preserved; pure verifier remained private' in result.stdout
