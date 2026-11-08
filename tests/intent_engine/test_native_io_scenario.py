"""Effectful code is observed through a real test with fresh fixtures, not replayed as a sensor."""
import importlib
from pathlib import Path
import uuid

import pytest

from flowguard.intent.loader import load
from flowguard.intent.runtime import Runtime
from tests.intent_engine._source_fixture import source_sessions, source_engine


@pytest.mark.parametrize('seed,run_target,expected', [(3,True,'ok'),(1,True,'red'),(3,False,'grey')])
def test_native_io_finally_and_fresh_fixtures_keep_real_positive_and_negative_results(tmp_path,seed,run_target,expected):
    module = 'native_io_' + uuid.uuid4().hex
    log = tmp_path / 'fixture-paths.txt'
    (tmp_path/'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    (tmp_path/'tests/intent').mkdir(parents=True)
    (tmp_path/(module+'.py')).write_text('''from pathlib import Path
# flowguard: sensor LIMIT(x: count, filename: path) -> allowed: bool
def limit(x: int, filename: str) -> bool:
    try:
        return x <= int(Path(filename).read_text())
    finally:
        Path(filename + '.closed').write_text('finished')
''')
    (tmp_path/'test_native_io.py').write_text(f'''from pathlib import Path
import pytest
from {module} import limit as saved_alias
@pytest.fixture
def x(): return 2
@pytest.fixture
def run_target(): return {run_target!r}
@pytest.fixture
def filename(tmp_path,run_target):
    path=tmp_path/'limit.txt'
    path.write_text({str(seed)!r})
    with Path({str(log)!r}).open('a') as stream:
        stream.write(str(path)+'\\n')
    yield str(path)
    if run_target:
        assert Path(str(path)+'.closed').read_text()=='finished'
# flowguard: event CASE(x: int; filename, run_target) calibrated_by=test_native_io.py::test_native
def test_native(x: int,filename: str,run_target: bool):
    if run_target:
        answer=saved_alias(x,filename)
        assert type(answer) is bool
''')
    (tmp_path/'tests/intent/policy.py').write_text('''from flowguard.intent import rule,row,flow,Node,Read,Relation
@rule('LIMIT',decides='seeded limit',fields={'x':int},source='assumed: the fixture threshold is three')
def LIMIT(x): return x <= 3
LIMIT.rows(row(x=2,expect=True,why='below the declared limit'),row(x=5,expect=False,why='above the declared limit'))
flow('IO',source='assumed: actual native IO observation',nodes=[Node('case','CASE',start=True),Node('answer','LIMIT',phase='return',caller='case',end=True)],edges=[('case','answer')],relations=[Relation('LIMIT',{'x':Read('case','arg.x')},Read('answer'),on='answer')])
''')
    model = load(root=tmp_path)
    assert not model.errors, model.errors
    engine = source_engine(model)
    model.deep = False  # Exercise the ordinary rows contract; no decision probes.
    rule=model.rules['LIMIT']
    assert len(rule.homes)==1 and hasattr(rule.homes[0],'scenario')
    target=importlib.import_module(module).limit
    alias,code=target,target.__code__
    before=log.read_text().splitlines() if log.exists() else []
    calls=[]
    with Runtime(tmp_path).record(predicate=lambda current: current is code,
                                  callback=lambda frame,event,arg:calls.append(frame.f_locals['x']),private=True,entry_only=True):
        result=engine.run_home(rule,rule.homes[0],'rows')
    assert result['verdict']==expected,result
    assert target is alias and target.__code__ is code
    after=log.read_text().splitlines()
    if run_target:
        assert calls==[2,5]
        paths=after[len(before):]
        assert len(paths)==2 and len(set(paths))==2
        assert all(Path(path+'.closed').read_text()=='finished' for path in paths)
        if expected=='red':
            assert any('disagree' in message for message in result['red'])
    else:
        assert calls==[] and not result['entered']
        assert result['grey'] and not result['red']
