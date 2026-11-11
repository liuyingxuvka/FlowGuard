"""Round 20, phase 4: rule fields read on each call (`fields`), fixed samples 13 and 14.

The project is `tests/fixtures/round20_fields` (see its README): a judgment whose rule fields come from
a sqlite3 connection and a record (`MAY_BORROW`, rule `BORROW` quoting the owner's words R1), a grace
constant whose rule repeats its value (`STANDING`, rule `GRACE`), and a scenario test with an event
anchor `calibrated_by` that keeps the third route (scenario test plus flow) for a writing function.
Each test applies one edit to the committed baseline and reads the FlowGuard block of the run.
"""
from pathlib import Path
import ast
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import textwrap

import pytest

from flowguard.intent import anchors
from flowguard.intent.runtime import Reading, Runtime
from tests.intent_engine._cli_fixture import display_text

SOURCE = str(Path(__file__).resolve().parents[2])
FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/round20_fields'


def _git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                           *arguments], check=True, capture_output=True, text=True, timeout=60).stdout


def _flowguard(root, *arguments, env=None):
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); from flowguard.__main__ import main; raise SystemExit(main(sys.argv[1:]))'
    return subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '--root', str(root), *arguments],
                          cwd=root, capture_output=True, text=True, timeout=120, env={**os.environ, **(env or {})})


def _pytest(root, *options):
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    result = subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '-q', '-p', 'no:cacheprovider', *options],
                            cwd=root, capture_output=True, text=True, timeout=180)
    text = display_text(result)
    assert 'INTERNALERROR' not in text, text
    return result, text


def _block(text):
    lines = text.splitlines()
    start = next((index for index, line in enumerate(lines) if line.startswith('FlowGuard（')), None)
    if start is None:
        return []
    block = []
    for line in lines[start + 1:]:
        if not line.strip() or line.startswith(('====', '____')) or re.match(r'\d+ (passed|failed)', line):
            break
        block.append(line)
    return block


def _results(root):
    with sqlite3.connect(root / '.flowguard/cache/map.sqlite') as connection:
        return {item: json.loads(payload) for item, payload in connection.execute('SELECT item, payload FROM result')}


def _edit(root, file, old, new):
    path = root / file
    text = path.read_text(encoding='utf-8')
    assert old in text, (file, old)
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


@pytest.fixture(scope='module')
def template(tmp_path_factory):
    root = tmp_path_factory.mktemp('round20_fields') / 'shop'
    for file in FIXTURE.rglob('*.txt'):
        relative = file.relative_to(FIXTURE).as_posix()
        if relative == 'R1_owner.txt':
            continue
        target = root / relative.removesuffix('.txt')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(file.read_bytes())
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'round-20 fields baseline')
    stored = _flowguard(root, 'req', 'add', str(FIXTURE / 'R1_owner.txt'), '--id', 'R1')
    assert stored.returncode == 0, stored.stdout + stored.stderr
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'owner words R1')
    brief = _flowguard(root)
    assert brief.returncode == 0, brief.stdout + brief.stderr
    return root


@pytest.fixture()
def shop(template, tmp_path):
    return Path(shutil.copytree(template, tmp_path / 'shop', symlinks=True))


BORROW_ITEMS = ('tests/intent/borrow.py::BORROW[shop.hires.may_borrow:cells]',
                'tests/intent/borrow.py::BORROW[shop.hires.may_borrow:rows]')


def test_sample_13_fields_read_from_a_connection_and_a_record_verify_the_rule_without_a_scenario(shop):
    result, text = _pytest(shop, '-rA')
    assert result.returncode == 0, text
    results = _results(shop)
    for item in BORROW_ITEMS:
        assert results[item]['verdict'] == 'ok', results[item]   # the guarded sqlite reads are not grey
        assert results[item]['tests'] == ['tests/test_hires.py::test_may_borrow'], results[item]
    assert int(results[BORROW_ITEMS[0]]['label'].split()[0]) >= 3, results[BORROW_ITEMS[0]]
    assert 'PASSED tests/intent/borrow.py::BORROW[shop.hires.may_borrow:cells]' in text, text
    # The project's own test asserts that its customers table still has its two rows.


def test_sample_13_a_broken_judgment_is_red_with_the_owner_sentence(shop):
    _edit(shop, 'shop/hires.py', '<= 10:', '<= 9:')
    result, text = _pytest(shop)
    assert result.returncode == 1, text
    block = _block(text)
    red = next(line for line in block if line.startswith('red: BORROW'))
    assert 'days=10 member=F -> rule T, code False' in red, red
    assert 'shop.hires.may_borrow:' in red and 'calls disagree' in red, red
    assert red.endswith('BORROW source: owner R1: 逾期超过 10 天就不能再借，会员除外。'), red
    assert 'FAILED tests/intent/borrow.py::BORROW[shop.hires.may_borrow:cells]' in text and '1 failed' in text, text
    assert not any(line.startswith('unverified: BORROW') for line in block), block


def test_sample_13_a_field_that_cannot_be_read_is_grey_and_names_the_field(shop):
    _edit(shop, 'shop/hires.py', 'member=is_member(db, hire.customer)', 'member=is_member(db, hire.customer_id)')
    result, text = _pytest(shop, '-vv')       # -q is already on: -vv is one -v
    assert result.returncode == 0, text
    assert all(f'{item} UNVERIFIED' in text for item in BORROW_ITEMS), text
    assert not any(line.startswith('red: BORROW') for line in _block(text)), text
    reason = "field member could not be evaluated: AttributeError: 'Hire' object has no attribute 'customer_id'"
    cells = _results(shop)[BORROW_ITEMS[0]]
    assert cells['verdict'] == 'grey' and not cells['red'], cells
    assert any(reason in grey for grey in cells['grey']), cells
    shown = display_text(_flowguard(shop, 'show', 'BORROW'))     # where the block's last line points
    assert 'shop.hires.may_borrow: ' + reason in shown, shown


def test_sample_13_a_partial_run_without_the_rule_items_still_checks_the_calls(shop):
    _edit(shop, 'shop/hires.py', '<= 10:', '<= 9:')
    result, text = _pytest(shop, 'tests/test_hires.py')
    assert result.returncode == 1, text
    red = next(line for line in _block(text) if line.startswith('red: BORROW'))
    assert 'days=10 member=F' in red and '-> rule T, code False' in red and 'source: owner R1' in red, red


def test_a_field_that_writes_the_database_is_refused_and_grey_with_its_field(shop):
    _edit(shop, 'shop/hires.py', 'member=is_member(db, hire.customer)', 'member=remember(db, hire.customer)')
    path = shop / 'shop/hires.py'
    path.write_text(path.read_text() + '\n\ndef remember(db, customer):\n'
                    '    db.execute("insert into customers values (99, 1)")\n    return True\n')
    result, text = _pytest(shop, '-rA')
    assert result.returncode == 0, text            # the project test's own row count is still 2
    cells = _results(shop)[BORROW_ITEMS[0]]
    assert cells['verdict'] == 'grey', cells
    assert any(reason.endswith('field member：replay refused: shop/hires.py:32 db.execute("insert into customers values (99, 1)")：write database INSERT customers') for reason in cells['grey']), cells


def test_sample_14_the_changed_grace_constant_leaves_both_rule_leads(shop):
    _edit(shop, 'shop/policy.py', 'GRACE_DAYS = 14', 'GRACE_DAYS = 21')
    result, text = _pytest(shop)
    leads = [line for line in _block(text) if line.startswith('lead: ')]
    assert 'lead: rule GRACE still uses old value 14（tests/intent/grace.py decision line 7、regression row line 12): if requirements changed, update the rule first' in leads, leads
    copy = next(line for line in leads if ' copies at ' in line)
    assert copy == ('lead: STANDING copies at shop/policy.py:standing changed; rule GRACE is unchanged -> if requirements changed, first use python -m flowguard req add to store the new owner words, then update rule tests/intent/grace.py:4; otherwise confirm that this code change is correct'), copy


def test_sample_14_a_change_that_also_edits_the_rule_has_no_copy_lead(shop):
    _edit(shop, 'shop/policy.py', 'GRACE_DAYS = 14', 'GRACE_DAYS = 21')
    _edit(shop, 'tests/intent/grace.py', 'return days <= 14', 'return days <= 21')
    result, text = _pytest(shop)
    assert not any(' copies at ' in line for line in _block(text)), text


def test_the_scenario_route_with_a_calibrated_event_anchor_still_checks_its_rule(shop):
    """The third route: a writing function's rule through a scenario test and a flow relation."""
    result, text = _pytest(shop, '-rA')
    results = _results(shop)
    assert results['tests/intent/notices.py::NOTICE[shop.notices.send_notice:rows]']['verdict'] == 'ok', results
    _edit(shop, 'shop/notices.py', 'if days <= 3:', 'if days <= 4:')
    result, text = _pytest(shop)
    assert result.returncode == 1, text
    assert 'FAILED tests/intent/notices.py::NOTICE[shop.notices.send_notice:rows]' in text, text
    red = next(line for line in _block(text) if line.startswith('red: NOTICE'))
    assert 'days=4 -> rule T, code False (row L10)' in red, red


# ---- the comment syntax ------------------------------------------------------------------------------

def _facts(text):
    source = textwrap.dedent(text).lstrip()
    return anchors.source_facts(ast.parse(source), source, 'policy', 'policy.py')


def test_fields_combine_with_the_context_separator_and_calibrated_by_in_either_order():
    facts = _facts('''
        # flowguard: sensor A(today: day; db, hire) fields days=(today - hire.due).days calibrated_by=tests/t.py::t
        def a(db, hire, today: date) -> bool:
            return True

        # flowguard: sensor B calibrated_by=tests/t.py::t[1] fields days=(today - hire.due).days member=db.execute("select m from c where id=?", (hire.c,)).fetchone()[0] == 1
        def b(db, hire, today: date) -> bool:
            return True

        # flowguard: sensor C -> fields: bool
        def c(days: int) -> bool:
            return True
    ''')
    found = {row['name']: row for row in facts['anchors']}
    assert not facts.get('anchor_issues') and not any(row['issues'] for row in found.values()), facts
    assert found['A']['fields'] == (('days', '(today - hire.due).days'),) and found['A']['calibrated_by'] == 'tests/t.py::t'
    assert [p['role'] for p in found['A']['parameters']] == ['context', 'context', 'input'], found['A']
    assert found['B']['calibrated_by'] == 'tests/t.py::t[1]'
    assert found['B']['fields'] == (('days', '(today - hire.due).days'),
                                    ('member', 'db.execute("select m from c where id=?", (hire.c,)).fetchone()[0] == 1'))
    assert found['C']['fields'] == () and found['C']['output'] == 'fields'


@pytest.mark.parametrize('comment,reason', [
    ('fields days=(today - ', 'invalid anchor: unmatched parentheses or quotes'),
    ('fields days', "invalid fields: fields must be followed by name=expression, 'days' is not"),
    ('fields days= member=x', 'invalid fields: field days has no expression'),
    ('fields days=today -', 'invalid fields: field days expression today - is not a Python expression'),
    ('fields days=1 days=2', 'invalid fields: duplicate field names: days'),
])
def test_a_wrong_fields_comment_is_red_and_says_how_to_write_it(comment, reason):
    facts = _facts(f'''
        # flowguard: sensor A {comment}
        def a(today: date) -> bool:
            return True
    ''')
    message, = [row['message'] for row in facts['anchor_issues']]
    assert message.startswith('policy.py:1 ' + reason), message
    if not reason.startswith('invalid anchor'):
        assert message.endswith(anchors.FIELDS_HELP), message


def test_fields_belong_to_a_judgment_and_never_repeat_a_parameter():
    facts = _facts('''
        # flowguard: event E fields days=1
        def e(today: date) -> None:
            pass

        # flowguard: sensor S fields today=today.day
        def s(today: date) -> bool:
            return True

        # flowguard: owner hires.reserved writers=shop:reserve fields days=1
    ''')
    problems = [row['message'] for row in facts['anchor_issues']]
    assert problems[0].startswith('policy.py:1 fields apply only to sensor and function owner anchors'), problems
    assert problems[1].startswith('policy.py:9 data owners cannot have fields'), problems
    issue, = facts['anchors'][0]['issues']
    assert issue['level'] == 'red' and issue['message'].startswith('policy.py:5 field today matches a parameter'), issue


def test_an_explicit_write_in_a_field_is_refused_statically_at_the_comment_line(tmp_path):
    import importlib.util, inspect
    (tmp_path / 'fieldwrite.py').write_text(textwrap.dedent('''
        SEEN = []

        def note(day):
            SEEN.append(day)
            return day

        def judge(today):
            return today > 3
    ''').lstrip())
    spec = importlib.util.spec_from_file_location('fieldwrite', tmp_path / 'fieldwrite.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    runtime = Runtime(tmp_path, previous={})
    bound = inspect.signature(module.judge).bind(5)
    reading = Reading('JUDGE', 'fieldwrite:judge')
    runtime.field_values(module.judge, bound, (('days', 'note(today)'),), 7, reading)
    assert reading.fields is None and module.SEEN == []
    assert reading.field_reasons == ['field days：explicit write: line 4 changes module state SEEN（SEEN.append）'], reading.field_reasons
    reading = Reading('JUDGE', 'fieldwrite:judge')
    runtime.field_values(module.judge, bound, (('days', '[today + n for n in range(2)][1]'),), 7, reading)
    assert reading.fields == {'days': 6} and not reading.field_reasons, reading


# ---- calibrated_by with fields, show, req add ----------------------------------------------------------

def test_calibrated_by_with_fields_keeps_only_the_named_tests_calls(shop):
    _edit(shop, 'shop/hires.py', '# flowguard: sensor MAY_BORROW fields',
          '# flowguard: sensor MAY_BORROW(today; db, hire) calibrated_by=tests/test_hires.py::test_member fields')
    test = shop / 'tests/test_hires.py'
    test.write_text(test.read_text() + textwrap.dedent('''

        def test_member(tmp_path):
            db = open_db(tmp_path / "member.db")
            db.execute("insert into customers values (2, 1)")
            assert may_borrow(db, Hire(2, 2, date(2026, 1, 1)), date(2026, 1, 20))
    '''))
    _git(shop, 'add', '.')
    _git(shop, 'commit', '-qm', 'calibrated fields')
    result, text = _pytest(shop, '-rA')
    assert result.returncode == 0, text
    cells = _results(shop)[BORROW_ITEMS[0]]
    assert cells['verdict'] == 'ok' and cells['tests'] == ['tests/test_hires.py::test_member'], cells
    assert 'calibrat' not in ' '.join(cells['grey'] + cells['red']), cells


def test_show_lists_the_classes_a_rule_gives_no_result_for_and_total_makes_them_red(shop):
    _edit(shop, 'tests/intent/borrow.py', '    return days <= 10 or member',
          '    if days < 0:\n        return None\n    return days <= 10 or member')
    shown = _flowguard(shop, 'show', 'BORROW', env={'PYTHONIOENCODING': 'cp1252'})
    text = display_text(shown)
    assert shown.returncode == 0, text
    line = next(line for line in text.splitlines() if line.startswith('undecided: '))
    assert line.startswith('undecided: rule BORROW has no result for 4 classes'), line
    assert 'days=-1 member=F' in line and 'days=-1 member=T' in line and 'days=0' not in line, line
    assert not any(line.startswith('red: ') for line in text.splitlines()), text
    _edit(shop, 'tests/intent/borrow.py', 'anchor="MAY_BORROW")', 'anchor="MAY_BORROW", total=True)')
    text = display_text(_flowguard(shop, 'show', 'BORROW'))
    red = next(line for line in text.splitlines() if line.startswith('red: '))
    assert red.startswith('red: BORROW declares total=True, but 4 classes have no rule result: ') and 'days=-1 member=T' in red, red
    assert red.endswith('-> give these cases a result in the rules, or remove total=True'), red


def test_show_prints_nothing_extra_for_a_rule_that_always_answers(shop):
    text = display_text(_flowguard(shop, 'show', 'BORROW'))
    assert 'undecided' not in text, text


def test_req_add_says_how_a_lasting_rule_cites_the_stored_words(shop, tmp_path):
    words = tmp_path / 'R2.txt'
    words.write_text('会员每次最多借五本。\n', encoding='utf-8')
    for env in (None, {'PYTHONIOENCODING': 'cp1252'}):
        identifier = 'R2' if env is None else 'R3'
        stored = _flowguard(shop, 'req', 'add', str(words), '--id', identifier, env=env)
        assert stored.returncode == 0, stored.stdout + stored.stderr
        lines = display_text(stored).splitlines()
        assert lines[0].startswith(f'stored {identifier} (request, sha ')
        assert lines[1] == (f'if these words set a continuing rule, write it in tests/intent/ and cite {identifier} as its source: '
                            f'source="owner {identifier}: <the exact sentence from the owner words>"'), lines


def test_check_reruns_the_tests_that_reached_a_fields_rule_when_only_the_rule_changed(tmp_path):
    root = tmp_path / 'late'
    (root / 'tests/intent').mkdir(parents=True)
    (root / 'shop.py').write_text('# flowguard: sensor LATE fields days=today - hire["due"]\n'
                                  'def is_late(hire: dict, today: int) -> bool:\n    return today - hire["due"] > 2\n')
    (root / 'tests/test_shop.py').write_text('from shop import is_late\n\n\ndef test_late():\n    assert is_late({"due": 1}, 5)\n')
    (root / 'tests/intent/late.py').write_text(textwrap.dedent('''
        from flowguard.intent import rule


        @rule("LATE_RULE", decides="late", fields={"days": int}, anchor="LATE", source="assumed: late after two days")
        def LATE_RULE(days):
            return days > 2
    ''').lstrip())
    (root / 'tests/test_flowguard_intent.py').write_text(
        'def test_flowguard_intent(request):\n    from flowguard.intent.plugin import sentinel\n    sentinel(request.config)\n')
    (root / '.gitignore').write_text('.flowguard/cache/\n__pycache__/\n')
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\ntestpaths=["tests"]\n'
                                         'addopts = "-p flowguard.intent.plugin"\n')
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'late baseline')
    for _ in range(2):              # the second check starts from saved, reusable test results
        checked = _flowguard(root, 'check')
        assert checked.returncode == 0, display_text(checked)
    rule = root / 'tests/intent/late.py'
    rule.write_text(rule.read_text() + '\n# the rule file changed, its test did not\n')
    checked = _flowguard(root, 'check')
    assert checked.returncode == 0, display_text(checked)
    cells = _results(root)['tests/intent/late.py::LATE_RULE[shop.is_late:cells]']
    assert cells['verdict'] == 'ok' and cells['tests'] == ['tests/test_shop.py::test_late'], cells
