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


# ---- the 4.3 block: one first line, the nine kinds, budgets (design 4.7) -----------------------------------------

import re as _re

from flowguard import __version__
from flowguard.intent import deprecation
from flowguard.intent.signals import Line

SHAPE = _re.compile(r'^(FlowGuard \d+\.\d+ \(|(red|before|known|known fixed\?|changed|impact|loosened|not compared): |\+\d+ more: )')
VERSION = '.'.join(__version__.split('.')[:2])


def _line(kind, number, *, places=None, function='m:f', text=None, step='do it', detail=()):
    place = f'src/pkg{number}/file{number}.py:f{number}'
    return Line(kind, f'{kind}:{number}', f'{function}{number}', text or f'subject {number}: {place} broke', step,
                (place,) if places is None else places, detail)


def _block(lines, **options):
    return signals.render_block(lines, title=signals.title(lines, baseline='a' * 40, kind='task', seconds=1.25), **options).splitlines()


def test_the_first_line_counts_every_kind_before_the_budget_and_always_red():
    lines = [_line('impact', number) for number in range(5)] + [_line('known', 9), _line('not compared', 7), _line('changed', 8)]
    assert signals.title(lines, baseline='0123456789' * 4, kind='task', seconds=3.44) == \
        f'FlowGuard {VERSION} (since 0123456): 0 red, 1 known, 1 changed, 5 impact, 1 not compared; 3.4 s'
    assert signals.title([], baseline=None, kind=None, seconds=0) == f'FlowGuard {VERSION} (no baseline: nothing compared): 0 red; 0.0 s'
    assert signals.title([Line('deprecated', 'x')], baseline='b' * 40, kind='HEAD', seconds=0.04) == \
        f'FlowGuard {VERSION} (since HEAD bbbbbbb): 0 red; 0.0 s'


def test_the_first_line_names_the_baseline_each_way_a_run_can_have_one():
    head = 'c' * 40
    assert [signals.baseline_label(head, kind, ahead, option) for kind, ahead, option in (
        ('task', 0, '--flowguard-base'), ('task', 1, '--flowguard-base'), ('task', 2, '--flowguard-base'),
        ('task', None, '--flowguard-base'), ('HEAD', 0, '--flowguard-base'), ('base', None, '--flowguard-base'),
        ('base', None, '--base'), ('missing', None, '--base'))] == [
        'since ccccccc', 'since ccccccc, 1 commit before HEAD', 'since ccccccc, 2 commits before HEAD', 'since ccccccc',
        'since HEAD ccccccc', 'since --flowguard-base ccccccc', 'since --base ccccccc',
        'since ccccccc, not in this repository: nothing compared; run python -m flowguard new-task']
    assert signals.baseline_label(None, 'HEAD') == 'no baseline: nothing compared'


def test_the_first_line_shortens_a_commit_id_and_names_a_ref_as_it_was_given():
    """Only a full commit id is cut to seven characters: a branch, a tag, HEAD~1 or an abbreviated id is the name the
    option was given (`since --base release/task-start`, never `since --base release`)."""
    assert [signals.baseline_label(given, 'base', None, '--base') for given in (
        'release/task-start', 'origin/main', 'HEAD~1', 'v4.2.1', '6e18a86f', 'c' * 40, 'd' * 64)] == [
        'since --base release/task-start', 'since --base origin/main', 'since --base HEAD~1', 'since --base v4.2.1',
        'since --base 6e18a86f', 'since --base ccccccc', 'since --base ddddddd']


def test_red_loosened_and_known_fixed_are_listed_in_full_and_the_rest_keep_to_ten_lines():
    lines = ([_line('red', number) for number in range(15)] + [_line('loosened', number) for number in range(4)]
             + [_line('known fixed?', number) for number in range(3)] + [_line('changed', number) for number in range(5)]
             + [_line('before', number) for number in range(4)] + [_line('known', number) for number in range(2)]
             + [_line('impact', number) for number in range(6)] + [_line('not compared', number) for number in range(9)])
    block = _block(lines)
    assert block[0] == f'FlowGuard {VERSION} (since aaaaaaa): 15 red, 4 before, 2 known, 3 known fixed?, 5 changed, 6 impact, 4 loosened, 9 not compared; 1.2 s'
    kinds = [line.partition(': ')[0] for line in block[1:]]
    assert kinds == ['red'] * 15 + ['before', 'known', 'known'] + ['known fixed?'] * 3 + ['changed'] * 3 + [
        'impact'] * 2 + ['loosened'] * 4 + ['not compared', '+6 more'], block
    # known lines (each a step of the owner's entry, `ask owner` among them) come first within the two lines; the count
    # line stands where its kind keeps the order of the kinds
    assert block[16:19] == ['before: 4 more (4 before) -> python -m flowguard show --last',
                            'known: subject 0: file0.py:f0 broke -> do it', 'known: subject 1: file1.py:f1 broke -> do it'], block
    assert block[-2] == 'not compared: 9 functions (no reason recorded) -> not a failure'
    assert block[-1] == '+6 more: python -m flowguard show --last'
    rest = [line for line in block[1:] if not line.startswith(('red: ', 'loosened: ', 'known fixed?: '))]
    assert len(rest) == 10
    # The count line takes the kind most of the hidden lines have.
    assert _block([_line('before', 0)] + [_line('known', number) for number in range(4)])[1:] == [
        'known: subject 0: file0.py:f0 broke -> do it', 'known: subject 1: file1.py:f1 broke -> do it',
        'known: 3 more (2 known, 1 before) -> python -m flowguard show --last']
    # Two or more before lines never hide a known line: one known and one before fill the two lines.
    assert _block([_line('before', number) for number in range(3)] + [_line('known', 9, step='ask owner (not asked yet)')])[1:] == [
        'before: subject 0: file0.py:f0 broke -> do it', 'before: 2 more (2 before) -> python -m flowguard show --last',
        'known: subject 9: file9.py:f9 broke -> ask owner (not asked yet)']
    # Nothing to say: the first line alone.
    assert _block([]) == [f'FlowGuard {VERSION} (since aaaaaaa): 0 red; 1.2 s']


def test_everything_lists_every_line_uncut_and_one_line_per_item_not_compared():
    lines = [_line('changed', number) for number in range(5)] + [_line('not compared', number, detail=('async',)) for number in range(4)]
    lines.append(_line('red', 9, text='subject 9: src/pkg9/file9.py:f9 ' + 'x' * 300))
    block = _block(lines, everything=True)
    assert len(block) == 1 + 10 and block[1].startswith('red: subject 9: file9.py:f9 ' + 'x' * 300), block
    assert block[-1] == 'not compared: subject 3: file3.py:f3 broke -> do it', block


def test_a_line_keeps_200_characters_besides_its_places_and_its_subject_places_and_step():
    deep = 'src/' + '/'.join(f'level{number}' for number in range(30)) + '/policy.py'
    line = Line('red', 'rule:R', 'm:f', f'rule R: {"a" * 150} at {deep}:standing and {"b" * 150}', 'change the code',
                (f'{deep}:standing',))
    said, = _block([line])[1:]
    assert said.startswith('red: rule R: a') and said.endswith(' -> change the code') and 'policy.py:standing' in said, said
    assert '...' in said and deep not in said and len(said) - len('policy.py:standing') == 200, said
    # Project text on several lines stays on one line of the block.
    broken = Line('red', 'rule:S', '', 'rule S: "first\nsecond"\r\nthird', 'x')
    assert _block([broken])[1:] == ['red: rule S: "first second" third -> x']


def test_a_line_names_at_most_three_places_and_paths_are_file_names_unless_two_share_one():
    places = tuple(f'src/a{number}.py:f' for number in range(5))
    line = Line('known', 'known.k', '', 'known.k at ' + ', '.join(places), 'ask owner (not asked yet)', places)
    assert _block([line])[1] == 'known: known.k at a0.py:f, a1.py:f, a2.py:f (+2 places) -> ask owner (not asked yet)'
    # The step's places count too: the text names one, the step two more, the rest are counted.
    homes = [f'src/a{number}.py:f' for number in range(5)]
    step = signals.rule_steps('R', homes, 'tests/intent/r.py:3', ['days=4 -> rule False, code True'])[0].rstrip('; ')
    assert step == 'change the code so src/a0.py:f, src/a1.py:f, src/a2.py:f, src/a3.py:f and src/a4.py:f follow rule R', step
    line = Line('red', 'rule:R', '', 'rule R: days=4: rule False, code True at src/a0.py:f', step, tuple(homes))
    assert _block([line])[1] == ('red: rule R: days=4: rule False, code True at a0.py:f -> change the code so a0.py:f, '
                                 'a1.py:f, a2.py:f (+2 places) follow rule R')
    code = ['days=4 -> rule False, code True']
    one = Line('red', 'rule:R', '', 'rule R: x', signals.rule_steps('R', homes[:4], 'r.py:3', code)[0].rstrip('; '), tuple(homes[:4]))
    assert _block([one])[1] == 'red: rule R: x -> change the code so a0.py:f, a1.py:f, a2.py:f (+1 place) follow rule R'
    assert signals.rule_steps('R', homes[:1], 'r.py:3', code)[0] == 'change the code so src/a0.py:f follows rule R; '
    clash = [Line('red', 'x', 'f', 'same X: on n=1: web/api/util.ts:f returns 1, app/api/util.ts:f returns 2', 'decide',
                  ('web/api/util.ts:f', 'app/api/util.ts:f')),
             Line('before', 'y', 'g', 'together A at lib/util.ts:g was broken at task start', 'leave', ('lib/util.ts:g',))]
    assert _block(clash)[1:] == ['red: same X: on n=1: web/api/util.ts:f returns 1, app/api/util.ts:f returns 2 -> decide',
                                 'before: together A at lib/util.ts:g was broken at task start -> leave']
    assert signals._short_paths(['a/b/c.py', 'x/b/c.py', 'd.py', 'e/d2.py']) == {
        'a/b/c.py': 'a/b/c.py', 'x/b/c.py': 'x/b/c.py', 'd.py': 'd.py', 'e/d2.py': 'd2.py'}
    assert signals._short_paths(['a/b/c.py', 'x/y/c.py']) == {'a/b/c.py': 'b/c.py', 'x/y/c.py': 'y/c.py'}


def test_a_path_never_shortens_to_an_end_another_file_of_the_repository_is_or_shares():
    """D17 over the repository's file list: `util.py` is the whole path of another file and `lib/util.py` ends the same
    way, so neither name may stand for `src/util.py`; without the list only the block's own paths count."""
    files = ['util.py', 'src/util.py', 'src/a/util.py', 'lib/a/util.py', 'pkg/only.py', 'x/b/c.py']
    assert signals._short_paths(['src/util.py', 'src/a/util.py', 'pkg/only.py'], files) == {
        'src/util.py': 'src/util.py', 'src/a/util.py': 'src/a/util.py', 'pkg/only.py': 'only.py'}
    assert signals._short_paths(['a/b/c.py'], files) == {'a/b/c.py': 'a/b/c.py'}
    assert signals._short_paths(['src/util.py']) == {'src/util.py': 'util.py'}
    line = Line('changed', 'changed:m:f', 'm:f', 'f (src/util.py:3): (n=1) was 1, now 2; 1/1 inputs differ', 'if you meant it, say so',
                ('src/util.py:3',))
    assert signals.render_block([line], title='T', files=files).splitlines()[1] == \
        'changed: f (src/util.py:3): (n=1) was 1, now 2; 1/1 inputs differ -> if you meant it, say so'
    assert signals.render_block([line], title='T').splitlines()[1].startswith('changed: f (util.py:3)')


def test_a_pytest_block_names_a_file_by_an_end_no_other_file_of_the_repository_has(tmp_path):
    from tests.intent_engine.test_default_runtime_signals import _git, _run
    from tests.intent_engine._cli_fixture import block
    files = {'policy.py': 'def late_fee(days: int) -> int:\n    return days\n', 'pkg/__init__.py': '',
             'pkg/policy.py': 'def late_fee(days: int) -> int:\n    return days * 2\n',
             'tests/test_fee.py': 'from pkg.policy import late_fee\ndef test_fee():\n    assert late_fee(2) in (4, 6)\n',
             '.gitignore': '.flowguard/cache/\n__pycache__/\n.pytest_cache/\n',
             'pyproject.toml': '[tool.pytest.ini_options]\npythonpath=["."]\ntestpaths=["tests"]\n'}
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text, encoding='utf-8')
    _git(tmp_path, 'init', '-q', '-b', 'main')
    _git(tmp_path, 'add', '.')
    _git(tmp_path, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'two policies')
    (tmp_path / 'pkg/policy.py').write_text(files['pkg/policy.py'].replace('days * 2', 'days * 3'), encoding='utf-8')
    result = _run(tmp_path)
    assert result.returncode == 0 and block(result)[1:] == [
        'changed: late_fee (pkg/policy.py:1): (days=2) was 4, now 6; 1/1 inputs differ -> if you meant it, say so'], result.stdout


def test_the_not_compared_line_names_up_to_three_items_and_the_most_common_reasons():
    one = [signals.not_compared('STANDING (src/policy.py:2)', ['uses attribute close'], function='m:standing', places=('src/policy.py:2',))]
    assert _block(one)[1] == 'not compared: STANDING (policy.py:2) (uses attribute close) -> not a failure'
    three = [signals.not_compared(name, [reason]) for name, reason in (('A', 'async'), ('B', 'async'), ('C[rules]', 'not compared: uses getConfig'))]
    assert _block(three)[1] == 'not compared: 3 items: A, B and C[rules] (async, or uses getConfig) -> not a failure'
    many = [signals.not_compared(f'N{number}', [f'reason {number % 4}'], function=f'm:n{number}') for number in range(6)]
    assert _block(many)[1] == 'not compared: 6 functions (reason 0, reason 1, or 2 other reasons) -> not a failure'
    # Only the step follows ' -> ': a reason's own next step reads after a colon (its detail keeps it as it is).
    sourced = [signals.not_compared('A', ['assumed -> confirm against actual owner words']),
               signals.not_compared('B', ['R9 missing -> req add the actual owner words']),
               signals.not_compared('C -> D', ['uses getConfig'])]
    said = _block(sourced)[1]
    assert said == ('not compared: 3 items: A, B and C: D (assumed: confirm against actual owner words, R9 missing: req add the '
                    'actual owner words, or 1 other reason) -> not a failure'), said
    assert said.count('->') == 1 and sourced[0].detail == ('assumed -> confirm against actual owner words',)


def test_every_line_of_a_block_has_one_of_the_shapes_and_flowguard_text_is_ascii():
    import random
    generator = random.Random(43)
    for _ in range(60):
        lines = []
        for number in range(generator.randrange(0, 40)):
            kind = generator.choice(signals.KINDS)
            places = tuple(f'src/{generator.choice("ab")}/f{generator.randrange(4)}.py:fn' for _ in range(generator.randrange(0, 6)))
            text = generator.choice(['subject: x', 'rule R: ' + 'y' * generator.randrange(0, 400), 'a\nb', 'café 会员'])
            lines.append(Line(kind, f'n{number}', generator.choice(['', 'm:f']), text + ' ' + ' '.join(places),
                              generator.choice(['', 'step']), places, ('why',)))
        for everything in (False, True):
            block = _block(lines, everything=everything)
            assert all(SHAPE.match(line) for line in block), block
            assert not any(line.startswith('deprecated') for line in block), block
            frame = [line for line in block if 'caf' not in line and '会' not in line]
            assert all(line.isascii() for line in frame), frame


def test_a_deprecated_feature_says_so_once_per_process_and_each_run_names_what_it_used(capsys):
    start = deprecation.mark()
    for _ in range(3):
        deprecation.warn('old spelling', 'new spelling')
    deprecation.warn('other spelling')
    # design 4.7: `deprecated: X goes in 5.0 -> Y`, on stderr, once per feature in a process
    assert capsys.readouterr().err.splitlines() == ['deprecated: old spelling goes in 5.0 -> write new spelling',
                                                    'deprecated: other spelling goes in 5.0 -> do not use it']
    assert deprecation.used(start) == ['old spelling', 'other spelling']
    later = deprecation.mark()
    deprecation.warn('old spelling')
    assert capsys.readouterr().err == '' and deprecation.used(later) == ['old spelling']


def test_same_name_copies_are_worded_for_the_43_lines_without_choosing_a_copy():
    same = lambda left, right: left == right
    assert signals.copy_says([('a.py:f', 52), ('b.py:g', 53)], same, signals.value_text) == (
        'a.py:f returns 52, b.py:g returns 53', 'decide which copy is right, then make the other agree')
    assert signals.copy_says([('a.py:f', True), ('b.py:g', True), ('c.py:h', False)], same, signals.value_text, total=4) == (
        'a.py:f and b.py:g return True, c.py:h returns False; 1 other copy has no result for this input',
        'decide which copy is right, then make the others agree')
    assert signals.copy_says([('c.py:h', 'x'), ('a.py:f', 'y')], same, signals.value_text, owner='a.py:f',
                             apart=[('b.py:g', 'n=2')]) == (
        "the reference a.py:f returns 'y', c.py:h returns 'x'; b.py:g differs from the reference on n=2",
        'make c.py:h agree with the reference')
    issue = signals.copies_issue('WEEKS', [('year=2026', 'a.py:f returns 52, b.py:g returns 53', 'decide', {frozenset(('a.py:f', 'b.py:g'))})],
                                 [('year=2025', 'b.py:g returns 52, a.py:f returns 53', 'decide', {frozenset(('a.py:f', 'b.py:g'))})],
                                 places=['a.py:f', 'b.py:g'], files={'a.py', 'b.py'})
    assert issue.parts[0] == ('a.py:f|b.py:g', ('a.py:f', 'b.py:g'), 'on year=2026: a.py:f returns 52, b.py:g returns 53', 'decide')
    assert issue.parts[1][1] == ('b.py:g', 'a.py:f') and issue.fresh == frozenset({'a.py:f|b.py:g'})
    lines, _ = signals.deliver([issue], touched_functions={'a.py:f|b.py:g'}, touched_files=())
    assert [(line.kind, line.text) for line in lines] == [
        ('red', 'same WEEKS: on year=2026: a.py:f returns 52, b.py:g returns 53')]
    old = signals.copies_issue('WEEKS', [], [('year=2025', 'b.py:g returns 52, a.py:f returns 53', 'decide', {frozenset(('a.py:f', 'b.py:g'))})],
                               places=['a.py:f', 'b.py:g'])
    lines, _ = signals.deliver([old], touched_functions={'a.py:f|b.py:g'}, touched_files=())
    assert [(line.kind, line.text, line.step) for line in lines] == [
        ('before', 'same WEEKS disagreed at task start on year=2025: b.py:g returns 52, a.py:f returns 53',
         'leave it unless your task is about it')]


def test_four_or_more_same_name_copies_name_three_and_count_the_others_where_they_belong():
    """A line names at most three places: of four or more copies the others are counted in the group of their answer,
    never cut out of a `who returns what` clause (that left another copy's answer pinned on a place); every copy is
    in the finding's detail."""
    same = lambda left, right: left == right
    four = [(f'limits.py:{name}', value) for name, value in (('chart', 1), ('calendar', 2), ('report', 3), ('export', 4))]
    five = [(f'limits.py:{name}', value) for name, value in
            (('chart', 1), ('calendar', 1), ('report', 2), ('export', 2), ('summary', 3))]
    assert signals.copy_says(four, same, signals.value_text) == (
        'limits.py:chart returns 1, limits.py:calendar returns 2, limits.py:report returns 3, 1 other copy returns 4',
        'decide which copy is right, then make the others agree')
    assert signals.copy_says(five, same, signals.value_text)[0] == (
        'limits.py:chart and limits.py:calendar return 1, limits.py:report and 1 other copy return 2, 1 other copy returns 3')
    assert signals.copy_says(five, same, signals.value_text, limit=None)[0] == (
        'limits.py:chart and limits.py:calendar return 1, limits.py:report and limits.py:export return 2, limits.py:summary returns 3')
    # the reference first; the step names the copies the text names and counts the rest
    assert signals.copy_says(five, same, signals.value_text, owner='limits.py:report', apart=[('limits.py:export', 'days=2')]) == (
        'the reference limits.py:report returns 2, limits.py:chart and limits.py:calendar return 1, 1 other copy returns 3; '
        '1 other copy differs from the reference on other inputs',
        'make limits.py:chart, limits.py:calendar and 1 other copy agree with the reference')
    places = [place for place, _ in five]
    lines = signals.copy_lines([('days=1', five)], same, signals.value_text, total=5, words=signals.copy_says)
    issue = signals.copies_issue('LIMIT', lines, [], places=places, files={'limits.py'})
    found, _ = signals.deliver([issue], touched_functions=(), touched_files=())
    assert _block(found)[1:] == [
        'red: same LIMIT: on days=1: limits.py:chart and limits.py:calendar return 1, limits.py:report and 1 other copy return 2, '
        '1 other copy returns 3 -> decide which copy is right, then make the others agree'], found
    assert found[0].detail == ('copies: ' + ', '.join(places),), found


def test_a_changed_line_shows_the_smallest_changed_input_and_how_many_differ():
    line = signals.changed_line('STANDING', 'policy:standing', 'shop/policy.py', 3,
                                [({'days': 9}, False, True), ({'days': 5}, False, True), ({'days': 7}, 'x', {'raises': 'ValueError: no'})], 12)
    assert (line.kind, line.name, line.function, line.text, line.step, line.places) == (
        'changed', 'changed:policy:standing', 'policy:standing',
        'STANDING (shop/policy.py:3): (days=5) was False, now True; 3/12 inputs differ', 'if you meant it, say so', ('shop/policy.py:3',))
    assert line.detail == ('(days=9) was False, now True', '(days=5) was False, now True', "(days=7) was 'x', now raises ValueError: no")
    assert signals.changed_line('late', 'm:late', 'm.py', 0, [({}, 1, 2)], 1, unanchored=True).detail[-1] == \
        'no flowguard comment: compared because its code changed'


def test_a_changed_line_and_the_check_view_take_list_and_dict_inputs():
    """A recorded input is any JSON value: lists and dicts are compared by their JSON (equal JSON is one value),
    never hashed."""
    rows = [({'items': [5], 'order': {'b': 1, 'a': 2}}, 5, 6), ({'items': [1, 2], 'order': {'a': 2, 'b': 1}}, 3, 4),
            ({'items': [1, 2], 'order': {'a': 1}}, 3, 5)]
    line = signals.changed_line('TOTAL', 'calc:total', 'calc.py', 2, rows, 3)
    assert line.text == 'TOTAL (calc.py:2): (items=[1, 2], order={"a": 1}) was 3, now 5; 3/3 inputs differ', line
    assert line.detail[0] == '(items=[5], order={"a": 2, "b": 1}) was 5, now 6', line
    # check still renders a pytest batch's report with the 4.2 view of its changed points
    item = dict(name='TOTAL', file='calc.py', line=2, status='ok', complete=True, total=3, changed=rows,
                rows=[(inputs, new) for inputs, _, new in rows])
    text = signals.render(dict(session=True, baseline='a' * 40, baseline_kind='task', source_changed=True, items=[item]))
    assert 'changed: TOTAL' in text and 'items=[1, 2]' in text, text


def test_a_pytest_run_whose_changed_function_takes_a_list_prints_and_keeps_its_changed_line(tmp_path):
    from tests.intent_engine.test_default_runtime_signals import _project, _run
    from tests.intent_engine._cli_fixture import block, last
    policy = _project(tmp_path, '''
        # flowguard: same TOTAL
        def total(items: list) -> int:
            return sum(items)
    ''', '''
        from policy import total
        def test_total():
            assert total([1, 2]) >= 3 and total([5]) >= 5
    ''')
    policy.write_text(policy.read_text().replace('sum(items)', 'sum(items) + 1'))
    result = _run(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    changed = 'changed: total (policy.py:2): (items=[1, 2]) was 3, now 4; 2/2 inputs differ -> if you meant it, say so'
    assert block(result)[1:] == [changed], result.stdout
    assert changed in last(tmp_path).splitlines()


def test_every_stdout_line_of_a_pytest_block_has_one_of_the_shapes(tmp_path):
    """Design 4.7 over real pytest runs: the block is the last thing on stdout, each of its lines starts with the
    first line, one of the kinds or `+N more:`; deprecation notices go to stderr only."""
    from tests.intent_engine.test_default_runtime_signals import _project, _run
    from tests.intent_engine._cli_fixture import display_text
    policy = _project(tmp_path / 'copies', '''
        import sqlite3
        # flowguard: same STANDING
        def standing(days: int) -> bool:
            return days <= 3
        # flowguard: same STANDING
        def preview(days: int) -> bool:
            return days <= 3
        def late_fee(days: int) -> int:
            return days * 2
        # flowguard: sensor AVAILABLE
        def available(db: sqlite3.Connection, stock: int) -> bool:
            return stock > 0
    ''', '''
        import sqlite3
        from policy import standing, preview, late_fee, available
        def test_native():
            assert standing(0) and preview(0) and late_fee(2) in (4, 6)
            with sqlite3.connect(':memory:') as db:
                assert available(db, 1)
    ''', rule='''
        from flowguard.intent import rule, row
        @rule('STANDING_RULE', decides='standing', fields={'days': int}, anchor='STANDING',
              source='doc policy.txt "At most three days."')
        def STANDING_RULE(days):
            return days <= 3
        STANDING_RULE.rows(row(days=4, expect=False, why='the fourth day must remain refused'))
    ''')
    policy.write_text(policy.read_text().replace('return days <= 3', 'return days <= 7', 1)
                      .replace('days * 2', 'days * 3').replace('stock > 0', 'stock >= 0'))
    result = _run(tmp_path / 'copies')
    lines = display_text(result.stdout).splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith('FlowGuard '))
    block = lines[start:]
    assert result.returncode == 1 and all(SHAPE.match(line) for line in block), block
    kinds = {line.partition(': ')[0] for line in block[1:]}
    assert {'red', 'changed', 'not compared'} <= kinds, block
    assert not any(line.startswith('deprecated') for line in lines), lines
    # the project uses nothing deprecated: the old-value lead FlowGuard makes itself prints no notice
    assert 'deprecated' not in result.stderr, result.stderr


def test_the_block_follows_pytests_summary_with_every_reporter_option_and_after_an_interrupt(tmp_path):
    """Design 4.7 (D25): the block prints after pytest's own summary line, also with --no-summary, without the
    terminal reporter (-p no:terminal, which prints nothing else) and when a test interrupts the run."""
    from tests.intent_engine.test_default_runtime_signals import _project, _run
    changed = 'changed: late_fee (policy.py:1): (days=2) was 4, now 6; 1/1 inputs differ -> if you meant it, say so'
    policy = _project(tmp_path / 'p', 'def late_fee(days: int) -> int:\n    return days * 2\n', '''
        from policy import late_fee
        def test_fee():
            assert late_fee(2) in (4, 6)
    ''')
    policy.write_text(policy.read_text().replace('days * 2', 'days * 3'))
    import subprocess
    import sys
    from tests.intent_engine._cli_fixture import SOURCE
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    for options in ((), ('--no-summary',), ('-p', 'no:terminal')):
        result = _run(tmp_path / 'p', *options) if 'no:terminal' not in options else subprocess.run(   # -q needs the reporter
            [sys.executable, '-c', bootstrap, SOURCE, '-p', 'flowguard.intent.plugin', *options], cwd=tmp_path / 'p',
            capture_output=True, text=True, timeout=60)
        lines = result.stdout.splitlines()
        start = next(index for index, line in enumerate(lines) if line.startswith('FlowGuard '))
        assert result.returncode == 0 and _re.fullmatch(rf'FlowGuard {_re.escape(VERSION)} \(since [0-9a-f]{{7}}\): 0 red, 1 changed; '
                                                         r'\d+\.\d s', lines[start]) and lines[start + 1:] == [changed], (options, lines)
        if 'no:terminal' in options:
            assert lines == lines[start:start + 2], lines            # nothing else prints
        else:
            assert _re.match(r'1 passed in ', lines[start - 1]), lines  # right after pytest's summary line
    (tmp_path / 'p/tests/test_stop.py').write_text('def test_stop():\n    raise KeyboardInterrupt\n', encoding='utf-8')
    result = _run(tmp_path / 'p')
    lines = result.stdout.splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith('FlowGuard '))
    assert result.returncode == 2 and lines[start + 1:] == [changed], lines
    assert any('KeyboardInterrupt' in line for line in lines[:start]) and _re.search(r'\d+ passed in ', lines[start - 1]), lines


def test_a_known_entry_naming_an_old_same_name_disagreement_is_its_known_line_in_pytest(tmp_path):
    """The PT frontend case (design 6.1): copies that already disagreed, a known.toml entry naming them and a change
    touching their file give the entry's line with its step, never red or before, and the run passes."""
    from tests.intent_engine.test_default_runtime_signals import _git, _project, _run
    from tests.intent_engine._cli_fixture import block, last
    root = tmp_path / 'weeks'
    policy = _project(root, '''
        # flowguard: same WEEKS
        def weeks(year: int) -> int:
            return 52
        # flowguard: same WEEKS
        def iso_weeks(year: int) -> int:
            return 53 if year == 2025 else 52
    ''', '''
        from policy import weeks, iso_weeks
        def test_weeks():
            assert weeks(2024) == iso_weeks(2024) == 52
    ''')
    (root / '.flowguard').mkdir()
    (root / '.flowguard/known.toml').write_text(
        '[known.iso-weeks]\nsites = ["policy.py:weeks", "policy.py:iso_weeks"]\n'
        'why = "the two copies disagree on 2025; the owner has not said which is right"\nact = "ask"\n'
        'ask = "Has 2025 52 or 53 ISO weeks?"\nfinding = "same:WEEKS"\n', encoding='utf-8')
    _git(root, 'add', '.')
    _git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'known disagreement')
    untouched = _run(root)
    assert untouched.returncode == 0 and block(untouched)[1:] == [], untouched.stdout     # nothing touches the copies
    # A comment below the copies touches their file, not the entry's sites (D31): neither known nor before.
    policy.write_text(policy.read_text() + '# a documentation-only edit\n')
    commented = _run(root)
    assert commented.returncode == 0 and block(commented)[1:] == [], commented.stdout
    policy.write_text(policy.read_text().replace('    return 52\n', '    return 50 + 2\n', 1))     # one site, same answers
    result = _run(root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert block(result)[1:] == ['known: known.iso-weeks at policy.py:weeks, policy.py:iso_weeks -> ask owner (not asked yet)'], result.stdout
    shown = last(root).splitlines()
    assert '    ask: Has 2025 52 or 53 ISO weeks?' in shown, shown
    # Without the entry the same disagreement is before, with the input it is about.
    (root / '.flowguard/known.toml').unlink()
    result = _run(root)
    assert result.returncode == 0 and block(result)[1:] == [
        'before: same WEEKS disagreed at task start on year=2025: policy.py:weeks returns 52, policy.py:iso_weeks returns 53 '
        '-> leave it unless your task is about it', "loosened: known.iso-weeks removed from known.toml -> name it in your report; needs the owner's yes"
    ], result.stdout


def test_a_known_entry_whose_same_name_copies_now_agree_in_the_pytest_session_is_known_fixed(tmp_path):
    """Design 4.7's own example: the session compared the copies sealed and they agree now, so the entry naming their
    disagreement asks whether it is fixed; a session that could not compare every copy does not ask."""
    from tests.intent_engine.test_default_runtime_signals import _git, _project, _run
    from tests.intent_engine._cli_fixture import block
    root = tmp_path / 'weeks'
    policy = _project(root, '''
        # flowguard: same WEEKS
        def weeks(year: int) -> int:
            return 52
        # flowguard: same WEEKS
        def iso_weeks(year: int) -> int:
            return 53 if year == 2025 else 52
    ''', '''
        from policy import weeks, iso_weeks
        def test_weeks():
            assert weeks(2024) == iso_weeks(2024) == 52
    ''')
    (root / '.flowguard').mkdir()
    (root / '.flowguard/known.toml').write_text(
        '[known.iso-weeks]\nsites = ["policy.py:weeks", "policy.py:iso_weeks"]\n'
        'why = "the two copies disagree on 2025; the owner has not said which is right"\nact = "leave"\n'
        'finding = "same:WEEKS"\n', encoding='utf-8')
    _git(root, 'add', '.')
    _git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'known disagreement')
    policy.write_text(policy.read_text().replace('return 53 if year == 2025 else 52', 'return 52'))
    result = _run(root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert block(result)[1:] == ['known fixed?: known.iso-weeks: copies of WEEKS now agree -> the owner deferred it: '
                                 'revert, or say why in your report'], result.stdout
    # One copy that cannot run sealed: the copies were not all compared, so nothing is said to be fixed.
    policy.write_text(policy.read_text().replace('def iso_weeks(year: int) -> int:\n    return 52',
                                                 'def iso_weeks(year: int) -> int:\n    return len(open(__file__).read()) * 0 + 52'))
    result = _run(root)
    shown = block(result)
    assert result.returncode == 0 and not any(line.startswith('known fixed?') for line in shown), result.stdout
    assert any(line.startswith('not compared: ') and 'WEEKS' in line for line in shown), result.stdout


def test_a_known_entry_naming_a_rule_whose_items_all_pass_in_the_session_is_known_fixed(tmp_path):
    from tests.intent_engine.test_default_runtime_signals import _git, _project, _run
    from tests.intent_engine._cli_fixture import block
    root = tmp_path / 'days'
    policy = _project(root, '# flowguard: sensor STANDING\ndef standing(days: int) -> bool:\n    return days <= 3\n',
                      'from policy import standing\ndef test_native():\n    assert standing(0) is True\n', rule='''
        from flowguard.intent import rule, row
        @rule('STANDING_RULE', decides='standing', fields={'days': int}, anchor='STANDING',
              source='doc policy.txt "At most three days."')
        def STANDING_RULE(days):
            return days <= 3
        STANDING_RULE.rows(row(days=4, expect=False, why='the fourth day must remain refused'))
    ''')
    (root / '.flowguard').mkdir()
    (root / '.flowguard/known.toml').write_text('[known.days]\nsites = ["policy.py:standing"]\nwhy = "deferred"\nact = "leave"\n'
                                                'finding = "rule:STANDING_RULE"\n', encoding='utf-8')
    _git(root, 'add', '.')
    _git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'known rule finding')
    policy.write_text(policy.read_text().replace('days <= 3', '3 >= days'))
    result = _run(root)
    assert result.returncode == 0 and block(result)[1:] == [
        'known fixed?: known.days: rule:STANDING_RULE no longer found -> the owner deferred it: revert, or say why in your report'
    ], result.stdout
    # The rule's items not run (another test selected): nothing says it is fixed; the touched site is known.
    result = _run(root, 'tests/test_case.py')
    assert result.returncode == 0 and block(result)[1:] == [
        'known: known.days at policy.py:standing -> leave it (the owner deferred it)'], result.stdout


def test_an_intent_item_failing_only_on_a_source_broken_at_task_start_passes_and_is_before_where_touched(tmp_path):
    """Design 6.1: the exit code follows red only. A quote already gone from its document at the baseline makes no
    verdict red; it is a before line where the change touches the file declaring the rule, else nothing."""
    from tests.intent_engine.test_default_runtime_signals import _git, _project, _run
    from tests.intent_engine._cli_fixture import block
    root = tmp_path / 'gone'
    _project(root, '# flowguard: sensor STANDING\ndef standing(days: int) -> bool:\n    return days <= 3\n',
             'from policy import standing\ndef test_native():\n    assert standing(0) is True\n', rule='''
        from flowguard.intent import rule, row
        @rule('STANDING_RULE', decides='standing', fields={'days': int}, anchor='STANDING',
              source='doc policy.txt "At most three days."')
        def STANDING_RULE(days):
            return days <= 3
        STANDING_RULE.rows(row(days=4, expect=False, why='the fourth day must remain refused'))
    ''')
    (root / 'policy.txt').write_text('At most four days.\n', encoding='utf-8')
    _git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qam', 'the quote is gone')
    untouched = _run(root)
    assert untouched.returncode == 0 and '5 passed' in untouched.stdout, untouched.stdout + untouched.stderr
    assert not any(line.startswith(('red: ', 'before: ')) for line in block(untouched)), untouched.stdout
    intent = root / 'tests/intent/decisions.py'
    intent.write_text(intent.read_text() + '# a comment beside the rule\n', encoding='utf-8')
    touched = _run(root)
    assert touched.returncode == 0 and '5 passed' in touched.stdout, touched.stdout + touched.stderr
    assert [line for line in block(touched) if line.startswith(('red: ', 'before: '))] == [
        'before: source STANDING_RULE at decisions.py:2 was broken at task start -> leave it unless your task is about it'
    ], touched.stdout


def test_a_rule_whose_source_does_not_parse_is_a_red_input_line_of_the_session_never_a_crash(tmp_path):
    """D4: a source that is no source form (a bare sentence) is an input problem: the loader's red `load` line names
    the declaration and the parser's words, and the session judges nothing of the refused rule (it crashed doing so)
    while it still prints, keeps and judges everything else; an item of the rule that ran keeps its own red."""
    from tests.intent_engine.test_default_runtime_signals import _project, _run
    from tests.intent_engine._cli_fixture import block, last
    policy = _project(tmp_path, '# flowguard: sensor STANDING\ndef standing(days: int) -> bool:\n    return days <= 3\n',
                      'from policy import standing\ndef test_native():\n    assert standing(4) in (True, False)\n', rule='''
        from flowguard.intent import rule
        @rule('STANDING_RULE', decides='standing', fields={'days': int}, anchor='STANDING', source='At most three days.')
        def STANDING_RULE(days):
            return days <= 3
    ''')
    policy.write_text(policy.read_text().replace('days <= 3', 'days <= 5'))
    load = ('red: load tests/intent/decisions.py:2: STANDING_RULE: source needs rule.<id> (a rule of .flowguard/rules.toml), '
            'R<id> "exact words", owner R-id, doc PATH "quoted words", assumed: or lesson: '
            '-> correct this declaration; until then none of its file is checked')
    for options, rule in (((), ['red: rule STANDING_RULE: days=4: rule False, code True at policy.py:standing']),
                          (('tests/test_case.py',), [])):          # with and without the rule's own items
        result = _run(tmp_path, *options)
        assert result.returncode == 1 and 'Traceback' not in result.stderr, result.stdout + result.stderr
        reds = [line for line in block(result) if line.startswith('red: ')]
        assert [line.partition(' (')[0] for line in reds if line.startswith('red: rule ')] == rule, result.stdout
        assert [line.partition(': source needs')[0] for line in reds if line.startswith('red: load ')] == [
            'red: load decisions.py:2: STANDING_RULE'], result.stdout
        assert load in last(tmp_path).splitlines(), last(tmp_path)
        assert 'changed: standing (policy.py:2)' in '\n'.join(block(result)), result.stdout


def test_a_rule_red_spells_both_results_and_its_step_names_the_copy_that_disagrees_in_a_sentence(tmp_path):
    """Two homes of one rule, one of them changed: the rule's result is spelled as the code's (`rule False, code True`,
    never `rule F`) and the step names where the code disagrees (`so orders.py:preview_accept follows rule WINDOW`),
    in pytest and in check alike."""
    from tests.intent_engine.test_unverified_outcome import _cli, _project, _pytest
    from tests.intent_engine._cli_fixture import block
    root = _project(tmp_path / 'p', {
        'policy.txt': 'At most three days.\n',
        'orders.py': '''
            # flowguard: same ACCEPT ref(days: day) -> allowed: bool
            def accept(days: int) -> bool:
                return days <= 3

            # flowguard: same ACCEPT(days: day) -> allowed: bool
            def preview_accept(days: int) -> bool:
                return days <= 3
        ''',
        'tests/test_orders.py': '''
            from orders import accept, preview_accept

            def test_accept():
                assert accept(3) and not accept(5)
                assert preview_accept(2)
        ''',
        'tests/intent/window.py': '''
            from flowguard.intent import rule, row

            @rule("WINDOW", decides="acceptance window", fields={"days": int},
                  source='assumed: at most three days', anchor="ACCEPT")
            def WINDOW(days):
                return days <= 3

            WINDOW.rows(row(days=4, expect=False, why="the fourth day was accepted"))
        ''',
    })
    path = root / 'orders.py'
    path.write_text(path.read_text(encoding='utf-8').replace(
        'def preview_accept(days: int) -> bool:\n    return days <= 3', 'def preview_accept(days: int) -> bool:\n    return days <= 4'),
        encoding='utf-8')
    red = ('red: rule WINDOW: days=4: rule False, code True at orders.py:preview_accept (1 of 6 cells disagree) (+1 more) '
           '-> change the code so orders.py:preview_accept follows rule WINDOW')
    for run, (result, _) in (('pytest', _pytest(root, '-q')), ('check', _cli(root, 'check'))):
        assert result.returncode == 1 and red in block(result), (run, result.stdout)


def test_every_line_has_one_arrow_before_its_step_whatever_the_project_spells(tmp_path):
    """` -> ` separates a line from its step, once per line: a recorded value that holds ` -> ` is written so that it
    holds none (the same value in Python and JSON), a comment's own `->` stays out of the separator, and a rule red
    reads `days=4: rule False, code True`."""
    from tests.intent_engine.test_unverified_outcome import _cli, _project, _pytest
    root = _project(tmp_path / 'p', {
        'route.py': '''
            # flowguard: same ROUTE ref
            def route(a: int) -> str:
                return f'{a} -> hub'

            # flowguard: same ROUTE
            def route_copy(a: int) -> str:
                return f'{a} -> hub'
        ''',
        'orders.py': '''
            # flowguard: same ACCEPT(days: day) -> allowed: bool -> extra
            def preview_accept(days: int) -> bool:
                return days <= 3
        ''',
        'tests/test_route.py': '''
            from route import route, route_copy

            def test_route():
                assert route(1) and route_copy(1)
        ''',
    })
    path = root / 'route.py'
    path.write_text(path.read_text(encoding='utf-8').replace("    return f'{a} -> hub'\n", "    return f'{a} -> cafe'\n", 2)
                    .replace("    return f'{a} -> cafe'\n", "    return f'{a} -> hub'\n", 1), encoding='utf-8')
    for run, (result, _) in (('pytest', _pytest(root, '-q')), ('check', _cli(root, 'check')),
                             ('check --static', _cli(root, 'check', '--static'))):
        lines = result.stdout.splitlines()          # as printed: `block` would undo the escape of a display
        shown = lines[next(number for number, line in enumerate(lines) if line.startswith('FlowGuard ')):]
        assert result.returncode == 1 and all(line.count(' -> ') == 1 for line in shown[1:]), (run, shown)
        assert 'red: comment orders.py:1: anchor return type bool->extra != source bool -> correct this flowguard comment' in shown, (run, shown)
        if run == 'pytest':
            assert ("red: same ROUTE: on a=1: the reference route.py:route returns '1 -\\u003e hub', route.py:route_copy returns "
                    "'1 -\\u003e cafe' -> make route.py:route_copy agree with the reference") in shown, shown
