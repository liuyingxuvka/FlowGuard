"""Finite model data and real scoped observations, without an adapter API."""
import importlib.util
from pathlib import Path
import sys
import uuid

import pytest

from flowguard.intent.api import Refused, rule
from flowguard.intent.anchors import collect_sources
from flowguard.intent.flow import (Capture, Flow, Node, Read, Relation, Transition,
                                  check_flow, finite_check, runtime_check, validate)


def source(tmp_path, body):
    name = 'flow_case_' + uuid.uuid4().hex
    path = tmp_path / (name + '.py')
    path.write_text(body)
    index = collect_sources(tmp_path, [(path.name, name)])
    assert not [i for i in index.issues if i.level == 'red'], index.issues
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return index, module


def relation(fn, fields, identifier='EQUAL'):
    return rule(identifier, decides=identifier, source='assumed: independent unit control', fields=fields)(fn)


BASIC = '''# flowguard: event begin(value: int)
def begin(value: int): return None
# flowguard: event save(value: int)
def save(value: int): return value
# flowguard: event publish(value: int)
def publish(value: int): return value
'''


def test_small_model_matches_true_sequence_and_original_rule(tmp_path):
    index, m = source(tmp_path, BASIC)
    same_value = relation(lambda saved, published: saved == published, {'saved': int, 'published': int})
    model = Flow('PUBLISH', 'assumed: small flow',
        (Node('begin', start=True), Node('save', phase='return'), Node('publish', phase='return', end=True)),
        (('begin', 'save'), ('save', 'publish')),
        relations=(Relation(same_value, {'saved': Read('save'), 'published': Read('publish')}, on='publish'),))
    with Capture(tmp_path, index, 'one') as captured:
        m.begin(3); m.save(3); m.publish(3)
    result = check_flow(model, index, captured.events)
    assert result['verdict'] == 'ok', result
    assert result['runtime']['checked_relations'] == 1
    assert len(captured.events) == 6  # call/return, never a set of entered functions


def test_call_is_not_success_and_publishing_old_value_is_red(tmp_path):
    index, m = source(tmp_path, BASIC.replace('return value\n# flowguard: event publish', 'raise ValueError("save failed")\n# flowguard: event publish'))
    model = Flow('PUBLISH', 'assumed: save must finish',
        ('begin', Node('save', phase='return'), Node('publish', phase='return')),
        (('begin', 'save'), ('save', 'publish')))
    with Capture(tmp_path, index, 'one') as captured:
        m.begin(3)
        with pytest.raises(ValueError): m.save(3)
        m.publish(2)
    result = runtime_check(model, captured.events, index)
    assert result['verdict'] == 'red', result
    assert any('begin -> publish' in r for r in result['red'])


def test_old_payload_is_rejected_by_real_reading_relation(tmp_path):
    index, m = source(tmp_path, BASIC)
    same_value = relation(lambda saved, published: saved == published, {'saved': int, 'published': int})
    model = Flow('PUBLISH', 'assumed: relation',
        ('begin', Node('save', phase='return'), Node('publish', phase='return')),
        (('begin', 'save'), ('save', 'publish')),
        relations=(Relation(same_value, {'saved': Read('save'), 'published': Read('publish')}, on='publish'),))
    with Capture(tmp_path, index, 'one') as captured:
        m.begin(3); m.save(3); m.publish(2)
    result = runtime_check(model, captured.events, index)
    assert result['verdict'] == 'red' and any('EQUAL' in r for r in result['red']), result


def test_repeated_calls_are_not_deduplicated_or_last_wins(tmp_path):
    index, m = source(tmp_path, BASIC)
    model = Flow('PUBLISH', 'assumed: one publication',
        ('begin', Node('save', phase='return'), Node('publish', phase='return')),
        (('begin', 'save'), ('save', 'publish')))
    with Capture(tmp_path, index, 'one') as captured:
        m.begin(3); m.save(3); m.publish(3); m.publish(4)
    result = runtime_check(model, captured.events, index)
    assert result['verdict'] == 'red', result
    publications = [e for e in captured.events if e.anchor == 'publish' and e.phase == 'return']
    assert [e.occurrence for e in publications] == [1, 2]


def test_occurrence_metadata_selects_two_real_readings(tmp_path):
    index, m = source(tmp_path, BASIC)
    same_value = relation(lambda before, after: before == after, {'before': int, 'after': int})
    model = Flow('READ', 'assumed: equal reread',
        (Node('before', 'save', phase='return', occurrence=1), Node('after', 'save', phase='return', occurrence=2)),
        (('before', 'after'),), relations=(Relation(same_value, {'before': Read('before'), 'after': Read('after')}, on='after'),))
    with Capture(tmp_path, index, 'one') as captured:
        m.save(3); m.save(3)
    result = runtime_check(model, captured.events, index)
    assert result['verdict'] == 'ok', result


def test_missing_edge_coverage_stays_grey(tmp_path):
    index, m = source(tmp_path, BASIC)
    model = Flow('PUBLISH', 'assumed: optional save branch',
        (Node('begin'), Node('save'), Node('publish', end=True)),
        (('begin', 'save'), ('save', 'publish'), ('begin', 'publish')))
    with Capture(tmp_path, index, 'one') as captured:
        m.begin(3); m.publish(3)
    result = runtime_check(model, captured.events, index)
    assert result['verdict'] == 'grey' and any('unobserved edge begin -> save' in x for x in result['grey'])


def test_different_cases_cannot_supply_each_others_missing_steps(tmp_path):
    index, m = source(tmp_path, BASIC)
    model = Flow('PUBLISH', 'assumed: scope', ('begin', 'save', 'publish'), (('begin', 'save'), ('save', 'publish')))
    with Capture(tmp_path, index, 'first') as first: m.begin(3); m.save(3)
    with Capture(tmp_path, index, 'second') as second: m.publish(3)
    result = runtime_check(model, [*first.events, *second.events], index)
    assert result['verdict'] == 'red', result
    assert any('first' in x for x in result['red']) and any('second' in x for x in result['red'])


def test_finite_states_reachability_and_invalid_transition(tmp_path):
    body = '''class Job:
    # flowguard: states Job.status = new | saved | published
    status = 'new'
# flowguard: event save(value: int)
def save(value: int): return value
# flowguard: event publish(value: int)
def publish(value: int): return value
'''
    index, _ = source(tmp_path, body)
    good = Flow('JOB', 'assumed: finite', ('save', 'publish'), (('save', 'publish'),),
        (Transition('Job.status', 'new', 'saved', 'save', initial=True),
         Transition('Job.status', 'saved', 'published', 'publish')))
    result = finite_check(good, index)
    assert result['verdict'] == 'ok' and result['states'] == 2, result
    bad = Flow('JOB', 'assumed: impossible state', ('save', 'publish'), (('save', 'publish'),),
        (Transition('Job.status', 'new', 'published', 'save', initial=True),
         Transition('Job.status', 'saved', 'published', 'publish')))
    result = finite_check(bad, index)
    assert result['verdict'] == 'red' and any('no enabled transition' in r for r in result['red']), result


def test_nonfinite_or_unknown_state_is_not_exhaustive(tmp_path):
    index, _ = source(tmp_path, BASIC)
    model = Flow('JOB', 'assumed: unknown', ('save',), (), (Transition('Unknown.status', 0, 1, 'save'),))
    result = finite_check(model, index)
    assert result['verdict'] != 'ok' and any('Unknown.status' in r for r in result['red'] + result['grey'])


def test_missing_anchor_is_red_and_large_model_warns(tmp_path):
    index, _ = source(tmp_path, BASIC)
    result = validate(Flow('BAD', 'assumed: missing', ('missing',), ()), index)
    assert result['verdict'] == 'red'
    nodes = tuple(Node('n' + str(n), 'save') for n in range(11))
    result = validate(Flow('BIG', 'assumed: split', nodes, tuple(('n'+str(n), 'n'+str(n+1)) for n in range(10))), index)
    assert any('10' in r for r in result['info'])


def test_utf8_view_is_explicit_and_preserves_bom_and_crlf(tmp_path):
    body = '''# flowguard: event case(payload: str)
def case(payload: str): return None
# flowguard: sensor read(raw: bytes) -> body: bytes
def read(raw: bytes) -> bytes: return raw
'''
    index, m = source(tmp_path, body)
    original = relation(lambda payload: payload, {'payload': str}, 'BYTES')
    model = Flow('BYTES', 'assumed: strict utf8', ('case', Node('read', phase='return')), (('case','read'),),
        relations=(Relation(original, {'payload': Read('case','arg.payload')}, Read('read',view='utf8'), 'read'),))
    payload = '\ufeff原话\r\nline\n'
    with Capture(tmp_path, index, 'one') as captured: m.case(payload); m.read(payload.encode('utf-8'))
    assert runtime_check(model, captured.events, index)['verdict'] == 'ok'
    with Capture(tmp_path, index, 'bad') as captured: m.case(payload); m.read(payload.encode('utf-8-sig'))
    assert runtime_check(model, captured.events, index)['verdict'] == 'red'


def test_custom_conversion_callback_is_refused():
    with pytest.raises(ValueError, match='view'): Read('read', view=lambda x: x)


def test_state_runtime_uses_actual_before_after_and_catches_wrong_change(tmp_path):
    body = '''class Job:
    # flowguard: states Job.status = new | saved | published
    status = 'new'
    # flowguard: event save(value: int)
    def save(self, value: int): self.status = 'saved'; return value
    # flowguard: event publish(value: int)
    def publish(self, value: int): self.status = 'published'; return value
'''
    index, m = source(tmp_path, body)
    model = Flow('JOB', 'assumed: actual states',
        (Node('save',phase='return'), Node('publish',phase='return')), (('save','publish'),),
        (Transition('Job.status','new','saved','save'), Transition('Job.status','saved','published','publish')))
    with Capture(tmp_path,index,'one') as captured:
        job=m.Job(); job.save(3); job.publish(3)
    assert runtime_check(model,captured.events,index)['verdict'] == 'ok'
    with Capture(tmp_path,index,'bad') as captured:
        job=m.Job(); job.status='published'; job.save(3); job.publish(3)
    result=runtime_check(model,captured.events,index)
    assert result['verdict']=='red' and any('actually changes' in r for r in result['red']),result


def test_refused_matches_actual_exception_and_caught_none_is_a_real_return(tmp_path):
    body='''# flowguard: event reject(value: int)
def reject(value: int): raise ValueError('actual refusal')
# flowguard: event catches(value: int)
def catches(value: int):
    try: raise ValueError('handled')
    except ValueError: return None
'''
    index,m=source(tmp_path,body)
    original=relation(lambda value: Refused('ValueError'),{'value':int},'REFUSAL')
    model=Flow('REFUSAL','assumed: refusal',(Node('reject',phase='raise'),),(),
        relations=(Relation(original,{'value':Read('reject','arg.value')},Read('reject','error'),'reject'),))
    with Capture(tmp_path,index,'one')as captured:
        with pytest.raises(ValueError):m.reject(3)
        m.catches(3)
    assert runtime_check(model,captured.events,index)['verdict']=='ok'
    assert [(e.phase,e.result)for e in captured.events if e.anchor=='catches']==[('call',None),('return',None)]


def test_ambiguous_prior_reading_is_grey_instead_of_last_wins(tmp_path):
    index,m=source(tmp_path,BASIC)
    equal=relation(lambda saved,published:saved==published,{'saved':int,'published':int})
    model=Flow('LOOP','assumed: repeated save',('begin',Node('save',phase='return'),Node('publish',phase='return')),
        (('begin','save'),('save','save'),('save','publish')),
        relations=(Relation(equal,{'saved':Read('save'),'published':Read('publish')},on='publish'),))
    with Capture(tmp_path,index,'one')as captured:m.begin(3);m.save(2);m.save(3);m.publish(3)
    result=runtime_check(model,captured.events,index)
    assert result['verdict']=='grey' and any('2 occurrences' in r for r in result['grey']),result


def test_finite_state_invariant_uses_existing_rule(tmp_path):
    body='''class Job:
    # flowguard: states Job.status = new | saved | broken
    status='new'
# flowguard: event save(value: int)
def save(value: int): return value
'''
    index,_=source(tmp_path,body)
    allowed=relation(lambda status:status!='broken',{'status':('new','saved','broken')},'ALLOWED')
    model=Flow('JOB','assumed: invariant',('save',),(),(Transition('Job.status','new','broken','save'),),
        relations=(Relation(allowed,{'status':Read('$state','Job.status')}),))
    result=finite_check(model,index)
    assert result['verdict']=='red' and any('ALLOWED' in r for r in result['red']),result


def joint_flow(tmp_path, children=2, coupled=False, detail=False, detail_kind=bool):
    from test_joint_composition import project, parts
    from types import SimpleNamespace
    from flowguard.intent import sites
    model,engine=project(tmp_path,children,coupled=coupled,detail_kind=detail_kind)
    app=next(model.cfg.root.glob('joint_app_*.py'))
    names=('left','right','third')[:children]
    index=model.anchor_index
    fn=sites.resolve(app.stem+':approve')
    checked = parts(model, engine, 'TOP')
    # The pytest IntentItem adds target identity to its actual result payload.
    checked = [checked[0], *(dict(p, target=model.rules['TOP'].homes[0].target) for p in checked[1:])]
    engine.contract_summary('TOP', parts=checked)  # actual complete pytest-item path
    nodes=[Node(n,'gate_'+n,phase='return',model=n.upper())for n in names]+[Node('approve',phase='return')]
    edges=tuple((a.name,b.name)for a,b in zip(nodes,nodes[1:]))
    relation_=Relation(model.rules['TOP'],{n+'_ok':Read(n)for n in names},Read('approve'),'approve')
    flow=Flow('FLOW','doc SPEC.txt "Approval is exactly the conjunction of the gate outcomes."',tuple(nodes),edges,relations=(relation_,))
    with Capture(model.cfg.root,index,'joint')as captured:
        assert fn(*(SimpleNamespace(flag=True,detail=detail)for _ in names)) is True
    return flow,index,captured,engine


@pytest.mark.parametrize('children',[2,3])
def test_existing_engine_lower_models_verify_real_joint_contract(tmp_path,children):
    flow,index,captured,engine=joint_flow(tmp_path,children)
    result=check_flow(flow,index,captured.events,engine=engine)
    assert result['verdict']=='ok',result
    cells=next(v for k,v in engine.results.items()if k[0]=='TOP' and len(k)>2 and k[2]=='cells')
    assert cells['composition']['parent_calls']==4**children


@pytest.mark.parametrize('children',[2,3])
def test_joint_counterexample_cannot_hide_behind_passing_actual_scenario(tmp_path,children):
    flow,index,captured,engine=joint_flow(tmp_path,children,coupled=True)
    result=check_flow(flow,index,captured.events,engine=engine)
    assert result['verdict']=='red',result
    assert any('depends on more' in r for r in result['red']),result


def test_lower_green_dictionary_does_not_replace_engine_verification(tmp_path):
    flow,index,captured,_=joint_flow(tmp_path)
    fake={name:{'verdict':'ok','complete':True,'outcomes':[['bool','True'],['bool','False']]}for name in ('LEFT','RIGHT','TOP')}
    result=check_flow(flow,index,captured.events,contracts=fake)
    assert result['verdict']=='grey' and any('metadata alone' in r for r in result['grey']),result


def test_actual_lower_site_cannot_be_replaced_by_an_unrelated_site(tmp_path):
    from dataclasses import replace
    flow,index,captured,engine=joint_flow(tmp_path)
    changed=[replace(e,site='somewhere:fake')if e.anchor=='gate_left'else e for e in captured.events]
    result=check_flow(flow,index,changed,engine=engine)
    assert result['verdict']=='grey' and any('outside the verified lower contract' in r for r in result['grey']),result


def test_actual_wrong_lower_result_is_red(tmp_path):
    from dataclasses import replace
    flow,index,captured,engine=joint_flow(tmp_path)
    changed=[replace(e,result=False)if e.anchor=='gate_left'and e.phase=='return'else e for e in captured.events]
    result=check_flow(flow,index,changed,engine=engine)
    assert result['verdict']=='red' and any('actual lower result' in r for r in result['red']),result


def test_test_scenario_has_real_ancestry_and_ignores_other_utility_calls(tmp_path):
    body=BASIC+'''# flowguard: event scenario(value: int)
def scenario(value: int): save(value); publish(value)
'''
    index,m=source(tmp_path,body)
    from dataclasses import replace
    index.entries=tuple(replace(a,source_role='test')if a.name=='scenario'else a for a in index.entries)
    equal=relation(lambda saved,published:saved==published,{'saved':int,'published':int})
    model=Flow('SCOPED','assumed: explicit test input',
        (Node('case','scenario'),Node('save',phase='return',caller='case'),Node('publish',phase='return',caller='case')),
        (('case','save'),('save','publish')),
        relations=(Relation(equal,{'saved':Read('save'),'published':Read('publish')},on='publish'),))
    with Capture(tmp_path,index,'ordinary')as unrelated:m.save(99);m.publish(99)
    with Capture(tmp_path,index,'actual')as captured:
        m.save(99);m.scenario(3);m.publish(99)
    result=runtime_check(model,[*unrelated.events,*captured.events],index)
    assert result['verdict']=='ok' and result['checked_relations']==1,result
    assert result['ignored_case_scopes']==1


def test_direct_caller_selects_role_without_first_or_last_recursive_result(tmp_path):
    body='''# flowguard: sensor recursive(value: number) -> answer: bool
def recursive(value: int) -> bool:
    if value > 0: recursive(value-1)
    return value > 0
# flowguard: event scenario(value: int)
def scenario(value: int): recursive(value)
'''
    index,m=source(tmp_path,body)
    from dataclasses import replace
    index.entries=tuple(replace(a,source_role='test')if a.name=='scenario'else a for a in index.entries)
    original=relation(lambda value:value>0,{'value':int})
    model=Flow('ROLE','assumed: exact source caller',('scenario',Node('answer','recursive',phase='return',caller='scenario')),
        (('scenario','answer'),),relations=(Relation(original,{'value':Read('scenario','arg.value')},Read('answer'),'answer'),))
    with Capture(tmp_path,index,'one')as captured:m.scenario(2)
    values=[e.result for e in captured.events if e.anchor=='recursive'and e.phase=='return']
    assert values==[False,True,True]
    result=runtime_check(model,captured.events,index)
    assert result['verdict']=='ok' and result['checked_relations']==1,result


def test_changed_direct_caller_edge_is_grey_not_a_behavior_bug(tmp_path):
    body=BASIC+'''def helper(value): save(value)
# flowguard: event scenario(value: int)
def scenario(value: int): helper(value)
'''
    index,m=source(tmp_path,body)
    from dataclasses import replace
    index.entries=tuple(replace(a,source_role='test')if a.name=='scenario'else a for a in index.entries)
    model=Flow('SCOPED','assumed: fixed experimental caller',('scenario',Node('save',phase='return',caller='scenario')),(('scenario','save'),))
    with Capture(tmp_path,index,'one')as captured:m.scenario(3)
    result=runtime_check(model,captured.events,index)
    assert result['verdict']=='grey' and not result['red'],result
    assert any('caller edge' in r for r in result['grey'])


def test_fixed_empty_and_literal_equals_views_do_not_execute_callbacks(tmp_path):
    body='''# flowguard: event inputs(value: bool)
def inputs(value: bool): return None
# flowguard: sensor problems(value: flag) -> issues: list
def problems(value: bool) -> list: return [] if value else ['actual diagnostic']
'''
    index,m=source(tmp_path,body)
    original=relation(lambda value:value,{'value':bool})
    model=Flow('LITERALS','assumed: literal size relation',('inputs',Node('problems',phase='return')),(('inputs','problems'),),
        relations=(Relation(original,{'value':Read('inputs','arg.value')},Read('problems',view='empty'),'problems'),))
    for value in (True,False):
        with Capture(tmp_path,index,str(value))as captured:m.inputs(value);m.problems(value)
        assert runtime_check(model,captured.events,index)['verdict']=='ok'
    with pytest.raises(ValueError,match='literal'):Read('problems',equals=lambda:True)


def test_explicit_states_from_native_local_and_literal_equality(tmp_path):
    body='''class State:
    # flowguard: states State.status = new | ok | failed
    status='new'
# flowguard: event sentinel(complete: bool)
def sentinel(complete: bool):
    state=State()
    state.status='ok' if complete else 'failed'
'''
    index,m=source(tmp_path,body)
    original=relation(lambda complete:complete,{'complete':bool})
    model=Flow('STATE','assumed: observed literal', (Node('sentinel',phase='return'),),(),
        relations=(Relation(original,{'complete':Read('sentinel','arg.complete')},Read('sentinel','state.State.status',equals='ok'),'sentinel'),))
    for value in (True,False):
        with Capture(tmp_path,index,str(value))as captured:m.sentinel(value)
        assert runtime_check(model,captured.events,index)['verdict']=='ok'


def test_new_production_entry_bypasses_owner_in_actual_runtime(tmp_path):
    body=BASIC+'''# flowguard: event added_entry(value: int)
def added_entry(value: int): publish(value)
'''
    index,m=source(tmp_path,body)
    model=Flow('PRODUCTION','assumed: publication requires saving',
        ('begin',Node('save',phase='return'),Node('publish',phase='return')),
        (('begin','save'),('save','publish')))
    with Capture(tmp_path,index,'new_route')as captured:m.added_entry(3)
    result=runtime_check(model,captured.events,index)
    assert result['verdict']=='red' and any('outside declared entries' in r for r in result['red']),result
    assert any('added_entry' in r for r in result['info'])


def test_static_new_root_route_is_checked_but_wrapping_existing_entry_is_legal(tmp_path):
    from flowguard.intent.flow import static_check
    from flowguard.intent.flow_paths import PathReport
    index,_=source(tmp_path,BASIC)
    model=Flow('PRODUCTION','assumed: owner path',('begin','save','publish'),(('begin','save'),('save','publish')))
    bad=static_check(model,PathReport((('new_entry','publish'),),(),('app.py',)))
    assert bad['verdict']=='red' and any('new entry new_entry' in r for r in bad['red']),bad
    good=static_check(model,PathReport((('new_wrapper','begin','save','publish'),),(),('app.py',)))
    assert good['verdict']=='ok' and any('new_wrapper' in r for r in good['info']),good


def test_mutable_enum_value_and_noncontainer_empty_are_unverified(tmp_path):
    body = """from enum import Enum
class Token(Enum): MUTABLE=[]
# flowguard: event token(value: Token)
def token(value: Token): return []
# flowguard: event wrong(value: bool)
def wrong(value: bool): return ''
"""
    index,m=source(tmp_path,body)
    original=relation(lambda value:True,{'value':bool})
    model=Flow('OPAQUE','assumed: no hidden coercion',(Node('token',phase='return'),),(),
        relations=(Relation(original,{'value':Read('token','arg.value')},Read('token',view='empty'),'token'),))
    with Capture(tmp_path,index,'one')as captured:m.token(m.Token.MUTABLE)
    result=runtime_check(model,captured.events,index)
    assert result['verdict']=='grey' and any('immutable primitive' in r for r in result['grey']),result
    model=Flow('WRONG','assumed: exact container',(Node('wrong',phase='return'),),(),
        relations=(Relation(original,{'value':Read('wrong','arg.value')},Read('wrong',view='empty'),'wrong'),))
    with Capture(tmp_path,index,'one')as captured:m.wrong(True)
    result=runtime_check(model,captured.events,index)
    assert result['verdict']=='grey' and any('actual list' in r for r in result['grey']),result


def test_several_declared_state_instances_stay_grey(tmp_path):
    body="""class State:
    # flowguard: states State.status = new | ok
    status='new'
# flowguard: event sentinel(complete: bool)
def sentinel(complete: bool):
    first=State(); second=State()
    first.status='ok'
"""
    index,m=source(tmp_path,body)
    original=relation(lambda complete:complete,{'complete':bool})
    model=Flow('STATE','assumed: no instance guessing',(Node('sentinel',phase='return'),),(),
        relations=(Relation(original,{'complete':Read('sentinel','arg.complete')},Read('sentinel','state.State.status',equals='ok'),'sentinel'),))
    with Capture(tmp_path,index,'one')as captured:m.sentinel(True)
    result=runtime_check(model,captured.events,index)
    assert result['verdict']=='grey' and any('several' in r for r in result['grey']),result
    assert any('several' in r for r in captured.issues)


def test_interleaved_case_streams_and_unpaired_returns_do_not_claim_verification(tmp_path):
    from dataclasses import replace
    index,m=source(tmp_path,BASIC)
    model=Flow('FLOW','assumed: complete invocation',(Node('save',phase='return'),),())
    with Capture(tmp_path,index,'first')as first:m.save(3)
    with Capture(tmp_path,index,'second')as second:m.save(3)
    bad=[first.events[0],*second.events,first.events[1]]
    result=runtime_check(model,bad,index)
    assert result['verdict']=='grey' and any('interleaved' in r for r in result['grey']),result
    result=runtime_check(model,[first.events[1]],index)
    assert result['verdict']=='grey' and any('no matching observed call' in r for r in result['grey']),result


def test_bool_lower_input_42_is_a_declared_domain_error(tmp_path):
    # Same original 42 input: it was incorrectly labelled domain-valid before
    # the shared Kind check. Keep it and strengthen the expected boundary.
    flow,index,captured,engine=joint_flow(tmp_path,detail=42)
    result=check_flow(flow,index,captured.events,engine=engine)
    assert result['verdict']=='red',result
    assert any('detail' in r and 'bool' in r for r in result['red']),result


def test_int_lower_input_42_is_valid_but_outside_verified_pool(tmp_path):
    flow,index,captured,engine=joint_flow(tmp_path,detail=42,detail_kind=int)
    result=check_flow(flow,index,captured.events,engine=engine)
    assert result['verdict']=='grey' and not result['red'],result
    assert any('outside the verified lower representatives' in r for r in result['grey']),result


def test_arbitrary_recursive_flow_cannot_borrow_a_same_named_rule_contract(tmp_path):
    from dataclasses import replace
    flow,index,captured,engine=joint_flow(tmp_path)
    nested=Flow('LEFT','assumed: unrelated flow',('not_the_real_anchor',),())
    flow.nodes=tuple(replace(n,model=nested)if n.name=='left'else n for n in flow.nodes)
    result=check_flow(flow,index,captured.events,engine=engine)
    assert result['verdict']=='grey' and any('recursive Flow' in r for r in result['grey']),result


@pytest.mark.parametrize('bypass',[True,False])
def test_real_map_module_root_new_entry_respects_existing_owner(tmp_path,bypass):
    from contextlib import closing
    from flowguard.structure import build
    from flowguard.intent.flow import static_check
    from flowguard.intent.flow_paths import analyze_root_paths
    body=BASIC+"""# flowguard: event existing_entry(value: int)
def existing_entry(value: int): save(value); publish(value)
# flowguard: event added_entry(value: int)
def added_entry(value: int): """+('publish(value)'if bypass else'existing_entry(value)')+"""
if __name__=='__main__': added_entry(3)
"""
    index,_=source(tmp_path,body)
    model=Flow('PRODUCTION','assumed: all real root routes',('existing_entry','save','publish'),
        (('existing_entry','save'),('save','publish')))
    with closing(build(tmp_path))as graph:
        report=analyze_root_paths(graph,index,{'existing_entry','save','publish'})
    result=static_check(model,report)
    assert result['verdict']==('red'if bypass else'ok'),result
    if bypass:assert any('new entry added_entry' in r for r in result['red']),result


def test_invariant_does_not_become_a_synthetic_decision_reading(tmp_path):
    from flowguard.intent.flow import relation_observations
    index,m=source(tmp_path,BASIC)
    original=relation(lambda value:True,{'value':int})
    model=Flow('INVARIANT','assumed: no actual output',(Node('save',phase='return'),),(),
        relations=(Relation(original,{'value':Read('save','arg.value')},on='save'),))
    with Capture(tmp_path,index,'one')as captured:m.save(3)
    projected=relation_observations(model,captured,index,original.id)
    assert projected['status']=='grey' and projected['observations']==[]
    assert any('invariant' in r for r in projected['grey'])


def test_one_recorder_can_delegate_from_existing_calibration_hook(tmp_path):
    index,m=source(tmp_path,BASIC)
    recorder=Capture(tmp_path,index,'backend')
    def hook(frame,event,arg):
        watched=recorder.on_trace(frame,event,arg)
        return hook if watched else None
    assert sys.gettrace() is None
    sys.settrace(hook)
    try:m.save(3)
    finally:sys.settrace(None);recorder.close()
    assert recorder.issues==[]
    assert [(e.phase,e.result)for e in recorder.events]==[('call',None),('return',3)]


def replacement_flow(tmp_path, *, wrong=False, overrides=False, conflict=False):
    from flowguard.intent.config import load_config
    from flowguard.intent.loader import load
    from flowguard.intent.engine import Engine
    module='replacement_'+uuid.uuid4().hex
    path=tmp_path/(module+'.py')
    path.write_text('# flowguard: sensor accept(days: day) -> answer: bool\n'
                    'def accept(days: int) -> bool: return days <= '+('9'if wrong else'7')+'\n')
    (tmp_path/'tests/intent').mkdir(parents=True)
    (tmp_path/'pyproject.toml').write_text('[tool.flowguard]\nauthority_docs=["policy.txt"]\n')
    (tmp_path/'policy.txt').write_text('The corrected window permits seven days.\n')
    relation_key='overrides'if overrides else'supersedes'
    (tmp_path/'tests/intent/policy.py').write_text('''from flowguard.intent import rule,row
@rule('OLD',decides='window',fields={'days':int},source='doc policy.txt "The corrected window permits seven days."')
def OLD(days): return days <= 3
OLD.rows(row(days=3,expect=True,why='old still applicable boundary'),
         row(days=4,expect=False,why='old fourth day',retired='current owner explicitly permits seven days'))
@rule('NEW',decides='window',fields={'days':int},source='doc policy.txt "The corrected window permits seven days."',RELATION=[OLD])
def NEW(days): return days <= 7
NEW.rows(row(days=4,expect=True,why='new owner permits fourth day'),row(days=8,expect=False,why='eighth day still refused'))
'''.replace('RELATION',relation_key))
    if conflict:
        policy=tmp_path/'tests/intent/policy.py'
        policy.write_text(policy.read_text()+"\n@rule('OTHER',decides='window',fields={'days':int},source='doc policy.txt \"The corrected window permits seven days.\"')\ndef OTHER(days): return False\n")
    model=load(load_config(tmp_path));assert not model.errors,model.errors
    engine=Engine(model)
    native=__import__(module)
    index=collect_sources(tmp_path,[(path.name,module)])
    flow=Flow('WINDOW','doc policy.txt "The corrected window permits seven days."',(Node('accept',phase='return'),),(),
        relations=(Relation(model.rules['OLD'],{'days':Read('accept','arg.days')},Read('accept'),'accept'),))
    with Capture(tmp_path,index,'four')as first:native.accept(4)
    with Capture(tmp_path,index,'eight')as second:native.accept(8)
    return flow,index,[*first.events,*second.events],engine


@pytest.mark.parametrize('overrides',[False,True])
def test_flow_relation_uses_current_effective_policy_after_legitimate_replacement(tmp_path,overrides):
    flow,index,events,engine=replacement_flow(tmp_path,overrides=overrides)
    old=engine.m.rules['OLD'];new=engine.m.rules['NEW']
    assert old.eval({'days':4}) is False and engine.effective(old,{'days':4}) is True
    assert old.all_rows[1].retired=='current owner explicitly permits seven days'
    if not overrides:
        assert any(cell=={'days':3} for cell,_,_ in engine._cases_of(new,'rows'))
    result=runtime_check(flow,events,index,engine=engine)
    assert result['verdict']=='ok',result


def test_wrong_native_code_still_red_under_replacement_policy(tmp_path):
    flow,index,events,engine=replacement_flow(tmp_path,wrong=True)
    result=runtime_check(flow,events,index,engine=engine)
    assert result['verdict']=='red' and any('NEW' in r or 'OLD' in r for r in result['red']),result


def test_finite_invariant_uses_same_effective_replacement_owner(tmp_path):
    _,_,_,engine=replacement_flow(tmp_path)
    body="""class Stage:
    # flowguard: states Stage.days = 3 | 4
    days=3
# flowguard: event advance(value: int)
def advance(value: int): return value
"""
    index,_=source(tmp_path,body)
    model=Flow('FINITE','assumed: current owner',('advance',),(),
        (Transition('Stage.days',3,4,'advance'),),
        (Relation(engine.m.rules['OLD'],{'days':Read('$state','Stage.days')}),))
    result=finite_check(model,index,engine=engine)
    assert result['verdict']=='ok',result


def test_active_rule_conflict_is_red_instead_of_an_arbitrary_expected_value(tmp_path):
    flow,index,events,engine=replacement_flow(tmp_path,conflict=True)
    result=runtime_check(flow,events,index,engine=engine)
    assert result['verdict']=='red' and any('active rules conflict' in r for r in result['red']),result


def test_truthy_string_cannot_enter_a_declared_bool_relation_domain(tmp_path):
    body='''# flowguard: sensor active() -> value: bool
def active() -> bool: return 'False'
'''
    index,m=source(tmp_path,body)
    calls=[]
    def expected(active):
        calls.append(active)
        return bool(active)
    original=relation(expected,{'active':bool},'ACTIVE_BOOL')
    model=Flow('DOMAIN','assumed: boolean readings',(Node('active',phase='return'),),(),
        relations=(Relation(original,{'active':Read('active')},on='active'),))
    with Capture(tmp_path,index,'actual')as captured:m.active()
    result=runtime_check(model,captured,index)
    assert result['verdict']=='red',result
    assert calls==[], 'a value outside the declared domain must not reach the predicate'
    assert any('active' in r and 'bool' in r for r in result['red']),result


def test_finite_state_relation_uses_the_same_kind_gate_before_predicate(tmp_path):
    body='''class Flag:
    # flowguard: states Flag.active = 'False'
    active='False'
# flowguard: event inspect_flag()
def inspect_flag(): return None
'''
    index,_=source(tmp_path,body)
    calls=[]
    def expected(active):
        calls.append(active)
        return bool(active)
    original=relation(expected,{'active':bool},'FINITE_BOOL')
    model=Flow('FINITE_DOMAIN','assumed: strict state reading',('inspect_flag',),(),
        (Transition('Flag.active','False','False','inspect_flag'),),
        (Relation(original,{'active':Read('$state','Flag.active')}),))
    result=finite_check(model,index)
    assert result['verdict']=='red' and any('bool' in r for r in result['red']),result
    assert calls==[]


@pytest.mark.parametrize('names',[(),('active','extra')])
def test_actual_relation_field_set_mismatch_is_red_before_predicate(tmp_path,names):
    body='''# flowguard: sensor active() -> value: bool
def active() -> bool: return True
'''
    index,m=source(tmp_path,body)
    calls=[]
    def expected(active):calls.append(active);return active
    original=relation(expected,{'active':bool},'FIELDS')
    model=Flow('FIELDS','assumed: exact field wiring',(Node('active',phase='return'),),(),
        relations=(Relation(original,{name:Read('active')for name in names},on='active'),))
    with Capture(tmp_path,index,'actual')as captured:m.active()
    result=runtime_check(model,captured,index)
    assert result['verdict']=='red' and any('fields' in r for r in result['red']),result
    assert calls==[]


def test_path_reading_does_not_become_a_str_by_coercion(tmp_path):
    body='''from pathlib import Path
# flowguard: sensor path() -> value: Path
def path() -> Path: return Path('actual')
'''
    index,m=source(tmp_path,body)
    original=relation(lambda value:bool(value),{'value':str},'TEXT')
    model=Flow('PATH','assumed: real type',(Node('path',phase='return'),),(),
        relations=(Relation(original,{'value':Read('path')},on='path'),))
    with Capture(tmp_path,index,'actual')as captured:m.path()
    result=runtime_check(model,captured,index)
    assert result['verdict']=='red' and any('str' in r for r in result['red']),result
    assert isinstance(next(e.result for e in captured.events if e.phase=='return'),Path)
