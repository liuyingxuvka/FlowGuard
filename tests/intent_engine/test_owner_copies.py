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
    _project(tmp_path, {'policy.py': mapped})
    code, text = _check(tmp_path)
    assert code == 1, text
    assert ('red: same-name anchor ELIGIBLE：days=4，2 copies: 1 copies return F (reference policy.py:2 owner), 1 copies return T (policy.py:5 copy) -> make policy.py:5 copy agree with the reference;') in text, text


def test_math_is_not_grey_and_representatives_include_halves_and_non_finite_values(tmp_path):
    _project(tmp_path, {'rounding.py': '''
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
    '''})
    code, text = _check(tmp_path)
    assert code == 1, text
    assert ('red: same-name anchor ROUND：value=-0.5，2 copies: 1 copies return -1 (reference rounding.py:6 away), 1 copies return 0 (rounding.py:13 up) -> make rounding.py:13 up agree with the reference;') in text, text
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
    assert agreed.returncode == 0 and 'same-name anchor' not in _text(agreed), _text(agreed)
    policy.write_text(policy.read_text(encoding='utf-8').replace('overdue_days <= 3', 'overdue_days <= 5'), encoding='utf-8')
    result = _pytest(tmp_path)
    text = _text(result)
    assert result.returncode == 1 and '1 passed' in result.stdout, text
    assert 'red: same-name anchor ELIGIBLE：days=4，2 copies: 1 copies return F (policy.py:11 eligible), 1 copies return T (policy.py:16 preview)' in text, text


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
    return [line for line in text.splitlines() if line.startswith('red: same-name anchor LIMIT')], text


def test_three_same_name_copies_are_counted_by_answer_and_the_red_does_not_choose_the_right_one(tmp_path):
    # 4.2 told the AI to change the copy the test reached (`让 chart 和同名副本一致`), here one of the two that
    # agree: done as written, it copies the odd one's answer. The red counts the answers and leaves the choice.
    _project(tmp_path, {'limits.py': _copies(3, 3, 3), **REACHES_CHART})
    red, text = _same_name_red(tmp_path, _copies(3, 3, 4))
    assert red == ['red: same-name anchor LIMIT：days=4，3 copies: 2 copies return F (limits.py:2 chart, limits.py:7 calendar), 1 copies return T (limits.py:12 report) -> first decide which copy is correct, then make the remaining copies agree with it; if intentionally different, use different anchor names and declare distinct'], text


def test_two_same_name_copies_are_one_answer_each_and_an_owner_stays_the_reference(tmp_path):
    _project(tmp_path, {'limits.py': _copies(3, 3), **REACHES_CHART})
    red, text = _same_name_red(tmp_path, _copies(4, 3))
    # one each: no side is the larger one, and the step names no copy to change
    assert red == ['red: same-name anchor LIMIT：days=4，2 copies: 1 copies return T (limits.py:2 chart), 1 copies return F (limits.py:7 calendar) -> first decide which copy is correct, then make the other copy agree with it; if intentionally different, use different anchor names and declare distinct'], text
    # The owner is the reference its copies follow: the copy changes, also when the test reaches the owner
    # (4.2 then said `让 chart 和同名副本一致`, the owner after its copy).
    red, text = _same_name_red(tmp_path, _copies(3, 4, owner=True))
    assert red == ['red: same-name anchor LIMIT：days=4，2 copies: 1 copies return F (reference limits.py:2 chart), 1 copies return T (limits.py:7 calendar) -> make limits.py:7 calendar agree with the reference; if intentionally different, use different anchor names and declare distinct'], text


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
    assert red == ['red: anchor LIMIT：report（limits.py:12） changed behavior; 2 previously equivalent copies are unchanged: limits.py:7  limits.py:2 → make report match reference chart(limits.py:2)',
                   'red: same-name anchor LIMIT：days=4，3 copies: 2 copies return F (reference limits.py:2 chart, limits.py:7 calendar), 1 copies return T (limits.py:12 report) -> make limits.py:12 report agree with the reference; if intentionally different, use different anchor names and declare distinct'], text
    # The owner changed: its copies follow it.
    red, text = _checked_red(tmp_path, _copies(4, 3, 3, owner=True))
    assert red == ['red: reference LIMIT：chart（limits.py:2） changed behavior; 2 previously equivalent copies are unchanged: limits.py:7  limits.py:12 → update together, or call chart',
                   'red: same-name anchor LIMIT：days=4，3 copies: 1 copies return T (reference limits.py:2 chart), 2 copies return F (limits.py:7 calendar, limits.py:12 report) -> make limits.py:7 calendar、limits.py:12 report agree with the reference; if intentionally different, use different anchor names and declare distinct'], text


def test_check_names_the_owner_when_it_changed_with_a_copy_and_a_third_copy_stayed(tmp_path):
    # Round 22 F1, second review: chart (the owner) and calendar changed, report did not. The red took the first
    # anchored function, calendar, and sent both back ("让 calendar、chart 回到原来的行为"), while the same-name red of
    # the same check sent report to the owner.
    _project(tmp_path, {'limits.py': _copies(3, 3, 3, owner=True)})
    red, text = _checked_red(tmp_path, _copies(4, 4, 3, owner=True))
    assert red == ['red: reference LIMIT：calendar（limits.py:7）、chart（limits.py:2） (2 locations) changed behavior; 1 previously equivalent copies are unchanged: limits.py:12 → update together, or call chart',
                   'red: same-name anchor LIMIT：days=4，3 copies: 2 copies return T (reference limits.py:2 chart, limits.py:7 calendar), 1 copies return F (limits.py:12 report) -> make limits.py:12 report agree with the reference; if intentionally different, use different anchor names and declare distinct'], text


def test_check_leaves_the_choice_between_copies_when_none_is_the_owner(tmp_path):
    _project(tmp_path, {'limits.py': _copies(3, 3, 3)})
    red, text = _checked_red(tmp_path, _copies(3, 3, 4))
    assert red == ['red: anchor LIMIT：report（limits.py:12） changed behavior; 2 previously equivalent copies are unchanged: limits.py:7  limits.py:2 → first decide which copy is correct: for an intended change, update together or call report; otherwise make report return to the original behavior',
                   'red: same-name anchor LIMIT：days=4，3 copies: 2 copies return F (limits.py:2 chart, limits.py:7 calendar), 1 copies return T (limits.py:12 report) -> first decide which copy is correct, then make the remaining copies agree with it; if intentionally different, use different anchor names and declare distinct'], text


# Round 22 F1, second review: chart is the owner, report already differs from it at days=3 (`days < 3`), and this
# task changes calendar only (`days <= 4`). The red named the first copy that differs and listed report with the
# owner on that input (`2 份得 F（负责人 limits.py:2 chart、limits.py:12 report）`); 4.2.0 named both.
def _split_copies(calendar):
    """`_copies(3, calendar, 3, owner=True)` with report at `days < 3`."""
    source = _copies(3, calendar, 3, owner=True)
    return source[:source.rindex('days <= 3')] + 'days < 3\n'


SPLIT_RED = ('red: same-name anchor LIMIT：days=3，3 copies: 1 copies return T (reference limits.py:2 chart), 1 copies return F (limits.py:12 report), plus 1 copies differ from the reference on other inputs: limits.py:7 calendar (days=4) -> make limits.py:12 report agree with the reference；days=4，3 copies: 1 copies return F (reference limits.py:2 chart), 1 copies return T (limits.py:7 calendar), plus 1 copies differ from the reference on other inputs: limits.py:12 report (days=3) -> make limits.py:7 calendar agree with the reference; if intentionally different, use different anchor names and declare distinct')


def test_check_names_every_copy_that_differs_from_the_owner_on_its_own_input(tmp_path):
    _project(tmp_path, {'limits.py': _split_copies(3)})
    red, text = _checked_red(tmp_path, _split_copies(4))
    assert [line for line in red if 'same-name anchor' in line] == [SPLIT_RED], text
    assert 'red same-name anchor' not in text, text          # no pair is left to a block of its own


def test_pytest_names_every_copy_that_differs_from_the_owner_on_its_own_input(tmp_path):
    _project(tmp_path, {'limits.py': _split_copies(3), **REACHES_CHART})
    red, text = _same_name_red(tmp_path, _split_copies(4))
    assert red == [SPLIT_RED], text


# ---- fixed examples 10 and 11: the KWP rounding copies ---------------------------------------------------

def test_fixed_10_a_registered_owner_lists_the_other_six_kwp_copies_by_behavior(tmp_path):
    _commit(_kwp(tmp_path))
    owner = tmp_path / 'Step1/src/kwp_step1/matlab_fallbacks.py'
    lines = owner.read_text(encoding='utf-8').splitlines(True)
    assert lines[13] == '\n' and lines[14].startswith('def matlab_round(')
    lines[13] = '# flowguard: owner MATLAB_ROUND\n'
    owner.write_text(''.join(lines), encoding='utf-8')
    code, text = _check(tmp_path)
    assert code == 0, text
    leads = _lines(text)
    header = next(line for line in leads if line.startswith('lead: reference MATLAB_ROUND'))
    assert 'Step1/src/kwp_step1/matlab_fallbacks.py:15' in header and 'has 6 suspected copies' in header, text
    assert re.search('candidates: 6; time: \\d+\\.\\d\\d seconds', header) and '# flowguard: same MATLAB_ROUND' in header, text
    same = next(line for line in leads if line.startswith('lead: copy: 3 copies'))
    assert 'not a proof' in same and all(place in same for place in (
        'Step3/src/kwp_step3/technology.py:53', 'Step2/src/kwp_step2/try_data.py:15',
        'Step10/step10_baublock_progress_maps.py:'))
    assert 'compared on all reference values; call-site reachability of negative, non-finite and other values was not checked' in header, header
    half = [line for line in leads if 'value=-2.5 → -2(reference returns -3）' in line]
    assert len(half) == 1 and half[0].startswith('lead: similar 2 copies:') and 'simulation_preparation.py:25' in half[0] \
        and 'Step6a/kwp_step6a/config.py:' in half[0], text
    # Grouped by the first difference; int(x + 0.5) and floor(x + 0.5) still differ on negative whole numbers.
    assert 'these copies also differ on other representative values' in half[0], half[0]
    legacy = next(line for line in leads if 'step2_demand_library.py' in line)
    assert legacy.startswith('lead: similar 1 copies:') and 'value=nan → 0(reference returns raised ValueError）' in legacy, text
    assert len([line for line in leads if re.match('lead: (copy:|diverged copy|similar) ', line)]) == 3, text


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
    title = next(line for line in text.splitlines() if line.startswith('FlowGuard（'))
    assert title.startswith('FlowGuard（since task start '), text
    lead = next(line for line in _lines(text) if 'changed behavior' in line)
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
    assert result.returncode == 0, text
    lead = next(line for line in _lines(text) if 'old values 14' in line)
    expected = [f'policy.py:{number}' for number, line in enumerate(changed.splitlines(), 1)
                if re.search(r'(<=|>) 14:?$|LIMITS\[0\]', line)]
    assert len(expected) == 4 and 'remain in 4 decisions:' in lead, (expected, text)
    assert all(place in lead for place in expected) and lead.count('(in a large function)') == 2, text
    assert '…' not in lead and '# flowguard: same NAME ref' in lead


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
    assert 'lead: rule GRACE still uses old value 14(tests/intent/grace.py decision line 7、regression row line 12): if requirements changed, update the rule first' in text, text


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
    assert 'spellings differ' not in text, text
    (tmp_path / 'view.py').write_text("def title(kind):\n    return 'My organization' if kind else ''\n", encoding='utf-8')
    code, text = _check(tmp_path)
    lead = next(line for line in _lines(text) if 'spellings differ' in line)
    assert "'My Organization'（labels.py:2）" in lead and "'My organization'(view.py:2, spelling added in this task)" in lead, text


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
    assert code == 0 and 'outside the declared writer' not in text, text
    # Enter pytest's cached static route before --all, while leaving every real writer unchanged.
    (tmp_path / 'changed.py').write_text('def unrelated(): return 1\n', encoding='utf-8')
    code, text = _check(tmp_path, '--all')
    assert code == 0 and 'lead: before: hires.reserved writes outside the declared writer: shop/store.py:7 legacy（sql:update, value 0）' in text, text
    (tmp_path / 'shop/api.py').write_text('def cancel(db, hire_id):\n    db.execute("UPDATE hires SET reserved = 0 WHERE id = ?", (hire_id,))\n', encoding='utf-8')
    code, text = _check(tmp_path)
    assert code == 1, text
    red = next(line for line in text.splitlines() if line.startswith('red: new write outside the declared writer'))
    assert 'hires.reserved：shop/api.py:2 cancel（sql:update, value 0）' in red and 'allowed only: shop.store:reserve' in red, red
    assert 'add shop.api:cancel to the writers agreement (comment at shop/store.py:1）' in red and 'legacy' not in red, red
    result = _pytest(tmp_path)
    assert result.returncode == 1 and 'red: new write outside the declared writer for hires.reserved' in _text(result), _text(result)


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


def test_copy_discovery_replays_through_the_runtime_and_lists_what_it_cannot_run(tmp_path):
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
           '_real = R.Runtime._replay_rows\n'
           'def _counted(self, original, *a, **k):\n'
           '    sys.__stderr__.write("REPLAY " + original.__qualname__ + "\\n")\n'
           '    return _real(self, original, *a, **k)\n'
           'R.Runtime._replay_rows = _counted\n')
    result = subprocess.run([sys.executable, '-c', _cli_fixture._BOOT, SOURCE, 'unused-marker', spy,
                             '--root', str(tmp_path), 'check', '--all'], cwd=tmp_path, capture_output=True, text=True, timeout=120)
    text = _text(result)
    assert result.returncode == 0, text
    replayed = set(re.findall(r'REPLAY (\w+)', result.stderr))
    assert {'half', 'same', 'spin'} <= replayed, result.stderr
    assert re.search('copy: 1 copies \\(match the reference on \\d+ representative values; not a proof\\): rules.py:6', text), text
    unclear = next(line for line in _lines(text) if line.startswith('lead: unavailable copies:'))
    assert 'rules.py:10（exceeded 0.5 seconds without completion）' in unclear, unclear
    assert "vendor_copy.py:4（import failed: ModuleNotFoundError: No module named 'not_installed_anywhere'）" in unclear, unclear
    # `broken` imports json inside its body: that import now runs under the replay guard, and the copy's
    # TypeError for every representative is a behaviour to compare, not something left unseen.
    assert 'rules.py:16' not in unclear, unclear


def test_a_new_copy_of_a_registered_owner_is_red(tmp_path):
    _project(tmp_path, {'rules.py': '''
        # flowguard: owner HALF
        def half(value: float) -> float:
            return value * 0.5
    '''})
    code, text = _check(tmp_path)
    assert code == 0 and not _lines(text), text
    rules = tmp_path / 'rules.py'
    rules.write_text(rules.read_text(encoding='utf-8') + '\n\ndef again(amount: float) -> float:\n    return 0.5 * amount\n', encoding='utf-8')
    code, text = _check(tmp_path)
    assert code == 1, text
    assert 'red: reference HALF（rules.py:2） has a new copy outside it: rules.py:6(copy) -> call half, or write above it: # flowguard: same HALF' in text, text


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
    assert code == 0 and 'new write outside the declared writer' not in text, text
    (tmp_path / 'backend/src/services/rogue.ts').write_text(
        'export async function moveEmployee(prisma: any, id: string, unit: string) {\n'
        '  await prisma.employee.update({ where: { id }, data: { organizationalUnitId: unit } });\n}\n', encoding='utf-8')
    code, text = _check(tmp_path)
    assert code == 1, text
    red = next(line for line in text.splitlines() if line.startswith('red: new write outside the declared writer'))
    assert red.startswith('red: new write outside the declared writer for Employee.organizationalUnitId：backend/src/services/rogue.ts:2 moveEmployee（update）'), red
    assert 'allowed only: transferEmployee' in red and 'comment at backend/src/owners.ts:1' in red and red.count('.ts:') == 2, red


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
    _project(tmp_path, {'shop/__init__.py': '', 'shop/store.py': '''
        def _mark(db, hire_id):
            db.execute("UPDATE hires SET state = 'held' WHERE id = ?", (hire_id,))


        def _deep(db, hire_id):
            _mark(db, hire_id)


        def reserve(db, hire_id):
            db.execute("UPDATE hires SET reserved = 1 WHERE id = ?", (hire_id,))
            _deep(db, hire_id)


        def release(db, hire_id):
            db.execute("UPDATE hires SET reserved = 0 WHERE id = ?", (hire_id,))


        def import_rows(db):
            db.execute("UPDATE hires SET reserved = 0")
    '''})
    code, text = _check(tmp_path)
    assert code == 0 and 'missing paired write' not in text, text
    store = tmp_path / 'shop/store.py'
    store.write_text("# flowguard: owner hires.reserved with=hires.state=held alone=shop.store:import_rows(bulk import marks rows later)\n"
                     + store.read_text(encoding='utf-8'), encoding='utf-8')
    code, text = _check(tmp_path)
    assert code == 1, text
    red = next(line for line in text.splitlines() if line.startswith('red: missing paired write'))
    # Round 20 semantics change: the partner is looked for in the same operation (callers three levels up,
    # then three levels down from them), no longer in the writer's own call tree only.
    assert red.startswith('red: missing paired write for hires.reserved：shop/store.py:16 release writes hires.reserved, the same operation (3 caller levels, then 3 callee levels) does not write hires.state=held'), red
    assert 'reserve' not in red.partition('：')[2].split(' writes ')[0] and 'import_rows' not in red and 'except=path:function(reason)' in red, red


def test_copy_discovery_compares_on_the_codes_own_literals(tmp_path):
    _copy_fixture(tmp_path, 'kwp_normalize')
    _project(tmp_path, {}, pyproject='[tool.pytest.ini_options]\npythonpath = ["Step1/src", "Step3/src"]\n')
    technology = tmp_path / 'Step3/src/kwp_step3/technology.py'
    technology.write_text(technology.read_text(encoding='utf-8').replace('def normalize_technology_name(value: object)',
                                                          '# flowguard: owner TECHNOLOGY\ndef normalize_technology_name(value: object)'), encoding='utf-8')
    code, text = _check(tmp_path)
    assert code == 0, text
    forked = next(line for line in _lines(text) if line.startswith('lead: diverged copy 1 copies'))
    assert 'Step1/src/kwp_step1/utils.py:' in forked and "→ 'district_heat'(reference returns 'waermenetze'）" in forked, forked


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
    code, text = _check(tmp_path)
    assert code == 0 and any(line.startswith('lead: diverged copy 1 copies') for line in _lines(text)), text
    (tmp_path / '.flowguard').mkdir(exist_ok=True)
    # Round 24 review: a decision on a same-name family whose names merely include the anchor name is not this one
    (tmp_path / '.flowguard/ledger.toml').write_text('[structure."copies:helper+TECHNOLOGY"]\n' + DECIDED, encoding='utf-8')
    code, text = _check(tmp_path)
    assert code == 0 and any(line.startswith('lead: diverged copy 1 copies') for line in _lines(text)), text
    (tmp_path / '.flowguard/ledger.toml').write_text('[structure."copies:TECHNOLOGY"]\n' + DECIDED, encoding='utf-8')
    code, text = _check(tmp_path)
    assert code == 0, text
    assert not [line for line in _lines(text) if 'TECHNOLOGY' in line or line.startswith(('lead: diverged copy', 'lead: copy'))], text


def test_a_function_whose_copies_the_owner_decided_gets_no_changed_alone_lead(tmp_path):
    body = ("export function total(items: number[], rate: number): number {{\n  let sum = 0;\n"
            "  for (const item of items) {{\n    if (item > {limit}) {{ sum += item * rate; }} else {{ sum += item; }}\n  }}\n"
            "  return Math.round(sum * 100) / 100;\n}}\n")
    _project(tmp_path, {'src/a.ts': body.format(limit=10), 'src/b.ts': body.format(limit=20), RULE_FILE[0]: RULE_FILE[1]})
    (tmp_path / 'src/a.ts').write_text(body.format(limit=10).replace('* 100) / 100', '* 1000) / 1000'), encoding='utf-8')
    static = lambda: _check(tmp_path, '--static')
    code, text = static()
    assert code == 0 and any(line.startswith('lead: total(src/a.ts:1) changed;') for line in _lines(text)), text
    (tmp_path / '.flowguard').mkdir(exist_ok=True)
    (tmp_path / '.flowguard/ledger.toml').write_text('[structure."copies:total"]\n' + DECIDED, encoding='utf-8')
    code, text = static()
    assert code == 0 and not any(line.startswith('lead: total(') for line in _lines(text)), text


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
    assert code == 0, text
    assert any(line.startswith('lead: UserRepo.save(src/repo/user.ts:2) changed; previously identical copies: 1 unchanged: src/repo/order.ts:2')
               for line in _lines(text)), text
    # the decided family itself stays quiet: a changed member does not list the other member
    _git(tmp_path, 'checkout', '-q', '--', 'src/repo/user.ts')
    (tmp_path / 'src/a.ts').write_text(body.format(limit=10).replace('* 100) / 100', '* 1000) / 1000'), encoding='utf-8')
    code, text = _check(tmp_path, '--static')
    assert code == 0 and not any(line.startswith('lead: save(') for line in _lines(text)), text


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
    assert code == 0 and not any(line.startswith('lead: save(') for line in _lines(text)), text
    # an exact copy of a member that the decided problem does not list (src/c.ts beside src/a.ts) keeps its lead
    exact = tmp_path / 'exact'
    _project(exact, {'src/a.ts': body.format(limit=10), 'src/b.ts': body.format(limit=20), 'src/c.ts': body.format(limit=10)})
    code, text = _check(exact, '--static', '--all')
    assert 'copy：Same-named functions have different bodies (structural similarity at least 0.8): save src/a.ts:1  src/b.ts:1' in text, text
    for name, content in decided.items():
        (exact / name).parent.mkdir(exist_ok=True)
        (exact / name).write_text(content, encoding='utf-8')
    _git(exact, 'add', '.')
    _git(exact, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'decided')
    (exact / 'src/a.ts').write_text(body.format(limit=10).replace('* 100) / 100', '* 1000) / 1000'), encoding='utf-8')
    code, text = _check(exact, '--static')
    assert code == 0, text
    assert [line for line in _lines(text) if line.startswith('lead: save(')] == [
        'lead: save(src/a.ts:1) changed; previously identical copies: 1 unchanged: src/c.ts:1(update them together when required; to lock them, write above the reference: // flowguard: same SAVE ref, above the copy: // flowguard: same SAVE)'], text


def test_a_copies_problem_lists_the_same_functions_after_a_file_is_mapped_again(tmp_path):
    # Round 25 check: the problem compared its members with whichever function the map returned first, so a comment
    # added to src/a.ts (mapped again, now last) made it list src/b.ts, src/c.ts and src/a.ts instead of a and b.
    body = ("export function save(items: number[], rate: number): number {{\n  let sum = 0;\n"
            "  for (const item of items) {{\n    if (item > {limit}) {{ sum += item * rate; }} else {{ sum += item; }}\n  }}\n"
            "  return Math.round(sum * 100) / 100;\n}}\n")
    _project(tmp_path, {'src/a.ts': body.format(limit=10), 'src/b.ts': body.format(limit=20), 'src/c.ts': body.format(limit=10)})
    listed = lambda text: [line for line in text.splitlines() if 'Same-named functions have different bodies' in line]
    code, text = _check(tmp_path, '--static', '--all')
    assert listed(text) == ['1. copy：Same-named functions have different bodies (structural similarity at least 0.8): save src/a.ts:1  src/b.ts:1'], text
    (tmp_path / 'src/a.ts').write_text('// rounded to cents\n' + body.format(limit=10), encoding='utf-8')
    code, text = _check(tmp_path, '--static', '--all')
    assert listed(text) == ['1. copy：Same-named functions have different bodies (structural similarity at least 0.8): save src/a.ts:2  src/b.ts:1'], text


def test_a_copies_decision_on_a_problem_this_task_made_quiets_its_changed_alone_lead(tmp_path):
    # Final check of r25-init: two identical save functions at the baseline are no copies problem; the task edits
    # one, the owner decides the copies problem that appears, and the changed-alone lead about the pair stayed.
    body = ("export function save(items: number[], rate: number): number {{\n  let sum = 0;\n"
            "  for (const item of items) {{\n    if (item > 10) {{ sum += item * rate; }} else {{ sum += item; }}\n  }}\n"
            "  return Math.round(sum * {scale}) / {scale};\n}}\n")
    _project(tmp_path, {'src/a.ts': body.format(scale=100), 'src/b.ts': body.format(scale=100), RULE_FILE[0]: RULE_FILE[1]})
    (tmp_path / 'src/a.ts').write_text(body.format(scale=1000), encoding='utf-8')
    code, text = _check(tmp_path, '--static')
    assert code == 0 and any(line.startswith('lead: save(src/a.ts:1) changed;') for line in _lines(text)), text
    (tmp_path / '.flowguard').mkdir(exist_ok=True)
    (tmp_path / '.flowguard/ledger.toml').write_text('[structure."copies:save"]\n' + DECIDED, encoding='utf-8')
    code, text = _check(tmp_path, '--static')
    assert code == 0 and not any(line.startswith('lead: save(') for line in _lines(text)), text


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
    assert 'declarations differ' not in text, text                      # old: only the old ledger lists it
    code, text = _check(tmp_path, '--all')
    assert ("lead: before: declarations differ: AvailabilityStatus a/contracts.py:4（'blocked' | 'ready'; missing 'available'）  b/contracts.py:4（'available' | 'blocked'; missing 'ready'）") in text, text
    (tmp_path / 'b/kinds.py').write_text('from typing import Literal\nKind = Literal["member", "guest", "staff"]\n', encoding='utf-8')
    code, text = _check(tmp_path)
    assert ("lead: declarations differ: Kind a/kinds.py:2（'guest' | 'member'; missing 'staff'）  b/kinds.py:2（'guest' | 'member' | 'staff'）"
            in text), text


def test_two_typescript_union_declarations_with_different_members_are_a_lead(tmp_path):
    _project(tmp_path, {'backend/src/lending.ts': "export type LendingStatus = 'DRAFT' | 'ACTIVE' | 'ENDED';\n"})
    (tmp_path / 'frontend/src').mkdir(parents=True)
    (tmp_path / 'frontend/src/lending.ts').write_text("export type LendingStatus = 'DRAFT' | 'ACTIVE';\n", encoding='utf-8')
    code, text = _check(tmp_path)
    assert ("lead: declarations differ: LendingStatus backend/src/lending.ts:1（'ACTIVE' | 'DRAFT' | 'ENDED'）  frontend/src/lending.ts:1（'ACTIVE' | 'DRAFT'; missing 'ENDED'）") in text, text
