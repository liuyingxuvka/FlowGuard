"""Round-20 fixed samples 1, 2, 3, 4, 5, 7, 9 and 19 in one project, each in a full ordinary pytest run.

The project is `tests/fixtures/round20_samples` (see its README): the round-19 acceptance project with
seven anchors, five grace copies and one rule quoting the owner's words. Every sample applies one edit to
the committed baseline and reads the FlowGuard block at the end of the complete run, where 4.0 crowded
the relevant lines out: in 4.3 the first line counts each kind, then red, changed and the one not compared line,
at most ten lines besides red, loosened and known fixed?.
"""
from pathlib import Path
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys

import pytest

from flowguard import __version__
from tests.intent_engine._cli_fixture import block, display_text, last, unchecked

SOURCE = str(Path(__file__).resolve().parents[2])
FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/round20_samples'
BROKEN = 'import sys\nsys.path.insert(0, ".")\ndef broken(:\n    pass\n'
BROKEN_LINE = 'not compared: _tmp_x.py (cannot be parsed: SyntaxError: invalid syntax line 3) -> not a failure'
VERSION = '.'.join(__version__.split('.')[:2])


def _git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                           *arguments], check=True, capture_output=True, text=True, timeout=60).stdout


def _flowguard(root, *arguments):
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); from flowguard.__main__ import main; raise SystemExit(main(sys.argv[1:]))'
    return subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '--root', str(root), *arguments],
                          cwd=root, capture_output=True, text=True, timeout=120)


@pytest.fixture(scope='module')
def template(tmp_path_factory):
    root = tmp_path_factory.mktemp('round20') / 'shop'
    for file in FIXTURE.rglob('*.txt'):
        relative = file.relative_to(FIXTURE).as_posix()
        if relative == 'R1_owner.txt':
            continue
        target = root / relative.removesuffix('.txt')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(file.read_bytes())
    (root / '_tmp_x.py').write_text(BROKEN)              # sample 19: a broken file stays grey by itself
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'round-20 samples baseline')
    stored = _flowguard(root, 'req', 'add', str(FIXTURE / 'R1_owner.txt'), '--id', 'R1')
    assert stored.returncode == 0, stored.stdout + stored.stderr
    assert (root / '.flowguard/requests/R1.md').read_bytes() == (FIXTURE / 'R1_owner.txt').read_bytes()
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'owner words R1')
    brief = _flowguard(root)                             # the session start records the task baseline
    assert brief.returncode == 0, brief.stdout + brief.stderr
    return root


@pytest.fixture()
def shop(template, tmp_path):
    return Path(shutil.copytree(template, tmp_path / 'shop', symlinks=True))


def _edit(root, file, old, new):
    path = root / file
    text = path.read_text()
    assert old in text, (file, old)
    path.write_text(text.replace(old, new, 1))


def _pytest(root, *options, env=None):
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    result = subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '-q', '-p', 'no:cacheprovider', *options],
                            cwd=root, capture_output=True, text=True, timeout=180, env={**os.environ, **(env or {})})
    text = display_text(result)
    assert 'INTERNALERROR' not in text, text             # sample 19 in every run
    return result, text


def _block(result):
    """The FlowGuard block, last on stdout: its first line, then lines of the kinds in their order, at most ten
    besides red, loosened and known fixed?, nothing cut to `…`."""
    title, *lines = block(result)
    assert not any('…' in line for line in lines), lines
    return title, lines


def _observations(root):
    with sqlite3.connect(root / '.flowguard/cache/map.sqlite') as connection:
        return json.loads(connection.execute("SELECT v FROM meta WHERE k='runtime_observations'").fetchone()[0])['items']


def test_without_a_change_the_run_is_quiet(shop):
    result, text = _pytest(shop)
    assert result.returncode == 0 and '12 passed' in result.stdout, text
    # Only the first line with FlowGuard's own time (4.10) and the broken file of sample 19, which is never
    # compared: no red, change or before line.
    title, block = _block(result)
    assert re.fullmatch(r'FlowGuard \d+\.\d+ \(since [0-9a-f]{7}\): 0 red, 1 not compared; \d+\.\d s', title), title
    assert block == [BROKEN_LINE], block


def test_sample_1_a_database_decision_is_not_compared_and_names_itself(shop):
    _edit(shop, 'shop/store.py', 'return stock > reserved', 'return stock >= reserved')
    result, text = _pytest(shop)
    assert result.returncode == 0 and '12 passed' in result.stdout, text
    title, block = _block(result)
    head = _git(shop, 'rev-parse', 'HEAD').strip()
    assert title.startswith(f'FlowGuard {VERSION} (since {head[:7]}): 0 red, 2 not compared; '), title
    # The connection argument is not JSON: no change is claimed for it either way (4.5, 6.4).
    assert block == ['not compared: 2 items: _tmp_x.py and AVAILABLE (cannot be parsed: SyntaxError: invalid syntax line 3, '
                     'or no comparable JSON result) -> not a failure'], block
    assert '    no comparable JSON result' in last(shop).splitlines()
    assert not any(line.startswith('changed: can_hire') for line in block), block


def test_sample_2_a_database_write_is_not_compared_and_the_table_has_one_row(shop, tmp_path):
    _edit(shop, 'shop/store.py', 'return count + stock - reserved', 'return max(0, count + stock - reserved)')
    rows = {}
    for label, options in (('plugin', ()), ('without', ('-p', 'no:flowguard.intent.plugin'))):
        target = tmp_path / (label + '.json')
        result, text = _pytest(shop, *options, 'tests/test_store.py', env={'HIRES_ROWS': str(target)})
        assert result.returncode == 0, text
        rows[label] = json.loads(target.read_text())
        if label == 'plugin':
            assert _block(result)[1] == ['not compared: 3 items: _tmp_x.py, STANDING and HIRES (cannot be parsed: SyntaxError: '
                                         'invalid syntax line 3, no recorded JSON inputs, or 1 other reason) -> not a failure'], text
            assert any('HIRES: no comparable JSON result' in reason for item in _observations(shop)['items']
                       for reason in item.get('reasons', ())), text
    assert rows == {'plugin': 1, 'without': 1}
    result, text = _pytest(shop)                         # the full suite shows the same line, with HIRES's reason
    assert result.returncode == 0 and 'HIRES' in _block(result)[1][-1], text
    assert 'no comparable JSON result' in unchecked(shop)['HIRES'], last(shop)


def test_sample_3_a_helper_constant_makes_the_copies_disagree_at_its_own_value(shop):
    _edit(shop, 'shop/policy.py', 'GRACE_DAYS = 3', 'GRACE_DAYS = 7')
    result, text = _pytest(shop)
    title, block = _block(result)
    # standing_allows reaches the changed constant through its same-file helper, which its sealed run executes
    # (design 4.5): both are compared before and after. Their recorded calls (0 and 9) answer the same: no
    # change is claimed for either.
    items = {item.get('name'): item for item in _observations(shop)['items']}
    assert items['STANDING']['total'] == 2 and items['STANDING']['changed'] == [], items
    assert items['within_grace']['total'] == 2 and items['within_grace']['changed'] == [], items
    assert not any(line.startswith('changed: standing_allows') for line in block), block
    # The copy in preview.py still says 3: the helper's constant 7 is in the compared union, where the
    # same-name anchors now disagree: red with its next step.
    assert result.returncode == 1, text
    # Its next step chooses neither copy (the changed one may be the right one) and offers no way to silence it.
    assert block == ['red: same STANDING: on days_after_expiry=7, suspended=False, owed=0: policy.py:standing_allows returns True, '
                     'preview.py:preview_allows returns False -> decide which copy is right, then make the other agree', BROKEN_LINE], block


def test_sample_4_unanchored_late_fee_claims_no_change_for_the_member_branch_no_test_calls(shop):
    _edit(shop, 'shop/fees.py', 'return fee // 2 if member else fee', 'return fee * 2 // 3 if member else fee')
    result, text = _pytest(shop)
    assert result.returncode == 0, text
    # Inputs come only from the tests' calls (4.5): late_fee(5, False) gives 9 before and after.
    item = next(item for item in _observations(shop)['items'] if item.get('name') == 'late_fee')
    assert item['unanchored'] and item['rows'] == [[{'days': 5, 'member': False}, 9]] and item['changed'] == [], item
    assert not any(line.startswith('changed: late_fee') for line in _block(result)[1]), text


def test_sample_5_the_skipped_save_step_is_a_changed_decision_on_the_real_path(shop):
    _edit(shop, 'shop/publish.py', 'return not artifact_id.startswith("tmp")', 'return not artifact_id.startswith(("tmp", "a"))')
    result, text = _pytest(shop)
    assert result.returncode == 0, text
    block = _block(result)[1]
    assert block == ["changed: needs_save (publish.py:17): (artifact_id='a1') was True, now False; 1/1 inputs differ "
                     '-> if you meant it, say so', BROKEN_LINE], block
    assert '    no flowguard comment: compared because its code changed' in last(shop).splitlines()
    # The test is not run again with the old code (6.5); the real current path is recorded without SAVED.
    assert not any('became' in line for line in block), block
    with sqlite3.connect(shop / '.flowguard/cache/map.sqlite') as connection:
        events = json.loads(connection.execute("SELECT v FROM meta WHERE k='runtime_observations'").fetchone()[0])['events']
    calls = [event['anchor'] for event in events if event['case'] == 'tests/test_publish.py::test_release' and event['phase'] == 'call']
    assert calls == ['ENTRY', 'PUBLISHED'], events


def test_sample_7_rule_violation_is_one_red_line_with_the_owner_sentence(shop):
    _edit(shop, 'shop/deposit.py', 'return deposit > 100', 'return deposit > 100 and not member')
    result, text = _pytest(shop)
    assert result.returncode == 1 and '2 failed, 10 passed' in result.stdout, text
    block = _block(result)[1]
    # One red line for the rule's home; the owner sentence and every step are its detail (show --last).
    assert block == ['red: rule DEPOSIT_REVIEW: deposit=101 member=T -> rule True, code False at shop/deposit.py:needs_approval '
                     '(2 of 10 cells disagree) (+1 more) -> change the code so shop/deposit.py:needs_approval follows rule DEPOSIT_REVIEW',
                     BROKEN_LINE], block
    shown = last(shop).splitlines()
    detail = shown[shown.index(next(line for line in shown if line.startswith('red: rule DEPOSIT_REVIEW: '))) + 1:]
    assert '    change the code so shop/deposit.py:needs_approval follows rule DEPOSIT_REVIEW' in detail, shown
    assert any(line.startswith('    if requirements changed, ') and 'tests/intent/deposit.py:4' in line for line in detail), shown
    assert '    DEPOSIT_REVIEW source: owner R1: 会员也一样，不能例外。' in detail, shown


def test_sample_7_the_phase_0_config_fee_rule_is_unverified_in_the_new_block(tmp_path):
    from tests.intent_engine.test_calibrated_config_rule import _demo, _sealed_grey
    root = _demo(tmp_path / 'demo')
    _edit(root, 'shop/fees.json', '"per_day": 3', '"per_day": 4')
    _edit(root, 'tests/test_fees.py', '== 9', '== 12')
    result, text = _pytest(root, '-rf')
    # The calibrated reader of fees.json cannot run sealed: its rule items are unverified, never passed or red.
    assert result.returncode == 0 and '2 passed, 3 unverified' in result.stdout, text
    assert not any(line.startswith('red: FEE') for line in _block(result)[1]), text
    _sealed_grey(root)


def test_sample_9_both_database_calls_run_once_and_are_not_compared(shop):
    _edit(shop, 'shop/members.py', '    return days_after_expiry <= 3\n', '    return days_after_expiry <= 7\n')
    result, text = _pytest(shop)
    assert result.returncode == 0 and '12 passed' in result.stdout, text       # one debt row, as the test asserts
    assert _block(result)[1] == ['not compared: 2 items: _tmp_x.py and BORROW (cannot be parsed: SyntaxError: invalid syntax '
                                 'line 3, or no comparable JSON result) -> not a failure'], text
    assert not [item for item in _observations(shop)['items'] if item.get('name') == 'BORROW'], _observations(shop)


def test_sample_19_the_broken_file_is_only_unverified(shop):
    _edit(shop, 'shop/store.py', 'return stock > reserved', 'return stock >= reserved')
    result, text = _pytest(shop)
    assert result.returncode == 0, text
    grey = [item for item in _observations(shop)['items'] if item.get('name') == 'uncovered']
    assert any('_tmp_x.py' in reason and 'cannot be parsed' in reason for item in grey for reason in item['reasons']), grey
