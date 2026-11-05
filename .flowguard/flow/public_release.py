"""The one public release route: flow gate, optional suite, then original-byte snapshot."""
from flowguard.flow import Model, need

m = Model('public release command', covers=['flowguard/__main__.py', 'flowguard/flow/release.py'])
m.field('phase', ('start', 'flow_ok', 'suite_ok', 'done', 'flow_failed', 'suite_failed', 'snapshot_failed'), 'start')
m.field('asked_suite', (False, True), False)
m.field('suite_ran', (False, True), False)
m.field('snapshotted', (False, True), False)

@m.action(shards=(False, True), passes=(False, True))
def check_flow(s, shards, passes):
    need(s['phase'] == 'start')
    s['asked_suite'] = shards
    s['phase'] = 'flow_ok' if passes else 'flow_failed'

@m.action(passes=(False, True))
def run_suite(s, passes):
    need(s['phase'] == 'flow_ok' and s['asked_suite'])
    s['suite_ran'] = True
    s['phase'] = 'suite_ok' if passes else 'suite_failed'

@m.action(passes=(False, True))
def snapshot_originals(s, passes):
    need(s['phase'] == 'suite_ok' or s['phase'] == 'flow_ok' and not s['asked_suite'])
    s['snapshotted'] = passes
    s['phase'] = 'done' if passes else 'snapshot_failed'

@m.action()
def next_invocation(s):
    need(s['phase'] in ('done', 'flow_failed', 'suite_failed', 'snapshot_failed'))
    s['phase'] = 'start'
    s['asked_suite'] = s['suite_ran'] = s['snapshotted'] = False

m.always('the suite is explicitly requested', lambda s: not s['suite_ran'] or s['asked_suite'])
m.always('pass preserves the original-byte boundary', lambda s: s['phase'] != 'done' or s['snapshotted'])
m.reach('flow checks without whole pytest', lambda s: s['phase'] == 'done' and not s['suite_ran'])
m.reach('whole suite follows the flow gate', lambda s: s['phase'] == 'done' and s['suite_ran'])
m.after('flow result determines the first gate', 'check_flow',
        lambda before, after, shards, passes: after['phase'] == ('flow_ok' if passes else 'flow_failed')
        and after['asked_suite'] == shards and not after['suite_ran'] and not after['snapshotted'])
m.after('the requested suite runs before its result is known', 'run_suite',
        lambda before, after, passes: after['suite_ran']
        and after['phase'] == ('suite_ok' if passes else 'suite_failed'))
m.after('snapshot result determines final success', 'snapshot_originals',
        lambda before, after, passes: after['snapshotted'] == passes
        and after['phase'] == ('done' if passes else 'snapshot_failed'))
m.after('a new invocation carries no previous pass', 'next_invocation',
        lambda before, after: after['phase'] == 'start' and not after['asked_suite']
        and not after['suite_ran'] and not after['snapshotted'])
m.only_when('the suite follows a successful flow check', 'run_suite',
            lambda before, passes: before['phase'] == 'flow_ok' and before['asked_suite'])
m.only_when('snapshot follows all requested checks', 'snapshot_originals',
            lambda before, passes: before['phase'] == 'suite_ok'
            or before['phase'] == 'flow_ok' and not before['asked_suite'])
m.only_when('only a finished invocation can restart', 'next_invocation',
            lambda before: before['phase'] in ('done', 'flow_failed', 'suite_failed', 'snapshot_failed'))
MODEL = m
