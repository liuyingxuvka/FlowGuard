"""Actual command/worker sessions over persistent source-bound conflicts."""
import json
import subprocess
import sys

import pytest

from checkrun import env, run_check
from flowguard.flow.project import read_conflicts

BROKEN = '''
from flowguard.flow import Model, need
m = Model('repair')
m.field('place', ['branch','main'], 'branch')
m.field('state', ['broken','ready'], 'broken', source='R1')
@m.action(source='R1')
def repair(s):
    need(s['place']=='main', 'repair only at main', source='R2')
    s['state']='ready'
m.terminal('state', ['ready'], source='R1')
m.terminal('place', ['main'])
m.progress('repair remains possible', lambda s:s['state']=='broken', lambda s:s['state']=='ready', source='R1')
ADDED
MODEL=m
'''
FIX = '''
@m.action()
def move_home(s):
    s['place']='main'
'''

CLEAN_LAMP = '''from flowguard.flow import Model
m=Model('lamp')
m.field('on',(False,True),False)
@m.action()
def flip(s):
    s['on']=not s['on']
MODEL=m
'''


def command(project, *args):
    return subprocess.run([sys.executable,'-m','flowguard',*args],cwd=project.root,env=env(),capture_output=True,text=True,timeout=120)


def prepare(project, template=BROKEN):
    project.request('R1','Broken tools must become ready after repair.\n')
    project.request('R2','Repair is allowed only at main.\n')
    return project.flow('repair', template.replace('ADDED',''))


def test_real_check_records_scope_guard_sources_and_keeps_model_only_fix_open(project):
    project.file('app.py', 'class Repair: pass\n')
    template = BROKEN.replace("Model('repair')", "Model('repair', covers=['app.py:Repair'])")
    prepare(project, template)
    first = run_check(project.root,'--json')
    assert first.code == 1, first.err + first.out
    saved = read_conflicts(project.root)
    stuck = next(c for c in saved['conflicts'] if c['kind']=='STUCK')
    assert {'R1','R2'} <= set(stuck['sources'])
    baseline = stuck['history']['baseline']
    assert baseline['scope']['coverage']['field:state'] == ["'broken'", "'ready'"]
    assert baseline['scope']['starts'][0].startswith('initial:')
    guard = next(o for o in baseline['obligations'] if o['kind']=='guard')
    assert guard['dependencies'] and guard['cases']
    project.flow('repair', template.replace('ADDED', FIX))
    second = run_check(project.root,'--json')
    assert second.code == 1, second.err + second.out
    inherited = next(c for c in read_conflicts(project.root)['conflicts'] if c['id']==stuck['id'])
    assert inherited['history']['baseline'] == baseline
    assert inherited['history']['latest']['outcome'] == 'model_absent'
    assert 'native original-condition' in next(f for f in second.data['conflicts'] if f['id']==stuck['id'])['detail']['kept']
    assert not second.data['closed']


def test_default_status_refreshes_changed_model_and_prints_conflicts_before_static_facts(project):
    prepare(project)
    result = command(project, 'status','--wait','30')
    assert result.returncode == 0, result.err
    assert result.stdout.index('OPEN STUCK') < result.stdout.index('FLOWGUARD STATUS')
    assert 'Repair is allowed only at main.' in result.stdout
    assert 'model-only: check the owner words and actual code' in result.stdout
    assert 'repair the model or code as warranted' in result.stdout
    assert 'repair the dead end in code' not in result.stdout
    assert '--provisional' not in result.stdout
    saved = read_conflicts(project.root)
    before = saved['models']['repair']['core']['digest']
    project.flow('repair', BROKEN.replace('ADDED', FIX))
    again = command(project, 'status','--json','--wait','30')
    data = json.loads(again.stdout)
    assert data['flow_refresh']['refreshed'] == ['repair']
    assert read_conflicts(project.root)['models']['repair']['core']['digest'] != before


def test_decide_owner_is_persistent_and_provisional_dead_end_is_rejected(project):
    prepare(project); checked = run_check(project.root, '--json')
    stuck = next(c for c in checked.data['conflicts'] if c['kind']=='STUCK')
    rejected = command(project,'decide',stuck['id'],'--provisional','Later','--json')
    assert rejected.returncode == 2 and 'provisional_not_allowed' in rejected.stdout
    owner = command(project,'decide',stuck['id'],'--owner','Broken tools must become ready after repair.','--request','R1','--json')
    assert owner.returncode == 0, owner.stdout + owner.stderr
    result = json.loads(owner.stdout)
    assert result['result']['open'] and not result['result']['commit_allowed'] and not result['result']['code_fixed']
    status = command(project,'status','--json')
    assert 'owner choice recorded; model/code repair still required' in status.stdout
    assert read_conflicts(project.root)['conflicts']


def test_read_only_commit_command_compares_actual_staged_bytes(project):
    project.flow('lamp', '''from flowguard.flow import Model
m=Model('lamp')
m.field('on',(False,True),False)
@m.action()
def flip(s):
    s['on']=not s['on']
MODEL=m
''')
    project.commit()
    path = project.root/'.flowguard/flow/lamp.py'
    path.write_text(path.read_text()+'\n# staged checked change\n')
    checked = run_check(project.root,'--json')
    assert checked.code == 0, checked.out
    project.git('add','.flowguard/flow/lamp.py')
    ready = command(project,'check','--commit-ready','--json')
    assert json.loads(ready.stdout)['ready'], ready.stdout
    path.write_text(path.read_text()+'\n# different staged bytes\n')
    project.git('add','.flowguard/flow/lamp.py')
    blocked = command(project,'check','--commit-ready','--json')
    data = json.loads(blocked.stdout)
    assert blocked.returncode == 1 and 'stale_index' in {r['code'] for r in data['reasons']}


def test_real_provisional_decision_keeps_question_and_picture_across_unrelated_session(project):
    from flowguard.map.requests import retire_request
    project.request('R1','Keep open_rule enabled.\n')
    project.request('R2','Keep closed_rule enabled.\n')
    project.flow('rules', """from flowguard.flow import Model
m=Model('rules')
m.field('open',(False,True),False)
@m.action()
def toggle(s):
    s['open']=not s['open']
m.always('open_rule', lambda s:s['open'],source='R1')
m.always('closed_rule', lambda s:not s['open'],source='R2')
MODEL=m
""")
    checked = run_check(project.root,'--json')
    conflict = next(c for c in checked.data['conflicts'] if c['kind']=='RULE CONTRADICTION')
    decided = command(project,'decide',conflict['id'],'--provisional','Keep the reversible current choice pending owner confirmation.','--json')
    assert decided.returncode == 0, decided.stdout + decided.stderr
    result = json.loads(decided.stdout)
    assert result['result']['open'] and result['result']['commit_allowed']
    assert conflict['picture'], checked.out
    picture = command(project,'show',conflict['id'],'--json')
    assert picture.returncode == 0, picture.stdout + picture.stderr
    assert run_check(project.root, '--json').code == 1
    stable = run_check(project.root, '--json')
    assert all(part['cached'] for part in stable.data['parts'])
    prior = next(row for row in read_conflicts(project.root)['conflicts'] if row['id']==conflict['id'])
    ledger = project.root/'.flowguard/conflicts.json'
    ledger.unlink()
    unrecorded = command(project, 'status', '--json')
    assert json.loads(unrecorded.stdout)['flow_refresh']['refreshed'] == [] and not ledger.exists()
    restored = run_check(project.root, 'rules', '--json')
    assert restored.code == 1 and all(part['cached'] for part in restored.data['parts'])
    recovered = next(row for row in read_conflicts(project.root)['conflicts'] if row['id']==conflict['id'])
    assert recovered['history']['baseline'] == prior['history']['baseline']
    assert recovered['history']['decision_refs'] == prior['history']['decision_refs']
    project.file('unrelated.py','X = 1\n')
    status = command(project,'status','--json')
    assert 'AI temporary decision, owner to confirm' in status.stdout
    retire_request(project.root,'R2')
    invalid = command(project,'status','--json')
    assert 'request_retired' in invalid.stdout


@pytest.mark.parametrize('walk_steps,seed', [(64,0), (0,11)])
def test_status_refreshes_only_changed_model_owner(project, walk_steps, seed):
    project.flow('a', """from flowguard.flow import Model
m=Model('a')
m.field('value',(0,1),0)
@m.action()
def flip(s):
    s['value']=1-s['value']
MODEL=m
""")
    project.flow('b', """from flowguard.flow import Model
m=Model('b')
m.field('value',(0,1),0)
@m.action()
def flip(s):
    s['value']=1-s['value']
MODEL=m
""")
    assert run_check(project.root,'--json','--walk-steps',str(walk_steps),'--seed',str(seed)).code == 0
    old = read_conflicts(project.root)['models']['b']['core']['digest']
    path = project.root/'.flowguard/flow/a.py'
    path.write_text(path.read_text()+'\n# change only a\n')
    status = command(project,'status','--json')
    assert json.loads(status.stdout)['flow_refresh']['refreshed'] == ['a']
    assert read_conflicts(project.root)['models']['b']['core']['digest'] == old


def test_status_names_model_missing_from_partial_record_and_check_restores_cached_results(project):
    prepare(project)
    lamp = project.flow('lamp', CLEAN_LAMP)
    checked = run_check(project.root, '--json')
    assert checked.code == 1, checked.out + checked.err
    original = {entry['id'] for entry in read_conflicts(project.root)['conflicts']}
    ledger = project.root / '.flowguard/conflicts.json'
    ledger.unlink()
    absent = command(project, 'status', '--json')
    assert json.loads(absent.stdout)['flow_models'] == [
        'flow models: no check recorded (run python -m flowguard check)']
    assert not ledger.exists()
    lamp.write_text(lamp.read_text() + '\n# only lamp needs refreshing\n')
    partial = command(project, 'status', '--json')
    data = json.loads(partial.stdout)
    assert data['flow_refresh']['refreshed'] == ['lamp']
    assert set(read_conflicts(project.root)['models']) == {'lamp'}
    assert data['flow_models'] == [
        'flow models: no check recorded for repair (run python -m flowguard check)']
    restored = run_check(project.root, 'repair', '--json')
    assert restored.code == 1, restored.out + restored.err
    assert all(part['cached'] for part in restored.data['parts'])
    saved = read_conflicts(project.root)
    assert set(saved['models']) == {'lamp', 'repair'}
    assert original == {entry['id'] for entry in saved['conflicts']}


def test_commit_ready_missing_partial_result_keeps_existing_staged_scope(project):
    repair = prepare(project)
    lamp = project.flow('lamp', CLEAN_LAMP)
    project.commit()
    assert run_check(project.root, '--json').code == 1
    ledger = project.root / '.flowguard/conflicts.json'
    ledger.unlink()
    lamp.write_text(lamp.read_text() + '\n# refresh lamp only\n')
    assert run_check(project.root, 'lamp', '--json').code == 0
    project.git('add', '.flowguard/flow/lamp.py', '.flowguard/conflicts.json')
    ready = command(project, 'check', '--commit-ready', '--json')
    assert ready.returncode == 0, ready.stdout + ready.stderr
    assert json.loads(ready.stdout)['affected'] == ['lamp']
    repair.write_text(repair.read_text() + '\n# staged missing result\n')
    project.git('add', '.flowguard/flow/repair.py')
    before = ledger.read_bytes()
    jobs = project.root / '.flowguard/cache/flow/jobs'
    runs = set(jobs.glob('*/*/plan.json'))
    blocked = command(project, 'check', '--commit-ready', '--json')
    assert blocked.returncode == 1, blocked.stdout + blocked.stderr
    assert json.loads(blocked.stdout)['reasons'] == [dict(code='missing_finished_result', model='repair')]
    assert ledger.read_bytes() == before and set(jobs.glob('*/*/plan.json')) == runs
    project.git('reset', '-q', 'HEAD', '--', '.')
    unaffected = command(project, 'check', '--commit-ready', '--json')
    assert unaffected.returncode == 0 and json.loads(unaffected.stdout)['affected'] == []


def test_numbered_object_renaming_keeps_same_decision_identity(project):
    project.request('R1','Keep open_rule enabled.\n')
    project.request('R2','Keep closed_rule enabled.\n')
    template = '''from flowguard.flow import Model
m=Model('rules')
items=m.objects('tool', 'OBJECT')
m.field('open',(False,True),False,over=items)
@m.action(tool=items)
def toggle(s,tool):
    s['open',tool]=not s['open',tool]
m.always('open_rule',lambda s:all(s['open',tool] for tool in items),source='R1')
m.always('closed_rule',lambda s:not any(s['open',tool] for tool in items),source='R2')
MODEL=m
'''
    project.flow('rules',template.replace('OBJECT','T1'))
    first=run_check(project.root,'--json')
    conflict=next(c for c in first.data['conflicts'] if c['kind']=='RULE CONTRADICTION')
    decided=command(project,'decide',conflict['id'],'--provisional','Keep reversible choice','--json')
    assert decided.returncode == 0, decided.stdout
    event=json.loads(decided.stdout)['decision']['id']
    project.flow('rules',template.replace('OBJECT','Renamed7'))
    after=run_check(project.root,'--json')
    assert conflict['id'] in {c['id'] for c in after.data['conflicts']}
    status=command(project,'status','--json')
    assert 'AI temporary decision, owner to confirm' in status.stdout
    assert 'provisional_evidence_changed' not in status.stdout
    saved=next(c for c in read_conflicts(project.root)['conflicts'] if c['id']==conflict['id'])
    assert event in saved['history']['decision_refs']


def test_pure_model_correction_closes_with_executed_model_regression_and_no_code_claim(project):
    prepare(project)
    before = run_check(project.root,'--json')
    original = next(c for c in before.data['conflicts'] if c['kind']=='STUCK')
    project.flow('repair', BROKEN.replace('ADDED', FIX))
    after = run_check(project.root,'--json')
    assert original['id'] not in {c['id'] for c in after.data['conflicts']}, after.out
    saved = read_conflicts(project.root)
    closed = next(c for c in saved['closed'] if c['id']==original['id'])
    proof = closed['closure']
    assert proof['kind']=='model_corrected' and proof['boundary']=='model-only'
    path=project.root/proof['regression']['path']
    executed=subprocess.run([sys.executable,str(path)],cwd=project.root,env=env(),capture_output=True,text=True)
    assert executed.returncode==0, executed.stderr
    (project.root/'.flowguard/conflicts.json').unlink()
    restored = run_check(project.root, 'repair', '--json')
    assert restored.code == after.code and all(part['cached'] for part in restored.data['parts'])
    recovered = next(row for row in read_conflicts(project.root)['closed'] if row['id']==original['id'])
    assert recovered['history']['baseline'] == closed['history']['baseline']
    assert recovered['closure']['kind'] == 'model_corrected' and recovered['closure']['regression']['passed']
    project.flow('repair',BROKEN.replace('ADDED',''))
    broken_again=subprocess.run([sys.executable,str(path)],cwd=project.root,env=env(),capture_output=True,text=True)
    assert broken_again.returncode!=0 and 'original model conflict reproduces' in broken_again.stderr


def test_commit_ready_without_result_is_read_only_and_starts_no_worker(project):
    project.flow('lamp', """from flowguard.flow import Model
m=Model('lamp')
m.field('on',(False,True),False)
@m.action()
def flip(s):
    s['on']=not s['on']
MODEL=m
""")
    project.commit()
    path=project.root/'.flowguard/flow/lamp.py'
    path.write_text(path.read_text()+'\n# staged\n')
    project.git('add','.flowguard/flow/lamp.py')
    result=command(project,'check','--commit-ready','--json')
    assert result.returncode==1
    assert {r['code'] for r in json.loads(result.stdout)['reasons']}=={'missing_result'}
    assert not (project.root/'.flowguard/cache/flow/jobs').exists()


def test_native_unknown_has_its_own_boundary_not_a_capped_model_claim(project):
    from flowguard.flow import jobs, cli
    from flowguard.flow.parts import PartContext, PartSpec, core_part
    from flowguard.flow.project import cache_dir
    from flowguard.flow import diagram
    path=project.flow('lamp', """from flowguard.flow import Model
m=Model('lamp')
m.field('on',(False,True),False)
@m.action()
def flip(s):
    s['on']=not s['on']
MODEL=m
""")
    spec=PartSpec('core','lamp',(('max_states',200000),))
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(diagram,'conflict_pictures',lambda *args:[])
        part=core_part(PartContext(project.root,spec,path,cache_dir(project.root)))
    # Unit boundary input to the renderer; actual native capture is tested by its owner.
    part.info['native']={'schema':'flowguard.native-evidence.v1','bound':True,'status':'unknown'}
    planned=jobs.Planned(spec,'.flowguard/flow/lamp.py')
    outcome=jobs.Outcome([planned],[part],[True],[None],True)
    assembled=cli.assemble(project.root,outcome,None)
    lines,data=cli.render(project.root,assembled,'python -m flowguard check')
    assert data['exit']==3 and data['unknown']==['lamp'] and not data['complete']
    assert 'native conformance unavailable: lamp' in data['verdict']
    assert 'capped at' not in data['verdict']
    assert cli.conflicts_data(project.root,assembled,None)['models']['lamp']['unknown']


@pytest.mark.parametrize('change', ['unchanged', 'new_reference', 'retired_owner', 'edited_decision', 'changed_scope', 'partial_ledger'])
def test_missing_ledger_recipe_revalidates_actual_decisions_and_live_changes(project, change):
    from flowguard.flow import jobs
    from flowguard.flow.project import read_manifest
    from flowguard.map.requests import retire_request
    lamp = None
    if change == 'partial_ledger':
        lamp = project.flow('lamp', "from flowguard.flow import Model\nm=Model('lamp')\nm.field('on',(False,True),False)\n@m.action()\ndef flip(s): s['on']=not s['on']\nMODEL=m\n")
    prepare(project)
    first = run_check(project.root, '--json')
    stuck = next(c for c in first.data['conflicts'] if c['kind'] == 'STUCK')
    decided = command(project, 'decide', stuck['id'], '--owner',
                      'Broken tools must become ready after repair.', '--request', 'R1', '--json')
    assert decided.returncode == 0, decided.stdout + decided.stderr
    identifier = json.loads(decided.stdout)['decision']['id']
    assert run_check(project.root, '--json').code == 1
    stable = run_check(project.root, '--json')
    assert stable.code == 1 and all(part['cached'] for part in stable.data['parts'])
    if change == 'new_reference':
        another = command(project, 'decide', stuck['id'], '--owner',
                          'Repair is allowed only at main.', '--request', 'R2', '--json')
        assert another.returncode == 0, another.stdout + another.stderr
        changed = run_check(project.root, '--json')
        assert changed.code == 1 and any(not part['cached'] for part in changed.data['parts'] if part['kind']=='core')
        assert len(next(row for row in read_conflicts(project.root)['conflicts'] if row['id']==stuck['id'])['history']['decision_refs']) == 2
    actual = read_manifest(project.root, 'repair', with_receipt=True)
    original_entry = next(row for row in read_conflicts(project.root)['conflicts'] if row['id']==stuck['id'])
    ledger = project.root / '.flowguard/conflicts.json'
    ledger.unlink()
    if change == 'retired_owner':
        retire_request(project.root, 'R1')
    elif change == 'edited_decision':
        event = project.root / '.flowguard/decisions' / (identifier + '.json')
        event.write_text(event.read_text().replace('Broken tools', 'Altered tools'))
    elif change == 'partial_ledger':
        lamp.write_text(lamp.read_text()+'\n# only lamp changed\n')
    elif change == 'changed_scope':
        model = project.root/'.flowguard/flow/repair.py'
        model.write_text(model.read_text().replace("['broken','ready']", "['broken','ready','retired']"))
    # These changes are outside the original model-only input stamp. The real
    # decision owner must still check their integrity and active authority.
    item = jobs.Planned.from_json(actual['planned'])
    assert (jobs.lookup(project.root, item, recorded_digest=actual['digest']) is not None) == (change != 'changed_scope')
    before = set((project.root/'.flowguard/cache/flow/jobs').glob('*/*/plan.json'))
    status = command(project, 'status', '--json')
    assert status.returncode == 0, status.stdout + status.stderr
    data = json.loads(status.stdout)
    if change in ('retired_owner', 'edited_decision', 'changed_scope'):
        assert data['flow_refresh']['refreshed'] == ['repair'] and ledger.exists()
        current_entry = next(row for row in read_conflicts(project.root)['conflicts'] if row['id']==stuck['id'])
        assert current_entry['history']['decision_refs'] == []
    else:
        if change == 'partial_ledger':
            assert data['flow_refresh']['refreshed'] == ['lamp']
            assert set(read_conflicts(project.root)['models']) == {'lamp'}
        else:
            assert data['flow_refresh']['refreshed'] == [] and not ledger.exists()
            assert set((project.root/'.flowguard/cache/flow/jobs').glob('*/*/plan.json')) == before
        before_restore = set((project.root/'.flowguard/cache/flow/jobs').glob('*/*/plan.json'))
        restored = run_check(project.root, 'repair', '--json')
        assert restored.code == 1 and all(part['cached'] for part in restored.data['parts'])
        assert set((project.root/'.flowguard/cache/flow/jobs').glob('*/*/plan.json')) == before_restore
        current_entry = next(row for row in read_conflicts(project.root)['conflicts'] if row['id']==stuck['id'])
        assert current_entry['history']['baseline'] == original_entry['history']['baseline']
        assert current_entry['history']['decision_refs'] == original_entry['history']['decision_refs']
