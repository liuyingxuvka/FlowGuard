"""Changed untyped functions use real primitive inputs; opaque context stays grey."""
import json
import sqlite3

import pytest

from tests.intent_engine._cli_fixture import last
from tests.intent_engine.test_default_runtime_signals import _project, _run, _text, _has_change


def observations(root):
    path=root / '.flowguard/cache/map.sqlite'
    assert path.is_file()
    with sqlite3.connect(path) as connection:
        value=connection.execute("SELECT v FROM meta WHERE k='runtime_observations'").fetchone()
    assert value is not None
    return json.loads(value[0])['items']


def test_untyped_changed_function_reports_automatic_member_changes(tmp_path):
    policy=_project(tmp_path, '''
        def late_fee(days, member):
            return max(0, days - 3) if member else days
    ''', '''
        from policy import late_fee
        def test_native():
            assert late_fee(0, False) == 0
            assert late_fee(5, True) in (2, 3)
    ''')
    policy.write_text(policy.read_text().replace('days - 3','days - 2'))
    result=_run(tmp_path)
    text=_text(result)
    assert result.returncode==0 and '1 passed' in result.stdout,text
    assert 'late_fee' in text and 'member' in text and _has_change(text),text
    assert '    no flowguard comment: compared because its code changed' in last(tmp_path).splitlines(),text
    report=observations(tmp_path)
    assert report['source_changed'] is True
    readings=[item for item in report['items'] if item.get('name')=='late_fee']
    # Only the recorded member call (5, True) differs: 2 before, 3 now.
    assert [item['changed'] for item in readings]==[[[{'days':5,'member':True},2,3]]],report


@pytest.mark.parametrize('operation,protocol', [('bool(ctx)','__bool__'),('ctx[0]','__getitem__')])
def test_untyped_opaque_context_runs_its_protocol_once_and_is_not_compared(tmp_path,operation,protocol):
    method='def __bool__(self):' if protocol=='__bool__' else 'def __getitem__(self,key):'
    policy=_project(tmp_path, 'def use_context(ctx):\n    return '+operation+'\n', '''
        from policy import use_context
        class Context:
            def __init__(self): self.hits=0
            METHOD
                self.hits+=1
                return True
        def test_native():
            ctx=Context()
            assert use_context(ctx) is True
            assert ctx.hits==1
    '''.replace('METHOD',method))
    policy.write_text(policy.read_text().replace('return '+operation,'return '+operation+' or False'))
    result=_run(tmp_path)
    text=_text(result)
    assert result.returncode==0 and '1 passed' in result.stdout,text
    report=observations(tmp_path)
    assert report['source_changed'] is True
    # The context object is not JSON: the call is not compared, has no rows, and its protocol ran once.
    readings=[item for item in report['items'] if 'use_context' in item.get('name','')+' '.join(item.get('reasons',()))]
    assert readings==[dict(changed=0,changes=[],complete=False,name='uncovered',reasons=['use_context: no comparable JSON result'],
                           status='grey',total=0)],text+'\n'+json.dumps(report)
    assert not report['red'],report
    assert 'not compared: use_context (no comparable JSON result) -> not a failure' in text.splitlines(),text
