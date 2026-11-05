"""Persistent sessions consume actual model/native/regression evidence."""
from flowguard.flow import Model, need
m = Model('persistent conflict sessions')
CASES = ('same_model_only', 'helper_unknown', 'weakened', 'capped', 'removed', 'native_and_regression', 'model_regression', 'constructor_output_fix', 'saved_prefix_omitted', 'owner_choice', 'provisional')
m.field('phase', ('open', 'held', 'closed'), 'open')
m.field('case', ('none', *CASES), 'none')
m.field('native', (False, True), False)
m.field('regression', (False, True), False)
m.field('model_only', (False, True), False)
@m.action(case=CASES)
def later_session(s, case):
    need(s['phase'] == 'open')
    s['case'] = case
    s['native'] = case in ('native_and_regression', 'constructor_output_fix')
    s['model_only'] = case == 'model_regression'
    s['regression'] = case in ('native_and_regression', 'constructor_output_fix', 'model_regression')
    s['phase'] = 'closed' if s['regression'] and (s['native'] or s['model_only']) else 'held'
@m.action()
def next_change(s):
    need(s['phase'] != 'open')
    s['phase'], s['case'], s['native'], s['regression'], s['model_only'] = 'open', 'none', False, False, False
m.always('model absence alone never closes code conflict', lambda s: s['phase'] != 'closed' or s['regression'] and (s['native'] or s['model_only']))
m.always('temporary decisions stay visible', lambda s: s['case'] != 'provisional' or s['phase'] == 'held')
m.reach('complete evidence can close', lambda s: s['phase'] == 'closed')
MODEL = m
