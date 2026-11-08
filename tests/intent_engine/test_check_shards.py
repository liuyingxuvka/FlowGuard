"""Full checks must finish the actual collection and never borrow partial trust."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

SOURCE = str(Path(__file__).resolve().parents[2])


def project(root):
    (root / 'tests/intent').mkdir(parents=True)
    (root / 'policy.py').write_text('# flowguard: sensor PERMIT(x: flag) -> answer: bool\ndef permit(x: bool) -> bool:\n    return x\n')
    (root / 'tests/intent/permit.py').write_text('''from flowguard.intent import rule, row
@rule('PERMIT', decides='permit', fields={'x': bool}, anchor='PERMIT', source='assumed: only true is permitted')
def PERMIT(x): return x
PERMIT.rows(row(x=False,expect=False,why='false remains forbidden'))
''')
    (root / 'tests/test_flowguard_intent.py').write_text('def test_flowguard_intent(request):\n    from flowguard.intent.plugin import sentinel\n    sentinel(request.config)\n')
    (root / 'tests/test_values.py').write_text('''import pytest
from policy import permit
@pytest.mark.parametrize('x',[False,True])
@pytest.mark.parametrize('repeat',[0,1])
def test_values(x,repeat): assert permit(x) is x
@pytest.mark.skipif(True,reason='declared platform control')
def test_legitimate_skip(): assert False
''')
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    return root


def run(root, *args, inject=''):
    boot = ';'.join(['import sys', 'sys.path.insert(0,sys.argv.pop(1))', 'from flowguard.intent import cli',
                     *([inject] if inject else []), 'raise SystemExit(cli.main())'])
    return subprocess.run([sys.executable, '-c', boot, SOURCE, 'check', *args], cwd=root,
                          text=True, capture_output=True, timeout=60)


def metadata(root):
    with closing(sqlite3.connect(root / '.flowguard/cache/map.sqlite')) as con:
        ordinary = con.execute("SELECT v FROM meta WHERE k='ordinary_collection'").fetchone()
        deps = con.execute('SELECT * FROM test_dependency ORDER BY file').fetchall()
    return ordinary, deps


def attempt(root):
    with closing(sqlite3.connect(root / '.flowguard/cache/map.sqlite')) as con:
        row = con.execute("SELECT v FROM meta WHERE k='intent_attempt'").fetchone()
    assert row is not None, 'the real verification attempt must be stored'
    return json.loads(row[0])


def test_full_deep_check_finishes_every_parameter_and_intent_item(tmp_path):
    root = project(tmp_path)
    (root / 'tests/test_extra.py').write_text('def test_extra(): assert True\n')
    result = run(root, '--all', '--deep')
    assert result.returncode == 0, result.stdout + result.stderr
    checked = attempt(root)
    nodes = checked['complete_collection']
    collected = set(nodes['collected_nodeids'])
    assert collected == set(nodes['completed_nodeids'])
    assert {f'tests/test_values.py::test_values[{repeat}-{value}]'
            for repeat in (0, 1) for value in ('False', 'True')} <= collected
    assert {'tests/test_values.py::test_legitimate_skip', 'tests/test_extra.py::test_extra',
            'tests/test_flowguard_intent.py::test_flowguard_intent',
            'tests/intent/permit.py::PERMIT[rules]'} <= collected
    assert checked['declared'] == checked['collected'] == checked['selected']
    assert checked['declared'] >= 4 and checked['deferred'] == 0
    assert checked['deep'] and checked['sentinel'] == 'ok'
    assert checked['exit'] == 0 and checked['missing'] == checked['errors'] == []


@pytest.mark.parametrize('value', ['0/3', '4/3', '1/0', '-1/3', '1', '1/2/3', 'x/3', '１/3', '1/2'])
def test_retired_shard_argument_is_rejected_instead_of_running_a_partial_check(tmp_path, value):
    root = project(tmp_path)
    result = run(root, '--all', '--shard', value)
    assert result.returncode == 2, result.stdout + result.stderr
    assert 'unrecognized arguments' in result.stderr and '--shard' in result.stderr


@pytest.mark.parametrize('args', [('--shard', '1/2'), ('--all', '--since', 'HEAD', '--shard', '1/2'),
                                  ('--all', '--shard-report', 'receipt.json')])
def test_retired_shard_modes_cannot_claim_a_full_collection(tmp_path, args):
    root = project(tmp_path)
    result = run(root, *args)
    assert result.returncode == 2
    assert 'unrecognized arguments' in result.stderr
    assert not (root / 'receipt.json').exists()


def test_a_project_selection_filter_cannot_turn_a_complete_check_green(tmp_path):
    root = project(tmp_path)
    config = root / 'pyproject.toml'
    config.write_text(config.read_text() + 'addopts="-k test_values"\n')
    result = run(root, '--all', '--deep')
    assert result.returncode != 0
    assert 'no paths, filters or collection overrides' in result.stdout + result.stderr


def test_a_recursion_override_cannot_hide_an_ordinary_subdirectory(tmp_path):
    root = project(tmp_path)
    (root / 'tests/ordinary_subdir').mkdir()
    (root / 'tests/ordinary_subdir/test_hidden.py').write_text('def test_hidden(): assert False\n')
    config = root / 'pyproject.toml'
    config.write_text(config.read_text() + 'addopts="-o norecursedirs=ordinary_subdir"\n')
    result = run(root, '--all', '--deep')
    assert result.returncode != 0
    assert 'no paths, filters or collection overrides' in result.stdout + result.stderr


def test_an_external_collection_hook_cannot_remove_an_ordinary_item(tmp_path):
    root = project(tmp_path)
    (root / 'tests/conftest.py').write_text('''import pytest
@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items):
    items[:] = [item for item in items if item.nodeid != "tests/test_values.py::test_values[1-True]"]
''')
    result = run(root, '--all', '--deep')
    assert result.returncode != 0
    assert 'another selection changed the full ordinary collection' in result.stdout + result.stderr


def test_partial_ordinary_success_cannot_refresh_or_borrow_a_full_file_baseline(tmp_path):
    from test_plugin import run as ordinary
    root = project(tmp_path)
    full = run(root, '--all', '--deep')
    assert full.returncode == 0, full.stdout + full.stderr
    baseline = metadata(root)
    test = root / 'tests/test_values.py'
    test.write_text(test.read_text().replace('def test_values(x,repeat): assert permit(x) is x',
        'def test_values(x,repeat):\n    assert permit(x) is x\n    assert not (x and repeat == 1)'))
    partial = ordinary(root, 'tests/test_values.py::test_values[0-False]')
    assert partial.returncode == 0, partial.stdout + partial.stderr
    assert metadata(root) == baseline
    rerun = run(root, '--all', '--deep')
    assert rerun.returncode != 0, rerun.stdout + rerun.stderr
    assert 'test_values[1-True]' in rerun.stdout and 'FAILED' in rerun.stdout


def test_real_scenario_driver_file_runs_in_the_complete_check(tmp_path):
    from tests.intent_engine._source_fixture import scenario
    root = project(tmp_path)
    declaration = root / 'tests/intent/permit.py'
    code, intent = scenario(root, 'policy', 'def permit(x):\n    return x\n',
                            declaration.read_text().replace(", anchor='PERMIT'", ''),
                            rule='PERMIT', target='permit', parameters={'x': 'bool'},
                            source_parameters={'x': 'bool'},
                            body='answer=app.permit(x)\nassert type(answer) is bool')
    (root / 'policy.py').write_text(code)
    declaration.write_text(intent)
    result = run(root, '--all', '--deep')
    assert result.returncode == 0, result.stdout + result.stderr
    nodes = attempt(root)['complete_collection']
    node = 'tests/test_native_permit.py::test_permit'
    assert node in nodes['collected_nodeids'] and node in nodes['completed_nodeids']


@pytest.mark.skipif(sys.platform == 'win32', reason='This fixture exercises a POSIX directory symlink alias')
def test_scenario_file_collected_through_an_alias_keeps_its_real_selected_path(tmp_path):
    from tests.intent_engine._source_fixture import scenario
    root = project(tmp_path)
    declaration = root / 'tests/intent/permit.py'
    code, intent = scenario(root, 'policy', 'def permit(x):\n    return x\n',
                            declaration.read_text().replace(", anchor='PERMIT'", ''),
                            rule='PERMIT', target='permit', parameters={'x': 'bool'},
                            source_parameters={'x': 'bool'},
                            body='answer=app.permit(x)\nassert type(answer) is bool')
    cases = root / 'tests/cases'
    cases.mkdir()
    (root / 'tests/test_native_permit.py').rename(cases / 'test_native_permit.py')
    code = code.replace('tests/test_native_permit.py::test_permit', 'tests/cases/test_native_permit.py::test_permit')
    (root / 'policy.py').write_text(code)
    declaration.write_text(intent)
    (root / 'aliased_cases').symlink_to(cases, target_is_directory=True)
    config = root / 'pyproject.toml'
    config.write_text(config.read_text() + 'testpaths=["tests/intent","tests/test_flowguard_intent.py","aliased_cases"]\n')
    result = run(root, '--all', '--deep')
    assert result.returncode == 0, result.stdout + result.stderr
    nodes = attempt(root)['complete_collection']
    node = 'aliased_cases/test_native_permit.py::test_permit'
    assert node in nodes['collected_nodeids'] and node in nodes['completed_nodeids']


def test_a_final_source_failure_is_not_hidden_by_successful_pytest(tmp_path):
    root = project(tmp_path)
    after_pytest = '''def change_source_after_pytest(*args, **kwargs):
    result = original_check(*args, **kwargs)
    from pathlib import Path
    (Path(args[1]) / 'broken.py').write_text("# flowguard: sensor FINAL(x: count) -> answer: bool\\ndef unseen(y: bool) -> bool: return y\\n")
    return result
'''
    injected = 'original_check=cli._run_check_pytest;exec(' + repr(after_pytest) + ');cli._run_check_pytest=change_source_after_pytest'
    result = run(root, '--all', '--deep', inject=injected)
    assert result.returncode == 1, result.stdout + result.stderr
    assert attempt(root)['exit'] == 0, 'the original pytest succeeded before the source check failed'
    assert "broken.py:1: anchor parameters ['x'] != source ['y']" in result.stdout


def test_a_retired_report_flag_cannot_overwrite_or_reuse_an_existing_report(tmp_path):
    root = project(tmp_path)
    report = root / 'previous.json'
    original = b'{"previous":true}\n'
    report.write_bytes(original)
    result = run(root, '--all', '--shard-report', str(report))
    assert result.returncode == 2
    assert 'unrecognized arguments' in result.stderr
    assert report.read_bytes() == original


@pytest.mark.parametrize('defect', ['ordinary_failure', 'early_exit', 'missing_sentinel'])
def test_failures_and_unfinished_complete_attempts_are_never_successful(tmp_path, defect):
    root = project(tmp_path)
    if defect == 'missing_sentinel':
        (root / 'tests/test_flowguard_intent.py').unlink()
    else:
        statement = 'assert False' if defect == 'ordinary_failure' else "__import__('pytest').exit('unfinished', returncode=0)"
        (root / 'tests/test_a_stop.py').write_text('def test_a_stop():\n    ' + statement + '\n')
    result = run(root, '--all', '--deep')
    assert result.returncode != 0, result.stdout + result.stderr
    if defect != 'missing_sentinel':
        checked = attempt(root)
        assert checked['exit'] != 0
        if defect == 'early_exit':
            nodes = checked['complete_collection']
            assert set(nodes['completed_nodeids']) != set(nodes['collected_nodeids'])
            assert checked['errors']
