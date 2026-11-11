"""A calibrated anchor or scenario reads the calls its test made in the ordinary run; no test runs again.

Design 4.5 and 8: the comparison runs sealed after the tests, so FlowGuard never re-runs a test, and a
side effect of a test happens exactly as often as without FlowGuard. A calibrated point is the named
test's recorded JSON call with the requested inputs put in place, evaluated in the sealed environment.
"""
from collections import Counter
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import textwrap

from flowguard.intent import anchors, calibration
from tests.intent_engine._protocol_controls import bind_anchor
from tests.intent_engine._source_fixture import source_sessions  # noqa: F401 (fixture)
from tests.intent_engine.test_calibration import project

SOURCE = str(Path(__file__).resolve().parents[2])

FEES = '''# flowguard: same LATE_FEE(days: day, member: bool) -> fee: int calibrated_by=tests/test_fees.py::test_fee
def late_fee(days: int, member: bool) -> int:
    if days <= 2:
        return 0
    fee = (days - 2) * 3
    return fee // 2 if member else fee


# flowguard: sensor CHOICE(x: count) -> allowed: bool calibrated_by=tests/test_fees.py::test_choice
def choice(x: int) -> bool:
    return x <= 3
'''

INTENT = '''from flowguard.intent import rule, row, flow, Node, Read, Relation

@rule("FEE", decides="late fee", fields={"days": int, "member": bool},
      source='doc policy.txt "Three per day after two free days, members half."', anchor="LATE_FEE")
def FEE(days, member):
    if days <= 2:
        return 0
    fee = (days - 2) * 3
    return fee // 2 if member else fee

FEE.rows(row(days=3, member=True, expect=1, why="half of 3 rounds down"))

@rule("CHOICE_RULE", decides="choice", fields={"x": int},
      source='doc policy.txt "At most three."')
def CHOICE_RULE(x):
    return x <= 3

CHOICE_RULE.rows(row(x=2, expect=True, why="the recorded input"), row(x=5, expect=False, why="another input"))

flow('OBSERVE_CHOICE', source='doc policy.txt "At most three."',
     nodes=[Node('case', 'CASE_CHOICE', start=True), Node('answer', 'CHOICE', phase='return', caller='case', end=True)],
     edges=[('case', 'answer')],
     relations=[Relation('CHOICE_RULE', {'x': Read('case', 'arg.x')}, Read('answer'), on='answer')])
'''


def _git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                           *arguments], check=True, capture_output=True, text=True, timeout=30).stdout


def _shop(root):
    (root / 'shop').mkdir(parents=True)
    (root / 'tests/intent').mkdir(parents=True)
    (root / 'shop/__init__.py').write_text('')
    (root / 'shop/fees.py').write_text(FEES)
    (root / 'policy.txt').write_text('Three per day after two free days, members half.\nAt most three.\n')
    # The counter fixture: every run of any test body's setup writes one line with the test's id.
    (root / 'tests/conftest.py').write_text(textwrap.dedent('''
        import pytest
        pytest_plugins = ["flowguard.intent.plugin"]
        @pytest.fixture(autouse=True)
        def counted(request):
            with open(request.config.rootpath / 'runs.log', 'a', encoding='utf-8') as log:
                log.write(request.node.nodeid + '\\n')
            yield
    ''').lstrip())
    (root / 'tests/test_fees.py').write_text(textwrap.dedent('''
        import pytest
        from shop.fees import late_fee, choice
        def test_fee():
            assert late_fee(5, False) == 9
        @pytest.fixture
        def x():
            return 2
        # flowguard: event CASE_CHOICE(x: int)
        def test_choice(x: int):
            assert choice(x) is True
    ''').lstrip())
    (root / 'tests/intent/fees.py').write_text(INTENT)
    (root / 'tests/test_flowguard_intent.py').write_text(
        'def test_flowguard_intent(request):\n    from flowguard.intent.plugin import sentinel\n    sentinel(request.config)\n')
    (root / '.gitignore').write_text('.flowguard/cache/\n__pycache__/\n.pytest_cache/\nruns.log\n')
    (root / 'pyproject.toml').write_text('[project]\nname = "shop"\nversion = "0.1.0"\n\n[tool.flowguard]\n'
                                         'authority_docs = ["policy.txt"]\n\n[tool.pytest.ini_options]\n'
                                         'pythonpath = ["."]\naddopts = "-p flowguard.intent.plugin"\n')
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'shop baseline')
    return root


def _pytest(root):
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    return subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '-q', '-p', 'no:cacheprovider', '-rA'],
                          cwd=root, capture_output=True, text=True, timeout=180)


def test_an_ordinary_run_runs_each_test_body_once_with_calibrated_and_scenario_anchors(tmp_path):
    root = _shop(tmp_path / 'shop')
    result = _pytest(root)
    runs = Counter((root / 'runs.log').read_text(encoding='utf-8').split())
    # Each collected test ran exactly once: the calibrated anchor's named test and the scenario's test
    # were not run again for the rule items, whatever their rows ask.
    assert runs and set(runs.values()) == {1}, (runs, result.stdout[-3000:])
    assert {'tests/test_fees.py::test_fee', 'tests/test_fees.py::test_choice'} <= set(runs), runs
    assert result.returncode == 0, result.stdout + result.stderr
    with sqlite3.connect(root / '.flowguard/cache/map.sqlite') as connection:
        results = {item.partition('::')[2]: json.loads(payload) for item, payload in connection.execute('SELECT item, payload FROM result')}
    # The calibrated row is evaluated sealed with the named test's own call as its context.
    assert results['FEE[shop.fees.late_fee:rows]']['verdict'] == 'ok', results['FEE[shop.fees.late_fee:rows]']
    # The scenario's own run gives its recorded input; the other row would need the test to run again.
    scenario = next(value for key, value in results.items() if key.startswith('CHOICE_RULE[') and key.endswith(':rows]'))
    assert scenario['verdict'] == 'grey', scenario
    assert any('the scenario test ran with x=2; another input needs the test to run again' in reason
               for reason in scenario['grey']), scenario


def test_calibrated_points_never_run_the_named_test_body_again(tmp_path):
    anchor = project(tmp_path, '''# flowguard: same LIMIT(x) calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3
''', '''from pathlib import Path
from policy import limit
def test_native():
    with open(Path(__file__).with_name('runs.log'), 'a', encoding='utf-8') as log:
        log.write('run\\n')
    assert limit(2) is True
''')
    bind_anchor(tmp_path, anchor)
    log = tmp_path / 'runs.log'
    assert log.read_text(encoding='utf-8').split() == ['run']            # the one ordinary run
    readings = [calibration.execute(tmp_path, anchor, values) for values in ({}, {'x': 1}, {'x': 4}, {'x': 5})]
    assert [(reading.status, reading.value) for reading in readings] == [('ok', True), ('ok', True), ('ok', False), ('ok', False)], readings
    assert log.read_text(encoding='utf-8').split() == ['run']            # no point ran the test body again


def test_a_named_test_that_did_not_run_leaves_the_point_not_compared(tmp_path):
    (tmp_path / 'policy.py').write_text('# flowguard: same LIMIT(x) calibrated_by=test_policy.py::test_native\n'
                                        'def limit(x: int) -> bool:\n    return x <= 3\n')
    (tmp_path / 'test_policy.py').write_text('from policy import limit\ndef test_native(): assert limit(2) is True\n')
    (tmp_path / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    anchor = anchors.collect_sources(tmp_path, [('policy.py', 'policy')]).entries[0]
    scope, item = bind_anchor(tmp_path, anchor)
    scope.runtime.ran.discard(item.nodeid)
    scope.runtime.readings.clear()
    scope.runtime._seen.clear()
    observed = calibration._sensor(tmp_path, anchor, {'x': 5})
    assert observed == {'status': 'grey', 'reasons': ['not compared: the named test did not run in this session']}
