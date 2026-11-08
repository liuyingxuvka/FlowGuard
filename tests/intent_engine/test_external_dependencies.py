"""Actual external inputs must never be licensed by absent project candidates."""
from contextlib import closing
from pathlib import Path
import uuid
import json

import pytest

from tests.intent_engine import _cli_fixture as cli_fixture

from flowguard.intent import cli, deps
from flowguard.structure import build
from test_cli import project
from test_cli_incremental import calls


def external_project(tmp_path, *, style='direct', source=None):
    root, cfg = project(tmp_path)
    outside = tmp_path / ('provider_' + uuid.uuid4().hex)
    outside.mkdir()
    name = outside.name
    body = source or 'import os\ndef read(): return os.getenv("FG_N1_VALUE", "alpha")\n'
    (outside / (name + '.py')).write_text(body)
    config = root / 'pyproject.toml'
    config.write_text(config.read_text() + '\n[tool.pytest.ini_options]\ntestpaths=["tests"]\npythonpath=[' + json.dumps(str(outside)) + ']\n')
    if style == 'alias':
        imports, expression = f'from {name} import read as fetch', 'fetch()'
    elif style == 'reexport':
        (root / 'bridge.py').write_text(f'from {name} import read\n')
        imports, expression = 'from bridge import read', 'read()'
    elif style == 'package':
        (outside / (name + '.py')).unlink()
        package = outside / name
        package.mkdir()
        (package / 'inner.py').write_text(body)
        (package / '__init__.py').write_text('from .inner import read\n')
        imports, expression = f'from {name} import read', 'read()'
    else:
        imports, expression = f'from {name} import read', 'read()'
    (root / 'tests/test_external.py').write_text(imports + '\ndef test_external(): assert ' + expression + ' == "alpha"\n')
    cli.init(cfg)
    return root, cfg, outside / (name + '.py')


def dependency(cfg):
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        return deps.test_dependencies(cfg, graph)['tests/test_external.py']


@pytest.mark.parametrize('style', ['direct', 'alias', 'reexport', 'package'])
def test_external_environment_change_is_executed_and_matches_full(tmp_path, monkeypatch, style):
    root, cfg, _ = external_project(tmp_path, style=style)
    monkeypatch.setenv('FG_N1_VALUE', 'alpha')
    assert cli_fixture.check(cfg, everything=True) == 0
    assert '<unresolved>' in dependency(cfg)
    selected = calls(monkeypatch)
    monkeypatch.setenv('FG_N1_VALUE', 'beta')
    assert cli_fixture.check(cfg) == 1
    assert selected and any('tests/test_external.py' in command for command in selected)
    assert cli_fixture.check(cfg, everything=True) == 1
    assert 'test_external' in (cfg.cache / 'check-output.txt').read_text()


def test_external_source_change_is_not_hidden_by_unchanged_distribution_identity(tmp_path, monkeypatch):
    root, cfg, module = external_project(tmp_path, source='def read(): return "alpha"\n')
    assert cli_fixture.check(cfg, everything=True) == 0
    selected = calls(monkeypatch)
    assert cli_fixture.check(cfg) == 0 and selected  # Correct opaque executions are usable.
    module.write_text('def read(): return "beta"\n')
    assert cli_fixture.check(cfg) == 1
    assert cli_fixture.check(cfg, everything=True) == 1


def test_external_initializer_input_is_not_assumed_pure(tmp_path, monkeypatch):
    root, cfg, _ = external_project(tmp_path, source='import os\nVALUE=os.getenv("FG_N1_VALUE", "alpha")\ndef read(): return VALUE\n')
    monkeypatch.setenv('FG_N1_VALUE', 'alpha')
    assert cli_fixture.check(cfg, everything=True) == 0
    monkeypatch.setenv('FG_N1_VALUE', 'beta')
    assert cli_fixture.check(cfg) == cli_fixture.check(cfg, everything=True) == 1


def test_unmodeled_stdlib_call_is_not_pure_merely_because_it_is_stdlib(tmp_path):
    root, cfg = project(tmp_path)
    test = root / 'tests/test_version.py'
    test.write_text('import tomllib\ndef test_version(): assert tomllib.loads("version=1")["version"] == 1\n')
    with closing(build(root)) as graph:
        record = deps.test_dependencies(cfg, graph)['tests/test_version.py']
    assert any('unverified external call tomllib.loads' in r for r in record['<unresolved>'])


def test_lookalike_path_api_cannot_borrow_the_stdlib_path_model(tmp_path):
    root, cfg, _ = external_project(tmp_path, source='class Path:\n    def __init__(self, value): pass\n    def read_text(self): return "alpha"\ndef read(): return Path("data.txt").read_text()\n')
    assert '<unresolved>' in dependency(cfg)


def test_a_dependency_environment_inside_the_project_is_still_external(tmp_path, monkeypatch):
    root, cfg = project(tmp_path)
    environment = root / '.venv'
    package = environment / 'lib/python/site-packages'
    package.mkdir(parents=True)
    (environment / 'pyvenv.cfg').write_text('home = interpreter\n')
    (package / 'hidden_provider.py').write_text('import os\ndef read(): return os.getenv("FG_N1_VALUE", "alpha")\n')
    config = root / 'pyproject.toml'
    config.write_text(config.read_text() + '\n[tool.pytest.ini_options]\ntestpaths=["tests"]\npythonpath=[' + json.dumps(str(package)) + ']\n')
    (root / 'tests/test_external.py').write_text('from hidden_provider import read\ndef test_external(): assert read()=="alpha"\n')
    cli.init(cfg)
    monkeypatch.setenv('FG_N1_VALUE', 'alpha')
    assert '<unresolved>' in dependency(cfg)
    assert cli_fixture.check(cfg, everything=True) == 0
    monkeypatch.setenv('FG_N1_VALUE', 'beta')
    assert cli_fixture.check(cfg) == cli_fixture.check(cfg, everything=True) == 1


@pytest.mark.parametrize('external', [False, True], ids=['project', 'external'])
@pytest.mark.parametrize('namespace', [False, True], ids=['regular-child', 'namespace-child'])
def test_origin_lookup_never_imports_an_uninitialized_parent(tmp_path, external, namespace):
    """Nested namespace specs require a loaded parent; discovery must stay read-only."""
    import sys

    root, cfg = project(tmp_path)
    search = tmp_path / 'outside' if external else root
    name = 'provider_' + uuid.uuid4().hex
    parent = search / name
    child = parent / 'nested'
    child.mkdir(parents=True)
    (parent / '__init__.py').write_text('raise AssertionError("origin discovery executed parent")\n')
    if not namespace:
        (child / '__init__.py').write_text('raise AssertionError("origin discovery executed child")\n')
    leaf = child / 'provider.py'
    leaf.write_text('import os\ndef read(): return os.getenv("FG_N1_VALUE", "alpha")\n')
    if external:
        config = root / 'pyproject.toml'
        config.write_text(config.read_text() + '\n[tool.pytest.ini_options]\npythonpath=[' + json.dumps(str(search)) + ']\n')
        from flowguard.intent.config import load_config
        cfg = load_config(root)
    module = name + '.nested.provider'
    parents = [name, name + '.nested', module]
    assert not any(part in sys.modules for part in parents)
    with closing(build(root)) as graph:
        context = deps._TestDependencies(cfg, graph, deps.Now(cfg, graph))
        kind, location = context.origin(module)
        if namespace:
            assert (kind, location) == ('unknown', None)
            assert context.import_reason(module) == 'unverified external import ' + module
        else:
            assert kind == ('external' if external else 'project')
            assert Path(location) == leaf
    assert not any(part in sys.modules for part in parents)
