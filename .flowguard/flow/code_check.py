"""Command scheduling protocol, not a state graph inferred from pytest execution."""
from flowguard.flow import Model, need

m = Model('explicit recorded code checks', covers=['flowguard/flow/codeaudit.py', 'flowguard/flow/cli.py'])
m.field('phase', ('idle', 'running', 'recorded', 'stale'), 'idle')
m.field('selected', (False, True), False)
m.field('runs', (0, 1), 0)
m.field('failed', (False,True), False)
m.field('reused_failure', (False,True), False)

@m.action()
def ordinary_check(s):
    need(s['phase'] == 'idle' and not s['selected'] or s['phase'] == 'recorded' and s['failed'])
    if s['failed']:
        s['reused_failure'] = True

@m.action()
def select_tests(s):
    need(s['phase'] == 'idle')
    s['selected'], s['phase'], s['runs'] = True, 'running', 1

@m.action()
def wait_returns(s):
    need(s['phase'] == 'running')

@m.action(passed=(False,True))
def finish(s, passed):
    need(s['phase'] == 'running')
    s['phase'] = 'recorded'
    s['failed'] = not passed

@m.action()
def edit_source(s):
    need(s['phase'] == 'recorded')
    s['phase'] = 'stale'
    s['reused_failure'] = False

@m.action()
def status(s):
    need(s['phase'] in ('recorded', 'stale'))

@m.action()
def explicit_retest(s):
    need(s['phase'] == 'stale' and s['selected'])
    s['phase'] = 'running'

m.always('code capture requires explicit tests', lambda s: not s['runs'] or s['selected'])
m.always('resume reuses the same selected run', lambda s: s['runs'] <= 1)
m.reach('edited code waits for explicit retest', lambda s: s['phase'] == 'stale')
m.always('a reused current failure keeps its exact selected run', lambda s:
         not s['reused_failure'] or s['phase']=='recorded' and s['failed'] and s['runs']==1)
m.reach('ordinary checks can retain the known failed run', lambda s:s['reused_failure'])
MODEL = m
