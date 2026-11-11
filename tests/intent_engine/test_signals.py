"""Human-readable views preserve uncertainty, locations and bounded output."""
from contextlib import closing

from flowguard.intent import differences as D, signals
from flowguard.structure import build
from tests.intent_engine.test_anchor_differences import compare, original_flag, unintended_flag


def available(stock, reserved):
    return stock > reserved


def too_available(stock, reserved):
    return stock >= reserved


def test_multifield_bounds_form_readable_intervals_and_keep_boolean_identity():
    _, report = compare(original_flag, unintended_flag, {'days': int, 'active': bool})
    regions = {row['region'] for row in report['changes']}
    assert 'days=4–7，active=F' in regions
    assert any('active=T' in label for label in regions)
    assert not any('not (' in label for label in regions)


def test_relational_boundary_stays_a_relation_between_inputs():
    _, report = compare(available, too_available, {'stock': int, 'reserved': int})
    assert report['changed'] == 1
    assert report['changes'][0]['region'] in ('stock=reserved', 'reserved=stock')


def test_tuple_readings_print_interval_minimal_example_and_exact_cause():
    item = dict(name='STANDING', file='shop/policy.py', line=8, comparison_status='ok', complete=True,
                rows=[({'days': day}, day <= 7) for day in range(12)],
                changed=[({'days': day}, False, True) for day in (7, 6, 4, 5)],
                cause=dict(name='GRACE_DAYS', before=3, after=7, file='shop/policy.py', line=1))
    lines = signals.render(dict(items=[item], source_changed=True)).splitlines()
    assert len(lines) == 3
    assert 'days=4–7' in lines[1] and 'example: days=4' in lines[1]
    assert '; function result False → True(example: ' in lines[1]
    assert lines[2] == 'cause: GRACE_DAYS 3 → 7（shop/policy.py:1）'


def test_correlated_or_disconnected_samples_do_not_become_a_cartesian_interval():
    for inputs in ([{'x': 4}, {'x': 6}], [{'x': 0, 'y': 1}, {'x': 1, 'y': 0}]):
        text = signals.render(dict(name='point', rows=[(row, False) for row in inputs],
                                   changed=[(row, False, True) for row in inputs], comparison_status='ok'))
        assert 'x=4–6' not in text and 'x=0–1，y=0–1' not in text


def test_path_changes_use_named_order_and_quiet_runs_print_nothing():
    report = dict(items=[], paths=[dict(test='test_release', before=['入口', '保存', '发布'], after=['入口', '发布'])])
    assert signals.render(report) == 'path test_release：入口 → 保存 → 发布 became 入口 → 发布'
    assert signals.render(dict(source_changed=False, changes=[], complete=True, total=0, changed=0)) == ''
    assert signals.render(dict(source_changed=True, changes=[], complete=True, total=12, changed=0)) == 'total 12 classes，changed 0 classes'


def test_old_code_unavailable_never_becomes_a_verified_zero_change():
    text = signals.render(dict(name='check', comparison_status='unavailable', comparison_reasons=['旧函数不可读取'],
                               status='ok', rows=[({'x': 1}, True)], changed=[]))
    assert 'comparison incomplete' in text and 'uncovered: 旧函数不可读取' in text
    assert 'total 1 classes，changed 0 classes' not in text


def test_red_constraints_cannot_be_crowded_out_by_information():
    report = dict(red=['违反规矩：days=4，出处：“最多三天。”'],
                  items=[dict(name='x'*200, total=10, changed=0, complete=True) for _ in range(20)],
                  leads=['more information'] * 10)
    lines = signals.render(report, limit=100).splitlines()
    assert lines[0] == 'red: 违反规矩：days=4，出处：“最多三天。”'
    assert len(lines) <= 10 and all(len(line) <= 100 for line in lines)
    crowded = signals.render(dict(red=[f'违反 {i}' for i in range(20)], items=[])).splitlines()
    assert len(crowded) == 10 and 'plus 11 constraint violations' in crowded[-1]


def test_same_name_disagreement_is_red_but_source_copies_are_only_leads():
    report = dict(comparison=True, same_name=True, status='red', complete=True, total=1, changed=1,
                  changes=[dict(anchor='STANDING', region='days=4–7', witness={'days': '4'},
                                before='F', after='T', before_target='policy:one', after_target='preview:two')])
    text = signals.render(report)
    assert text.startswith('red same-name anchor STANDING') and 'policy:one ↔ preview:two' in text
    assert len(text.splitlines()) <= 3


def test_same_name_lines_name_each_copy_where_it_first_differs_and_keep_it_apart_from_the_owner():
    # Round 22 F1, second review: only the first input where a copy differed was reported.
    inputs = [('days=3', [('a', True), ('b', True), ('c', False)]),
              ('days=4', [('a', False), ('b', True), ('c', False)]),
              ('days=5', [('a', False), ('b', True), ('c', False)]),
              ('days=6', [('b', True), ('c', True)])]                 # the owner has no answer here
    lines = signals.copy_lines(inputs, lambda x, y: x == y, str, owner='a', total=3)
    assert [(where, text, step) for where, text, step, _ in lines] == [
        ('days=3', '3 copies: 1 copies return True (reference a), 1 copies return False (c), plus 1 copies differ from the reference on other inputs: b (days=4)', 'make c agree with the reference'),
        ('days=4', '3 copies: 1 copies return False (reference a), 1 copies return True (b), plus 1 copies differ from the reference on other inputs: c (days=3)', 'make b agree with the reference')]
    assert signals.copy_red('LIMIT', lines[:1]) == ('same-name anchor LIMIT：days=3，3 copies: 1 copies return True (reference a), 1 copies return False (c), plus 1 copies differ from the reference on other inputs: b (days=4) -> make c agree with the reference; if intentionally different, use different anchor names and declare distinct')
    # Without an owner no copy is the reference: a line is kept where it first shows two copies that differ.
    lines = signals.copy_lines(inputs, lambda x, y: x == y, str, total=3)
    assert [(where, text, step) for where, text, step, _ in lines] == [
        ('days=3', '3 copies: 2 copies return True (a, b), 1 copies return False (c)', 'first decide which copy is correct, then make the remaining copies agree with it'),
        ('days=4', '3 copies: 2 copies return False (a, c), 1 copies return True (b)', 'first decide which copy is correct, then make the remaining copies agree with it')]
    assert lines[1][3] == {frozenset('ab'), frozenset('bc')}
    assert signals.copy_lines(inputs[2:3], lambda x, y: x == y, str, owner='a', total=3)[0][1] == \
        '3 copies: 2 copies return False (reference a, c), 1 copies return True (b)'


def test_demo_eight_lists_every_old_value_site_whatever_its_field_name(tmp_path):
    """Round 20 removed the shared-field-word filter and the five-location cap of this lead."""
    source = '''GRACE_DAYS=21
LIMITS=(14, 30)
def owner(days):
    return days <= GRACE_DAYS
def preview(days):
    return days <= 14
def renewal(overdue_days):
    return overdue_days <= 14
def standing(days):
    return days <= LIMITS[0]
'''
    for name in ('booking', 'delivery'):
        source += '\ndef '+name+'(days):\n'
        source += ''.join(f'    work_{number} = {number}\n' for number in range(20))
        source += '    if days <= 14:\n        return "grace"\n'
        source += ''.join(f'    later_{number} = {number}\n' for number in range(20))
        source += '    return "expired"\n'
    # A field named nothing like `days` is listed too: without the field-word filter `amount <= 14` is a site.
    source += '\ndef unrelated(amount):\n    return amount <= 14\n'
    (tmp_path/'policy.py').write_text(source, encoding='utf-8')
    change = dict(before=14, after=21, target='policy:owner', identity='policy:GRACE_DAYS')
    lines = source.splitlines()
    # Each site's line is the comparison that still holds the old value, inside its own function.
    expected = {'policy:preview': 'return days <= 14', 'policy:renewal': 'return overdue_days <= 14',
                'policy:standing': 'return days <= LIMITS[0]', 'policy:booking': 'if days <= 14:',
                'policy:delivery': 'if days <= 14:', 'policy:unrelated': 'return amount <= 14'}
    where = {}
    for target, text in expected.items():
        start = next(number for number, line in enumerate(lines) if line.startswith(f'def {target.partition(":")[2]}('))
        where[target] = next(number for number, line in enumerate(lines) if number > start and line.strip() == text) + 1
    with closing(build(tmp_path)) as graph:
        report = signals.stale_copies(graph, [change])
        assert report['kind'] == 'lead' and report['total'] == 6
        assert {row['target']: row['line'] for row in report['locations']} == where, report['locations']
        assert all(row['file'] == 'policy.py' for row in report['locations'])
        assert {row['target'] for row in report['locations'] if row['big']} == {'policy:booking', 'policy:delivery'}
        text = signals.render(dict(items=[], leads=[report]))
        assert 'old values 14 remain in 6 decisions' in text and len(text.splitlines()) == 1
        assert all(f"{row['file']}:{row['line']}" in text for row in report['locations'])
        assert '# flowguard: same NAME ref' in text and '…' not in text


def test_successful_comparison_grid_is_not_a_claim_of_complete_partition():
    text = signals.render(dict(name='point', comparison_status='ok', status='ok',
                               rows=[({'x': 1}, True)], changed=[],
                               reasons=['comparison grid is not a proof of partition completeness'],
                               comparison_reasons=[]))
    assert 'candidate classes: 1; compared: 1; comparison incomplete; proven changed classes: 0' in text
    assert 'not a proof of partition completeness' in text
    assert 'total 1 classes，changed 0 classes' not in text


def test_constraint_red_remains_visible_without_source_changes():
    text = signals.render(dict(source_changed=False, items=[dict(status='red', name='rule',
                                red=['例：days=4；出处：“最多三天。”'], changes=[], changed=0)]))
    assert text.startswith('red: 例：days=4；出处：“最多三天。”')


def test_explicit_comparison_does_not_invent_same_named_anchors():
    report = dict(comparison=True, status='red', complete=True, total=1, changed=1,
                  changes=[dict(anchor='other', region='days=4–7', witness={'days': '4'}, before='F', after='T')])
    text = signals.render(report)
    assert text.startswith('red comparison ') and 'same-name anchor' not in text


def test_readable_labels_do_not_mutate_the_source_constant_environment():
    import ast
    from flowguard.intent import cells as C
    env = {'GRACE': 7}
    kinds = {'days': C.kind_of(int)}
    assert signals.class_label([('days <= GRACE', None, env)], [True], kinds, {'days': 4}) == 'days≤7'
    assert env == {'GRACE': 7}


def _compared(number, changed=None):
    item = dict(name=f'K{number}', file='knobs.py', line=2 + 4 * number, status='ok', comparison_status='ok',
                complete=True, total=2, changed=0, changes=[])
    if changed:
        item.update(total=3, changed=1, changes=[dict(region='n=2–16', inputs={'n': 2}, before='T', after='F')],
                    cause=dict(name=f'K{number} 的常量', before=17, after=2, file='knobs.py', line=3 + 4 * number))
    return item


def test_an_explicit_comparison_lists_changes_first_and_counts_unchanged_points_apart():
    session = dict(session=True, baseline='a' * 40, baseline_kind='base', source_changed=True, comparison_requested=True)
    lines = signals.render(dict(session, items=[_compared(number) for number in range(13)])).splitlines()
    assert lines[0] == 'FlowGuard（since --flowguard-base aaaaaaa）' and len(lines) == 11, lines
    assert lines[1] == 'compared: K0（knobs.py:2）total 2 classes，changed 0 classes' and all(line.startswith('compared: ') for line in lines[1:]), lines
    assert lines[-1] == 'compared: plus 4 unchanged items: K9、K10、K11、K12', lines
    # One change among unchanged points: its line is printed whole, before them, never in an overflow.
    lines = signals.render(dict(session, items=[*(_compared(number) for number in range(12)), _compared(12, True)])).splitlines()
    assert lines[1] == ('changed: K12（knobs.py:50）total 3 classes，changed 1 classes：n=2–16; function result T → F(example: n=2）  cause: K12 的常量 17 → 2（knobs.py:51）'), lines
    assert not any(line.startswith('changed: plus ') for line in lines) and len(lines) == 11, lines
    assert lines[2:-1] == [f'compared: K{number}（knobs.py:{2 + 4 * number}）total 2 classes，changed 0 classes' for number in range(8)], lines
    assert lines[-1] == 'compared: plus 4 unchanged items: K8、K9、K10、K11', lines


def test_one_unverified_point_is_said_once():
    # Round 22 review: with one point unverified the count line repeated its only reason, which the next line gives.
    report = dict(session=True, baseline='a' * 40, baseline_kind='task', source_changed=True, items=[],
                  unverified=['N1: reason 1 needs a test'])
    assert signals.render(report).splitlines()[1:] == ['unverified 1 items (not passed)', 'unverified: N1：reason 1 needs a test']


def test_the_unverified_overflow_counts_lines_and_names_every_point_it_leaves_out():
    report = dict(session=True, baseline='a' * 40, baseline_kind='task', source_changed=True, items=[],
                  unverified=[f'N{number}: reason {number} needs a test' for number in range(1, 7)])
    lines = signals.render(report).splitlines()
    assert lines[1] == 'unverified 6 items (not passed): most common reason is "reason 1 needs a test"', lines
    assert lines[2:4] == ['unverified: N1：reason 1 needs a test', 'unverified: N2：reason 2 needs a test'], lines
    assert lines[-1] == 'unverified: plus 4 entries（N3、N4、N5、N6）: python -m flowguard show NAME explains why', lines


def test_old_and_current_source_delimiters_keep_the_same_original_quote():
    quote = 'owner R1: 会员也一样，不能例外。'
    for marker in (' source: ', ' 出处：'):
        rendered = signals.render(dict(session=True, items=[], red=['LIMIT' + marker + quote]))
        assert 'red: LIMIT' in rendered
        assert 'LIMIT source: ' + quote in rendered
