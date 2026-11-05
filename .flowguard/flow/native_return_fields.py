"""Selected return facts are per invocation; unsupported values remain explicit."""
from flowguard.flow import Model,need
m=Model('selected native return fields')
m.field('phase',('idle','reached','returned','raised'),'idle')
m.field('selected',(False,True),False)
m.field('facts',('absent','current','unknown'),'absent')
m.field('reason',('absent','current','unsupported','unavailable'),'absent')
@m.action(selected=(False,True))
def reach(s,selected):
    need(s['phase']=='idle')
    s['phase']='reached';s['selected']=selected
@m.action(value=('scalar','complex','missing','raised'))
def finish(s,value):
    need(s['phase']=='reached')
    s['phase']='raised' if value=='raised' else 'returned'
    s['facts']='absent' if not s['selected'] else 'current' if value=='scalar' else 'unknown'
    s['reason']='absent' if not s['selected'] else 'current' if value=='scalar' else 'unsupported' if value=='complex' else 'unavailable'
@m.action()
def next_invocation(s):
    need(s['phase'] in ('returned','raised'))
    s['phase']='idle';s['selected']=False;s['facts']='absent';s['reason']='absent'
m.always('unselected invocations expose no fields',lambda s:s['selected'] or s['facts']=='absent')
m.always('current fields require a completed selected invocation',lambda s:s['facts']!='current' or (s['selected'] and s['phase']=='returned'))
m.always('unknown facts retain their actual observation boundary',
         lambda s:s['facts']!='unknown' or s['reason'] in ('unsupported','unavailable'))
MODEL=m
