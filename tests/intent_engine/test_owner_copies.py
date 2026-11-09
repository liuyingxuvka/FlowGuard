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


def _lines(text, prefix='线索：'):
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
    assert 'keep one owner' in index.issues[0].message and 'policy.py:1' in index.issues[0].message


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
    assert 'parameters correspond only by name: write # flowguard: sensor ELIGIBLE(days=<its parameter>)' in hint
    mapped = source.replace('# flowguard: sensor ELIGIBLE\n', '# flowguard: sensor ELIGIBLE(days=overdue_days)\n')
    facts = _facts(mapped)
    copy = anchors._anchor(facts['anchors'][1])
    assert [(p.name, p.alias, p.source) for p in copy.parameters] == [('days', 'overdue_days', 'overdue_days')]
    assert not anchors._index([anchors._anchor(row) for row in facts['anchors']], []).issues
    _project(tmp_path, {'policy.py': mapped})
    code, text = _check(tmp_path)
    assert code == 1, text
    assert re.search(r'红 同名锚点 ELIGIBLE（policy:owner ↔ policy:copy）', text) and 'days=4' in text, text


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
    assert '红 同名锚点 ROUND（rounding:away ↔ rounding:up）' in text, text
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
    assert agreed.returncode == 0 and '同名锚点' not in _text(agreed), _text(agreed)
    policy.write_text(policy.read_text().replace('overdue_days <= 3', 'overdue_days <= 5'))
    result = _pytest(tmp_path)
    text = _text(result)
    assert result.returncode == 1 and '1 passed' in result.stdout, text
    assert re.search(r'红：同名锚点 ELIGIBLE：days=4，F ≠ T', text), text


# ---- fixed examples 10 and 11: the KWP rounding copies ---------------------------------------------------

def test_fixed_10_a_registered_owner_lists_the_other_six_kwp_copies_by_behavior(tmp_path):
    _commit(_kwp(tmp_path))
    owner = tmp_path / 'Step1/src/kwp_step1/matlab_fallbacks.py'
    lines = owner.read_text().splitlines(True)
    assert lines[13] == '\n' and lines[14].startswith('def matlab_round(')
    lines[13] = '# flowguard: owner MATLAB_ROUND\n'
    owner.write_text(''.join(lines))
    code, text = _check(tmp_path)
    assert code == 0, text
    leads = _lines(text)
    header = next(line for line in leads if line.startswith('线索：负责人 MATLAB_ROUND'))
    assert 'Step1/src/kwp_step1/matlab_fallbacks.py:15' in header and '疑似副本 6 份' in header, text
    assert re.search(r'候选 6 个，用时 \d+\.\d\d 秒', header) and '# flowguard: sensor MATLAB_ROUND' in header, text
    same = next(line for line in leads if line.startswith('线索：副本 3 份'))
    assert '不是证明' in same and all(place in same for place in (
        'Step3/src/kwp_step3/technology.py:53', 'Step2/src/kwp_step2/try_data.py:15',
        'Step10/step10_baublock_progress_maps.py:'))
    assert '这是在负责人的全部代表值上比较的结果，调用点是否走到负数、非有限值等没有核对' in header, header
    half = [line for line in leads if 'value=-2.5 → -2（负责人给 -3）' in line]
    assert len(half) == 1 and half[0].startswith('线索：相似 2 份：') and 'simulation_preparation.py:25' in half[0] \
        and 'Step6a/kwp_step6a/config.py:' in half[0], text
    # Grouped by the first difference; int(x + 0.5) and floor(x + 0.5) still differ on negative whole numbers.
    assert '这几份在别的代表值上也互不相同' in half[0], half[0]
    legacy = next(line for line in leads if 'step2_demand_library.py' in line)
    assert legacy.startswith('线索：相似 1 份：') and 'value=nan → 0（负责人给 raised ValueError）' in legacy, text
    assert len([line for line in leads if re.match(r'线索：(副本|分叉的副本|相似) ', line)]) == 3, text


def test_fixed_11_three_changed_copies_name_the_four_left_behind(tmp_path):
    _kwp(tmp_path)
    fixed = {}
    for relative, floor in (('Step1/src/kwp_step1/matlab_fallbacks.py', 'floor'), ('Step3/src/kwp_step3/technology.py', 'math.floor'),
                            ('Step10/step10_baublock_progress_maps.py', 'math.floor')):
        path = tmp_path / relative
        fixed[relative] = path.read_text()
        # The pre-1da8721 bodies are reconstructed (README): the unchanged copies' floor(x + 0.5).
        before, count = re.subn(r'(    """.*?"""\n)    number = float\(value\)\n.*?\n(?=\n|\Z)',
                                lambda match: match.group(1) + f'    return int({floor}(float(value) + 0.5))\n', fixed[relative], count=1, flags=re.S)
        assert count == 1
        path.write_text(before)
    _commit(tmp_path, 'before 1da8721')
    for relative, text in fixed.items():
        (tmp_path / relative).write_text(text)
    code, text = _check(tmp_path)
    assert code == 0, text
    lead = next(line for line in _lines(text) if '改了行为' in line)
    assert '这 3 处改了行为' in lead and all(place in lead for place in (
        'Step1/src/kwp_step1/matlab_fallbacks.py:15', 'Step3/src/kwp_step3/technology.py:53',
        'Step10/step10_baublock_progress_maps.py:'))
    twins, similar = lead.split('相似', 1)
    assert '原来和它们行为相同的 1 份没改：Step6a/kwp_step6a/config.py:' in twins, lead
    assert all(place in similar for place in ('Step2/src/kwp_step2/simulation_preparation.py:25',
                                              'Step2/src/kwp_step2/try_data.py:15', 'Step2/step2_demand_library.py:')), lead
    assert '# flowguard: owner MATLAB_ROUND' in lead


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
    (tmp_path / 'policy.py').write_text(source)
    _project(tmp_path, {'tests/test_case.py': 'from policy import renewal\ndef test_native():\n    assert renewal(0)\n'})
    changed = source.replace('return overdue_days <= 14', 'return overdue_days <= 21')
    (tmp_path / 'policy.py').write_text(changed)
    result = _pytest(tmp_path)
    text = _text(result)
    assert result.returncode == 0, text
    lead = next(line for line in _lines(text) if '旧值 14' in line)
    expected = [f'policy.py:{number}' for number, line in enumerate(changed.splitlines(), 1)
                if re.search(r'(<=|>) 14:?$|LIMITS\[0\]', line)]
    assert len(expected) == 4 and '还出现在 4 个判断里' in lead, (expected, text)
    assert all(place in lead for place in expected) and lead.count('（大函数中）') == 2, text
    assert '…' not in lead and '# flowguard: owner' in lead


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
    policy.write_text(policy.read_text().replace('GRACE_DAYS = 14', 'GRACE_DAYS = 21'))
    text = _text(_pytest(tmp_path))
    assert '线索：规则 GRACE 里还写着旧值 14（tests/intent/grace.py 判断第 7 行、回归行第 12 行）：需求变了就先改规则' in text, text


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
    money.write_text(money.read_text().replace('def margin', '# flowguard: owner MARGIN\ndef margin')
                     + "\n\ndef upper(row):\n    return {'ID': row}\n")
    code, text = _check(tmp_path, '--all')
    assert code == 0, text
    assert 'money.py:6' not in text and '疑似副本' not in text and '写法不一致' not in text, text


def test_a_new_spelling_of_a_label_is_a_lead_and_an_old_one_is_not(tmp_path):
    _project(tmp_path, {'labels.py': '''
        def home(kind):
            if kind == 'My Organization':
                return 'home'
            return 'other'
    '''})
    code, text = _check(tmp_path)
    assert '写法不一致' not in text, text
    (tmp_path / 'view.py').write_text("def title(kind):\n    return 'My organization' if kind else ''\n")
    code, text = _check(tmp_path)
    lead = next(line for line in _lines(text) if '写法不一致' in line)
    assert "'My Organization'（labels.py:2）" in lead and "'My organization'（view.py:2，这次新增的写法）" in lead, text


# ---- data owners ---------------------------------------------------------------------------------------

def test_a_new_write_outside_a_data_owner_is_red_and_older_ones_are_the_old_ledger(tmp_path):
    _project(tmp_path, {'shop/__init__.py': '', 'shop/store.py': '''
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
    assert code == 0 and '负责人以外' not in text, text
    code, text = _check(tmp_path, '--all')
    assert code == 0 and '线索：旧账 hires.reserved 负责人以外的写入：shop/store.py:7 legacy（sql:update，值 0）' in text, text
    (tmp_path / 'shop/api.py').write_text('def cancel(db, hire_id):\n    db.execute("UPDATE hires SET reserved = 0 WHERE id = ?", (hire_id,))\n')
    code, text = _check(tmp_path)
    assert code == 1, text
    red = next(line for line in text.splitlines() if line.startswith('红：负责人以外新增写入'))
    assert 'hires.reserved：shop/api.py:2 cancel（sql:update，值 0）' in red and '只允许 shop.store:reserve' in red, red
    assert '把 shop.api:cancel 加进 writers=（owner 注释在 shop/store.py:1）' in red and 'legacy' not in red, red
    result = _pytest(tmp_path)
    assert result.returncode == 1 and '红：负责人以外新增写入 hires.reserved' in _text(result), _text(result)


# ---- copy discovery: replay route, timeout, import errors, a new copy of an owner ---------------------------

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
    assert re.search(r'副本 1 份（在 \d+ 个代表值上与负责人相同，不是证明）：rules.py:6', text), text
    unclear = next(line for line in _lines(text) if line.startswith('线索：看不清'))
    assert 'rules.py:10（超过 0.5 秒没有结束）' in unclear, unclear
    assert "vendor_copy.py:4（导入出错：ModuleNotFoundError: No module named 'not_installed_anywhere'）" in unclear, unclear
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
    rules.write_text(rules.read_text() + '\n\ndef again(amount: float) -> float:\n    return 0.5 * amount\n')
    code, text = _check(tmp_path)
    assert code == 1, text
    assert '红：负责人 HALF（rules.py:2） 之外新起了一份：rules.py:6（副本）→ 改成调用 half，或在它上方写 # flowguard: sensor HALF' in text, text


def test_a_typescript_data_owner_turns_a_new_prisma_write_outside_its_writers_red(tmp_path):
    fixtures = Path(__file__).resolve().parents[1] / 'fixtures/planning_tool'
    for path in fixtures.rglob('*.txt'):
        target = tmp_path / path.relative_to(fixtures).with_suffix('')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    (tmp_path / 'backend/src/owners.ts').write_text(
        '// flowguard: owner Employee.organizationalUnitId writers=transferEmployee\nexport {};\n')
    (tmp_path / '.gitignore').write_text('.flowguard/cache/\n')
    _commit(tmp_path)
    code, text = _check(tmp_path)
    assert code == 0 and '负责人以外新增写入' not in text, text
    (tmp_path / 'backend/src/services/rogue.ts').write_text(
        'export async function moveEmployee(prisma: any, id: string, unit: string) {\n'
        '  await prisma.employee.update({ where: { id }, data: { organizationalUnitId: unit } });\n}\n')
    code, text = _check(tmp_path)
    assert code == 1, text
    red = next(line for line in text.splitlines() if line.startswith('红：负责人以外新增写入'))
    assert red.startswith('红：负责人以外新增写入 Employee.organizationalUnitId：backend/src/services/rogue.ts:2 moveEmployee（update）'), red
    assert '只允许 transferEmployee' in red and 'owner 注释在 backend/src/owners.ts:1' in red and red.count('.ts:') == 2, red


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
    ''').lstrip())
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
    ''').lstrip())
    (tmp_path / 'writers.py').write_text(textwrap.dedent('''
        from models import Job, Step, Phase


        def close(job: Job):
            job.status = 'closed'


        def jump(step: Step):
            step.phase = 'published'
            step.phase = Phase.SAVED
    ''').lstrip())
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
    assert code == 0 and '配对没写' not in text, text
    store = tmp_path / 'shop/store.py'
    store.write_text("# flowguard: owner hires.reserved with=hires.state=held alone=shop.store:import_rows(bulk import marks rows later)\n"
                     + store.read_text())
    code, text = _check(tmp_path)
    assert code == 1, text
    red = next(line for line in text.splitlines() if line.startswith('红：配对没写'))
    assert red.startswith('红：配对没写：shop/store.py:16 release 写了 hires.reserved，调用树（向下 3 层）里没写 hires.state=held'), red
    assert 'reserve' not in red.split('写了')[0] and 'import_rows' not in red and 'alone=函数名(理由)' in red, red


def test_copy_discovery_compares_on_the_codes_own_literals(tmp_path):
    _copy_fixture(tmp_path, 'kwp_normalize')
    _project(tmp_path, {}, pyproject='[tool.pytest.ini_options]\npythonpath = ["Step1/src", "Step3/src"]\n')
    technology = tmp_path / 'Step3/src/kwp_step3/technology.py'
    technology.write_text(technology.read_text().replace('def normalize_technology_name(value: object)',
                                                          '# flowguard: owner TECHNOLOGY\ndef normalize_technology_name(value: object)'))
    code, text = _check(tmp_path)
    assert code == 0, text
    forked = next(line for line in _lines(text) if line.startswith('线索：分叉的副本 1 份'))
    assert 'Step1/src/kwp_step1/utils.py:' in forked and "→ 'district_heat'（负责人给 'waermenetze'）" in forked, forked


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
    assert '两份声明不同' not in text, text                      # old: only the old ledger lists it
    code, text = _check(tmp_path, '--all')
    assert ("线索：旧账 两份声明不同：AvailabilityStatus a/contracts.py:4（'blocked' | 'ready'；少 'available'）  "
            "b/contracts.py:4（'available' | 'blocked'；少 'ready'）") in text, text
    (tmp_path / 'b/kinds.py').write_text('from typing import Literal\nKind = Literal["member", "guest", "staff"]\n')
    code, text = _check(tmp_path)
    assert ("线索：两份声明不同：Kind a/kinds.py:2（'guest' | 'member'；少 'staff'）  b/kinds.py:2（'guest' | 'member' | 'staff'）"
            in text), text


def test_two_typescript_union_declarations_with_different_members_are_a_lead(tmp_path):
    _project(tmp_path, {'backend/src/lending.ts': "export type LendingStatus = 'DRAFT' | 'ACTIVE' | 'ENDED';\n"})
    (tmp_path / 'frontend/src').mkdir(parents=True)
    (tmp_path / 'frontend/src/lending.ts').write_text("export type LendingStatus = 'DRAFT' | 'ACTIVE';\n")
    code, text = _check(tmp_path)
    assert ("线索：两份声明不同：LendingStatus backend/src/lending.ts:1（'ACTIVE' | 'DRAFT' | 'ENDED'）  "
            "frontend/src/lending.ts:1（'ACTIVE' | 'DRAFT'；少 'ENDED'）") in text, text
