"""A call with an SQLite connection is never replayed: its callbacks see only the business call."""
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
                assert runtime.observe(fn, inspect.signature(fn).bind(db, 9))
                reading = runtime.readings[-1]
                assert reading.sample is None and reading.reasons == ['not JSON data'] and reading.rows == []
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
        assert runtime.observe(fn, inspect.signature(fn).bind(db, 7)) is True
        assert hits == []          # nothing calls typeof to prove the condition, and nothing replays the read
    reading, = runtime.readings
    assert reading.sample is None and reading.reasons == ['not JSON data'] and reading.rows == []


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
                assert runtime.observe(fn, inspect.signature(fn).bind(db, 9))
                reading = runtime.readings[-1]
                assert reading.sample is None and reading.reasons == ['not JSON data'] and reading.rows == []
            else:
                assert fn(db, 9)
            counts.append(len(hits))
    assert counts[0] > 0 and counts[1] == counts[0]
