"""The nested test harness keeps real pytest fixtures fresh without another Session."""
import sys
from pathlib import Path
import uuid

from flowguard.intent.loader import load
from tests.intent_engine._source_fixture import source_engine, source_sessions


def test_same_session_harness_does_not_borrow_the_outer_tmp_path(tmp_path):
    root=tmp_path/'native-project'
    (root/'tests/intent').mkdir(parents=True)
    module='fresh_native_'+uuid.uuid4().hex
    (root/(module+'.py')).write_text('''# flowguard: sensor LIMIT(x: count) -> allowed: bool calibrated_by=tests/test_native.py::test_case
def limit(x: int) -> bool:
    return x <= 3
''')
    (root/'tests/test_native.py').write_text('from pathlib import Path\nfrom '+module+' import limit\nSEEN=[]\n'+
        '# flowguard: event CASE(x: count, tmp_path: path)\n'+
        'def test_case(x: int=2, *, tmp_path: Path):\n'+
        '    SEEN.append(tmp_path)\n'+
        f'    assert tmp_path != Path({str(tmp_path)!r}), "borrowed the outer fixture"\n'+
        '    assert limit(x) is True\n')
    (root/'tests/conftest.py').write_text('''import pytest
@pytest.fixture(autouse=True)
def actual_conftest(tmp_path):
    marker=tmp_path/'actual-conftest'
    marker.write_text('real fixture')
    yield
    assert marker.read_text()=='real fixture'
''')
    (root/'tests/intent/policy.py').write_text('''from flowguard.intent import rule,row
@rule('LIMIT',decides='limit',fields={'x':int},anchor='LIMIT',source='assumed: independent third-day boundary')
def LIMIT(x): return x <= 3
LIMIT.rows(row(x=4,expect=False,why='fourth day is refused'))
''')
    model=load(root=root)
    assert not model.errors,model.errors
    engine=source_engine(model)
    rule=model.rules['LIMIT']
    result=engine.run_home(rule,rule.homes[0],'cells')
    assert result['verdict']=='ok',result
    native=next(value for value in sys.modules.values()
                if getattr(value,'__file__',None)==str(root/'tests/test_native.py'))
    assert len(native.SEEN)>=3
    assert len(set(native.SEEN))==len(native.SEEN)
    assert tmp_path not in native.SEEN
