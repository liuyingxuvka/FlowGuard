"""Ordinary pytest source-relative inputs are resolved from the recorded project root."""
from pathlib import Path
import pytest
from flowguard.native import session


@pytest.mark.parametrize('nodeids',[None,['tests/test_relative.py::test_example']])
def test_recorded_pytest_runs_from_its_project_root(tmp_path,nodeids):
    (tmp_path/'examples').mkdir()
    example=tmp_path/'examples/input.txt'
    example.write_text('actual relative input')
    (tmp_path/'tests').mkdir()
    (tmp_path/'tests/test_relative.py').write_text("from pathlib import Path\ndef test_example():\n    assert Path('examples/input.txt').read_text()=='actual relative input'\n")
    before=Path.cwd()
    result=session.replay({'root':str(tmp_path),'classes':[]},[],operation='record',
                          options={'test_nodeids':nodeids} if nodeids else {})
    assert result['pytest_exitcode']==0
    [row]=result['recordings']
    assert row['pytest_outcome']=='passed'
    assert str(example) in result['footprint']['files']
    assert Path.cwd()==before
