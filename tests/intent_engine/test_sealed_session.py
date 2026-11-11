"""Post-session comparison uses source, never a second live project call."""
import json
import sqlite3

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
