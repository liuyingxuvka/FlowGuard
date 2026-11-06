"""Real pytest subprocesses exercise collection, missing-plugin and failure-cause controls."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import textwrap
import types

import pytest

from flowguard.intent.tracer import Footprint


@pytest.fixture
def sample(tmp_path):
    (tmp_path / 'src/sample').mkdir(parents=True)
    (tmp_path / 'src/sample/__init__.py').write_text('')
    (tmp_path / 'src/sample/policy.py').write_text('def accept(days):\n    return days <= 3\n')
    (tmp_path / 'tests/intent').mkdir(parents=True)
    (tmp_path / 'tests/intent/decisions.py').write_text(textwrap.dedent('''
        from flowguard.intent import rule, row
        @rule('LIMIT', decides='limit', fields={'days': int}, source='assumed: the known boundary')
        def LIMIT(days):
            return days <= 3
        LIMIT.rows(row(days=4, expect=False, why='fourth-day regression'))
        @LIMIT.home('sample.policy:accept')
        def check(c, fn):
            return fn(c.days)
    '''))
    (tmp_path / 'tests/test_flowguard_intent.py').write_text('def test_flowguard_intent(request):\n    from flowguard.intent.plugin import sentinel\n    sentinel(request.config)\n')
    (tmp_path / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["src"]\n')
    return tmp_path


def run(root, *arguments, plugin=True, env=None):
    # The external development interpreter also has the released 1.x package.
    # Explicitly select the source under test without altering that environment.
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    source = str(Path(__file__).resolve().parents[2])
    return subprocess.run([sys.executable, '-c', bootstrap, source, '-q', *(['-p', 'flowguard.intent.plugin'] if plugin else []), *arguments],
                          cwd=root, capture_output=True, text=True, timeout=60, env=env)


def database(root):
    return sqlite3.connect(root / '.flowguard/cache/map.sqlite')


def test_no_intent_or_marked_guard_does_not_build_a_map_or_inject_child_tracing(tmp_path):
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests/test_plain.py').write_text('''import os, subprocess, sys
def test_plain():
    assert 'FLOWGUARD_TRACE_ROOT' not in os.environ
    subprocess.run([sys.executable, '-c', "import os; assert 'FLOWGUARD_TRACE_ROOT' not in os.environ"], check=True)
''')
    result = run(tmp_path)
    assert result.returncode == 0 and '1 passed' in result.stdout, result.stdout + result.stderr
    assert not (tmp_path / '.flowguard/cache/map.sqlite').exists()


def test_installed_sdk_child_bootstrap_does_not_expose_neighbor_packages_to_no_site_python(tmp_path):
    site = tmp_path / 'installed-site'
    site.mkdir()
    shutil.copytree(Path(__file__).resolve().parents[2] / 'flowguard', site / 'flowguard',
                    ignore=shutil.ignore_patterns('__pycache__'))
    (site / 'flowguard_test_optional_provider.py').write_text('AVAILABLE = True\n')
    project = tmp_path / 'project'
    project.mkdir()
    program = r'''
import json, os, subprocess, sys, types
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from flowguard.intent.plugin import Session
state = Session(types.SimpleNamespace(rootpath=Path(sys.argv[2])))
state.previous_session = None
query = """import importlib.util,json,sys
print(json.dumps(dict(optional=importlib.util.find_spec('flowguard_test_optional_provider') is not None,
                     pytest=importlib.util.find_spec('pytest') is not None,
                     sdk=getattr(sys.modules.get('flowguard'), '__file__', None))))"""
def child(*flags):
    result = subprocess.run([sys.executable, *flags, '-c', query], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)
before = child('-S')
state.import_children()
try:
    during = child('-S')
    normal = child()
finally:
    state.close()
after = child('-S')
print(json.dumps(dict(before=before, during=during, normal=normal, after=after)))
'''
    result = subprocess.run([sys.executable, '-I', '-c', program, str(site), str(project)],
                            cwd=project, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert data['before']['optional'] is False and data['after']['optional'] is False
    assert data['during']['optional'] is False
    assert data['during']['sdk'] is None and data['during']['pytest'] is False
    assert data['normal']['optional'] is False and data['normal']['pytest'] is True
    assert Path(data['normal']['sdk']) == site / 'flowguard/__init__.py'


def test_unmarked_ordinary_test_keeps_its_result_but_has_no_function_ledger(sample):
    (sample / 'tests/test_plain.py').write_text('''import os
from sample.policy import accept
def test_plain():
    assert 'FLOWGUARD_TRACE_ROOT' not in os.environ
    assert accept(4) is False
''')
    result = run(sample)
    assert result.returncode == 0, result.stdout + result.stderr
    with database(sample) as connection:
        assert connection.execute("SELECT outcome FROM reading WHERE test='tests/test_plain.py::test_plain'").fetchone()[0] == 'passed'
        assert connection.execute("SELECT count(*) FROM footprint WHERE test='tests/test_plain.py::test_plain'").fetchone()[0] == 0


def test_recording_selected_tests_preserves_other_facts_and_unrecorded_runs_retire_them(sample):
    (sample / 'tests/test_plain.py').write_text('''from sample.policy import accept
def test_first():
    assert accept(4) is False
def test_second():
    assert accept(2) is True
''')
    assert run(sample, '--flowguard-record-tests').returncode == 0
    with database(sample) as connection:
        original = connection.execute("SELECT node,fp,call_lines FROM footprint WHERE test='tests/test_plain.py::test_second' ORDER BY node").fetchall()
        assert original
        assert connection.execute("SELECT static_group,observed_group FROM trace_test WHERE test='tests/test_plain.py::test_first'").fetchone()
    assert run(sample, '--flowguard-record-tests', '--flowguard-rules=', 'tests/intent',
               'tests/test_flowguard_intent.py', 'tests/test_plain.py::test_first').returncode == 0
    with database(sample) as connection:
        assert connection.execute("SELECT node,fp,call_lines FROM footprint WHERE test='tests/test_plain.py::test_second' ORDER BY node").fetchall() == original
        assert connection.execute("SELECT count(*) FROM footprint WHERE test='tests/test_plain.py::test_first'").fetchone()[0]
    assert run(sample, 'tests/test_plain.py::test_first').returncode == 0
    with database(sample) as connection:
        assert connection.execute("SELECT count(*) FROM footprint WHERE test='tests/test_plain.py::test_first'").fetchone()[0] == 0
        signatures = {row[0] for row in connection.execute('SELECT test FROM trace_test')}
        assert 'tests/test_plain.py::test_first' not in signatures
        assert 'tests/test_plain.py::test_second' in signatures
        assert connection.execute("SELECT node,fp,call_lines FROM footprint WHERE test='tests/test_plain.py::test_second' ORDER BY node").fetchall() == original


def test_a_marked_guard_entering_its_home_only_in_a_python_child_is_real(sample):
    (sample / 'tests/test_child_guard.py').write_text('''import subprocess, sys, pytest
@pytest.mark.rule('LIMIT')
def test_child_guard():
    subprocess.run([sys.executable, '-c', 'from sample.policy import accept; assert accept(4) is False'], check=True)
''')
    result = run(sample)
    assert result.returncode == 0, result.stdout + result.stderr
    with database(sample) as connection:
        assert connection.execute("SELECT count(*) FROM footprint WHERE test='tests/test_child_guard.py::test_child_guard' AND node='sample.policy:accept' AND origin='child'").fetchone()[0] == 1


def test_plain_pytest_executes_declared_items_and_sentinel(sample):
    result = run(sample)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '5 passed' in result.stdout
    with database(sample) as connection:
        attempt = json.loads(connection.execute("SELECT v FROM meta WHERE k='intent_attempt'").fetchone()[0])
        assert attempt['declared'] == attempt['collected'] == 4 and attempt['sentinel'] == 'ok'
        assert connection.execute('SELECT count(*) FROM result').fetchone()[0] == 4


def test_complete_item_summary_reuses_the_real_results_without_executing_homes_again(sample):
    (sample / 'tests/conftest.py').write_text('''import pytest
@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session):
    engine = session.config._flowguard_intent.engine
    def refuse(*args, **kwargs):
        raise AssertionError('session summary reexecuted the decision')
    engine.run_rules = engine.run_home = engine.run_live = engine.witnesses = refuse
''')
    result = run(sample)
    assert result.returncode == 0, result.stdout + result.stderr
    with database(sample) as connection:
        result = json.loads(connection.execute("SELECT payload FROM result WHERE rule='LIMIT' AND item LIKE '%[rules]'").fetchone()[0])
        summary = result['own_contract']
        assert summary['complete'] and summary['homes'] == ['sample.policy:accept']
        assert summary['outcomes'] == [['bool', 'False'], ['bool', 'True']]


def test_an_incomplete_item_summary_does_not_become_a_verified_contract(sample):
    from flowguard.intent.config import load_config
    from flowguard.intent.engine import Engine
    from flowguard.intent.loader import load
    engine = Engine(load(load_config(sample)))
    summary = engine.contract_summary('LIMIT', parts=[])
    assert summary['verdict'] == 'grey' and 'not all declared contract items ran' in summary['reasons']


def test_session_metadata_failure_rolls_back_the_attempt_and_previous_results(sample):
    assert run(sample).returncode == 0
    with database(sample) as connection:
        old_attempt = connection.execute("SELECT v FROM meta WHERE k='intent_attempt'").fetchone()[0]
        old_results = connection.execute('SELECT item,payload,stamp FROM result ORDER BY item').fetchall()
    (sample / 'tests/conftest.py').write_text('''import pytest, sqlite3
@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session):
    import flowguard.intent.plugin as plugin
    def fail(*args):
        raise sqlite3.OperationalError('injected metadata write failure')
    plugin._save_readings = fail
''')
    result = run(sample)
    assert result.returncode != 0 and 'injected metadata write failure' in result.stdout + result.stderr
    with database(sample) as connection:
        assert connection.execute("SELECT v FROM meta WHERE k='intent_attempt'").fetchone()[0] == old_attempt
        assert connection.execute('SELECT item,payload,stamp FROM result ORDER BY item').fetchall() == old_results


def test_fixing_an_early_exit_does_not_leave_an_unclearable_synthetic_failure(sample):
    from flowguard.intent.cli import main
    config = sample / 'pyproject.toml'
    config.write_text(config.read_text() + '[tool.flowguard]\nskip_policy="forbid"\n')
    test = sample / 'tests/test_exit.py'
    test.write_text('''import pytest
@pytest.fixture(autouse=True)
def stop():
    yield
    pytest.exit('stop here', returncode=0)
def test_real():
    pass
''')
    assert main(['--root', str(sample), 'check', '--all']) == 1
    test.write_text('def test_real():\n    pass\n')
    assert main(['--root', str(sample), 'check', '--all']) == 0
    with database(sample) as connection:
        assert '<session>' not in {row[0] for row in connection.execute('SELECT test FROM reading')}


def test_autoload_disabled_missing_plugin_is_a_real_failure(sample):
    # The package explicitly requests this measurement; it is not a test workaround.
    result = run(sample, plugin=False, env=dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'))
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'plugin not loaded: 0 of 4' in result.stdout and 'LIMIT[rules]' in result.stdout
    assert 'skipped' not in result.stdout


def test_missing_plugin_diagnosis_reads_declarations_without_executing_the_project(sample):
    path = sample / 'tests/intent/decisions.py'
    path.write_text(path.read_text() + '\nfrom pathlib import Path\nPath("intent-executed").write_text("unsafe diagnostic")\n')
    result = run(sample, plugin=False)
    assert result.returncode == 1
    assert 'plugin not loaded: 0 of 4' in result.stdout and 'LIMIT[rules]' in result.stdout
    assert not (sample / 'intent-executed').exists()


def test_partial_collection_never_overwrites_a_complete_result(sample):
    assert run(sample).returncode == 0
    with database(sample) as connection:
        original = connection.execute("SELECT v FROM meta WHERE k='intent_collection'").fetchone()[0]
    result = run(sample, '--ignore=tests/intent')
    assert result.returncode == 1 and 'only 0 of 4 intent items' in result.stdout
    with database(sample) as connection:
        assert connection.execute("SELECT v FROM meta WHERE k='intent_collection'").fetchone()[0] == original
        attempt = json.loads(connection.execute("SELECT v FROM meta WHERE k='intent_attempt'").fetchone()[0])
        assert attempt['sentinel'] == 'failed' and len(attempt['missing']) == 4
        assert connection.execute('SELECT count(*) FROM result').fetchone()[0] == 4


def test_an_ordinary_partial_unit_run_does_not_require_the_sentinel(sample):
    assert run(sample).returncode == 0
    with database(sample) as connection:
        original = connection.execute("SELECT v FROM meta WHERE k='intent_collection'").fetchone()[0]
    (sample / 'tests/test_unit.py').write_text('def test_unit():\n    assert True\n')
    result = run(sample, 'tests/test_unit.py')
    assert result.returncode == 0, result.stdout + result.stderr
    with database(sample) as connection:
        assert connection.execute("SELECT v FROM meta WHERE k='intent_collection'").fetchone()[0] == original
        attempt = json.loads(connection.execute("SELECT v FROM meta WHERE k='intent_attempt'").fetchone()[0])
        assert attempt['sentinel'] is None and len(attempt['missing']) == 4
        assert connection.execute('SELECT count(*) FROM result').fetchone()[0] == 4


def test_k_deselection_is_not_mistaken_for_intent_execution(sample):
    result = run(sample, '-k', 'test_flowguard_intent')
    assert result.returncode == 1 and 'only 0 of 4 intent items' in result.stdout


def test_deferred_items_without_cached_results_cannot_pass_sentinel(sample):
    result = run(sample, '--flowguard-rules=unknown')
    assert result.returncode == 1 and 'only 0 of 4 intent items' in result.stdout


def test_deferred_items_with_actual_previous_results_are_reported_as_reused(sample):
    assert run(sample).returncode == 0
    result = run(sample, '--flowguard-rules=')
    assert result.returncode == 0, result.stdout + result.stderr
    with database(sample) as connection:
        attempt = json.loads(connection.execute("SELECT v FROM meta WHERE k='intent_attempt'").fetchone()[0])
        assert attempt['selected'] == 0 and attempt['deferred'] == 4 and not attempt['missing']


def test_intent_filename_matching_python_files_is_collected_once(sample):
    path = sample / 'tests/intent/decisions.py'
    path.rename(path.with_name('test_decisions.py'))
    result = run(sample)
    assert result.returncode == 0 and '5 passed' in result.stdout, result.stdout + result.stderr


def test_explicit_nonmatching_intent_filename_is_collected_once(sample):
    result = run(sample, 'tests/intent/decisions.py', 'tests/test_flowguard_intent.py')
    assert result.returncode == 0 and '5 passed' in result.stdout, result.stdout + result.stderr
    collected = run(sample, '--collect-only', 'tests/intent/decisions.py::LIMIT[rules]')
    assert collected.returncode == 0 and '1 test collected' in collected.stdout
    assert collected.stdout.count('tests/intent/decisions.py::LIMIT[rules]') == 1


def test_load_failure_is_visible_as_a_failing_item(sample):
    (sample / 'tests/intent/decisions.py').write_text('from definitely_missing_intent_helper import value\n')
    result = run(sample)
    assert result.returncode == 1
    assert 'tests/intent/decisions.py::load' in result.stdout and 'definitely_missing_intent_helper' in result.stdout


@pytest.mark.parametrize('body,kind,reason', [
    ("raise ValueError('a domain error')", 'code', ''),
    ("import no_such_external_dependency_r14", 'env', 'missing package'),
    ("open('/outside-project-missing-r14/file.txt')", 'env', 'FileNotFoundError'),
    ("open('project-missing-r14.txt')", 'code', 'project FileNotFoundError'),
    ("raise PermissionError(13, 'denied', 'project-denied.txt')", 'code', 'project PermissionError'),
    ("raise PermissionError(13, 'denied', '/outside-project-r14/denied.txt')", 'env', 'PermissionError'),
    ("raise TimeoutError('deadline')", 'env', 'timeout'),
])
def test_direct_failure_classification_preserves_pytest_failure(sample, body, kind, reason):
    (sample / 'src/sample/failure.py').write_text('def fail():\n    ' + body + '\n')
    (sample / 'tests/test_failure.py').write_text('from sample.failure import fail\ndef test_failure():\n    fail()\n')
    result = run(sample)
    assert result.returncode == 1, result.stdout + result.stderr
    with database(sample) as connection:
        row = connection.execute("SELECT outcome,kind,reason FROM reading WHERE test='tests/test_failure.py::test_failure'").fetchone()
        assert row[0] == 'failed' and row[1] == kind and reason in row[2]


@pytest.mark.parametrize('code,kind', [
    ('import no_such_external_child_dependency_r14', 'env'),
    ('import sample.missing_project_module_r14', 'code'),
    ("open('/outside-project-child-r14/missing.txt')", 'env'),
    ("raise ValueError('a child domain error')", 'code'),
])
def test_failed_python_child_is_classified_from_its_actual_exception(sample, code, kind):
    text = f'''import subprocess, sys
def test_child():
    result = subprocess.run([sys.executable, '-c', {code!r}], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
'''
    (sample / 'tests/test_child.py').write_text(text)
    result = run(sample)
    assert result.returncode == 1, result.stdout + result.stderr
    with database(sample) as connection:
        assert connection.execute("SELECT kind FROM reading WHERE test='tests/test_child.py::test_child'").fetchone()[0] == kind


def test_child_path_classification_reads_the_error_line_not_a_later_repr(sample):
    from flowguard.intent.config import load_config
    from flowguard.intent.readings import child_failure
    text = '''E       AssertionError: Traceback (most recent call last):
E           File "<string>", line 1, in <module>
E         FileNotFoundError: [Errno 2] No such file or directory: '/outside-project/missing.txt'
E       assert 1 == 0
E        + where 1 = CompletedProcess(args=['python'], stderr='some repr')
'''
    assert child_failure(text, load_config(sample)) == ('env', 'child os error outside project')
    assert child_failure("print('FileNotFoundError: outside')", load_config(sample)) is None


def test_child_functions_and_edges_have_the_map_owners_fingerprint(sample):
    (sample / 'src/sample/failure.py').write_text('def leaf(): return 7\ndef caller(): return leaf()\n')
    (sample / 'tests/test_child.py').write_text('import subprocess, sys, pytest\nfrom sample.policy import accept\n@pytest.mark.rule("LIMIT")\ndef test_child():\n    assert accept(4) is False\n    subprocess.run([sys.executable,"-c","from sample.failure import caller; assert caller()==7"],check=True)\n')
    result = run(sample)
    assert result.returncode == 0, result.stdout + result.stderr
    with database(sample) as connection:
        footprints = dict(connection.execute("SELECT node,fp FROM footprint WHERE test='tests/test_child.py::test_child' AND origin='child'"))
        for name in ('sample.failure:caller', 'sample.failure:leaf'):
            assert footprints[name] == connection.execute('SELECT fp FROM node WHERE id=?', (name,)).fetchone()[0]
        assert footprints['sample.failure'] == connection.execute("SELECT fp FROM node WHERE id='sample.failure'").fetchone()[0]
        lines = json.loads(connection.execute("SELECT call_lines FROM footprint WHERE node='sample.failure:leaf' AND origin='child'").fetchone()[0])
        assert ['src/sample/failure.py', 2] in lines
        assert connection.execute("SELECT count(*) FROM edge WHERE src='sample.failure:caller' AND dst='sample.failure:leaf' AND prov='observed'").fetchone()[0] == 1


@pytest.mark.parametrize('calls_home', [True, False])
def test_rule_marker_requires_entering_a_real_home(sample, calls_home):
    text = 'import pytest\nfrom sample.policy import accept\n@pytest.mark.rule("LIMIT")\ndef test_marked():\n    ' + ('assert accept(4) is False' if calls_home else 'assert True') + '\n'
    (sample / 'tests/test_marked.py').write_text(text)
    result = run(sample)
    assert result.returncode == (0 if calls_home else 1), result.stdout + result.stderr
    assert ('marked but never enters LIMIT' in result.stdout) is not calls_home
    if calls_home:
        with database(sample) as connection:
            lines = json.loads(connection.execute("SELECT call_lines FROM footprint WHERE test='tests/test_marked.py::test_marked' AND node='sample.policy:accept'").fetchone()[0])
            assert ['tests/test_marked.py', 5] in lines


def test_collection_failure_is_an_environment_reading(sample):
    (sample / 'tests/test_missing.py').write_text('import missing_test_collection_dependency_r14\n')
    result = run(sample)
    assert result.returncode == 2, result.stdout + result.stderr
    with database(sample) as connection:
        assert connection.execute("SELECT kind,reason FROM reading WHERE test='tests/test_missing.py'").fetchone() == ('env', 'collection')


def test_comprehension_is_covered_by_its_named_owner_and_nested_functions_survive(sample):
    source = sample / 'src/sample/comps.py'
    source.write_text('def outer(value):\n    def inner(item):\n        return item\n    return all(inner(v) <= 3 for v in [value])\n')
    (sample / 'tests/test_comp.py').write_text('import pytest\nfrom sample.policy import accept\nfrom sample.comps import outer\n@pytest.mark.rule("LIMIT")\ndef test_comp():\n    assert accept(4) is False\n    assert outer(1)\n')
    result = run(sample)
    assert result.returncode == 0, result.stdout + result.stderr
    with database(sample) as connection:
        previous = connection.execute("SELECT fp FROM node WHERE id='sample.comps:outer'").fetchone()[0]
        entries = dict(connection.execute("SELECT node,fp FROM footprint WHERE test='tests/test_comp.py::test_comp'"))
        assert entries['sample.comps:outer'] == previous
        assert entries['sample.comps:outer.inner']
        assert not any('<genexpr>' in node for node in entries)
        assert connection.execute("SELECT count(*) FROM edge WHERE src='sample.comps:outer' AND dst='sample.comps:outer.inner' AND prov='observed'").fetchone()[0] == 1
    source.write_text(source.read_text().replace('<= 3', '<= 4'))
    result = run(sample)
    assert result.returncode == 0, result.stdout + result.stderr
    with database(sample) as connection:
        current = connection.execute("SELECT fp FROM node WHERE id='sample.comps:outer'").fetchone()[0]
        assert current != previous
        assert connection.execute("SELECT fp FROM footprint WHERE test='tests/test_comp.py::test_comp' AND node='sample.comps:outer'").fetchone()[0] == current


def test_nested_footprints_keep_their_own_project_scope(tmp_path):
    first, second = tmp_path / 'first.py', tmp_path / 'second.py'
    first.write_text('def owner(): return 1\n')
    second.write_text('def owner(): return 2\n')
    modules = []
    for path in (first, second):
        module = types.ModuleType(path.stem)
        exec(compile(path.read_text(), str(path), 'exec'), module.__dict__)
        modules.append(module)
    with Footprint(lambda path: path == str(first)) as outer:
        assert modules[0].owner() == 1
        with Footprint(lambda path: path == str(second)) as inner:
            assert modules[1].owner() == 2
            assert modules[0].owner() == 1
    assert {row[0] for row in outer.entered} == {str(first)}
    assert {row[0] for row in inner.entered} == {str(second)}


def test_entering_a_nested_scope_does_not_credit_the_tracer_refresh(tmp_path):
    from flowguard.intent import tracer
    path = tmp_path / 'subject.py'
    path.write_text('def owner(): return 2\n')
    module = types.ModuleType('subject')
    exec(compile(path.read_text(), str(path), 'exec'), module.__dict__)
    with Footprint(lambda filename: filename == tracer.__file__):
        with Footprint(lambda filename: filename == str(path)) as subject:
            assert module.owner() == 2
    assert {entry[0] for entry in subject.entered} == {str(path)}


@pytest.mark.parametrize('throw', [False, True])
def test_resuming_an_existing_generator_is_a_real_function_entry(tmp_path, throw):
    path = tmp_path / 'stream.py'
    source = 'def stream():\n    try:\n        yield 0\n        yield 1\n    except ValueError:\n        yield 2\n'
    module = types.ModuleType('sample_stream')
    exec(compile(source, str(path), 'exec'), module.__dict__)
    generator = module.stream()
    assert next(generator) == 0
    with Footprint(lambda filename: filename == str(path)) as footprint:
        assert (generator.throw(ValueError()) if throw else next(generator)) == (2 if throw else 1)
    assert (str(path), 1, 'stream') in footprint.entered


@pytest.mark.parametrize('marker,body,expected,summary', [
    ('@pytest.mark.skipif(True,reason="platform")', 'assert False', 0, '1 skipped'),
    ('@pytest.mark.skipif("True",reason="platform")', 'assert False', 0, '1 skipped'),
    ('@pytest.mark.skipif(False,reason="platform")', 'pytest.skip("hidden")', 1, 'effective skipif/xfail'),
    ('@pytest.mark.skipif("False",reason="platform")', 'pytest.skip("hidden")', 1, 'effective skipif/xfail'),
    ('@pytest.mark.xfail(True,reason="known defect")', 'assert False', 0, '1 xfailed'),
    ('@pytest.mark.xfail(False,reason="inactive")', 'pytest.xfail("hidden")', 1, 'effective skipif/xfail'),
])
def test_only_effective_declared_skip_conditions_are_preserved(sample, marker, body, expected, summary):
    (sample / 'tests/test_skip.py').write_text('import pytest\n' + marker + '\ndef test_skip():\n    ' + body + '\n')
    result = run(sample)
    assert result.returncode == expected and summary in result.stdout, result.stdout + result.stderr


def test_a_swallowed_error_skip_prints_the_original_cause(sample):
    (sample / 'tests/test_skip.py').write_text('import pytest\ndef test_skip():\n    try:\n        raise ValueError("broken source record")\n    except ValueError:\n        getattr(pytest,"skip")("hidden")\n')
    result = run(sample)
    assert result.returncode == 1
    assert 'while handling ValueError: broken source record' in result.stdout


def test_importorskip_during_collection_is_a_real_failure(sample):
    (sample / 'tests/test_skip.py').write_text('import pytest\npytest.importorskip("missing_collection_skip_r14")\n')
    result = run(sample)
    assert result.returncode == 2 and 'collection skip' in result.stdout, result.stdout + result.stderr


def test_existing_python_and_c_profilers_are_preserved(tmp_path):
    path = tmp_path / 'profiled.py'
    path.write_text('def owner(): return 7\n')
    script = '''import cProfile,sys,types
sys.path.insert(0,sys.argv[1])
from flowguard.intent.tracer import Footprint
path=sys.argv[2]
module=types.ModuleType('profiled')
exec(compile('def owner(): return 7\\n',path,'exec'),module.__dict__)
events=[]
def previous(frame,event,arg):
    if frame.f_code.co_filename==path and event=='call': events.append(frame.f_code.co_name)
sys.setprofile(previous)
with Footprint(lambda filename:filename==path) as footprint:
    assert module.owner()==7
assert sys.getprofile() is previous
sys.setprofile(None)
assert events==['owner'] and (path,1,'owner') in footprint.entered
profiler=cProfile.Profile()
profiler.enable()
original=sys.getprofile()
try:
    with Footprint(lambda filename:filename==path) as footprint:
        assert module.owner()==7
    assert sys.getprofile() is original
finally:
    profiler.disable()
assert (path,1,'owner') in footprint.entered
print('both profilers preserved')
'''
    # A fresh stdlib-only process isolates the pre-existing profiler from the
    # outer pytest run's own observer. No version or outcome is substituted.
    result = subprocess.run([sys.executable, '-S', '-c', script, str(Path(__file__).resolve().parents[2]), str(path)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and 'both profilers preserved' in result.stdout, result.stdout + result.stderr


@pytest.mark.parametrize('text,reason', [('def broken(:\n    pass\n', 'SyntaxError'),
                                      ('assert False, "invalid module invariant"\n', 'AssertionError')])
def test_explicit_collection_code_defects_are_not_environment_failures(sample, text, reason):
    (sample / 'tests/test_broken.py').write_text(text)
    result = run(sample)
    assert result.returncode == 2, result.stdout + result.stderr
    with database(sample) as connection:
        kind, message = connection.execute("SELECT kind,reason FROM reading WHERE test='tests/test_broken.py'").fetchone()
        assert kind == 'code' and reason in message


@pytest.mark.parametrize('value,exit_code', [('open', 0), ('held', 1)])
def test_state_literal_item_is_collected_and_checked(sample, value, exit_code):
    (sample / 'src/sample/models.py').write_text(f'class Hire:\n    def __init__(self):\n        self.status={value!r}\n')
    (sample / 'tests/intent/states.py').write_text('from flowguard.intent import states\nstates("sample.models:Hire.status",["open","returned"],source="assumed: available states")\n')
    result = run(sample)
    assert result.returncode == exit_code, result.stdout + result.stderr
    with database(sample) as connection:
        row = connection.execute("SELECT verdict,payload FROM result WHERE item LIKE '%[states]'").fetchone()
        assert row is not None and (row[0] == 'red') is (exit_code == 1)


@pytest.mark.parametrize('allow_handler', [False, True])
def test_structure_item_keeps_an_explicit_reason_for_each_allowed_handler(sample, allow_handler):
    (sample / 'src/sample/handler.py').write_text('def parse(value):\n    try:\n        return int(value)\n    except ValueError:\n        return None\n')
    text = '''from flowguard.intent import structure_rule, allow
@structure_rule('HANDLERS',source='assumed: exceptions need a reason')
def HANDLERS(graph):
    return [h for h in graph.handlers() if h['file']=='src/sample/handler.py']
'''
    if allow_handler:
        text += 'HANDLERS.allows(allow("src/sample/handler.py:4","invalid input is an optional value here"))\n'
    (sample / 'tests/intent/structure.py').write_text(text)
    result = run(sample)
    assert result.returncode == (0 if allow_handler else 1), result.stdout + result.stderr
    with database(sample) as connection:
        row = connection.execute("SELECT verdict,payload FROM result WHERE rule='HANDLERS'").fetchone()
        assert row is not None and (row[0] == 'red') is not allow_handler
