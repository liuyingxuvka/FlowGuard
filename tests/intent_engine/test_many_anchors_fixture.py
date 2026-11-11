"""A project with 30 anchors, ten rules, copy groups and database reads, in full ordinary pytest runs.

The project is `tests/fixtures/many_anchors` (see its README). Without the plugin its 34 tests pass;
with the plugin and no change the run passes quietly; a change against the owner's words, and a copy
that drifts from its owner, are red with their source and the places involved. Only behaviour is
asserted here; the run times are measured outside the suite.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys

import pytest

from tests.intent_engine._cli_fixture import display_text

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
    assert '62 passed' in result.stdout, text
    assert 'FlowGuard（' not in text, text


def test_a_change_against_the_owner_words_is_red_with_the_sentence(shop):
    _edit(shop, 'shop/fees.py', '    return deposit > 100\n', '    return deposit > 100 and not member\n')
    result, text = _pytest(shop)
    assert result.returncode == 1, text
    red = next(line for line in text.splitlines() if line.startswith('red: DEPOSIT_REVIEW'))
    assert 'deposit=150 member=T -> rule T, code False' in red and 'source: owner R1: 会员也一样，不能例外。' in red, red
    assert 'FAILED tests/intent/rules.py::DEPOSIT_REVIEW[shop.fees.needs_approval:rows]' in text, text


def test_a_copy_that_drifts_from_its_owner_is_red_at_both_places(shop):
    _edit(shop, 'shop/preview.py', 'return days_after_expiry <= 3 and owed <= 20', 'return days_after_expiry <= 4 and owed <= 20')
    result, text = _pytest(shop)
    assert result.returncode == 1, text
    red = next(line for line in text.splitlines() if line.startswith('red: same-name anchor STANDING'))
    # the owner is the reference: the copy that left it is the one to change
    assert ('3 copies: 2 copies return F (reference shop/policy.py:5 standing_allows, shop/kiosk.py:2 kiosk_allows), 1 copies return T (shop/preview.py:2 preview_allows) -> make shop/preview.py:2 preview_allows agree with the reference') in red, red
    assert any(line.startswith('lead: old values 3 remain in') and 'shop/kiosk.py:3' in line for line in text.splitlines()), text
    assert 'FAILED tests/intent/rules.py::STANDING_RULE[shop.preview.preview_allows:rows]' in text, text
