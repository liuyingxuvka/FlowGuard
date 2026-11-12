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


def _deprecated_leads(root):
    """The 5.0-deprecated leads of the last run in `root`, which only `show --last` prints."""
    shown = _cli_fixture.last(root).splitlines()
    return shown[shown.index('deprecated leads (5.0):') + 1:] if 'deprecated leads (5.0):' in shown else []


def _leads(root):
    """The 5.0-deprecated leads of the last run in `root`, each `feature: text` (`show --last`)."""
    return [lead.strip() for lead in _deprecated_leads(root)]


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
    assert red == ['red: same LIMIT: limits.py:report changed behavior; 2 copies that answered the same are unchanged: limits.py:calendar  '
                   'limits.py:chart -> make report match reference chart(limits.py:2)',
                   'red: same LIMIT: on days=4: the reference limits.py:chart and limits.py:calendar return False, limits.py:report returns True '
                   '-> make limits.py:report agree with the reference'], text
    # The owner changed: its copies follow it.
    red, text = _checked_red(tmp_path, _copies(4, 3, 3, owner=True))
    assert red == ['red: same LIMIT: limits.py:chart changed behavior; 2 copies that answered the same are unchanged: limits.py:calendar  '
                   'limits.py:report -> update together, or call chart',
                   'red: same LIMIT: on days=4: the reference limits.py:chart returns True, limits.py:calendar and limits.py:report return False '
                   '-> make limits.py:calendar, limits.py:report agree with the reference'], text


def test_check_names_the_owner_when_it_changed_with_a_copy_and_a_third_copy_stayed(tmp_path):
    # Round 22 F1, second review: chart (the owner) and calendar changed, report did not. The red took the first
    # anchored function, calendar, and sent both back ("让 calendar、chart 回到原来的行为"), while the same-name red of
    # the same check sent report to the owner.
    _project(tmp_path, {'limits.py': _copies(3, 3, 3, owner=True)})
    red, text = _checked_red(tmp_path, _copies(4, 4, 3, owner=True))
    assert red == [*(f'red: same LIMIT: limits.py:{name} changed behavior; 1 copy that answered the same is unchanged: limits.py:report '
                     '-> update together, or call chart' for name in ('calendar', 'chart')),
                   'red: same LIMIT: on days=4: the reference limits.py:chart and limits.py:calendar return True, limits.py:report returns False '
                   '-> make limits.py:report agree with the reference'], text


def test_check_leaves_the_choice_between_copies_when_none_is_the_owner(tmp_path):
    _project(tmp_path, {'limits.py': _copies(3, 3, 3)})
    red, text = _checked_red(tmp_path, _copies(3, 3, 4))
    assert red == ['red: same LIMIT: limits.py:report change...anged: limits.py:calendar  limits.py:chart -> first decide which copy is correct: '
                   'for an intended change, update together or call report; otherwise make report return to the original behavior',
                   'red: same LIMIT: on days=4: limits.py:chart and limits.py:calendar return False, limits.py:report returns True '
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
        'known fixed?: known.limit: copies of LIMIT now agree -> the owner has not decided: revert, or say why in your report'], text


# Round 22 F1, second review: chart is the owner, report already differs from it at days=3 (`days < 3`), and this
# task changes calendar only (`days <= 4`). The red named the first copy that differs and listed report with the
# owner on that input (`2 份得 F（负责人 limits.py:2 chart、limits.py:12 report）`); 4.2.0 named both.
def _split_copies(calendar):
    """`_copies(3, calendar, 3, owner=True)` with report at `days < 3`."""
    source = _copies(3, calendar, 3, owner=True)
    return source[:source.rindex('days <= 3')] + 'days < 3\n'


# check runs copies no test reached on their current code alone: with a copy's file touched, every input where they
# differ is this change's (D24, fail-closed); pytest compares each input with the baseline (before on days=3).
SPLIT_RED = ['red: same LIMIT: on days=3: the reference limits.py:chart returns True, limits.py:report returns False; limits.py:calendar '
             'differs from the reference on days=4 -> make limits.py:report agree with the reference',
             'red: same LIMIT: on days=4: the reference limits.py:chart returns False, limits.py:calendar returns True; limits.py:report '
             'differs from the reference on days=3 -> make limits.py:calendar agree with the reference']


def test_check_names_every_copy_that_differs_from_the_owner_on_its_own_input(tmp_path):
    _project(tmp_path, {'limits.py': _split_copies(3)})
    red, text = _checked_red(tmp_path, _split_copies(4))
    assert [line for line in red if line.startswith('red: same LIMIT: on ')] == SPLIT_RED, text
    assert len(red) == 3, text          # and the changed calendar's own red; no pair is left to a line of its own


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

def test_fixed_10_a_registered_owner_lists_the_other_six_kwp_copies_by_behavior(tmp_path):
    _commit(_kwp(tmp_path))
    owner = tmp_path / 'Step1/src/kwp_step1/matlab_fallbacks.py'
    lines = owner.read_text(encoding='utf-8').splitlines(True)
    assert lines[13] == '\n' and lines[14].startswith('def matlab_round(')
    lines[13] = '# flowguard: owner MATLAB_ROUND\n'
    owner.write_text(''.join(lines), encoding='utf-8')
    code, text = _check(tmp_path)
    # copy discovery is a 5.0-deprecated heuristic: its leads are show --last's
    assert code == 0 and _block(text)[1:] == [], text
    leads = [lead.strip().removeprefix('unregistered copy discovery: ') for lead in _deprecated_leads(tmp_path)]
    header = next(line for line in leads if line.startswith('reference MATLAB_ROUND'))
    assert 'Step1/src/kwp_step1/matlab_fallbacks.py:15' in header and 'has 6 suspected copies' in header, text
    assert re.search('candidates: 6; time: \\d+\\.\\d\\d seconds', header) and '# flowguard: same MATLAB_ROUND' in header, text
    same = next(line for line in leads if line.startswith('copy: 3 copies'))
    assert 'not a proof' in same and all(place in same for place in (
        'Step3/src/kwp_step3/technology.py:53', 'Step2/src/kwp_step2/try_data.py:15',
        'Step10/step10_baublock_progress_maps.py:'))
    assert 'only comparable JSON inputs count; call-site reachability was not checked' in header, header
    half = [line for line in leads if 'value=-2.5 -> -2(reference returns -3)' in line]
    assert len(half) == 1 and half[0].startswith('similar 2 copies:') and 'simulation_preparation.py:25' in half[0] \
        and 'Step6a/kwp_step6a/config.py:' in half[0], text
    # Grouped by the first difference; int(x + 0.5) and floor(x + 0.5) still differ on negative whole numbers.
    assert 'these copies also differ on other representative values' in half[0], half[0]
    legacy = next(line for line in leads if 'step2_demand_library.py' in line)
    assert legacy.startswith('similar 1 copies:'), text
    assert not any('value=nan' in line for line in leads), text
    assert any(line.startswith('not compared:') and 'step2_demand_library.py' in line for line in leads), text
    assert len([line for line in leads if re.match('(copy:|diverged copy|similar) ', line)]) == 3, text


def test_fixed_11_three_changed_copies_name_the_four_left_behind(tmp_path):
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
    # No rules, so no pytest batch: the title still names the baseline the leads were compared with.
    title, *lines = _block(text)
    head = _git(tmp_path, 'rev-parse', 'HEAD').strip()
    assert re.fullmatch(rf'FlowGuard \d+\.\d+ \(since {head[:7]}\): 0 red, 7 not compared; \d+\.\d s', title), text
    assert lines == ['not compared: 7 functions (3/20 inputs not compared: non-finite JSON number) -> not a failure'], text
    # similar implementations are a 5.0-deprecated heuristic: its lead is show --last's
    lead = next(line.strip().removeprefix('similar-implementation leads: ') for line in _deprecated_leads(tmp_path) if 'changed behavior' in line)
    assert '(3 locations) changed behavior' in lead and all(place in lead for place in (
        'Step1/src/kwp_step1/matlab_fallbacks.py:15', 'Step3/src/kwp_step3/technology.py:53',
        'Step10/step10_baublock_progress_maps.py:'))
    twins, similar = lead.split('similar', 1)
    assert '1 previously equivalent copies are unchanged: Step6a/kwp_step6a/config.py:' in twins, lead
    assert all(place in similar for place in ('Step2/src/kwp_step2/simulation_preparation.py:25',
                                              'Step2/src/kwp_step2/try_data.py:15', 'Step2/step2_demand_library.py:')), lead
    assert '# flowguard: same MATLAB_ROUND ref' in lead


# ---- fixed examples 8, 14 and 18: static leads ---------------------------------------------------------

def test_fixed_8_one_changed_grace_copy_names_the_other_four(tmp_path):
    source = 'LIMITS = (14, 30)\n\n'
    source += 'def renewal(overdue_days: int) -> bool:\n    return overdue_days <= 14\n\n'
    source += 'def quote(late: int) -> bool:\n    return not late > 14\n\n'
    source += 'def standing(days: int) -> bool:\n    return days <= LIMITS[0]\n\n'
    for name in ('booking', 'delivery'):
        source += f'def {name}(days: int) -> str:\n' + ''.join(f'    work_{n} = {n}\n' for n in range(20))
        source += '    if days <= 14:\n        return "grace"\n' + ''.join(f'    later_{n} = {n}\n' for n in range(20))
        source += '    return "expired"\n\n'
    source += 'def unrelated(amount: int) -> bool:\n    return amount <= 15\n'
    (tmp_path / 'policy.py').write_text(source, encoding='utf-8')
    _project(tmp_path, {'tests/test_case.py': 'from policy import renewal\ndef test_native():\n    assert renewal(0)\n'})
    changed = source.replace('return overdue_days <= 14', 'return overdue_days <= 21')
    (tmp_path / 'policy.py').write_text(changed, encoding='utf-8')
    result = _pytest(tmp_path)
    text = _text(result)
    assert result.returncode == 0 and 'old values' not in result.stdout, text
    # A 5.0-deprecated heuristic: the lead is no line of the block, show --last lists it.
    lead = next(line for line in _deprecated_leads(tmp_path) if 'old values 14' in line)
    expected = [f'policy.py:{number}' for number, line in enumerate(changed.splitlines(), 1)
                if re.search(r'(<=|>) 14:?$|LIMITS\[0\]', line)]
    assert len(expected) == 4 and 'remain in 4 decisions:' in lead, (expected, text)
    assert all(place in lead for place in expected) and lead.count('(in a large function)') == 2, text
    assert '…' not in lead and lead.startswith('    old-value leads: '), lead


def test_fixed_14_a_rule_that_still_holds_the_old_value_is_a_lead(tmp_path):
    policy = _project(tmp_path, {'policy.py': '''
        GRACE_DAYS = 14

        # flowguard: sensor STANDING
        def standing(days: int) -> bool:
            return days <= GRACE_DAYS
    ''', 'tests/test_case.py': '''
        from policy import standing
        def test_native():
            assert standing(0)
    ''', 'tests/test_flowguard_intent.py': '''
        def test_flowguard_intent(request):
            from flowguard.intent.plugin import sentinel
            sentinel(request.config)
    ''', 'tests/intent/grace.py': '''
        from flowguard.intent import rule, row


        @rule("GRACE", decides="grace period", fields={"days": int}, anchor="STANDING",
              source="assumed: a member keeps standing for fourteen days")
        def GRACE(days):
            return days <= 14


        GRACE.rows(
            row(days=15, expect=False, why="day fifteen is past the grace period"),
            row(days=14, expect=True, why="the last grace day"),
        )
    '''}) / 'policy.py'
    policy.write_text(policy.read_text(encoding='utf-8').replace('GRACE_DAYS = 14', 'GRACE_DAYS = 21'), encoding='utf-8')
    text = _text(_pytest(tmp_path))
    assert ('    old-value leads: rule GRACE still uses old value 14(tests/intent/grace.py decision line 7, regression row line 12): '
            'if requirements changed, update the rule first') in _deprecated_leads(tmp_path), text


def test_fixed_18_numbers_equal_only_at_zero_are_unrelated_and_dict_keys_never_drift(tmp_path):
    _project(tmp_path, {'money.py': '''
        def margin(price: float) -> float:
            return price * 0.2


        def tax(amount: float) -> float:
            return amount * 0.19


        def keys(row):
            return {'id': row, 'name': 'x'}
    ''', 'tests/test_case.py': 'def test_native():\n    assert True\n'})
    money = tmp_path / 'money.py'
    money.write_text(money.read_text(encoding='utf-8').replace('def margin', '# flowguard: owner MARGIN\ndef margin')
                     + "\n\ndef upper(row):\n    return {'ID': row}\n", encoding='utf-8')
    code, text = _check(tmp_path, '--all')
    assert code == 0, text
    assert 'money.py:6' not in text and all(marker not in text for marker in ('suspected copy', 'suspected copies')) and 'spellings differ' not in text, text


def test_a_new_spelling_of_a_label_is_a_lead_and_an_old_one_is_not(tmp_path):
    _project(tmp_path, {'labels.py': '''
        def home(kind):
            if kind == 'My Organization':
                return 'home'
            return 'other'
    '''})
    code, text = _check(tmp_path)
    assert _block(text)[1:] == [] and not _deprecated_leads(tmp_path), text
    (tmp_path / 'view.py').write_text("def title(kind):\n    return 'My organization' if kind else ''\n", encoding='utf-8')
    code, text = _check(tmp_path)
    # label spellings are a 5.0-deprecated heuristic: a lead of show --last, no line of the block
    assert code == 0 and _block(text)[1:] == [], text
    lead = next(line for line in _deprecated_leads(tmp_path) if 'spellings differ' in line)
    assert "'My Organization'(labels.py:2)" in lead and "'My organization'(view.py:2, spelling added in this task)" in lead, text


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
    assert any('LIMIT' in line for line in found.section)


def test_reusing_static_findings_returns_its_issues_reds_and_leads_without_mutating_it(tmp_path, monkeypatch):
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
        assert static.issues and static.red and static.leads
        def repeated_static(*args, **kwargs):
            raise AssertionError('the existing static facts must be reused')
        monkeypatch.setattr(owners, 'static_findings', repeated_static)
        found = owners.check_findings(cfg, graph, index, base, everything=True, static=static)
    assert static == before
    assert found is not static
    assert found.issues == static.issues
    assert all(line in found.red for line in static.red)
    assert all(line in found.leads for line in static.leads)
    assert found.summary == static.summary
    assert found.section == static.section
    assert all(found.stats[key] == value for key, value in static.stats.items())


def test_copy_discovery_uses_sealed_source_and_lists_what_it_cannot_run(tmp_path):
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
    # copy discovery is a 5.0-deprecated heuristic: its leads are show --last's, no line of the block
    assert _block(text)[1:] == [], text
    leads = [lead.strip().removeprefix('unregistered copy discovery: ') for lead in _deprecated_leads(tmp_path)]
    copies = next(line for line in leads if line.startswith('before: copy:'))
    assert 'rules.py:6' in copies and 'vendor_copy.py:4' in copies and 'not a proof' in copies, leads
    unclear = next(line for line in leads if line.startswith('unavailable copies:'))
    assert 'rules.py:10' in unclear and '0.5' in unclear and 'completion' in unclear, unclear
    assert 'rules.py:16 (unsupported Import)' in unclear, unclear
    assert 'vendor_copy.py:4' not in unclear, unclear
    # FlowGuard runs copy discovery itself: only the project's own 4.2 owner spelling is deprecated
    notices = [line for line in result.stderr.splitlines() if line.startswith('deprecated: ')]
    assert notices == ['deprecated: function owner goes in 5.0 -> write same NAME ref'], result.stderr


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
    leads = [lead.strip().removeprefix('unregistered copy discovery: ') for lead in _deprecated_leads(tmp_path)]
    assert any('peer.py:2' in line and 'copy:' in line for line in leads), leads
    unavailable = next(line for line in leads if line.startswith('unavailable copies:'))
    assert 'peer.py:4' in unavailable and 'uses ' in unavailable, leads


def test_changed_alone_compares_baseline_source_without_importing_the_project(tmp_path):
    from contextlib import closing
    from flowguard.intent import owners
    from flowguard.intent.config import load_config
    from flowguard.structure import build
    marker = tmp_path / 'initialized.txt'
    source = f"open({str(marker)!r}, 'w').write('initialized')\ndef limit(value: int):\n    return value <= 3\n"
    _project(tmp_path, {'policy.py': source, 'peer.py': 'def copy(value: int):\n    return value <= 3\n'})
    base = _git(tmp_path, 'rev-parse', 'HEAD').strip()
    (tmp_path / 'policy.py').write_text(source.replace('<= 3', '<= 4'), encoding='utf-8')
    cfg = load_config(tmp_path)
    with closing(build(tmp_path, roots=cfg.roots)) as graph:
        found = owners.changed_alone(cfg, graph, anchors.collect(graph), owners.Change(cfg, graph, base))
    assert not marker.exists()
    assert any('changed behavior' in line and 'peer.py:1' in line for line in found.leads), found


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
    assert not found.red
    assert any('not compared' in line and 'same raised exception' in line for line in found.leads), found
    assert not any('changed behavior' in line for line in found.leads), found


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
    forked = next(lead for lead in _leads(tmp_path) if lead.startswith('unregistered copy discovery: diverged copy 1 copies'))
    assert 'Step1/src/kwp_step1/utils.py:' in forked and "-> 'district_heat'(reference returns 'waermenetze')" in forked, forked


RULE_FILE = ('AGENTS.md', 'The two normalizers stay apart until the step 1 importer is retired next year.\n')
DECIDED = ('decision = "the step 1 copy stays as it is until the old importer is retired"\n'
           'source = { file = "AGENTS.md", text = "The two normalizers stay apart until the step 1 importer is retired next year." }\n')


def test_an_owner_whose_copies_the_owner_decided_gets_no_discovery_leads(tmp_path):
    # Round 23 check of r23-ondelete: [structure."copies:TECHNOLOGY"] closed the --all entry, but check still printed
    # the owner's look-alike leads.
    _copy_fixture(tmp_path, 'kwp_normalize')
    _project(tmp_path, {RULE_FILE[0]: RULE_FILE[1]}, pyproject='[tool.pytest.ini_options]\npythonpath = ["Step1/src", "Step3/src"]\n')
    technology = tmp_path / 'Step3/src/kwp_step3/technology.py'
    technology.write_text(technology.read_text(encoding='utf-8').replace('def normalize_technology_name(value: object)',
                                                          '# flowguard: owner TECHNOLOGY\ndef normalize_technology_name(value: object)'), encoding='utf-8')
    diverged = 'unregistered copy discovery: diverged copy 1 copies'
    code, text = _check(tmp_path)
    assert code == 0 and any(lead.startswith(diverged) for lead in _leads(tmp_path)), text
    (tmp_path / '.flowguard').mkdir(exist_ok=True)
    # Round 24 review: a decision on a same-name family whose names merely include the anchor name is not this one
    (tmp_path / '.flowguard/ledger.toml').write_text('[structure."copies:helper+TECHNOLOGY"]\n' + DECIDED, encoding='utf-8')
    code, text = _check(tmp_path)
    assert code == 0 and any(lead.startswith(diverged) for lead in _leads(tmp_path)), text
    (tmp_path / '.flowguard/ledger.toml').write_text('[structure."copies:TECHNOLOGY"]\n' + DECIDED, encoding='utf-8')
    code, text = _check(tmp_path)
    assert code == 0 and _block(text)[1:] == [] and _leads(tmp_path) == [], text


def test_a_function_whose_copies_the_owner_decided_gets_no_changed_alone_lead(tmp_path):
    body = ("export function total(items: number[], rate: number): number {{\n  let sum = 0;\n"
            "  for (const item of items) {{\n    if (item > {limit}) {{ sum += item * rate; }} else {{ sum += item; }}\n  }}\n"
            "  return Math.round(sum * 100) / 100;\n}}\n")
    _project(tmp_path, {'src/a.ts': body.format(limit=10), 'src/b.ts': body.format(limit=20), RULE_FILE[0]: RULE_FILE[1]})
    (tmp_path / 'src/a.ts').write_text(body.format(limit=10).replace('* 100) / 100', '* 1000) / 1000'), encoding='utf-8')
    static = lambda: _check(tmp_path, '--static')
    code, text = static()
    assert code == 0 and any(lead.startswith('similar-implementation leads: total(src/a.ts:1) changed;') for lead in _leads(tmp_path)), text
    assert _block(text)[1:] == ['before: copies total at a.ts:total was broken at task start -> leave it unless your task is about it'], text
    (tmp_path / '.flowguard').mkdir(exist_ok=True)
    (tmp_path / '.flowguard/ledger.toml').write_text('[structure."copies:total"]\n' + DECIDED, encoding='utf-8')
    code, text = static()
    assert code == 0 and _block(text)[1:] == [] and _leads(tmp_path) == [], text


def test_a_copies_decision_silences_only_the_members_of_its_family(tmp_path):
    # Round 24 review: [structure."copies:save"] for two drifted module-level `save` functions also silenced the
    # changed-alone lead of every function or method named save anywhere, such as two identical repository methods.
    body = ("export function save(items: number[], rate: number): number {{\n  let sum = 0;\n"
            "  for (const item of items) {{\n    if (item > {limit}) {{ sum += item * rate; }} else {{ sum += item; }}\n  }}\n"
            "  return Math.round(sum * 100) / 100;\n}}\n")
    method = ("export class {name}Repo {{\n  save(row: any, db: any): any {{\n    const data = {{ ...row, updatedAt: new Date() }};\n"
              "    if (!data.id) {{ throw new Error('no id'); }}\n    return db.{table}.update({{ where: {{ id: data.id }}, data }});\n"
              "  }}\n}}\n")
    _project(tmp_path, {'src/a.ts': body.format(limit=10), 'src/b.ts': body.format(limit=20), RULE_FILE[0]: RULE_FILE[1],
                        'src/repo/user.ts': method.format(name='User', table='row'),
                        'src/repo/order.ts': method.format(name='Order', table='row')})
    (tmp_path / '.flowguard').mkdir(exist_ok=True)
    (tmp_path / '.flowguard/ledger.toml').write_text('[structure."copies:save"]\n' + DECIDED, encoding='utf-8')
    _git(tmp_path, 'add', '.')
    _git(tmp_path, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'decided')
    user = tmp_path / 'src/repo/user.ts'
    user.write_text(user.read_text(encoding='utf-8').replace("throw new Error('no id')", "throw new Error('no user id')"),
                    encoding='utf-8')
    code, text = _check(tmp_path, '--static')
    assert code == 0 and _block(text)[1:] == [], text
    assert any(lead.startswith('similar-implementation leads: UserRepo.save(src/repo/user.ts:2) changed; previously identical copies: 1 '
                               'unchanged: src/repo/order.ts:2') for lead in _leads(tmp_path)), text
    # the decided family itself stays quiet: a changed member does not list the other member
    _git(tmp_path, 'checkout', '-q', '--', 'src/repo/user.ts')
    (tmp_path / 'src/a.ts').write_text(body.format(limit=10).replace('* 100) / 100', '* 1000) / 1000'), encoding='utf-8')
    code, text = _check(tmp_path, '--static')
    assert code == 0 and _block(text)[1:] == [] and _leads(tmp_path) == [], text


def test_a_copies_decision_holds_for_the_family_the_owner_decided_on(tmp_path):
    # Round 25 check of ondelete-1: the decided family was read from the edited code, so an edit that moved a member
    # away from the other brought back the lead the decision had closed, while an exact copy the decided problem
    # left out joined the family once its twin was edited and lost the lead the guide promises it.
    body = ("export function save(items: number[], rate: number): number {{\n  let sum = 0;\n"
            "  for (const item of items) {{\n    if (item > {limit}) {{ sum += item * rate; }} else {{ sum += item; }}\n  }}\n"
            "  return Math.round(sum * 100) / 100;\n}}\n")
    decided = {'.flowguard/ledger.toml': '[structure."copies:save"]\n' + DECIDED, RULE_FILE[0]: RULE_FILE[1]}
    moved = tmp_path / 'moved'
    _project(moved, {'src/a.ts': body.format(limit=10), 'src/b.ts': body.format(limit=20), **decided})
    edited = (body.format(limit=10)
              .replace('sum += item * rate; }', 'sum += item * rate; } else if (item < 0) { throw new Error("negative " + item); }')
              .replace('  return Math.round', '  if (sum > 1e9) { return -1; }\n  return Math.round'))
    (moved / 'src/a.ts').write_text(edited, encoding='utf-8')
    code, text = _check(moved, '--static')
    assert code == 0 and _block(text)[1:] == [] and _leads(moved) == [], text
    # an exact copy of a member that the decided problem does not list (src/c.ts beside src/a.ts) keeps its lead
    exact = tmp_path / 'exact'
    _project(exact, {'src/a.ts': body.format(limit=10), 'src/b.ts': body.format(limit=20), 'src/c.ts': body.format(limit=10)})
    code, text = _check(exact, '--static', '--all')
    assert _block(text)[1:] == [f'before: copies save at {name}.ts:save was broken at task start -> leave it unless your task is about it'
                                for name in ('a', 'b')], text
    for name, content in decided.items():
        (exact / name).parent.mkdir(exist_ok=True)
        (exact / name).write_text(content, encoding='utf-8')
    _git(exact, 'add', '.')
    _git(exact, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'decided')
    (exact / 'src/a.ts').write_text(body.format(limit=10).replace('* 100) / 100', '* 1000) / 1000'), encoding='utf-8')
    code, text = _check(exact, '--static')
    assert code == 0 and _block(text)[1:] == [], text
    assert _leads(exact) == [
        'similar-implementation leads: save(src/a.ts:1) changed; previously identical copies: 1 unchanged: src/c.ts:1(update them together '
        'when required; to lock them, write above the reference: // flowguard: same SAVE ref, above the copy: // flowguard: same SAVE)'], text


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


def test_a_copies_decision_on_a_problem_this_task_made_quiets_its_changed_alone_lead(tmp_path):
    # Final check of r25-init: two identical save functions at the baseline are no copies problem; the task edits
    # one, the owner decides the copies problem that appears, and the changed-alone lead about the pair stayed.
    body = ("export function save(items: number[], rate: number): number {{\n  let sum = 0;\n"
            "  for (const item of items) {{\n    if (item > 10) {{ sum += item * rate; }} else {{ sum += item; }}\n  }}\n"
            "  return Math.round(sum * {scale}) / {scale};\n}}\n")
    _project(tmp_path, {'src/a.ts': body.format(scale=100), 'src/b.ts': body.format(scale=100), RULE_FILE[0]: RULE_FILE[1]})
    (tmp_path / 'src/a.ts').write_text(body.format(scale=1000), encoding='utf-8')
    code, text = _check(tmp_path, '--static')
    assert code == 0 and any(lead.startswith('similar-implementation leads: save(src/a.ts:1) changed;') for lead in _leads(tmp_path)), text
    assert _block(text)[1:] == [
        f'impact: copies save: {name}.ts:save has another body than the same-named save in src/{other}.ts -> fix it, or say why in your report'
        for name, other in (('a', 'b'), ('b', 'a'))], text
    (tmp_path / '.flowguard').mkdir(exist_ok=True)
    (tmp_path / '.flowguard/ledger.toml').write_text('[structure."copies:save"]\n' + DECIDED, encoding='utf-8')
    code, text = _check(tmp_path, '--static')
    assert code == 0 and _block(text)[1:] == [] and _leads(tmp_path) == [], text


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


def test_a_similar_implementation_lead_leaves_out_and_never_asks_to_register_the_copies_registered_with_it(tmp_path):
    """A changed copy of `same ACCEPT` whose former twin is the registered reference: that name's comparison covers the
    pair, so the lead names only the unregistered look-alike, under the registered name, and asks to mark only it."""
    root = _project(tmp_path, {
        'orders.py': '''
            # flowguard: same ACCEPT ref
            def accept(days: int) -> bool:
                return days <= 3


            # flowguard: same ACCEPT
            def preview_accept(days: int) -> bool:
                return days <= 3


            def quote_accept(days: int) -> bool:
                return days <= 3
        ''',
    })
    orders = root / 'orders.py'
    orders.write_text(orders.read_text().replace('def preview_accept(days: int) -> bool:\n    return days <= 3',
                                                 'def preview_accept(days: int) -> bool:\n    return days <= 4'), encoding='utf-8')
    _check(root, '--static')
    leads = [lead for lead in _leads(root) if lead.startswith('similar-implementation leads: ')]
    assert len(leads) == 1 and 'orders.py:2' not in leads[0] and 'PREVIEW_ACCEPT' not in leads[0] and ' ref' not in leads[0], leads
    assert 'orders.py:11' in leads[0] and leads[0].endswith('write above each copy not marked yet: # flowguard: same ACCEPT)'), leads
    # check compares the behaviour instead; none of its leads asks to register the registered copies either
    _check(root)
    assert not any('PREVIEW_ACCEPT' in lead for lead in _leads(root)), _leads(root)
    # With the look-alike registered too, every former twin is covered: no lead at all.
    orders.write_text(orders.read_text().replace('\ndef quote_accept', '# flowguard: same ACCEPT\ndef quote_accept'), encoding='utf-8')
    _git(root, 'add', '.')
    _git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'mark the look-alike')
    orders.write_text(orders.read_text().replace('return days <= 4', 'return days <= 5'), encoding='utf-8')
    _check(root, '--static')
    assert not any(lead.startswith('similar-implementation leads: ') for lead in _leads(root)), _leads(root)
