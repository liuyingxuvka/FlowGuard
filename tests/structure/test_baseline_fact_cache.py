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


def test_one_kind_of_a_baseline_record_is_read_without_decoding_the_record_again(tmp_path, monkeypatch):
    root = project(tmp_path)
    (root / 'app.py').write_text('LIMIT = 4\ndef eligible(x): return x <= LIMIT\n')
    with closing(build(root)) as graph:
        whole = graph._baseline_facts('HEAD', 'app.py', 'app')
        assert graph._baseline_part('HEAD', 'app.py', 'app', 'nodes') == whole['nodes']
        assert graph._baseline_part('HEAD', 'app.py', 'app', 'no such kind') is None
        assert graph._baseline_part('HEAD', 'absent.py', 'absent', 'nodes') is None
        delta = graph._delta_against('HEAD', ['app.py'])
    decoded = []
    unpack = api.store.unpack
    def counted(blob):
        value = unpack(blob)
        if isinstance(value, dict) and 'nodes' in value:
            decoded.append(value)            # a whole record
        return value
    with closing(build(root)) as graph:
        monkeypatch.setattr(api.store, 'unpack', counted)
        assert graph._baseline_part('HEAD', 'app.py', 'app', 'nodes') == whole['nodes']
        assert graph._baseline_part('HEAD', 'app.py', 'app', 'literals') == whole['literals']
        assert graph._baseline_part('HEAD', 'app.py', 'app', 'no such kind') is None
        assert graph._delta_against('HEAD', ['app.py']) == delta
        assert decoded == []
        assert Change(load_config(root), graph, 'HEAD').old_facts('app.py') == whole      # the record itself is kept


def test_a_record_kept_before_its_parts_gets_them_in_one_commit(tmp_path):
    root = project(tmp_path)
    with closing(build(root)) as graph:
        whole = graph._baseline_facts('HEAD', 'app.py', 'app')
        graph.con.execute("DELETE FROM meta WHERE k LIKE 'baseline_facts:%:%'")
        graph.con.commit()
        graph._derived.clear()
        assert graph._baseline_part('HEAD', 'app.py', 'app', 'nodes') == whole['nodes']
        kept = graph.con.execute("SELECT COUNT(*) FROM meta WHERE k LIKE 'baseline_facts:%:%'").fetchone()[0]
        assert kept == len(whole) + 1 and not graph.con.in_transaction


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
    from flowguard.intent.owners import _shape_key
    first, second = ast.parse(before).body[0], ast.parse(after).body[0]
    original = ast.dump(first, include_attributes=True)
    assert (_shape_key(first) == _shape_key(second)) is same
    assert ast.dump(first, include_attributes=True) == original


def _blank_dump(function):
    """The earlier projection, kept as the oracle: every constant replaced by its type name, then dumped."""
    def blank(node):
        if isinstance(node, ast.Constant):
            return ast.Constant(type(node.value).__name__)
        if isinstance(node, ast.AST):
            return type(node)(**{name: blank(value) for name, value in ast.iter_fields(node)})
        if isinstance(node, list):
            return [blank(value) for value in node]
        return node
    return ast.dump(blank(function), include_attributes=False)


@pytest.mark.parametrize('before,after', [
    ('def f(x): return x + 1', 'def f(x): return x + 2'),
    ('def f(x): return u"a"', 'def f(x): return "b"'),
    ('def f(x): return None', 'def f(x): return ...'),
    ('def f(x=1, *, y=2): return {1: x, **y}', 'def f(x=3, *, y=4): return {5: x, **y}'),
    ('def f(x): return {**x, 1: 2}', 'def f(x): return {1: 2, **x}'),
    ('def f(x) -> int: return 1', 'def f(x): return 1'),
    ('def f(x):\n    global a\n    return a', 'def f(x):\n    global b\n    return b'),
    ('def f(x): return f"{x!r:>{1}}"', 'def f(x): return f"{x!s:>{2}}"'),
    ('def f(x): return x[1:2]', 'def f(x): return x[1:2:3]'),
    ('def f(x):\n    from . import a\n    return 1', 'def f(x):\n    from .. import a\n    return 2'),
    ('def f(x):\n    match x:\n        case None: return 1\n        case [1, *r]: return 2',
     'def f(x):\n    match x:\n        case True: return 1\n        case [3, *r]: return 4'),
    ('def f(x): return lambda y=1: y', 'def f(x): return lambda y=2: y'),
    ('def f(x): return (1, 2)', 'def f(x): return [1, 2]'),
    ('def f(x): return b"a"', 'def f(x): return "a"'),
    ('@d(1)\ndef f(x): return 1', '@d(2)\ndef f(x): return 1'),
    ('async def f(x): await g(1)', 'async def f(x): await g(2)'),
])
def test_shape_key_decides_as_the_blanked_dump_and_keeps_constants_in_walk_order(before, after):
    from flowguard.intent.owners import _shape_key
    first, second = ast.parse(before).body[0], ast.parse(after).body[0]
    same = _shape_key(first) == _shape_key(second)
    assert same is (_blank_dump(first) == _blank_dump(second))
    if same:      # one structure: the walk meets the constants of both at the same places
        walked = [[type(node.value).__name__ for node in ast.walk(tree) if isinstance(node, ast.Constant)] for tree in (first, second)]
        assert walked[0] == walked[1]


def test_shape_key_reads_an_expression_deeper_than_the_recursion_limit():
    import sys
    from flowguard.intent.owners import _shape_key
    depth = sys.getrecursionlimit() + 100
    tree = ast.parse('def f(x):\n    return x' + ' + 1' * depth + '\n').body[0]
    other = ast.parse('def f(x):\n    return x' + ' + 2' * depth + '\n').body[0]
    assert _shape_key(tree) == _shape_key(other)


LITERALS = [None, ..., True, False, 0, -7, 2 ** 200, 0x1 << 20000, -0.0, 1e-300, float('inf'), 1.5j,
            'text é\ud800', b'\x00\xff', (1, [2.0, {3: 'x'}]), {1, 'a'}, {'k': (None, ...)}, ()]


@pytest.mark.parametrize('value', LITERALS, ids=[type(value).__name__ for value in LITERALS])
def test_stored_literals_keep_their_exact_type_and_value(value):
    import json
    from flowguard.intent.owners import _packed, _unpacked
    back = _unpacked(json.loads(json.dumps(_packed(value))))
    def same(a, b):
        if type(a) is not type(b):
            return False
        if type(a) in (tuple, list):
            return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
        if type(a) is dict:
            return list(a) == list(b) and all(same(a[key], b[key]) for key in a)
        if type(a) is float:
            return a.hex() == b.hex()
        return a == b
    assert same(back, value)


def test_constant_facts_are_read_once_per_text_and_never_borrowed_by_an_edit(tmp_path, monkeypatch):
    from flowguard.intent import owners
    root = project(tmp_path)
    (root / 'app.py').write_text('LIMIT = 4\ndef eligible(x): return x <= LIMIT\n')
    read = []
    original = owners._read_constants
    monkeypatch.setattr(owners, '_read_constants', lambda text: read.append(text) or original(text))
    def changes():
        with closing(build(root)) as graph:
            return [(row['before'], row['after']) for row in owners.constant_changes(Change(load_config(root), graph, 'HEAD'))]
    assert changes() == [(3, 4)] and len(read) == 2           # the baseline blob and the working-tree text
    blobs = []
    monkeypatch.setattr(Change, 'old_text', lambda self, file: blobs.append(file))
    assert changes() == [(3, 4)] and len(read) == 2           # a reopened map reads neither again
    (root / 'app.py').write_text('LIMIT = 5\ndef eligible(x): return x <= LIMIT\n')
    assert changes() == [(3, 5)] and len(read) == 3 and blobs == []     # only the edited text is read


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
