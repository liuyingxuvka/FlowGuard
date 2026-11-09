"""Call-site replay is refused before an effect happens, then voided (design 4.7).

Every replayed call (current code, baseline code swapped in, the original-value recheck) runs under one
guard in the replaying thread only. The audit hook refuses writes, processes, threads and network access;
sqlite3 connections refuse writing statements and return to a savepoint; arguments are deep copies; the
static check stops only explicit writes, so reads, dates and `.days` are replayed.
"""
import inspect
import json
import socket
import sqlite3
import subprocess
import sys
import textwrap
import threading
from pathlib import Path

import pytest

from flowguard.intent import runtime as R
from flowguard.intent.runtime import Runtime
from tests.intent_engine._cli_fixture import display_text
from tests.intent_engine.test_runtime_candidate import module


def _observe(tmp_path, source, call, *, old=None, axes=None, name='f'):
    m = module(tmp_path, textwrap.dedent(source))
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': textwrap.dedent(old or source)})
    fn = getattr(m, name)
    with runtime.hook(fn, axes=axes):
        outcome = call(fn)
    return m, runtime.readings[-1], outcome


def test_a_file_write_is_refused_before_it_happens_and_names_its_line(tmp_path):
    target = tmp_path / 'log.txt'
    m, reading, outcome = _observe(tmp_path, f'''
        def f(x: int):
            with open({str(target)!r}, 'a') as stream:
                stream.write('x')
            return x <= 3
    ''', lambda fn: fn(1), axes={'x': [0, 4]})
    assert outcome is True
    assert target.read_text() == 'x'                     # only the real call wrote
    assert reading.status == 'grey' and reading.rows == []
    assert reading.reasons[0].startswith('回放被拦住：r19_candidate.py:3 with open(')
    assert '写文件 ' + str(target) in reading.reasons[0]


def test_a_refusal_the_replayed_code_swallows_still_voids_the_replay(tmp_path):
    target = tmp_path / 'swallowed.txt'
    m, reading, outcome = _observe(tmp_path, f'''
        def f(x: int):
            try:
                open({str(target)!r}, 'w').close()
            except BaseException:
                pass
            return x <= 3
    ''', lambda fn: fn(1), axes={'x': [0, 4]})
    assert outcome is True and target.exists()
    assert reading.status == 'grey' and reading.rows == [] and '写文件' in reading.reasons[0]


@pytest.mark.parametrize('statement,what', [
    ("import subprocess; subprocess.run(['true'])", '启动子进程'),
    ("import os; os.system('true')", '执行 shell 命令'),
    ("import os, tempfile; os.remove(tempfile.gettempdir() + '/flowguard-never-there')", '删除文件'),
    ("import os, tempfile; os.mkdir(tempfile.gettempdir() + '/flowguard-never-made')", '新建目录'),
    ("import socket; socket.socket().connect(('127.0.0.1', 9))", '连接网络'),
    pytest.param("import threading; threading.Thread(target=print).start()", '启动线程', marks=pytest.mark.skipif(
        sys.version_info < (3, 12), reason='Python 3.11 raises no audit event when a thread starts')),
])
def test_processes_files_threads_and_network_are_refused(tmp_path, statement, what):
    m, reading, outcome = _observe(tmp_path, f'''
        def f(x: int):
            if x == 1:
                return True
            {statement}
            return x <= 3
    ''', lambda fn: fn(1), axes={'x': [0, 4]})
    assert outcome is True
    assert reading.status == 'grey' and what in reading.reasons[0], reading.reasons
    assert 'r19_candidate.py:5' in reading.reasons[0]


def _hires(db_path):
    db = sqlite3.connect(db_path)
    db.executescript('CREATE TABLE IF NOT EXISTS hires(item_id INTEGER); CREATE TABLE IF NOT EXISTS items(id, stock)')
    return db


HIRE = '''
    def hire_count(db, item_id: int, stock: int, reserved: int) -> int:
        db.execute("insert into hires(item_id) values (?)", (item_id,))
        (count,) = db.execute("select count(*) from hires").fetchone()
        return count + stock - reserved
'''


def test_database_writes_are_denied_rolled_back_and_the_connection_is_restored(tmp_path):
    db = _hires(tmp_path / 'h.db')
    before = db.total_changes
    m, reading, outcome = _observe(tmp_path, HIRE, lambda fn: fn(db, 1, 2, 1), name='hire_count',
                                   axes={'stock': [1, 2], 'reserved': [0, 1]})
    assert outcome == 2
    assert db.execute('SELECT count(*) FROM hires').fetchone()[0] == 1          # the real call only
    assert db.total_changes == before + 1
    assert reading.status == 'grey' and reading.rows == []
    assert reading.reasons[0] == ('回放被拦住：r19_candidate.py:3 db.execute("insert into hires(item_id) values (?)", '
                                  '(item_id,))：写数据库 INSERT hires')
    db.execute('INSERT INTO hires VALUES (5)')          # no authorizer was left behind
    assert db.execute('SELECT count(*) FROM hires').fetchone()[0] == 2
    assert not db.in_transaction or db.isolation_level is not None


def test_a_statement_prepared_before_the_replay_is_denied_too(tmp_path):
    db = _hires(tmp_path / 'h.db')
    m = module(tmp_path, textwrap.dedent(HIRE))
    assert m.hire_count(db, 1, 0, 0) == 1                # the INSERT is now in the statement cache
    db.commit()
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': textwrap.dedent(HIRE)})
    with runtime.hook(m.hire_count, axes={'stock': [1], 'reserved': [0]}):
        assert m.hire_count(db, 1, 2, 1) == 3
    assert db.execute('SELECT count(*) FROM hires').fetchone()[0] == 2
    assert runtime.readings[-1].status == 'grey' and 'INSERT' in runtime.readings[-1].reasons[0]


def test_an_open_transaction_of_the_test_survives_the_replay_savepoint(tmp_path):
    db = _hires(tmp_path / 'h.db')
    db.execute('INSERT INTO items VALUES (1, 2)')        # pending, not committed
    assert db.in_transaction
    source = '''
        def f(db, x: int):
            return db.execute("select stock from items").fetchone()[0] >= x
    '''
    m, reading, outcome = _observe(tmp_path, source, lambda fn: fn(db, 1), axes={'x': [0, 3]})
    assert outcome is True and reading.status == 'ok' and reading.rows
    assert db.in_transaction
    db.rollback()
    assert db.execute('SELECT count(*) FROM items').fetchone()[0] == 0


def test_connections_opened_during_a_replay_cannot_write_or_create_files(tmp_path):
    existing = tmp_path / 'existing.db'
    _hires(existing).close()
    created = tmp_path / 'created.db'
    for path, what in ((existing, '写数据库 INSERT'), (created, '新建数据库文件')):
        source = f'''
            import sqlite3
            def f(x: int):
                if x == 1:
                    return True
                db = sqlite3.connect({str(path)!r})
                db.execute("insert into hires values (1)")
                db.commit()
                return x <= 3
        '''
        m, reading, outcome = _observe(tmp_path, source, lambda fn: fn(1), axes={'x': [0, 4]})
        assert reading.status == 'grey' and what in reading.reasons[0], reading.reasons
    assert sqlite3.connect(existing).execute('SELECT count(*) FROM hires').fetchone()[0] == 0
    assert not created.exists()


def test_python_sql_functions_are_refused_in_the_statement_that_calls_them(tmp_path):
    hits = []
    with sqlite3.connect(':memory:') as db:
        db.create_function('touch', 0, lambda: hits.append(1) or 1)
        m, reading, outcome = _observe(tmp_path, '''
            def f(db, x: int):
                return db.execute("select touch()").fetchone()[0] <= x
        ''', lambda fn: fn(db, 1), axes={'x': [0, 2]})
    assert outcome is True and hits == [1]
    assert reading.status == 'grey' and 'SQL 函数 touch' in reading.reasons[0]


@pytest.mark.parametrize('kind', ['file', 'socket', 'driver', 'nested'])
def test_arguments_the_guard_cannot_see_into_are_not_replayed(tmp_path, kind):
    class Driver:
        def cursor(self): pass
        def commit(self): pass
        def rollback(self): pass
    class Holder:
        pass
    resource = {'file': lambda: open(tmp_path / 'out.txt', 'w'), 'socket': socket.socket,
                'driver': Driver, 'nested': lambda: Holder()}[kind]()
    if kind == 'nested':
        resource.inner = Holder()
        resource.inner.stream = open(tmp_path / 'deep.txt', 'w')
    try:
        m, reading, outcome = _observe(tmp_path, 'def f(context, x: int):\n    return x <= 3\n',
                                       lambda fn: fn(resource, 1), axes={'x': [0, 4]})
    finally:
        for value in (resource, getattr(getattr(resource, 'inner', None), 'stream', None)):
            if hasattr(value, 'close'):
                value.close()
    assert reading.status == 'grey' and reading.rows == []
    assert reading.reasons[0].startswith('看不清：参数 context'), reading.reasons
    if kind == 'nested':
        assert 'context.inner.stream' in reading.reasons[0]


def test_an_existing_authorizer_is_not_replaced_and_the_call_is_not_replayed(tmp_path):
    hits = []
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE t(n)')
        db.set_authorizer(lambda *args: (hits.append(args), sqlite3.SQLITE_OK)[1])
        m, reading, outcome = _observe(tmp_path, '''
            def f(db, x: int):
                return db.execute("select count(*) from t").fetchone()[0] <= x
        ''', lambda fn: fn(db, 1), axes={'x': [0, 2]})
        real = len(hits)
        db.execute('select n from t')
        assert len(hits) > real                          # still the test's own authorizer
    assert reading.status == 'grey' and '看不清' in reading.reasons[0] and 'authorizer' in reading.reasons[0]


def test_mutable_arguments_are_replayed_on_copies(tmp_path):
    config = {'allowed': True, 'calls': 0}
    m, reading, outcome = _observe(tmp_path, '''
        def f(config, x: int):
            config['calls'] += 1
            return config['allowed'] and x <= 3
    ''', lambda fn: fn(config, 1), axes={'x': [0, 4]})
    assert outcome is True and config['calls'] == 1
    assert reading.status == 'ok' and {row['x'] for row, _ in reading.rows} >= {0, 4}


def test_an_argument_that_cannot_be_copied_and_changes_voids_the_replay(tmp_path):
    class Counter:
        def __init__(self):
            self.calls = 0
        def __deepcopy__(self, memo):
            raise TypeError('not copyable')
    counter = Counter()
    m, reading, outcome = _observe(tmp_path, '''
        def f(counter, x: int):
            counter.calls += 1
            return x <= 3
    ''', lambda fn: fn(counter, 1), axes={'x': [0, 4]})
    assert outcome is True
    assert reading.status == 'grey' and '回放改了参数 counter' in reading.reasons[0]


@pytest.mark.parametrize('body,line', [
    ('global TOTAL\n    TOTAL = x', 2),
    ('CACHE[x] = True', 2),
    ('CACHE.update({x: True})', 2),
    ('helper(x)', 2),
])
def test_explicit_writes_to_module_state_stay_grey_statically(tmp_path, body, line):
    m, reading, outcome = _observe(tmp_path, f'''
TOTAL = 0
CACHE = {{}}
def helper(x):
    CACHE[x] = 1
def f(x: int):
    {body}
    return x <= 3
''', lambda fn: fn(1), axes={'x': [0, 4]})
    assert outcome is True and reading.status == 'grey'
    assert reading.reasons[0].startswith('明确的写操作：'), reading.reasons


def test_database_read_wrappers_dates_and_days_are_replayed(tmp_path):
    from datetime import date
    with sqlite3.connect(':memory:') as db:
        db.executescript("CREATE TABLE hires(id, due TEXT); INSERT INTO hires VALUES (1, '2026-11-01')")
        m, reading, outcome = _observe(tmp_path, '''
            from datetime import date
            def due_of(db, item_id):
                return date.fromisoformat(db.execute("select due from hires where id=?", (item_id,)).fetchone()[0])
            def f(db, item_id: int, today: date) -> bool:
                return (today - due_of(db, item_id)).days > 3
        ''', lambda fn: fn(db, 1, date(2026, 11, 9)))
    assert outcome is True
    assert reading.status == 'ok' and reading.rows, reading.reasons


def test_the_baseline_code_write_is_refused_with_its_baseline_line(tmp_path):
    old = '''
        def f(db, x: int):
            db.execute("UPDATE count SET n = n + 1")
            return x <= 3
    '''
    with sqlite3.connect(':memory:') as db:
        db.executescript('CREATE TABLE count(n); INSERT INTO count VALUES (0)')
        m, reading, outcome = _observe(tmp_path, 'def f(db, x: int):\n    return x <= 3\n', lambda fn: fn(db, 2),
                                       old=old, axes={'x': [2, 4]})
        assert db.execute('SELECT n FROM count').fetchone()[0] == 0
    assert reading.status == 'ok' and reading.rows and reading.comparison_status == 'grey'
    assert reading.comparison_reasons[0] == ('基准代码的回放被拦住：r19_candidate.py（基准）:3 '
                                             'db.execute("UPDATE count SET n = n + 1")：写数据库 UPDATE count')


def test_a_new_write_loses_the_observation_the_baseline_had(tmp_path):
    target = tmp_path / 'audit.txt'
    old = 'def f(x: int):\n    return x <= 3\n'
    now = f'def f(x: int):\n    open({str(target)!r}, "a").close()\n    return x <= 3\n'
    m, reading, outcome = _observe(tmp_path, now, lambda fn: fn(1), old=old, axes={'x': [0, 4]})
    assert reading.status == 'grey' and reading.lost == reading.reasons[0] and 'r19_candidate.py:2' in reading.lost
    both = now.replace('return x <= 3', 'return x <= 4')
    m, reading, outcome = _observe(tmp_path / 'both' if (tmp_path / 'both').mkdir() is None else tmp_path, both,
                                   lambda fn: fn(1), old=now, axes={'x': [0, 4]})
    assert reading.status == 'grey' and reading.lost == ''            # the baseline was grey as well


def test_only_the_replaying_thread_is_guarded(tmp_path):
    other = tmp_path / 'other-thread.txt'
    started, done = threading.Event(), threading.Event()
    def write():
        started.wait(10)
        other.write_text('written while a replay ran')
        done.set()
    worker = threading.Thread(target=write)
    worker.start()
    m = module(tmp_path, 'def f(x: int, started, done):\n    if not started.is_set():\n        started.set()\n'
                         '        done.wait(10)\n    return x <= 3\n')
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': (tmp_path / 'r19_candidate.py').read_text()})
    with runtime.hook(m.f, axes={'x': [0]}):
        assert m.f(1, started, done) is True
    worker.join(10)
    assert other.read_text() == 'written while a replay ran'


def test_the_audit_hook_is_installed_only_when_a_replay_first_runs(tmp_path):
    (tmp_path / 'hooked_module.py').write_text('def f(x: int):\n    return x <= 3\n')
    script = textwrap.dedent('''
        import sys, json
        sys.path.insert(0, sys.argv[1])
        sys.path.insert(0, sys.argv[2])
        from flowguard.intent import runtime as R
        before = R._HOOKED
        import inspect
        from hooked_module import f
        rt = R.Runtime(sys.argv[2], previous={})
        rt.observe(f, inspect.signature(f).bind(1), axes={'x': [0, 4]})
        print(json.dumps([before, R._HOOKED, R._CALLING, rt.readings[0].status]))
    ''')
    result = subprocess.run([sys.executable, '-c', script, str(Path(__file__).resolve().parents[2]), str(tmp_path)],
                            capture_output=True, text=True, timeout=60)
    assert json.loads(result.stdout) == [False, True, 0, 'ok'], result.stdout + result.stderr


def test_an_implicit_operator_that_writes_is_refused_at_its_own_line(tmp_path):
    target = tmp_path / 'operator.txt'
    m, reading, outcome = _observe(tmp_path, f'''
        class Money:
            def __le__(self, other):
                open({str(target)!r}, 'a').close()
                return True
        LIMIT = Money()
        def f(x: int):
            return LIMIT <= x
    ''', lambda fn: fn(1), axes={'x': [0, 4]})
    assert outcome is True and target.exists()
    assert reading.status == 'grey' and 'r19_candidate.py:4 ' in reading.reasons[0], reading.reasons


@pytest.mark.parametrize('definition', [
    'CREATE VIEW debt AS SELECT 1 AS n',
    'CREATE TABLE debt(base); INSERT INTO debt VALUES (1); CREATE TEMP TABLE debt(n); INSERT INTO debt VALUES (1)',
    'CREATE TABLE debt(base, n GENERATED ALWAYS AS (base+1)); INSERT INTO debt(base) VALUES (0)',
    "CREATE TABLE debt(n INTEGER); INSERT INTO debt VALUES ('text')",
])
def test_views_temp_tables_generated_columns_and_text_storage_are_read_without_writing(tmp_path, definition):
    with sqlite3.connect(':memory:') as db:
        db.executescript(definition)
        before = db.total_changes
        m, reading, outcome = _observe(tmp_path, '''
            def f(db, x: int):
                return db.execute("SELECT n FROM debt").fetchone()[0] != x
        ''', lambda fn: fn(db, 7), axes={'x': [0, 7]})
        assert db.total_changes == before
    assert reading.status == 'ok' and reading.rows, reading.reasons
