"""A project with 30 anchors, ten rules, copy groups and database reads, in full ordinary pytest runs.

The project is `tests/fixtures/many_anchors` (see its README). Without the plugin its 34 tests pass;
with the plugin and no change the run passes quietly; a change against the owner's words, and a copy
that drifts from its owner, are red with their source and the places involved. Only behaviour is
asserted here; the run times are measured outside the suite.
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

from tests.intent_engine._cli_fixture import block, display_text, last

SOURCE = str(Path(__file__).resolve().parents[2])
FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/many_anchors'


def _git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                           *arguments], check=True, capture_output=True, text=True, timeout=60).stdout


def _flowguard(root, *arguments):
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); from flowguard.__main__ import main; raise SystemExit(main(sys.argv[1:]))'
    return subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '--root', str(root), *arguments],
                          cwd=root, capture_output=True, text=True, timeout=120)


def _pytest(root, *options):
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    result = subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '-q', '-p', 'no:cacheprovider', *options],
                            cwd=root, capture_output=True, text=True, timeout=300, env=dict(os.environ))
    text = display_text(result)
    assert 'INTERNALERROR' not in text, text
    return result, text


@pytest.fixture(scope='module')
def template(tmp_path_factory):
    root = tmp_path_factory.mktemp('many') / 'shop'
    for file in FIXTURE.rglob('*.txt'):
        relative = file.relative_to(FIXTURE).as_posix()
        if relative == 'R1_owner.txt':
            continue
        target = root / relative.removesuffix('.txt')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(file.read_bytes())
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'many anchors baseline')
    stored = _flowguard(root, 'req', 'add', str(FIXTURE / 'R1_owner.txt'), '--id', 'R1')
    assert stored.returncode == 0, stored.stdout + stored.stderr
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
    text = path.read_text(encoding='utf-8')
    assert old in text, (file, old)
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


def test_the_fixture_has_its_anchors_rules_and_copies(template):
    sources = [path.read_text(encoding='utf-8') for path in (template / 'shop').glob('*.py')]
    comments = [line.strip() for text in sources for line in text.splitlines() if line.strip().startswith('# flowguard: ')]
    assert len(comments) == 30, comments
    assert sum('owner STANDING' in line or 'sensor STANDING' in line for line in comments) == 3
    assert sum('owner ROUND_HALF' in line or 'sensor ROUND_HALF' in line for line in comments) == 3
    rules = (template / 'tests/intent/rules.py').read_text(encoding='utf-8')
    assert rules.count('@rule(') == 10
    result, text = _pytest(template, '-o', 'addopts=', '-p', 'no:flowguard.intent.plugin',
                           '--ignore=tests/test_flowguard_intent.py')
    assert result.returncode == 0 and '34 passed' in result.stdout, text


def test_without_a_change_the_run_passes_quietly(shop):
    result, text = _pytest(shop)
    assert result.returncode == 0, text
    # 75 items, as before the sealed comparison (62 passed, 13 unverified): the anchors that read a literal
    # constant from shop.settings run sealed with that constant read from its source, never imported.
    assert '62 passed, 13 unverified' in result.stdout, text
    # Nothing red, changed or before: the timed first line and the one line of what could not be compared.
    title, *rest = block(text)
    assert re.fullmatch(r'FlowGuard \d+\.\d+ \(since [0-9a-f]{7}\): 0 red, 22 not compared; \d+\.\d s', title), title
    assert rest == ['not compared: 22 items (assumed: confirm against actual owner words, or not exhaustively checked) '
                    '-> not a failure'], rest
    with sqlite3.connect(shop / '.flowguard/cache/map.sqlite') as connection:
        greys = {item: json.loads(payload)['grey'] for item, payload in connection.execute('SELECT item, payload FROM result')
                 if json.loads(payload)['verdict'] == 'grey'}
        results = {item: json.loads(payload)['verdict'] for item, payload in connection.execute('SELECT item, payload FROM result')}
    assert not any('uses unavailable binding' in reason for reasons in greys.values() for reason in reasons), greys
    assert results['tests/intent/rules.py::STANDING_RULE[shop.policy.standing_allows:rows]'] == 'ok', results


def test_a_change_against_the_owner_words_is_red_with_the_sentence(shop):
    _edit(shop, 'shop/fees.py', '    return deposit > 100\n', '    return deposit > 100 and not member\n')
    result, text = _pytest(shop)
    assert result.returncode == 1, text
    assert [line for line in block(text) if line.startswith('red: ')] == [
        'red: rule DEPOSIT_REVIEW: deposit=101 member=T -> rule T, code False at fees.py:needs_approval (2 of 10 cells disagree) '
        '(+1 more) -> change the code so fees.py:needs_approval follows rule DEPOSIT_REVIEW'], text
    # The other count and the owner's sentence are the red's detail.
    shown = last(shop).splitlines()
    detail = shown[shown.index(next(line for line in shown if line.startswith('red: rule DEPOSIT_REVIEW: '))) + 1:]
    assert 'deposit=150 member=T -> rule T, code False at shop/fees.py:needs_approval (1 of 1 rows disagree, row L' in detail[0], shown
    assert '    DEPOSIT_REVIEW source: owner R1: 会员也一样，不能例外。' in detail, shown
    assert 'FAILED tests/intent/rules.py::DEPOSIT_REVIEW[shop.fees.needs_approval:rows]' in text, text


def test_a_copy_that_drifts_from_its_owner_is_red_at_both_places(shop):
    _edit(shop, 'shop/preview.py', 'return days_after_expiry <= 3 and owed <= 20', 'return days_after_expiry <= 4 and owed <= 20')
    result, text = _pytest(shop)
    assert result.returncode == 1, text
    # The owner reads GRACE_DAYS from shop.settings, a literal read from its source: all three copies run
    # sealed, and the owner is the reference the drifting copy must agree with.
    assert ('red: same STANDING: on days_after_expiry=4, suspended=False, owed=0: kiosk.py:kiosk_allows and the reference '
            'policy.py:standing_allows return False, preview.py:preview_allows returns True '
            '-> make preview.py:preview_allows agree with the reference') in block(text), text
    with sqlite3.connect(shop / '.flowguard/cache/map.sqlite') as connection:
        items = json.loads(connection.execute("SELECT v FROM meta WHERE k='runtime_observations'").fetchone()[0])['items']['items']
    assert not any('uses unavailable binding' in reason for item in items for reason in item.get('reasons', ())), items
    shown = last(shop).splitlines()
    leads = shown[shown.index('deprecated leads (5.0):') + 1:]
    assert any('old values 3 remain in' in line and 'shop/kiosk.py:3' in line for line in leads), shown
    assert 'FAILED tests/intent/rules.py::STANDING_RULE[shop.preview.preview_allows:rows]' in text, text
