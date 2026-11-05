"""Actual changed model obligations and immutable owner source, not waiver flags."""
from copy import deepcopy
import pytest

from flowguard.flow import history
from flowguard.flow.checks import check_model
from flowguard.flow.decisions import record_decision
from flowguard.flow.descriptors import finding_terms, input_evidence, model_descriptor
from flowguard.flow.model import load_model
from flowguard.flow.project import conflict_entry
from flowguard.flow.regression import prepare_model_closures
from flowguard.map.common import MapError
from flowguard.map.requests import retire_request, store_request

TEMPLATE = '''
from flowguard.flow import Model, need
m=Model('repair')
m.setting('place','branch',source='R2')
S=m.settings
m.field('state',['broken','ready'],'broken',source='R1')
@m.action(source='R1')
def repair(s):
    need(S['place']=='LOCATION','repair only at main',source='GUARD_SOURCE')
    s['state']='ready'
m.terminal('state',['ready'],source='R1')
m.progress('repair remains possible',lambda s:s['state']=='broken',lambda s:s['state']=='ready',source='R1')
MODEL=m
'''
NEW = 'Repair at branch is allowed; state must become ready.'
ENDING = 'Retire repair at main; state broken is a legitimate end; ready is no longer promised.'


def compute(project, text):
    path=project.flow('repair',text)
    loaded=load_model(path,project.root)
    report=check_model(loaded)
    inputs=input_evidence(project.root,loaded.reads)
    descriptor=model_descriptor(loaded,report,'actual-'+inputs['.flowguard/flow/repair.py']['sha256'],inputs)
    current=dict(receipt=descriptor['receipt'],finished=True,loaded=True,complete=report.graph.complete,
        errors=len(report.graph.errors),scope=descriptor['scope'],obligations=descriptor['obligations'],replay='not_run',
        conflicts=[dict(id=f.id,kind=f.kind,subject=f.subject) for f in report.findings if f.cls=='conflict'])
    return loaded,report,descriptor,current


def setup_change(project,quote=NEW,*,supersedes=('R2',)):
    project.request('R1','Broken state must become ready after repair.')
    project.request('R2','Place is branch; repair is allowed only at main.')
    old=TEMPLATE.replace('LOCATION','main').replace('GUARD_SOURCE','R2')
    loaded,report,_,current=compute(project,old)
    finding=next(f for f in report.findings if f.kind=='STUCK')
    finding.detail['subject_terms']=finding_terms(finding,loaded.model)
    entry=conflict_entry(finding,observation=current)
    store_request(project.root,(quote+'\n').encode(),identifier='R3',supersedes=supersedes)
    event=record_decision(project.root,entry,owner=quote,request='R3')
    entry['history']['decision_refs'].append(event['id'])
    return entry,old,event


def test_actual_replacement_guard_resolves_as_requirement_change_with_executed_regression(project):
    entry,old,event=setup_change(project)
    baseline=deepcopy(entry['history']['baseline'])
    loaded,report,descriptor,current=compute(project,old.replace("=='main'","=='branch'").replace("source='R2')\n    s", "source='R3')\n    s"))
    assert not report.findings
    assert history.assess(entry,current)['outcome']=='retain'
    result=history.assess(entry,current,root=project.root)
    assert result['outcome']=='requirement_changed' and not result['reasons']
    resolution=result['resolution']
    change=next(row for row in resolution['changes'] if row['obligation'].startswith('guard:'))
    assert change['supersedes']==[['R3','R2']]
    assert change['old']['sources']==['R2'] and change['new']['sources']==['R3']
    assert change['authority']['quote']==NEW and change['decision']==event['id']
    assert entry['history']['baseline']==baseline
    assert history.resolution_current(project.root,entry,resolution)==resolution
    from flowguard.flow.cli import conflict_question
    question=conflict_question(project.root,history.compared(entry,current,root=project.root))
    assert 'replacement requirement R3' in question and NEW in question
    closures,limits=prepare_model_closures(project.root,loaded,report,descriptor,[entry])
    assert not limits
    proof=closures[entry['id']]
    assert proof['kind']=='requirement_changed' and proof['regression']['passed']
    assert proof['resolution']==resolution
    source=project.root/proof['regression']['path']
    namespace={'__file__':str(source),'__name__':'__main__'}
    compute(project,old)
    with pytest.raises(AssertionError,match='real dead end'):
        exec(compile(source.read_text(),str(source),'exec'),namespace)


def test_explicit_new_legitimate_end_retires_the_old_operation_and_ready_promise(project):
    entry,old,_=setup_change(project,ENDING,supersedes=('R1','R2'))
    replacement='''
from flowguard.flow import Model
m=Model('repair')
m.setting('place','branch',source='R2')
m.field('state',['broken'],'broken',source='R3')
m.terminal('state',['broken'],source='R3')
MODEL=m
'''
    loaded,report,descriptor,current=compute(project,replacement)
    assert not report.findings
    comparison=history.assess(entry,current,root=project.root)
    assert comparison['outcome']=='requirement_changed'
    resolution=comparison['resolution']
    assert resolution['scope']['before']!=resolution['scope']['after']
    assert any(row['code']=='coverage_removed' for row in resolution['scope']['changes'])
    assert {row['old']['kind'] for row in resolution['changes']} >= {'guard','operation','field','ending'}
    closures,limits=prepare_model_closures(project.root,loaded,report,descriptor,[entry])
    assert not limits and closures[entry['id']]['kind']=='requirement_changed'


@pytest.mark.parametrize('failure',['unrelated_quote','no_supersedes','retired','edited','unchanged_bug','incomplete','old_quote','existing_routes','unbound_new_source'])
def test_owner_event_is_not_a_blanket_waiver(project,failure):
    quote='The repair button becomes blue.' if failure=='unrelated_quote' else NEW
    entry,old,event=setup_change(project,quote,supersedes=() if failure=='no_supersedes' else ('R2',))
    text=old.replace("=='main'","=='branch'").replace("source='R2')\n    s", "source='R3')\n    s")
    if failure=='unchanged_bug':
        text=text.replace("=='branch'","=='main'")
    elif failure=='unbound_new_source':
        text=text.replace("source='R3')\n    s", "source='R2')\n    s")
    _,_,_,current=compute(project,text)
    if failure=='retired':
        retire_request(project.root,'R3')
    elif failure=='edited':
        (project.root/'.flowguard/requests/R3.md').write_text(NEW+' edited')
    elif failure=='incomplete':
        current['complete']=False
    elif failure=='old_quote':
        old_event=record_decision(project.root,entry,owner='repair is allowed only at main.',request='R2')
        entry['history']['decision_refs']=[old_event['id']]
    elif failure=='existing_routes':
        # An event from the other choice purpose cannot authorize new requirements.
        from flowguard.flow import resolution
        original=resolution.read_decision
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(resolution,'read_decision',lambda root,ident:{**original(root,ident),'purpose':'existing_routes'})
            assert history.assess(entry,current,root=project.root)['outcome']=='retain'
        return
    result=history.assess(entry,current,root=project.root)
    assert result['outcome']=='retain' and result['reasons']


def test_finished_source_resolution_revalidates_retirement_without_model_execution(project):
    entry,old,_=setup_change(project)
    _,_,_,current=compute(project,old.replace("=='main'","=='branch'").replace("source='R2')\n    s", "source='R3')\n    s"))
    resolution=history.assess(entry,current,root=project.root)['resolution']
    retire_request(project.root,'R3')
    with pytest.raises(MapError,match='requirement_authority_changed'):
        history.resolution_current(project.root,entry,resolution)


def test_staged_resolution_requires_the_actual_regular_authority_records(project):
    from flowguard.flow.commit_ready import commit_ready
    from flowguard.flow.parts import ENGINE_DIGEST
    entry,old,event=setup_change(project)
    loaded,report,descriptor,current=compute(project,old.replace("=='main'","=='branch'").replace("source='R2')\n    s", "source='R3')\n    s"))
    closures,limits=prepare_model_closures(project.root,loaded,report,descriptor,[entry])
    assert not limits
    project.commit()
    receipt=dict(engine=ENGINE_DIGEST,models={'repair':dict(finished=True,unknown=False,
        inputs=descriptor['inputs'],core={'digest':descriptor['receipt']},observation=current)})
    closed=[dict(entry,closure=closures[entry['id']])]
    def ready():
        return commit_ready(project.root,['repair'],receipt,[],closed=closed)
    assert ready()['ready']
    relative='.flowguard/decisions/'+event['id']+'.json'
    project.git('rm','--cached',relative)
    assert not ready()['ready']
    project.git('add',relative)
    blob=__import__('subprocess').run(['git','-C',str(project.root),'rev-parse',':'+relative],
        capture_output=True,text=True,check=True).stdout.strip()
    project.git('update-index','--cacheinfo','120000,'+blob+','+relative)
    result=ready()
    assert not result['ready'] and any(reason['code']=='requirement_evidence_not_staged' for reason in result['reasons'])


def test_real_check_closes_replaced_requirements_with_the_original_baselines(project):
    from checkrun import run_check
    from flowguard.flow.project import read_conflicts, write_conflicts
    project.request('R1','Broken state must become ready after repair.')
    project.request('R2','Place is branch; repair is allowed only at main.')
    old=TEMPLATE.replace('LOCATION','main').replace('GUARD_SOURCE','R2')
    project.flow('repair',old)
    first=run_check(project.root,'--json')
    assert first.code==1
    data=read_conflicts(project.root)
    assert any(c['kind']=='STUCK' for c in data['conflicts'])
    baselines={c['id']:deepcopy(c['history']['baseline']) for c in data['conflicts']}
    store_request(project.root,(NEW+'\n').encode(),identifier='R3',supersedes=('R2',))
    for entry in data['conflicts']:
        event=record_decision(project.root,entry,owner=NEW,request='R3')
        entry['history']['decision_refs'].append(event['id'])
    write_conflicts(project.root,data)
    project.flow('repair',old.replace("=='main'","=='branch'").replace("source='R2')\n    s", "source='R3')\n    s"))
    after=run_check(project.root,'--json')
    assert after.code==0,after.out+after.err
    saved=read_conflicts(project.root)
    assert not saved['conflicts']
    for entry in saved['closed']:
        assert entry['closure']['kind']=='requirement_changed'
        assert entry['history']['baseline']==baselines[entry['id']]
        assert entry['closure']['regression']['passed']
