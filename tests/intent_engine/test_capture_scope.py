"""Early omission is exactly the existing model's test-entry boundary."""
import importlib
from dataclasses import replace
from collections import defaultdict

import pytest

from flowguard.intent import anchors
from flowguard.intent.config import load_config,setup_path
from flowguard.intent.imports import prepare
from flowguard.intent.flow import Capture,Flow,Node,Relation,Read,runtime_check,_scenario_scopes
from tests.intent_engine.test_scenario_execution import scenario
from tests.intent_engine.test_flow_model import source,BASIC,relation


def load_case(root):
    setup_path(load_config(root));prepare(root)
    return importlib.import_module('policy'),importlib.import_module('test_case')


@pytest.mark.parametrize('broken,verdict', [(False,'ok'),(True,'red')])
def test_test_entry_filter_keeps_actual_relation_verdict_and_occurrence(tmp_path,broken,verdict):
    binding=scenario(tmp_path)
    if broken:
        path=tmp_path/'policy.py'
        path.write_text(path.read_text().replace('return x <= 3','return x > 3'))
        binding.anchor_index=anchors.collect_sources(tmp_path,[('policy.py','policy'),('test_case.py','test_case',True)])
    policy,case=load_case(tmp_path)
    value=2
    # One outside call comes before the real case. Occurrence selectors must
    # retain their original identity even when its unused event is omitted.
    model=binding.flow
    oracle=relation(lambda x:x<=3,{'x':int})
    model.nodes=tuple(replace(node,occurrence=2) if node.name=='answer' else node for node in model.nodes)
    old=model.relations[0]
    model.relations=(Relation(oracle,old.inputs,old.actual,old.on),)
    for filtered in (False,True):
        with Capture(tmp_path,binding.anchor_index,'one',models=[model] if filtered else None) as captured:
            policy.choice(2)
            case.test_case(value)
        assert captured.issues==[]
        cases,_=_scenario_scopes(model,{'one':captured.events},binding.anchor_index)
        events=next(iter(cases.values()))
        actual=[e for e in events if e.anchor=='choice' and e.phase=='return']
        assert len(actual)==1 and actual[0].occurrence==2
        assert actual[0].values['x']==value and actual[0].result is (not broken)
        outcome=runtime_check(model,captured,binding.anchor_index,rules={oracle.id:oracle})
        assert outcome['verdict']==verdict,outcome
        if filtered:
            assert len(captured.events)==4
        else:
            assert len(captured.events)==6


def test_production_entry_bypass_is_never_pruned(tmp_path):
    index,module=source(tmp_path,BASIC)
    model=Flow('PRODUCTION','assumed: required sequence',(Node('begin',start=True),Node('publish',phase='return',end=True)),(('begin','publish'),))
    outputs=[]
    for filtered in (False,True):
        with Capture(tmp_path,index,'bypass',models=[model] if filtered else None) as observed:
            module.publish(3)
        outputs.append(runtime_check(model,observed,index))
        assert [(e.anchor,e.phase)for e in observed.events]==[('publish','call'),('publish','return')]
    assert all(r['verdict']=='red' for r in outputs),outputs


def test_production_model_is_retained_alongside_an_unentered_test_model(tmp_path):
    binding=scenario(tmp_path)
    policy,_=load_case(tmp_path)
    production=Flow('DIRECT','assumed: production begins here',(Node('choice',start=True,end=True,phase='return'),),())
    with Capture(tmp_path,binding.anchor_index,'direct',models=[binding.flow,production]) as observed:
        assert policy.choice(4) is False
    assert [(e.anchor,e.phase)for e in observed.events]==[('choice','call'),('choice','return')]


def test_unmodeled_anchor_inside_test_entry_keeps_its_actual_event_and_notice(tmp_path):
    binding=scenario(tmp_path)
    path=tmp_path/'policy.py'
    path.write_text(path.read_text().replace('return x <= 3','return audit(x <= 3)')+'''
# flowguard: sensor audit(value: flag) -> result: bool
def audit(value: bool) -> bool:
    return value
''')
    binding.anchor_index=anchors.collect_sources(tmp_path,[('policy.py','policy'),('test_case.py','test_case',True)])
    policy,case=load_case(tmp_path)
    oracle=relation(lambda x:x<=3,{'x':int})
    old=binding.flow.relations[0]
    binding.flow.relations=(Relation(oracle,old.inputs,old.actual,old.on),)
    results=[]
    for filtered in (False,True):
        with Capture(tmp_path,binding.anchor_index,'one',models=[binding.flow] if filtered else None) as captured:
            policy.choice(2)
            case.test_case(2)
        cases,_=_scenario_scopes(binding.flow,{'one':captured.events},binding.anchor_index)
        events=next(iter(cases.values()))
        assert captured.issues==[]
        audit=[e for e in events if e.anchor=='audit']
        assert [(e.phase,e.occurrence,e.values['value'],e.result)for e in audit]==[
            ('call',2,True,None),('return',2,True,True)]
        results.append(runtime_check(binding.flow,captured,binding.anchor_index,rules={oracle.id:oracle}))
        assert len(captured.events)==(6 if filtered else 10)
    assert results[0]==results[1]
    assert any('anchor not included in FLOW: audit' in item for item in results[1]['info'])


def test_unentered_test_scope_does_not_claim_an_actual_result(tmp_path):
    from flowguard.intent.flow import relation_observations
    binding=scenario(tmp_path)
    policy,_=load_case(tmp_path)
    results=[]
    for filtered in (False,True):
        with Capture(tmp_path,binding.anchor_index,'outside',models=[binding.flow] if filtered else None) as observed:
            policy.choice(4)
        result=relation_observations(binding.flow,observed,binding.anchor_index,'RULE')
        assert result['observations']==[]
        results.append(result)
    assert results[0]['status']==results[1]['status']=='grey'
