"""Only explicitly selected names expose strict built-in truth/type facts."""
import pytest
from flowguard.native import session


SOURCE='''SECRET = 'must not be recorded'
def choose(relevant, fallback):
    return relevant or fallback
class Program:
    def run(self):
        choose([], [])
        choose([1], ['alternate'])
        choose(None, ())
        choose(0, b'')
        choose({}, set())
        choose(False, '')
        choose(0.0, 0j)
        return 1
'''


def spec(tmp_path,source=SOURCE, function='choose', line=3):
    (tmp_path/'program.py').write_text(source)
    return {'root':str(tmp_path),'system':'program:Program','classes':['program:Program'],
            'statements':[{'id':'selected-or','path':'program.py','function':function,'line':line,
                           'unambiguous':True,'truth_names':['relevant','fallback']}]}


def facts(result):
    return [event for step in result['steps'] for event in step['events'] if 'name_truth' in event]


def test_selected_builtin_truth_facts_are_per_call_and_do_not_dump_values(tmp_path):
    result=session.replay(spec(tmp_path),[{'name':'run'}])
    events=facts(result)
    assert len(events)==7 and len({e['call_token'] for e in events})==7
    assert all(e['function']=='choose' and e['line']==3 and e['kind']=='statement' for e in events)
    assert events[0]['name_truth']['relevant']=={'status':'current','type':'builtins:list','truth':False}
    assert events[1]['name_truth']['relevant']['truth'] is True
    assert events[2]['name_truth']['relevant']['type']=='builtins:NoneType'
    assert events[2]['name_truth']['fallback']['type']=='builtins:tuple'
    assert events[3]['name_truth']['fallback']=={'status':'current','type':'builtins:bytes','truth':False}
    assert events[4]['name_truth']['relevant']['type']=='builtins:dict'
    assert events[4]['name_truth']['fallback']['type']=='builtins:set'
    assert events[5]['name_truth']['relevant']['type']=='builtins:bool'
    assert events[5]['name_truth']['fallback']['type']=='builtins:str'
    assert events[6]['name_truth']['relevant']['type']=='builtins:float'
    assert events[6]['name_truth']['fallback']['type']=='builtins:complex'
    assert 'SECRET' not in repr(events) and 'must not be recorded' not in repr(events)
    assert 'alternate' not in repr(events)


def test_custom_truth_is_unknown_without_an_extra_bool_call(tmp_path):
    source='''class Custom:
    def __bool__(self): raise LookupError('actual SUT bool')
def choose(relevant,fallback):
    return relevant or fallback
class Program:
    def run(self): return choose(Custom(), [])
'''
    result=session.replay(spec(tmp_path,source,line=4),[{'name':'run'}])
    assert result['steps'][0]['outcome']=='crash'
    assert result['steps'][0]['exception']['message']=='actual SUT bool'
    [event]=facts(result)
    assert event['name_truth']['relevant']['status']=='unknown'
    assert event['name_truth']['fallback']['truth'] is False
    bool_errors=[e for e in result['steps'][0]['events'] if e['function']=='Custom.__bool__' and e['kind']=='exception']
    assert len(bool_errors)==1


def test_unbound_local_does_not_borrow_a_same_named_global(tmp_path):
    source='''relevant = [1]
fallback = []
def choose():
    value = relevant or fallback
    relevant = []
    return value
class Program:
    def run(self): return choose()
'''
    result=session.replay(spec(tmp_path,source,line=4),[{'name':'run'}])
    assert result['steps'][0]['exception']['type']=='builtins:UnboundLocalError'
    [event]=facts(result)
    assert event['name_truth']['relevant']['status']=='unknown'
    assert event['name_truth']['fallback']['truth'] is False


def test_observer_only_pytest_uses_the_same_selected_truth_events(tmp_path):
    selected=spec(tmp_path)
    selected.pop('system');selected['classes']=[]
    (tmp_path/'tests').mkdir()
    (tmp_path/'tests/test_program.py').write_text("from program import choose\ndef test_chosen():\n    assert choose([], [])==[]\n    assert choose([1],[])==[1]\n")
    result=session.replay(selected,[],operation='record',options={'test_nodeids':['tests/test_program.py::test_chosen']})
    [row]=result['recordings']
    assert row['pytest_outcome']=='passed'
    events=[e for e in row['observer_events'] if 'name_truth' in e]
    assert len(events)==2
    assert [e['name_truth']['relevant']['truth'] for e in events]==[False,True]


def test_custom_metaclass_equality_is_not_an_observation_operation(tmp_path):
    source='''class Meta(type):
    def __eq__(self, other): raise AssertionError('custom type equality was called')
class Custom(metaclass=Meta):
    def __bool__(self): raise LookupError('actual SUT bool')
def choose(relevant,fallback):
    return relevant or fallback
class Program:
    def run(self): return choose(Custom(), [])
'''
    result=session.replay(spec(tmp_path,source,line=6),[{'name':'run'}])
    assert result['steps'][0]['exception']['message']=='actual SUT bool'
    assert facts(result)[0]['name_truth']['relevant']['status']=='unknown'
