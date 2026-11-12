"""A calibrated sensor that reads a configuration file is unverified, never passed.

The fixture is the round-19 demo's LATE_FEE/FEE pair: the anchor uses the old
``calibrated_by`` form and its function reads ``fees.json``. Calibrated points run
in the sealed environment (design 4.5), which has no files: the rule's items on
the anchor stay unverified with the reason, and are never reported as passed. A
plain sensor's own real call is still checked against its rule (last test).
"""
from pathlib import Path
import json
import sqlite3
import subprocess
import sys
import textwrap

from flowguard.intent import anchors, calibration
from tests.intent_engine._cli_fixture import display_text, last
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


CELLS, ROWS = 'tests/intent/fees.py::FEE[shop.fees.late_fee:cells]', 'tests/intent/fees.py::FEE[shop.fees.late_fee:rows]'


def _sealed_grey(root):
    with sqlite3.connect(root / '.flowguard/cache/map.sqlite') as con:
        results = {item: json.loads(payload) for item, payload in
                   con.execute("SELECT item, payload FROM result WHERE rule='FEE'")}
    for item in (CELLS, ROWS):
        assert results[item]['verdict'] == 'grey', results
        assert any('uses attribute loads' in reason for reason in results[item]['grey']), results[item]


def test_config_file_fee_change_leaves_the_calibrated_rule_unverified_not_passed(tmp_path):
    root = _demo(tmp_path / 'demo')
    first = _pytest(root)
    assert first.returncode == 0 and '2 passed, 3 unverified' in first.stdout, first.stdout + first.stderr
    _sealed_grey(root)
    # The demo change: the configured fee and the project's own test move together.
    (root / 'shop/fees.json').write_text('{"free_days": 2, "per_day": 4}\n')
    test = root / 'tests/test_fees.py'
    test.write_text(test.read_text().replace('== 9', '== 12'))
    changed = _pytest(root)
    text = display_text(changed)
    # The sealed environment cannot read fees.json, so it claims neither red nor passed for the rule.
    assert changed.returncode == 0 and '2 passed, 3 unverified' in text, text
    assert 'FAILED tests/test_fees.py' not in text, 'the project test was updated with the change'
    _sealed_grey(root)
    assert 'calibrated anchor must be prepared' not in text


def test_failing_calibration_test_fails_the_run_and_the_rule_stays_unverified(tmp_path):
    root = _demo(tmp_path / 'demo')
    (root / 'shop/fees.json').write_text('{"free_days": 2, "per_day": 4}\n')
    result = _pytest(root)
    text = display_text(result)
    assert result.returncode == 1 and '1 failed, 1 passed, 3 unverified' in text, text
    assert 'FAILED tests/test_fees.py::test_fee' in text, text
    _sealed_grey(root)
    assert 'calibrated anchor must be prepared' not in text


def test_calibrated_config_reader_points_run_sealed_and_never_read_the_file(tmp_path):
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
    # No point reads limit.json in the sealed environment: each is unverified with the reason, no value.
    assert [(reading.status, reading.value) for reading in readings] == [('grey', None)] * 3, readings
    assert all(any('uses attribute loads' in reason for reason in reading.reasons) for reading in readings), readings
    (tmp_path / 'limit.json').write_text('{"limit": 9}\n')
    again = calibration.execute(tmp_path, anchor, {'x': 5})
    assert again.status == 'grey' and again.value is None, again


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
    assert ('red: rule LIMIT: days=4 -> rule F, code True at policy.py:accept '
            '-> change the code so policy.py:accept follows rule LIMIT') in text.splitlines(), text
    assert '    LIMIT source: At most three days.' in last(root).splitlines(), text
    assert 'no verified current reading' not in text, text
