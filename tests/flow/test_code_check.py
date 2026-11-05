"""Actual CLI/jobs/native recorder controls for opt-in code route checks."""
import json
import subprocess
import pytest

from checkrun import command, env, run_check

BROKEN = '''def primary():
    raise ValueError("broken primary")

def load():
    try:
        return primary()
    except ValueError:
        return 7
'''
CASE = 'tests/test_app.py::test_load'


def program(project):
    project.file('app.py', BROKEN)
    project.file('tests/test_app.py', 'from app import load\ndef test_load():\n    assert load() == 7\n')
    project.file('tests/test_unrelated.py', 'def test_unrelated():\n    raise AssertionError("must not run unselected test")\n')


def status(project):
    result = subprocess.run(command('status'), cwd=project.root, env=env(), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def test_default_check_does_not_collect_or_run_pytest_without_a_model(project):
    project.file('tests/test_unwanted.py', 'raise AssertionError("default check collected tests")\n')
    checked = run_check(project.root, '--json')
    assert checked.code == 0 and checked.data['parts'] == []
    assert not (project.root / '.flowguard/conflicts.json').exists()


def test_explicit_tests_find_masking_cache_once_and_status_preserves_source_facts(project):
    program(project)
    checked = run_check(project.root, '--tests', CASE, '--json')
    assert checked.code == 1, checked.out
    data = checked.data
    assert data['models'] == {} and len(data['parts']) == 1
    assert [row['kind'] for row in data['conflicts']] == ['MASKING']
    assert data['code_audit']['boundary'] == 'recorded tests/invocations only'
    saved = json.loads((project.root / '.flowguard/conflicts.json').read_text())
    entry, = saved['conflicts']
    assert entry['code_evidence']['route']['primary_failures'][0]['exception']['message'] == 'broken primary'
    assert entry['code_evidence']['tests'] == [CASE]
    again = run_check(project.root, '--tests', CASE, '--json')
    assert again.code == 1 and again.data['parts'][0]['cached'], again.out
    before = (project.root / '.flowguard/conflicts.json').read_bytes()
    text = status(project)
    assert entry['id'] in text and 'broken primary' in text and 'repair the witnessed primary failure' in text
    assert 'recorded tests/invocations only' in text
    assert (project.root / '.flowguard/conflicts.json').read_bytes() == before
    project.file('unrelated.py', 'def other(): return 3\n')
    assert 'stale; pending explicit retest' in status(project)
    assert entry['id'] in status(project)


@pytest.mark.parametrize('newline', [b'\n', b'\r\n'], ids=['lf', 'crlf'])
def test_aliased_temporary_directory_keeps_code_inputs_current(project, tmp_path, monkeypatch, newline):
    from flowguard.flow.jobs import lookup, plan

    physical = tmp_path / 'physical-temp'
    physical.mkdir()
    alias = tmp_path / 'temp-alias'
    alias.symlink_to(physical, target_is_directory=True)
    monkeypatch.setenv('TMPDIR', str(alias))
    program(project)
    source = project.root / 'app.py'
    raw = ('from pathlib import Path\nDATA = Path(__file__).with_name("payload.bin").read_bytes()\n' + BROKEN).encode().replace(b'\n', newline)
    source.write_bytes(raw)
    payload = project.root / 'payload.bin'
    binary = b'\x00\r\n'
    payload.write_bytes(binary)
    first = run_check(project.root, '--tests', CASE, '--json')
    assert first.code == 1, first.out
    again = run_check(project.root, '--tests', CASE, '--json')
    assert again.code == 1 and again.data['parts'][0]['cached'], again.out
    assert source.read_bytes() == raw and payload.read_bytes() == binary
    item, = plan(project.root, [], tests=[CASE])
    assert lookup(project.root, item) is not None
    payload.write_bytes(b'\x00\n')  # Binary newlines are real input bytes, not Python source equivalence.
    assert lookup(project.root, item) is None
    payload.write_bytes(binary)
    source.write_bytes(raw.replace(b'raise ValueError("broken primary")', b'return 7'))
    assert lookup(project.root, item) is None


def test_source_edit_cannot_quietly_close_the_original_recorded_finding(project):
    program(project)
    first = run_check(project.root, '--tests', CASE, '--json')
    identifier = first.data['conflicts'][0]['id']
    project.file('app.py', 'def load(): return 7\n')
    assert 'stale; pending explicit retest' in status(project)
    checked = run_check(project.root, '--tests', CASE, '--json')
    assert checked.code == 1 and identifier in {row['id'] for row in checked.data['conflicts']}
    assert 'original recorded code observation not yet verified repaired' in checked.data['conflicts'][0]['detail']['kept']
    assert checked.data['closed'] == []


def test_primary_repair_retains_original_test_and_source_guard_and_closes_only_that_scope(project):
    program(project)
    first = run_check(project.root, '--tests', CASE, '--json')
    identifier = first.data['conflicts'][0]['id']
    project.file('app.py', BROKEN.replace('raise ValueError("broken primary")', 'return 7'))
    checked = run_check(project.root, '--tests', CASE, '--json')
    assert checked.code == 0, checked.out
    assert checked.data['conflicts'] == [] and checked.data['closed'][0]['id'] == identifier
    saved = json.loads((project.root / '.flowguard/conflicts.json').read_text())
    proof = saved['closed'][0]['closure']
    assert proof['boundary'] == 'original recorded tests/invocations only'
    assert proof['regressions'][0]['nodeid'] == CASE and proof['regressions'][0]['passed']
    assert proof['primary_refs'] == ['app.py#primary']


def test_changed_test_cannot_weaken_away_original_code_conflict(project):
    program(project)
    first = run_check(project.root, '--tests', CASE, '--json')
    identifier = first.data['conflicts'][0]['id']
    project.file('app.py', BROKEN.replace('raise ValueError("broken primary")', 'return 7'))
    project.file('tests/test_app.py', 'from app import load\ndef test_load():\n    load()\n')
    checked = run_check(project.root, '--tests', CASE, '--json')
    assert checked.code == 1 and identifier in {row['id'] for row in checked.data['conflicts']}
    assert not checked.data['closed']


def test_project_code_part_is_planned_once_alongside_multiple_models(project):
    from flowguard.flow.jobs import plan
    program(project)
    for name in ['a', 'b']:
        project.flow(name, 'from flowguard.flow import Model\nm=Model("lamp")\nm.field("x", (False,True), False)\nMODEL=m\n')
    parts = plan(project.root, list((project.root / '.flowguard/flow').glob('*.py')), tests=[CASE])
    assert len([part for part in parts if part.spec.kind == 'code-audit']) == 1
    assert len([part for part in parts if part.spec.kind == 'core']) == 2


def test_native_capture_returns_running_then_resumes_same_existing_job(project):
    project.file('app.py', 'def load(): return 7\n')
    project.file('tests/test_app.py', 'import time\nfrom app import load\ndef test_load():\n    time.sleep(0.5)\n    assert load() == 7\n')
    first = run_check(project.root, '--tests', CASE, '--wait', '0', '--keep', '30', '--json')
    assert first.data['running'] is not None and first.data['resume']
    assert not (project.root / '.flowguard/conflicts.json').exists()
    again = run_check(project.root, '--tests', CASE, '--wait', '30', '--keep', '30', '--json')
    assert again.data['running'] is None and again.data['resume'] is None, again.out
    assert len(again.data['parts']) == 1


def test_model_native_unknown_is_a_finished_result_not_an_endless_running_job(project):
    from test_native_evidence import APP, MODEL
    project.file('app.py', 'import time\n' + APP.replace('self.n = 1', 'time.time()\n        self.n = 1'))
    project.flow('counter', MODEL)
    checked = run_check(project.root, '--json')
    assert checked.data['running'] is None and checked.data['resume'] is None, checked.out
    assert not checked.data['complete'] and checked.data['models']['counter']['finished']
    assert 'native conformance unavailable' in checked.data['verdict']


def test_local_masking_and_visible_facts_survive_an_unrelated_subprocess_gap(project):
    program(project)
    project.file('app.py', BROKEN + '\ndef visible():\n    try:\n        raise ValueError("visible primary")\n    except ValueError:\n        raise\n')
    project.file('tests/test_app.py', '''import subprocess, sys, pytest
from app import load, visible
def test_load():
    assert load() == 7
def test_visible():
    with pytest.raises(ValueError): visible()
def test_child():
    assert subprocess.run([sys.executable, '-c', 'pass']).returncode == 0
''')
    checked = run_check(project.root, '--tests', CASE, 'tests/test_app.py::test_visible', 'tests/test_app.py::test_child', '--json')
    assert checked.data['running'] is None and not checked.data['complete'], checked.out
    assert [row['kind'] for row in checked.data['conflicts']] == ['MASKING']
    assert 'VISIBLE' in {row['classification'] for row in checked.data['code_audit']['witnesses']}
    text = status(project)
    assert 'broken primary' in text and 'witnessed VISIBLE' in text and 'UNKNOWN observed scope' in text


def test_existing_both_purpose_uses_live_owner_authority_and_retirement_reopens(project):
    from flowguard.map.requests import retire_request
    project.file('app.py', '''def price(rate, days):
    cost = multiply(rate, days)
    return cost * 80 // 100
def quote(rate, days):
    amount = multiply(rate, days)
    return -(-amount * 80 // 100)
def multiply(a, b): return a * b
''')
    project.file('tests/test_app.py', 'from app import price,quote\ndef test_price():\n    assert price(3,1)==2\ndef test_quote():\n    assert quote(3,1)==3\n')
    cases = ['tests/test_app.py::test_price', 'tests/test_app.py::test_quote']
    first = run_check(project.root, '--tests', *cases, '--json')
    assert [row['kind'] for row in first.data['conflicts']] == ['BOTH'], first.out
    identifier = first.data['conflicts'][0]['id']
    words = 'price and quote may both remain because their rounding serves distinct callers.'
    project.request('R1', words + '\n')
    def decide(*extra):
        result = subprocess.run(command('decide', identifier, '--owner', words, '--request', 'R1', '--json', *extra),
                                cwd=project.root, env=env(), text=True, capture_output=True)
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(result.stdout)
    assert decide()['result']['open']
    assert json.loads((project.root / '.flowguard/conflicts.json').read_text())['conflicts']
    declared = decide('--existing-routes')
    assert declared['result']['outcome'] == 'routes_declared' and not declared['result']['code_fixed']
    saved = json.loads((project.root / '.flowguard/conflicts.json').read_text())
    assert not saved['conflicts'] and saved['closed'][0]['code_evidence']['route']['classification'] == 'BOTH'
    assert 'DECLARED BOTH' in status(project)
    again = run_check(project.root, '--tests', *cases, '--json')
    assert again.code == 0 and not again.data['conflicts'], again.out
    unrelated_scope = run_check(project.root, '--tests', cases[0], '--json')
    assert unrelated_scope.code == 0, unrelated_scope.out
    assert 'DECLARED BOTH' in status(project)
    retire_request(project.root, 'R1')
    assert 'OPEN BOTH' in status(project)
    restored = json.loads((project.root / '.flowguard/conflicts.json').read_text())
    assert restored['conflicts'][0]['id'] == identifier


def test_owner_words_cannot_declare_a_masked_primary_failure(project):
    program(project)
    first = run_check(project.root, '--tests', CASE, '--json')
    identifier = first.data['conflicts'][0]['id']
    words = 'load may use both routes.'
    project.request('R1', words + '\n')
    result = subprocess.run(command('decide', identifier, '--owner', words, '--request', 'R1', '--existing-routes', '--json'),
                            cwd=project.root, env=env(), text=True, capture_output=True)
    assert result.returncode == 2 and 'decision_route_purpose_invalid' in result.stdout
    assert json.loads((project.root / '.flowguard/conflicts.json').read_text())['conflicts'][0]['id'] == identifier


def test_selected_test_failure_is_nonzero_and_retained_without_rerunning(project):
    project.file('app.py', 'def load(): return 7\n')
    project.file('tests/test_app.py', 'from app import load\ndef test_load():\n    assert load()==7\n')
    project.commit()
    project.file('app.py', 'def load(): return 8\n')
    project.git('add', 'app.py')
    checked = run_check(project.root, '--tests', CASE, '--json')
    assert checked.code == 2 and checked.data['errors'][0]['kind'] == 'TEST FAILED', checked.out
    assert checked.data['code_audit']['test_failures'] == [CASE]
    assert 'selected native test failed' in status(project)
    ordinary = run_check(project.root, '--json')
    assert ordinary.code == 2 and ordinary.data['parts'] == []
    assert ordinary.data['code_audit']['test_failures'] == [CASE]
    ready = run_check(project.root, '--commit-ready', '--json')
    assert ready.code == 1 and not ready.data['ready']
    assert any(reason['code'] == 'selected_tests_failed' for reason in ready.data['reasons'])


def test_code_audit_current_index_uses_the_existing_read_only_policy(project):
    program(project)
    project.commit()
    assert run_check(project.root, '--tests', CASE, '--json').code == 1
    project.file('app.py', BROKEN.replace('raise ValueError("broken primary")', 'return 7'))
    assert run_check(project.root, '--tests', CASE, '--json').code == 0
    project.git('add', 'app.py')
    ready = run_check(project.root, '--commit-ready', '--json')
    assert ready.code == 0 and ready.data['ready'], ready.out
    assert ready.data['affected'] == ['@recorded-code']
    project.file('app.py', BROKEN.replace('raise ValueError("broken primary")', 'return 8'))
    project.git('add', 'app.py')
    stale = run_check(project.root, '--commit-ready', '--json')
    assert stale.code == 1 and not stale.data['ready'], stale.out
    assert any(reason['code'] == 'stale_index' for reason in stale.data['reasons'])


def test_identical_handlers_keep_distinct_primary_witnesses_and_repairs(project):
    source = '''def first(): raise ValueError("first primary")
def second(): raise ValueError("second primary")
def load(which):
    if which == "first":
        try:
            return first()
        except ValueError:
            return 7
    try:
        return second()
    except ValueError:
        return 7
'''
    project.file('app.py', source)
    project.file('tests/test_app.py', 'from app import load\ndef test_first():\n    assert load("first")==7\ndef test_second():\n    assert load("second")==7\n')
    cases = ['tests/test_app.py::test_first', 'tests/test_app.py::test_second']
    before = run_check(project.root, '--tests', *cases, '--json')
    assert len(before.data['conflicts']) == 2, before.out
    identifiers = {row['detail']['route']['primary_failures'][0]['exception']['message']: row['id']
                   for row in before.data['conflicts']}
    assert set(identifiers) == {'first primary', 'second primary'}
    project.file('app.py', source.replace('raise ValueError("first primary")', 'return 7'))
    after = run_check(project.root, '--tests', *cases, '--json')
    assert after.code == 1 and [row['id'] for row in after.data['conflicts']] == [identifiers['second primary']]
    assert after.data['closed'][0]['id'] == identifiers['first primary']

