"""Clean declarations stay small; actual conflict comparisons retain their evidence."""
from copy import deepcopy
import json

import pytest

from checkrun import run_check
from flowguard.flow import descriptors
from flowguard.flow.parts import PartContext, PartSpec, core_part
from flowguard.flow.project import cache_dir, read_conflicts


MODEL = '''from flowguard.flow import Model, need
m = Model('bounded')
m.field('phase', range(3), 0)
EXTRA_FIELDS
@m.action()
def advance(s):
    need(s['phase'] < 2, source='R1')
    s['phase'] += 1
m.terminal('phase', [2])
m.always('phase remains bounded', lambda s: s['phase'] >= 0, source='R1')
MODEL = m
'''


def setup(project, extra_fields=''):
    project.request('R1', 'The phase remains bounded and can advance to completion.')
    return project.flow('bounded', MODEL.replace('EXTRA_FIELDS', extra_fields))


def test_clean_three_state_model_does_not_evaluate_declared_cartesian_predicates(project, monkeypatch):
    path = setup(project, '\n'.join(f"m.field('unused_{i}', range(4), 0)" for i in range(6)))
    evaluated = []
    state = descriptors.State
    def count_state(*args, **kwargs):
        evaluated.append(None)
        return state(*args, **kwargs)
    monkeypatch.setattr(descriptors, 'State', count_state)
    core = core_part(PartContext(project.root, PartSpec('core', 'bounded'), path, cache_dir(project.root)))
    assert core.complete and core.info['reach']['states'] == 3
    assert not any(row['cls'] == 'conflict' for row in core.findings)
    assert not evaluated
    descriptor = core.info['descriptor']
    assert all(row['cases'] is None for row in descriptor['obligations'])
    assert descriptor['comparison_limits'] == ['finite comparison not evaluated for clean declaration']
    assert descriptor['scope']['coverage']['field:unused_5'] == ['0', '1', '2', '3']
    assert all(row['definition'] and row['sources'] and row['dependencies'] for row in descriptor['obligations'])
    checked = run_check(project.root, '--json')
    assert checked.code == 0 and checked.data['complete'], checked.out + checked.err
    assert (project.root / '.flowguard/conflicts.json').stat().st_size < 32_000


def test_current_clean_model_still_compares_full_retained_conflict_relations(project):
    path = setup(project)
    text = path.read_text().replace("s['phase'] >= 0", "s['phase'] == 0")
    project.flow('bounded', text)
    first = run_check(project.root, '--json')
    assert first.code == 1, first.out + first.err
    entry, = [row for row in read_conflicts(project.root)['conflicts'] if row['kind'] == 'BROKEN']
    baseline = deepcopy(entry['history']['baseline'])
    rule, = [row for row in baseline['obligations'] if row['kind'] == 'always']
    assert len(rule['cases']) == 3 and set(rule['cases'].values()) == {False, True}
    project.flow('bounded', text.replace("s['phase'] == 0", "s['phase'] <= 2"))
    weakened = run_check(project.root, '--json')
    assert weakened.code == 1, weakened.out + weakened.err
    saved = read_conflicts(project.root)
    retained, = [row for row in saved['conflicts'] if row['id'] == entry['id']]
    assert retained['history']['baseline'] == baseline
    assert 'sourced_obligation_weakened' in {row['code'] for row in retained['history']['latest']['reasons']}
    current, = [row for row in saved['models']['bounded']['observation']['obligations'] if row['kind'] == 'always']
    assert len(current['cases']) == 3 and set(current['cases'].values()) == {True}


def test_new_requested_rule_contradiction_has_full_comparison_tables(project):
    path = setup(project)
    project.request('R2', 'The phase must remain above one.')
    text = path.read_text().replace("s['phase'] >= 0", "s['phase'] < 1")
    text = text.replace('MODEL = m', "m.always('phase above one', lambda s: s['phase'] > 1, source='R2')\nMODEL = m")
    project.flow('bounded', text)
    checked = run_check(project.root, '--json')
    assert checked.code == 1, checked.out + checked.err
    entry, = [row for row in read_conflicts(project.root)['conflicts'] if row['kind'] == 'RULE CONTRADICTION']
    rules = [row for row in entry['history']['baseline']['obligations'] if row['kind'] == 'always']
    assert len(rules) == 2 and all(len(row['cases']) == 3 for row in rules)


def test_native_drift_from_clean_model_also_gets_full_comparison_evidence(project):
    from test_native_operation_closure import MODEL as NATIVE_MODEL, setup as setup_native
    project.request('R1', 'The counter must stay within its declared values.')
    setup_native(project, model=NATIVE_MODEL.replace('MODEL=m',
        "m.always('counter stays bounded', lambda s: s['n'] >= 0, source='R1')\nMODEL=m"))
    checked = run_check(project.root, '--json')
    assert checked.code == 1, checked.out + checked.err
    entry, = [row for row in read_conflicts(project.root)['conflicts'] if row['kind'] == 'MODEL DRIFT']
    rule, = [row for row in entry['history']['baseline']['obligations'] if row['kind'] == 'always']
    assert len(rule['cases']) == 2


@pytest.mark.parametrize('weaken', [False, True])
def test_new_route_only_conflict_keeps_actual_relations_for_repair_or_weakening(project, weaken):
    path = setup(project)
    alternative = '''@m.action(source='R1')
def alternative(s):
    need(s['phase'] < 2, source='R1')
    s['phase'] += 1
'''
    text = path.read_text().replace('@m.action()', "@m.action(source='R1')")
    text = text.replace('m.terminal', alternative + '\nm.terminal')
    project.flow('bounded', text)
    checked = run_check(project.root, '--json')
    assert checked.code == 1, checked.out + checked.err
    entry, = [row for row in read_conflicts(project.root)['conflicts'] if row['kind'] == 'DUPLICATE ROUTE']
    baseline = deepcopy(entry['history']['baseline'])
    assert entry['sources'] == ['R1']
    assert all(row['cases'] for row in baseline['obligations'])
    actual = json.loads((cache_dir(project.root) / 'parts' / (baseline['receipt'] + '.json')).read_text())
    assert actual['kind'] == 'routes' and actual['info']['descriptor']['obligations'] == baseline['obligations']
    replacement = alternative.replace("s['phase'] < 2", 'True' if weaken else "s['phase'] == 0")
    replacement = replacement.replace("s['phase'] += 1", "s['phase'] = min(2, s['phase'] + 2)" if weaken else "s['phase'] += 2")
    project.flow('bounded', text.replace(alternative, replacement))
    after = run_check(project.root, '--json')
    saved = read_conflicts(project.root)
    if weaken:
        assert after.code == 1, after.out + after.err
        retained, = [row for row in saved['conflicts'] if row['id'] == entry['id']]
        assert retained['history']['baseline'] == baseline
        assert {row['code'] for row in retained['history']['latest']['reasons']} == {'sourced_obligation_weakened'}
    else:
        assert after.code == 0, after.out + after.err
        closed, = [row for row in saved['closed'] if row['id'] == entry['id']]
        assert closed['history']['baseline'] == baseline
        assert closed['closure']['kind'] == 'model_corrected' and closed['closure']['regression']['passed']
