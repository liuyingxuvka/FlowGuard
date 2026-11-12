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






@pytest.fixture
def hierarchy(tmp_path, source_sessions):
    return verified(tmp_path)












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



def test_chained_identity_source_calls_stay_unknown(tmp_path):
    from test_flow_paths import inspect,LEAVES,TARGETS
    result=inspect(tmp_path,LEAVES+'def entry(): return check() is check() is post()\n',TARGETS)
    assert result.paths==() and any('Compare expression order is not supported' in reason for reason in result.unknown)




