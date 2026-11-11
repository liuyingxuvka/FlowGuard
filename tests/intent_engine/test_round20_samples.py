"""Round-20 fixed samples 1, 2, 3, 4, 5, 7, 9 and 19 in one project, each in a full ordinary pytest run.

The project is `tests/fixtures/round20_samples` (see its README): the round-19 acceptance project with
seven anchors, five grace copies and one rule quoting the owner's words. Every sample applies one edit to
the committed baseline and reads the FlowGuard block at the end of the complete run, where 4.0 crowded
the relevant lines out: red first, then changes, leads and the unverified summary, at most ten lines
after the reds, names and places never shortened.
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

from tests.intent_engine._cli_fixture import display_text

SOURCE = str(Path(__file__).resolve().parents[2])
FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/round20_samples'
BROKEN = 'import sys\nsys.path.insert(0, ".")\ndef broken(:\n    pass\n'


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


def _block(text):
    """The FlowGuard block: its title, the red lines with their next steps, and the bounded rest."""
    lines = text.splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith('FlowGuard（'))
    block = []
    for line in lines[start + 1:]:
        if not line.strip() or line.startswith(('====', '____')) or re.match(r'\d+ (passed|failed)', line):
            break
        block.append(line)
    red = [line for line in block if line.startswith('red: ') or line.startswith('    ')]
    rest = [line for line in block if line not in red]
    assert len(rest) <= 10, block
    assert not any('…' in line for line in block), block
    kinds = ('red', 'changed', 'compared', 'lead', 'unverified')
    order = [kinds.index(re.match('|'.join(kinds), line)[0]) for line in block if not line.startswith('    ')]
    assert order == sorted(order), block
    return lines[start], block


def _observations(root):
    with sqlite3.connect(root / '.flowguard/cache/map.sqlite') as connection:
        return json.loads(connection.execute("SELECT v FROM meta WHERE k='runtime_observations'").fetchone()[0])['items']


def test_without_a_change_the_run_is_quiet(shop):
    result, text = _pytest(shop)
    assert result.returncode == 0 and '12 passed' in result.stdout, text
    # Only the title with FlowGuard's own time (4.10): no red, change, lead or unverified line.
    title, block = _block(text)
    assert re.fullmatch(r'FlowGuard（since task start [0-9a-f]{7}）; \d+\.\d{3} s', title) and block == [], (title, block)


def test_sample_1_a_database_decision_is_not_compared_and_names_itself(shop):
    _edit(shop, 'shop/store.py', 'return stock > reserved', 'return stock >= reserved')
    result, text = _pytest(shop)
    assert result.returncode == 0 and '12 passed' in result.stdout, text
    title, block = _block(text)
    head = _git(shop, 'rev-parse', 'HEAD').strip()
    assert title.startswith(f'FlowGuard（since task start {head[:7]}）; '), title
    # The connection argument is not JSON: no change is claimed for it either way (4.5, 6.4).
    assert 'unverified: AVAILABLE：no comparable JSON result' in block, block
    assert not any(line.startswith('changed: AVAILABLE') for line in block), block


def test_sample_2_a_database_write_is_not_compared_and_the_table_has_one_row(shop, tmp_path):
    _edit(shop, 'shop/store.py', 'return count + stock - reserved', 'return max(0, count + stock - reserved)')
    rows = {}
    for label, options in (('plugin', ()), ('without', ('-p', 'no:flowguard.intent.plugin'))):
        target = tmp_path / (label + '.json')
        result, text = _pytest(shop, *options, 'tests/test_store.py', env={'HIRES_ROWS': str(target)})
        assert result.returncode == 0, text
        rows[label] = json.loads(target.read_text())
        if label == 'plugin':
            assert any('HIRES' in line for line in _block(text)[1] if line.startswith('unverified')), text
            assert any('HIRES: no comparable JSON result' in reason for item in _observations(shop)['items']
                       for reason in item.get('reasons', ())), text
    assert rows == {'plugin': 1, 'without': 1}
    result, text = _pytest(shop)                         # the full suite shows the same line
    assert result.returncode == 0 and 'unverified: HIRES：no comparable JSON result' in _block(text)[1], text


def test_sample_3_a_helper_constant_makes_the_copies_disagree_at_its_own_value(shop):
    _edit(shop, 'shop/policy.py', 'GRACE_DAYS = 3', 'GRACE_DAYS = 7')
    result, text = _pytest(shop)
    title, block = _block(text)
    # standing_allows reaches the changed constant through its same-file helper, which its sealed run executes
    # (design 4.5): both are compared before and after. Their recorded calls (0 and 9) answer the same: no
    # change is claimed for either.
    items = {item.get('name'): item for item in _observations(shop)['items']}
    assert items['STANDING']['total'] == 2 and items['STANDING']['changed'] == [], items
    assert items['within_grace']['total'] == 2 and items['within_grace']['changed'] == [], items
    assert not any(line.startswith('changed: STANDING') for line in block), block
    # The copy in preview.py still says 3: the helper's constant 7 is in the compared union, where the
    # same-name anchors now disagree: red with its next step.
    assert result.returncode == 1, text
    red = next(index for index, line in enumerate(block) if line.startswith('red: same-name anchor STANDING：'))
    assert 'days_after_expiry=7' in block[red], block
    assert '2 copies: 1 copies return T (shop/policy.py:10 standing_allows), 1 copies return F (shop/preview.py:2 preview_allows)' in block[red], block
    # its next step chooses neither copy: the changed one may be the right one
    assert block[red].endswith(' -> first decide which copy is correct, then make the other copy agree with it; if intentionally different, use different anchor names and declare distinct'), block


def test_sample_4_unanchored_late_fee_claims_no_change_for_the_member_branch_no_test_calls(shop):
    _edit(shop, 'shop/fees.py', 'return fee // 2 if member else fee', 'return fee * 2 // 3 if member else fee')
    result, text = _pytest(shop)
    assert result.returncode == 0, text
    # Inputs come only from the tests' calls (4.5): late_fee(5, False) gives 9 before and after.
    item = next(item for item in _observations(shop)['items'] if item.get('name') == 'late_fee')
    assert item['unanchored'] and item['rows'] == [[{'days': 5, 'member': False}, 9]] and item['changed'] == [], item
    assert not any(line.startswith('changed: late_fee') for line in _block(text)[1]), text


def test_sample_5_the_skipped_save_step_is_a_changed_decision_on_the_real_path(shop):
    _edit(shop, 'shop/publish.py', 'return not artifact_id.startswith("tmp")', 'return not artifact_id.startswith(("tmp", "a"))')
    result, text = _pytest(shop)
    assert result.returncode == 0, text
    block = _block(text)[1]
    line = next(line for line in block if line.startswith('changed: needs_save(unanchored, automatic)（shop/publish.py:17）'))
    assert "artifact_id='a1'" in line and 'function result True → False' in line, line
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
    block = _block(text)[1]
    reds = [index for index, line in enumerate(block) if line.startswith('red: DEPOSIT_REVIEW')]
    assert len(reds) == 1, block
    line = block[reds[0]]
    assert 'deposit=101 member=T' in line and line.endswith('source: owner R1: 会员也一样，不能例外。'), line
    assert block[reds[0] + 1] == '    change the code so shop/deposit.py:2 follows rule DEPOSIT_REVIEW; ', block
    assert 'tests/intent/deposit.py:4' in block[reds[0] + 2], block


def test_sample_7_the_phase_0_config_fee_rule_is_unverified_in_the_new_block(tmp_path):
    from tests.intent_engine.test_calibrated_config_rule import _demo, _sealed_grey
    root = _demo(tmp_path / 'demo')
    _edit(root, 'shop/fees.json', '"per_day": 3', '"per_day": 4')
    _edit(root, 'tests/test_fees.py', '== 9', '== 12')
    result, text = _pytest(root, '-rf')
    # The calibrated reader of fees.json cannot run sealed: its rule items are unverified, never passed or red.
    assert result.returncode == 0 and '2 passed, 3 unverified' in result.stdout, text
    assert not any(line.startswith('red: FEE') for line in _block(text)[1]), text
    _sealed_grey(root)


def test_sample_9_both_database_calls_run_once_and_are_not_compared(shop):
    _edit(shop, 'shop/members.py', '    return days_after_expiry <= 3\n', '    return days_after_expiry <= 7\n')
    result, text = _pytest(shop)
    assert result.returncode == 0 and '12 passed' in result.stdout, text       # one debt row, as the test asserts
    assert 'unverified: BORROW：no comparable JSON result' in _block(text)[1], text
    assert not [item for item in _observations(shop)['items'] if item.get('name') == 'BORROW'], _observations(shop)


def test_sample_19_the_broken_file_is_only_unverified(shop):
    _edit(shop, 'shop/store.py', 'return stock > reserved', 'return stock >= reserved')
    result, text = _pytest(shop)
    assert result.returncode == 0, text
    grey = [item for item in _observations(shop)['items'] if item.get('name') == 'uncovered']
    assert any('_tmp_x.py' in reason and 'cannot be parsed' in reason for item in grey for reason in item['reasons']), grey
