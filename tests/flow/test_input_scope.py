"""Real native starts distinguish call inputs from expected constructor outputs."""
from pathlib import Path
import base64

import pytest

from flowguard.flow.adapter import check_trace, fields, trace_calls
from flowguard.flow.checks import CONFLICT, check_model
from flowguard.flow.descriptors import input_evidence, model_descriptor
from flowguard.flow.history import assess
from flowguard.flow.model import load_model
from flowguard.flow.project import conflict_entry

TEMPLATE = '''from flowguard.flow import Model
from flowguard.flow.adapter import fields
m=Model('initial', covers=['app.py:Program'])
m.field('n',(0,1),INITIAL)
m.terminal('n',(0,1))
m.always('starts ready',lambda s:s['n']==1,source='R1')
RESTORE
m.bind_adapter({'system':'app:Program','classes':['app:Program']},
               state=lambda snapshot:{'n':fields(snapshot,names=('n',))['n']},operations=OPERATIONS,output=lambda row:None,
               start=START,prefix=PREFIX)
MODEL=m
'''
APP = '''class Program:
    def __init__(self):
        self.n=INITIAL
    @classmethod
    def load(cls,path):
        import json
        result=cls()
        with open(path) as source:
            result.n=json.load(source)['n']
        return result
'''


def actual(project, *, initial, start=None, prefix=(), restore=False):
    restore_action = "@m.action()\ndef restore(s):\n    s['n']=0\n" if restore else ''
    operations = {'restore':{'name':'load','args':[{'$file':'old.json'}],'replace':True}} if restore else {}
    text=TEMPLATE.replace('INITIAL',str(initial)).replace('START',repr(start or {})).replace('PREFIX',repr(prefix))
    path=project.flow('initial',text.replace('RESTORE',restore_action).replace('OPERATIONS',repr(operations)))
    loaded=load_model(path,project.root)
    report=check_model(loaded)
    observed=check_trace(report.graph,trace_calls(report.graph,()))
    assert observed.status=='conformant', observed.reason
    reads=set(loaded.reads)
    for name in observed.native['footprint']['files']:
        absolute=Path(name)
        if absolute.is_relative_to(project.root) and absolute.is_file():
            reads.add(absolute.relative_to(project.root).as_posix())
    descriptor=model_descriptor(loaded,report,'observed-model',input_evidence(project.root,reads))
    observation=dict(receipt=descriptor['receipt'],finished=True,loaded=True,complete=report.graph.complete,
                     errors=len(report.graph.errors),scope=descriptor['scope'],obligations=descriptor['obligations'],replay='not_run')
    return report,observed,observation


def test_native_constructor_output_fix_retains_same_actual_input_scope(project):
    project.request('R1','The initial state starts ready.\n')
    project.file('app.py',APP.partition('    @classmethod')[0].replace('INITIAL','0'))
    before,native_before,observation=actual(project,initial=0)
    failure=next(f for f in before.findings if f.cls==CONFLICT and f.kind=='BROKEN')
    original=conflict_entry(failure,observation=observation)
    assert fields(native_before.native['initial'],names=('n',))=={'n':0}
    project.file('app.py',APP.partition('    @classmethod')[0].replace('INITIAL','1'))
    after,native_after,current=actual(project,initial=1)
    assert fields(native_after.native['initial'],names=('n',))=={'n':1}
    assert not any(f.id==failure.id for f in after.findings)
    assert current['scope']['starts']==observation['scope']['starts']
    assert assess(original,current)['outcome']=='model_absent'


@pytest.mark.parametrize('change',['omit','replace'])
def test_omitted_or_changed_actual_old_save_prefix_is_not_the_same_start(project,change):
    project.request('R1','The initial state starts ready.\n')
    project.file('app.py',APP.replace('INITIAL','0'))
    start={'files':{'old.json':base64.b64encode(b'{"n":0}').decode(),
                    'other.json':base64.b64encode(b'{"n":0}').decode()}}
    prefix=({'name':'load','args':[{'$file':'old.json'}],'replace':True},)
    before,native_before,observation=actual(project,initial=0,start=start,prefix=prefix,restore=True)
    original=conflict_entry(next(f for f in before.findings if f.kind=='BROKEN'),observation=observation)
    changed=() if change=='omit' else ({'name':'load','args':[{'$file':'other.json'}],'replace':True},)
    _,native_after,current=actual(project,initial=0,start=start,prefix=changed,restore=True)
    # Native output is equal; it does not license dropping a distinct saved input.
    assert fields(native_before.native['final'],names=('n',))==fields(native_after.native['final'],names=('n',))
    result=assess(original,current)
    assert result['outcome']=='retain'
    assert 'start_removed' in {row['code'] for row in result['reasons']}
