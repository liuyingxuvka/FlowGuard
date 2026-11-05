"""Old JSON/SQLite inputs use the real adapter and original worker/cache owners."""
import json
import os
from contextlib import closing
from pathlib import Path
import sqlite3
import pytest

from flowguard.flow.model import load_model

PROGRAM='''import json,sqlite3
from pathlib import Path
class Refusal(Exception): pass
class Program:
    def __init__(self):
        self.items={name:{'cond':'ready','new':True} for name in ('T1','T2')}
    def load(self,path):
        if Path(path).suffix=='.json':
            self.items=json.loads(Path(path).read_text())
        else:
            with sqlite3.connect(path) as db:
                self.items={name:{'cond':condition,'new':False} for name,condition in db.execute('select id,condition from tools order by id')}
    def tools(self): return list(self.items.keys())
    def damage(self,tool):
        if self.items[tool]['cond']!='ready': raise Refusal('already damaged')
        self.items[tool]={'cond':'repair','new':True}
    def repair(self,tool):
        if self.items[tool]['cond']!='repair': raise Refusal('not damaged')
        if not self.items[tool]['new']: raise Refusal('old stuck item was missed')
        self.items[tool]['cond']='ready'
'''
MODEL='''from flowguard.flow import Model,need
from flowguard.flow.adapter import fields
m=Model('tools',covers=['program.py:Program.damage','program.py:Program.repair'])
TOOLS=m.objects('tool','T1','T2')
m.field('cond',('ready','repair'),'ready',over=TOOLS)
@m.action(tool=TOOLS)
def damage(s,tool):
    need(s['cond',tool]=='ready')
    s['cond',tool]='repair'
@m.action(tool=TOOLS)
def repair(s,tool):
    need(s['cond',tool]=='repair')
    s['cond',tool]='ready'
m.progress('every damaged tool can recover',lambda s,t:s['cond',t]=='repair',lambda s,t:s['cond',t]=='ready',over=TOOLS)
def view(snapshot,ids=None):
    slots=m.kinds['tool']
    ids=slots if ids is None else ids
    items=fields(snapshot,names=('items',))['items']
    return {('cond',slot):items[actual]['cond'] for slot,actual in zip(slots,ids)}
def dispatch(value,ids):
    slots=m.kinds['tool']
    actual=dict(zip(slots,ids))[value.function_input['tool']]
    return {'name':value.function_name,'kwargs':{'tool':actual}}
def load(file): return [{'name':'load','args':[file]},{'name':'tools'}]
m.bind_adapter({'system':'program:Program','classes':['program:Program'],'refusal':['program:Refusal']},state=view,
               operations={'damage':'damage','repair':'repair'})
SAMPLES
MODEL=m
'''
DECL="m.saved_samples('fixtures/*',version='v0',load=load,state=view,dispatch=dispatch)"


def fixture(project,*,samples=True):
    project.file('program.py',PROGRAM)
    project.flow('tools',MODEL.replace('SAMPLES',DECL if samples else ''))
    items={f'old{number}':dict(cond='repair' if number%2 else 'ready',new=False) for number in range(12)}
    project.file('fixtures/v0.json',json.dumps(items))
    database=project.root/'fixtures/v0.sqlite'
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute('create table tools(id text,condition text)')
        connection.executemany('insert into tools values(?,?)',[(name,item['cond']) for name,item in items.items()])
    return items


def core(project,data):
    part=next(part for part in data['parts'] if part['kind']=='core' and part['model']=='tools')
    return json.loads((project.root/'.flowguard/cache/flow/parts'/(part['digest']+'.json')).read_text())


def test_model_loading_only_records_saved_sample_declarations(project):
    fixture(project)
    source=(project.root/'.flowguard/flow/tools.py').read_text().replace('def load(file): return',"def load(file): raise AssertionError('sample callback ran in model loader')\ndef unused(file): return")
    path=project.flow('tools',source)
    loaded=load_model(path,project.root)
    assert len(loaded.model.sample_sources)==1
    assert not any('fixtures' in path for path in loaded.reads)


def test_no_old_samples_is_an_explicit_boundary_without_a_new_gate(project):
    from checkrun import run_check
    fixture(project,samples=False)
    run=run_check(project.root,'--json')
    assert run.code==0,run.out+run.err
    saved=core(project,run.data)['info']['saved_samples']
    assert saved['status']=='unchecked' and saved['files']==[] and saved['starts']==[]
    public=run.data['models']['tools']['saved_samples']
    assert public['status']=='unchecked' and public['files']==public['starts']==0
    assert 'loads' not in public
    project.flow('other',"from flowguard.flow import Model\nm=Model('other')\nm.field('ready',(True,),True)\nMODEL=m\n")
    text=run_check(project.root)
    assert text.code==0 and text.out.count('old saves not checked')==1,text.out+text.err


def test_real_old_json_and_sqlite_starts_are_deduplicated_and_report_the_missed_recovery(project):
    from checkrun import run_check
    fixture(project)
    run=run_check(project.root,'--full','--json')
    assert run.code==1,run.out+run.err
    assert any(finding['kind']=='MODEL DRIFT' for finding in run.data['conflicts'])
    receipt=core(project,run.data)
    saved=receipt['info']['saved_samples']
    assert saved['worker_pid']!=os.getpid()
    assert len(saved['files'])==2 and len(saved['starts'])==2
    assert {Path(row['path']).suffix for row in saved['files']}=={'.json','.sqlite'}
    assert all(row['version']=='v0' and row['sha256'] for row in saved['files'])
    assert saved['objects']==24 and saved['object_width']==1
    public=run.data['models']['tools']['saved_samples']
    assert public['files']==2 and public['starts']==2 and public['objects']==24
    assert 'loads' not in public and 'worker_pid' not in public
    checks=receipt['info']['native']['checks']
    old=[check for check in checks.values() if check.get('saved_sample')]
    assert old and any(check['status']=='drift' for check in old)
    assert any(key.startswith('saved:') and key.endswith(':walk') and check.get('saved_sample')
               for key,check in checks.items())
    assert any('old stuck item was missed' in repr(check['native']) for check in old)
    assert all(check['native']['rule_captures']['native_evidence']['status']=='current' for check in old)


def test_actual_malformed_input_is_a_file_crash_and_not_an_engine_failure(project):
    from checkrun import run_check
    fixture(project)
    project.file('fixtures/malformed.json','{broken input')
    run=run_check(project.root,'--full','--json')
    assert run.code==1,run.out+run.err
    crash=next(finding for finding in run.data['conflicts'] if finding['kind']=='FILE CRASH')
    assert crash['detail']['exception']['type']=='json.decoder:JSONDecodeError'
    assert crash['detail']['saved_sample']['path']=='fixtures/malformed.json'
    assert not run.data['errors']
    import subprocess
    from checkrun import command,env
    shown=subprocess.run(command('show',crash['id'],'--json','--keep','1'),cwd=project.root,env=env(),capture_output=True,text=True,timeout=30)
    assert shown.returncode==0,shown.stdout+shown.stderr
    picture=json.loads(shown.stdout)['pictures'][0]
    assert picture['drawn'] and picture['subject_id']==crash['id']
    assert 'JSONDecodeError' in picture['mermaid']


def test_relational_rule_uses_actual_pairs_without_enumerating_more_objects(project):
    from checkrun import run_check
    fixture(project)
    path=project.root/'.flowguard/flow/tools.py'
    source=path.read_text().replace("m.progress('every damaged", "PAIRS=[(first,second) for first in TOOLS for second in TOOLS if first!=second]\nm.always('two repair states are unsafe',lambda s:all(s['cond',first]=='ready' or s['cond',second]=='ready' for first,second in PAIRS))\nm.progress('every damaged")
    source=source.replace("    need(s['cond',tool]=='ready')","    need(s['cond',tool]=='ready')\n    need(all(s['cond',other]=='ready' for other in TOOLS))")
    path.write_text(source)
    program=project.root/'program.py'
    program.write_text(PROGRAM.replace("    def damage(self,tool):","    def damage(self,tool):\n        if any(item['cond']=='repair' for item in self.items.values()): raise Refusal('another repair')"))
    run=run_check(project.root,'--full','--json')
    assert run.code==1,run.out+run.err
    assert any(finding['kind']=='BROKEN' and finding['detail'].get('saved_sample') for finding in run.data['conflicts'])
    saved=core(project,run.data)['info']['saved_samples']
    assert saved['object_width']==2 and len(saved['starts'])==4


def test_saved_only_model_conflict_picture_uses_its_cached_observed_start(project,monkeypatch):
    from checkrun import run_check
    from flowguard.flow.parts import PartContext,PartSpec,run_part
    from flowguard.native import session
    fixture(project)
    (project.root/'fixtures/v0.sqlite').unlink()
    project.file('fixtures/v0.json',json.dumps({'old0':dict(cond='repair',new=False),'old1':dict(cond='repair',new=False)}))
    path=project.root/'.flowguard/flow/tools.py'
    source=path.read_text().replace("m.progress('every damaged", "PAIRS=[(first,second) for first in TOOLS for second in TOOLS if first!=second]\nm.always('two repair states are unsafe',lambda s:all(s['cond',first]=='ready' or s['cond',second]=='ready' for first,second in PAIRS))\nm.progress('every damaged")
    path.write_text(source.replace("    need(s['cond',tool]=='ready')","    need(s['cond',tool]=='ready')\n    need(all(s['cond',other]=='ready' for other in TOOLS))"))
    program=PROGRAM.replace("        if not self.items[tool]['new']: raise Refusal('old stuck item was missed')\n",'')
    (project.root/'program.py').write_text(program.replace('    def damage(self,tool):',"    def damage(self,tool):\n        if any(item['cond']=='repair' for item in self.items.values()): raise Refusal('another repair')"))
    checked=run_check(project.root,'--full','--json')
    finding=next(row for row in checked.data['conflicts'] if row['kind']=='BROKEN' and row['detail'].get('saved_sample'))
    def rerun(*args,**kwargs):raise AssertionError('show must use checked saved observations')
    monkeypatch.setattr(session,'replay',rerun)
    picture=run_part(PartContext(project.root,PartSpec('picture','tools',(('what',finding['id']),)),path,project.root/'cache'))
    assert picture.info['drawn'] and picture.info['subject_id']==finding['id']
    assert 'saved input' in picture.info['first_line'] and 'repair' in picture.info['mermaid']
    import subprocess
    from checkrun import command,env
    shown=subprocess.run(command('show',finding['id'],'--json','--keep','1'),cwd=project.root,env=env(),capture_output=True,text=True,timeout=30)
    assert shown.returncode==0,shown.stdout+shown.stderr
    assert json.loads(shown.stdout)['pictures'][0]['subject_id']==finding['id']


def test_removed_samples_retain_the_original_conflict_and_new_files_invalidate_cache(project):
    from checkrun import run_check
    fixture(project)
    first=run_check(project.root,'--full','--json')
    assert first.code==1,first.out+first.err
    identifiers={finding['id'] for finding in first.data['conflicts']}
    project.file('fixtures/new.json',json.dumps({'another':dict(cond='repair',new=False)}))
    changed=run_check(project.root,'--full','--json')
    assert changed.code==1 and not next(part for part in changed.data['parts'] if part['kind']=='core')['cached']
    assert len(core(project,changed.data)['info']['saved_samples']['files'])==3
    for path in (project.root/'fixtures').iterdir():path.unlink()
    empty=run_check(project.root,'--full','--json')
    assert empty.code==1 and identifiers<={finding['id'] for finding in empty.data['conflicts']},empty.out+empty.err
    assert core(project,empty.data)['info']['saved_samples']['status']=='unchecked'


def test_actual_old_input_recovery_closes_only_with_the_executed_same_file_regression(project):
    from checkrun import run_check
    fixture(project)
    first=run_check(project.root,'--full','--json')
    assert first.code==1,first.out+first.err
    identifier=next(finding['id'] for finding in first.data['conflicts'] if finding['kind']=='MODEL DRIFT')
    original={path.name:path.read_bytes() for path in (project.root/'fixtures').iterdir()}
    program=project.root/'program.py'
    program.write_text(PROGRAM.replace("        if not self.items[tool]['new']: raise Refusal('old stuck item was missed')\n",''))
    repaired=run_check(project.root,'--full','--json')
    assert repaired.code==0 and identifier in {finding['id'] for finding in repaired.data['closed']},repaired.out+repaired.err
    receipt=core(project,repaired.data)
    proof=receipt['info']['native']['closures'][identifier]
    assert proof['regression']['passed'] is True
    assert {path.name:path.read_bytes() for path in (project.root/'fixtures').iterdir()}==original
    from flowguard.flow.regression import write_executable
    import pytest
    program.write_text(PROGRAM)
    artifact=project.root/proof['regression']['path']
    with pytest.raises(AssertionError,match='no longer conforms'):
        write_executable(project.root,proof['regression']['path'],artifact.read_text())


def test_supplied_file_must_be_actually_read_before_old_coverage_can_be_checked(project):
    from checkrun import run_check
    fixture(project)
    (project.root/'program.py').write_text(PROGRAM.replace('    def load(self,path):','    def load(self,path):\n        return\n    def unused_load(self,path):'))
    run=run_check(project.root,'--full','--json')
    assert run.code==3 and not run.data['conflicts'],run.out+run.err
    saved=core(project,run.data)['info']['saved_samples']
    assert saved['status']=='unknown' and not saved['starts']
    assert any('did not read' in reason for reason in saved['limits'])


def test_sample_projection_fault_is_an_engine_error_not_a_file_crash(project):
    from checkrun import run_check
    fixture(project)
    path=project.root/'.flowguard/flow/tools.py'
    path.write_text(path.read_text().replace('def view(snapshot,ids=None):',"def view(snapshot,ids=None):\n    if ids is not None: raise LookupError('actual sample projection bug')"))
    run=run_check(project.root,'--full','--json')
    assert run.code==2 and not run.data['conflicts'],run.out+run.err
    assert 'NativeEngineError' in run.data['verdict'] and 'projection bug' in run.data['verdict']


def test_a_failed_unchanged_native_prefix_never_becomes_successful_construction(project):
    import base64
    from dataclasses import replace
    from flowguard.flow.checks import check_model
    from flowguard.flow.adapter import check_trace,trace_calls
    fixture(project,samples=False)
    report=check_model(load_model(project.root/'.flowguard/flow/tools.py',project.root))
    binding=replace(report.graph.model.adapter_binding,start={'files':{'bad.json':base64.b64encode(b'{bad').decode()}},
                    prefix=({'name':'load','args':[{'$file':'bad.json'}]},))
    result=check_trace(report.graph,trace_calls(report.graph,()),binding=binding)
    assert result.native['steps'][0]['outcome']=='crash'
    assert result.native['steps'][0]['before']==result.native['steps'][0]['after']
    assert result.status=='drift'


def test_a_real_old_format_load_crash_closes_with_its_own_same_file_regression(project):
    from checkrun import run_check
    fixture(project)
    legacy=json.dumps([dict(id='legacy',cond='ready',new=True)])
    project.file('fixtures/legacy.json',legacy)
    first=run_check(project.root,'--full','--json')
    assert first.code==1,first.out+first.err
    identifier=next(f['id'] for f in first.data['conflicts'] if f['kind']=='FILE CRASH')
    program=project.root/'program.py'
    repaired=PROGRAM.replace("        if not self.items[tool]['new']: raise Refusal('old stuck item was missed')\n",'')
    repaired=repaired.replace('            self.items=json.loads(Path(path).read_text())',"            data=json.loads(Path(path).read_text())\n            self.items={row['id']:{'cond':row['cond'],'new':row['new']} for row in data} if isinstance(data,list) else data")
    program.write_text(repaired)
    run=run_check(project.root,'--full','--json')
    assert run.code==0 and identifier in {f['id'] for f in run.data['closed']},run.out+run.err
    proof=core(project,run.data)['info']['native']['closures'][identifier]
    assert proof['regression']['passed'] is True
    assert (project.root/'fixtures/legacy.json').read_text()==legacy


def test_single_object_projection_does_not_change_the_original_binding(project):
    from flowguard.flow.samples import analyze
    fixture(project)
    path=project.root/'.flowguard/flow/tools.py'
    path.write_text(path.read_text().replace("TOOLS=m.objects('tool','T1','T2')","TOOLS=('T1',)").replace("slots=m.kinds['tool']","slots=tuple(field.obj for field in m.fields)"))
    loaded=load_model(path,project.root)
    binding=loaded.model.adapter_binding
    result=analyze(project.root,loaded)
    assert len(result['coverage']['starts'])==2
    assert loaded.model.adapter_binding is binding and binding.start=={} and binding.prefix==()


def test_unreadable_source_is_typed_unknown_without_mislabeling_the_sut(project,monkeypatch):
    from flowguard.flow import samples
    fixture(project)
    loaded=load_model(project.root/'.flowguard/flow/tools.py',project.root)
    original=samples.file_stamp
    def unavailable(path):
        if Path(path).suffix=='.json':raise PermissionError('injected actual filesystem read failure')
        return original(path)
    monkeypatch.setattr(samples,'file_stamp',unavailable)
    result=samples.analyze(project.root,loaded)
    assert result['coverage']['status']=='unknown' and not result['complete']
    assert any(row.get('status')=='unreadable' for row in result['coverage']['files'])
    assert not any(finding.kind=='FILE CRASH' for finding in result['findings'])


def test_actual_unmodeled_old_state_is_unknown_and_not_an_empty_pass(project):
    from checkrun import run_check
    fixture(project)
    (project.root/'program.py').write_text(PROGRAM.replace("        if not self.items[tool]['new']: raise Refusal('old stuck item was missed')\n",''))
    project.file('fixtures/extra.json',json.dumps({'unknown':dict(cond='unmodeled legacy state',new=False)}))
    run=run_check(project.root,'--full','--json')
    assert run.code==3 and not run.data['conflicts'],run.out+run.err
    saved=core(project,run.data)['info']['saved_samples']
    assert saved['status']=='unknown' and len(saved['files'])==3
    assert any('outside' in reason and 'domains' in reason for reason in saved['limits'])


def test_unsupported_object_relations_still_observe_the_real_file_load_crash(project):
    from checkrun import run_check
    fixture(project)
    path=project.root/'.flowguard/flow/tools.py'
    path.write_text(path.read_text().replace('SAMPLES',DECL).replace("MODEL=m","m.objects('other','O1','O2')\nMODEL=m"))
    project.file('fixtures/malformed.json','{actual broken old save')
    run=run_check(project.root,'--full','--json')
    assert run.code==1,run.out+run.err
    assert any(finding['kind']=='FILE CRASH' for finding in run.data['conflicts'])
    saved=core(project,run.data)['info']['saved_samples']
    assert saved['status']=='unknown' and saved['object_width'] is None and saved['loads']
    assert any('one declared object kind' in reason for reason in saved['limits'])


def test_failed_discovery_without_a_file_is_unknown_rather_than_unchecked(project,monkeypatch):
    from flowguard.flow import samples
    fixture(project)
    loaded=load_model(project.root/'.flowguard/flow/tools.py',project.root)
    def unavailable(*args,**kwargs):
        raise PermissionError('actual sample directory is unreadable')
    monkeypatch.setattr(samples.os,'walk',unavailable)
    result=samples.analyze(project.root,loaded)
    assert result['coverage']['status']=='unknown' and not result['complete']
    assert result['coverage']['files']==[] and 'unreadable' in result['coverage']['limits'][0]


def test_three_object_closure_cannot_claim_complete_single_pair_scope(project):
    from flowguard.flow.samples import _width
    from flowguard.flow import Model
    m=Model('three')
    objects=m.objects('item','A','B','C')
    m.field('ready',(False,True),True,over=objects)
    def predicate(state):
        return all(state['ready',obj] for obj in objects)
    m.always('all three objects are linked',predicate)
    width,limits=_width(m)
    assert width==2 and any('exceeds' in reason for reason in limits)


def test_setting_explanations_keep_the_actual_old_start(project):
    from flowguard.flow.checks import check_model
    path=project.flow('old_start', '''from flowguard.flow import Model,need
m=Model('old start')
m.setting('repair',False,vary=[True])
S=m.settings
m.field('phase',('fresh','old','done'),'fresh')
@m.action()
def repair(s):
    need(s['phase']=='fresh' and S['repair'])
    s['phase']='done'
m.reach('done',lambda s:s['phase']=='done')
MODEL=m
''')
    report=check_model(load_model(path,project.root),start=('old',))
    missing=next(finding for finding in report.findings if finding.kind=='NEVER REACHED' and finding.detail.get('rule')=='done')
    assert missing.detail['explained']==[]


def test_removed_original_saved_object_is_stale_scope_not_a_judgment_crash(project):
    import pytest
    from flowguard.flow.model import ModelError
    from flowguard.flow.samples import analyze,restore_start
    fixture(project)
    path=project.root/'.flowguard/flow/tools.py'
    result=analyze(project.root,load_model(path,project.root))
    context=next(origin for start in result['coverage']['starts'] for origin in start['origins']
                 if origin['path']=='fixtures/v0.json' and origin['ids']==['old0'])
    program=project.root/'program.py'
    program.write_text(PROGRAM.replace('    def tools(self): return list(self.items.keys())',
        "    def tools(self):\n        self.items.pop('old0',None)\n        return list(self.items.keys())"))
    with pytest.raises(ModelError,match='original saved object'):
        restore_start(project.root,path,context)


def test_three_object_relation_is_loaded_without_inventing_a_pair_check(project):
    from flowguard.flow.samples import analyze
    fixture(project)
    path=project.root/'.flowguard/flow/tools.py'
    source=path.read_text().replace("TOOLS=m.objects('tool','T1','T2')","TOOLS=m.objects('tool','T1','T2','T3')")
    source=source.replace("m.progress('every damaged", "m.always('three linked',lambda s:sum(s['cond',obj]=='repair' for obj in TOOLS)!=3)\nm.progress('every damaged")
    path.write_text(source)
    result=analyze(project.root,load_model(path,project.root))
    assert len(result['coverage']['loads'])==2 and result['coverage']['objects']==24
    assert result['coverage']['status']=='unknown' and not result['complete']
    assert result['coverage']['starts']==[] and result['native']==[]


def test_dict_held_three_object_rule_cannot_be_a_clean_unary_save_check(project):
    from flowguard.flow.samples import analyze
    from flowguard.flow.checks import check_model
    fixture(project)
    program=project.root/'program.py'
    program.write_text(PROGRAM.replace("('T1','T2')","('T1','T2','T3')").replace(
        "        if not self.items[tool]['new']: raise Refusal('old stuck item was missed')\n",''))
    path=project.root/'.flowguard/flow/tools.py'
    source=path.read_text().replace("TOOLS=m.objects('tool','T1','T2')", "TOOLS=m.objects('tool','T1','T2','T3')\nBY_NAME={t:t for t in TOOLS}")
    source=source.replace("m.progress('every damaged", "m.always('three damaged objects are forbidden',lambda s:sum(s['cond',t]=='repair' for t in BY_NAME.values())!=3)\nm.progress('every damaged")
    path.write_text(source)
    project.file('fixtures/v0.json',json.dumps({f'old{i}':dict(cond='repair',new=False) for i in range(3)}))
    loaded=load_model(path,project.root)
    full=check_model(loaded,start=('repair','repair','repair'))
    assert any(finding.kind=='BROKEN' for finding in full.findings)
    result=analyze(project.root,loaded)
    assert len(result['coverage']['loads'])==2
    assert result['coverage']['status']=='unknown' and not result['complete']
    assert any('exceeds' in reason for reason in result['coverage']['limits'])
    assert result['coverage']['starts']==[] and result['native']==[]


@pytest.mark.parametrize('kind',('keys','values','nested','set','frozenset'))
def test_builtin_collection_relations_keep_all_declared_ids(kind):
    from flowguard.flow import Model
    from flowguard.flow.samples import _width
    m=Model('collections');items=m.objects('item','A','B','C')
    m.field('ready',(False,True),True,over=items)
    if kind=='keys':data={item:0 for item in items};read=lambda:data.keys()
    elif kind=='values':data={index:item for index,item in enumerate(items)};read=lambda:data.values()
    elif kind=='nested':data={'nested':[tuple(items)]};read=lambda:data['nested'][0]
    elif kind=='set':data=set(items);read=lambda:data
    else:data=frozenset(items);read=lambda:data
    m.always('the three object relation',lambda state:sum(state['ready',obj] for obj in read())!=3)
    width,limits=_width(m)
    assert width==2 and any('exceeds' in reason for reason in limits)


def test_cyclic_and_custom_collection_metadata_stays_unknown_without_callbacks():
    from flowguard.flow import Model
    from flowguard.flow.samples import _width
    class Opaque(dict):
        def __iter__(self):raise AssertionError('custom iteration must not run')
        def items(self):raise AssertionError('custom lookup must not run')
        def __getattribute__(self,name):raise AssertionError('custom attribute access must not run')
    for kind in ('cyclic','custom'):
        m=Model(kind);items=m.objects('item','A','B');m.field('ready',(False,True),True,over=items)
        data=[] if kind=='cyclic' else Opaque(A='A',B='B')
        if kind=='cyclic':data.append(data)
        m.always('relation is not silently assumed unary',lambda state:data is not None)
        _,limits=_width(m)
        assert any('cyclic' in reason if kind=='cyclic' else 'opaque collection' in reason for reason in limits)


def test_readonly_model_settings_do_not_become_an_opaque_object_relation():
    from flowguard.flow import Model
    from flowguard.flow.samples import _width
    m=Model('settings');items=m.objects('item','A','B');m.field('ready',(False,True),True,over=items)
    m.setting('enabled',True);settings=m.settings
    m.reach('one object uses its normal setting',lambda state,obj:state['ready',obj] or settings['enabled'],over=items)
    assert _width(m)==(1,[])
