"""Native values retain aliases; source functions use public-prefix restoration."""
from flowguard.flow import Model, need
m=Model('native immutable values', covers=['flowguard/native/session.py:_Graph', 'flowguard/native/session.py:_Session.checkpoint'])
m.field('phase', ('new','observed','restored','unknown'), 'new', source='R15')
m.field('kind', ('pending','regex-text','regex-bytes','source-function','closure','opaque'), 'pending', source='R15')
for name in ('aliases','flags','copy_safe'):
    m.field(name, ('pending','preserved','unavailable'), 'pending', source='R15')
@m.action(kind=('regex-text','regex-bytes','source-function','closure','opaque'), source='R15')
def observe(s,kind):
    need(s['phase']=='new')
    s['kind']=kind
    supported=kind not in ('opaque','closure')
    s['aliases']='preserved' if supported else 'unavailable'
    s['flags']=s['copy_safe']='preserved' if kind.startswith('regex-') else 'unavailable'
    s['phase']='observed' if supported else 'unknown'
@m.action(method=('heap-copy','public-prefix'), source='R15')
def restore(s,method):
    need(s['phase']=='observed')
    s['phase']='unknown' if method=='heap-copy' and s['kind']=='source-function' else 'restored'
m.terminal('phase', ('restored','unknown'), source='R15')
for name in ('aliases','flags','copy_safe'):
    m.terminal(name, ('preserved','unavailable'), source='R15')
m.always('supported immutable checkpoints retain aliases and flags',lambda s:
         not s['kind'].startswith('regex-') or s['phase'] not in ('observed','restored') or all(s[key]=='preserved' for key in ('aliases','flags','copy_safe')),source='R15')
m.always('opaque values and business closures remain unknown',lambda s:s['kind'] not in ('opaque','closure') or s['phase']=='unknown',source='R15')
m.always('function references never authorize a shared heap checkpoint',lambda s:
         s['kind']!='source-function' or s['copy_safe']=='unavailable',source='R15')
m.reach('source function references restore through their public prefix',lambda s:
        s['kind']=='source-function' and s['phase']=='restored',source='R15')
m.reach('a heap-copy request still refuses a shared source function',lambda s:
        s['kind']=='source-function' and s['phase']=='unknown',source='R15')
MODEL=m
