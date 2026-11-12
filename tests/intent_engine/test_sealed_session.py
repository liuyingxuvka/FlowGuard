"""Post-session comparison uses source, never a second live project call."""
import json
from pathlib import Path
import sqlite3
import textwrap

import pytest

from tests.intent_engine.test_default_runtime_signals import _git, _project, _run, _text


def _report(root):
    with sqlite3.connect(root / '.flowguard/cache/map.sqlite') as con:
        return json.loads(con.execute("SELECT v FROM meta WHERE k='runtime_observations'").fetchone()[0])['items']


def test_changed_uses_only_the_actual_json_input_after_tests(tmp_path):
    path = _project(tmp_path, 'def answer(n):\n    return n + 1\n', '''
        from policy import answer
        def test_answer():
            assert answer(2) in (3, 4)
    ''')
    path.write_text(path.read_text().replace('n + 1', 'n + 2'))
    result = _run(tmp_path)
    assert result.returncode == 0, _text(result)
    item = next(item for item in _report(tmp_path)['items'] if item['name'] == 'answer')
    assert item['total'] == 1 and item['changed'] == [[{'n': 2}, 3, 4]], item


def test_same_copies_are_compared_without_importing_the_other_module(tmp_path):
    path = _project(tmp_path, '# flowguard: same ANSWER\ndef answer(n):\n    return n + 1\n', '''
        from policy import answer
        def test_answer():
            assert answer(2) == 3
    ''')
    other = tmp_path / 'other.py'
    other.write_text('from pathlib import Path\nPath("unwanted").write_text("imported")\n'
                     '# flowguard: same ANSWER\ndef answer(n):\n    return n + 1\n')
    _git(tmp_path, 'add', 'other.py')
    _git(tmp_path, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'equal copies')
    other.write_text(other.read_text().replace('n + 1', 'n + 2'))
    result = _run(tmp_path)
    assert result.returncode == 1, _text(result)
    assert not (tmp_path / 'unwanted').exists()
    report = _report(tmp_path)
    assert any('ANSWER' in line for line in report['red']), report
    assert not report['before'], report


def test_preexisting_copy_difference_is_before_and_not_a_test_failure(tmp_path):
    path = _project(tmp_path, '# flowguard: same ANSWER\ndef answer(n):\n    return n + 1\n', '''
        from policy import answer
        def test_answer():
            assert answer(2) == 3
    ''')
    other = tmp_path / 'other.py'
    other.write_text('# flowguard: same ANSWER\ndef answer(n):\n    return n + 2\n')
    _git(tmp_path, 'add', 'other.py')
    _git(tmp_path, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'existing disagreement')
    path.write_text(path.read_text() + '\n# documentation-only edit\n')
    result = _run(tmp_path)
    assert result.returncode == 0, _text(result)
    report = _report(tmp_path)
    assert not report['red'] and any('ANSWER' in line for line in report['before']), report
    assert 'before: ' in _text(result)


def test_equal_exceptions_are_not_reported_as_unchanged(tmp_path):
    path = _project(tmp_path, 'def answer(n):\n    raise ValueError("no result")\n', '''
        import pytest
        from policy import answer
        def test_answer():
            with pytest.raises(ValueError, match='no result'):
                answer(2)
    ''')
    path.write_text(path.read_text().replace('raise ValueError', 'n += 0\n    raise ValueError'))
    result = _run(tmp_path)
    assert result.returncode == 0, _text(result)
    item = next(item for item in _report(tmp_path)['items'] if item['name'] == 'answer')
    assert item['status'] == 'grey' and not item['changed'] and not item['rows'], item
    assert 'same exception' in ' '.join(item['reasons'])


def test_nested_calls_keep_their_own_recorded_identity(tmp_path):
    path = _project(tmp_path, 'def inner(n):\n    return n + 1\n\ndef outer(n):\n    return inner(n) * 2\n', '''
        from policy import outer
        def test_outer():
            assert outer(2) in (6, 8)
    ''')
    path.write_text(path.read_text().replace('n + 1', 'n + 2').replace('inner(n) * 2', '2 * inner(n)'))
    result = _run(tmp_path)
    assert result.returncode == 0, _text(result)
    items = {item['name']: item for item in _report(tmp_path)['items'] if item.get('file') == 'policy.py'}
    assert items['inner']['changed'] == [[{'n': 2}, 3, 4]], items
    assert items['outer']['changed'] == [[{'n': 2}, 6, 8]], items


def test_same_copies_also_try_the_numbers_their_sealed_helpers_and_constants_use(tmp_path):
    # The boundary 7 is neither a recorded call, its neighbour, nor a literal inside `standing`: it is the
    # module constant its same-file helper reads. The copies agreed at the baseline (both 3) and now
    # disagree from 4 to 7, so the union must reach 7 (design 4.5: the function's numeric constants).
    path = _project(tmp_path, 'GRACE = 3\n\ndef within(days):\n    return days <= GRACE\n\n'
                    '# flowguard: same STANDING\ndef standing(days: int) -> bool:\n    return within(days)\n\n'
                    '# flowguard: same STANDING\ndef preview(days: int) -> bool:\n    return days <= 3\n', '''
        from policy import preview, standing
        def test_copies():
            assert standing(0) and preview(0)
            assert not standing(9) and not preview(9)
    ''')
    path.write_text(path.read_text().replace('GRACE = 3', 'GRACE = 7'))
    result = _run(tmp_path)
    text = _text(result)
    assert result.returncode == 1 and '1 passed' in result.stdout, text
    report = _report(tmp_path)
    red, = [line for line in report['red'] if 'STANDING' in line]
    assert 'days=7' in red and not report['before'], report


def test_a_copy_that_cannot_run_sealed_does_not_hide_a_disagreement_between_the_others(tmp_path):
    path = _project(tmp_path, '# flowguard: same ANSWER\ndef answer(n):\n    return n + 1\n', '''
        from other import answer as other
        from policy import answer
        from third import answer as third
        def test_answer():
            assert answer(2) == other(2) == third(2) == 3
    ''')
    (tmp_path / 'settings.py').write_text('STEP = 1\n')
    (tmp_path / 'other.py').write_text('from settings import STEP\n# flowguard: same ANSWER\ndef answer(n):\n    return n + STEP\n')
    (tmp_path / 'third.py').write_text('# flowguard: same ANSWER\ndef answer(n):\n    return n + 1\n')
    _git(tmp_path, 'add', 'settings.py', 'other.py', 'third.py')
    _git(tmp_path, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'three copies')
    path.write_text(path.read_text().replace('n + 1', 'n + 1 if n != 3 else 0'))
    result = _run(tmp_path)
    text = _text(result)
    assert result.returncode == 1 and '1 passed' in result.stdout, text
    report = _report(tmp_path)
    red, = [line for line in report['red'] if 'ANSWER' in line]
    assert 'n=3' in red and '(plus 1 copies without a result for this input)' in red, red
    assert any('ANSWER: other.py:3 answer uses unavailable binding STEP' in reason
               for item in report['items'] for reason in item.get('reasons', ())), [item.get('reasons') for item in report['items']]


def _copies(tmp_path, source, test, change):
    """Two or more same-name copies in policy.py, committed, then `change` (old, new) applied once."""
    path = _project(tmp_path, source, test)
    path.write_text(path.read_text().replace(*change, 1))
    result = _run(tmp_path)
    return result, _text(result), _report(tmp_path)


def _named(lines, name):
    return [line for line in lines if name in line]


def _reasons(report):
    return [reason for item in report['items'] for reason in item.get('reasons', ())]


# ---- design 4.5: the union of recorded calls, each recorded number +-1 and the copies' constants -----------

def test_a_negative_constant_of_a_copy_is_in_the_union(tmp_path):
    # Both copies refused below -5 at the baseline; one now refuses below -3. -5 is the literal `-5`, not 5.
    result, text, report = _copies(tmp_path, '''
        # flowguard: same STANDING
        def standing(days: int) -> bool:
            return days >= -5
        # flowguard: same STANDING
        def preview(days: int) -> bool:
            return days >= -5
    ''', '''
        from policy import standing, preview
        def test_native():
            assert standing(0) and preview(0)
    ''', ('return days >= -5', 'return days >= -3'))
    red, = _named(report['red'], 'STANDING')
    assert result.returncode == 1 and 'days=-5' in red and not report['before'], text


def test_the_numbers_of_a_tuple_constant_a_copy_reads_are_in_the_union(tmp_path):
    # The copies now differ at 7 only, the second number of the tuple constant the changed copy reads.
    result, text, report = _copies(tmp_path, '''
        BOUNDS = (3, 7)
        # flowguard: same STANDING
        def standing(days: int) -> bool:
            return days <= BOUNDS[0]
        # flowguard: same STANDING
        def preview(days: int) -> bool:
            return days <= 3
    ''', '''
        from policy import standing, preview
        def test_native():
            assert standing(0) and preview(0)
    ''', ('return days <= BOUNDS[0]', 'return days <= BOUNDS[0] or days == BOUNDS[1]'))
    red, = _named(report['red'], 'STANDING')
    assert result.returncode == 1 and 'days=7' in red and not report['before'], text


def test_every_constant_is_compared_even_after_many_recorded_calls(tmp_path):
    # 20 distinct far calls per copy fill 40 of the 64 inputs, and their neighbours would fill the rest:
    # the constants 3 and 7 still come before any neighbour.
    result, text, report = _copies(tmp_path, '''
        # flowguard: same STANDING
        def standing(days: int) -> bool:
            return days <= 3
        # flowguard: same STANDING
        def preview(days: int) -> bool:
            return days <= 3
    ''', '''
        from policy import standing, preview
        def test_native():
            for days in range(100, 300, 10):
                assert not standing(days)
            for days in range(1000, 1200, 10):
                assert not preview(days)
    ''', ('return days <= 3', 'return days <= 7'))
    red, = _named(report['red'], 'STANDING')
    assert result.returncode == 1 and 'days=7' in red and not report['before'], text


def test_recorded_inputs_alone_over_the_cap_still_leave_every_constant_a_place(tmp_path):
    # Four copies, 20 distinct far calls each: 80 recorded inputs, more than the 64 compared. The constants 3
    # and 7 keep their place before the recorded inputs are cut, and the cut is named.
    copies = ''.join(f'''
        # flowguard: same STANDING
        def copy{number}(days: int) -> bool:
            return days <= 3
    ''' for number in range(4))
    test = 'from policy import copy0, copy1, copy2, copy3\ndef test_native():\n' + ''.join(
        f'    for days in range({1000 * (number + 1)}, {1000 * (number + 1) + 200}, 10):\n        assert not copy{number}(days)\n'
        for number in range(4))
    result, text, report = _copies(tmp_path, copies, test, ('return days <= 3', 'return days <= 7'))
    red, = _named(report['red'], 'STANDING')
    assert result.returncode == 1 and 'days=7' in red and not report['before'], text
    assert any('STANDING: compared on 64 inputs; 18 recorded inputs left out' in line
               for line in text.splitlines() + _reasons(report)), text


def test_the_neighbours_of_a_recorded_number_are_in_the_union(tmp_path):
    # No numeric literal: the copies now differ at 4 only, the neighbour of the recorded 3.
    result, text, report = _copies(tmp_path, '''
        # flowguard: same STANDING
        def standing(days: int) -> bool:
            return days <= len('abc')
        # flowguard: same STANDING
        def preview(days: int) -> bool:
            return days <= len('abc')
    ''', '''
        from policy import standing, preview
        def test_native():
            assert standing(3) and preview(3)
    ''', ("return days <= len('abc')", "return days <= len('abcd')"))
    red, = _named(report['red'], 'STANDING')
    assert result.returncode == 1 and 'days=4' in red and not report['before'], text


def test_a_boolean_input_never_gains_arithmetic_or_numeric_constants(tmp_path):
    # The copies agree on every boolean; they would differ on flag=2 (True + 1) or flag=3 (a constant).
    result, text, report = _copies(tmp_path, '''
        # flowguard: same SHOWN
        def shown(flag: bool, days: int) -> str:
            return 'open' if flag is True and days <= 3 else 'closed'
        # flowguard: same SHOWN
        def visible(flag: bool, days: int) -> str:
            return 'open' if flag and days <= 3 else 'closed'
    ''', '''
        from policy import shown, visible
        def test_native():
            assert shown(True, 2) == visible(True, 2) == 'open'
            assert shown(False, 2) == visible(False, 2) == 'closed'
    ''', ("flag is True and days <= 3", "flag is True and days <= 4"))
    red, = _named(report['red'], 'SHOWN')
    assert result.returncode == 1 and 'days=4' in red and 'flag=T' in red, text
    assert not report['before'] and 'flag=2' not in text and 'flag=3' not in text, text


# ---- design 4.5: each input is judged on its own against the copies' versions at the baseline -------------

def test_an_input_where_the_old_copies_both_raise_does_not_hide_a_new_break_on_another(tmp_path):
    # Both copies raise for a negative day (the neighbour -1 of the recorded 0); at 7 they agreed at the
    # baseline and differ now.
    result, text, report = _copies(tmp_path, '''
        # flowguard: same STANDING
        def standing(days: int) -> bool:
            if days < 0:
                raise ValueError('negative')
            return days <= 3
        # flowguard: same STANDING
        def preview(days: int) -> bool:
            if days < 0:
                raise ValueError('negative')
            return days <= 3
    ''', '''
        from policy import standing, preview
        def test_native():
            assert standing(0) and preview(0)
    ''', ('return days <= 3', 'return days <= 7'))
    red, = _named(report['red'], 'STANDING')
    assert result.returncode == 1 and 'days=7' in red and not report['before'], text
    assert 'baseline comparison unavailable' not in text, text


def test_an_old_disagreement_on_one_input_does_not_hide_a_new_one_on_another(tmp_path):
    # The copies already differ at 91 (before); the change breaks 4..7, where they agreed: red there.
    result, text, report = _copies(tmp_path, '''
        # flowguard: same STANDING
        def standing(days: int) -> bool:
            return days <= 3
        # flowguard: same STANDING
        def preview(days: int) -> bool:
            return days <= 3 or days == 91
    ''', '''
        from policy import standing, preview
        def test_native():
            assert standing(0) and preview(0)
    ''', ('return days <= 3\n', 'return days <= 7\n'))
    red, = _named(report['red'], 'STANDING')
    before, = _named(report['before'], 'STANDING')
    assert result.returncode == 1 and 'days=7' in red and 'days=91' not in red, text
    # At 7 both old copies returned F: the old disagreement is named only where it was.
    assert 'days=91' in before and 'days=7' not in before, text


def _three_copies(tmp_path, other_now, policy_change):
    """policy, other and third answer n + 1; at the baseline other read STEP from another module (it cannot
    run sealed there), now it is `other_now`."""
    path = _project(tmp_path, '# flowguard: same ANSWER\ndef answer(n):\n    return n + 1\n', '''
        from other import answer as other
        from policy import answer
        from third import answer as third
        def test_answer():
            assert answer(2) == other(2) == third(2) == 3
    ''')
    (tmp_path / 'settings.py').write_text('STEP = 1\n')
    (tmp_path / 'other.py').write_text('from settings import STEP\n# flowguard: same ANSWER\ndef answer(n):\n    return n + STEP\n')
    (tmp_path / 'third.py').write_text('# flowguard: same ANSWER\ndef answer(n):\n    return n + 1\n')
    _git(tmp_path, 'add', 'settings.py', 'other.py', 'third.py')
    _git(tmp_path, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'three copies')
    (tmp_path / 'other.py').write_text('# flowguard: same ANSWER\ndef answer(n):\n    return ' + other_now + '\n')
    if policy_change:
        path.write_text(path.read_text().replace('n + 1', policy_change))
    result = _run(tmp_path)
    return result, _text(result), _report(tmp_path)


def test_a_copy_whose_baseline_cannot_run_sealed_does_not_hide_a_new_break_between_the_others(tmp_path):
    # policy and third agreed at the baseline and differ now at n=3: red. Only the pairs with other, whose
    # baseline did not run, are not compared there.
    result, text, report = _three_copies(tmp_path, 'n + 1', 'n + 1 if n != 3 else 0')
    red, = _named(report['red'], 'ANSWER')
    assert result.returncode == 1 and 'n=3' in red and 'third.py:2 answer' in red, text
    assert any('ANSWER: baseline comparison unavailable' in reason and 'n=3' in reason for reason in _reasons(report)), text


def test_a_new_disagreement_where_a_baseline_could_not_run_is_not_compared_rather_than_red(tmp_path):
    # Only other now differs (at n=3), and its baseline could not run sealed: whether the copies agreed
    # there before is unknown, so the disagreement is not compared, neither red nor before.
    result, text, report = _three_copies(tmp_path, 'n + 1 if n != 3 else 0', None)
    assert result.returncode == 0 and not _named(report['red'], 'ANSWER') and not report['before'], text
    assert any('ANSWER: baseline comparison unavailable' in reason and 'n=3' in reason for reason in _reasons(report)), text


# ---- comparison due: the function itself changed (before/after), or its name has two or more copies -------

_NOT_COMPARABLE = '''
    import json
    # flowguard: same OPAQUE
    def opaque(db, days: int) -> bool:
        return days <= 3
    # flowguard: same READS
    def reads(days: int) -> bool:
        return days <= json.loads("3")
    def changed(days: int) -> bool:
        return days <= 3
'''


def test_an_unchanged_lone_same_function_in_a_changed_file_is_not_due_for_a_comparison(tmp_path):
    result, text, report = _copies(tmp_path, _NOT_COMPARABLE, '''
        from policy import opaque, reads, changed
        def test_calls():
            assert opaque(object(), 2) and reads(2) and changed(2)
    ''', ('def changed(days: int) -> bool:\n    return days <= 3', 'def changed(days: int) -> bool:\n    return days < 4'))
    assert result.returncode == 0, text
    assert not [line for line in text.splitlines() + _reasons(report) if 'OPAQUE' in line or 'READS' in line], text


def test_a_function_in_an_unchanged_file_is_not_compared_before_and_after(tmp_path):
    path = _project(tmp_path, _NOT_COMPARABLE, '''
        from policy import opaque, reads, changed
        from other import later
        def test_calls():
            assert opaque(object(), 2) and reads(2) and changed(2) and later(2)
    ''')
    (tmp_path / 'other.py').write_text('def later(days):\n    return days <= 3\n')
    _git(tmp_path, 'add', 'other.py')
    _git(tmp_path, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'other file')
    (tmp_path / 'other.py').write_text('def later(days):\n    return days < 4\n')
    result = _run(tmp_path)
    text = _text(result)
    assert result.returncode == 0 and path.read_text() == textwrap.dedent(_NOT_COMPARABLE).lstrip(), text
    lines = text.splitlines() + _reasons(_report(tmp_path))
    assert not [line for line in lines if 'OPAQUE' in line or 'READS' in line], text


def test_a_changed_function_or_a_name_with_two_copies_is_due_and_listed_when_not_comparable(tmp_path):
    result, text, report = _copies(tmp_path, _NOT_COMPARABLE + '''
    # flowguard: same TWIN
    def twin(db, days: int) -> bool:
        return days <= 3
    # flowguard: same TWIN
    def double(db, days: int) -> bool:
        return days <= 3
    ''', '''
        from policy import opaque, reads, twin, double
        def test_calls():
            assert opaque(object(), 2) and reads(2) and twin(object(), 2) and double(object(), 2)
    ''', ('return days <= json.loads("3")', 'return days < json.loads("4")'))
    assert result.returncode == 0, text
    assert any(item.get('name') == 'READS' and 'uses attribute loads' in item['reasons']
               for item in report['items']), report['items']                                      # changed itself
    assert 'TWIN: no comparable JSON result' in _reasons(report), report['items']                 # two copies
    assert not any('OPAQUE' in line for line in text.splitlines() + _reasons(report)), text       # neither


@pytest.mark.parametrize('helper, call', [
    ("from decimal import Decimal\ndef _fee(amount):\n    return 5 if amount < Decimal('100') else 0\n", 'Decimal(total)'),
    ('def _fee(pair):\n    return 5 if pair[0] < 100 else 0\n', '(total, 1)'),
], ids=['decimal', 'tuple'])
def test_a_function_whose_same_file_helper_changed_is_compared_before_and_after(tmp_path, helper, call):
    # fee itself is unchanged, but its sealed run executes _fee, whose bound moved from 100 to 50 (design 4.5:
    # the def and the same-file functions it uses). _fee is called with no JSON value, so only fee's recorded
    # call can show the change.
    path = _project(tmp_path, helper + f'# flowguard: same FEE\ndef fee(total: int) -> int:\n    return _fee({call})\n', '''
        from policy import fee
        def test_fee():
            assert fee(60) >= 0
    ''')
    path.write_text(path.read_text().replace('100', '50'))
    result = _run(tmp_path)
    text = _text(result)
    item = next((item for item in _report(tmp_path)['items'] if item.get('name') == 'FEE'), None)
    assert result.returncode == 0 and item is not None and item['changed'] == [[{'total': 60}, 5, 0]], (text, item)
    assert any(line.startswith('changed: FEE') and 'total=60' in line for line in text.splitlines()), text


# ---- a moved copy is compared with its own version at the baseline (git rename detection) ------------------

def test_moving_a_copy_keeps_its_old_difference_before(tmp_path):
    _project(tmp_path, '# flowguard: same STANDING\ndef standing(days: int) -> bool:\n    return days <= 3\n', '''
        from policy import standing
        from other import preview
        def test_native():
            assert standing(0) and preview(0)
    ''')
    (tmp_path / 'other.py').write_text('# flowguard: same STANDING\ndef preview(days: int) -> bool:\n    return days <= 3 or days == 91\n')
    _git(tmp_path, 'add', 'other.py')
    _git(tmp_path, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'two copies')
    _git(tmp_path, 'mv', 'other.py', 'moved.py')
    test = tmp_path / 'tests/test_case.py'
    test.write_text(test.read_text().replace('from other import', 'from moved import'))
    result = _run(tmp_path)
    text, report = _text(result), _report(tmp_path)
    before, = _named(report['before'], 'STANDING')
    assert result.returncode == 0 and not report['red'] and 'days=91' in before and 'moved.py' in before, text
    # the moved file's own function is unchanged: no before/after is due for it
    assert not [item for item in report['items'] if item.get('file') == 'moved.py'], report['items']


def test_the_retired_comparison_table_has_neither_a_writer_nor_a_reader(tmp_path):
    from flowguard.intent import cache, plugin
    assert not {'COMPARISONS', 'comparisons', 'save_comparisons'} & set(vars(cache)), 'retired with 4.3 (tests/RETIRED_4_3.md)'
    path = _project(tmp_path, 'def answer(n):\n    return n + 1\n', '''
        from policy import answer
        def test_answer():
            assert answer(2) in (3, 4)
    ''')
    path.write_text(path.read_text().replace('n + 1', 'n + 2'))
    result = _run(tmp_path)
    assert result.returncode == 0, _text(result)
    with sqlite3.connect(tmp_path / '.flowguard/cache/map.sqlite') as con:
        assert not con.execute("SELECT 1 FROM sqlite_master WHERE name='comparison'").fetchone()
    assert 'save_comparisons' not in Path(plugin.__file__).read_text(encoding='utf-8')
