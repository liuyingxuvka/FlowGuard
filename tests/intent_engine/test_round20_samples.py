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
    red = [line for line in block if line.startswith('红：') or line.startswith('    ')]
    rest = [line for line in block if line not in red]
    assert len(rest) <= 10, block
    assert not any('…' in line for line in block), block
    kinds = ('红', '变', '比较', '线索', '未验证')
    order = [kinds.index(re.match('|'.join(kinds), line)[0]) for line in block if not line.startswith('    ')]
    assert order == sorted(order), block
    return lines[start], block


def _observations(root):
    with sqlite3.connect(root / '.flowguard/cache/map.sqlite') as connection:
        return json.loads(connection.execute("SELECT v FROM meta WHERE k='runtime_observations'").fetchone()[0])['items']


def test_without_a_change_the_run_is_quiet(shop):
    result, text = _pytest(shop)
    assert result.returncode == 0 and '12 passed' in result.stdout, text
    assert 'FlowGuard（' not in text, text


def test_sample_1_equal_stock_and_reserved_changes_from_refused_to_allowed(shop):
    _edit(shop, 'shop/store.py', 'return stock > reserved', 'return stock >= reserved')
    result, text = _pytest(shop)
    assert result.returncode == 0, text
    title, block = _block(text)
    head = _git(shop, 'rev-parse', 'HEAD').strip()
    assert title == f'FlowGuard（相对任务开始 {head[:7]}）', title
    line = next(line for line in block if line.startswith('变：AVAILABLE（shop/store.py:12）'))
    assert re.search(r'(stock=reserved|reserved=stock)（0–2）', line) and 'False → True' in line, line


def test_sample_2_database_write_is_refused_at_its_line_and_the_table_is_unchanged(shop, tmp_path):
    _edit(shop, 'shop/store.py', 'return count + stock - reserved', 'return max(0, count + stock - reserved)')
    rows = {}
    for label, options in (('plugin', ()), ('without', ('-p', 'no:flowguard.intent.plugin'))):
        target = tmp_path / (label + '.json')
        result, text = _pytest(shop, *options, 'tests/test_store.py', env={'HIRES_ROWS': str(target)})
        assert result.returncode == 0, text
        rows[label] = json.loads(target.read_text())
        if label == 'plugin':
            line = next(line for line in _block(text)[1] if line.startswith('未验证：HIRES'))
            assert ('回放被拦住：shop/store.py:19 db.execute("insert into hires(item_id) values (?)", (item_id,))'
                    '：写数据库 INSERT hires') in line, line
    assert rows == {'plugin': 1, 'without': 1}
    result, text = _pytest(shop)                         # the full suite shows the same line
    assert result.returncode == 0 and any(line.startswith('未验证：HIRES（shop/store.py:18）：回放被拦住') for line in _block(text)[1]), text


def test_sample_3_a_helper_constant_shows_its_whole_interval_and_cause(shop):
    _edit(shop, 'shop/policy.py', 'GRACE_DAYS = 3', 'GRACE_DAYS = 7')
    result, text = _pytest(shop)
    title, block = _block(text)
    line = next(line for line in block if line.startswith('变：STANDING（shop/policy.py:10）'))
    assert 'days_after_expiry=4–7' in line and 'False → True' in line, line
    assert '原因：GRACE_DAYS 3 → 7（shop/policy.py:1）' in line, line
    # The copy in preview.py still says 3: the same-name anchors now disagree, red with its next step.
    assert result.returncode == 1, text
    red = next(index for index, line in enumerate(block) if line.startswith('红：同名锚点 STANDING：'))
    assert 'shop/policy.py:10' in block[red] and 'shop/preview.py:2' in block[red] and '≠' in block[red], block
    assert block[red + 1].startswith('    '), block


def test_sample_4_unanchored_late_fee_reports_the_member_classes(shop):
    _edit(shop, 'shop/fees.py', 'return fee // 2 if member else fee', 'return fee * 2 // 3 if member else fee')
    result, text = _pytest(shop)
    assert result.returncode == 0, text
    line = next(line for line in _block(text)[1] if line.startswith('变：late_fee（未挂锚点，自动）（shop/fees.py:1）'))
    assert int(re.search(r'变 (\d+) 类', line)[1]) >= 5 and 'member=T' in line and 'member=F' not in line, line
    assert '例：days=3, member=T：1 → 2' in line, line


def test_sample_5_the_skipped_save_step_is_a_visible_path_change(shop):
    _edit(shop, 'shop/publish.py', 'return not artifact_id.startswith("tmp")', 'return not artifact_id.startswith(("tmp", "a"))')
    result, text = _pytest(shop)
    assert result.returncode == 0, text
    assert '变：路径 tests/test_publish.py::test_release：ENTRY → SAVED → PUBLISHED 变成 ENTRY → PUBLISHED' in _block(text)[1], text


def test_sample_7_rule_violation_is_one_red_line_with_the_owner_sentence(shop):
    _edit(shop, 'shop/deposit.py', 'return deposit > 100', 'return deposit > 100 and not member')
    result, text = _pytest(shop)
    assert result.returncode == 1 and '2 failed, 10 passed' in result.stdout, text
    block = _block(text)[1]
    reds = [index for index, line in enumerate(block) if line.startswith('红：DEPOSIT_REVIEW')]
    assert len(reds) == 1, block
    line = block[reds[0]]
    assert 'deposit=101 member=T' in line and line.endswith('出处：owner R1: 会员也一样，不能例外。'), line
    assert block[reds[0] + 1] == '    改代码，让 shop/deposit.py:2 符合规则 DEPOSIT_REVIEW；', block
    assert 'tests/intent/deposit.py:4' in block[reds[0] + 2], block


def test_sample_7_the_phase_0_config_fee_rule_is_red_in_the_new_block(tmp_path):
    from tests.intent_engine.test_calibrated_config_rule import _demo
    root = _demo(tmp_path / 'demo')
    _edit(root, 'shop/fees.json', '"per_day": 3', '"per_day": 4')
    _edit(root, 'tests/test_fees.py', '== 9', '== 12')
    result, text = _pytest(root, '-rf')
    assert result.returncode == 1 and '2 failed' in result.stdout, text
    line = next(line for line in _block(text)[1] if line.startswith('红：FEE'))
    assert 'days=3 member=F -> rule 3, code 4' in line and '出处：assumed: 3 per day after 2 free days, members half' in line, line


def test_sample_9_both_database_contexts_are_observed_and_the_second_shows_an_interval(shop):
    _edit(shop, 'shop/members.py', '    return days_after_expiry <= 3\n', '    return days_after_expiry <= 7\n')
    result, text = _pytest(shop)
    assert result.returncode == 0, text
    line = next(line for line in _block(text)[1] if line.startswith('变：BORROW（shop/members.py:11）'))
    assert 'days_after_expiry=4–7，member_id=1' in line and '原因：BORROW 的常量 3 → 7（shop/members.py:15）' in line, line
    readings = [item for item in _observations(shop)['items'] if item.get('name') == 'BORROW']
    assert len(readings) == 2 and all(item['status'] == 'ok' for item in readings), readings
    assert readings[0]['changed'] == [] and len(readings[1]['changed']) == 4, readings


def test_sample_19_the_broken_file_is_only_unverified(shop):
    _edit(shop, 'shop/store.py', 'return stock > reserved', 'return stock >= reserved')
    result, text = _pytest(shop)
    assert result.returncode == 0, text
    grey = [item for item in _observations(shop)['items'] if item.get('name') == '未覆盖']
    assert any('_tmp_x.py' in reason and 'cannot be parsed' in reason for item in grey for reason in item['reasons']), grey
