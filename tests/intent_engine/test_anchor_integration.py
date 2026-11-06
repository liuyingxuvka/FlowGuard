"""Exercise source comments through the actual CLI and ordinary pytest plugin."""
from pathlib import Path
import subprocess
import sys

import pytest


def run(root, *args):
    source = str(Path(__file__).resolve().parents[2])
    command = [sys.executable, '-c',
               'import sys;sys.path.insert(0,sys.argv.pop(1));import pytest;raise SystemExit(pytest.main(sys.argv[1:]))',
               source, '-q', '-p', 'flowguard.intent.plugin', *args]
    return subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=60)


def project(root, code, intent, tests=''):
    (root / 'tests/intent').mkdir(parents=True)
    (root / 'app.py').write_text(code)
    (root / 'tests/intent/policy.py').write_text(intent)
    (root / 'tests/test_flowguard_intent.py').write_text(
        'def test_flowguard_intent(request):\n'
        ' from flowguard.intent.plugin import sentinel\n sentinel(request.config)\n')
    if tests:
        (root / 'tests/test_actual.py').write_text(tests)
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')


RULE = '''from flowguard.intent import rule,row
@rule('LIMIT',decides='grace',fields={'days':int},source='assumed: regression',anchor='GRACE')
def LIMIT(days): return days <= 3
LIMIT.rows(row(days=4,expect=False,why='the fourth day remains refused'))
'''
SOURCE = '''# flowguard: sensor GRACE(days: days) -> allowed: bool
def accept(days: int) -> bool:
    return days <= 3
'''


def test_draft_reads_source_without_importing_the_target(tmp_path, capsys):
    from flowguard.intent import cli
    project(tmp_path, 'raise RuntimeError("must not be imported")\n' + SOURCE, RULE)
    assert cli.main(['--root', str(tmp_path), 'anchor', 'draft', 'app:accept']) == 0
    text = capsys.readouterr().out
    assert '# flowguard: sensor accept(days:' in text
    assert 'range days:' in text and '3' in text


def test_tool_type_failure_is_not_an_expected_business_refusal(tmp_path):
    intent = '''from flowguard.intent import rule,row,Refused
@rule('LIMIT',decides='grace',fields={'days':int},source='assumed: reject input',anchor='GRACE')
def LIMIT(days): return Refused('Exception')
LIMIT.rows(row(days=4,expect=Refused('Exception'),why='the program must actually refuse'))
'''
    project(tmp_path, SOURCE.replace('days <= 3', '1'), intent)
    result = run(tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'return does not have declared type' in result.stdout + result.stderr


def test_same_name_copy_disagreement_fails_pytest_and_check_without_rules(tmp_path, capsys):
    from flowguard.intent import cli
    copy = SOURCE.replace('def accept(', 'def other(').replace('<= 3', '<= 7')
    project(tmp_path, SOURCE + '\n' + copy, '')
    result = run(tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'GRACE' in result.stdout
    assert cli.main(['--root', str(tmp_path), 'check']) == 1
    assert 'GRACE' in capsys.readouterr().out


@pytest.mark.parametrize('merged', [False, True])
def test_named_anchor_distinct_is_a_collected_checked_item(tmp_path, merged):
    copy = SOURCE.replace('GRACE', 'OTHER').replace('def accept(', 'def other(')
    if not merged:
        copy = copy.replace('<= 3', '<= 7')
    intent = '''from flowguard.intent import distinct
distinct('GRACE','OTHER',why='these are deliberately different policies',source='assumed: separation')
'''
    project(tmp_path, SOURCE + '\n' + copy, intent)
    result = run(tmp_path)
    assert result.returncode == int(merged), result.stdout + result.stderr
    from flowguard.intent.cache import read
    from flowguard.intent.config import load_config
    data = read(load_config(tmp_path))
    parts = [part for group in data['results'].values() for part in group['items'].values()
             if part.get('kind') == 'anchor_distinct']
    assert len(parts) == 1
    assert parts[0]['verdict'] == ('red' if merged else 'ok')
    assert parts[0]['provisional'] and parts[0]['behavior_checked']
    assert any(rule.get('kind') == 'anchor_distinct' for rule in data['summary']['rules'].values())


@pytest.mark.parametrize('mode', ['valid', 'wrong', 'missing', 'signature'])
def test_rule_uses_real_anchor_without_a_call_adapter(tmp_path, mode):
    code = SOURCE
    if mode == 'wrong':
        code = code.replace('<= 3', '<= 4')
    if mode == 'missing':
        code = code.replace('# flowguard: sensor GRACE(days: days) -> allowed: bool\n', '')
    if mode == 'signature':
        code = code.replace('GRACE(days:', 'GRACE(expired:')
    project(tmp_path, code, RULE)
    result = run(tmp_path)
    assert result.returncode == (0 if mode == 'valid' else 1), result.stdout + result.stderr
    if mode == 'valid':
        from flowguard.intent.cache import read
        from flowguard.intent.config import load_config
        readings = read(load_config(tmp_path))['results']['LIMIT']['items'].values()
        assert any(part.get('kind') == 'cells' and part.get('entered') for part in readings)
        assert all(part['verdict'] != 'red' for part in readings)


@pytest.mark.parametrize('broken', [False, True])
def test_flow_checks_actual_order_even_when_native_test_passes(tmp_path, broken):
    code = '''# flowguard: event ENTRY()
def run():
    save()
    return publish()
# flowguard: event SAVED()
def save():
    return None
# flowguard: event PUBLISHED()
def publish():
    return 'done'
'''
    if broken:
        code = code.replace('    save()\n', '')
    intent = '''from flowguard.intent import flow,Node
flow('ORDER',source='assumed: save completes before publish',
     nodes=[Node('entry','ENTRY'),Node('save','SAVED',phase='return'),Node('publish','PUBLISHED')],
     edges=[('entry','save'),('save','publish')])
'''
    project(tmp_path, code, intent, 'from app import run\ndef test_run(): assert run() == "done"\n')
    result = run(tmp_path)
    assert result.returncode == int(broken), result.stdout + result.stderr
    if broken:
        assert 'runtime path entry -> publish is not allowed' in result.stdout + result.stderr
