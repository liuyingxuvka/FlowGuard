"""Immutable baseline facts are reusable; source changes and reader identity are not."""
from contextlib import closing
import ast
import sqlite3
import subprocess
import zlib

import pytest

from flowguard.intent.config import load_config
from flowguard.intent.owners import Change, named
from flowguard.map.common import MapError
from flowguard.structure import build
from flowguard.structure import api


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), '-c', 'user.name=Fixture',
                                    '-c', 'user.email=fixture@example.invalid', *args], text=True).strip()


def project(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'app.py').write_text('LIMIT = 3\ndef eligible(x): return x <= LIMIT\n')
    git(root, 'init', '-q', '-b', 'main')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'original boundary')
    return root


def counted(monkeypatch):
    calls, original = [], api.extract
    def extract(root, file, raw, module, test):
        calls.append((file, module, test))
        return original(root, file, raw, module, test)
    monkeypatch.setattr(api, 'extract', extract)
    return calls


def test_old_facts_delta_and_reopened_map_share_one_source_extraction(tmp_path, monkeypatch):
    root = project(tmp_path)
    (root / 'app.py').write_text('LIMIT = 4\ndef eligible(x): return x <= LIMIT\n')
    calls = counted(monkeypatch)
    with closing(build(root)) as graph:
        old = Change(load_config(root), graph, 'HEAD').old_facts('app.py')
        assert any(n['qual'] == 'LIMIT' and n['sig'] == '3' for n in old['nodes'])
        delta = graph._delta_against('HEAD', ['app.py'])
        assert {row[0] for row in delta if row[1] == 'changed'} == {'app:LIMIT'}
        assert graph._delta_against('HEAD', ['app.py']) == delta
        assert calls == [('app.py', 'app', False)]
    with closing(build(root)) as graph:
        assert Change(load_config(root), graph, 'HEAD').old_facts('app.py') == old
        assert graph._delta_against('HEAD', ['app.py']) == delta
        assert calls == [('app.py', 'app', False)]


def test_blob_module_test_and_reader_changes_do_not_borrow_cached_facts(tmp_path, monkeypatch):
    root = project(tmp_path)
    calls = counted(monkeypatch)
    with closing(build(root)) as graph:
        first = graph._baseline_facts('HEAD', 'app.py', 'app')
        (root / 'app.py').write_text('LIMIT = 4\ndef eligible(x): return x <= LIMIT\n')
        git(root, 'add', 'app.py')
        git(root, 'commit', '-qm', 'new boundary')
        second = graph._baseline_facts('HEAD', 'app.py', 'app')
        assert [n['sig'] for n in first['nodes'] if n['qual'] == 'LIMIT'] == ['3']
        assert [n['sig'] for n in second['nodes'] if n['qual'] == 'LIMIT'] == ['4']
        graph._baseline_facts('HEAD', 'app.py', 'different_module')
        tests = graph._baseline_facts('HEAD', 'app.py', 'app', True)
        assert next(n for n in tests['nodes'] if n['qual'] == 'eligible')['kind'] == 'test'
        graph.con.execute("UPDATE meta SET v=v||'-new-reader' WHERE k='reader_digest'")
        graph.con.commit()
        assert graph._baseline_facts('HEAD', 'app.py', 'app') == second
        assert calls == [('app.py', 'app', False), ('app.py', 'app', False),
                         ('app.py', 'different_module', False), ('app.py', 'app', True), ('app.py', 'app', False)]


def test_cache_damage_and_missing_commit_are_not_accepted_as_absent_source(tmp_path):
    root = project(tmp_path)
    with closing(build(root)) as graph:
        assert graph._baseline_facts('HEAD', 'absent.py', 'absent') == {}
        with pytest.raises(MapError):
            graph._baseline_facts('not-a-real-commit', 'app.py', 'app')
        graph._baseline_facts('HEAD', 'app.py', 'app')
        graph.con.execute("UPDATE meta SET v=? WHERE k LIKE 'baseline_facts:%'", (b'broken cache',))
        graph.con.commit()
        graph._derived.clear()
        with pytest.raises(zlib.error):
            graph._baseline_facts('HEAD', 'app.py', 'app')


def test_source_fact_cache_does_not_commit_an_existing_transaction(tmp_path):
    root = project(tmp_path)
    with closing(build(root)) as graph:
        graph.con.execute("INSERT INTO meta VALUES('uncommitted-user-row','keep private')")
        graph._baseline_facts('HEAD', 'app.py', 'app')
        with closing(sqlite3.connect(graph.path)) as other:
            assert other.execute("SELECT v FROM meta WHERE k='uncommitted-user-row'").fetchone() is None
        graph.con.rollback()


def test_touched_uses_the_same_move_filtered_delta_without_full_impact(tmp_path, monkeypatch):
    root = project(tmp_path)
    (root / 'app.py').write_text('LIMIT = 4\ndef eligible(x): return x <= LIMIT\ndef added(x): return x > 9\n')
    with closing(build(root)) as graph:
        expected = graph.impact(since='HEAD')
        change = Change(load_config(root), graph, 'HEAD')
        def forbidden(*args, **kwargs):
            raise AssertionError('touched needs no callers, readers or data propagation')
        monkeypatch.setattr(graph, 'impact', forbidden)
        assert change.touched() == {named(n) for n in [*expected['changed'], *expected['added']]}
        assert change.touched() == {'app:LIMIT', 'app:added'}


@pytest.mark.parametrize('before,after,same', [
    ('def f(x): return x <= 3', 'def f(x): return x <= 4', True),
    ('def f(x): return x <= 3', 'def f(x): return x < 3', False),
    ('def f(x): return x <= 3', 'def f(x): return x <= 3.0', False),
    ('def f(x="old"): return [x, True]', 'def f(x="new"): return [x, False]', True),
    ('def f(x):\n def g(y): return y + 1\n return g(x)',
     'def f(x):\n def g(y): return y + 9\n return g(x)', True),
])
def test_literal_shape_projection_keeps_structure_types_and_original_ast(before, after, same):
    from flowguard.intent.owners import _shape
    first, second = ast.parse(before).body[0], ast.parse(after).body[0]
    original = ast.dump(first, include_attributes=True)
    assert (_shape(first) == _shape(second)) is same
    assert ast.dump(first, include_attributes=True) == original


def test_parse_error_in_old_source_is_preserved_on_cold_and_hot_read(tmp_path):
    root = project(tmp_path)
    (root / 'app.py').write_text('def broken(\n')
    git(root, 'add', 'app.py'); git(root, 'commit', '-qm', 'unreadable baseline')
    (root / 'app.py').write_text('def repaired(): return 3\n')
    with closing(build(root)) as graph:
        facts = graph._baseline_facts('HEAD', 'app.py', 'app')
        assert facts['parse_error'] and facts['nodes'] == []
    with closing(build(root)) as graph:
        assert graph._baseline_facts('HEAD', 'app.py', 'app') == facts


@pytest.mark.parametrize('old,new,pairs', [
    ('def f(x): return x <= 3', 'def f(x): return x <= 4', [(3, 4)]),
    ('def f(x): return x <= 3', 'def f(x): return x < 4', []),
    ('def f(x): return x <= 3', 'def f(x): return x <= 3.0', []),
    ('def f(x):\n "old text"\n return x <= 3', 'def f(x):\n "new text"\n return x <= 3', [('old text', 'new text')]),
    ('@decorate(3)\ndef f(x): return x <= 3', '@decorate(4)\ndef f(x): return x <= 3', [(3, 4)]),
    ('def f(x):\n "\u0085same"\n return x <= 3', 'def f(x):\n "\u0085same"\n return x <= 4', [(3, 4)]),
])
def test_literal_change_shortcut_keeps_structure_and_docstring_semantics(tmp_path, old, new, pairs):
    from flowguard.intent.owners import constant_changes
    root = project(tmp_path)
    (root / 'app.py').write_text(old + '\n')
    git(root, 'add', 'app.py'); git(root, 'commit', '-qm', 'baseline judgment')
    (root / 'app.py').write_text(new + '\n')
    with closing(build(root)) as graph:
        result = constant_changes(Change(load_config(root), graph, 'HEAD'))
    assert [(row['before'], row['after']) for row in result] == pairs


def test_baseline_tree_keeps_nested_project_and_literal_file_identity(tmp_path):
    root = project(tmp_path)
    inside = root / 'inside'
    inside.mkdir()
    name = 'hash # 空格.py'
    (inside / name).write_text('def eligible(x): return x <= 3\n')
    git(root, 'add', 'inside'); git(root, 'commit', '-qm', 'nested source')
    with closing(build(inside)) as graph:
        facts = graph._baseline_facts('HEAD', name, 'literal_module')
        assert [node['qual'] for node in facts['nodes']] == ['eligible']
    with closing(build(root)) as graph:
        with pytest.raises(MapError):
            graph._baseline_facts('HEAD', 'inside', 'not_a_file')
