"""Actual ordinary checks distinguish code-only reuse from ambient inputs."""
from contextlib import closing
from pathlib import Path
import sqlite3

import pytest

from tests.intent_engine import _cli_fixture as cli_fixture

from flowguard.intent import cache, cli, deps
from flowguard.structure import build
from test_cli import project
from test_cli_incremental import calls
from test_plugin import run


def sample(tmp_path, owner, assertion='value() == "old"'):
    root, cfg = project(tmp_path)
    (root / 'owner.py').write_text(owner)
    (root / 'tests/test_ordinary.py').write_text('from owner import value\ndef test_value(): assert ' + assertion + '\n')
    cli.init(cfg)
    return root, cfg


def record(cfg):
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        return deps.test_dependencies(cfg, graph)['tests/test_ordinary.py']


def test_default_inventory_and_old_red_do_not_promote_a_production_testfile_api(tmp_path, monkeypatch, capsys):
    root, cfg = project(tmp_path)
    config = root / 'pyproject.toml'
    config.write_text(config.read_text() + '\n[tool.pytest.ini_options]\ntestpaths=["tests"]\n')
    api = root / 'src/production/test_file_contract.py'
    api.parent.mkdir(parents=True)
    api.write_text('def testfile_snapshot(path): return path\ndef testfile_series(path): return path\n')
    (root / 'tests/test_plain.py').write_text('def test_plain(): assert True\n')
    cli.init(cfg)
    assert cli_fixture.check(cfg, everything=True) == 0
    # A genuinely requested explicit pytest can have failed outside the default
    # scope. Preserve that history without promoting it into default check.
    explicit = run(root, str(api))
    assert explicit.returncode == 1 and "fixture 'path' not found" in explicit.stdout
    observed = calls(monkeypatch)
    assert cli_fixture.check(cfg) == 0
    assert not any(str(api.relative_to(root)) in command for command in observed)
    assert not deps.test_scope(cfg)('src/production/test_file_contract.py')


@pytest.mark.parametrize('suffix', ['ts', 'cpp', 'cs'])
def test_default_pytest_scope_does_not_promote_foreign_test_named_files(tmp_path, suffix):
    root, cfg = project(tmp_path)
    path = root / ('tests/test_foreign.' + suffix)
    path.write_text('foreign syntax is not a Python pytest module\n')
    assert not deps.test_scope(cfg)(path.relative_to(root).as_posix())


def test_an_unused_dynamic_sibling_does_not_prevent_pure_test_reuse(tmp_path, monkeypatch):
    root, cfg = sample(tmp_path, 'from pathlib import Path\ndef value(): return "old"\ndef unused(path): return Path(path).read_text()\n')
    assert cli_fixture.check(cfg) == 0
    assert '<unresolved>' in record(cfg)  # File-grained closure includes the dynamic sibling.
    observed = calls(monkeypatch)
    assert cli_fixture.check(cfg) == 0 and observed
    (root / 'owner.py').write_text((root / 'owner.py').read_text().replace('return "old"', 'return "new"'))
    assert cli_fixture.check(cfg) == 1
    assert any('tests/test_ordinary.py' in command for command in observed)


@pytest.mark.parametrize('reading', ['read_text', 'open'])
def test_literal_project_data_is_content_tracked_including_path_open(tmp_path, monkeypatch, reading):
    expression = 'path.read_text()' if reading == 'read_text' else 'path.open().read()'
    root, cfg = sample(tmp_path, f'from pathlib import Path\ndef value():\n    path = Path(__file__).parent / "data.txt"\n    return {expression}\n')
    (root / 'data.txt').write_text('old')
    assert cli_fixture.check(cfg) == 0
    saved = record(cfg)
    assert '<unresolved>' in saved and 'data.txt' in saved
    observed = calls(monkeypatch)
    assert cli_fixture.check(cfg) == 0 and observed
    (root / 'data.txt').write_text('new')
    assert cli_fixture.check(cfg) == 1 and observed


@pytest.mark.parametrize('expression', ['os.environ["FG_TEST_INPUT"]', 'os.getenv("FG_TEST_INPUT")'])
def test_environment_reads_never_silently_reuse_a_past_success(tmp_path, monkeypatch, expression):
    root, cfg = sample(tmp_path, 'import os\ndef value(): return ' + expression + '\n')
    monkeypatch.setenv('FG_TEST_INPUT', 'old')
    assert cli_fixture.check(cfg) == 0 and '<unresolved>' in record(cfg)
    observed = calls(monkeypatch)
    monkeypatch.setenv('FG_TEST_INPUT', 'new')
    assert cli_fixture.check(cfg) == 1 and observed


@pytest.mark.parametrize('style', ['environment', 'literal'])
def test_external_path_open_remains_unknown_when_only_the_input_changes(tmp_path, monkeypatch, style):
    outside = tmp_path / 'outside.txt'
    outside.write_text('old')
    monkeypatch.setenv('FG_TEST_INPUT', str(outside))
    path = 'os.environ["FG_TEST_INPUT"]' if style == 'environment' else repr(str(outside))
    root, cfg = sample(tmp_path, 'import os\nfrom pathlib import Path\ndef value(): return Path(' + path + ').open().read()\n')
    assert cli_fixture.check(cfg) == 0 and '<unresolved>' in record(cfg)
    outside.write_text('new')
    assert cli_fixture.check(cfg) == 1


def test_uncalled_function_defaults_still_run_during_import(tmp_path, monkeypatch):
    outside = tmp_path / 'outside.txt'
    outside.write_text('present')
    monkeypatch.setenv('FG_TEST_INPUT', str(outside))
    root, cfg = sample(tmp_path, 'import os\nfrom pathlib import Path\ndef unused(value=Path(os.environ["FG_TEST_INPUT"]).read_text()): return value\ndef value(): return "old"\n')
    assert cli_fixture.check(cfg) == 0 and '<unresolved>' in record(cfg)
    outside.unlink()
    assert cli_fixture.check(cfg) != 0
    assert 'FileNotFoundError' in (cfg.cache / 'check-output.txt').read_text()


def test_used_fixture_bodies_are_included_but_plain_conftest_helpers_are_not(tmp_path, monkeypatch):
    root, cfg = sample(tmp_path, 'def value(): return "old"\n')
    conftest = root / 'tests/conftest.py'
    conftest.write_text(conftest.read_text() + '''
import os, pytest
from pathlib import Path
def unused_cli(): return Path(os.environ['UNUSED']).read_text()
@pytest.fixture
def supplied(): return os.environ['FG_TEST_INPUT']
''')
    (root / 'tests/test_ordinary.py').write_text('def test_value(supplied): assert supplied == "old"\n')
    monkeypatch.setenv('FG_TEST_INPUT', 'old')
    assert cli_fixture.check(cfg) == 0
    saved = record(cfg)
    assert '<unresolved>' in saved
    assert not any('unused_cli' in reason for reason in saved['<unresolved>'])
    monkeypatch.setenv('FG_TEST_INPUT', 'new')
    assert cli_fixture.check(cfg) == 1


def test_resolved_literal_dynamic_import_uses_the_same_dependency_owner(tmp_path, monkeypatch):
    root, cfg = sample(tmp_path, 'import importlib\ndef value():\n    module = importlib.import_module("native_owner")\n    return module.value()\n')
    (root / 'native_owner.py').write_text('def value(): return "old"\n')
    assert cli_fixture.check(cfg) == 0 and '<unresolved>' in record(cfg)
    observed = calls(monkeypatch)
    assert cli_fixture.check(cfg) == 0 and observed
    (root / 'native_owner.py').write_text('def value(): return "new"\n')
    assert cli_fixture.check(cfg) == 1 and observed


def test_unresolved_callback_is_not_silently_treated_as_pure(tmp_path):
    root, cfg = sample(tmp_path, 'def choose(fn): return fn()\ndef value(): return choose(lambda: "old")\n')
    assert cli_fixture.check(cfg) == 0 and '<unresolved>' in record(cfg)


def test_transitive_fixture_dependency_is_not_lost_by_definition_order(tmp_path, monkeypatch):
    root, cfg = sample(tmp_path, 'def value(): return "old"\n')
    conftest = root / 'tests/conftest.py'
    conftest.write_text(conftest.read_text() + '''
import os, pytest
@pytest.fixture
def base(): return os.environ['FG_TEST_INPUT']
@pytest.fixture
def supplied(base): return base
''')
    (root / 'tests/test_ordinary.py').write_text('def test_value(supplied): assert supplied == "old"\n')
    monkeypatch.setenv('FG_TEST_INPUT', 'old')
    assert cli_fixture.check(cfg) == 0 and '<unresolved>' in record(cfg)
    monkeypatch.setenv('FG_TEST_INPUT', 'new')
    assert cli_fixture.check(cfg) == 1


def test_ambiguous_path_assignment_keeps_the_real_input_boundary(tmp_path):
    root, cfg = sample(tmp_path, '''from pathlib import Path
def value():
    path = Path(__file__).parent / 'first.txt'
    if False:
        path = Path(__file__).parent / 'second.txt'
    return path.read_text()
''')
    (root / 'first.txt').write_text('old')
    (root / 'second.txt').write_text('other')
    assert cli_fixture.check(cfg) == 0 and '<unresolved>' in record(cfg)
    (root / 'first.txt').write_text('new')
    assert cli_fixture.check(cfg) == 1


def test_wildcard_import_cannot_hide_an_ambient_dependency(tmp_path, monkeypatch):
    root, cfg = sample(tmp_path, 'import os\ndef value(): return os.getenv("FG_TEST_INPUT")\n')
    (root / 'tests/test_ordinary.py').write_text('from owner import *\ndef test_value(): assert value() == "old"\n')
    monkeypatch.setenv('FG_TEST_INPUT', 'old')
    assert cli_fixture.check(cfg) == 0 and '<unresolved>' in record(cfg)
    monkeypatch.setenv('FG_TEST_INPUT', 'new')
    assert cli_fixture.check(cfg) == 1


@pytest.mark.parametrize('kind', ['function', 'parameter'])
def test_successful_complete_file_collection_retires_only_obsolete_failed_nodeids(tmp_path, monkeypatch, kind):
    root, cfg = sample(tmp_path, 'def value(): return "old"\n')
    test = root / 'tests/test_ordinary.py'
    if kind == 'function':
        test.write_text('from owner import value\ndef test_old(): assert value() == "wrong"\n')
        obsolete = 'tests/test_ordinary.py::test_old'
        replacement = 'from owner import value\ndef test_new(): assert value() == "old"\n'
    else:
        test.write_text('import pytest\nfrom owner import value\n@pytest.mark.parametrize("expected", [pytest.param("wrong",id="old")])\ndef test_value(expected): assert value() == expected\n')
        obsolete = 'tests/test_ordinary.py::test_value[old]'
        replacement = 'import pytest\nfrom owner import value\n@pytest.mark.parametrize("expected", [pytest.param("old",id="new")])\ndef test_value(expected): assert value() == expected\n'
    assert cli_fixture.check(cfg, everything=True) == 1
    assert cache.read(cfg)['tests'][obsolete]['outcome'] == 'failed'
    test.write_text(replacement)
    assert cli_fixture.check(cfg, everything=True) == 0
    assert obsolete not in cache.read(cfg)['tests']
    with sqlite3.connect(cfg.cache / 'map.sqlite') as con:
        assert con.execute('SELECT outcome FROM reading WHERE test=?', (obsolete,)).fetchone()[0] == 'failed'
    observed = calls(monkeypatch)
    assert cli_fixture.check(cfg) == 0
    if kind == 'parameter':
        # The original pytest.param input is unchanged. Its third-party import
        # and execution are opaque under N1; collection retirement still works.
        assert '<unresolved>' in record(cfg) and observed
    else:
        assert observed == []


def test_partial_success_does_not_hide_a_newer_partial_failure(tmp_path):
    root, cfg = sample(tmp_path, 'def value(): return "old"\n')
    test = root / 'tests/test_ordinary.py'
    test.write_text('def test_a(): assert True\ndef test_b(): assert True\n')
    assert cli_fixture.check(cfg, everything=True) == 0
    before = cache.read(cfg)['test_collection']
    test.write_text(test.read_text() + 'def test_new(): assert False\n')
    assert run(root, 'tests/test_ordinary.py::test_new').returncode == 1
    assert run(root, 'tests/test_ordinary.py::test_a').returncode == 0
    data = cache.read(cfg)
    assert data['test_collection'] == before
    assert data['tests']['tests/test_ordinary.py::test_new']['outcome'] == 'failed'


def test_failed_collection_preserves_last_complete_nodes_and_current_error(tmp_path):
    root, cfg = sample(tmp_path, 'def value(): return "old"\n')
    assert cli_fixture.check(cfg, everything=True) == 0
    before = cache.read(cfg)['test_collection']
    (root / 'tests/test_ordinary.py').write_text('def broken(:\n')
    assert run(root, 'tests/test_ordinary.py').returncode != 0
    data = cache.read(cfg)
    assert data['test_collection'] == before
    assert data['tests']['tests/test_ordinary.py']['phase'] == 'collect'
    assert data['tests']['tests/test_ordinary.py']['outcome'] == 'failed'


def test_other_file_failure_does_not_keep_an_obsolete_node_current(tmp_path):
    root, cfg = sample(tmp_path, 'def value(): return "old"\n')
    test = root / 'tests/test_ordinary.py'
    test.write_text('def test_old(): assert False\n')
    assert cli_fixture.check(cfg, everything=True) == 1
    test.write_text('def test_new(): assert True\n')
    (root / 'tests/test_other.py').write_text('def test_current_failure(): assert False\n')
    assert cli_fixture.check(cfg, everything=True) == 1
    data = cache.read(cfg)
    assert 'tests/test_ordinary.py::test_old' not in data['tests']
    assert data['tests']['tests/test_other.py::test_current_failure']['outcome'] == 'failed'
    with sqlite3.connect(cfg.cache / 'map.sqlite') as con:
        assert con.execute("SELECT outcome FROM reading WHERE test='tests/test_ordinary.py::test_old'").fetchone()[0] == 'failed'
