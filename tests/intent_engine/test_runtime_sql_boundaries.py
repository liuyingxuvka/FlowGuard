"""Small controls for the deliberately narrow SQLite replay boundary."""
import inspect
import sqlite3

import pytest

from flowguard.intent.runtime import Runtime
from test_runtime_candidate import module


def _runtime(root, query, *, statement='return db.execute(QUERY, (x,)).fetchone() is not None'):
    statement = statement.replace('QUERY', repr(query))
    source = 'def allowed(db, x: int):\n    ' + statement + '\n'
    result = module(root, source)
    return result.allowed, Runtime(root, previous={'r19_candidate.py': source})


@pytest.mark.parametrize('kind', ['authorizer', 'progress', 'trace'])
def test_native_python_callbacks_have_only_the_one_business_calls_effects(tmp_path, kind):
    fn, runtime = _runtime(tmp_path, 'SELECT n FROM debt', statement='return db.execute(QUERY).fetchone()[0] <= x')
    counts = []
    for observe in (False, True):
        with sqlite3.connect(':memory:') as db:
            db.executescript('CREATE TABLE debt(n); INSERT INTO debt VALUES (1)')
            hits = []
            if kind == 'authorizer':
                db.set_authorizer(lambda *args: (hits.append(args), sqlite3.SQLITE_OK)[1])
            elif kind == 'progress':
                db.set_progress_handler(lambda: (hits.append(1), 0)[1], 1)
            else:
                db.set_trace_callback(hits.append)
            if observe:
                assert runtime.safety(fn, {'db': db, 'x': 9})
                assert hits == []  # Even the gate's PRAGMAs must not run.
                assert runtime.observe(fn, inspect.signature(fn).bind(db, 9), axes={'x': [0, 9]})
                assert runtime.readings[0].status == 'grey' and runtime.readings[0].rows == []
            else:
                assert fn(db, 9)
            counts.append(len(hits))
    assert counts[0] > 0 and counts[1] == counts[0]


def test_overridden_builtin_collation_sort_is_not_replayed(tmp_path):
    fn, runtime = _runtime(tmp_path, 'SELECT n FROM debt ORDER BY name COLLATE NOCASE LIMIT 1',
                           statement='return db.execute(QUERY).fetchone()[0] <= x')
    counts = []
    for observe in (False, True):
        with sqlite3.connect(':memory:') as db:
            db.executescript("CREATE TABLE debt(name TEXT, n); INSERT INTO debt VALUES ('b', 1), ('a', 2)")
            hits = []
            db.create_collation('NOCASE', lambda a, b: (hits.append((a, b)), (a > b) - (a < b))[1])
            if observe:
                assert runtime.observe(fn, inspect.signature(fn).bind(db, 9), axes={'x': [0, 9]})
                assert runtime.readings[0].status == 'grey' and runtime.readings[0].rows == []
            else:
                assert fn(db, 9)
            counts.append(len(hits))
    assert counts[0] > 0 and counts[1] == counts[0]


def test_integer_affinity_does_not_prove_current_storage_is_numeric(tmp_path):
    fn, runtime = _runtime(tmp_path, 'SELECT n FROM debt WHERE n=?')
    with sqlite3.connect(':memory:') as db:
        db.executescript("CREATE TABLE debt(n INTEGER); INSERT INTO debt VALUES ('text')")
        assert runtime.observe(fn, inspect.signature(fn).bind(db, 7), axes={'x': [7, 8]}) is False
    assert runtime.readings[0].status == 'grey' and runtime.readings[0].rows == []


def test_numeric_where_accepts_current_rows_but_not_text_candidate(tmp_path):
    fn, runtime = _runtime(tmp_path, 'SELECT n FROM debt WHERE n=?')
    with sqlite3.connect(':memory:') as db:
        db.executescript('CREATE TABLE debt(n INTEGER); INSERT INTO debt VALUES (7)')
        assert runtime.observe(fn, inspect.signature(fn).bind(db, 7), axes={'x': [7, 8]}) is True
        assert runtime.readings[-1].status == 'ok' and len(runtime.readings[-1].rows) == 2
        assert runtime.observe(fn, inspect.signature(fn).bind(db, 7), axes={'x': [7, '7']}) is True
        assert runtime.readings[-1].status == 'grey' and runtime.readings[-1].rows == []
        assert 'SQL condition candidates' in runtime.readings[-1].reasons[0]


def test_overridden_typeof_is_not_called_to_prove_the_condition(tmp_path):
    fn, runtime = _runtime(tmp_path, 'SELECT n FROM debt WHERE n=?')
    with sqlite3.connect(':memory:') as db:
        db.executescript('CREATE TABLE debt(n INTEGER); INSERT INTO debt VALUES (7)')
        hits = []
        db.create_function('typeof', 1, lambda value: (hits.append(value), 'integer')[1])
        assert runtime.observe(fn, inspect.signature(fn).bind(db, 7), axes={'x': [7, 8]}) is True
        assert hits == []
    assert runtime.readings[0].status == 'grey' and runtime.readings[0].rows == []


@pytest.mark.parametrize('definition', [
    'CREATE VIEW debt AS SELECT 1 AS n',
    'CREATE TABLE debt(base); INSERT INTO debt VALUES (1); CREATE TEMP TABLE debt(n); INSERT INTO debt VALUES (1)',
    'CREATE TABLE debt(base, n GENERATED ALWAYS AS (base+1)); INSERT INTO debt(base) VALUES (0)',
])
def test_views_temp_ambiguity_and_generated_columns_are_not_replayed(tmp_path, definition):
    fn, runtime = _runtime(tmp_path, 'SELECT n FROM debt', statement='return db.execute(QUERY).fetchone()[0] <= x')
    with sqlite3.connect(':memory:') as db:
        db.executescript(definition)
        assert runtime.observe(fn, inspect.signature(fn).bind(db, 7), axes={'x': [0, 7]})
    assert runtime.readings[0].status == 'grey' and runtime.readings[0].rows == []


def test_registered_converter_only_runs_for_the_business_fetch(tmp_path, monkeypatch):
    fn, runtime = _runtime(tmp_path, 'SELECT n FROM debt', statement='return db.execute(QUERY).fetchone()[0] <= x')
    hits = []
    monkeypatch.setitem(sqlite3.converters, 'R19NUM', lambda raw: (hits.append(raw), int(raw))[1])
    with sqlite3.connect(':memory:', detect_types=sqlite3.PARSE_DECLTYPES) as db:
        db.executescript('CREATE TABLE debt(n R19NUM); INSERT INTO debt VALUES (1)')
        assert runtime.observe(fn, inspect.signature(fn).bind(db, 7), axes={'x': [0, 7]})
    assert hits == [b'1']
    assert runtime.readings[0].status == 'grey' and runtime.readings[0].rows == []


def test_registered_parameter_adapter_only_runs_for_the_business_execute(tmp_path, monkeypatch):
    fn, runtime = _runtime(tmp_path, 'SELECT n FROM debt WHERE n=?')
    hits = []
    with sqlite3.connect(':memory:') as db:
        db.executescript('CREATE TABLE debt(n INTEGER); INSERT INTO debt VALUES (7)')
        monkeypatch.setitem(sqlite3.adapters, (int, sqlite3.PrepareProtocol), lambda value: (hits.append(value), value)[1])
        sqlite3.register_adapter(int, sqlite3.adapters[(int, sqlite3.PrepareProtocol)])
        assert runtime.observe(fn, inspect.signature(fn).bind(db, 7), axes={'x': [7, 8]})
    assert hits == [7]
    assert runtime.readings[0].status == 'grey' and runtime.readings[0].rows == []


def test_typeof_storage_scan_is_repeated_when_same_connection_changes(tmp_path):
    fn, runtime = _runtime(tmp_path, 'SELECT n FROM debt WHERE n=?')
    with sqlite3.connect(':memory:') as db:
        db.executescript('CREATE TABLE debt(n INTEGER); INSERT INTO debt VALUES (7)')
        assert runtime.observe(fn, inspect.signature(fn).bind(db, 7), axes={'x': [7, 8]})
        assert runtime.readings[-1].status == 'ok'
        db.execute("UPDATE debt SET n='text'")
        assert runtime.observe(fn, inspect.signature(fn).bind(db, 7), axes={'x': [7, 8]}) is False
        assert runtime.readings[-1].status == 'grey' and runtime.readings[-1].rows == []


def test_text_candidate_for_conditional_read_inside_helper_is_not_replayed(tmp_path):
    source = '''def helper(db, value):
    return db.execute('SELECT n FROM debt WHERE n=?', (value,)).fetchone() is not None
def allowed(db, x: int):
    return helper(db, x)
'''
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    with sqlite3.connect(':memory:') as db:
        db.executescript('CREATE TABLE debt(n INTEGER); INSERT INTO debt VALUES (7)')
        assert runtime.observe(m.allowed, inspect.signature(m.allowed).bind(db, 7), axes={'x': [7, '7']})
    assert runtime.readings[0].status == 'grey' and runtime.readings[0].rows == []


def test_text_candidate_is_rejected_when_only_old_body_uses_numeric_where(tmp_path):
    old = "def allowed(db, x: int):\n    return db.execute('SELECT n FROM debt WHERE n=?', (x,)).fetchone() is not None\n"
    m = module(tmp_path, 'def allowed(db, x: int):\n    return x == 7\n')
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with sqlite3.connect(':memory:') as db:
        db.executescript('CREATE TABLE debt(n INTEGER); INSERT INTO debt VALUES (7)')
        assert runtime.observe(m.allowed, inspect.signature(m.allowed).bind(db, 7), axes={'x': [7, '7']})
    assert runtime.readings[0].status == 'grey' and runtime.readings[0].rows == []
