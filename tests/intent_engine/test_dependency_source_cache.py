"""Dependency syntax is shared; source and filesystem changes remain current inputs."""
from collections import Counter
from contextlib import closing

from flowguard.intent import cache, deps
from flowguard.intent.config import load_config
from flowguard.structure import build


SOURCE = ('from pathlib import Path\n'
          'def value():\n'
          '    return (Path(__file__).parent / "first.txt").read_text()\n')


def project(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'tests').mkdir()
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
    (root / 'owner.py').write_text(SOURCE)
    (root / 'first.txt').write_text('old')
    (root / 'second.txt').write_text('new')
    for name in ('first', 'second'):
        (root / f'tests/test_{name}.py').write_text('from owner import value\ndef test_value(): assert value() == "old"\n')
    return root, load_config(root)


def test_shared_source_is_read_parsed_and_path_scanned_once_per_dependency_analysis(tmp_path, monkeypatch):
    root, cfg = project(tmp_path)
    with closing(build(root, workers=1)) as graph:
        observed = Counter()
        read, parse, paths = deps.read_source, deps.ast.parse, deps._literal_paths

        def reading(path):
            observed['read:' + path.relative_to(root).as_posix()] += 1
            return read(path)

        def parsing(source, *args, **kwargs):
            if source == SOURCE:
                observed['parse:owner.py'] += 1
            return parse(source, *args, **kwargs)

        def scanning(tree, relative, *args):
            observed['scan:' + relative] += 1
            return paths(tree, relative, *args)

        monkeypatch.setattr(deps, 'read_source', reading)
        monkeypatch.setattr(deps.ast, 'parse', parsing)
        monkeypatch.setattr(deps, '_literal_paths', scanning)
        records = deps.test_dependencies(cfg, graph)
    assert set(records) == {'tests/test_first.py', 'tests/test_second.py'}
    assert all('owner.py' in record and 'first.txt' in record and '<unresolved>' not in record
               for record in records.values())
    assert observed['read:owner.py'] == observed['parse:owner.py'] == observed['scan:owner.py'] == 1
    assert observed['read:tests/test_first.py'] == observed['read:tests/test_second.py'] == 1


def test_source_changes_replace_cached_paths_and_dependency_signature_with_the_same_now(tmp_path):
    root, cfg = project(tmp_path)
    with closing(build(root, workers=1)) as graph:
        now = deps.Now(cfg, graph)
        before = deps.test_dependencies(cfg, graph, now)['tests/test_first.py']
        (root / 'owner.py').write_text(SOURCE.replace('first.txt', 'second.txt'))
        after = deps.test_dependencies(cfg, graph, now)['tests/test_first.py']
    assert 'first.txt' in before and 'second.txt' not in before
    assert 'second.txt' in after and 'first.txt' not in after
    assert cache.test_signature(before) != cache.test_signature(after)
    assert any('Map source identity changed: owner.py' in reason for reason in after['<unresolved>'])
    with closing(build(root, workers=1)) as graph:
        rebuilt = deps.test_dependencies(cfg, graph)['tests/test_first.py']
    assert 'second.txt' in rebuilt and 'first.txt' not in rebuilt and '<unresolved>' not in rebuilt


def test_cached_syntax_does_not_cache_data_values_or_directory_qualification(tmp_path):
    root, cfg = project(tmp_path)
    path = root / 'first.txt'
    with closing(build(root, workers=1)) as graph:
        now = deps.Now(cfg, graph)
        before = deps.test_dependencies(cfg, graph, now)['tests/test_first.py']
        path.write_text('changed')
        changed = deps.test_dependencies(cfg, graph, now)['tests/test_first.py']
        path.unlink()
        path.mkdir()
        directory = deps.test_dependencies(cfg, graph, now)['tests/test_first.py']
        path.rmdir()
        path.write_text('restored')
        restored = deps.test_dependencies(cfg, graph, now)['tests/test_first.py']
    assert before['first.txt'] != changed['first.txt']
    assert cache.test_signature(before) != cache.test_signature(changed)
    assert 'first.txt' not in directory and '<unresolved>' in directory
    assert 'first.txt' in restored and '<unresolved>' not in restored


def test_cached_literal_path_rechecks_a_retargeted_symlink(tmp_path):
    root, cfg = project(tmp_path)
    path = root / 'first.txt'
    path.unlink()
    path.symlink_to('second.txt')
    outside = tmp_path / 'outside.txt'
    outside.write_text('outside')
    with closing(build(root, workers=1)) as graph:
        now = deps.Now(cfg, graph)
        before = deps.test_dependencies(cfg, graph, now)['tests/test_first.py']
        path.unlink()
        path.symlink_to(outside)
        after = deps.test_dependencies(cfg, graph, now)['tests/test_first.py']
    assert 'second.txt' in before and '<unresolved>' not in before
    assert 'second.txt' not in after and '<unresolved>' in after
    assert any('dynamic or external data read' in reason for reason in after['<unresolved>'])
