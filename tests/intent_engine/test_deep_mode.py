"""Ordinary checks retain real boundaries; expensive confidence checks are explicit."""
import json
from pathlib import Path
import subprocess
import sys

from tests.intent_engine.test_plugin import database, run, sample


def check(root, *arguments):
    source = str(Path(__file__).resolve().parents[2])
    program = 'import sys; sys.path.insert(0,sys.argv.pop(1)); from flowguard.intent.cli import main; raise SystemExit(main(sys.argv[1:]))'
    return subprocess.run([sys.executable, '-c', program, source, 'check', *arguments],
                          cwd=root, capture_output=True, text=True, timeout=60)


def test_ordinary_pytest_never_calls_decision_probes_or_mutants(sample):
    (sample / 'tests/conftest.py').write_text("""from flowguard.intent.engine import Engine
from flowguard.intent import sites
def refuse(*args, **kwargs):
    raise AssertionError('ordinary pytest must not run deep probes or mutation survival')
Engine.probe = Engine.run_live = sites.mutants_of = refuse
""")
    result = run(sample)
    assert result.returncode == 0, result.stdout + result.stderr
    with database(sample) as connection:
        payloads = [json.loads(row[0]) for row in connection.execute('SELECT payload FROM result')]
        assert {item['kind'] for item in payloads} == {'rules', 'rows', 'cells'}
        attempt = json.loads(connection.execute("SELECT v FROM meta WHERE k='intent_attempt'").fetchone()[0])
        assert attempt['deep'] is False


def test_default_check_finds_a_new_code_boundary_without_dynamic_probe(sample):
    policy = sample / 'src/sample/policy.py'
    policy.write_text(policy.read_text().replace('return days <= 3', 'return days <= 3 or days == 91'))
    result = check(sample)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'days=91' in result.stdout and 'rule F, code True' in result.stdout
    with database(sample) as connection:
        attempt = json.loads(connection.execute("SELECT v FROM meta WHERE k='intent_attempt'").fetchone()[0])
        assert attempt['deep'] is False


def test_deep_check_runs_mutation_survival_after_a_complete_default_cache(sample):
    # This positive cache case needs a real, independently readable source.
    (sample / 'policy.txt').write_text('At most three days.\n')
    config = sample / 'pyproject.toml'
    config.write_text(config.read_text() + '[tool.flowguard]\nauthority_docs=["policy.txt"]\n')
    declaration = sample / 'tests/intent/decisions.py'
    declaration.write_text(declaration.read_text().replace(
        'assumed: the known boundary', 'doc policy.txt "At most three days."'))
    ordinary = check(sample)
    assert ordinary.returncode == 0, ordinary.stdout + ordinary.stderr
    deep = check(sample, '--deep')
    assert deep.returncode == 0, deep.stdout + deep.stderr
    with database(sample) as connection:
        payloads = [json.loads(row[0]) for row in connection.execute('SELECT payload FROM result')]
        assert all(item['verdict'] == 'ok' for item in payloads)
        live = [item for item in payloads if item['kind'] == 'live']
        assert len(live) == 1 and live[0]['mutants'] > 0 and live[0]['k'] == live[0]['n'] > 0
        collection = json.loads(connection.execute("SELECT v FROM meta WHERE k='intent_collection'").fetchone()[0])
        assert collection['deep'] is True
        attempt = json.loads(connection.execute("SELECT v FROM meta WHERE k='intent_attempt'").fetchone()[0])
        assert attempt['deep'] is True
        deep_attempt = attempt
    ordinary = check(sample)
    assert ordinary.returncode == 0, ordinary.stdout + ordinary.stderr
    with database(sample) as connection:
        attempt = json.loads(connection.execute("SELECT v FROM meta WHERE k='intent_attempt'").fetchone()[0])
        # An unaffected default check reuses the historical deep receipt; it
        # must not relabel that receipt or pretend mutation ran again.
        assert attempt == deep_attempt


def test_unresolved_callee_boundaries_stay_grey_and_deep_finds_the_counterexample(sample):
    policy = sample / 'src/sample/policy.py'
    policy.write_text(policy.read_text().replace('return days <= 3', 'return hidden(days)')
                      + '\ndef hidden(days: int) -> bool:\n    return days <= 3 or days == 91\n')
    ordinary = check(sample)
    assert ordinary.returncode == 0, ordinary.stdout + ordinary.stderr
    with database(sample) as connection:
        cells = [json.loads(row[0]) for row in connection.execute('SELECT payload FROM result')
                 if json.loads(row[0])['kind'] == 'cells']
        assert len(cells) == 1 and cells[0]['verdict'] == 'grey'
        assert any('hidden(days)' in reason for reason in cells[0]['grey'])
    deep = check(sample, '--deep')
    assert deep.returncode == 1, deep.stdout + deep.stderr
    assert 'days=91' in deep.stdout and 'rule F, code True' in deep.stdout


def test_assumed_source_stays_grey_and_does_not_reuse_a_deep_receipt(sample):
    deep = check(sample, '--deep')
    assert deep.returncode == 0, deep.stdout + deep.stderr
    with database(sample) as connection:
        deep_attempt = json.loads(connection.execute("SELECT v FROM meta WHERE k='intent_attempt'").fetchone()[0])
        payloads = [json.loads(row[0]) for row in connection.execute('SELECT payload FROM result')]
        rules = next(item for item in payloads if item['kind'] == 'rules')
        assert rules['verdict'] == 'grey' and any('assumed' in reason for reason in rules['grey'])
        assert any(item['kind'] == 'live' and item['mutants'] > 0 for item in payloads)
    ordinary = check(sample)
    assert ordinary.returncode == 0, ordinary.stdout + ordinary.stderr
    with database(sample) as connection:
        attempt = json.loads(connection.execute("SELECT v FROM meta WHERE k='intent_attempt'").fetchone()[0])
        payloads = [json.loads(row[0]) for row in connection.execute('SELECT payload FROM result')]
        assert attempt['deep'] is False and attempt['stamp'] > deep_attempt['stamp']
        assert all(item['kind'] != 'live' for item in payloads)
        rules = next(item for item in payloads if item['kind'] == 'rules')
        assert rules['verdict'] == 'grey' and any('assumed' in reason for reason in rules['grey'])
