"""Only reached source selectors expose actual shallow return contract facts."""
import pytest
from flowguard.native import session

SOURCE='''class Meta(type):
    def __eq__(self,other): raise AssertionError('observer called custom type equality')
class Custom(metaclass=Meta): pass
def report(depth):
    if depth:
        return report(depth-1)
    marker=True
    return {'status':'failed','exit_code':2,'custom':Custom(),
            'body':'private request body','nested':{'hidden':'private nested body'}}
class Program:
    def run(self):
        report(1)
        report(0)
        return 1
'''


def spec(tmp_path,source=SOURCE):
    (tmp_path/'program.py').write_text(source)
    return dict(root=str(tmp_path),system='program:Program',classes=['program:Program'],statements=[
        dict(id='status',path='program.py',function='report',line=7,unambiguous=True,return_fields=['status','custom','missing']),
        dict(id='code',path='program.py',function='report',line=8,unambiguous=True,return_fields=['exit_code'])])


def selected_events(result):
    return [event for step in result['steps'] for event in step['events'] if 'return_fields' in event]


def test_selected_return_fields_belong_to_the_reached_recursive_invocation(tmp_path):
    result=session.replay(spec(tmp_path),[dict(name='run')])
    assert result['steps'][0]['outcome']=='success'
    events=selected_events(result)
    assert len(events)==2 and len({event['call_token'] for event in events})==2
    assert all(event['return_status']=='returned' and event['result']['status']=='unknown' for event in events)
    assert all(event['return_fields']['status']=={'status':'current','value':'failed'} for event in events)
    assert all(event['return_fields']['exit_code']=={'status':'current','value':2} for event in events)
    assert all(event['return_fields']['custom']['status']=='unknown' and event['return_fields']['missing']['status']=='unknown' for event in events)
    assert all(event['return_fields']['custom']['reason'] != event['return_fields']['missing']['reason'] for event in events)
    outer=[event for event in result['steps'][0]['events'] if event['kind']=='return' and event['function']=='report' and 'return_fields' not in event]
    assert len(outer)==1 and events[0]['parent_call_token']==outer[0]['call_token']
    assert 'body' not in repr(events) and 'nested' not in repr(events)


def test_selected_dict_lookup_does_not_call_custom_key_equality(tmp_path):
    source='''class Key:
    def __hash__(self): return hash('status')
    def __eq__(self,other): raise AssertionError('observer called custom key equality')
def report(depth):
    marker=True
    return {Key():3,'exit_code':2}
class Program:
    def run(self):
        report(0)
        return 1
'''
    selected=spec(tmp_path,source)
    selected['statements'][0]['line']=5;selected['statements'][1]['line']=6
    result=session.replay(selected,[dict(name='run')])
    assert result['steps'][0]['outcome']=='success'
    [event]=selected_events(result)
    assert event['return_fields']['status']['status']=='unknown'
    assert event['return_fields']['exit_code']['value']==2


def test_raised_selected_invocation_cannot_publish_returned_fields(tmp_path):
    source=SOURCE.replace("return {'status':'failed','exit_code':2,'custom':Custom(),\n            'body':'private request body','nested':{'hidden':'private nested body'}}","raise LookupError('actual SUT failure')")
    result=session.replay(spec(tmp_path,source),[dict(name='run')])
    assert result['steps'][0]['outcome']=='crash'
    assert result['steps'][0]['exception']['type']=='builtins:LookupError'
    events=selected_events(result)
    assert events and all(event['return_status']=='raised' for event in events)
    assert all(fact['status']=='unknown' for event in events for fact in event['return_fields'].values())


def test_observer_only_pytest_uses_the_same_selected_return_contract(tmp_path):
    selected=spec(tmp_path);selected.pop('system');selected['classes']=[]
    (tmp_path/'test_program.py').write_text("from program import report\ndef test_failed_report():\n    result=report(1)\n    assert result['status']=='failed' and result['exit_code']==2\n")
    result=session.replay(selected,[],operation='record',options={'test_nodeids':['test_program.py::test_failed_report']})
    [row]=result['recordings'];assert row['pytest_outcome']=='passed'
    events=[event for event in row['observer_events'] if 'return_fields' in event]
    assert len(events)==1 and events[0]['return_fields']['status']['value']=='failed'


def test_unambiguous_unreached_selection_cannot_borrow_another_invocation(tmp_path):
    selected=spec(tmp_path)
    for row in selected['statements']:
        row['unambiguous']=False
    result=session.replay(selected,[dict(name='run')])
    assert result['steps'][0]['outcome']=='success' and selected_events(result)==[]


def test_return_field_observation_fault_reaches_the_caller(tmp_path,monkeypatch):
    original=session.run_isolated_process
    def controlled(command,**kwargs):
        command=list(command)
        marker='_worker(sys.argv[1],fd)'
        fault="""def failed_observation(self,value):
    raise LookupError('injected return observation fault')
_worker.__globals__['_ObservedState'].return_scalar=failed_observation
"""
        assert command[2].count(marker)==1
        command[2]=command[2].replace(marker,'\n'+fault+'\n'+marker)
        return original(command,**kwargs)
    monkeypatch.setattr(session,'run_isolated_process',controlled)
    with pytest.raises(session.NativeEngineError,match='injected return observation fault'):
        session.replay(spec(tmp_path),[dict(name='run')])
