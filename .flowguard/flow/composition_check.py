"""Ordinary checks stay cheap; only the existing worker qualifies a full scope."""
from flowguard.flow import Model, need
m=Model('composition check', covers=['flowguard/flow/parts.py','flowguard/flow/diagram.py'])
m.field('phase', ('idle','ordinary','full','checked','ordinary_done','qualified','unknown'), 'idle')
m.field('full', (False,True), False)
m.field('expensive', (False,True), False)
@m.action(full=(False,True))
def prepare(s, full):
    need(s['phase']=='idle')
    s['full']=full
    s['phase']='full' if full else 'ordinary'
@m.action(complete=(False,True))
def check(s, complete):
    need(s['phase'] in ('ordinary','full'))
    s['phase']='checked' if complete else 'unknown'
@m.action(result=('qualified','unknown'))
def qualify(s, result):
    need(s['phase']=='checked' and s['full'])
    s['expensive']=True
    s['phase']=result
@m.action()
def ordinary_done(s):
    need(s['phase']=='checked' and not s['full'])
    s['phase']='ordinary_done'
@m.action()
def next_check(s):
    need(s['phase'] in ('ordinary_done','qualified','unknown'))
    s['phase']='idle'
    s['full']=False
    s['expensive']=False
m.always('ordinary checks never pay for full qualification', lambda s: s['full'] or not s['expensive'])
m.always('qualification is worker full work', lambda s: s['phase']!='qualified' or s['full'] and s['expensive'])
MODEL=m
