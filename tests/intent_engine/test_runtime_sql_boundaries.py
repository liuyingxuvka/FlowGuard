"""SQLite connections holding Python callbacks are not replayed; plain reads are."""
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


def test_overridden_typeof_is_not_called_to_prove_the_condition(tmp_path):
    fn, runtime = _runtime(tmp_path, 'SELECT n FROM debt WHERE n=?')
    with sqlite3.connect(':memory:') as db:
        db.executescript('CREATE TABLE debt(n INTEGER); INSERT INTO debt VALUES (7)')
        hits = []
        db.create_function('typeof', 1, lambda value: (hits.append(value), 'integer')[1])
        assert runtime.observe(fn, inspect.signature(fn).bind(db, 7), axes={'x': [7, 8]}) is True
        assert hits == []          # nothing calls typeof to prove the condition; the replay reads the table
    assert runtime.readings[0].status == 'ok' and runtime.readings[0].rows


@pytest.mark.parametrize('kind', ['authorizer', 'progress'])
def test_literal_integer_read_rejects_callbacks_before_any_extra_sql(tmp_path, kind):
    fn, runtime = _runtime(tmp_path, 'SELECT 6', statement='return db.execute(QUERY).fetchone()[0] <= x')
    counts = []
    for observe in (False, True):
        with sqlite3.connect(':memory:') as db:
            hits = []
            if kind == 'authorizer':
                db.set_authorizer(lambda *args: (hits.append(args), sqlite3.SQLITE_OK)[1])
            else:
                db.set_progress_handler(lambda: (hits.append(1), 0)[1], 1)
            if observe:
                assert runtime.safety(fn, {'db': db, 'x': 9})
                assert hits == []
                assert runtime.observe(fn, inspect.signature(fn).bind(db, 9), axes={'x': [0, 9]})
                assert runtime.readings[0].status == 'grey' and runtime.readings[0].rows == []
            else:
                assert fn(db, 9)
            counts.append(len(hits))
    assert counts[0] > 0 and counts[1] == counts[0]


@pytest.mark.parametrize('query', ['SELECT 6', 'SELECT -6', 'SELECT +6', 'SELECT 0;'])
def test_plain_integer_literal_is_a_real_read_without_table_callbacks(tmp_path, query):
    fn, runtime = _runtime(tmp_path, query, statement='return db.execute(QUERY).fetchone()[0] <= x')
    with sqlite3.connect(':memory:') as db:
        assert runtime.observe(fn, inspect.signature(fn).bind(db, 9), axes={'x': [0, 9]})
    assert runtime.readings[0].status == 'ok'
    assert {row['x'] for row, value in runtime.readings[0].rows} == {0, 8, 9, 10}
