"""Saved data is parsed by the real native loader, never by model import."""
from flowguard.flow import Model,need
m=Model('saved sample coverage',covers=['flowguard/flow/samples.py','flowguard/flow/native_picture.py'])
m.field('phase',('idle','unchecked','loaded','crash','unknown','checked'),'idle')
m.field('source_kept',(False,True),False)
m.field('actual_load',(False,True),False)
m.field('oracle_input',(False,),False)
m.field('relation_known',(False,True),True)
m.field('view_start',('fresh','saved'),'fresh')
m.field('sut_replayed',(False,),False)
@m.action(result=('absent','loaded','crash','unknown'),relation_known=(False,True))
def load(s,result,relation_known):
    need(s['phase']=='idle')
    s['relation_known']=relation_known
    s['phase']='unchecked' if result=='absent' else 'unknown' if result=='loaded' and not relation_known else result
    s['source_kept']=result!='absent'
    s['actual_load']=result in ('loaded','crash')
@m.action()
def check(s):
    need(s['phase']=='loaded' and s['relation_known'])
    s['phase']='checked'
@m.action()
def show(s):
    need(s['phase'] in ('checked','crash'))
    s['view_start']='saved'
@m.action()
def next_sample(s):
    need(s['phase'] in ('unchecked','checked','crash','unknown'))
    s['phase']='idle';s['source_kept']=False;s['actual_load']=False;s['relation_known']=True;s['view_start']='fresh'
m.always('checked starts have an actual load and source',lambda s:s['phase']!='checked' or (s['actual_load'] and s['source_kept']))
m.always('a file crash retains its actual source',lambda s:s['phase']!='crash' or (s['actual_load'] and s['source_kept']))
m.always('expected model state is never a native construction input',lambda s:not s['oracle_input'])
m.always('checked starts need the actual declared object relation',lambda s:s['phase']!='checked' or s['relation_known'])
m.always('saved pictures use the actual observed start',lambda s:s['view_start']!='saved' or s['actual_load'] and s['source_kept'])
m.always('show never reruns the system',lambda s:not s['sut_replayed'])
MODEL=m
