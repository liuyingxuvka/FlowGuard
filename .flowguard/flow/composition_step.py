"""Synchronous model calls stage writes until every participant accepts."""
from flowguard.flow import Model, need

m = Model('composition step', covers=['flowguard/flow/model.py', 'flowguard/flow/compose.py'])
m.field('phase', ('idle', 'guards', 'staged', 'committed', 'refused', 'owner_error', 'effect_error'), 'idle')
m.field('value', (0, 1, 2), 0)
m.field('before', (0, 1, 2), 0)
m.field('local_value', (0, 1, 2), 0)
m.field('peer_seen', (0, 1, 2), 0)

@m.action(owner_ok=(False, True))
def begin(s, owner_ok):
    need(s['phase'] == 'idle')
    s['before'] = s['value']
    s['local_value'] = s['value']
    s['peer_seen'] = s['value']
    s['phase'] = 'guards' if owner_ok else 'owner_error'

@m.action(value=(0, 1, 2))
def local_write(s, value):
    need(s['phase'] == 'guards')
    s['local_value'] = value

@m.action(result=('refused', 'effect_error', 'agreed'))
def participants(s, result):
    need(s['phase'] == 'guards')
    s['phase'] = 'staged' if result == 'agreed' else result

@m.action()
def commit(s):
    need(s['phase'] == 'staged')
    s['value'] = s['local_value']
    s['phase'] = 'committed'

@m.action()
def next_step(s):
    need(s['phase'] in ('committed', 'refused', 'owner_error', 'effect_error'))
    s['phase'] = 'idle'

m.always('guards and errors expose no partial writes', lambda s: s['phase'] not in
         ('guards', 'staged', 'refused', 'owner_error', 'effect_error') or s['value'] == s['before'])
m.always('a committed step applies the staged transition', lambda s:
         s['phase'] != 'committed' or s['value'] == s['local_value'])
m.always('other participants keep the joint prestate', lambda s:
         s['phase'] == 'idle' or s['peer_seen'] == s['before'])
m.reach('all participants can commit together', lambda s: s['phase'] == 'committed')
MODEL = m
