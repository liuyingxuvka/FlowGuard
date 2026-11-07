"""Explicit live failure output keeps pytest's real outcomes and private probes."""
import json
from types import SimpleNamespace

import pytest

from flowguard.intent import diagnostics, plugin
from tests.intent_engine.test_plugin import run


def test_diagnose_reports_final_failures_before_continuing_and_keeps_probes_private(tmp_path):
    (tmp_path/'tests/intent').mkdir(parents=True)
    (tmp_path/'pyproject.toml').write_text('[tool.pytest.ini_options]\ntestpaths=["tests"]\n')
    (tmp_path/'conftest.py').write_text('''import pytest
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item,call):
    outcome=yield
    report=outcome.get_result()
    if item.name=='test_2_real_followup'and report.when=='call'and report.passed:
        terminal=item.config.get_terminal_writer()
        terminal.line('REAL_FOLLOWUP_TEST_418')
        terminal.flush()
''')
    (tmp_path/'tests/intent/broken.py').write_text("""from flowguard.intent import rule,row
@rule('BAD',decides='bad',fields={'flag':bool},source='assumed: deliberate failure control')
def BAD(flag): return flag
BAD.rows(row(flag=True,expect=False,why='deliberate wrong row'))
""")
    (tmp_path/'tests/test_results.py').write_text('''import pytest
from flowguard.intent import calibration
from tests.intent_engine.test_controlled_stop_reporting import native_project


def test_1_actual_failure():
    raise AssertionError('ACTUAL_FAILURE_BODY_418')


def test_2_real_followup():
    assert 2+2==4


def test_3_private_probes(tmp_path,monkeypatch):
    root=tmp_path/'native'
    root.mkdir()
    anchor=native_project(root)
    (root/'pyproject.toml').write_text('[tool.pytest.ini_options]\\npythonpath=["."]\\naddopts="-p flowguard.intent.plugin --flowguard-diagnose"\\n')
    real_main=pytest.main
    captured=[]
    class Recorder:
        def pytest_sessionfinish(self,session):
            assert calibration.probe_context(session.config)
            assert session.config.getoption('--flowguard-diagnose')
            captured.append(session.config.get_terminal_writer()._file.getvalue())
    def recorded(args,plugins):
        return real_main(args,plugins=[*plugins,Recorder()])
    monkeypatch.setattr(pytest,'main',recorded)
    results=[calibration._stage(root,anchor,values,stage)
             for stage,values in [('baseline',{}),('zero',{}),('case',{'x':5})]]
    assert [r['status']for r in results]==['ok','ok','ok'],results
    assert [r['pytest_exit']for r in results]==[0,1,1],results
    assert len(captured)==3
    assert all('FlowGuard failure:'not in text for text in captured)


@pytest.mark.xfail(reason='valid expected failure control',strict=True)
def test_4_valid_xfail():
    raise AssertionError('EXPECTED_XFAIL_418')


def test_5_unguarded_skip():
    pytest.skip('UNGUARDED_SKIP_418')
''')
    outputs=[]
    for extra in [(),('--flowguard-diagnose',)]:
        completed=run(tmp_path,*extra)
        mode='on'if extra else'off'
        (tmp_path/('captured-'+mode+'.stdout.txt')).write_text(completed.stdout)
        (tmp_path/('captured-'+mode+'.stderr.txt')).write_text(completed.stderr)
        assert completed.returncode==1,completed.stdout+completed.stderr
        assert '3 failed, 2 passed, 1 xfailed'in completed.stdout,completed.stdout
        assert '_Stop'not in completed.stdout,completed.stdout
        outputs.append(completed.stdout)
    off,on=outputs
    assert 'FlowGuard failure:'not in off
    prefix='FlowGuard failure: tests/test_results.py::test_1_actual_failure [call]'
    follow='REAL_FOLLOWUP_TEST_418'
    assert on.index(prefix)<on.index('ACTUAL_FAILURE_BODY_418')<on.index(follow),on
    assert off.index(follow)<off.index('ACTUAL_FAILURE_BODY_418'),off
    assert 'FlowGuard failure: tests/intent/broken.py::BAD[rules] [call]'in on,on
    assert 'FlowGuard failure: tests/test_results.py::test_5_unguarded_skip [call]'in on,on
    assert 'FlowGuard failure: tests/test_results.py::test_4_valid_xfail'not in on,on


@pytest.mark.parametrize('failure',['get','write','flush'])
def test_optional_live_terminal_failure_preserves_the_real_report(tmp_path,capsys,failure):
    class Unavailable:
        def write(self,text):
            if failure=='write':raise OSError('terminal write unavailable')
        def flush(self):
            if failure=='flush':raise OSError('terminal flush unavailable')
    def terminal():
        if failure=='get':raise LookupError('terminal unavailable')
        return Unavailable()
    report=pytest.TestReport(nodeid='test_real.py::test_failed',location=('test_real.py',1,'test_failed'),
                             keywords={},outcome='failed',longrepr='original assertion failure',when='call')
    before=dict(report.__dict__)
    state=plugin.Session.__new__(plugin.Session)
    state.config=SimpleNamespace(get_terminal_writer=terminal)
    state.diagnostic_issues=[]
    with diagnostics.EventLog(tmp_path/'diagnostic.jsonl')as log:
        state.diagnostics=log
        state.pytest_runtest_logreport(report)
        assert state.diagnostic_issues
    assert report.__dict__==before
    captured=capsys.readouterr()
    assert not captured.out and not captured.err
    rows=[json.loads(line)for line in (tmp_path/'diagnostic.jsonl').read_text().splitlines()]
    assert rows==[dict(kind='diagnostic-unavailable',output='terminal',error='LookupError'if failure=='get'else'OSError')]
