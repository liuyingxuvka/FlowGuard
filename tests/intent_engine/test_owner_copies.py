"""Owners, copies and static leads (round 20, fixed examples 6, 8, 10, 11, 14 and 18).

Each project commits its baseline first; the working-tree edit is what `check` and pytest report.
The KWP copies come from `tests/fixtures/kwp_rounding` (sources and line numbers in its README).
"""
from pathlib import Path
import os
import re
import subprocess
import sys
import textwrap

from tests.intent_engine import _cli_fixture
from tests.intent_engine._cli_fixture import display_text as _text

from flowguard.intent import anchors

SOURCE = str(Path(__file__).resolve().parents[2])
KWP = Path(__file__).resolve().parents[1] / 'fixtures/kwp_rounding'
KWP_PATH = '[tool.pytest.ini_options]\npythonpath = ["Step1/src", "Step2/src", "Step2", "Step3/src", "Step6a", "."]\n'


def _git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), *arguments], check=True, capture_output=True, text=True, timeout=20).stdout


def _project(root, files, *, pyproject='[tool.pytest.ini_options]\npythonpath=["."]\ntestpaths=["tests"]\n'):
    for name, text in {'.gitignore': '.flowguard/cache/\n__pycache__/\n.pytest_cache/\n', 'pyproject.toml': pyproject, **files}.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip() if name.endswith('.py') else text, encoding='utf-8')
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture baseline')
    return root


def _kwp(root):
    files = {str(path.relative_to(KWP).with_suffix('')): path.read_text(encoding='utf-8') for path in KWP.rglob('*.py.txt')}
    for name, text in {'.gitignore': '.flowguard/cache/\n__pycache__/\n', 'pyproject.toml': KWP_PATH, **files}.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding='utf-8')
    return root


def _commit(root, message='fixture baseline'):
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', message)


def _pytest(root):
    bootstrap = ('import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; '
                 'raise SystemExit(pytest.main(sys.argv[1:]))')
    return subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '-q', '-p', 'flowguard.intent.plugin'], cwd=root,
                          capture_output=True, text=True, timeout=60, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))


def _check(root, *options, before_main=''):
    result = subprocess.run([sys.executable, '-c', _cli_fixture._BOOT, SOURCE, 'unused-marker', before_main,
                             '--root', str(root), 'check', *options], cwd=root, capture_output=True, text=True,
                            timeout=120, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    return result.returncode, _text(result)


def _block(text):
    """The FlowGuard block of a check's output: its first line and the lines after it of the block's shapes (stderr's
    notices and the observed pytest command follow it)."""
    lines = text.splitlines()
    start = next(index for index, line in enumerate(lines) if re.match(r'FlowGuard \d+\.\d+ \(', line))
    block = [lines[start]]
    for line in lines[start + 1:]:
        if not _cli_fixture.SHAPE.match(line):
            break
        block.append(line)
    return block


def _lines(text, prefix='lead: '):
    return [line for line in text.splitlines() if line.startswith(prefix)]


def _facts(text, file='policy.py'):
    import ast
    source = textwrap.dedent(text).lstrip()
    return anchors.source_facts(ast.parse(source), source, file[:-3], file)


# ---- comments ----------------------------------------------------------------------------------------

def test_owner_comments_name_a_reference_copy_or_a_field_with_its_writers():
    facts = _facts('''
        # flowguard: owner ROUND
        def owner(value: float) -> int:
            return int(value)
        # flowguard: sensor ROUND
        def copy(value: float) -> int:
            return int(value)
        # flowguard: owner hires.reserved writers=shop.store:reserve,shop.store:release
        # flowguard: owner hires writers=shop.store:reserve
    ''')
    rows = [(row['kind'], row['name'], row['qual'], row['owner'], tuple(row['writers'])) for row in facts['anchors']]
    assert rows == [('sensor', 'ROUND', 'owner', True, ()), ('sensor', 'ROUND', 'copy', False, ()),
                    ('owner', 'hires.reserved', '', False, ('shop.store:reserve', 'shop.store:release'))]
    assert [issue['message'] for issue in facts['anchor_issues']] == [
        'a data owner needs Table.column (or Model.field) with writers=function,... and/or with=Model.field[=value],...; '
        'alone=function(reason) needs with=']
    ts = anchors.foreign_owners('// flowguard: owner Employee.organizationalUnitId writers=transferEmployee\n',
                                'typescript/a.ts', 'a.ts')
    assert [(row['kind'], row['name'], tuple(row['writers']), row['line']) for row in ts['anchors']] == [
        ('owner', 'Employee.organizationalUnitId', ('transferEmployee',), 1)]


def test_one_judgment_has_one_owner():
    facts = _facts('''
        # flowguard: owner ROUND
        def first(value: float) -> int:
            return int(value)
        # flowguard: owner ROUND
        def second(value: float) -> int:
            return int(value)
    ''')
    index = anchors._index([anchors._anchor(row) for row in facts['anchors']], [])
    assert [issue.code for issue in index.issues] == ['owner', 'owner']
    assert 'keep one reference' in index.issues[0].message and 'policy.py:1' in index.issues[0].message


def test_a_projection_is_written_without_a_colon():
    facts = _facts('''
        # flowguard: sensor ELIGIBLE -> result[0]
        def first(days: int):
            return days <= 3, 'why'
        # flowguard: sensor ELIGIBLE -> result.ok
        def second(days: int):
            return days
        # flowguard: sensor BAD -> result()
        def bad(days: int):
            return days
    ''')
    projections = [(row['name'], row['projection'], row['output'], row['output_type']) for row in facts['anchors']]
    assert projections == [('ELIGIBLE', 'result[0]', '', ''), ('ELIGIBLE', 'result.ok', '', '')]
    assert [issue['message'] for issue in facts['anchor_issues']] == ['invalid sensor anchor syntax']
    first = anchors._anchor(facts['anchors'][0])
    assert anchors.project(first, (False, 'why')) is False


def test_an_output_declaration_keeps_its_colon():
    facts = _facts('''
        # flowguard: sensor ELIGIBLE(days: day) -> allowed: bool
        def first(days: int) -> bool:
            return days <= 3
    ''')
    row = facts['anchors'][0]
    assert (row['output'], row['output_type'], row['projection'], tuple(row['issues'])) == ('allowed', 'bool', '', ())


def test_parameters_correspond_only_by_name_unless_the_copy_writes_its_mapping(tmp_path):
    source = '''
        # flowguard: owner ELIGIBLE
        def owner(days: int) -> bool:
            return days <= 3
        # flowguard: sensor ELIGIBLE
        def copy(overdue_days: int) -> bool:
            return overdue_days <= 4
    '''
    index = anchors._index([anchors._anchor(row) for row in _facts(source)['anchors']], [])
    hint = next(issue.message for issue in index.issues if 'ELIGIBLE(' in issue.message)
    assert 'parameters correspond only by name: write # flowguard: same ELIGIBLE(days=<its parameter>)' in hint
    mapped = source.replace('# flowguard: sensor ELIGIBLE\n', '# flowguard: sensor ELIGIBLE(days=overdue_days)\n')
    facts = _facts(mapped)
    copy = anchors._anchor(facts['anchors'][1])
    assert [(p.name, p.alias, p.source) for p in copy.parameters] == [('days', 'overdue_days', 'overdue_days')]
    assert not anchors._index([anchors._anchor(row) for row in facts['anchors']], []).issues
    # check compares copies no test ran on their current code: copies this change touches are its own (D24)
    _project(tmp_path, {'policy.py': mapped.replace('overdue_days <= 4', 'overdue_days <= 3')})
    (tmp_path / 'policy.py').write_text(textwrap.dedent(mapped).lstrip(), encoding='utf-8')
    code, text = _check(tmp_path)
    assert code == 1 and _lines(text, 'red: same ELIGIBLE: on ') == [
        'red: same ELIGIBLE: on days=4: the reference policy.py:owner returns False, policy.py:copy returns True '
        '-> make policy.py:copy agree with the reference'], text


def test_math_is_not_grey_and_representatives_include_halves_and_non_finite_values(tmp_path):
    source = '''
        import math
        from math import floor, isfinite


        # flowguard: owner ROUND
        def away(value: float) -> int:
            if not isfinite(value):
                raise ValueError("finite only")
            return floor(value + 0.5) if value >= 0.0 else math.ceil(value - 0.5)


        # flowguard: sensor ROUND
        def up(value: float) -> int:
            if not math.isfinite(value):
                raise ValueError("finite only")
            return math.floor(value + 0.5)
    '''
    # check compares copies no test ran on their current code: copies this change touches are its own (D24)
    _project(tmp_path, {'rounding.py': source.replace('return math.floor(value + 0.5)\n', 'return floor(value + 0.5) if value >= 0.0 else math.ceil(value - 0.5)\n')})
    (tmp_path / 'rounding.py').write_text(textwrap.dedent(source).lstrip(), encoding='utf-8')
    code, text = _check(tmp_path)
    assert code == 1 and _lines(text, 'red: same ROUND: on ') == [
        'red: same ROUND: on value=-0.5: the reference rounding.py:away returns -1, rounding.py:up returns 0 '
        '-> make rounding.py:up agree with the reference'], text
    assert 'not proved pure' not in text and 'import is unresolved' not in text, text
    from flowguard.intent import cells
    assert {-2.5, -0.5, 0.5, 2.5}.issubset(cells.representatives(cells.Kind('float')))
    assert any(value != value for value in cells.representatives(cells.Kind('float')))


# ---- fixed example 6 ---------------------------------------------------------------------------------

def test_fixed_6_copies_with_different_return_forms_are_compared_through_their_projections(tmp_path):
    policy = _project(tmp_path, {'policy.py': '''
        from dataclasses import dataclass


        @dataclass(frozen=True)
        class Answer:
            ok: bool
            why: str


        # flowguard: sensor ELIGIBLE -> result[0]
        def eligible(days: int):
            return days <= 3, 'within the window'


        # flowguard: sensor ELIGIBLE(days=overdue_days) -> result.ok
        def preview(overdue_days: int) -> Answer:
            return Answer(overdue_days <= 3, 'preview')
    ''', 'tests/test_case.py': '''
        from policy import eligible, preview
        def test_native():
            assert eligible(0)[0]
            assert preview(0).ok
    '''}) / 'policy.py'
    agreed = _pytest(tmp_path)
    assert agreed.returncode == 0 and not re.search(r'^red: same ', _text(agreed), re.M), _text(agreed)
    policy.write_text(policy.read_text(encoding='utf-8').replace('overdue_days <= 3', 'overdue_days <= 5'), encoding='utf-8')
    result = _pytest(tmp_path)
    text = _text(result)
    # Both ordinary calls still run and retain their original projections. Their tuple/dataclass
    # results are not JSON, so the closed comparison must stay explicitly unverified.
    assert result.returncode == 0 and '1 passed' in result.stdout, text
    assert _cli_fixture.block(result)[1:] == [
        'not compared: ELIGIBLE (no recorded JSON inputs, or no comparable JSON result) -> not a failure'], text


# ---- round 22 F1: a same-name red names every copy's answer and chooses none -------------------------------

def _copies(*bounds, owner=False):
    """limits.py: one LIMIT copy per bound (`days <= bound`), at lines 2, 7, 12, ...; the first is the owner."""
    names = ('chart', 'calendar', 'report')
    return '\n\n'.join(f'# flowguard: {"owner" if owner and not index else "sensor"} LIMIT\n'
                       f'def {names[index]}(days: int) -> bool:\n    return days <= {bound}\n'
                       for index, bound in enumerate(bounds))


REACHES_CHART = {'tests/test_limits.py': '''
    from limits import chart
    def test_chart():
        assert chart(1)
'''}


def _same_name_red(root, source):
    (root / 'limits.py').write_text(source, encoding='utf-8')
    result = _pytest(root)
    text = _text(result)
    assert result.returncode == 1, text
    lines = _cli_fixture.block(result)
    return [line for line in lines if line.startswith('red: same LIMIT')], lines


def test_three_same_name_copies_are_counted_by_answer_and_the_red_does_not_choose_the_right_one(tmp_path):
    # 4.2 told the AI to change the copy the test reached (`让 chart 和同名副本一致`), here one of the two that
    # agree: done as written, it copies the odd one's answer. The red counts the answers and leaves the choice.
    _project(tmp_path, {'limits.py': _copies(3, 3, 3), **REACHES_CHART})
    red, text = _same_name_red(tmp_path, _copies(3, 3, 4))
    assert red == ['red: same LIMIT: on days=4: limits.py:chart and limits.py:calendar return False, limits.py:report returns True '
                   '-> decide which copy is right, then make the others agree'], text


def test_two_same_name_copies_are_one_answer_each_and_an_owner_stays_the_reference(tmp_path):
    _project(tmp_path, {'limits.py': _copies(3, 3), **REACHES_CHART})
    red, text = _same_name_red(tmp_path, _copies(4, 3))
    # one each: no side is the larger one, and the step names no copy to change
    assert red == ['red: same LIMIT: on days=4: limits.py:chart returns True, limits.py:calendar returns False '
                   '-> decide which copy is right, then make the other agree'], text
    # The owner is the reference its copies follow: the copy changes, also when the test reaches the owner
    # (4.2 then said `让 chart 和同名副本一致`, the owner after its copy).
    red, text = _same_name_red(tmp_path, _copies(3, 4, owner=True))
    assert red == ['red: same LIMIT: on days=4: the reference limits.py:chart returns False, limits.py:calendar returns True '
                   '-> make limits.py:calendar agree with the reference'], text


def _checked_red(root, source):
    (root / 'limits.py').write_text(source, encoding='utf-8')
    code, text = _check(root)
    assert code == 1, text
    return sorted(line for line in text.splitlines() if line.startswith('red')), text


def test_check_sends_a_changed_copy_back_to_the_owner_and_counts_every_copys_answer(tmp_path):
    # Round 22 F1 review: with the owner chart among the copies left as they were, check said `→ 一起改，或改成调用
    # report`, the owner after its copy; its comparison listed chart ↔ report only, `F → T` read as the change, and
    # named no owner.
    _project(tmp_path, {'limits.py': _copies(3, 3, 3, owner=True)})
    red, text = _checked_red(tmp_path, _copies(3, 3, 4, owner=True))
    # one red per member (D30): the same-name red covers the changed copy, no changed-alone red repeats it
    assert red == ['red: same LIMIT: on days=4: the reference limits.py:chart and limits.py:calendar return False, limits.py:report returns True '
                   '-> make limits.py:report agree with the reference'], text
    # The owner changed: its copies follow it.
    red, text = _checked_red(tmp_path, _copies(4, 3, 3, owner=True))
    assert red == ['red: same LIMIT: on days=4: the reference limits.py:chart returns True, limits.py:calendar and limits.py:report return False '
                   '-> make limits.py:calendar, limits.py:report agree with the reference'], text


def test_check_names_the_owner_when_it_changed_with_a_copy_and_a_third_copy_stayed(tmp_path):
    # Round 22 F1, second review: chart (the owner) and calendar changed, report did not. The red took the first
    # anchored function, calendar, and sent both back ("让 calendar、chart 回到原来的行为"), while the same-name red of
    # the same check sent report to the owner.
    _project(tmp_path, {'limits.py': _copies(3, 3, 3, owner=True)})
    red, text = _checked_red(tmp_path, _copies(4, 4, 3, owner=True))
    assert red == ['red: same LIMIT: on days=4: the reference limits.py:chart and limits.py:calendar return True, limits.py:report returns False '
                   '-> make limits.py:report agree with the reference'], text


def test_check_leaves_the_choice_between_copies_when_none_is_the_owner(tmp_path):
    _project(tmp_path, {'limits.py': _copies(3, 3, 3)})
    red, text = _checked_red(tmp_path, _copies(3, 3, 4))
    assert red == ['red: same LIMIT: on days=4: limits.py:chart and limits.py:calendar return False, limits.py:report returns True '
                   '-> decide which copy is right, then make the others agree'], text


KNOWN_LIMIT = (
    '[known.limit]\nsites = ["limits.py:chart", "limits.py:calendar"]\nwhy = "the copies disagree at 4"\nact = "ask"\n'
    'ask = "which limit is right?"\nfinding = "same:LIMIT"\n')


def test_check_says_known_fixed_for_same_name_copies_it_compared_and_found_agreeing(tmp_path):
    # D24: check runs the same-name copies no test reached on their current code. Copies that already disagreed and
    # that this change leaves alone say nothing; once they agree, the known entry naming their disagreement may be
    # fixed, as a pytest session or a vitest run that compared every copy says it (`ran`).
    _project(tmp_path, {'limits.py': _copies(3, 4), '.flowguard/known.toml': KNOWN_LIMIT})
    code, text = _check(tmp_path)
    assert code == 0 and _block(text)[1:] == [], text
    (tmp_path / 'limits.py').write_text(_copies(3, 3), encoding='utf-8')
    code, text = _check(tmp_path)
    assert code == 0 and _block(text)[1:] == [
        'known fixed?: known.limit: copies of LIMIT now agree -> the owner has not answered known.limit: if this change settles it, say so in your report'], text


# Round 22 F1, second review: chart is the owner, report already differs from it at days=3 (`days < 3`), and this
# task changes calendar only (`days <= 4`). The red named the first copy that differs and listed report with the
# owner on that input (`2 份得 F（负责人 limits.py:2 chart、limits.py:12 report）`); 4.2.0 named both.
def _split_copies(calendar):
    """`_copies(3, calendar, 3, owner=True)` with report at `days < 3`."""
    source = _copies(3, calendar, 3, owner=True)
    return source[:source.rindex('days <= 3')] + 'days < 3\n'


# report already differs at days=3; calendar newly differs at days=4. check compares the copies no test reached as
# pytest compares them, each input with the baseline too (design 4.5): the old pair is before, the new one red.
SPLIT_RED = ['red: same LIMIT: on days=4: the reference limits.py:chart and limits.py:report return False, limits.py:calendar '
             'returns True -> make limits.py:calendar agree with the reference']
SPLIT_BEFORE = ['before: same LIMIT disagreed at task start on days=3: the reference limits.py:chart and limits.py:calendar return True, '
                'limits.py:report returns False -> leave it unless your task is about it']


def test_check_names_every_copy_that_differs_from_the_owner_on_its_own_input(tmp_path):
    _project(tmp_path, {'limits.py': _split_copies(3)})
    red, text = _checked_red(tmp_path, _split_copies(4))
    assert [line for line in red if line.startswith('red: same LIMIT: on ')] == SPLIT_RED, text
    assert [line for line in text.splitlines() if line.startswith('before: same LIMIT')] == SPLIT_BEFORE, text
    assert len(red) == 1, text          # the same-name red covers the changed calendar: no changed-alone red besides


def test_pytest_names_every_copy_that_differs_from_the_owner_on_its_own_input(tmp_path):
    _project(tmp_path, {'limits.py': _split_copies(3), **REACHES_CHART})
    red, text = _same_name_red(tmp_path, _split_copies(4))
    # report already differs at days=3; calendar newly differs at days=4. The old pair cannot hide the new one.
    assert red == ['red: same LIMIT: on days=4: the reference limits.py:chart and limits.py:report return False, limits.py:calendar '
                   'returns True -> make limits.py:calendar agree with the reference'], text
    assert [line for line in text if line.startswith('before: same LIMIT')] == [
        'before: same LIMIT disagreed at task start on days=3: the reference limits.py:chart and limits.py:calendar return True, '
        'limits.py:report returns False -> leave it unless your task is about it'], text


# ---- fixed examples 10 and 11: the KWP rounding copies ---------------------------------------------------

def test_fixed_10_the_unchanged_kwp_look_alikes_of_a_registered_owner_get_no_line(tmp_path):
    _commit(_kwp(tmp_path))
    owner = tmp_path / 'Step1/src/kwp_step1/matlab_fallbacks.py'
    lines = owner.read_text(encoding='utf-8').splitlines(True)
    assert lines[13] == '\n' and lines[14].startswith('def matlab_round(')
    lines[13] = '# flowguard: owner MATLAB_ROUND\n'
    owner.write_text(''.join(lines), encoding='utf-8')
    code, text = _check(tmp_path)
    # Copy discovery compares the look-alikes of the reference: copies the baseline already had, and look-alikes
    # that are no diverged copy, are no finding (only a diverged copy, or a copy this change adds, is one).
    assert code == 0 and _block(text)[1:] == [], text


def test_fixed_11_three_changed_unregistered_copies_give_only_their_not_compared_line(tmp_path):
    _kwp(tmp_path)
    fixed = {}
    for relative, floor in (('Step1/src/kwp_step1/matlab_fallbacks.py', 'floor'), ('Step3/src/kwp_step3/technology.py', 'math.floor'),
                            ('Step10/step10_baublock_progress_maps.py', 'math.floor')):
        path = tmp_path / relative
        fixed[relative] = path.read_text(encoding='utf-8')
        # The pre-1da8721 bodies are reconstructed (README): the unchanged copies' floor(x + 0.5).
        before, count = re.subn(r'(    """.*?"""\n)    number = float\(value\)\n.*?\n(?=\n|\Z)',
                                lambda match: match.group(1) + f'    return int({floor}(float(value) + 0.5))\n', fixed[relative], count=1, flags=re.S)
        assert count == 1
        path.write_text(before, encoding='utf-8')
    _commit(tmp_path, 'before 1da8721')
    for relative, text in fixed.items():
        (tmp_path / relative).write_text(text, encoding='utf-8')
    code, text = _check(tmp_path)
    assert code == 0, text
    # No rules, so no pytest batch: the title still names the baseline the changed functions were compared with.
    title, *lines = _block(text)
    head = _git(tmp_path, 'rev-parse', 'HEAD').strip()
    assert re.fullmatch(rf'FlowGuard \d+\.\d+ \(since {head[:7]}\): 0 red, 7 not compared; \d+\.\d s', title), text
    # None of the changed functions has a flowguard comment: the copy they left behind is no finding.
    assert lines == ['not compared: 7 functions (3/20 inputs not compared: non-finite JSON number) -> not a failure'], text


# ---- fixed example 18: look-alikes that share only a number ---------------------------------------------


def test_fixed_18_numbers_equal_only_at_zero_are_unrelated(tmp_path):
    _project(tmp_path, {'money.py': '''
        def margin(price: float) -> float:
            return price * 0.2


        def tax(amount: float) -> float:
            return amount * 0.19
    ''', 'tests/test_case.py': 'def test_native():\n    assert True\n'})
    money = tmp_path / 'money.py'
    money.write_text(money.read_text(encoding='utf-8').replace('def margin', '# flowguard: owner MARGIN\ndef margin'), encoding='utf-8')
    code, text = _check(tmp_path, '--all')
    assert code == 0, text
    assert 'money.py:6' not in text and 'copies of MARGIN' not in text, text


# ---- data owners ---------------------------------------------------------------------------------------

def test_a_new_write_outside_a_data_owner_is_red_and_older_ones_are_the_old_ledger(tmp_path):
    _project(tmp_path, {'changed.py': 'def unrelated(): return 0\n', 'shop/__init__.py': '', 'shop/store.py': '''
        # flowguard: owner hires.reserved writers=shop.store:reserve
        def reserve(db, hire_id):
            db.execute("UPDATE hires SET reserved = 1 WHERE id = ?", (hire_id,))


        def legacy(db):
            db.execute("UPDATE hires SET reserved = 0")
    ''', 'tests/test_case.py': '''
        def test_native():
            assert True
    '''})
    code, text = _check(tmp_path)
    assert code == 0 and _block(text)[1:] == [], text
    # Enter pytest's cached static route before --all, while leaving every real writer unchanged.
    (tmp_path / 'changed.py').write_text('def unrelated(): return 1\n', encoding='utf-8')
    code, text = _check(tmp_path, '--all')
    assert code == 0 and _block(text)[1:] == [
        'before: writers hires.reserved at store.py:legacy was broken at task start -> leave it unless your task is about it'], text
    (tmp_path / 'shop/api.py').write_text('def cancel(db, hire_id):\n    db.execute("UPDATE hires SET reserved = 0 WHERE id = ?", (hire_id,))\n', encoding='utf-8')
    code, text = _check(tmp_path)
    assert code == 1, text
    # the new write is red, the old one is no line; adding to the agreement is the owner's (show --last, not the step)
    assert _lines(text, 'red: ') == ['red: writers hires.reserved: api.py:cancel writes hires.reserved outside reserve -> call reserve instead'], text
    shown = _cli_fixture.last(tmp_path).splitlines()
    assert shown[shown.index('red: writers hires.reserved: shop/api.py:cancel writes hires.reserved outside reserve -> call reserve instead') + 1:][:2] == [
        '    agreement: shop/store.py:1', '    if the owner agrees that a function may write it, add it to that writers agreement'], shown
    result = _pytest(tmp_path)
    assert result.returncode == 1 and 'red: writers hires.reserved: api.py:cancel writes hires.reserved outside reserve -> call reserve instead' \
        in _cli_fixture.block(result), _text(result)


# ---- copy discovery: replay route, timeout, import errors, a new copy of an owner ---------------------------

def test_reusing_static_findings_keeps_discovered_copies_in_the_summary_and_all_listing(tmp_path):
    from contextlib import closing
    from flowguard.intent import owners
    from flowguard.intent.config import load_config
    from flowguard.structure import build
    _project(tmp_path, {'reference.py': '''
        # flowguard: same LIMIT ref
        def limit(value: int) -> bool:
            if value < 0: return False
            if value <= 3: return True
            return False
    ''', 'peer.py': '''
        def permitted(value: int) -> bool:
            if value < 0: return False
            if value <= 4: return True
            return False
    '''})
    cfg = load_config(tmp_path)
    base = _git(tmp_path, 'rev-parse', 'HEAD').strip()
    with closing(build(tmp_path, roots=cfg.roots)) as graph:
        index = anchors.collect(graph)
        static = owners.static_findings(cfg, graph, index, base, everything=True)
        found = owners.check_findings(cfg, graph, index, base, everything=True, static=static)
    assert 'copies:LIMIT' in {issue.name for issue in found.issues}
    assert found.summary['count'] == 1
    from flowguard.intent import signals          # --all lists every old finding
    listed, _ = signals.deliver(found.issues, touched_functions=(), touched_files=(), everything=True)
    assert any(line.name == 'copies:LIMIT' for line in listed), listed


def test_reusing_static_findings_returns_its_findings_and_lines_without_mutating_it(tmp_path, monkeypatch):
    from contextlib import closing
    from copy import deepcopy
    from flowguard.intent import owners
    from flowguard.intent.config import load_config
    from flowguard.structure import build
    _project(tmp_path, {'policy.py': '''
        # flowguard: writers account.status save
        # flowguard: together account.status account.changed
        def save(db):
            db.execute("UPDATE account SET status = 'ready'")
        def legacy(db):
            db.execute("UPDATE account SET status = 'ready'")
    '''})
    cfg = load_config(tmp_path)
    base = _git(tmp_path, 'rev-parse', 'HEAD').strip()
    with closing(build(tmp_path, roots=cfg.roots)) as graph:
        index = anchors.collect(graph)
        static = owners.static_findings(cfg, graph, index, base, everything=True)
        before = deepcopy(static)
        assert {issue.family for issue in static.issues} >= {'writer', 'pair'}
        def repeated_static(*args, **kwargs):
            raise AssertionError('the existing static facts must be reused')
        monkeypatch.setattr(owners, 'static_findings', repeated_static)
        found = owners.check_findings(cfg, graph, index, base, everything=True, static=static)
    assert static == before
    assert found is not static
    assert found.issues == static.issues
    assert all(line in found.lines for line in static.lines)
    assert found.known == static.known and static.ran <= found.ran
    assert found.summary == static.summary
    assert all(found.stats[key] == value for key, value in static.stats.items())


def test_copy_discovery_uses_sealed_source_and_a_look_alike_it_cannot_run_leaves_it_incomplete(tmp_path, monkeypatch):
    _project(tmp_path, {'rules.py': '''
        # flowguard: owner HALF
        def half(value: float) -> float:
            return value * 0.5


        def same(amount: float) -> float:
            return amount * 0.5


        def spin(value: float) -> float:
            while value == value or value * 0.5:
                pass
            return value


        def broken(value: float) -> float:
            import json
            return json.loads(value) * 0.5
    ''', 'tests/test_case.py': 'def test_native():\n    assert True\n', 'vendor_copy.py': '''
        import not_installed_anywhere


        def copied(value: float) -> float:
            return value * 0.5
    '''})
    spy = ('from flowguard.intent import runtime as R, owners as O\n'
           'O.TIMEOUT = 0.5\n'
           '_real = R.sealed\n'
           'def _counted(source, qual, args, kwargs):\n'
           '    assert isinstance(source, str)\n'
           '    sys.__stderr__.write("SEALED " + qual + "\\n")\n'
           '    return _real(source, qual, args, kwargs)\n'
           'R.sealed = _counted\n')
    result = subprocess.run([sys.executable, '-c', _cli_fixture._BOOT, SOURCE, 'unused-marker', spy,
                             '--root', str(tmp_path), 'check', '--all'], cwd=tmp_path, capture_output=True, text=True, timeout=120)
    text = _text(result)
    assert result.returncode == 0, text
    compared = set(re.findall(r'SEALED (\w+)', result.stderr))
    assert {'half', 'same', 'spin', 'copied'} <= compared, result.stderr
    # copies the baseline already had are no finding of this change
    assert _block(text)[1:] == [], text
    # FlowGuard runs copy discovery itself: only the project's own 4.2 owner spelling is deprecated
    notices = [line for line in result.stderr.splitlines() if line.startswith('deprecated: ')]
    assert notices == ['deprecated: function owner goes in 5.0 -> write same NAME ref'], result.stderr
    # spin (rules.py:10) does not complete and broken (rules.py:16) imports: copy discovery did not judge every
    # look-alike, so it does not count as run (a known entry's `known fixed?` needs it); without them it does.
    from contextlib import closing
    from flowguard.intent import owners
    from flowguard.intent.config import load_config
    from flowguard.structure import build
    monkeypatch.setattr(owners, 'TIMEOUT', 0.5)
    def discovered():
        cfg = load_config(tmp_path)
        with closing(build(tmp_path, roots=cfg.roots)) as graph:
            return owners.discover(cfg, graph, anchors.collect(graph), owners.Change(cfg, graph, None), everything=True)
    assert owners.COPY_DISCOVERY not in discovered().ran
    rules = tmp_path / 'rules.py'
    rules.write_text(rules.read_text(encoding='utf-8').split('\n\n\ndef spin')[0] + '\n', encoding='utf-8')
    assert owners.COPY_DISCOVERY in discovered().ran


def test_manual_copy_discovery_does_not_execute_module_initialization_or_function_effects(tmp_path):
    marker = tmp_path / 'executed.txt'
    _project(tmp_path, {'reference.py': f'''
        open({str(marker)!r}, 'w').write('module initialization')
        # flowguard: same LIMIT ref
        def limit(value: int) -> int:
            return value * 3
    ''', 'peer.py': f'''
        raise RuntimeError('module initialization must not run')
        def copy(value: int) -> int:
            return value * 3
        def effect(value: int) -> int:
            open({str(marker)!r}, 'w').write('function effect')
            return value * 3
    ''', 'tests/test_native.py': 'def test_native():\n    assert True\n'})
    code, text = _check(tmp_path, '--all')
    assert code == 0 and _block(text)[1:] == [], text
    assert not marker.exists()


def test_changed_alone_compares_baseline_source_without_importing_the_project(tmp_path):
    from contextlib import closing
    from flowguard.intent import owners
    from flowguard.intent.config import load_config
    from flowguard.structure import build
    marker = tmp_path / 'initialized.txt'
    source = f"open({str(marker)!r}, 'w').write('initialized')\n# flowguard: same LIMIT\ndef limit(value: int):\n    return value <= 3\n"
    _project(tmp_path, {'policy.py': source, 'peer.py': 'def copy(value: int):\n    return value <= 3\n'})
    base = _git(tmp_path, 'rev-parse', 'HEAD').strip()
    (tmp_path / 'policy.py').write_text(source.replace('<= 3', '<= 4'), encoding='utf-8')
    cfg = load_config(tmp_path)
    with closing(build(tmp_path, roots=cfg.roots)) as graph:
        found = owners.changed_alone(cfg, graph, anchors.collect(graph), owners.Change(cfg, graph, base))
    assert not marker.exists()
    # the baseline source of limit agreed with the unregistered copy, the new one does not: limit's finding names it
    issue = next(issue for issue in found.issues if issue.name == 'changed-alone:LIMIT')
    assert [part[:3] for part in issue.parts] == [('policy:limit', 'policy.py:limit',
                                                   'changed behavior; 1 copy that answered the same is unchanged: peer.py:copy')], issue


def test_changed_alone_does_not_count_the_same_raised_exception_as_agreement(tmp_path):
    from contextlib import closing
    from flowguard.intent import owners
    from flowguard.intent.config import load_config
    from flowguard.structure import build
    source = 'def limit(value: int):\n    raise ValueError("same")\n'
    _project(tmp_path, {'policy.py': source, 'peer.py': source.replace('limit', 'copy')})
    base = _git(tmp_path, 'rev-parse', 'HEAD').strip()
    (tmp_path / 'policy.py').write_text(source + '    return value\n', encoding='utf-8')
    cfg = load_config(tmp_path)
    with closing(build(tmp_path, roots=cfg.roots)) as graph:
        found = owners.changed_alone(cfg, graph, anchors.collect(graph), owners.Change(cfg, graph, base))
    assert not found.issues
    assert any(line.kind == 'not compared' and 'same raised exception' in line.text for line in found.lines), found


def test_a_new_copy_of_a_registered_owner_is_an_impact(tmp_path):
    # 4.3: structure findings cannot be red (design 6.1, D1); a copy this change adds is impact.
    _project(tmp_path, {'rules.py': '''
        # flowguard: owner HALF
        def half(value: float) -> float:
            return value * 0.5
    '''})
    code, text = _check(tmp_path)
    assert code == 0 and _block(text)[1:] == [], text
    rules = tmp_path / 'rules.py'
    rules.write_text(rules.read_text(encoding='utf-8') + '\n\ndef again(amount: float) -> float:\n    return 0.5 * amount\n', encoding='utf-8')
    code, text = _check(tmp_path)
    assert code == 0 and _block(text)[1:] == [
        'impact: copies of HALF: rules.py:again is a copy of the reference rules.py:half -> fix it, or say why in your report'], text


def test_a_typescript_data_owner_turns_a_new_prisma_write_outside_its_writers_red(tmp_path):
    fixtures = Path(__file__).resolve().parents[1] / 'fixtures/planning_tool'
    for path in fixtures.rglob('*.txt'):
        target = tmp_path / path.relative_to(fixtures).with_suffix('')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    (tmp_path / 'backend/src/owners.ts').write_text(
        '// flowguard: owner Employee.organizationalUnitId writers=transferEmployee\nexport {};\n', encoding='utf-8')
    (tmp_path / '.gitignore').write_text('.flowguard/cache/\n', encoding='utf-8')
    _commit(tmp_path)
    code, text = _check(tmp_path)
    assert code == 0 and _block(text)[1:] == [], text
    (tmp_path / 'backend/src/services/rogue.ts').write_text(
        'export async function moveEmployee(prisma: any, id: string, unit: string) {\n'
        '  await prisma.employee.update({ where: { id }, data: { organizationalUnitId: unit } });\n}\n', encoding='utf-8')
    code, text = _check(tmp_path)
    assert code == 1 and _lines(text, 'red: ') == [
        'red: writers Employee.organizationalUnitId: rogue.ts:moveEmployee writes Employee.organizationalUnitId outside transferEmployee '
        '-> call transferEmployee instead'], text
    # show --last names the run first; the agreement is the detail under the red line, found by its text
    shown = _cli_fixture.last(tmp_path).splitlines()
    red = next(index for index, line in enumerate(shown) if line.startswith('red: writers Employee.organizationalUnitId: '))
    assert shown[0].startswith('FlowGuard last run: check at ') and shown[red + 1] == '    agreement: backend/src/owners.ts:1', shown


def test_show_lists_an_owners_old_ledger(tmp_path):
    _project(tmp_path, {'shop.py': '''
        # flowguard: owner hires.reserved writers=shop:reserve
        def reserve(db):
            db.execute("UPDATE hires SET reserved = 1")


        def legacy(db):
            db.execute("UPDATE hires SET reserved = 0")


        # flowguard: owner HALF
        def half(value: float) -> float:
            return value * 0.5


        def same(amount: float) -> float:
            return amount * 0.5
    '''})
    for name, wanted in (('hires.reserved', ['owner hires.reserved shop.py:1; writers=shop:reserve',
                                              'outside writers: shop.py:7 legacy (sql:update, value 0)']),
                         ('HALF', ['owner HALF shop.py:11; 1 unregistered look-alikes (not run here; check --all compares them)',
                                   'look-alike shop.py:15 same'])):
        result = subprocess.run([sys.executable, '-c', _cli_fixture._BOOT, SOURCE, 'unused-marker', '',
                                 '--root', str(tmp_path), 'show', name], cwd=tmp_path, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0 and all(line in _text(result.stdout).splitlines() for line in wanted), _text(result)


# ---- coordinator additions: write values, value gate, pairs, own literals, two declarations ----------------

def _copy_fixture(root, name):
    fixtures = Path(__file__).resolve().parents[1] / 'fixtures' / name
    for path in fixtures.rglob('*.txt'):
        target = root / path.relative_to(fixtures).with_suffix('')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    return root


def test_all_sixteen_kwp_status_writes_read_their_enum_values(tmp_path):
    from contextlib import closing
    from flowguard.structure import build
    _copy_fixture(tmp_path, 'kwp_orchestrator')
    with closing(build(tmp_path)) as graph:
        rows = [row for row in graph.assignments(include_unknown=True)
                if row['field'] == 'kwp_platform.orchestrator:KwpApplication.status']
        assert len(rows) == 16 and all(row.get('values') for row in rows)
        assert {value for row in rows for value in row['values']} == {
            'planned', 'canceled', 'stale', 'running', 'recovering', 'completed', 'waiting_for_data', 'partial', 'failed'}
        assert next(row for row in rows if row['line'] == 244)['values'] == ['running', 'planned']   # a if c else b


def test_write_values_read_constants_keys_and_class_defaults(tmp_path):
    from contextlib import closing
    from flowguard.structure import build
    (tmp_path / 'jobs.py').write_text(textwrap.dedent('''
        from enum import Enum
        DONE = 'done'


        class Phase(Enum):
            NEW = 'new'


        class Job:
            status = 'new'

            def finish(self):
                self.status = DONE

            def restart(self):
                self.status = Phase.NEW


        def record(row):
            row['status'] = 'archived'
    ''').lstrip(), encoding='utf-8')
    with closing(build(tmp_path)) as graph:
        rows = {(row['field'], row['line']): row.get('values') or [row['value']] for row in graph.assignments(include_unknown=True)}
        assert rows[('jobs:Job.status', 10)] == ['new'] and rows[('jobs:Job.status', 13)] == ['done']
        assert rows[('jobs:Job.status', 16)] == ['new']
        by_name = [row for row in graph.writes('status', by_name=True) if row['function'] == 'record']
        assert [(row['field'], row['how'], row['receiver'], row['value']) for row in by_name] == [('status', 'name', 'row', 'archived')]


def test_one_value_gate_checks_states_anchors_enums_and_writes_outside_the_class(tmp_path):
    from contextlib import closing
    from flowguard.structure import build
    (tmp_path / 'models.py').write_text(textwrap.dedent('''
        from enum import StrEnum


        class Phase(StrEnum):
            NEW = 'new'
            SAVED = 'saved'


        # flowguard: states Job.status = new | saved | published
        class Job:
            def save(self):
                self.status = 'saved'


        class Step:
            phase: Phase
            later: Phase | None = None
    ''').lstrip(), encoding='utf-8')
    (tmp_path / 'writers.py').write_text(textwrap.dedent('''
        from models import Job, Step, Phase


        def close(job: Job):
            job.status = 'closed'


        def jump(step: Step):
            step.phase = 'published'
            step.phase = Phase.SAVED
    ''').lstrip(), encoding='utf-8')
    with closing(build(tmp_path)) as graph:
        found = [(issue.code, issue.file, issue.line, issue.name) for issue in anchors.collect(graph).issues]
    assert found == [('states-values', 'writers.py', 5, 'Job.status'), ('states-values', 'writers.py', 9, 'Step.phase')], found
    with closing(build(tmp_path)) as graph:
        message = next(issue.message for issue in anchors.collect(graph).issues if issue.name == 'Job.status')
    assert message.startswith("code writes Job.status='closed'; allowed: 'new' | 'saved' | 'published' (writers.py:5)"), message


def test_a_registered_pair_is_red_where_a_write_leaves_its_partner_out(tmp_path):
    # 4.3: an agreement is judged against the baseline code (what it finds there was there before the change), so
    # the agreement is the baseline's and the writes that are judged are this change's.
    agreement = "# flowguard: owner hires.reserved with=hires.state=held alone=shop.store:import_rows(bulk import marks rows later)\n"
    store = '''
        def _mark(db, hire_id):
            db.execute("UPDATE hires SET state = 'held' WHERE id = ?", (hire_id,))
        def _deep(db, hire_id):
            _mark(db, hire_id)
        def reserve(db, hire_id):
            db.execute("UPDATE hires SET reserved = 1 WHERE id = ?", (hire_id,))
            _deep(db, hire_id)
    '''
    _project(tmp_path, {'shop/__init__.py': '', 'shop/store.py': agreement + textwrap.dedent(store).lstrip()})
    code, text = _check(tmp_path)
    assert code == 0 and _block(text)[1:] == [], text
    path = tmp_path / 'shop/store.py'
    path.write_text(path.read_text(encoding='utf-8') + textwrap.dedent('''
        def release(db, hire_id):
            db.execute("UPDATE hires SET reserved = 0 WHERE id = ?", (hire_id,))
        def import_rows(db):
            db.execute("UPDATE hires SET reserved = 0")
    ''').lstrip(), encoding='utf-8')
    code, text = _check(tmp_path)
    # Round 20 semantics change: the partner is looked for in the same operation (callers three levels up,
    # then three levels down from them), no longer in the writer's own call tree only: reserve holds it through
    # _deep and _mark; import_rows is excepted; a red line names no way to silence it.
    assert code == 1 and _lines(text, 'red: ') == [
        'red: together hires.reserved: store.py:release writes hires.reserved without hires.state=held -> also write hires.state=held in release'], text
    assert 'except=' not in '\n'.join(_block(text)), text


def test_copy_discovery_compares_on_the_codes_own_literals(tmp_path):
    _copy_fixture(tmp_path, 'kwp_normalize')
    _project(tmp_path, {}, pyproject='[tool.pytest.ini_options]\npythonpath = ["Step1/src", "Step3/src"]\n')
    technology = tmp_path / 'Step3/src/kwp_step3/technology.py'
    technology.write_text(technology.read_text(encoding='utf-8').replace('def normalize_technology_name(value: object)',
                                                          '# flowguard: owner TECHNOLOGY\ndef normalize_technology_name(value: object)'), encoding='utf-8')
    code, text = _check(tmp_path)
    assert code == 0 and _block(text)[1:] == [], text
    # The copy in utils.py forks on a name only the copies' own tables spell: a copies finding of the reference (the
    # baseline had it, so it is no line of this change).
    from contextlib import closing
    from flowguard.intent import owners
    from flowguard.intent.config import load_config
    from flowguard.structure import build
    cfg = load_config(tmp_path)
    with closing(build(tmp_path, roots=cfg.roots)) as graph:
        found = owners.discover(cfg, graph, anchors.collect(graph), owners.Change(cfg, graph, owners.baseline(cfg)))
    forked = next(issue for issue in found.issues if issue.name == 'copies:TECHNOLOGY')
    assert 'diverged copy 1 copies' in forked.text and 'Step1/src/kwp_step1/utils.py:' in forked.text, forked
    assert "-> 'district_heat'(reference returns 'waermenetze')" in forked.text, forked.text


def _known_ignore(root, name, why):
    """`known add NAME --act ignore`: the 5.0 record of copies meant to differ (4.3: a [structure] decision)."""
    assert _cli_fixture.main(['--root', root, 'known', 'add', name, '--act', 'ignore', '--why', why]) == 0


def test_known_add_with_act_ignore_takes_the_copies_line_of_a_changed_copy_out(tmp_path):
    body = ("export function total(items: number[], rate: number): number {{\n  let sum = 0;\n"
            "  for (const item of items) {{\n    if (item > {limit}) {{ sum += item * rate; }} else {{ sum += item; }}\n  }}\n"
            "  return Math.round(sum * 100) / 100;\n}}\n")
    _project(tmp_path, {'src/a.ts': body.format(limit=10), 'src/b.ts': body.format(limit=20)})
    (tmp_path / 'src/a.ts').write_text(body.format(limit=10).replace('* 100) / 100', '* 1000) / 1000'), encoding='utf-8')
    static = lambda: _check(tmp_path, '--static')
    code, text = static()
    assert code == 0 and _block(text)[1:] == ['before: copies total at a.ts:total was broken at task start -> leave it unless your task is about it'], text
    _known_ignore(tmp_path, 'copies:total', 'the two totals round differently on purpose until the reports merge')
    code, text = static()
    assert code == 0 and _block(text)[1:] == ['loosened: known.copies-total added with act = "ignore" -> name it in your report; '
                                              "loosening an agreement is the owner's decision"], text


def test_a_copies_problem_lists_the_same_functions_after_a_file_is_mapped_again(tmp_path):
    # Round 25 check: the problem compared its members with whichever function the map returned first, so a comment
    # added to src/a.ts (mapped again, now last) made it list src/b.ts, src/c.ts and src/a.ts instead of a and b.
    body = ("export function save(items: number[], rate: number): number {{\n  let sum = 0;\n"
            "  for (const item of items) {{\n    if (item > {limit}) {{ sum += item * rate; }} else {{ sum += item; }}\n  }}\n"
            "  return Math.round(sum * 100) / 100;\n}}\n")
    _project(tmp_path, {'src/a.ts': body.format(limit=10), 'src/b.ts': body.format(limit=20), 'src/c.ts': body.format(limit=10)})
    listed = [f'before: copies save at {name}.ts:save was broken at task start -> leave it unless your task is about it' for name in ('a', 'b')]
    code, text = _check(tmp_path, '--static', '--all')
    assert _block(text)[1:] == listed, text
    (tmp_path / 'src/a.ts').write_text('// rounded to cents\n' + body.format(limit=10), encoding='utf-8')
    code, text = _check(tmp_path, '--static', '--all')
    assert _block(text)[1:] == listed, text


def test_a_copies_problem_this_task_made_is_impact_and_known_add_with_act_ignore_counts_it(tmp_path):
    # Final check of r25-init: two identical save functions at the baseline are no copies problem; the task edits
    # one, and the copies problem that appears is impact. 4.3 let the owner decide it in [structure]; 5.0 records it
    # with known add --act ignore, which counts it without a line.
    body = ("export function save(items: number[], rate: number): number {{\n  let sum = 0;\n"
            "  for (const item of items) {{\n    if (item > 10) {{ sum += item * rate; }} else {{ sum += item; }}\n  }}\n"
            "  return Math.round(sum * {scale}) / {scale};\n}}\n")
    _project(tmp_path, {'src/a.ts': body.format(scale=100), 'src/b.ts': body.format(scale=100)})
    (tmp_path / 'src/a.ts').write_text(body.format(scale=1000), encoding='utf-8')
    code, text = _check(tmp_path, '--static')
    assert code == 0 and _block(text)[1:] == [
        f'impact: copies save: {name}.ts:save has another body than the same-named save in src/{other}.ts -> fix it, or say why in your report'
        for name, other in (('a', 'b'), ('b', 'a'))], text
    _known_ignore(tmp_path, 'copies:save', 'the two save functions round to different units on purpose')
    code, text = _check(tmp_path, '--static')
    assert code == 0 and _block(text)[1:] == ['loosened: known.copies-save added with act = "ignore" -> name it in your report; '
                                              "loosening an agreement is the owner's decision"], text
    assert 'ignored: 2 (act = "ignore")' in _cli_fixture.last(tmp_path).splitlines(), _cli_fixture.last(tmp_path)


def test_two_declarations_of_one_name_with_different_members_are_a_lead(tmp_path):
    _project(tmp_path, {'a/contracts.py': '''
        from enum import StrEnum


        class AvailabilityStatus(StrEnum):
            READY = "ready"
            BLOCKED = "blocked"
    ''', 'b/contracts.py': '''
        from enum import StrEnum


        class AvailabilityStatus(StrEnum):
            AVAILABLE = "available"
            BLOCKED = "blocked"
    ''', 'a/kinds.py': 'from typing import Literal\nKind = Literal["member", "guest"]\n',
         'tests/test_case.py': 'def test_native():\n    assert True\n'})
    code, text = _check(tmp_path)
    assert _block(text)[1:] == [], text                      # old: only the --all listing lists it
    code, text = _check(tmp_path, '--all')
    # b/contracts.py and b/kinds.py keep the folder in the name of the a/ files (D17)
    assert _block(text)[1:] == [
        'before: declarations AvailabilityStatus at a/contracts.py:4 was broken at task start -> leave it unless your task is about it'], text
    (tmp_path / 'b/kinds.py').write_text('from typing import Literal\nKind = Literal["member", "guest", "staff"]\n', encoding='utf-8')
    code, text = _check(tmp_path)
    assert code == 0 and _block(text)[1:] == [
        "impact: declarations Kind: a/kinds.py:2 declares 'guest' | 'member'; b/kinds.py:2 declares 'guest' | 'member' | 'staff' "
        '-> fix it, or say why in your report'], text


def test_two_typescript_union_declarations_with_different_members_are_a_lead(tmp_path):
    _project(tmp_path, {'backend/src/lending.ts': "export type LendingStatus = 'DRAFT' | 'ACTIVE' | 'ENDED';\n"})
    (tmp_path / 'frontend/src').mkdir(parents=True)
    (tmp_path / 'frontend/src/lending.ts').write_text("export type LendingStatus = 'DRAFT' | 'ACTIVE';\n", encoding='utf-8')
    code, text = _check(tmp_path)
    assert code == 0 and _block(text)[1:] == [
        "impact: declarations LendingStatus: backend/src/lending.ts:1 declares 'ACTIVE' | 'DRAFT' | 'ENDED'; frontend/src/lending.ts:1 declares "
        "'ACTIVE' | 'DRAFT' -> fix it, or say why in your report"], text


def test_a_copy_this_change_makes_diverge_from_the_reference_is_new_never_broken_at_task_start(tmp_path):
    """Copy discovery (check): two copies agreed at the task start; the change unregisters one and changes it. Its copies
    finding is this change's (impact), not a problem the task started with (before)."""
    root = _project(tmp_path, {
        'orders.py': '''
            # flowguard: same ACCEPT ref
            def accept(days: int) -> bool:
                return days <= 3

            # flowguard: same ACCEPT
            def preview_accept(days: int) -> bool:
                return days <= 3
        ''',
        'tests/test_orders.py': 'from orders import accept, preview_accept\n\n\ndef test_accept():\n    assert accept(3) and preview_accept(2)\n',
    })
    orders = root / 'orders.py'
    orders.write_text(orders.read_text().replace('# flowguard: same ACCEPT\n', '').replace(
        'def preview_accept(days: int) -> bool:\n    return days <= 3', 'def preview_accept(days: int) -> bool:\n    return days <= 4'),
        encoding='utf-8')
    code, text = _check(root)
    shown = _block(text)
    assert code == 0 and not any(line.startswith('before: ') for line in shown), text
    assert 'impact: copies of ACCEPT: orders.py:preview_accept is a diverged copy of the reference orders.py:accept ' \
           '-> fix it, or say why in your report' in shown, text


def test_copies_meant_to_differ_are_recorded_by_known_add_with_act_ignore(tmp_path):
    """5.0 removed distinct: the copies finding's step names `known add ... --act ignore` instead, and that entry takes
    the copy out of the block (the copies family is one an automatic structure check finds)."""
    root = _project(tmp_path, {
        'orders.py': '''
            # flowguard: same ACCEPT ref
            def accept(days: int) -> bool:
                return days <= 3

            def preview_accept(days: int) -> bool:
                return days <= 3
        ''',
        'tests/test_orders.py': 'from orders import accept, preview_accept\n\n\ndef test_accept():\n    assert accept(3) and preview_accept(2)\n',
    })
    orders = root / 'orders.py'
    orders.write_text(orders.read_text().replace('def preview_accept(days: int) -> bool:\n    return days <= 3',
                                                 'def preview_accept(days: int) -> bool:\n    return days <= 4'), encoding='utf-8')
    impact = 'impact: copies of ACCEPT: orders.py:preview_accept is a diverged copy of the reference orders.py:accept'
    code, text = _check(root)
    assert code == 0 and any(line.startswith(impact) for line in _block(text)), text
    from contextlib import closing
    from flowguard.intent import owners
    from flowguard.intent.config import load_config
    from flowguard.structure import build
    with closing(build(root)) as graph:
        found = owners.check_findings(load_config(root), graph, anchors.collect(graph))
    step = next(issue.step for issue in found.issues if issue.name == 'copies:ACCEPT')
    assert step == ('choose one for each copy: call accept; or write # flowguard: same ACCEPT above the copy and make it '
                    'agree; or, for copies meant to differ, python -m flowguard known add copies:ACCEPT --act ignore --why '
                    'TEXT records that'), step
    assert _cli_fixture.main(['--root', root, 'known', 'add', 'copies:ACCEPT', '--act', 'ignore', '--why',
                              'the preview accepts a fourth day on purpose']) == 0
    code, text = _check(root)
    assert code == 0 and not any(line.startswith(impact) for line in _block(text)), text
    assert 'loosened: known.copies-accept added with act = "ignore"' in text, text


def test_a_rule_bound_to_a_typescript_copy_says_rules_run_python_functions_only(tmp_path):
    # Planning Tool's three ISO week copies are TypeScript; a rule bound to them was red with "home gone" and a
    # ModuleNotFoundError, as if the function had been deleted.
    _project(tmp_path, {
        'src/weeks.ts': '// flowguard: same ISO_WEEKS_IN_YEAR\nexport function weeks(year: number) { return 52; }\n',
        'tests/intent/iso_weeks.py': '''
            from flowguard.intent import rule, row

            @rule("ISO_WEEKS", decides="weeks in a year", fields={"year": int}, source="assumed: test", anchor="ISO_WEEKS_IN_YEAR")
            def ISO_WEEKS(year):
                return 52
        ''',
        'tests/test_flowguard_intent.py': 'def test_flowguard_intent(request):\n'
                                          '    from flowguard.intent.plugin import sentinel\n    sentinel(request.config)\n'})
    code, text = _check(tmp_path)
    red = [line for line in _block(text) if line.startswith('red: rule ISO_WEEKS')]
    assert code == 1 and len(red) == 1 and 'home gone' not in red[0] and 'ModuleNotFoundError' not in red[0], text
    assert red[0].startswith('red: rule ISO_WEEKS: src/weeks.ts:weeks is not Python: a rule runs only Python functions -> '), text
