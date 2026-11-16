"""Immutable baseline facts are reusable; source changes and reader identity are not."""
from contextlib import closing
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
    (root / 'app.py').write_text('LIMIT = 3\ndef eligible(x): return x <= LIMIT\n', encoding='utf-8')
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
    (root / 'app.py').write_text('LIMIT = 4\ndef eligible(x): return x <= LIMIT\n', encoding='utf-8')
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
        (root / 'app.py').write_text('LIMIT = 4\ndef eligible(x): return x <= LIMIT\n', encoding='utf-8')
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
    (root / 'app.py').write_text('LIMIT = 4\ndef eligible(x): return x <= LIMIT\n', encoding='utf-8')
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
    (root / 'app.py').write_text('LIMIT = 4\ndef eligible(x): return x <= LIMIT\ndef added(x): return x > 9\n', encoding='utf-8')
    with closing(build(root)) as graph:
        expected = graph.impact(since='HEAD')
        change = Change(load_config(root), graph, 'HEAD')
        def forbidden(*args, **kwargs):
            raise AssertionError('touched needs no callers, readers or data propagation')
        monkeypatch.setattr(graph, 'impact', forbidden)
        assert change.touched() == {named(n) for n in [*expected['changed'], *expected['added']]}
        assert change.touched() == {'app:LIMIT', 'app:added'}


def test_parse_error_in_old_source_is_preserved_on_cold_and_hot_read(tmp_path):
    root = project(tmp_path)
    (root / 'app.py').write_text('def broken(\n', encoding='utf-8')
    git(root, 'add', 'app.py'); git(root, 'commit', '-qm', 'unreadable baseline')
    (root / 'app.py').write_text('def repaired(): return 3\n', encoding='utf-8')
    with closing(build(root)) as graph:
        facts = graph._baseline_facts('HEAD', 'app.py', 'app')
        assert facts['parse_error'] and facts['nodes'] == []
    with closing(build(root)) as graph:
        assert graph._baseline_facts('HEAD', 'app.py', 'app') == facts


def test_baseline_tree_keeps_nested_project_and_literal_file_identity(tmp_path):
    root = project(tmp_path)
    inside = root / 'inside'
    inside.mkdir()
    name = 'hash # 空格.py'
    (inside / name).write_text('def eligible(x): return x <= 3\n', encoding='utf-8')
    git(root, 'add', 'inside'); git(root, 'commit', '-qm', 'nested source')
    with closing(build(inside)) as graph:
        facts = graph._baseline_facts('HEAD', name, 'literal_module')
        assert [node['qual'] for node in facts['nodes']] == ['eligible']
    with closing(build(root)) as graph:
        with pytest.raises(MapError):
            graph._baseline_facts('HEAD', 'inside', 'not_a_file')


def test_a_few_kinds_of_baseline_records_give_what_the_whole_records_give(tmp_path, monkeypatch):
    """`Change.old_record` gives the kinds of `old_facts` that a file's record holds ({} for a file absent at the
    baseline) without decoding the whole record, also for a record kept before its parts were and once the record is
    decoded; the baseline writes and definitions read from these kinds are those the whole records give."""
    root = project(tmp_path)
    (root / 'loans.py').write_text('LIMIT = 3\nclass Loan:\n    def __init__(self):\n        self.days = LIMIT\n'
                                   'def renew(loan: Loan):\n    loan.days = LIMIT + 1\n', encoding='utf-8')
    (root / 'gone.py').write_text('from loans import Loan\ndef close(loan: Loan):\n    loan.days = 0\n', encoding='utf-8')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'loans')
    (root / 'loans.py').write_text('LIMIT = 4\nclass Loan:\n    def __init__(self):\n        self.days = LIMIT\n'
                                   'def renew(loan: Loan):\n    loan.days = 5\n    loan.note = "x"\n', encoding='utf-8')
    (root / 'gone.py').unlink()
    (root / 'added.py').write_text('from loans import Loan\ndef open_(loan: Loan):\n    loan.days = 1\n', encoding='utf-8')
    kinds = ('language', 'writes', 'assignments', 'nodes', 'facts', 'no such kind')

    def whole_kinds(change, path):
        whole = change.old_facts(path)
        return {kind: whole[kind] for kind in kinds if kind in whole}

    with closing(build(root)) as graph:
        cfg = load_config(root)
        wholes = Change(cfg, graph, 'HEAD')
        paths = sorted(wholes.baseline_paths())
        assert paths == ['added.py', 'gone.py', 'loans.py']
        expected = {path: whole_kinds(wholes, path) for path in paths}
        assert expected['added.py'] == {} and 'no such kind' not in expected['loans.py']
        definitions = graph.definitions([(path, wholes.module(path), wholes.old_facts(path)) for path in paths])
        records = [data for path, _, data in graph.write_records() if path not in paths]
        records += [record for record in map(wholes.old_facts, paths) if record]
        writes = {by_name: graph.writes(by_name=by_name, facts=records, definitions=definitions) for by_name in (False, True)}
        assert {(row['function'], row['field'], row.get('value')) for row in writes[False]} >= {
            ('renew', 'days', 4), ('close', 'days', 0)}
    decoded = []
    unpack = api.store.unpack
    def counted(blob):
        value = unpack(blob)
        if isinstance(value, dict) and 'nodes' in value:
            decoded.append(value)            # a whole record
        return value
    for kept_before_parts in (False, True):
        with closing(build(root)) as graph:
            if kept_before_parts:
                graph.con.execute("DELETE FROM meta WHERE k LIKE 'baseline_facts:%:%'")
                graph.con.commit()
            monkeypatch.setattr(api.store, 'unpack', counted)
            change = Change(load_config(root), graph, 'HEAD')
            assert {path: change.old_record(path, kinds) for path in paths} == expected
            assert change.baseline_writes() == writes[False] and change.baseline_writes(by_name=True) == writes[True]
            assert change.baseline_definitions().env('loans') == definitions.env('loans')
            assert len(decoded) == (2 if kept_before_parts else 0)
            assert {path: change.old_record(path, kinds) for path in paths} == expected
            monkeypatch.setattr(api.store, 'unpack', unpack)
            decoded.clear()
    with closing(build(root)) as graph:
        change = Change(load_config(root), graph, 'HEAD')
        change.old_facts('loans.py')
        assert change.old_record('loans.py', kinds) == expected['loans.py']
    with closing(build(root)) as graph:             # a part lost from the cache is read as `_baseline_part` reads it
        graph.con.execute("DELETE FROM meta WHERE k LIKE 'baseline_facts:%:writes'")
        graph.con.commit()
        assert {path: Change(load_config(root), graph, 'HEAD').old_record(path, kinds) for path in paths} == expected
