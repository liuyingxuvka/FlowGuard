"""FG852 uses existing production owners and the one native adapter/recorder."""
from pathlib import Path
import pytest
from flowguard.flow.adapter import check_trace,trace_calls
from flowguard.flow.checks import check_model
from flowguard.flow.model import load_model

ROOT=Path(__file__).resolve().parents[2]


def graph(name):
    report=check_model(load_model(ROOT/'.flowguard/flow'/f'{name}.py',ROOT))
    assert report.graph.complete and not [f for f in report.findings if f.cls in ('conflict','model error')]
    return report.graph


@pytest.mark.parametrize('name,cases',[
    ('self_check_workflow',('running','clean','conflict','error','capped','native_unknown')),
    ('self_conflict_history',('complete','capped','smaller','reproduced','missing_obligation')),
    ('self_owner_words',('verbatim','elided','forged','unrelated')),
])
def test_native_self_models_execute_real_owner_cases(name,cases):
    model=graph(name)
    calls={(call.action.name,tuple(call.args)):call.index for call in model.calls}
    action='compare' if name=='self_conflict_history' else 'inspect'
    trace=trace_calls(model,[calls[(action,(case,))] for case in cases])
    result=check_trace(model,trace)
    assert result.status=='conformant',result.to_dict()
    assert result.native['steps'] and result.native['footprint']['files']
    assert all(step['outcome']=='success' for step in result.native['steps'])


def test_native_history_compares_actual_complete_capped_and_changed_scope_receipts(project):
    import base64
    from copy import deepcopy
    from dataclasses import replace
    import json
    from flowguard.flow.checks import CONFLICT,REPLAYED,replay_conflict
    from flowguard.flow.descriptors import input_evidence,model_descriptor
    from flowguard.flow.explore import Bounds
    from flowguard.flow.parts import PartSpec,part_digest
    from flowguard.flow.project import conflict_entry
    from flowguard.map.requests import store_request
    store_request(project.root,(ROOT/'.flowguard/requests/R15.md').read_bytes(),identifier='R15')
    source='''from flowguard.flow import Model,need
m=Model('repair')
ITEMS=m.objects('item',OBJECTS)
m.field('state',('broken','ready'),'broken',over=ITEMS,source='R15')
@m.action(item=ITEMS,source='R15')
def repair(s,item):
    need(s['state',item]=='ready')
    s['state',item]='ready'
@m.action(item=ITEMS,source='R15')
def reset(s,item):
    need(s['state',item]=='ready')
    s['state',item]='broken'
m.progress('can become ready',when=lambda s,item:True,
           goal=lambda s,item:s['state',item]=='ready',over=ITEMS,source='R15')
MODEL=m
'''
    path=project.flow('repair',source.replace('OBJECTS',"'A','B'"))
    def observe(limit=200000):
        loaded=load_model(path,project.root)
        report=check_model(loaded,Bounds(limit))
        digest=part_digest(project.root,PartSpec('core','repair',(('max_states',limit),)),list(loaded.reads))
        descriptor=model_descriptor(loaded,report,digest,input_evidence(project.root,loaded.reads))
        observation=dict(receipt=digest,finished=True,loaded=True,complete=report.graph.complete,
                         errors=len(report.graph.errors),scope=descriptor['scope'],obligations=descriptor['obligations'],replay='not_run')
        return loaded,report,observation
    before,broken,baseline=observe()
    finding=next(f for f in broken.findings if f.cls==CONFLICT and f.kind=='STUCK')
    original=conflict_entry(finding,observation=baseline)
    assert replay_conflict(before.model,original,Bounds())[0]==REPLAYED
    reproduced=deepcopy(baseline);reproduced['replay']='reproduced'
    # Correct one unsourced mistaken guard, preserving every sourced field and action.
    fixed=source.replace('OBJECTS',"'A','B'").replace("need(s['state',item]=='ready')","need(s['state',item]=='broken')",1)
    path.write_text(fixed)
    _,clean,complete=observe()
    assert clean.graph.complete and not [f for f in clean.findings if f.cls==CONFLICT]
    _,_,capped=observe(1)
    assert not capped['complete']
    path.write_text(fixed.replace("'A','B'","'A'"))
    _,_,smaller=observe()
    path.write_text(fixed.replace(",source='R15'",''))
    _,_,removed=observe()
    model=graph('self_conflict_history')
    calls={(call.action.name,tuple(call.args)):call.index for call in model.calls}
    inputs=dict(entry={k:v for k,v in original.items() if k!='history'},baseline=baseline,
                cases=dict(complete=complete,capped=capped,smaller=smaller,reproduced=reproduced,missing_obligation=removed))
    start={'files':{'history-inputs.json':base64.b64encode(json.dumps(inputs).encode()).decode()}}
    binding=replace(model.model.adapter_binding,start=start)
    sequence=[calls[('compare',(case,))] for case in ('capped','smaller','complete','reproduced','missing_obligation')]
    sequence.insert(3,calls[('rediscover',())])
    result=check_trace(model,trace_calls(model,sequence),binding=binding)
    assert result.status=='conformant',result.to_dict()
    assert result.native['rule_captures']['native_evidence']['status']=='current'


def test_real_archive_decision_preserves_original_words_and_refuses_forged_authority(project):
    from flowguard.flow.decisions import record_decision,read_decision,evaluate_decision
    from flowguard.map.common import MapError
    from flowguard.map.requests import store_request,retire_request
    raw=(ROOT/'.flowguard/requests/R15.md').read_bytes()
    store_request(project.root,raw,identifier='R15')
    body=project.root/'.flowguard/requests/R15.md'
    sidecar=body.with_suffix('.json');metadata=sidecar.read_bytes()
    entry=dict(id='self-archive-choice',kind='SECOND ROUTE',model='self_archive',subject='GitHub',
               subject_terms=['GitHub'],sources=['R15'])
    event=record_decision(project.root,entry,owner=raw.decode().strip(),request='R15')
    assert read_decision(project.root,event['id'])==event
    decided=evaluate_decision(project.root,entry,event['id'])
    assert decided['open'] is True and decided['code_fixed'] is False
    with pytest.raises(MapError,match='quote_not_in_request'):
        record_decision(project.root,entry,owner='Invented requirement for GitHub.',request='R15')
    with pytest.raises(MapError,match='request_exists'):
        store_request(project.root,b'replacement text',identifier='R15')
    assert body.read_bytes()==raw and sidecar.read_bytes()==metadata
    retire_request(project.root,'R15')
    with pytest.raises(MapError,match='request_retired'):
        evaluate_decision(project.root,entry,event['id'])
    assert body.read_bytes()==raw


def test_intentionally_broken_actual_verdict_is_detected_by_the_native_self_model(monkeypatch):
    model=graph('self_check_workflow')
    binding=model.model.adapter_binding
    backend=binding.execute.__func__.__globals__['session'].replay.__globals__
    call=next(call.index for call in model.calls if call.args==('running',))
    original=backend['run_isolated_process']
    invoked=[]
    def controlled(command,**kwargs):
        invoked.append(True)
        command=list(command)
        mutation='''session_type=_worker.__globals__['_Session']
step=session_type.step
def broken(self,recipe,**kwargs):
    if recipe.get('name')=='inspect':
        actual=type(self.objects['system']).inspect.__globals__['verdict']
        assert actual.__module__=='flowguard.flow.cli'
        def wrong(*args,**options): return 'intentionally broken verdict',0
        actual.__code__=wrong.__code__
    return step(self,recipe,**kwargs)
session_type.step=broken
'''
        entry='_worker(sys.argv[1],fd)'
        assert command[2].count(entry)==1
        command[2]=command[2].replace(entry,'\n'+mutation+'\n'+entry)
        return original(command,**kwargs)
    monkeypatch.setitem(backend,'run_isolated_process',controlled)
    trace=trace_calls(model,[call])
    assert trace.final_state['exit']==4
    result=check_trace(model,trace)
    assert invoked
    assert result.status=='drift'
    assert result.native['steps'][0]['outcome']=='success'
    assert result.native['rule_captures']['native_evidence']['status']=='current'


def test_a_real_self_model_change_reports_planted_conflicts_and_keeps_capped_history(project):
    import json
    from checkrun import run_check
    from flowguard.map.requests import store_request
    store_request(project.root,(ROOT/'.flowguard/requests/R15.md').read_bytes(),identifier='R15')
    project.file('.flowguard/selfuse/owners.py',(ROOT/'.flowguard/selfuse/owners.py').read_text())
    source=(ROOT/'.flowguard/flow/self_check_workflow.py').read_text()
    # The fixture's real driver still calls the canonical installed product library.
    # Only its local driver is a project-owned source anchor in this isolated project.
    source=source.replace(",'flowguard/flow/cli.py'",'').replace(",'flowguard/flow/jobs.py:Outcome'",'')
    path=project.flow('self_check_workflow',source)
    runs={}
    clean=run_check(project.root,'--json');runs['clean']=clean.data
    assert clean.code==0 and not clean.data['conflicts'],clean.out+clean.err
    path.write_text(source.replace("'running':4","'running':0",1))
    planted=run_check(project.root,'--json');runs['planted']=planted.data
    assert planted.code==1,planted.out+planted.err
    assert {'BROKEN','MODEL DRIFT'} <= {finding['kind'] for finding in planted.data['conflicts']}
    identifiers={finding['id'] for finding in planted.data['conflicts']}
    drift=next(finding for finding in planted.data['conflicts'] if finding['kind']=='MODEL DRIFT')
    summary=drift['detail']['native']
    record=json.loads((project.root/summary['record']).read_text())
    actual=record['info']['native']['checks'][summary['check']]
    assert actual['status']=='drift' and actual['native']['steps']
    path.write_text(source)
    capped=run_check(project.root,'--max-states','1','--json');runs['capped']=capped.data
    assert capped.code==1 and identifiers <= {finding['id'] for finding in capped.data['conflicts']},capped.out+capped.err
    fixed=run_check(project.root,'--json');runs['fixed']=fixed.data
    assert fixed.code==0 and not fixed.data['conflicts'],fixed.out+fixed.err
    assert identifiers <= {entry['id'] for entry in fixed.data['closed']}
    project.file('self-change-observations.json',json.dumps(runs,ensure_ascii=False,indent=2)+'\n')


def test_existing_archive_worker_and_release_controls_use_native_pytest_recording():
    from flowguard.flow.fallback import record_tests
    nodeids=[
        'tests/flow/test_self_use.py::test_real_archive_decision_preserves_original_words_and_refuses_forged_authority',
        'tests/flow/test_wait.py::test_the_caller_never_runs_model_code',
        'tests/flow/test_release_result.py::test_release_without_tests_names_the_scope',
        'tests/flow/test_native_evidence.py::test_emitted_stuck_regression_executes_the_repair_not_only_the_old_prefix',
    ]
    result=record_tests(ROOT,nodeids,timeout=120)
    assert result['pytest_exitcode']==0, result
    assert {row['test'] for row in result['recordings']}==set(nodeids)
    assert all(row['pytest_outcome']=='passed' for row in result['recordings'])
    assert result['test_scope']['finished'] is True
    archive=next(row for row in result['recordings'] if row['test']==nodeids[0])
    functions={(event['path'],event['function']) for event in archive['observer_events']}
    assert ('tests/flow/test_self_use.py',nodeids[0].split('::')[-1]) in functions
    # Engine-owned package imports use the controller's import shim. Their exact
    # source identities remain inputs; the original assertions exercise the APIs.
    files=result['footprint']['files']
    assert str(ROOT/'flowguard/flow/decisions.py') in files
    from flowguard.flow.parts import ENGINE_DIGEST,_engine_digest
    assert ENGINE_DIGEST==_engine_digest()  # Includes request code loaded by the engine bootstrap.
    # Child command execution is an explicit observation gap, not in-process proof.
    assert result['test_scope']['observer_gaps']
