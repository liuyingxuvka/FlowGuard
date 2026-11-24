"""Human-readable views preserve uncertainty, locations and bounded output."""
from contextlib import closing

import pytest

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
    assert 'days=4..7, active=F' in regions
    assert any('active=T' in label for label in regions)
    assert not any('not (' in label for label in regions)


def test_relational_boundary_stays_a_relation_between_inputs():
    _, report = compare(available, too_available, {'stock': int, 'reserved': int})
    assert report['changed'] == 1
    assert report['changes'][0]['region'] in ('stock=reserved', 'reserved=stock')


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
    # The red line of the first input, in the words of the 4.3 block: no way out besides the fix (4.7).
    words = signals.copy_lines(inputs, lambda x, y: x == y, str, owner='a', total=3, words=signals.copy_says)
    [red], _ = signals.deliver([signals.copies_issue('LIMIT', words[:1], [], places=['a', 'b', 'c'])], touched_functions=(),
                               touched_files=())
    assert (red.kind, red.text, red.step) == (
        'red', 'same LIMIT: on days=3: the reference a returns True, c returns False; b differs from the reference on days=4',
        'make c agree with the reference')
    # Without an owner no copy is the reference: a line is kept where it first shows two copies that differ.
    lines = signals.copy_lines(inputs, lambda x, y: x == y, str, total=3)
    assert [(where, text, step) for where, text, step, _ in lines] == [
        ('days=3', '3 copies: 2 copies return True (a, b), 1 copies return False (c)', 'first decide which copy is correct, then make the remaining copies agree with it'),
        ('days=4', '3 copies: 2 copies return False (a, c), 1 copies return True (b)', 'first decide which copy is correct, then make the remaining copies agree with it')]
    assert lines[1][3] == {frozenset('ab'), frozenset('bc')}
    assert signals.copy_lines(inputs[2:3], lambda x, y: x == y, str, owner='a', total=3)[0][1] == \
        '3 copies: 2 copies return False (reference a, c), 1 copies return True (b)'


def test_readable_labels_do_not_mutate_the_source_constant_environment():
    import ast
    from flowguard.intent import cells as C
    env = {'GRACE': 7}
    kinds = {'days': C.kind_of(int)}
    assert signals.class_label([('days <= GRACE', None, env)], [True], kinds, {'days': 4}) == 'days<=7'
    assert env == {'GRACE': 7}


def test_an_explicit_comparison_prints_its_changes_and_keeps_the_points_it_found_unchanged_for_show_last(tmp_path):
    from tests.intent_engine.test_default_runtime_signals import _project, _run
    from tests.intent_engine._cli_fixture import block, last
    policy = _project(tmp_path, '''
        def late_fee(days: int) -> int:
            return days * 2
        def grace(days: int) -> int:
            return days * 3
    ''', '''
        from policy import late_fee, grace
        def test_fee():
            assert late_fee(2) in (4, 6) and grace(1) == 3
    ''')
    policy.write_text(policy.read_text().replace('return days * 3', 'return 3 * days').replace('return days * 2', 'return days * 3'))
    result = _run(tmp_path, '--flowguard-base', 'HEAD')
    lines = block(result)
    assert result.returncode == 0 and _re.fullmatch(rf'FlowGuard {_re.escape(VERSION)} \(since --flowguard-base [0-9a-f]{{7}}\): 0 red, '
                                                    r'1 changed; \d+\.\d s', lines[0]), lines
    # the change is a line; the point that answers as before is no line, show --last names it
    assert lines[1:] == ['changed: late_fee (policy.py:1): (days=2) was 4, now 6; 1/1 inputs differ -> if you meant it, say so'], lines
    shown = last(tmp_path).splitlines()
    assert shown[shown.index('compared, unchanged:') + 1] == '    grace (policy.py:3): 1 inputs compared, none differs', shown


# ---- the 4.3 block: one first line, the eight kinds, budgets (design 4.7) -----------------------------------------

import re as _re

from flowguard import __version__
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
    assert signals.title([], baseline='b' * 40, kind='HEAD', seconds=0.04) == f'FlowGuard {VERSION} (since HEAD bbbbbbb): 0 red; 0.0 s'


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
    # known lines (each a step of the owner's entry, an open question among them) come first within the two lines; the count
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
    assert _block([_line('before', number) for number in range(3)] + [_line('known', 9, step='an open question for the owner, not asked yet')])[1:] == [
        'before: subject 0: file0.py:f0 broke -> do it', 'before: 2 more (2 before) -> python -m flowguard show --last',
        'known: subject 9: file9.py:f9 broke -> an open question for the owner, not asked yet']
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


def test_a_long_input_gives_way_first_and_a_changed_line_keeps_what_was_and_what_is_now():
    """Design 4.7, at most 200 characters besides the paths: the input a line is about gives way first (a changed
    line's inputs, a same-name line's `on ...:`), so a 300-character input never cuts away what a function answered
    before and now, nor which copy returns what; long answers give way after it, to one length together, and the
    words between the values stay."""
    text = 'abcd' + 'efgh' * 73 + 'hijx'                 # 300 characters
    def changed(old, new):
        line = signals.changed_line('longOne', 'src/m:longOne', 'src/m.ts', 25, [({'text': text}, old, new)], 1)
        said, = _block([line])[1:]
        assert len(said) - len('m.ts:25') <= 200, said
        return said
    assert changed(True, False) == (
        "changed: longOne (m.ts:25): (text='abcdefghefghefghefghefghefghefghefghefghefghefgh...hefghefghefghefghefghefghefgh"
        "efghefghefghefghefghhijx') was True, now False; 1/1 inputs differ -> if you meant it, say so")
    # The answers are as long: the input is cut to 36 characters first, then both answers alike.
    assert changed(text, text + 'x') == (
        "changed: longOne (m.ts:25): (text='abcdefghefg...efghefghefghhijx') was 'abcdefghefghefghef...ghefghefghefghhijx', "
        "now 'abcdefghefghefghef...hefghefghefghhijxx'; 1/1 inputs differ -> if you meant it, say so")
    same = Line('red', 'same:N', 'a|b', f'same N: on (text={text!r}): a.py:f returns 1, b.py:g returns 2',
                'decide which copy is right, then make the other agree', ('a.py:f', 'b.py:g'))
    said, = _block([same])[1:]
    assert said == ("red: same N: on (text='abcdefghefghefghefghefghefghefghefghefghefg...efghefghefghefghefghefghefghefghefgh"
                    "efghefghhijx'): a.py:f returns 1, b.py:g returns 2 -> decide which copy is right, then make the other agree")
    assert len(said) - len('a.py:f') - len('b.py:g') == 200, said


def test_the_comment_a_step_tells_the_user_to_write_keeps_its_whole_paths():
    # Review of 5.0: the block shortened the path inside the except= of the rewrite it printed, and `except=fees.py:move`
    # names no function: the comment a step says to write keeps its paths whole; the rest of the line is shortened.
    step = ('write # flowguard: together B.unit B.staff except=pkg/fees.py:move(r),pkg/fees.py:hold(s) and, on its own '
            'line, # flowguard: writers B.unit reserve,pkg/fees.py:move')
    line = Line('red', 'comment:pkg/fees.py:6:removed', '', 'comment pkg/fees.py:6: owner writers= and alone= were removed',
                step, ('pkg/fees.py:6',))
    assert _block([line])[1] == 'red: comment fees.py:6: owner writers= and alone= were removed -> ' + step
    other = Line('red', 'rule:R', '', 'rule R: x at pkg/fees.py:move', 'change pkg/fees.py:move or write // flowguard: same R '
                 'above pkg/fees.py:move', ('pkg/fees.py:move',))
    assert _block([other])[1] == 'red: rule R: x at fees.py:move -> change fees.py:move or write // flowguard: same R above pkg/fees.py:move'


def test_a_conflict_step_says_who_decides_and_both_routes_of_storing_his_decision():
    """R101, R105: 5.0.1's conflict step said `choose one by asking the owner`, and stored his decision only as typed
    words (`store the exact owner words with python -m flowguard req add`), while rule 7 of the rules block also names
    his pick among options the agent offered, which a plain request under its id would close."""
    said = ['conflict THREE vs FOUR at days=4: F vs T (1 of 6 shared cells) (owner R1, R2) -> the owner\'s words of the '
            'two rules disagree; only the owner can settle which holds']
    assert signals.rule_steps('FOUR', ['FOUR binding'], 'tests/intent/days.py:9', said) == [
        'rules THREE and FOUR conflict; only the owner can choose which holds; ',
        'when the owner decides, first store his typed words with python -m flowguard req add - --id R<n>, or his pick '
        'among options you offered with python -m flowguard req add REPLY --id R<n> --offer FILE --picked "TEXT", then '
        'update rule tests/intent/days.py:9']


@pytest.mark.parametrize('said, first', [
    (['days=4 -> rule False, code True'], 'change the code so app.py:accept follows rule FOUR; '),
    (['self: rule FOUR gives False on its own row L6 (expected True)'],
     'correct regression rows or rule tests/intent/days.py:9 so the rule and its regression rows agree; '),
    (['gap in loan days (total=True): no rule decides 2 cells, smallest days=-1'],
     'add rules or regression rows at tests/intent/days.py:9 so undecided cells have a rule result; '),
    (['unknown problem'], 'inspect rule tests/intent/days.py:9 and correct its source, binding or regression rows; '),
])
def test_every_rule_step_that_stores_the_owners_decision_names_both_routes(said, first):
    """R105: after the conflict step named both routes of rule 7 of the rules block, every other rule step still said
    `if requirements changed, first store the new owner words with python -m flowguard req add, then update rule ...`,
    the route that stores an answer to options the agent offered as a plain request and closes its id to the choice."""
    assert signals.rule_steps('FOUR', ['app.py:accept'], 'tests/intent/days.py:9', said) == [
        first,
        "if requirements changed, first store the owner's new typed words with python -m flowguard req add - --id R<n>, "
        'or his pick among options you offered with python -m flowguard req add REPLY --id R<n> --offer FILE --picked '
        '"TEXT", then update rule tests/intent/days.py:9']


def test_a_line_names_at_most_three_places_and_paths_are_file_names_unless_two_share_one():
    places = tuple(f'src/a{number}.py:f' for number in range(5))
    line = Line('known', 'known.k', '', 'known.k at ' + ', '.join(places), 'an open question for the owner, not asked yet', places)
    assert _block([line])[1] == 'known: known.k at a0.py:f, a1.py:f, a2.py:f (+2 places) -> an open question for the owner, not asked yet'
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
    # A function's line names the function, not the agreement it is marked with (5.1, Planning Tool: `2 functions:
    # PROJECT_SCOPE (scope.py:2) and PROJECT_SCOPE (scope.py:6)`); `show --last` keeps the line's own text.
    one = [signals.not_compared('STANDING (src/policy.py:2)', ['uses attribute close'], function='m:standing', places=('src/policy.py:2',))]
    assert _block(one)[1] == 'not compared: standing (policy.py:2) (uses attribute close) -> not a failure'
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


def test_the_not_compared_line_says_each_reason_the_sealed_comparison_gives_once_and_whole():
    """5.0 gate (GB-3): every reason ended `, which the sealed comparison does not run`, so the line of Planning Tool's
    TimeRangeSelector, loadPlanning and PlanningGrid repeated that clause for each reason and cut through the first one
    (`(holds a JSX element, which the sealed comparison do... is async, which the sealed comparison does not run)`). A
    reason names the construct in a few words, as the TS and Python sealed readers give it; the line keeps whole
    reasons and cuts at item boundaries."""
    from flowguard.intent.runtime import sealed
    from flowguard.intent.vitest import sealed_source
    jsx = sealed_source(b'export function TimeRangeSelector() { return <div role="group" />; }\n', 'src/T.tsx', 'TimeRangeSelector')[1]
    late = sealed_source(b'export async function loadPlanning(month: string) { return month; }\n', 'src/p.ts', 'loadPlanning')[1]
    held = sealed('def total(path):\n    with open(path) as handle:\n        return 1\n', 'total', ['x'], {})['reason']
    assert (jsx, late, held) == ('holds a JSX element', 'is async', 'holds a with statement')
    places = ('frontend/src/components/timeline/TimeRangeSelector.tsx:39', 'frontend/src/services/api/planning.api.ts:12',
              'frontend/src/components/planning/PlanningGrid.tsx:88', 'backend/reports/total.py:3')
    items = [signals.not_compared(f'{name} ({place})', [reason], function=f'm:{name}', places=(place,))
             for name, place, reason in zip(('TimeRangeSelector', 'loadPlanning', 'PlanningGrid', 'total'), places,
                                            (jsx, late, jsx, held))]
    assert _block(items[:1])[1] == 'not compared: TimeRangeSelector (TimeRangeSelector.tsx:39) (holds a JSX element) -> not a failure'
    assert _block(items[:3])[1] == (
        'not compared: 3 functions: TimeRangeSelector (TimeRangeSelector.tsx:39), loadPlanning (planning.api.ts:12) and '
        'PlanningGrid (PlanningGrid.tsx:88) (holds a JSX element, or is async) -> not a failure')
    assert _block(items)[1] == 'not compared: 4 functions (holds a JSX element, is async, or 1 other reason) -> not a failure'


def test_the_not_compared_line_never_cuts_through_an_item():
    """Planning Tool (5.0 review, pt:F17): a vitest run after two `same ISO_WEEK_NUMBER` marks said `not compared: 3 items:
    ISO_WEEK_NUMBER (AbsenceCalendarCard.tsx:134), ISO_WEEK_NUMBER (UtilizationTool...mjs (not reached ...)`: its paths
    counted toward the 200 characters and the cut fell inside the second item. Paths do not count; when the line is still
    too long the reasons give way in their middle, and items that leave them no room are counted."""
    calendar = 'frontend/src/components/employee-utilization/absence-calendar/AbsenceCalendarCard.tsx:134'
    toolbar = 'frontend/src/components/employee-utilization/utilization-toolbar/UtilizationToolbar.tsx:84'
    # 5.1: the third item was the static test that did not report, which the block now prints on a line of its own
    # (test_the_map_checks_that_did_not_report_to_a_vitest_run_keep_a_line_of_their_own); a file of the same length
    # that cannot be parsed keeps the three items' shape
    legacy = 'frontend/src/legacy/weeksTable.mjs'
    lines = [signals.not_compared(f'ISO_WEEK_NUMBER ({calendar})', ['not reached by any test'],
                                  function='tsx/AbsenceCalendarCard:getIsoWeek', places=(calendar,)),
             signals.not_compared(f'ISO_WEEK_NUMBER ({toolbar})', ['not reached by any test'],
                                  function='tsx/UtilizationToolbar:getIsoWeekNumber', places=(toolbar,)),
             signals.not_compared(legacy, ['cannot be parsed: an unexpected token'], places=(legacy,))]
    # the two copies of ISO_WEEK_NUMBER by their own names (5.1), the file by its path
    assert _block(lines)[1] == (
        'not compared: 3 items: getIsoWeek (AbsenceCalendarCard.tsx:134), getIsoWeekNumber (UtilizationToolbar.tsx:84) '
        'and weeksTable.mjs (not reached by any test, or cannot be parsed: an unexpected token) -> not a failure')
    # Longer reasons give way in their middle; the items stay whole.
    long = [signals.not_compared(line.text, [reason * 3], function=line.function, places=line.places)
            for line, reason in zip(lines, ('uses imported or mutable binding getIsoWeek ', 'unsupported generator ',
                                            'cannot be parsed: an unexpected token '))]
    said = _block(long)[1]
    assert said.startswith('not compared: 3 items: getIsoWeek (AbsenceCalendarCard.tsx:134), getIsoWeekNumber '
                           '(UtilizationToolbar.tsx:84) and weeksTable.mjs (') and '...' in said, said
    assert len(said.replace('AbsenceCalendarCard.tsx:134', '').replace('UtilizationToolbar.tsx:84', '')    # as `_cap` counts
               .replace('weeksTable.mjs', '')) == signals.WIDTH, said
    # Items too long to leave the reasons their room are counted.
    named = [signals.not_compared(f'{"ISO_WEEK_NUMBER_OF_THE_CALENDAR_YEAR_" * 2}{index} ({place})', ['not reached by any test'],
                                  places=(place,)) for index, place in enumerate((calendar, toolbar, legacy))]
    assert _block(named)[1] == 'not compared: 3 items (not reached by any test) -> not a failure'


def test_the_map_checks_that_did_not_report_to_a_vitest_run_keep_a_line_of_their_own():
    """Planning Tool (V1-27, PTWF-3e): a filtered vitest run whose static test did not run printed `not compared: 4 items
    (only JSON data arguments and results are recorded, uses imported or mutable binding counter, or 1 other reason)`;
    that the map checks (every agreement, known entry and ledger entry) did not run was the `1 other reason`. Their item
    is a line of its own, before the line that sums up the others, which counts and names them as before."""
    static, reason = 'frontend/flowguard.static.test.mjs', 'map checks did not report to this vitest run'
    alone = signals.not_compared(static, [reason], places=(static,))
    others = [signals.not_compared(f'{name} (frontend/src/more.ts:{line})', [reason], function=f'ts/more:{name}',
                                   places=(f'frontend/src/more.ts:{line}',))
              for name, line, reason in (('next', 4, 'uses imported or mutable binding counter'),
                                         ('asMap', 5, 'only JSON data arguments and results are recorded'),
                                         ('fnResult', 6, 'only JSON data arguments and results are recorded'),
                                         ('later', 7, 'is async'), ('wait', 8, 'holds an await'))]
    said = f'not compared: flowguard.static.test.mjs ({reason}) -> not a failure'
    shown = _block([*others, alone])
    assert shown[0].endswith(': 0 red, 6 not compared; 1.2 s') and shown[1:] == [
        said, 'not compared: 5 functions (only JSON data arguments and results are recorded, uses imported or mutable '
              'binding counter, or 2 other reasons) -> not a failure'], shown
    shown = _block([alone, *others[:3]])
    assert shown[1:] == [said, 'not compared: 3 functions: next (more.ts:4), asMap (more.ts:5) and fnResult (more.ts:6) '
                               '(only JSON data arguments and results are recorded, or uses imported or mutable binding '
                               'counter) -> not a failure'], shown
    assert _block([alone])[1:] == [said]
    # a run whose static test reported has no such line
    assert not [line for line in _block(others) if reason in line]
    assert signals.MAP_CHECKS_NOT_RUN == reason         # the reason the vitest report gives this item


def test_the_first_line_of_a_run_that_ended_early_says_what_it_did_not_cover():
    """PEMEL Studio (2026-11-23, PEMEL23-1c): a session pytest ended with INTERNALERROR after 2 of 3 tests printed
    `FlowGuard 5.0 (since 3e4ecdc): 0 red; 0.1 s`. Its note comes before the time; a finished run has none."""
    lines = [_line('not compared', 1)]
    assert signals.title(lines, baseline='a' * 40, kind='task', seconds=0.14,
                         note='run ended early (exit 3): 2 of 3 selected tests ran, the rest not checked') == (
        f'FlowGuard {VERSION} (since aaaaaaa): 0 red, 1 not compared; run ended early (exit 3): 2 of 3 selected tests '
        'ran, the rest not checked; 0.1 s')
    assert signals.title(lines, baseline='a' * 40, kind='task', seconds=0.14) == \
        f'FlowGuard {VERSION} (since aaaaaaa): 0 red, 1 not compared; 0.1 s'


def _moved_said(text, field, *places):
    """The block line of one impact line of moved writes of function `f` in src/m.py, whose step shows `field`, and
    its width as the block counts it (its places not counted)."""
    step = f'check them for this change only (python -m flowguard show {field})'
    shown = _block([Line('impact', 'impact:m:f', 'm:f', text, step, ('src/m.py:f', *places), ())])[1]
    return shown, len(shown.replace('m.py:12', '').replace('m.py:7', ''))


def test_an_impact_line_of_moved_writes_keeps_what_moved_where_and_its_other_words_give_way_first():
    """PTWF-V125, PEMEL17-18 (5.1 review): the block cut a moved-writes line in its middle, `set_default_model's
    wri...model, which it calls (model_preferences.py:10); other callers of _ap...yped reads not counted)`: what moved
    where was gone. The first fix kept that clause but cut the rest in its middle, and turned every other clause of
    the line into `...`, a dropped field, a new write and a delete too (5.1 review, FM open 0 and 1). Now only the
    other callers and the counts give way, the callers to a count first (`other callers of g: 9`); then the field lists
    are counted, the moved one last, and the list holding the step's field keeps it."""
    step = 'check them for this change only (python -m flowguard show {})'
    # the callers list becomes a count, and the counts stay where that fits
    assert _moved_said("f's writes of P.a moved to g, which it calls (src/m.py:7); other callers of g: import_default, "
                       'load_settings, reset_all and 6 more; 1 other writer, 3 readers of P', 'P.a', 'src/m.py:7') == (
        "impact: f's writes of P.a moved to g, which it calls (m.py:7); other callers of g: 9; 1 other writer, 3 readers "
        f'of P -> {step.format("P.a")}', 176)
    # then the counts go, and `...` says that something went
    assert _moved_said("f's writes of P.a, P.b moved to g, which it calls (src/m.py:7); other callers of g: import_default, "
                       'load_settings, reset_all and 6 more; 12 other writers (no writers agreement), 31 readers of P',
                       'P.a', 'src/m.py:7') == (
        "impact: f's writes of P.a, P.b moved to g, which it calls (m.py:7); other callers of g: 9; ... -> "
        f'{step.format("P.a")}', 154)
    # then the callers count
    assert _moved_said("f's writes of P.a moved to _apply_the_default_model_of_the_preferences_pane, which it calls "
                       '(src/m.py:7); other callers of _apply_the_default_model_of_the_preferences_pane: load; 1 other '
                       'writer, 3 readers of P', 'P.a', 'src/m.py:7') == (
        "impact: f's writes of P.a moved to _apply_the_default_model_of_the_preferences_pane, which it calls (m.py:7); "
        f'... -> {step.format("P.a")}', 173)
    # then the other change clauses are counted, the longest first; the one holding the step's field keeps it, and
    # the moved one keeps its names while the line fits
    assert _moved_said('f now writes P.theme, P.accent_colour, P.border_colour; its writes of P.a moved to g, which it '
                       'calls (src/m.py:7); no longer writes P.revision_note, P.revision_author; 1 other writer, 3 '
                       'readers of P', 'P.theme', 'src/m.py:7') == (
        "impact: f now writes P.theme and 2 more; its writes of P.a moved to g, which it calls (m.py:7); no longer writes "
        f'2 fields; ... -> {step.format("P.theme")}', 190)
    # where even counting every list leaves the line longer than WIDTH, nothing is counted for nothing (FM2 open 1):
    # the names and the callers count stay, only the counts go, a delete whole with its place, and the line is longer
    shown, width = _moved_said('f now writes P.theme; its writes of P.a, P.b, P.c, P.d, P.e, P.f, P.g, P.h, P.i, P.j, P.k '
                               'moved to g, which it calls (src/m.py:7); other callers of g: load; writes Q.? where it '
                               'wrote x, y, z (fields not visible: data is a parameter); no longer writes P.revision_note, '
                               'P.revision_author; now deletes P (src/m.py:12); 1 other writer, 3 readers of P', 'P.theme',
                               'src/m.py:7', 'src/m.py:12')
    assert shown == ("impact: f now writes P.theme; its writes of P.a, P.b, P.c, P.d, P.e, P.f, P.g, P.h, P.i, P.j, P.k "
                     'moved to g, which it calls (m.py:7); other callers of g: 1; writes Q.? where it wrote x, y, z (fields '
                     'not visible: data is a parameter); no longer writes P.revision_note, P.revision_author; now deletes P '
                     f'(m.py:12); ... -> {step.format("P.theme")}') and width > signals.WIDTH, shown
    # any other impact line is cut as before
    shown = _block([Line('impact', 'impact:m:f', 'm:f', 'f now writes ' + ', '.join(f'P.field_{number}' for number in range(20))
                         + '; 0 other writers, 1 reader (untyped reads not counted)', step.format('P.field_0'),
                         ('src/m.py:f',), ())])[1]
    assert len(shown) == signals.WIDTH and shown.startswith('impact: f now writes P.') and '...' in shown, shown


def test_the_moved_line_of_the_reporting_projects_keeps_a_dropped_field_a_new_write_and_a_delete():
    """5.1 review (FM open 0, 1): with PEMEL Studio's and Planning Tool's names the first fix printed a moved line
    whose other clauses were `...`, so it read as a plain relocation though the function also stopped writing a
    field, wrote a new one or deleted rows, a delete was a bare place, and the step named a field the line no longer
    named. Each clause stays; the step's field stays named; such a line is longer than WIDTH, and as no count would
    bring it within WIDTH, its names stay too (FM2 open 1: the second fix printed `no longer writes 1 field` and
    `writes of 2 fields` on these lines of 229 and more counted characters)."""
    for text, field, places in (
            ("set_default_model now writes ModelPreferences.last_changed; its writes of ModelPreferences.default_model, "
             'ModelPreferences.default_source moved to _apply_default_model, which it calls '
             '(src/pemel_service/library/model_preferences.py:11); other callers of _apply_default_model: '
             'import_default_model; no longer writes ModelPreferences.revision_note; now deletes model_preferences '
             '(src/pemel_service/library/model_preferences.py:19); 0 other writers, 1 reader (untyped reads not counted)',
             'ModelPreferences.last_changed', ('src/pemel_service/library/model_preferences.py:set_default_model',
                                               'src/pemel_service/library/model_preferences.py:11',
                                               'src/pemel_service/library/model_preferences.py:19')),
            ("assignProjectManager now writes ProjectMember.role; its writes of ProjectMember.projectId, "
             'ProjectMember.userId moved to reactivateOrCreateMember, which it calls (src/member-helpers.ts:1); other '
             'callers of reactivateOrCreateMember: inviteMember; no longer writes ProjectMember.active; now deletes '
             'ProjectMember (src/members.ts:6); 0 other writers, 1 reader of ProjectMember', 'ProjectMember.role',
             ('src/members.ts:assignProjectManager', 'src/member-helpers.ts:1', 'src/members.ts:6'))):
        step = f'check them for this change only (python -m flowguard show {field})'
        shown = _block([Line('impact', 'impact:f', 'f', text, step, places, ())])[1]
        said, _, shown_step = shown.partition(' -> ')
        assert shown_step == step and field in said, shown
        assert ' now writes ' in said and ' moved to ' in said and 'field' not in said.replace(field, ''), shown
        assert ('no longer writes ModelPreferences.revision_note' in said
                or 'no longer writes ProjectMember.active' in said), shown
        assert ('now deletes model_preferences (model_preferences.py:19)' in said
                or 'now deletes ProjectMember (members.ts:6)' in said), shown
        assert ', which it calls (model_preferences.py:11)' in said or ', which it calls (member-helpers.ts:1)' in said
    assert shown == ('impact: assignProjectManager now writes ProjectMember.role; its writes of ProjectMember.projectId, '
                     'ProjectMember.userId moved to reactivateOrCreateMember, which it calls (member-helpers.ts:1); other '
                     'callers of reactivateOrCreateMember: 1; no longer writes ProjectMember.active; now deletes '
                     'ProjectMember (members.ts:6); ... -> check them for this change only (python -m flowguard show '
                     'ProjectMember.role)'), shown


def test_a_moved_line_takes_its_least_shortened_form_that_fits_and_gets_back_what_counting_freed():
    """5.1 review (FM2 open 0, 2, 5): the second fix let the callers and the counts give way before it counted a
    field list, and never put them back when the count freed the room: `f's writes of P.alpha and 10 more moved to g,
    which it calls (prefs.py:19); ... -> ...` ended 54 characters within WIDTH without `other callers of g: 1`. Now
    what went comes back after counting where it fits, the callers count first, then the counts, then the callers'
    names (FM3 open 2: the third fix left `other callers of g: 1` where `h` fits as well); a line with two moved
    clauses keeps both whole; a line naming a helper the path queries did not see write the fields, or be called,
    every time gives way by the same rule."""
    step = 'check them for this change only (python -m flowguard show {})'
    fields = ', '.join(f'P.{name}' for name in ('alpha', 'beta', 'delta', 'epsilon', 'eta', 'gamma', 'iota', 'kappa',
                                                'lambda_', 'theta', 'zeta'))
    # the callers come back, by name where their names fit; the counts do not fit
    assert _moved_said(f"f's writes of {fields} moved to g, which it calls (src/m.py:7); other callers of g: h; 0 other "
                       'writers, 1 reader (untyped reads not counted)', 'P.alpha', 'src/m.py:7') == (
        "impact: f's writes of P.alpha and 10 more moved to g, which it calls (m.py:7); other callers of g: h; ... -> "
        f'{step.format("P.alpha")}', 169)
    # the counts come back too where they fit
    assert _moved_said(f"f's writes of {fields} moved to g, which it calls (src/m.py:7); other callers of g: h; 0 other "
                       'writers, 3 readers of P', 'P.alpha', 'src/m.py:7') == (
        "impact: f's writes of P.alpha and 10 more moved to g, which it calls (m.py:7); other callers of g: h; 0 other "
        f'writers, 3 readers of P -> {step.format("P.alpha")}', 197)
    # a long `no longer writes` list is counted, and the callers come back by name
    assert _moved_said("f's writes of P.a moved to g, which it calls (src/m.py:7); other callers of g: h, i, j; no longer "
                       f'writes {fields}; 0 other writers, 3 readers of P', 'P.a', 'src/m.py:7') == (
        "impact: f's writes of P.a moved to g, which it calls (m.py:7); other callers of g: h, i, j; no longer writes 11 "
        f'fields; ... -> {step.format("P.a")}', 183)
    # two helpers: both moved clauses stay whole, as do their names where no count brings the line within WIDTH
    shown, width = _moved_said('f now writes Prefs.theme; its writes of Prefs.model moved to _apply, which it calls '
                               '(src/m.py:7); its writes of Prefs.source moved to _apply_the_source_of_the_default_model, '
                               'which it calls (src/m.py:12); other callers of _apply: import_default; 3 other writers, 31 '
                               'readers of Prefs', 'Prefs.theme', 'src/m.py:7', 'src/m.py:12')
    assert shown == ("impact: f now writes Prefs.theme; its writes of Prefs.model moved to _apply, which it calls "
                     '(m.py:7); its writes of Prefs.source moved to _apply_the_source_of_the_default_model, which it '
                     f'calls (m.py:12); other callers of _apply: 1; ... -> {step.format("Prefs.theme")}') \
        and width > signals.WIDTH, shown
    assert _moved_said("f's writes of P.a moved to g, which it calls (src/m.py:7); its writes of P.b moved to h, which it "
                       'calls (src/m.py:12); other callers of g: load, save; other callers of h: reset; 1 other writer, 3 '
                       'readers of P', 'P.a', 'src/m.py:7', 'src/m.py:12') == (
        "impact: f's writes of P.a moved to g, which it calls (m.py:7); its writes of P.b moved to h, which it calls "
        f'(m.py:12); other callers of h: 1; ... -> {step.format("P.a")}', 198)
    # a helper the path queries did not see write the fields (or be called) every time is named whole; a list it
    # names is counted last, as a moved one is
    unseen = ' where FlowGuard did not see the {} run every time'
    assert _moved_said(f'f no longer writes P.a, P.b; it calls g (src/m.py:7), which writes them{unseen.format("writes")}; '
                       '1 other writer, 3 readers of P', 'P.a', 'src/m.py:7') == (
        f'impact: f no longer writes P.a, P.b; it calls g (m.py:7), which writes them{unseen.format("writes")}; ... -> '
        f'{step.format("P.a")}', 194)
    assert _moved_said('f no longer writes P.a, P.b, P.c, P.d, P.e, P.f, P.g, P.h, P.i; it calls g (src/m.py:7), which '
                       f'writes P.b{unseen.format("write")}; 1 other writer, 3 readers of P', 'P.b', 'src/m.py:7') == (
        f'impact: f no longer writes P.b and 8 more; it calls g (m.py:7), which writes P.b{unseen.format("write")}; ... '
        f'-> {step.format("P.b")}', 198)
    assert _moved_said(f'f no longer writes P.a, P.b; g (src/m.py:7), which it calls{unseen.format("call")}, writes them; '
                       '1 other writer, 3 readers of P', 'P.a', 'src/m.py:7') == (
        f'impact: f no longer writes P.a, P.b; g (m.py:7), which it calls{unseen.format("call")}, writes them; ... -> '
        f'{step.format("P.a")}', 193)
    shown, width = _moved_said('set_default_model no longer writes ModelPreferences.default_model, '
                               'ModelPreferences.default_source; _apply_default_model (src/m.py:7), which it calls'
                               f'{unseen.format("call")}, writes them; 1 other writer, 1 reader (untyped reads not '
                               'counted)', 'ModelPreferences.default_model', 'src/m.py:7')
    assert shown == ('impact: set_default_model no longer writes ModelPreferences.default_model, '
                     'ModelPreferences.default_source; _apply_default_model (m.py:7), which it calls'
                     f'{unseen.format("call")}, writes them; ... -> {step.format("ModelPreferences.default_model")}') \
        and width > signals.WIDTH, shown


def test_a_line_of_copies_that_take_different_parameters_never_cuts_inside_a_signature_or_a_return_type():
    """Review of 5.1 (FT open 3): the block cut such a line in the middle of a declared return type, `scope.ts:
    visibleProjects(user, projects): { org: numb...[] take different parameters`; with Planning Tool's paths and names
    the signatures and output types it asked for were what the block dropped. The return types give way first, each
    whole and the longest first, then the parameter lists, all of them; each copy's `path:function` stays, and show
    --last (`everything`) keeps every word."""
    service = 'backend/src/services/org-unit.service.ts:orgUnitService.canViewOrgUnit'
    registry = 'backend/src/services/org-unit-reference-registry.ts:listVisibleOrgUnitReferences'
    planning = 'frontend/src/components/planning/ProjectPlanningContent.tsx:visibleOrgUnits'
    shown = {service: 'org-unit.service.ts:orgUnitService.canViewOrgUnit',
             registry: 'org-unit-reference-registry.ts:listVisibleOrgUnitReferences',
             planning: 'ProjectPlanningContent.tsx:visibleOrgUnits'}

    def said(signatures, kind='red'):
        text, step = signals.copies_parameters(signatures)
        subject = 'same ORG_UNIT_SCOPE disagreed at task start: ' if kind == 'before' else 'same ORG_UNIT_SCOPE: '
        line = Line(kind, 'same:ORG_UNIT_SCOPE', signals.PARAMETERS, subject + text,
                    signals.BEFORE_STEP if kind == 'before' else step, tuple(place for place, _ in signatures))
        whole = _block([line], everything=True)[1]
        assert whole == f'{kind}: {line.text} -> {line.step}'.replace(service, shown[service]).replace(
            registry, shown[registry]).replace(planning, shown[planning])
        return _block([line])[1]
    tail = 'take different parameters -> ' + signals.PARAMETERS_STEP
    # the longest return type gives way whole; the other stays
    assert said([(service, '(user, orgUnit): boolean'), (registry, '(user, orgUnits): OrgUnitReference[]')]) == (
        'red: same ORG_UNIT_SCOPE: org-unit.service.ts:orgUnitService.canViewOrgUnit(user, orgUnit): boolean and '
        f'org-unit-reference-registry.ts:listVisibleOrgUnitReferences(user, orgUnits) {tail}')
    # a shorter step leaves room for both
    assert said([(service, '(user, orgUnit): boolean'), (registry, '(user, orgUnits): OrgUnitReference[]')], 'before') == (
        'before: same ORG_UNIT_SCOPE disagreed at task start: org-unit.service.ts:orgUnitService.canViewOrgUnit(user, '
        'orgUnit): boolean and org-unit-reference-registry.ts:listVisibleOrgUnitReferences(user, orgUnits): '
        'OrgUnitReference[] take different parameters -> leave it unless your task is about it')
    # a return type that holds the words between the copies (`, `, ` and `) gives way whole too, and the next one
    # where the line is still too long
    assert said([(service, '(user, orgUnit): Promise<boolean>'),
                 (registry, "(user, orgUnits, options): Promise<Map<'view and edit', OrgUnitReference[]>>")]) == (
        'red: same ORG_UNIT_SCOPE: org-unit.service.ts:orgUnitService.canViewOrgUnit(user, orgUnit) and '
        f'org-unit-reference-registry.ts:listVisibleOrgUnitReferences(user, orgUnits, options) {tail}')
    # then the parameter lists, all of them; the copies' names stay
    long = [(service, '(authenticatedUser, orgUnitWithMembers): Promise<boolean>'),
            (registry, '(authenticatedUser, orgUnitsWithMembers, includeArchived): Promise<OrgUnitReference[]>')]
    assert said(long) == ('red: same ORG_UNIT_SCOPE: org-unit.service.ts:orgUnitService.canViewOrgUnit and '
                          f'org-unit-reference-registry.ts:listVisibleOrgUnitReferences {tail}')
    # a rule bound to their anchor states them in its red, cut the same way
    text, _ = signals.copies_parameters(long)
    rule = Line('red', 'rule:SCOPE', 'SCOPE', 'rule SCOPE: same anchor ORG_UNIT_SCOPE: ' + text,
                'inspect rule tests/intent/scope_rule.py:3 and correct its source, binding or regression rows',
                ('tests/intent/scope_rule.py:3', service, registry))
    assert _block([rule])[1] == (
        'red: rule SCOPE: same anchor ORG_UNIT_SCOPE: org-unit.service.ts:orgUnitService.canViewOrgUnit and '
        'org-unit-reference-registry.ts:listVisibleOrgUnitReferences take different parameters -> inspect rule '
        'scope_rule.py:3 and correct its source, binding or regression rows')
    # Review of 5.1 (FT2 open 1): a parenthesis inside a quoted default (a Python copy's parameters as a comparison
    # spells them) closes no parameter list; the line was cut in its middle, inside the signature and into `take`
    for default in ("label=')'", "label='it\\'s )'", 'label="("'):
        assert said([(service, f'(user, {default}, orgUnit): Promise<boolean>'),
                     (registry, '(user, orgUnits): Promise<OrgUnitReference[]>')]) == (
            f'red: same ORG_UNIT_SCOPE: org-unit.service.ts:orgUnitService.canViewOrgUnit(user, {default}, orgUnit) and '
            f'org-unit-reference-registry.ts:listVisibleOrgUnitReferences(user, orgUnits) {tail}')
    # of more than three copies three are named, the others counted, as before
    assert said([(service, '(user, orgUnit): boolean'), (registry, '(user, orgUnits): OrgUnitReference[]'),
                 (planning, '(orgUnits, user): OrgUnit[]'), ('x/a.ts:f', '(a)'), ('x/b.ts:g', '(b)')], 'before') == (
        'before: same ORG_UNIT_SCOPE disagreed at task start: org-unit.service.ts:orgUnitService.canViewOrgUnit(user, '
        'orgUnit): boolean, org-unit-reference-registry.ts:listVisibleOrgUnitReferences(user, orgUnits), '
        'ProjectPlanningContent.tsx:visibleOrgUnits(orgUnits, user) and 2 other copies take different parameters -> '
        'leave it unless your task is about it')


def test_a_single_not_compared_item_keeps_its_name_and_place_and_its_reasons_give_way_first():
    """H4-3: one not compared item whose own text besides its paths and places was longer than about 125 characters
    lost its name and place (`not compared: 1 function (not reached by any test) -> not a failure`). Its reasons give
    way first, then its text before its place, in the middle; the place stays whole and the line keeps WIDTH."""
    calendar = 'frontend/src/components/calendars/AbsenceCalendarCard.tsx:134'
    def line(subject, reason):      # the function is named `subject` (the block names a function by its own name)
        said = _block([signals.not_compared(f'{subject} ({calendar})', [reason], function=f'tsx/AbsenceCalendarCard:{subject}',
                                            places=(calendar,))])[1]
        assert len(said.replace('AbsenceCalendarCard.tsx:134', '')) <= signals.WIDTH, said
        return said
    said = line('Q' * 230, 'not reached by any test')
    assert said.startswith('not compared: QQQ') and '...' in said and said.endswith(
        'QQQ (AbsenceCalendarCard.tsx:134) (not reached by any test) -> not a failure') \
        and len(said.replace('AbsenceCalendarCard.tsx:134', '')) == signals.WIDTH, said
    # A long reason gives way before the name, down to REASONS_KEPT characters; then the name gives way too.
    name = 'ISO_WEEK_NUMBER_OF_THE_CONFIGURED_CALENDAR_YEAR_' * 2
    said = line(name, 'uses imported or mutable binding ' + 'x' * 150)
    assert said.startswith(f'not compared: {name} (AbsenceCalendarCard.tsx:134) (uses imported or mutable binding...x') \
        and said.endswith('x...) -> not a failure') and len(said.replace('AbsenceCalendarCard.tsx:134', '')) == signals.WIDTH, said
    said = line(name * 2, 'uses imported or mutable binding ' + 'x' * 150)
    reason = said.rpartition(' (')[2].removesuffix(') -> not a failure')
    assert said.startswith('not compared: ISO_WEEK') and '...' in said.partition(' (Absence')[0] \
        and ' (AbsenceCalendarCard.tsx:134) (' in said and len(reason) == signals.REASONS_KEPT \
        and len(said.replace('AbsenceCalendarCard.tsx:134', '')) == signals.WIDTH, said
    assert line('ISO_WEEK_NUMBER', 'not reached by any test') == (
        'not compared: ISO_WEEK_NUMBER (AbsenceCalendarCard.tsx:134) (not reached by any test) -> not a failure')


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
            frame = [line for line in block if 'caf' not in line and '会' not in line]
            assert all(line.isascii() for line in frame), frame


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


def test_an_old_rule_finding_is_before_with_the_rules_own_step_where_its_files_are_touched():
    """Review of 5.1 (FT3 open 0): a rule's red that is its anchor's copies taking the different parameters they took at
    the task start is old (`Engine.anchor_errors`): its line is before, reads on after a colon as the copies' before line
    does, keeps the rule's own step, and is touched where the rule's file or a copy's file is."""
    what = ('same anchor PROJECT_SCOPE: scope.py:can_view(user, project) and scope.py:visible_projects(user, projects) '
            'take different parameters')
    step = 'inspect rule scope_rule.py:3 and correct its source, binding or regression rows'
    issue = signals.finding('rule', 'rule:SCOPE', 'rule SCOPE', [what], step, places=('scope_rule.py:3', 'scope.py:can_view'),
                            files=('tests/intent/scope_rule.py', 'scope.py'), detail=[step], fresh=False)
    lines, _ = signals.deliver([issue], touched_functions=(), touched_files={'scope.py'})
    assert [(line.kind, line.text, line.step) for line in lines] == [
        ('before', f'rule SCOPE was broken at task start: {what}', step)], lines
    assert signals.deliver([issue], touched_functions=(), touched_files={'other.py'})[0] == []
    assert [line.kind for line in signals.deliver([issue], touched_functions=(), touched_files=(), everything=True)[0]] == [
        'before']
    # this change's: red, as every rule's red
    fresh = signals.finding('rule', 'rule:SCOPE', 'rule SCOPE', [what], step, places=('scope_rule.py:3',))
    assert [(line.kind, line.text, line.step) for line in signals.deliver([fresh], touched_functions=(), touched_files=())[0]] == [
        ('red', f'rule SCOPE: {what}', step)]


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
    # the detail holds the other inputs: the one the line shows is not printed twice (5.0.1 listed every input there)
    assert line.detail == ('(days=9) was False, now True', "(days=7) was 'x', now raises ValueError: no")
    assert signals.changed_line('late', 'm:late', 'm.py', 0, [({}, 1, 2)], 1, why='its code changed').detail == \
        ('no flowguard comment: compared because its code changed',)
    assert signals.changed_line('late', 'm:late', 'm.py', 0, [({}, 1, 2)], 1).detail == ()    # a comment


def test_a_changed_line_takes_list_and_dict_inputs():
    """A recorded input is any JSON value: lists and dicts are compared by their JSON (equal JSON is one value),
    never hashed."""
    rows = [({'items': [5], 'order': {'b': 1, 'a': 2}}, 5, 6), ({'items': [1, 2], 'order': {'a': 2, 'b': 1}}, 3, 4),
            ({'items': [1, 2], 'order': {'a': 1}}, 3, 5)]
    line = signals.changed_line('TOTAL', 'calc:total', 'calc.py', 2, rows, 3)
    assert line.text == 'TOTAL (calc.py:2): (items=[1, 2], order={"a": 1}) was 3, now 5; 3/3 inputs differ', line
    assert line.detail[0] == '(items=[5], order={"a": 2, "b": 1}) was 5, now 6', line


SNAPSHOTS = [   # Planning Tool's G54: parseSnapshotConfig gained one key, the others kept their values
    ({'text': '{"baseline":"b1","reportVersion":2,"version":3}'}, {'baseline': 'b1', 'reportVersion': 2, 'version': 3},
     {'baseline': 'b1', 'demandPeriodConvention': 'legacy-half-open', 'reportVersion': 2, 'version': 3}),
    ({'text': '{"version":4}'}, {'baseline': 'none', 'reportVersion': 1, 'version': 4},
     {'baseline': 'none', 'demandPeriodConvention': 'legacy-half-open', 'reportVersion': 1, 'version': 4}),
    ({'text': '{"version":5,"inclusive":true}'}, {'baseline': 'none', 'reportVersion': 1, 'version': 5},
     {'baseline': 'none', 'demandPeriodConvention': 'inclusive', 'reportVersion': 1, 'version': 5})]


def test_a_changed_dict_result_names_the_keys_that_changed_and_keeps_its_full_values_in_the_detail():
    # PTW-G54-2: 5.0.1 printed both results as whole JSON, and the block cut their middles to the same text:
    # `... was {"baseline": "b1...2, "version": 3}, now {"baseline": "b1...2, "version": 3}; 3/3 inputs differ`.
    line = signals.changed_line('parseSnapshotConfig', 'src/snapshot:parseSnapshotConfig', 'src/snapshot.ts', 1, SNAPSHOTS, 3,
                                why='its code changed')
    assert line.text == ("parseSnapshotConfig (src/snapshot.ts:1): (text='{\"baseline\":\"b1\",\"reportVersion\":2,\"version\":3}') "
                         "now adds demandPeriodConvention='legacy-half-open' (3 other keys equal); 3/3 inputs differ"), line
    assert _block([line])[1:] == [
        "changed: parseSnapshotConfig (snapshot.ts:1): (text='{\"baseline\":\"b1\"...rsion\":2,\"version\":3}') now adds "
        "demandPeriodConvention='legacy-half-open' (3 other keys equal); 3/3 inputs differ -> if you meant it, say so"]
    # each input's full values once: the shown input's without its inputs, every other one with its own keys
    assert line.detail == (
        'in full: was {"baseline": "b1", "reportVersion": 2, "version": 3}, now {"baseline": "b1", "demandPeriodConvention": '
        '"legacy-half-open", "reportVersion": 2, "version": 3}',
        "(text='{\"version\":4}') now adds demandPeriodConvention='legacy-half-open' (3 other keys equal); in full: was "
        '{"baseline": "none", "reportVersion": 1, "version": 4}, now {"baseline": "none", "demandPeriodConvention": '
        '"legacy-half-open", "reportVersion": 1, "version": 4}',
        "(text='{\"version\":5,\"inclusive\":true}') now adds demandPeriodConvention='inclusive' (3 other keys equal); in "
        'full: was {"baseline": "none", "reportVersion": 1, "version": 5}, now {"baseline": "none", "demandPeriodConvention": '
        '"inclusive", "reportVersion": 1, "version": 5}',
        'no flowguard comment: compared because its code changed'), line.detail


def test_the_keys_of_a_changed_result_are_named_by_their_path_and_compared_by_their_json():
    def said(old, new):
        return signals.changed_line('f', 'm:f', 'm.py', 1, [({'x': 1}, old, new)], 1).text.removeprefix('f (m.py:1): (x=1) ')
    # a key removed, one changed, nested keys as dotted paths and list items by index; key order is no difference
    assert said({'legacy': True, 'reportVersion': 1, 'version': 3}, {'version': 3, 'reportVersion': 2}) == \
        'now removes legacy, changes reportVersion from 1 to 2 (1 other key equal); 1/1 inputs differ'
    assert said({'summary': {'total': 3, 'days': [1, 2]}, 'rows': [{'b': 'x'}, {'b': 'y'}]},
                {'rows': [{'b': 'x'}, {'b': 'z'}], 'summary': {'days': [1, 2], 'total': 4}}) == \
        "now changes rows[1].b from 'y' to 'z' and summary.total from 3 to 4 (2 other keys equal); 1/1 inputs differ"
    # a list of dicts as long as before, item by item; at most three keys named, the others counted
    assert said([{'id': 'a', 'value': 4}], [{'id': 'a', 'value': 6}]) == \
        'now changes [0].value from 4 to 6 (1 other key equal); 1/1 inputs differ'
    assert said({'a': 1, 'b': 1, 'c': 1, 'd': 1, 'e': 1}, {'a': 2, 'b': 2, 'c': 2, 'd': 2, 'e': 1, 'f': None}) == \
        'now adds f=None, changes a from 1 to 2 and b from 1 to 2 (2 more keys differ, 1 other key equal); 1/1 inputs differ'
    # JSON tells 1 from 1.0 and from True, and NaN equals NaN, as the whole values were compared; a key that is no
    # name is quoted, and a ` -> ` keeps the line's one step
    assert said({'n': 1, 'm': 1, 'nan': float('nan')}, {'n': 1.0, 'm': True, 'nan': float('nan')}) == \
        'now changes m from 1 to True and n from 1 to 1.0 (1 other key equal); 1/1 inputs differ'
    assert said({'a b': 'x -> y'}, {'a b': 'x'}) == "now changes [\"a b\"] from 'x -\\u003e y' to 'x'; 1/1 inputs differ"
    # any other pair keeps its whole values: a scalar, a raised exception, lists of other lengths or of other values,
    # and two dicts that differ only where they are spelled alike (vitest's undefined and null are both None)
    for old, new in ((1, 2), ({'a': 1}, {'raises': 'ValueError: no'}), ([{'a': 1}], [{'a': 1}, {'a': 2}]), ([1, 2], [1, 3]),
                     ({'a': None}, {'a': None}), ({'a': 1}, [{'a': 1}])):
        assert said(old, new) == f'was {signals.value_text(old)}, now {signals.value_text(new)}; 1/1 inputs differ', (old, new)


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


def test_a_pytest_run_whose_changed_function_returns_a_list_of_dicts_names_the_keys_that_changed(tmp_path):
    # PTW-G54-2 in Python: the rows a function returns gain a key; the line names it item by item, `show --last` keeps
    # each input's full values once.
    from tests.intent_engine.test_default_runtime_signals import _project, _run
    from tests.intent_engine._cli_fixture import block, last
    policy = _project(tmp_path, '''
        def hours(days: list) -> list:
            return [{'day': day, 'hours': 8} for day in days]
    ''', '''
        from policy import hours
        def test_hours():
            assert len(hours(['mon', 'tue'])) == 2 and hours(['sun'])[0]['day'] == 'sun'
    ''')
    policy.write_text(policy.read_text().replace("'hours': 8}", "'hours': 8, 'unit': 'h'}"))
    result = _run(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    changed = ('changed: hours (policy.py:1): (days=["mon", "tue"]) now adds [0].unit=\'h\' and [1].unit=\'h\' '
               '(4 other keys equal); 2/2 inputs differ -> if you meant it, say so')
    assert block(result)[1:] == [changed], result.stdout
    shown = last(tmp_path).splitlines()
    assert shown[shown.index(changed) + 1:][:3] == [
        '    in full: was [{"day": "mon", "hours": 8}, {"day": "tue", "hours": 8}], now [{"day": "mon", "hours": 8, "unit": "h"}, '
        '{"day": "tue", "hours": 8, "unit": "h"}]',
        '    (days=["sun"]) now adds [0].unit=\'h\' (2 other keys equal); in full: was [{"day": "sun", "hours": 8}], now '
        '[{"day": "sun", "hours": 8, "unit": "h"}]',
        '    no flowguard comment: compared because its code changed'], shown


def _entry_point(root, *arguments, vitest=None):
    """(exit code, stdout, stderr) of one real run in `root`: pytest (no arguments), `python -m flowguard ARGUMENTS`
    (check, check --static) or, with `vitest` (the vitest home folder), `vitest run`; escapes decoded, and the
    colours vitest writes where it detects CI removed."""
    import os
    import subprocess
    import sys
    from tests.intent_engine import _cli_fixture
    from tests.intent_engine.test_default_runtime_signals import _run
    from tests.intent_engine.test_vitest_adapter import ANSI, _environment, _tool
    if vitest is not None:
        result = subprocess.run([_tool('node'), str(vitest / 'node_modules/vitest/vitest.mjs'), 'run'], cwd=root,
                                capture_output=True, encoding='utf-8', timeout=600, env=_environment())
    elif arguments:
        result = subprocess.run([sys.executable, '-c', _cli_fixture._BOOT, _cli_fixture.SOURCE, 'unused-marker', '', '--root',
                                 str(root), *arguments], cwd=root, capture_output=True, encoding='utf-8', timeout=300,
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8'))
    else:
        result = _run(root)
    clean = lambda text: _cli_fixture.display_text(ANSI.sub('', text))
    return result.returncode, clean(result.stdout), clean(result.stderr)


def _shaped(stdout, stderr):
    """The block a run printed last on stdout, after asserting design 4.7's shapes over a real run: every line is the
    first line, one of the kinds or `+N more:`, with at most one ` -> ` (before its step); nothing follows it on
    stdout; no `deprecated:` notice is said (5.0 removed what 4.3 announced: a removed spelling is a red line)."""
    lines = stdout.splitlines()
    start = max(index for index, line in enumerate(lines) if _re.match(r'FlowGuard \d+\.\d+ \(', line))
    block = lines[start:]
    assert all(SHAPE.match(line) and line.count(' -> ') <= 1 for line in block), block
    assert not any('deprecated' in line for line in lines), lines
    assert not any(line.startswith('deprecated: ') for line in stderr.splitlines()), stderr
    return block


def _counted(root, block):
    """{(kind, finding name): lines} of the run `show --last` keeps (the newest slot: pytest's, check's and check
    --static's, or the vitest package's), whose first line is the block's and counts every kind as many times as the
    run has lines of it (before the budget)."""
    from flowguard.intent import cache
    from flowguard.intent.config import load_config
    from collections import Counter
    last = cache.read_runs(load_config(root))[0]
    assert last['title'] == block[0], (last['title'], block)
    kinds = Counter(line['kind'] for line in last['lines'])
    counts = block[0].partition('): ')[2].rpartition('; ')[0]          # `1 red, 2 known; 3.4 s`: before the seconds
    said = {kind: int(number) for number, kind in _re.findall(r'(\d+) (known fixed\?|not compared|[a-z]+)', counts)}
    assert said == {kind: kinds[kind] for kind in [*kinds, 'red'] if kinds[kind] or kind == 'red'}, (said, kinds)
    return Counter((line['kind'], line['name']) for line in last['lines'])


def _alike(seen, situations):
    """Each situation (a finding name) has the same kinds and counts in every entry point that can see it, and is
    there: `situations` {name: the entry points that see it}."""
    for name, runs in situations.items():
        found = {run: sorted((kind, number) for (kind, other), number in seen[run].items() if other == name) for run in runs}
        assert len(set(map(tuple, found.values()))) == 1 and all(found.values()), (name, found)


def test_every_block_line_has_one_shape_and_each_entry_point_counts_a_situation_alike(tmp_path):
    """Design 4.7 over real runs of one change through pytest, check and check --static: every line of each block
    has one of the shapes and at most one ` -> `; the block is the last thing on stdout and no `deprecated:` notice
    is said; the first line counts each kind of the run's lines; and a situation each of them can see (a pair this
    change broke, the field impact of that write, a 4.2 spelling 5.0 removed: all three; copies this change made
    disagree and a function whose recorded call now answers otherwise: the two that run the tests) is the same kind,
    as often, in each."""
    from tests.intent_engine.test_default_runtime_signals import _project
    root = tmp_path / 'copies'
    policy = _project(root, """
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
        # flowguard: together account.status account.changed
        def close(db):
            db.execute("UPDATE account SET status = 'closed', changed = 1")
    """, """
        import sqlite3
        from policy import standing, preview, late_fee, available
        def test_native():
            assert standing(0) and preview(0) and late_fee(2) in (4, 6)
            with sqlite3.connect(':memory:') as db:
                assert available(db, 1)
    """, rule="""
        from flowguard.intent import rule, row
        @rule('STANDING_RULE', decides='standing', fields={'days': int}, anchor='STANDING',
              source='doc policy.txt "At most three days."')
        def STANDING_RULE(days):
            return days <= 3
        STANDING_RULE.rows(row(days=4, expect=False, why='the fourth day must remain refused'))
    """)
    policy.write_text(policy.read_text().replace('return days <= 3', 'return days <= 7', 1).replace('days * 2', 'days * 3')
                      .replace('stock > 0', 'stock >= 0').replace(', changed = 1', ''))
    seen = {}
    for run in ('pytest', 'check', 'check --static'):
        code, stdout, stderr = _entry_point(root, *([] if run == 'pytest' else run.split()))
        block = _shaped(stdout, stderr)
        assert code == 1, (run, stdout, stderr)
        # the 4.2 spelling the project uses (`sensor`) is red at its line with its rewrite, in each entry point
        assert 'red: comment policy.py:10: sensor was removed in 5.0 -> write # flowguard: same AVAILABLE' in block, (run, block)
        seen[run] = _counted(root, block)
    assert {'red', 'changed', 'impact', 'not compared'} <= {kind for kind, _ in seen['pytest']}, seen
    every, tests = ('pytest', 'check', 'check --static'), ('pytest', 'check')
    _alike(seen, {'pair:account.status>account.changed': every, 'impact:policy:close': every,
                  'comment:policy.py:10:removed': every, 'same:STANDING': tests, 'changed:policy:late_fee': tests})


def test_a_vitest_block_has_the_shapes_and_counts_the_map_checks_as_check_and_check_static_do(vitest_home):
    """The same over a TypeScript change through check --static, check and a real vitest run, whose block joins the
    map checks of its static test: two declarations this change made differ (all three), copies it made disagree
    and a changed function's recorded call (vitest alone runs the TypeScript)."""
    from tests.intent_engine.test_vitest_adapter import VITEST, _commit, _flowguard
    root = vitest_home / 'shapes'
    _commit(root, {
        'package.json': '{"name":"shapes","private":true,"type":"module","scripts":{"test":"vitest run"},'
                        '"devDependencies":{"vitest":"' + VITEST + '"}}',
        'src/a.ts': "export type Kind = 'a' | 'b';\n// flowguard: same LIMIT\nexport function over(x: number): boolean {\n  return x > 3;\n}\n",
        'src/b.ts': "export type Kind = 'a' | 'b';\n// flowguard: same LIMIT\nexport const enough = (x: number): boolean => x > 3;\n",
        'tests/app.test.ts': ("import { it, expect } from 'vitest';\nimport { over } from '../src/a';\nimport { enough } from '../src/b';\n"
                              "it('real', () => { expect(over(4)).toBe(true); expect(typeof enough(4)).toBe('boolean'); });\n"),
    })
    assert _flowguard(root, 'init')[0] == 0
    _commit(root, message='wired')
    other = root / 'src/b.ts'
    other.write_text(other.read_text(encoding='utf-8').replace("'a' | 'b';", "'a' | 'b' | 'c';").replace('x > 3', 'x > 4'),
                     encoding='utf-8', newline='\n')
    seen = {}
    for run in ('check --static', 'check', 'vitest'):
        code, stdout, stderr = (_entry_point(root, vitest=vitest_home) if run == 'vitest' else _entry_point(root, *run.split()))
        assert code == (run == 'vitest'), (run, stdout, stderr)
        seen[run] = _counted(root, _shaped(stdout, stderr))
    _alike(seen, {'declarations:Kind': ('check --static', 'check', 'vitest'), 'same:LIMIT': ('vitest',),
                  'changed:typescript/src/b.ts:enough': ('vitest',)})


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


def _pemel_mod(root):
    """PEMEL Studio's shape (2026-11-23): app/mod.py edited after the task start, three tests of it in tests/test_a.py, and
    a conftest whose hook or test stops the session as MODE says."""
    from tests.intent_engine.test_static_check import _commit
    from tests.intent_engine.test_default_runtime_signals import _git
    _commit(root, {
        'pyproject.toml': '[tool.pytest.ini_options]\npythonpath = ["."]\n',
        'app/__init__.py': '',
        'app/mod.py': 'def head():\n    return 1\n\n\ndef area(w, h):\n    return w * h\n\n\ndef tail(x):\n    return x + 1\n',
        'conftest.py': """
            import os


            def pytest_runtest_logreport(report):
                if os.environ.get('MODE') == 'internal' and report.nodeid.endswith('test_two') and report.when == 'teardown':
                    raise RuntimeError('a plugin hook failed')
        """,
        'tests/test_a.py': """
            import os
            from app.mod import area


            def test_one():
                assert os.environ.get('MODE') != 'fail'
                assert area(2, 3) == 6


            def test_two():
                if os.environ.get('MODE') == 'interrupt':
                    raise KeyboardInterrupt
                assert area(2, 2) == 4


            def test_three():
                assert area(1, 1) == 1
        """})
    mod = root / 'app/mod.py'
    mod.write_text(mod.read_text(encoding='utf-8').replace('w * h', 'h * w'), encoding='utf-8')
    return _git(root, 'rev-parse', 'HEAD').strip()[:7]


def test_the_first_line_of_a_pytest_session_that_ended_early_counts_the_tests_that_ran(tmp_path):
    """PEMEL23-1c: a session pytest ended early (INTERNALERROR after 2 of 3 tests, exit 3) printed a plain
    `FlowGuard 5.0 (since 3e4ecdc): 0 red; 0.1 s`: nothing said that the run stopped or that a selected test never ran.
    An internal error, an interrupt and -x each say so in the first line, with the exit the shell sees and how many of
    the selected tests ran; show --last keeps that line. A finished run, and one that only collects, says nothing."""
    import os
    from tests.intent_engine.test_plugin import run
    from tests.intent_engine._cli_fixture import block, last
    head = _pemel_mod(tmp_path)
    untimed = lambda line: line.rpartition('; ')[0]
    first = f'FlowGuard {VERSION} (since {head}): 0 red'     # the first session records HEAD as the task start
    for mode, options, code, ran in (('internal', (), 3, 2), ('interrupt', (), 2, 1), ('fail', ('-x',), 1, 1)):
        result = run(tmp_path, '-p', 'no:randomly', *options, env=dict(os.environ, MODE=mode))
        shown = block(result)
        assert result.returncode == code and untimed(shown[0]) == (
            f'{first}; run ended early (exit {code}): {ran} of 3 selected tests ran, the rest not checked'), (mode, result.stdout)
        assert untimed(last(tmp_path).splitlines()[2]) == untimed(shown[0]), mode
    environment = {name: value for name, value in os.environ.items() if name != 'MODE'}
    for options in ((), ('--collect-only',)):
        result = run(tmp_path, *options, env=environment)
        assert result.returncode == 0 and untimed(block(result)[0]) == first, (options, result.stdout)


def test_the_early_end_and_the_completion_policy_count_the_same_tests(tmp_path):
    """skip_policy = "forbid" fails a session that pytest.exit(returncode=0) ended, naming the selected tests that never
    ran; the first line counts the same tests, and the exit the policy set."""
    from tests.intent_engine.test_plugin import run
    head = _pemel_mod(tmp_path)
    (tmp_path / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath = ["."]\n[tool.flowguard]\nskip_policy = "forbid"\n',
                                             encoding='utf-8')
    (tmp_path / 'tests/test_0.py').write_text('import pytest\n\n\ndef test_exit():\n    pytest.exit("enough", returncode=0)\n',
                                              encoding='utf-8')
    result = run(tmp_path, '-p', 'no:randomly', 'tests/test_0.py', 'tests/test_a.py')
    assert result.returncode == 1 and '; 4 selected test(s) never ran (' in result.stderr, result.stderr
    # pytest's own `!!! _pytest.outcomes.Exit: enough !!!` follows the block here
    first = [line for line in result.stdout.splitlines() if line.startswith(f'FlowGuard {VERSION} (')]
    assert [line.rpartition('; ')[0] for line in first] == [f'FlowGuard {VERSION} (since {head}): 0 red; run ended early '
                                                            '(exit 1): 0 of 4 selected tests ran, the rest not checked'], result.stdout


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
    # code-1: the line names the finding's place this change touched, with the count of its places
    assert block(result)[1:] == ['known: known.iso-weeks at policy.py:weeks (1 of 2 places): Has 2025 52 or 53 ISO weeks? '
                                 '-> an open question for the owner, not asked yet'], result.stdout
    shown = last(root).splitlines()
    assert '    ask: Has 2025 52 or 53 ISO weeks?' in shown, shown
    # Without the entry the same disagreement is before, with the input it is about.
    (root / '.flowguard/known.toml').unlink()
    result = _run(root)
    assert result.returncode == 0 and block(result)[1:] == [
        'before: same WEEKS disagreed at task start on year=2025: policy.py:weeks returns 52, policy.py:iso_weeks returns 53 '
        '-> leave it unless your task is about it', "loosened: known.iso-weeks removed from known.toml -> name it in your report; loosening an agreement is the owner's decision"
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
    assert block(result)[1:] == ['known fixed?: known.iso-weeks: copies of WEEKS now agree -> it was left on purpose: '
                                 'if you meant to fix it, remove known.iso-weeks and say so in your report'], result.stdout
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
    policy = _project(root, '# flowguard: same STANDING\ndef standing(days: int) -> bool:\n    return days <= 3\n',
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
        'known fixed?: known.days: rule:STANDING_RULE no longer found -> it was left on purpose: if you meant to fix it, remove known.days and say so in your report'
    ], result.stdout
    # The rule's items not run (another test selected): nothing says it is fixed; the touched site is known.
    result = _run(root, 'tests/test_case.py')
    assert result.returncode == 0 and block(result)[1:] == [
        'known: known.days at policy.py:standing -> left as it is on purpose; yours to change only if your task is about it'], result.stdout


def test_an_intent_item_failing_only_on_a_source_broken_at_task_start_passes_and_is_before_where_touched(tmp_path):
    """Design 6.1: the exit code follows red only. A quote already gone from its document at the baseline makes no
    verdict red; it is a before line where the change touches the file declaring the rule, else nothing."""
    from tests.intent_engine.test_default_runtime_signals import _git, _project, _run
    from tests.intent_engine._cli_fixture import block
    root = tmp_path / 'gone'
    _project(root, '# flowguard: same STANDING\ndef standing(days: int) -> bool:\n    return days <= 3\n',
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
    policy = _project(tmp_path, '# flowguard: same STANDING\ndef standing(days: int) -> bool:\n    return days <= 3\n',
                      'from policy import standing\ndef test_native():\n    assert standing(4) in (True, False)\n', rule='''
        from flowguard.intent import rule
        @rule('STANDING_RULE', decides='standing', fields={'days': int}, anchor='STANDING', source='At most three days.')
        def STANDING_RULE(days):
            return days <= 3
    ''')
    policy.write_text(policy.read_text().replace('days <= 3', 'days <= 5'))
    load = ('red: load tests/intent/decisions.py:2: STANDING_RULE: source needs rule.<id> (a rule of .flowguard/rules.toml), '
            'R<id> "exact words", R<id> picked "exact words", owner R-id, doc PATH "quoted words", assumed: or lesson: '
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


def test_a_line_whose_step_leaves_its_text_no_room_keeps_its_words_and_a_shorter_step_still_cuts_them():
    # 5.1: a copies line's step names how its copies resemble, who decides and the route (R101), more than WIDTH by
    # itself; the text then gave way to `orders.py:preview_accept i...e orders.py:accept`, too long still and unreadable.
    places = ('orders.py:preview_accept', 'orders.py:accept')
    text = 'copies of ACCEPT: orders.py:preview_accept is a diverged copy of the reference orders.py:accept'
    long = ('they resemble the reference accept (structural similarity 1.00); calling accept or marking each copy same ACCEPT '
            "makes them agree; whether they must stay separate is the owner's decision; if they must: python -m flowguard "
            'known add copies:ACCEPT --act ignore --why TEXT')
    line = signals.Line('impact', 'copies:ACCEPT', 'orders:preview_accept', text, long, places)
    assert _block([line])[1] == f'impact: {text} -> {long}'
    # a step that leaves the line room within WIDTH: the words between the places give way, as before
    filler = 'x' * 150
    said = _block([signals.Line('impact', 'copies:ACCEPT', 'orders:preview_accept', text, filler, places)])[1]
    assert said == ('impact: copies of ACCEPT: orders.py:preview_accept is a div...ference orders.py:accept -> ' + filler), said
    assert len(said.replace(places[0], '').replace(places[1], '')) == signals.WIDTH, said
