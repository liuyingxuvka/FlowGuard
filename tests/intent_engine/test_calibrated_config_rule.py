"""A calibrated sensor that reads a configuration file keeps the 3.0.1 red.

The fixture is the round-19 demo's LATE_FEE/FEE pair: the anchor uses the old
``calibrated_by`` form and its function reads ``fees.json``. Changing the
configured daily fee (and the project's own test with it) must make ordinary
pytest fail on the rule, not leave the rule grey and report it as passed.
"""
from pathlib import Path
import json
import sqlite3
import subprocess
import sys
import textwrap

from flowguard.intent import anchors, calibration
from tests.intent_engine._cli_fixture import display_text
from tests.intent_engine._protocol_controls import bind_anchor
from tests.intent_engine._source_fixture import source_sessions  # noqa: F401 (fixture)


FEES = '''import json
from pathlib import Path

_CONF = Path(__file__).with_name("fees.json")


# flowguard: sensor LATE_FEE(days: day, member: bool) -> fee: int calibrated_by=tests/test_fees.py::test_fee
def late_fee(days: int, member: bool) -> int:
    conf = json.loads(_CONF.read_text())
    if days <= conf["free_days"]:
        return 0
    fee = (days - conf["free_days"]) * conf["per_day"]
    return fee // 2 if member else fee
'''

RULE = '''from flowguard.intent import rule, row

@rule("FEE", decides="late fee", fields={"days": int, "member": bool},
      source="assumed: 3 per day after 2 free days, members half", anchor="LATE_FEE")
def FEE(days, member):
    if days <= 2:
        return 0
    fee = (days - 2) * 3
    return fee // 2 if member else fee

FEE.rows(row(days=3, member=True, expect=1, why="half of 3 rounds down"))
'''


def _git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                           *arguments], check=True, capture_output=True, text=True, timeout=30).stdout


def _demo(root):
    (root / 'shop').mkdir(parents=True)
    (root / 'tests/intent').mkdir(parents=True)
    (root / 'shop/__init__.py').write_text('')
    (root / 'shop/fees.py').write_text(FEES)
    (root / 'shop/fees.json').write_text('{"free_days": 2, "per_day": 3}\n')
    (root / 'tests/conftest.py').write_text('pytest_plugins = ["flowguard.intent.plugin"]\n')
    (root / 'tests/test_fees.py').write_text('from shop.fees import late_fee\n\n\ndef test_fee():\n    assert late_fee(5, False) == 9\n')
    (root / 'tests/intent/fees.py').write_text(RULE)
    (root / 'tests/test_flowguard_intent.py').write_text(
        'def test_flowguard_intent(request):\n    from flowguard.intent.plugin import sentinel\n    sentinel(request.config)\n')
    (root / '.gitignore').write_text('.flowguard/cache/\n__pycache__/\n.pytest_cache/\n')
    (root / 'pyproject.toml').write_text('[project]\nname = "shop"\nversion = "0.1.0"\n\n[tool.flowguard]\n\n'
                                         '[tool.pytest.ini_options]\npythonpath = ["."]\naddopts = "-p flowguard.intent.plugin"\n')
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'demo baseline')
    return root


def _pytest(root):
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    source = str(Path(__file__).resolve().parents[2])
    return subprocess.run([sys.executable, '-c', bootstrap, source, '-q', '-p', 'no:cacheprovider', '-rf'],
                          cwd=root, capture_output=True, text=True, timeout=120)


def _verdicts(root):
    with sqlite3.connect(root / '.flowguard/cache/map.sqlite') as con:
        return {item: json.loads(payload)['verdict'] for item, payload in
                con.execute("SELECT item, payload FROM result WHERE rule='FEE'")}


def test_config_file_fee_change_fails_ordinary_pytest_on_the_rule(tmp_path):
    root = _demo(tmp_path / 'demo')
    first = _pytest(root)
    assert first.returncode == 0, first.stdout + first.stderr
    cells, rows = 'tests/intent/fees.py::FEE[shop.fees.late_fee:cells]', 'tests/intent/fees.py::FEE[shop.fees.late_fee:rows]'
    before = _verdicts(root)
    assert before[cells] != 'red' and before[rows] == 'ok', before
    # The demo change: the configured fee and the project's own test move together.
    (root / 'shop/fees.json').write_text('{"free_days": 2, "per_day": 4}\n')
    test = root / 'tests/test_fees.py'
    test.write_text(test.read_text().replace('== 9', '== 12'))
    changed = _pytest(root)
    text = display_text(changed)
    assert changed.returncode == 1, text
    assert '2 failed' in text, text
    assert 'FAILED ' + cells in text and 'FAILED ' + rows in text, text
    assert 'FAILED tests/test_fees.py' not in text, 'the project test was updated with the change'
    assert 'smallest days=3 member=F -> rule 3, code 4' in text, text
    after = _verdicts(root)
    assert after[cells] == 'red' and after[rows] == 'red', after
    assert 'FEE source: assumed: 3 per day after 2 free days, members half' in text, text
    assert 'calibrated anchor must be prepared' not in text


def test_failing_calibration_test_keeps_its_red_reason_in_ordinary_pytest(tmp_path):
    root = _demo(tmp_path / 'demo')
    (root / 'shop/fees.json').write_text('{"free_days": 2, "per_day": 4}\n')
    result = _pytest(root)
    text = display_text(result)
    assert result.returncode == 1, text
    assert 'FAILED tests/test_fees.py::test_fee' in text, text
    verdicts = _verdicts(root)
    assert verdicts['tests/intent/fees.py::FEE[shop.fees.late_fee:rows]'] == 'red', verdicts
    assert 'real calibration test did not pass completely' in text, text
    assert 'calibrated anchor must be prepared' not in text


def test_calibrated_config_reader_uses_the_named_test_call_for_each_point(tmp_path):
    (tmp_path / 'policy.py').write_text(textwrap.dedent('''
        import json
        from pathlib import Path
        # flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
        def limit(x: int) -> bool:
            return x <= json.loads(Path(__file__).with_name('limit.json').read_text())['limit']
    ''').lstrip())
    (tmp_path / 'limit.json').write_text('{"limit": 3}\n')
    (tmp_path / 'test_policy.py').write_text('from policy import limit\ndef test_native(): assert limit(2) is True\n')
    (tmp_path / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    anchor = anchors.collect_sources(tmp_path, [('policy.py', 'policy')]).entries[0]
    scope, item = bind_anchor(tmp_path, anchor)
    readings = [calibration.execute(tmp_path, anchor, values) for values in ({}, {'x': 5}, {'x': 3})]
    assert [reading.status for reading in readings] == ['ok', 'ok', 'ok'], readings
    assert [reading.value for reading in readings] == [True, False, True]
    # The requested point replaced the named test's own call; the test was not run again around it.
    (tmp_path / 'limit.json').write_text('{"limit": 9}\n')
    assert calibration.execute(tmp_path, anchor, {'x': 5}).value is True


def test_real_call_of_a_config_reader_is_checked_against_its_rule(tmp_path):
    """A refused replay still leaves the test's own call: its inputs and outcome are a current reading."""
    root = tmp_path / 'reader'
    (root / 'tests/intent').mkdir(parents=True)
    (root / 'policy.py').write_text(textwrap.dedent('''
        import json
        from pathlib import Path
        _CONF = Path(__file__).with_name('limit.json')
        # flowguard: sensor LIMIT(days: day) -> allowed: bool
        def accept(days: int) -> bool:
            return days <= json.loads(_CONF.read_text())['limit']
    ''').lstrip())
    (root / 'limit.json').write_text('{"limit": 3}\n')
    (root / 'policy.txt').write_text('At most three days.\n')
    (root / 'tests/test_policy.py').write_text('from policy import accept\ndef test_accept(): assert accept(3) is True\n')
    (root / 'tests/intent/decisions.py').write_text(textwrap.dedent('''
        from flowguard.intent import rule
        @rule('LIMIT', decides='acceptance', fields={'days': int}, anchor='LIMIT', source='doc policy.txt "At most three days."')
        def LIMIT(days):
            return days <= 3
    ''').lstrip())
    (root / 'tests/test_flowguard_intent.py').write_text(
        'def test_flowguard_intent(request):\n    from flowguard.intent.plugin import sentinel\n    sentinel(request.config)\n')
    (root / '.gitignore').write_text('.flowguard/cache/\n__pycache__/\n.pytest_cache/\n')
    (root / 'pyproject.toml').write_text('[tool.flowguard]\nauthority_docs=["policy.txt"]\n\n'
                                         '[tool.pytest.ini_options]\npythonpath = ["."]\naddopts = "-p flowguard.intent.plugin"\n')
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'reader baseline')
    first = _pytest(root)
    assert first.returncode == 0, first.stdout + first.stderr
    (root / 'limit.json').write_text('{"limit": 4}\n')
    test = root / 'tests/test_policy.py'
    test.write_text(test.read_text().replace('accept(3)', 'accept(4)'))
    changed = _pytest(root)
    text = display_text(changed)
    assert changed.returncode == 1, text
    assert 'LIMIT: days=4 -> rule F, code True' in text, text
    assert 'LIMIT source: At most three days.' in text, text
    assert 'no verified current reading' not in text, text
