"""Composition through the real existing worker, store, picture and full parts."""
import json
import subprocess

from checkrun import command, env, run_check
from flowguard.flow.explore import Bounds
from flowguard.flow.model import load_model
from flowguard.flow.mutate import guard_mutants, run_mutants
from flowguard.flow.parts import PartContext, PartSpec, part_digest, run_part
from flowguard.flow.project import file_digest
from flowguard.flow.routes import route_checks


def joint(project, *, standalone=False, slow=False):
    project.request('Rremove', 'Removing a tool ends its availability.')
    project.request('Ruse', 'A removed tool must never be used.')
    project.file('_stock.py', '''
        from flowguard.flow import Model, need
        stock=Model('stock')
        tools=stock.objects('tool','T1')
        stock.field('exists',(False,True),True,over=tools,source='Rremove')
        stock.terminal('exists',(False,),source='Rremove')
        @stock.action(t=tools,source='Rremove')
        def remove(s,t):
            need(s['exists',t],source='Rremove')
            s['exists',t]=False
    ''')
    project.file('_use.py', '''
        from flowguard.flow import Model
        from _stock import stock,tools
        use=Model('use')
        exists=use.foreign(stock,'exists')
        use.field('used',(False,True),False,over=tools,source='Ruse')
        use.terminal('used',(True,),source='Ruse')
        @use.action(t=tools,source='Ruse')
        def use_tool(s,t):
            s['used',t]=True
        use.always('no removed tool is used',lambda s:all(not s['used',t] or exists(s,t) for t in tools),source='Ruse')
    ''')
    if slow:
        path=project.root/'_use.py'
        path.write_text(path.read_text().replace("s['used',t]=True", "__import__('time').sleep(.1)\n    s['used',t]=True"))
    return project.flow('joint', "from _use import use\nfrom _stock import stock\n" +
                        ('MODEL=use\n' if standalone else
                         "from flowguard.flow.compose import compose\nMODEL=compose('joint',stock,use,kind='tool')\n"))


def test_actual_check_and_show_keep_two_sources_and_original_input_receipts(project):
    joint(project)
    checked=run_check(project.root,'--json')
    assert checked.code==1, checked.out+checked.err
    broken=[f for f in checked.data['conflicts'] if f['kind']=='BROKEN']
    assert len(broken)==1 and set(broken[0]['sources'])=={'Rremove','Ruse'}
    summary=checked.data['models']['joint']['composition']
    assert summary['objects']=={'tool':1} and summary['projection']['status'].startswith('not run')
    assert summary['foreign'][0]['mode']=='owner model'
    record=json.loads((project.root/'.flowguard/conflicts.json').read_text())
    assert any(f['id']==broken[0]['id'] for f in record['conflicts'])
    manifest=project.root/'.flowguard/cache/flow/manifests'
    assert '_stock.py' in '\n'.join(p.read_text() for p in manifest.rglob('*.json'))
    shown=subprocess.run(command('show','joint','--json'),cwd=project.root,env=env(),capture_output=True,text=True,timeout=30)
    assert shown.returncode==0, shown.stdout+shown.stderr
    picture=json.loads(shown.stdout)['pictures'][0]
    assert picture['subject_id']==broken[0]['id']
    assert picture['composition']['ownership'] and picture['foreign'][0]['mode']=='owner model'
    assert picture['drawn']
    source=project.root/'_stock.py'
    source.write_text(source.read_text()+'\n# owner source changed\n')
    refreshed=run_check(project.root,'--json')
    assert not any(p['cached'] for p in refreshed.data['parts'])


def test_standalone_component_discloses_its_fixed_owner_start(project):
    joint(project,standalone=True)
    checked=run_check(project.root,'--json')
    assert checked.code==0, checked.out+checked.err
    assert checked.data['models']['joint']['composition'] is None
    assert checked.data['models']['joint']['foreign']==[{'model':'use','owner':'stock','field':'exists','mode':'fixed at owner start'}]


def test_imported_guard_authority_is_checked_even_when_the_guard_never_refuses(project):
    joint(project)
    source=project.root/'_stock.py'
    source.write_text(source.read_text().replace("need(s['exists',t],source='Rremove')",
                     "need(True,source='Rmissing')\n    need(s['exists',t],source='Rremove')"))
    checked=run_check(project.root,'--json')
    assert any(f['kind']=='SOURCE' and 'Rmissing' in f['text'] for f in checked.data['warnings']), checked.out+checked.err


def test_plain_core_never_invokes_the_declared_extra_object_builder(project):
    path=project.flow('plain','''
        from flowguard.flow import Model
        from flowguard.flow.compose import compose
        a=Model('a')
        tools=a.objects('tool','T1')
        a.field('ready',(False,True),False,over=tools)
        @a.action(t=tools)
        def flip(s,t):
            s['ready',t]=not s['ready',t]
        def forbidden():
            raise AssertionError('ordinary check invoked full qualification')
        MODEL=compose('plain',a,kind='tool',one_more=forbidden)
    ''')
    result=run_part(PartContext(project.root,PartSpec('core','plain'),path,project.root/'cache'))
    assert result.complete and not result.findings
    assert result.info['composition']['one_more']['status'].startswith('not run')


FULL='''
from flowguard.flow import Model
from flowguard.flow.compose import compose
def build(n):
    a=Model('a')
    tools=a.objects('tool',*('T'+str(i+1) for i in range(n)))
    a.field('active',(False,True),False,over=tools,source='Ractive')
    @a.action(t=tools,source='Ractive')
    def flip(s,t):
        s['active',t]=not s['active',t]
    RULE
    telemetry=Model('telemetry')
    telemetry.field('ping',(False,True),False)
    @telemetry.action()
    def ping(s):
        s['ping']=not s['ping']
    return compose('full',a,telemetry,kind='tool',one_more=lambda:build(n+1))
MODEL=build(2)
'''


def test_full_cli_runs_actual_projection_and_probe_but_keeps_original_store_scope(project):
    project.request('Ractive','Tools can independently be activated or deactivated.')
    project.flow('full',FULL.replace('RULE',''))
    checked=run_check(project.root,'--full','--json')
    assert checked.code==0 and checked.data['complete'], checked.out+checked.err
    summary=checked.data['models']['full']['composition']
    assert summary['projection']['verified'] and summary['projection']['fields_before']==3
    assert summary['projection']['fields_after']==2
    assert summary['one_more']['complete'] and summary['one_more']['changed'] is False
    assert summary['symmetry']['used'] and summary['symmetry']['verified']
    assert summary['symmetry']['states_reduced'] < summary['symmetry']['states_unreduced']
    assert checked.data['models']['full']['states']==8
    record=json.loads((project.root/'.flowguard/conflicts.json').read_text())
    assert 'field:ping' in record['models']['full']['observation']['scope']['coverage']


def test_a_new_third_object_conflict_is_exposed_as_an_unsettled_bound(project):
    project.request('Ractive','At most two tools may be active at once.')
    project.flow('full',FULL.replace('RULE',"a.always('capacity',lambda s:sum(s.values())<=2,source='Ractive')"))
    checked=run_check(project.root,'--full','--json')
    assert checked.code==3 and not checked.data['complete'], checked.out+checked.err
    probe=checked.data['models']['full']['composition']['one_more']
    assert probe['complete'] and probe['changed']
    assert any(f['kind']=='BROKEN' and f['path'] for f in probe['findings'])
    assert checked.data['unknown']==['full']


def routed(project):
    project.request('Rmain','The main finish operation requires free mode.')
    project.request('Ralt','The alternate route uses busy mode.')
    project.file('_primary.py','''
        from flowguard.flow import Model,need
        p=Model('primary')
        tools=p.objects('tool','T1')
        p.field('done',(False,True),False,over=tools)
        p.field('busy',(False,True),False)
        p.terminal('done',(True,))
        @p.action()
        def change_mode(s):
            s['busy']=not s['busy']
        def normalize(s,t):
            if s['done',t]:
                return 1
            return 1
        @p.action(t=tools,source='Rmain')
        def finish(s,t):
            need(not s['busy'],'main free',source='Rmain')
            need(not s['done',t],'unfinished')
            need(True,'redundant',source='Rmain')
            normalize(s,t)
            s['done',t]=True
        @p.action(t=tools,source='Ralt')
        def alternate(s,t):
            need(s['busy'],'alternate busy',source='Ralt')
            need(not s['done',t],'unfinished')
            s['done',t]=True
        p.only_when('main only free','finish',lambda s,t:not s['busy'],source='Rmain')
        p.only_when('alternate only busy','alternate',lambda s,t:s['busy'],source='Ralt')
    ''')
    return project.flow('routed','''
        from _primary import p
        from flowguard.flow import Model
        from flowguard.flow.compose import compose
        audit=Model('audit')
        audit.field('logged',(False,True),False)
        @audit.action()
        def log(s):
            s['logged']=not s['logged']
        MODEL=compose('routed',p,audit,kind='tool')
    ''')


def test_imported_original_functions_drive_branch_routes_and_guard_mutation(project):
    path=routed(project)
    loaded,graph,routes=route_checks(path,project.root,Bounds())
    assert routes.complete
    fallback=[f for f in routes.findings if f.kind=='FALLBACK ROUTE']
    assert fallback and set(fallback[0].sources)=={'Rmain','Ralt'}
    assert any(f.kind=='SAME-RESULT BRANCH' and f.detail['file']=='_primary.py' for f in routes.findings)
    assert any(f.kind=='DEAD GUARD' and f.detail['file']=='_primary.py' for f in routes.findings)
    mutations=run_mutants(load_model(path,project.root),Bounds())
    assert mutations.complete
    assert any(o['op']=='drop guard' and '_primary.py' in o['what'] and o['outcome']=='caught'
               and any('BROKEN' in reason for reason in o['by']) for o in mutations.outcomes)
    core=run_part(PartContext(project.root,PartSpec('core','routed',(('finite_comparison',True),)),path,project.root/'cache'))
    guards=[row for row in core.info['descriptor']['obligations'] if row['kind']=='guard']
    assert any(row['sources']==['Rmain'] and row['cases'] for row in guards)
    actual=run_check(project.root,'--full','--json')
    assert actual.code==1, actual.out+actual.err
    assert any(f['kind']=='FALLBACK ROUTE' and f['path'] and set(f['sources'])=={'Rmain','Ralt'}
               for f in actual.data['conflicts'])


def test_real_worker_wait_and_resume_keeps_composed_conflict_scope(project):
    joint(project,slow=True)
    first=run_check(project.root,'--json','--wait','0')
    assert first.code==4 and first.data['running'], first.out+first.err
    resumed=run_check(project.root,'--json','--wait','30')
    assert resumed.code==1 and resumed.data['running'] is None, resumed.out+resumed.err
    assert any(f['kind']=='BROKEN' for f in resumed.data['conflicts'])


def test_worker_only_builder_import_is_part_of_the_existing_input_receipt(project):
    project.request('Ractive','Tools can independently be activated or deactivated.')
    project.file('late_parts.py','def next_bound(build,n):\n    return build(n+1)\n')
    path=project.flow('full',FULL.replace('RULE','').replace('one_more=lambda:build(n+1)',
                      "one_more=lambda:__import__('late_parts').next_bound(build,n)"))
    spec=PartSpec('core','full',(('verify_symmetry',True),))
    result=run_part(PartContext(project.root,spec,path,project.root/'cache'))
    assert result.complete and 'late_parts.py' in result.reads
    assert result.info['descriptor']['inputs']['late_parts.py']['sha256']==file_digest(project.root,'late_parts.py')
    assert result.digest==part_digest(project.root,spec,result.reads)


def test_broken_late_helper_is_repairable_and_remains_in_the_input_manifest(project):
    project.request('Ractive','Tools can independently be activated or deactivated.')
    helper=project.file('late_parts.py','this is not valid Python:\n')
    path=project.flow('full',FULL.replace('RULE','').replace('one_more=lambda:build(n+1)',
                      "one_more=lambda:__import__('late_parts').next_bound(build,n)"))
    spec=PartSpec('core','full',(('verify_symmetry',True),))
    broken=run_part(PartContext(project.root,spec,path,project.root/'cache'))
    assert 'late_parts.py' in broken.reads and broken.findings[0]['kind']=='MODEL ERROR'
    helper.write_text('def next_bound(build,n):\n    return build(n+1)\n')
    repaired=run_part(PartContext(project.root,spec,path,project.root/'cache'))
    assert repaired.complete and repaired.digest!=broken.digest


def test_edit_during_full_analysis_cannot_stamp_old_observation_with_new_source(project):
    project.request('Ractive','Tools can independently be activated or deactivated.')
    text=FULL.replace('RULE','').replace('one_more=lambda:build(n+1)','one_more=lambda:next_bound(n+1)')
    text=text.replace('MODEL=build(2)', '''def next_bound(n):
    from pathlib import Path
    path=Path(__file__)
    path.write_text(path.read_text()+'\\n# edit while qualification is running\\n')
    return build(n)
MODEL=build(2)''')
    path=project.flow('full',text)
    before=file_digest(project.root,'.flowguard/flow/full.py')
    spec=PartSpec('core','full',(('verify_symmetry',True),))
    result=run_part(PartContext(project.root,spec,path,project.root/'cache'))
    assert result.complete
    assert file_digest(project.root,'.flowguard/flow/full.py')!=before
    assert result.info['descriptor']['inputs']['.flowguard/flow/full.py']['sha256']==before
    assert result.digest!=part_digest(project.root,spec,result.reads)


def test_top_level_binding_checks_actual_program_and_component_binding_stays_model_only(project):
    path=joint(project)
    project.file('app.py','''
        class Refusal(Exception): pass
        class Program:
            def __init__(self):
                self.exists=True
                self.used=False
            def remove(self,t):
                if not self.exists: raise Refusal('refused')
                self.exists=False
            def use_tool(self,t):
                self.used=True
    ''')
    path.write_text(path.read_text()+'''
from flowguard.flow.adapter import fields
from _stock import tools
MODEL.bind_adapter({'system':'app:Program','classes':['app:Program'],'refusal':['app:Refusal']},
    state=lambda snapshot:{(field,t):fields(snapshot,names=(field,))[field]
                           for field in ('exists','used') for t in tools},
    operations={'stock.remove':'remove','use.use_tool':'use_tool'})
''')
    actual=run_check(project.root,'--json')
    assert actual.code==1, actual.out+actual.err
    record=json.loads((project.root/'.flowguard/conflicts.json').read_text())
    broken=next(f for f in record['conflicts'] if f['kind']=='BROKEN')
    assert broken['native_confirmation']['status']=='confirmed'
    assert actual.data['models']['joint']['composition']['native']['top_level_binding']
    app=project.root/'app.py'
    app.write_text(app.read_text().replace('self.used=True','self.used=False'))
    changed=run_check(project.root,'--json')
    assert any(f['kind']=='MODEL DRIFT' for f in changed.data['conflicts']), changed.out+changed.err
    path.write_text(path.read_text().split('from flowguard.flow.adapter import fields')[0]+'''
from flowguard.flow.adapter import fields
from _stock import tools
stock.bind_adapter({'system':'app:Program','classes':['app:Program']},
    state=lambda snapshot:{('exists',t):fields(snapshot,names=('exists',))['exists'] for t in tools},
    operations={'remove':'remove'})
''')
    current=run_part(PartContext(project.root,PartSpec('core','joint'),path,project.root/'cache'))
    assert current.info['native']['status']=='model-only'
    assert current.info['composition']['native']['component_bindings']==['stock']
    assert not current.info['composition']['native']['top_level_binding']


def test_sequential_component_updates_match_actual_native_code(project):
    project.file('program.py','''class Refusal(Exception): pass
class Program:
    def __init__(self): self.n=0
    def update(self):
        if self.n: raise Refusal('already updated')
        self.n+=1
        self.n+=1
''')
    path=project.flow('counter','''from flowguard.flow import Model,need
from flowguard.flow.compose import compose
from flowguard.flow.adapter import fields
a=Model('component',covers=['program.py:Program.update'])
ITEMS=a.objects('item','I1')
a.field('n',(0,1,2),0,over=ITEMS)
a.terminal('n',(2,))
@a.action(i=ITEMS)
def update(s,i):
    need(s['n',i]==0)
    s['n',i]+=1
    s['n',i]+=1
a.reach('both updates remain visible',lambda s:all(s['n',i]==2 for i in ITEMS))
MODEL=compose('counter',a,kind='item')
MODEL.bind_adapter({'system':'program:Program','classes':['program:Program'],'refusal':['program:Refusal']},
    state=lambda snapshot:{('n',i):fields(snapshot,names=('n',))['n'] for i in ITEMS},
    operations={'component.update':'update'},dispatch=lambda value:{'name':'update'})
''')
    result=run_part(PartContext(project.root,PartSpec('core','counter'),path,project.root/'cache'))
    assert result.complete and not any(finding['cls'] in {'conflict','error'} for finding in result.findings)
    assert result.info['native']['status']=='conformant'
    runs=[check['native'] for check in result.info['native']['checks'].values() if check['native']['steps']]
    assert any(run['steps'][0]['outcome']=='success' for run in runs)


def test_same_named_feature_guards_in_one_file_keep_their_own_action_sources(project):
    project.request('Rfirst','The first feature accepts only unready tools.')
    project.request('Rsecond','The second feature accepts only unready tools.')
    path=project.flow('shared','''
        from flowguard.flow import Model,need
        from flowguard.flow.compose import compose
        a=Model('a')
        tools=a.objects('tool','T1')
        a.field('ready',(False,True),False,over=tools)
        @a.action(t=tools,source='Rfirst')
        def ready(s,t):
            need(not s['ready',t],'first guard')
            s['ready',t]=True
        b=Model('b')
        b.objects('tool','T1')
        b.field('ready',(False,True),False,over=tools)
        @b.action(t=tools,source='Rsecond')
        def ready(s,t):
            need(not s['ready',t],'second guard')
            s['ready',t]=True
        MODEL=compose('shared',a,b,kind='tool',features=True,owners={'ready':a})
    ''')
    mutants=guard_mutants(load_model(path,project.root).model)
    assert next(m.sources for m in mutants if 'first guard' in m.what)==('Rfirst',)
    assert next(m.sources for m in mutants if 'second guard' in m.what)==('Rsecond',)
    checked=run_part(PartContext(project.root,PartSpec('core','shared'),path,project.root/'cache'))
    operation=next(row for row in checked.info['descriptor']['obligations'] if row['kind']=='operation')
    assert operation['sources']==['Rfirst','Rsecond']
