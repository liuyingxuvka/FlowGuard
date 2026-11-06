"""Declaration policy consumes source facts, including unused aliased stdlib imports."""
from contextlib import closing
from flowguard.structure import build


def test_declarations_include_external_aliases_and_keep_typing_distinct(tmp_path):
    (tmp_path / 'app.py').write_text(
        'from typing import TYPE_CHECKING\n'
        'from contextlib import suppress as quiet\n'
        'from warnings import filterwarnings as hush\n'
        'if TYPE_CHECKING:\n'
        '    from warnings import warn\n'
        'def f():\n'
        '    import os as system\n'
        'raise RuntimeError("must never import this source")\n')
    with closing(build(tmp_path, workers=1)) as graph:
        links = list(graph.imports())
        rows = list(graph.imports(declarations=True))
        assert all(row['kind'] != 'import-declaration' for row in links)
        assert {(row['module'], row['name'], row['line'], row['typing']) for row in rows} == {
            ('typing', 'TYPE_CHECKING', 1, False), ('contextlib', 'suppress', 2, False),
            ('warnings', 'filterwarnings', 3, False), ('warnings', 'warn', 5, True),
            ('os', '', 7, False)}
        assert all(row['prov'] == 'source' and row['file'] == 'app.py' for row in rows)


def test_changed_declarations_replace_old_source_facts(tmp_path):
    path = tmp_path / 'app.py'
    path.write_text('from warnings import filterwarnings as hush\n')
    with closing(build(tmp_path, workers=1)) as graph:
        assert graph.imports(declarations=True)[0]['name'] == 'filterwarnings'
    path.write_text('from contextlib import suppress as quiet\n')
    with closing(build(tmp_path, workers=1)) as graph:
        rows = graph.imports(declarations=True)
        assert [(row['module'], row['name']) for row in rows] == [('contextlib', 'suppress')]


def test_definition_expressions_are_source_calls_in_the_outer_scope(tmp_path):
    (tmp_path / 'app.py').write_text(
        'import pytest as p\nimport warnings as w\n'
        '@p.mark.filterwarnings("ignore")\n'
        'def test_x(value=w.filterwarnings("ignore")):\n    pass\n')
    with closing(build(tmp_path, workers=1)) as graph:
        calls = {(row['resolved'], row['node'], row['line']) for row in graph.calls()}
        assert ('pytest.mark.filterwarnings', 'app', 3) in calls
        assert ('warnings.filterwarnings', 'app', 4) in calls
        assert not graph.edges('app:test_x', kind='calls')


def test_symbol_reads_and_unknown_assignment_targets_are_explicit_opt_in(tmp_path):
    (tmp_path / 'app.py').write_text(
        'import pytest as p\n'
        'deferred = p.skip\n'
        'also = deferred\n'
        'collect_ignore = ["test_other.py"]\n'
        'literal_none = None\n')
    with closing(build(tmp_path, workers=1)) as graph:
        assert graph.calls() == []
        reads = graph.calls(include_reads=True)
        assert any(row['resolved'] == 'pytest.skip' and row['read'] and row['line'] == 2 for row in reads)
        assert any(row['resolved'] == 'pytest.skip' and row['read'] and row['line'] == 3 for row in reads)
        assert [(row['field'], row['value']) for row in graph.assignments()] == [('app:literal_none', None)]
        unknown = {row['field']: row for row in graph.assignments(include_unknown=True) if not row['literal']}
        assert 'app:collect_ignore' in unknown and unknown['app:collect_ignore']['value'] is None
        assert not unknown['app:collect_ignore']['unresolved']


def test_old_reader_cache_reparses_unchanged_source_before_new_fact_queries(tmp_path):
    import sqlite3
    from flowguard.structure import store
    (tmp_path / 'app.py').write_text('import pytest\nlater = pytest.skip\n')
    with closing(build(tmp_path, workers=1)) as graph:
        database = graph.path
    # Simulate the old reader's persisted facts, not a source edit or cache deletion.
    with sqlite3.connect(database) as connection:
        data = store.unpack(connection.execute('SELECT data FROM file').fetchone()[0])
        data.pop('symbol_reads')
        connection.execute('UPDATE file SET data=?', (store.pack(data),))
        connection.execute("UPDATE meta SET v='reader-before-source-reads' WHERE k='reader_digest'")
    with closing(build(tmp_path, workers=1)) as graph:
        assert graph.stats['parsed'] == 1
        assert any(row['resolved'] == 'pytest.skip' and row.get('read')
                   for row in graph.calls(include_reads=True))
    with closing(build(tmp_path, workers=1)) as graph:
        assert graph.stats['parsed'] == 0
        assert graph.con.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
