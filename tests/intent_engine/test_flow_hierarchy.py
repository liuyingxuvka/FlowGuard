"""Registered child graphs export only complete proof from the same real calls."""
from dataclasses import replace
import importlib
import uuid

import pytest

from tests.intent_engine._cli_fixture import check as run_check
from tests.intent_engine._source_fixture import source_engine, source_sessions

from flowguard.intent import calibration
from flowguard.intent.anchors import _execution_session
from flowguard.intent.engine import Engine
from flowguard.intent.flow import Capture, Flow, Node, Read, Relation, check_flow
from flowguard.intent.loader import load


def project(tmp_path, *, missing_save=False, hierarchical=True, stateful=False, nested=False, export_entry=False):
    root=tmp_path / ('hierarchy_' + uuid.uuid4().hex)
    (root/'tests/intent').mkdir(parents=True)
    module='hierarchy_app_' + uuid.uuid4().hex
    native='test_native_' + module
    testnode='tests/' + native + '.py::test_case'
    (root/'pyproject.toml').write_text('[tool.flowguard]\nauthority_docs=["SPEC.txt"]\n')
    (root/'SPEC.txt').write_text('Child checks, saves and publishes before exporting flag.\nParent forwards the child outcome; stock is incidental.\n')
    (root/(module+'.py')).write_text('''# flowguard: event CHECK(flag: bool, detail: bool)
def check(flag: bool, detail: bool): return flag
# flowguard: event SAVE(flag: bool, detail: bool)
def save(flag: bool, detail: bool): return detail
# flowguard: sensor PUBLISH(flag: bool, detail: bool) -> done: bool
def publish(flag: bool, detail: bool) -> bool:
    if flag: return True
    return False
# flowguard: event ENTRY(flag: bool, detail: bool)
def child(flag: bool, detail: bool):
    check(flag, detail)
    save(flag, detail)
    return publish(flag, detail)
# flowguard: sensor UPPER(flag: bool, detail: bool, stock: bool) -> accepted: bool
def upper(flag: bool, detail: bool, stock: bool) -> bool:
    return child(flag, detail) is True
# flowguard: event PARENT_ENTRY(flag: bool, detail: bool, stock: bool)
def run(flag: bool, detail: bool, stock: bool):
    return upper(flag, detail, stock)
'''.replace('    save(flag, detail)\n','' if missing_save else '    save(flag, detail)\n'))
    if nested or export_entry:
        path=root/(module+'.py')
        text=path.read_text()
        if nested:
            text=text.replace('def check(flag: bool, detail: bool): return flag',
                              'def check(flag: bool, detail: bool): return '+('publish' if missing_save else 'save')+'(flag, detail)')
            text=text.replace('def save(flag: bool, detail: bool): return detail',
                              'def save(flag: bool, detail: bool): return publish(flag, detail)')
            prefix,body=text.split('def child(flag: bool, detail: bool):\n',1)
            _,suffix=body.split('# flowguard: sensor UPPER',1)
            text=prefix+'def child(flag: bool, detail: bool):\n    return check(flag, detail)\n# flowguard: sensor UPPER'+suffix
        if export_entry:
            text=text.replace('    return publish(flag, detail)\n', '    return publish(flag, detail) is True\n')
        path.write_text(text)
    if stateful:
        path=root/(module+'.py')
        text=path.read_text()
        text='''class Job:
    # flowguard: states Job.status = new | saved | published
    status='new'
JOB=Job()
def reset(): JOB.status='new'
'''+text
        text=text.replace('event SAVE(flag: bool, detail: bool)', 'event SAVE(flag: bool, detail: bool, job: Job)')
        text=text.replace('def save(flag: bool, detail: bool): return detail', "def save(flag: bool, detail: bool, job: Job=JOB): job.status='saved'; return detail")
        text=text.replace('sensor PUBLISH(flag: bool, detail: bool)', 'sensor PUBLISH(flag: bool, detail: bool, job: Job)')
        text=text.replace('def publish(flag: bool, detail: bool) -> bool:', "def publish(flag: bool, detail: bool, job: Job=JOB) -> bool:\n    job.status='published'")
        path.write_text(text)
    (root/('tests/'+native+'.py')).write_text('import pytest\nimport '+module+' as app\n'+'''@pytest.fixture
def flag(): return True
@pytest.fixture
def detail(): return False
@pytest.fixture
def stock(): return True
# flowguard: event CASE(flag: bool, detail: bool, stock: bool) calibrated_by='''+testnode+'''
def test_case(flag: bool, detail: bool, stock: bool):
    result = app.run(flag, detail, stock)
    assert result is True or result is False
''')
    if stateful:
        path=root/('tests/'+native+'.py')
        path.write_text(path.read_text().replace('    result = app.run', '    app.reset()\n    result = app.run'))
    policy='''from flowguard.intent import rule,row,flow,Node,Read,Relation,Transition
@rule('DONE',decides='done',fields={'flag':bool,'detail':bool},source='doc SPEC.txt "Child checks, saves and publishes before exporting flag."')
def DONE(flag,detail): return flag
DONE.rows(row(flag=True,detail=False,expect=True,why='flag permits'),row(flag=False,detail=False,expect=False,why='flag blocks'))
@rule('TOP',decides='accepted',fields={'done':bool,'stock':bool},uses=[DONE],source='doc SPEC.txt "Parent forwards the child outcome; stock is incidental."')
def TOP(done,stock): return done
TOP.rows(row(done=True,stock=True,expect=True,why='completed child is forwarded'))
'''
    if hierarchical:
        policy+='''flow('CHILD',source='doc SPEC.txt "Child checks, saves and publishes before exporting flag."',
 nodes=[Node('entry','ENTRY'),Node('check','CHECK',phase='return'),Node('save','SAVE',phase='return'),Node('published','PUBLISH',phase='return',end=True)],
 edges=[('entry','check'),('check','save'),('save','published')],
 relations=[Relation('DONE',{'flag':Read('entry','arg.flag'),'detail':Read('entry','arg.detail')},Read('published'),on='published')])
'''
    policy+='''flow('NATIVE',source='doc SPEC.txt "Parent forwards the child outcome; stock is incidental."',
 nodes=[Node('case','CASE'),Node('lower','PUBLISH',phase='return',model='MODEL'),Node('upper','UPPER',phase='return',end=True)],
 edges=[('case','lower'),('lower','upper')],
 relations=['''
    policy+='''Relation('DONE',{'flag':Read('case','arg.flag'),'detail':Read('case','arg.detail')},Read('lower'),on='lower'),'''
    policy+='''Relation('TOP',{'done':Read('lower'),'stock':Read('case','arg.stock')},Read('upper'),on='upper')])
'''
    if hierarchical:
        policy+='''flow('PARENT',source='doc SPEC.txt "Parent forwards the child outcome; stock is incidental."',
 nodes=[Node('start','PARENT_ENTRY'),Node('lower','PUBLISH',phase='return',model='CHILD'),Node('upper','UPPER',phase='return',end=True)],
 edges=[('start','lower'),('lower','upper')],
 relations=[Relation('TOP',{'done':Read('lower'),'stock':Read('start','arg.stock')},Read('upper'),on='upper')])
'''
    if stateful:
        policy=policy.replace("edges=[('entry','check'),('check','save'),('save','published')],", "edges=[('entry','check'),('check','save'),('save','published')],transitions=[Transition('Job.status','new','saved','save',initial=True),Transition('Job.status','saved','published','published')],")
    if nested:
        policy=policy.replace("Node('check','CHECK',phase='return'),Node('save','SAVE',phase='return')",
                              "Node('check','CHECK'),Node('save','SAVE')")
    if export_entry:
        policy=policy.replace("Node('published','PUBLISH',phase='return',end=True)",
                              "Node('published','PUBLISH',phase='return'),Node('end','ENTRY',phase='return',end=True)")
        policy=policy.replace("('save','published')],", "('save','published'),('published','end')],")
        policy=policy.replace("Read('published'),on='published')", "Read('end'),on='end')")
        policy=policy.replace("Node('lower','PUBLISH',phase='return'", "Node('lower','ENTRY',phase='return'")
    (root/'tests/intent/policy.py').write_text(policy.replace("'MODEL'",repr('CHILD' if hierarchical else 'DONE')))
    model=load(root=root)
    assert not model.errors,model.errors
    return model,Engine(model),module,native


def verified(tmp_path, **kwargs):
    model,_,module,native=project(tmp_path,**kwargs)
    engine=source_engine(model)
    with _execution_session(model.cfg.root),calibration._execution_session(model.cfg.root):
        for rule in model.rules.values():
            for home in rule.homes:
                assert calibration._prepare_scenario(model.cfg.root,home)['status']=='ok'
        for rule in model.rules.values():
            home=rule.homes[0]
            parts=[engine.run_rules(rule),*(dict(engine.run_home(rule,home,part),target=home.target) for part in ('rows','cells')),dict(engine.run_live(rule,home),target=home.target)]
            assert all(p['verdict']=='ok' for p in parts),parts
            engine.contract_summary(rule.id,parts=parts)
    scenario=importlib.import_module('tests.'+native)
    with Capture(model.cfg.root,model.anchor_index,'ordinary') as captured:
        scenario.test_case(True,False,True)
    return model,engine,captured


def test_rule_contract_cannot_prove_a_deleted_child_save(tmp_path):
    model,engine,captured=verified(tmp_path,missing_save=True,hierarchical=False)
    parent=check_flow(model.flows['NATIVE'],model.anchor_index,captured.events,engine=engine)
    child=Flow('CHILD',model.rules['DONE'].source,
               (Node('entry','ENTRY'),Node('check','CHECK',phase='return'),Node('save','SAVE',phase='return'),Node('published','PUBLISH',phase='return')),
               (('entry','check'),('check','save'),('save','published')))
    result=check_flow(child,model.anchor_index,captured.events)
    assert parent['verdict']=='ok',parent
    assert result['verdict']=='red',result
    assert engine.contract_summary('DONE')['verdict']=='ok'


@pytest.mark.parametrize('missing_save',[False,True])
def test_parent_exports_the_complete_registered_child_graph(tmp_path,missing_save):
    model,engine,captured=verified(tmp_path,missing_save=missing_save)
    result=engine.run_flow(model.flows['PARENT'],captured.events)
    assert result['verdict']==('red' if missing_save else 'ok'),'\n'.join(result['red']+result['grey'])
    assert engine.contract_summary('DONE')['verdict']=='ok'
    if missing_save:
        assert any('child Flow CHILD is red' in why for why in result['red']),result


@pytest.fixture
def hierarchy(tmp_path, source_sessions):
    return verified(tmp_path)


def test_unobserved_child_edge_stays_grey_at_parent(hierarchy):
    model,engine,captured=hierarchy
    child=model.flows['CHILD']
    changed=replace(child,edges=(*child.edges,('entry','published')))
    model.flows['CHILD']=changed
    try:
        result=engine.run_flow(model.flows['PARENT'],captured.events)
        assert result['verdict']=='grey' and not result['red'],result
        assert any('unobserved edge entry -> published' in why for why in result['grey']),result
    finally:
        model.flows['CHILD']=child


@pytest.mark.parametrize('problem',['missing','ambiguous','fake','cycle'])
def test_unverified_child_declarations_cannot_export_green(hierarchy,problem):
    model,engine,captured=hierarchy
    child,parent=model.flows['CHILD'],model.flows['PARENT']
    if problem=='missing':
        parent=replace(parent,nodes=tuple(replace(n,model='GONE') if n.model else n for n in parent.nodes))
    elif problem=='ambiguous':
        model.flows['CHILD']=replace(child,relations=(*child.relations,*child.relations))
    elif problem=='fake':
        parent=replace(parent,nodes=tuple(replace(n,model=replace(child)) if n.model else n for n in parent.nodes))
    else:
        model.flows['CHILD']=replace(child,nodes=tuple(replace(n,model='CHILD') if n.end else n for n in child.nodes))
    try:
        result=engine.run_flow(parent,captured.events)
        assert result['verdict']=='grey' and not result['red'],result
    finally:
        model.flows['CHILD']=child


def test_two_invocations_cannot_supply_each_others_missing_save(hierarchy):
    model,engine,captured=hierarchy
    good=captured.events
    bad=[replace(e,case='second') for e in good if e.anchor!='SAVE']
    result=engine.run_flow(model.flows['PARENT'],[*good,*bad])
    assert result['verdict']=='red' and any('check -> published' in why for why in result['red']),result


def test_output_cannot_borrow_an_entry_from_a_completed_other_call(hierarchy):
    model,engine,captured=hierarchy
    events=list(captured.events)
    entry=next(e for e in events if e.anchor=='ENTRY' and e.phase=='return')
    events=[replace(e,sequence=entry.sequence+1) if e.anchor=='PUBLISH' and e.phase=='return' else e for e in events]
    result=engine.run_flow(model.flows['PARENT'],events)
    assert result['verdict']=='grey' and any('ancestry crosses' in why for why in result['grey']),result


def test_child_state_proof_uses_actual_native_before_after(tmp_path):
    model,engine,captured=verified(tmp_path,stateful=True)
    parent=model.flows['PARENT']
    result=engine.run_flow(parent,captured.events)
    assert result['verdict']=='ok','\n'.join(result['red']+result['grey'])
    wrong=[replace(e,states={'Job.status':'published'}) if e.anchor=='SAVE' and e.phase=='return' else e for e in captured.events]
    result=engine.run_flow(parent,wrong)
    assert result['verdict']=='red' and any('actually changes' in why for why in result['red']),result
    unknown=[replace(e,before_states={}) if e.anchor=='SAVE' and e.phase=='return' else e for e in captured.events]
    result=engine.run_flow(parent,unknown)
    assert result['verdict']=='grey' and not result['red'],result


def test_parent_dependency_record_tracks_separate_child_declaration(hierarchy,tmp_path):
    from contextlib import closing
    from flowguard.intent import deps
    from flowguard.structure import build
    model,engine,captured=hierarchy
    child=model.flows['CHILD']
    relative='tests/intent/separate_child.py'
    path=model.cfg.root/relative
    original=model.file_of['CHILD']
    path.write_text("# independently maintained child graph\nEDGES=(('entry','check'),('check','save'),('save','published'))\n")
    model.file_of['CHILD']=relative
    try:
        with closing(build(model.cfg.root,roots=model.cfg.roots)) as graph:
            saved=deps.record(model.cfg,model,model.flows['PARENT'],[],graph)
            assert 'file:'+relative in saved['dependencies'],saved
            path.write_text("EDGES=(('entry','check'),('check','published'))\n")
            assert 'file:'+relative in deps.stale(saved,deps.Now(model.cfg,graph))
    finally:
        model.file_of['CHILD']=original
        path.unlink()


def test_changed_child_source_cannot_reuse_old_green_events(hierarchy):
    model,engine,captured=hierarchy
    path=next(model.cfg.root.glob('hierarchy_app_*.py'))
    original=path.read_text()
    try:
        path.write_text(original.replace('    save(flag, detail)\n',''))
        result=engine.run_flow(model.flows['PARENT'],captured.events)
        assert result['verdict']!='ok',result
        assert any('source identity changed' in why for why in result['grey']) or result['red'],result
    finally:
        path.write_text(original)


@pytest.mark.parametrize('variant,exit_code',[('positive',0),('delete-save',1),('untested-edge',0),('nested',0),('entry-return',0)])
def test_complete_cli_reports_the_real_hierarchy(tmp_path,variant,exit_code):
    from flowguard.intent import cli
    model,_,_,_=project(tmp_path,missing_save=variant=='delete-save',nested=variant=='nested',export_entry=variant=='entry-return')
    if variant=='untested-edge':
        path=model.cfg.root/'tests/intent/policy.py'
        path.write_text(path.read_text().replace("edges=[('entry','check'),('check','save'),('save','published')],",
                        "edges=[('entry','check'),('check','save'),('save','published'),('entry','published')],"))
    (model.cfg.root/'tests/test_flowguard_intent.py').write_text(
        'def test_flowguard_intent(request):\n from flowguard.intent.plugin import sentinel\n sentinel(request.config)\n')
    assert run_check(model.cfg,everything=True)==exit_code



def test_source_navigation_retains_the_child_model_reference(tmp_path):
    from flowguard.intent import cache
    model,_,_,_=project(tmp_path)
    summary=cache.scan(model.cfg)
    assert summary['rules']['PARENT']['models']==['CHILD']
    assert summary['rules']['CHILD']['models']==[]



@pytest.mark.parametrize('shape',['nested','entry-return'])
def test_real_child_entry_shapes_are_proved_not_guessed(tmp_path,shape):
    model,engine,captured=verified(tmp_path,nested=shape=='nested',export_entry=shape=='entry-return')
    result=engine.run_flow(model.flows['PARENT'],captured.events)
    assert result['verdict']=='ok','\n'.join(result['red']+result['grey'])
    no_entry=[event for event in captured.events if not(event.anchor=='ENTRY' and event.phase=='call')]
    result=engine.run_flow(model.flows['PARENT'],no_entry)
    assert result['verdict']=='grey' and any('no observed enclosing production entry' in why for why in result['grey']),result
    from flowguard.intent import sites
    native=sites.resolve_loaded(model.rules['DONE'].homes[0].scenario.target)
    with Capture(model.cfg.root,model.anchor_index,'another-call') as other:
        native(True,False,True)
    result=engine.run_flow(model.flows['PARENT'],[*no_entry,*other.events])
    assert result['verdict']=='grey' and any('no observed enclosing production entry' in why for why in result['grey']),result
    if shape=='entry-return':
        wrong=[replace(event,occurrence=event.occurrence+1) if event.anchor=='ENTRY' and event.phase=='return' else event for event in captured.events]
        result=engine.run_flow(model.flows['PARENT'],wrong)
        assert result['verdict']=='grey' and any('no observed enclosing production entry' in why for why in result['grey']),result
    else:
        completion=next(event for event in captured.events if event.anchor=='ENTRY' and event.phase=='return')
        wrong=[replace(event,sequence=completion.sequence+1) if event.anchor=='PUBLISH' and event.phase=='return' else event for event in captured.events]
        result=engine.run_flow(model.flows['PARENT'],wrong)
        assert result['verdict']=='grey' and any('ancestry crosses' in why for why in result['grey']),result



@pytest.mark.parametrize('shape',['nested','entry-return'])
def test_deleted_native_save_is_red_for_each_entry_shape(tmp_path,shape):
    model,engine,captured=verified(tmp_path,missing_save=True,nested=shape=='nested',export_entry=shape=='entry-return')
    result=engine.run_flow(model.flows['PARENT'],captured.events)
    assert result['verdict']=='red' and any('child Flow CHILD is red' in why for why in result['red']),result
    assert engine.contract_summary('DONE')['verdict']=='ok'
