"""Replacement owner contracts require actual new native behavior and regression."""
import runpy

import pytest

from test_requirement_resolution import TEMPLATE, NEW, ENDING, compute
from flowguard.flow.decisions import record_decision
from flowguard.flow.descriptors import finding_terms
from flowguard.flow.native_evidence import evaluate_report
from flowguard.flow.project import conflict_entry
from flowguard.map.requests import store_request

APP='''class Refusal(Exception): pass
class Program:
    def __init__(self): self.state='broken'
    def repair(self):
        if 'branch'!='main': raise Refusal('only main')
        self.state='ready'
'''
BIND='''m.bind_adapter({'system':'app:Program','classes':['app:Program'],'refusal':['app:Refusal']},
    state=lambda snapshot:{'state':fields(snapshot,names=('state',))['state']},operations=OPERATIONS)
'''


def bound(text,operations):
    return (text.replace("Model('repair')","Model('repair',covers=['app.py:Program'])")
            .replace('from flowguard.flow import Model', 'from flowguard.flow.adapter import fields\nfrom flowguard.flow import Model')
            .replace('MODEL=m',BIND.replace('OPERATIONS',repr(operations))+'MODEL=m'))


def original(project,*,ending=False):
    project.request('R1','Broken state must become ready after repair.')
    project.request('R2','Place is branch; repair is allowed only at main.')
    project.file('app.py',APP)
    text=bound(TEMPLATE.replace('LOCATION','main').replace('GUARD_SOURCE','R2'),{'repair':'repair'})
    loaded,report,_,observation=compute(project,text)
    finding=next(f for f in report.findings if f.kind=='STUCK')
    finding.detail['subject_terms']=finding_terms(finding,loaded.model)
    entry=conflict_entry(finding,observation=observation)
    before=evaluate_report(project.root,report)
    assert before['status']=='conformant',before['limits']
    entry['native_confirmation']=before['confirmed'][entry['id']]
    quote=ENDING if ending else NEW
    store_request(project.root,(quote+'\n').encode(),identifier='R3',supersedes=('R1','R2') if ending else ('R2',))
    event=record_decision(project.root,entry,owner=quote,request='R3')
    entry['history']['decision_refs'].append(event['id'])
    return entry,text


def test_new_guard_contract_observes_real_permit_and_emits_failing_if_reverted_regression(project):
    entry,text=original(project)
    project.file('app.py',APP.replace("'branch'!='main'","'branch'!='branch'"))
    _,report,_,observation=compute(project,text.replace("=='main'","=='branch'").replace("source='R2')\n    s", "source='R3')\n    s"))
    evidence=evaluate_report(project.root,report,[entry],observation=observation)
    assert evidence['status']=='conformant',evidence['limits']
    proof=evidence['closures'][entry['id']]
    assert proof['kind']=='requirement_changed' and proof['regression']['passed']
    assert proof['resolution']['changes'][0]['authority']['id']=='R3'
    assert any(check['native']['steps'] and check['native']['steps'][-1]['outcome']=='success'
               for check in evidence['checks'].values())
    regression=project.root/proof['regression']['path']
    project.file('app.py',APP)
    with pytest.raises(AssertionError,match='native regression'):
        runpy.run_path(str(regression),run_name='__main__')


def test_explicit_legitimate_end_checks_native_construction_even_with_no_operations(project):
    entry,_=original(project,ending=True)
    ended_app=APP.partition('    def repair')[0]
    project.file('app.py',ended_app)
    text=bound('''from flowguard.flow import Model
m=Model('repair')
m.setting('place','branch',source='R2')
m.field('state',['broken'],'broken',source='R3')
m.terminal('state',['broken'],source='R3')
MODEL=m
''',{})
    _,report,_,observation=compute(project,text)
    evidence=evaluate_report(project.root,report,[entry],observation=observation)
    assert evidence['status']=='conformant',evidence['limits']
    proof=evidence['closures'][entry['id']]
    assert proof['kind']=='requirement_changed' and proof['scope_preserved'] is False
    assert proof['checks'] and not report.graph.calls
    assert all(evidence['checks'][key]['native']['rule_captures']['native_evidence']['status']=='current' for key in proof['checks'])
    project.file('app.py',ended_app.replace("self.state='broken'","self.state='ready'"))
    with pytest.raises(AssertionError,match='native regression'):
        runpy.run_path(str(project.root/proof['regression']['path']),run_name='__main__')


@pytest.mark.parametrize('production',['old_behavior','unavailable'])
def test_model_and_owner_change_without_real_new_native_behavior_cannot_close(project,production):
    entry,text=original(project)
    if production=='unavailable':
        project.file('app.py',APP.replace("self.state='broken'", "self.state='broken'; import socket; socket.socket()"))
    _,report,_,observation=compute(project,text.replace("=='main'","=='branch'").replace("source='R2')\n    s", "source='R3')\n    s"))
    evidence=evaluate_report(project.root,report,[entry],observation=observation)
    assert evidence['status'] in {'drift','unknown'}
    assert not evidence['closures']


@pytest.mark.parametrize('decide_after_model_check',[False,True])
def test_real_native_check_resolves_then_reuses_canonical_cached_receipt(project,decide_after_model_check):
    from checkrun import run_check
    from flowguard.flow.project import read_conflicts,write_conflicts
    from flowguard.flow.commit_ready import commit_ready
    from flowguard.map.requests import retire_request
    project.request('R1','Broken state must become ready after repair.')
    project.request('R2','Place is branch; repair is allowed only at main.')
    project.file('app.py',APP)
    text=bound(TEMPLATE.replace('LOCATION','main').replace('GUARD_SOURCE','R2'),{'repair':'repair'})
    project.flow('repair',text)
    assert run_check(project.root,'--json').code==1
    data=read_conflicts(project.root)
    store_request(project.root,(NEW+'\n').encode(),identifier='R3',supersedes=('R2',))
    project.file('app.py',APP.replace("'branch'!='main'","'branch'!='branch'"))
    project.flow('repair',text.replace("=='main'","=='branch'").replace("source='R2')\n    s", "source='R3')\n    s"))
    if decide_after_model_check:
        assert run_check(project.root,'--json').code==1
        data=read_conflicts(project.root)
    for entry in data['conflicts']:
        event=record_decision(project.root,entry,owner=NEW,request='R3')
        entry['history']['decision_refs'].append(event['id'])
    write_conflicts(project.root,data)
    after=run_check(project.root,'--json')
    assert after.code==0,after.out+after.err
    summary=after.data['closed'][0]['requirement_change']
    assert summary['new']==[['R3',NEW]] and summary['code_fixed'] is False
    assert summary['old']==[['R2','Place is branch; repair is allowed only at main.']]
    assert all(row['closure']['kind']=='requirement_changed' for row in read_conflicts(project.root)['closed'])
    assert run_check(project.root,'--json').code==0
    cached=run_check(project.root,'--json')
    assert cached.code==0 and all(part['cached'] for part in cached.data['parts']),cached.out
    project.commit()
    data=read_conflicts(project.root)
    from flowguard.flow.cli import status_lines
    status='\n'.join(status_lines(project.root))
    assert 'REQUIREMENT CHANGED repair' in status and 'old R2:' in status and 'new R3:' in status
    ready=commit_ready(project.root,['repair'],data,[],closed=data['closed'])
    assert ready['ready'],ready
    retire_request(project.root,'R3')
    from flowguard.flow.codeaudit import reopen_declared
    reopened=reopen_declared(project.root,data)
    assert not reopened['closed'] and reopened['conflicts']
    assert all('requirement_authority_changed' in row['decision_reopened'] for row in reopened['conflicts'])
    assert all(row['history']['baseline'] == next(old['history']['baseline'] for old in data['closed'] if old['id']==row['id'])
               for row in reopened['conflicts'])
