"""Full collection is partitioned without lending partial runs whole-file trust."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest

from flowguard.intent.config import load_config
from flowguard.intent.plugin import parse_shard, _shard_items


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


def test_three_shards_cover_the_real_full_run_without_refreshing_partial_parameter_files(tmp_path):
    root = project(tmp_path)
    full = run(root, '--all')
    assert full.returncode == 0, full.stdout + full.stderr
    baseline = metadata(root)
    receipts = []
    for index in range(1, 4):
        report = root / f'part-{index}.json'
        result = run(root, '--all', '--shard', f'{index}/3', '--shard-report', str(report))
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'partial ordinary tests' in result.stdout
        receipt = json.loads(report.read_text())
        assert receipt['exit'] == receipt['pytest_exit'] == 0
        assert receipt['sentinel'] == 'ok'
        assert set(receipt['selected_nodeids']) == set(receipt['completed_nodeids'])
        assert receipt['intent']['declared_nodeids'] == receipt['intent']['selected_nodeids'] == receipt['intent']['completed_nodeids']
        assert receipt['interpreter']['prefix'] != str(root)
        assert metadata(root) == baseline
        receipts.append(receipt)
    universe = set(receipts[0]['collected_nodeids'])
    common = set(receipts[0]['common_nodeids'])
    partitions = [set(receipt['partition_nodeids']) for receipt in receipts]
    assert all(set(r['collected_nodeids']) == universe and set(r['common_nodeids']) == common for r in receipts)
    assert all(not (left & right) for number, left in enumerate(partitions) for right in partitions[number + 1:])
    assert set.union(*partitions) == universe - common
    assert all(set(r['selected_nodeids']) == common | part for r, part in zip(receipts, partitions))
    assert any('test_values[' in node for node in universe)


@pytest.mark.parametrize('value', ['0/3', '4/3', '1/0', '-1/3', '1', '1/2/3', 'x/3', '１/3'])
def test_invalid_shards_are_not_silently_empty(value):
    with pytest.raises(ValueError, match='1 <= k <= n'):
        parse_shard(value)


@pytest.mark.parametrize('args', [('--shard', '1/2'), ('--all', '--since', 'HEAD', '--shard', '1/2'),
                                  ('--all', '--shard-report', 'receipt.json')])
def test_cli_rejects_shard_modes_that_cannot_mean_a_full_collection(tmp_path, args):
    project(tmp_path)
    result = run(tmp_path, *args)
    assert result.returncode == 2
    assert 'requires' in result.stderr


def test_a_project_selection_filter_cannot_turn_a_shard_green(tmp_path):
    root = project(tmp_path)
    config = root / 'pyproject.toml'
    config.write_text(config.read_text() + 'addopts="-k test_values"\n')
    result = run(root, '--all', '--shard', '1/2', '--shard-report', str(root / 'result.json'))
    assert result.returncode != 0
    assert 'no paths, filters or collection overrides' in result.stdout + result.stderr
    assert not (root / 'result.json').exists()


def test_a_recursion_override_cannot_hide_an_ordinary_subdirectory(tmp_path):
    root = project(tmp_path)
    (root / 'tests/ordinary_subdir').mkdir()
    (root / 'tests/ordinary_subdir/test_hidden.py').write_text('def test_hidden(): assert False\n')
    config = root / 'pyproject.toml'
    config.write_text(config.read_text() + 'addopts="-o norecursedirs=ordinary_subdir"\n')
    result = run(root, '--all', '--shard', '1/2')
    assert result.returncode != 0
    assert 'no paths, filters or collection overrides' in result.stdout + result.stderr


def test_real_scenario_driver_file_runs_in_every_shard(tmp_path):
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
    for index in range(1, 4):
        report = root / f'scenario-{index}.json'
        result = run(root, '--all', '--shard', f'{index}/3', '--shard-report', str(report))
        assert result.returncode == 0, result.stdout + result.stderr
        receipt = json.loads(report.read_text())
        node = 'tests/test_native_permit.py::test_permit'
        assert node in receipt['common_nodeids']
        assert node in receipt['completed_nodeids']


@pytest.mark.skipif(sys.platform == 'win32', reason='This fixture exercises a POSIX directory symlink alias')
def test_scenario_file_collected_through_an_alias_stays_common(tmp_path):
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
    for index in range(1, 4):
        report = root / f'alias-{index}.json'
        result = run(root, '--all', '--shard', f'{index}/3', '--shard-report', str(report))
        assert result.returncode == 0, result.stdout + result.stderr
        receipt = json.loads(report.read_text())
        node = 'aliased_cases/test_native_permit.py::test_permit'
        assert node in receipt['collected_nodeids']
        assert node in receipt['common_nodeids']
        assert node in receipt['completed_nodeids']


def test_report_keeps_a_real_final_source_failure_after_pytest_passes(tmp_path):
    root = project(tmp_path)
    report = root / 'final-red.json'
    result = run(root, '--all', '--shard', '1/2', '--shard-report', str(report),
                 inject='cli._check_sources=lambda cfg: True')
    assert result.returncode == 1, result.stdout + result.stderr
    receipt = json.loads(report.read_text())
    assert receipt['pytest_exit'] == 0
    assert receipt['exit'] == 1


def test_an_existing_report_is_not_overwritten_or_reused(tmp_path):
    root = project(tmp_path)
    report = root / 'previous.json'
    original = b'{"previous":true}\n'
    report.write_bytes(original)
    result = run(root, '--all', '--shard', '1/2', '--shard-report', str(report))
    assert result.returncode == 2
    assert 'already exists' in result.stderr
    assert report.read_bytes() == original


@pytest.mark.parametrize('defect', ['ordinary_failure', 'early_exit', 'missing_sentinel'])
def test_shard_failures_and_unfinished_attempts_are_never_successful(tmp_path, defect):
    root = project(tmp_path)
    if defect == 'missing_sentinel':
        (root / 'tests/test_flowguard_intent.py').unlink()
    else:
        statement = 'assert False' if defect == 'ordinary_failure' else "__import__('pytest').exit('unfinished', returncode=0)"
        (root / 'tests/test_a_stop.py').write_text('def test_a_stop():\n    ' + statement + '\n')
    report = root / 'result.json'
    result = run(root, '--all', '--shard', '1/2', '--shard-report', str(report))
    assert result.returncode != 0, result.stdout + result.stderr
    if report.exists():
        assert json.loads(report.read_text())['exit'] != 0


def test_common_scenarios_come_from_bindings_and_model_test_anchors(tmp_path):
    nodes = ['tests/test_a.py::test_a', 'tests/test_b.py::test_b', 'tests/test_c.py::test_c',
             'tests/test_extra.py::test_extra', 'tests/test_flowguard_intent.py::test_flowguard_intent']
    items = [SimpleNamespace(nodeid=node, name=node.split('::')[-1], path=tmp_path / node.partition('::')[0]) for node in nodes]
    model = SimpleNamespace(
        rules={'R': SimpleNamespace(homes=[SimpleNamespace(testnode='tests/test_a.py::test_a')])},
        flows={'F': SimpleNamespace(nodes=[SimpleNamespace(reference='CASE'), SimpleNamespace(reference='SENSOR')])},
        anchor_index=SimpleNamespace(entries=[
            SimpleNamespace(name='CASE', source_role='test', file='tests/test_b.py', calibrated_by=''),
            SimpleNamespace(name='SENSOR', source_role='production', file='app.py', calibrated_by='tests/test_c.py::test_c')]))
    config = SimpleNamespace(option=SimpleNamespace(override_ini=[]), args_source=SimpleNamespace(name='TESTPATHS'),
                             getoption=lambda name: True if name == '--flowguard-record-tests' else None,
                             hook=SimpleNamespace(pytest_deselected=lambda **kw: None))
    state = SimpleNamespace(cfg=load_config(tmp_path), ordinary_deselected=False, get_model=lambda: model)
    _shard_items(config, state, items, '2/2')
    assert set(state.shard['common_nodeids']) == set(nodes) - {'tests/test_extra.py::test_extra'}
    assert state.shard['partition_nodeids'] == []
    assert state.ordinary_deselected
