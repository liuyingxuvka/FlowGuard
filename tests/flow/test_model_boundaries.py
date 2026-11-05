"""Data artifacts and native-code claims retain their different evidence bounds."""
import json

from checkrun import run_check
from flowguard.flow.project import read_conflicts
from flowguard.map.inventory import coverage_kind

DATA_MODEL = '''import json
from flowguard.flow import Model
with open('story.contract.json') as source:
    result=json.load(source)['result']
m=Model('story',covers=['story.contract.json'])
m.field('state',('broken','ready'),'broken',source='R1')
@m.action(source='R1')
def repair(s):
    s['state']=result
m.terminal('state',('ready',),source='R1')
m.reach('ready exists',lambda s:s['state']=='ready',source='R1')
MODEL=m
'''


def test_data_only_covered_model_can_close_as_model_correction(project):
    project.request('R1','Repair must reach the ready state.\n')
    project.file('story.contract.json',json.dumps({'result':'broken'}))
    project.flow('story',DATA_MODEL)
    first=run_check(project.root,'--json')
    ids={c['id'] for c in first.data['conflicts']}
    assert ids
    project.file('story.contract.json',json.dumps({'result':'ready'}))
    after=run_check(project.root,'--json')
    assert after.code==0, after.out
    saved=read_conflicts(project.root)
    assert ids <= {c['id'] for c in saved['closed']}
    assert all(c['closure']['kind']=='model_corrected' for c in saved['closed'])
    assert all(c['closure']['boundary']=='model-only' for c in saved['closed'])


def test_code_covered_model_does_not_use_data_only_closure(project):
    project.request('R1','Repair must reach the ready state.\n')
    project.file('app.py',"class Program:\n    result='broken'\n")
    model=DATA_MODEL.replace("import json\n",'').replace("with open('story.contract.json') as source:\n    result=json.load(source)['result']",'from app import Program\nresult=Program.result').replace("covers=['story.contract.json']","covers=['app.py:Program']")
    project.flow('story',model)
    first=run_check(project.root,'--json')
    ids={c['id'] for c in first.data['conflicts']}
    project.file('app.py',"class Program:\n    result='ready'\n")
    after=run_check(project.root,'--json')
    assert after.code==1 and ids <= {c['id'] for c in after.data['conflicts']}
    assert not read_conflicts(project.root)['closed']


def test_cover_directory_is_resolved_by_the_actual_source_inventory(project):
    project.file('contracts/story.contract.json','{}\n')
    assert coverage_kind(project.root,['contracts'])=='data-only'
    project.file('contracts/check.py','X=1\n')
    assert coverage_kind(project.root,['contracts'])=='code'
    assert coverage_kind(project.root,['missing'])=='unknown'
