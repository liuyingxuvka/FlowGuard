"""Real effects happen once; source-only comparisons refuse unsupported context.

Historical test names retain the old guarantee's identity. Automatic before-call grids,
resource snapshots and SQL guards are gone. Explicit sealed calls below check the
same isolation/refusal guarantees without claiming unobserved inputs were sampled.
"""
import inspect
import json
import os
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


def _sealed(module, reading, *, name='f', source=None):
    """Use the production source-only runner; never infer comparison from status=ok."""
    fn = getattr(module, name)
    if reading.sample is None:
        bound = inspect.signature(fn).bind(**reading.actual_inputs)
        args, kwargs = list(bound.args), dict(bound.kwargs)
    else:
        args, kwargs = reading.sample['args'], reading.sample['kwargs']
    return R.sealed(source or Path(module.__file__).read_text(), fn.__qualname__, args, kwargs)


def _unavailable(module, reading, **options):
    answer = _sealed(module, reading, **options)
    assert answer['status'] == 'unavailable', answer
    assert answer['reason']
    assert reading.rows == []  # ordinary observation did not manufacture a grid
    return answer['reason']


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
    assert reading.actual == ({'x': 1}, True)
    assert _unavailable(m, reading) == 'unsupported With'
    assert target.read_text() == 'x'


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
    assert _unavailable(m, reading) == 'unsupported Try'
    assert target.read_text() == '' and reading.actual == ({'x': 1}, True)


@pytest.mark.parametrize('statement,what', [
    ("import subprocess; subprocess.run(['true'])", 'start subprocess'),
    ("import os; os.system('true')", 'run shell command'),
    ("import os, tempfile; os.remove(tempfile.gettempdir() + '/flowguard-never-there')", 'remove file'),
    ("import os, tempfile; os.mkdir(tempfile.gettempdir() + '/flowguard-never-made')", 'create directory'),
    ("import socket; socket.socket().connect(('127.0.0.1', 9))", 'connect to network'),
    # Thread.start is refused before it registers the thread, on Python 3.11 (no audit event) too.
    ("import threading; threading.Thread(target=print).start()", 'start thread'),
    ("import _thread; _thread.start_new_thread(print, ())", 'start thread'),
    ("import os; os.chdir(os.getcwd())", 'change working directory'),
    pytest.param("import os; os.fchdir(os.open('.', os.O_RDONLY))", 'change working directory',
                 marks=pytest.mark.skipif(os.name == 'nt', reason='os.fchdir is POSIX only')),
    pytest.param("import os, tempfile; os.setxattr(tempfile.gettempdir(), 'user.flowguard', b'1')", 'change extended file attributes',
                 marks=pytest.mark.skipif(sys.platform != 'linux', reason='extended attributes are Linux only')),
    pytest.param("import os, tempfile; os.removexattr(tempfile.gettempdir(), 'user.flowguard')", 'remove extended file attributes',
                 marks=pytest.mark.skipif(sys.platform != 'linux', reason='extended attributes are Linux only')),
    pytest.param("import os; os.killpg(os.getpgid(0), 0)", 'signal process group',
                 marks=pytest.mark.skipif(os.name == 'nt', reason='process groups are POSIX only')),
    pytest.param("import signal, threading; signal.pthread_kill(threading.get_ident(), 0)", 'signal thread',
                 marks=pytest.mark.skipif(os.name == 'nt', reason='signal.pthread_kill is POSIX only')),
    # No audit event: wrapped while a replayed call runs.
    pytest.param("import os, tempfile; os.mkfifo(tempfile.gettempdir() + '/flowguard-never-made-fifo')", 'create named pipe',
                 marks=pytest.mark.skipif(os.name == 'nt', reason='os.mkfifo is POSIX only')),
    pytest.param("import os, stat, tempfile; os.mknod(tempfile.gettempdir() + '/flowguard-never-made-node', stat.S_IFREG)",
                 'create device file', marks=pytest.mark.skipif(os.name == 'nt', reason='os.mknod is POSIX only')),
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
    assert reading.actual == ({'x': 1}, True)
    assert _unavailable(m, reading) == 'unsupported Import'


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
    assert reading.sample is None and reading.actual_inputs['db'] is db
    _unavailable(m, reading, name='hire_count')
    assert db.total_changes == before + 1
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
    assert runtime.readings[-1].sample is None
    _unavailable(m, runtime.readings[-1], name='hire_count')
    assert db.execute('SELECT count(*) FROM hires').fetchone()[0] == 2


def test_an_open_transaction_of_the_test_survives_the_replay_savepoint(tmp_path):
    db = _hires(tmp_path / 'h.db')
    db.execute('INSERT INTO items VALUES (1, 2)')        # pending, not committed
    assert db.in_transaction
    source = '''
        def f(db, x: int):
            return db.execute("select stock from items").fetchone()[0] >= x
    '''
    m, reading, outcome = _observe(tmp_path, source, lambda fn: fn(db, 1), axes={'x': [0, 3]})
    assert outcome is True and reading.actual_inputs['db'] is db
    assert reading.sample is None
    _unavailable(m, reading)
    assert db.in_transaction
    db.rollback()
    assert db.execute('SELECT count(*) FROM items').fetchone()[0] == 0


def test_connections_opened_during_a_replay_cannot_write_or_create_files(tmp_path):
    existing = tmp_path / 'existing.db'
    _hires(existing).close()
    created = tmp_path / 'created.db'
    for path, what in ((existing, 'write database INSERT'), (created, 'create database file')):
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
        assert outcome is True and reading.actual == ({'x': 1}, True)
        _unavailable(m, reading)
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
    assert reading.sample is None and reading.actual[1] is True
    _unavailable(m, reading)
    assert hits == [1]


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
    assert reading.sample is None and reading.actual_inputs['context'] is resource
    assert reading.reasons == ['not JSON data']
    _unavailable(m, reading)


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
    assert reading.sample is None and reading.actual_inputs['db'] is db
    _unavailable(m, reading)


def test_mutable_arguments_are_replayed_on_copies(tmp_path):
    config = {'allowed': True, 'calls': 0}
    m, reading, outcome = _observe(tmp_path, '''
        def f(config, x: int):
            config['calls'] += 1
            return config['allowed'] and x <= 3
    ''', lambda fn: fn(config, 1), axes={'x': [0, 4]})
    assert outcome is True and config['calls'] == 1
    assert reading.sample['inputs']['config'] == {'allowed': True, 'calls': 0}
    assert _sealed(m, reading) == {'status': 'ok', 'value': True}
    rows = {x: R.sealed(Path(m.__file__).read_text(), 'f', [reading.sample['args'][0], x], {}) for x in (0, 4)}
    assert rows == {0: {'status': 'ok', 'value': True}, 4: {'status': 'ok', 'value': False}}
    assert config == {'allowed': True, 'calls': 1}


def test_an_argument_that_cannot_be_copied_is_not_replayed(tmp_path):
    # Replaying on the original would change the test's own object (design 4.7 compared it afterwards,
    # which cannot see into nested state): an argument deepcopy refuses is not replayed at all.
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
    assert outcome is True and counter.calls == 1          # only the real call ran
    assert reading.sample is None and reading.actual_inputs['counter'] is counter
    assert reading.reasons == ['not JSON data']
    _unavailable(m, reading)
    assert counter.calls == 1


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
    assert outcome is True and reading.actual == ({'x': 1}, True)
    before = m.TOTAL, dict(m.CACHE)
    if body in ('CACHE[x] = True', 'helper(x)'):
        assert _sealed(m, reading) == {'status': 'ok', 'value': True}
    else:
        _unavailable(m, reading)
    assert (m.TOTAL, m.CACHE) == before


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
    assert reading.sample is None and reading.actual[1] is True
    assert reading.actual_inputs['today'] == date(2026, 11, 9)
    _unavailable(m, reading)


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
    assert reading.sample is None and reading.actual[1] is True
    _unavailable(m, reading)
    _unavailable(m, reading, source=textwrap.dedent(old))


def test_a_new_write_loses_the_observation_the_baseline_had(tmp_path):
    target = tmp_path / 'audit.txt'
    old = 'def f(x: int):\n    return x <= 3\n'
    now = f'def f(x: int):\n    open({str(target)!r}, "a").close()\n    return x <= 3\n'
    m, reading, outcome = _observe(tmp_path, now, lambda fn: fn(1), old=old, axes={'x': [0, 4]})
    assert reading.actual == ({'x': 1}, True) and target.exists()
    _unavailable(m, reading)
    assert _sealed(m, reading, source=old) == {'status': 'ok', 'value': True}
    both = now.replace('return x <= 3', 'return x <= 4')
    m, reading, outcome = _observe(tmp_path / 'both' if (tmp_path / 'both').mkdir() is None else tmp_path, both,
                                   lambda fn: fn(1), old=now, axes={'x': [0, 4]})
    assert reading.actual == ({'x': 1}, True)
    _unavailable(m, reading)
    _unavailable(m, reading, source=now)


def test_only_the_replaying_thread_is_guarded(tmp_path):
    other = tmp_path / 'other-thread.txt'
    started, done = threading.Event(), threading.Event()
    def write():
        started.wait(10)
        other.write_text('written while a replay ran')
        done.set()
    worker = threading.Thread(target=write)
    worker.start()
    # The events are module state: an Event argument cannot be copied, and such an argument is not replayed.
    m = module(tmp_path, 'STARTED = DONE = None\ndef f(x: int):\n    if not STARTED.is_set():\n        STARTED.set()\n'
                         '        DONE.wait(10)\n    return x <= 3\n')
    m.STARTED, m.DONE = started, done
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': (tmp_path / 'r19_candidate.py').read_text()})
    with runtime.hook(m.f, axes={'x': [0]}):
        assert m.f(1) is True
    worker.join(10)
    assert other.read_text() == 'written while a replay ran'
    assert runtime.readings[-1].actual == ({'x': 1}, True)
    _unavailable(m, runtime.readings[-1])
    assert done.is_set() and not worker.is_alive()


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
        after_real = R._HOOKED
        answer = R.sealed('def f(x): return x <= 3', 'f', [1], {})
        print(json.dumps([before, after_real, R._HOOKED, R._CALLING, answer['status']]))
    ''')
    result = subprocess.run([sys.executable, '-c', script, str(Path(__file__).resolve().parents[2]), str(tmp_path)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == [False, False, True, 0, 'ok'], result.stdout + result.stderr


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
    _unavailable(m, reading)
    assert target.read_text() == '' and reading.actual == ({'x': 1}, True)


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
    assert reading.sample is None and reading.actual_inputs['db'] is db
    _unavailable(m, reading)


def test_a_class_passed_as_an_argument_is_looked_into_through_its_own_namespace(tmp_path):
    # A classmethod's `cls`: the instance `__dict__` descriptor does not apply to the class itself.
    # Class/instance identity is preserved in real readings; no resource walker inspects it.
    class Policy:
        limit = 3

        @classmethod
        def accept(cls, days):
            return days <= cls.limit

    m, reading, outcome = _observe(tmp_path, 'def f(policy, days): return policy.accept(days)\n',
                                   lambda fn: fn(Policy, 2))
    assert outcome is True and Policy.limit == 3 and vars(Policy()) == {}
    assert reading.sample is None and reading.actual_inputs['policy'] is Policy
    _unavailable(m, reading)
    with open(tmp_path / 'log.txt', 'w') as log:
        class Holder:
            output = log
        assert R.sealed('def f(cls): return True', 'f', [Holder], {}) == {
            'status': 'unavailable', 'reason': 'not JSON data'}
        assert not log.closed and log.tell() == 0



# ---- what a replay cannot copy or see into is not replayed (round 20 review) ---------------------------------

def _uncopyable_cases(tmp_path):
    """(argument, what the function does with it, how many times the real effect happened, why it is unseen)."""
    import csv
    import logging
    import queue
    from concurrent.futures import ThreadPoolExecutor
    lines = tmp_path / 'lines.txt'
    lines.write_text(''.join(f'line{i}\n' for i in range(20)))
    events = []
    rows = tmp_path / 'rows.csv'
    rows_stream = open(rows, 'w', newline='')
    log = tmp_path / 'arg.log'
    logger = logging.getLogger('flowguard.test.replay.arg')
    logger.propagate = False
    handler = logging.FileHandler(log, encoding='utf-8')
    logger.addHandler(handler)
    pool = ThreadPoolExecutor(1)
    jobs = queue.Queue()
    class Locked:
        def __init__(self):
            self.lock = threading.Lock()
            self.items = {}
    locked = Locked()
    reader = open(lines, encoding='utf-8')
    return {
        'generator': ((i for i in range(100)), 'next(value)', lambda value: next(value) == 1, 'is a generator or coroutine'),
        'readable file': (reader, 'value.readline()', lambda value: value.readline() == 'line1\n', 'is an open file'),
        'csv writer': (csv.writer(rows_stream), "value.writerow(['row'])",
                       lambda value: (rows_stream.flush(), len(rows.read_text().splitlines()))[1] == 1, 'is a csv reader or writer'),
        'csv reader': (csv.reader(open(lines, encoding='utf-8')), 'next(value)', lambda value: next(value) == ['line1'],
                       'is a csv reader or writer'),
        'builtin bound method': (events.append, "value('called')", lambda value: events == ['called'], 'is a function or bound method'),
        'closure': (lambda item: events.append(item), "value('called')", lambda value: events == ['called'], 'is a function or bound method'),
        'logger': (logger, "value.warning('called')", lambda value: (handler.flush(), len(log.read_text(encoding='utf-8').splitlines()))[1] == 1,
                   'is a logging logger'),
        'executor': (pool, "value.submit(print).result()", lambda value: True, 'is a queue or thread pool'),
        'queue': (jobs, 'value.put(1)', lambda value: value.qsize() == 1, 'is a queue or thread pool'),
        'nested uncopyable': (locked, "value.items.setdefault('calls', []).append(1)",
                              lambda value: value.items == {'calls': [1]}, 'cannot be copied'),
    }, [rows_stream, reader, handler, pool]


@pytest.mark.parametrize('kind', ['generator', 'readable file', 'csv writer', 'csv reader', 'builtin bound method',
                                  'closure', 'logger', 'executor', 'queue', 'nested uncopyable'])
def test_arguments_a_replay_could_only_share_with_the_test_are_not_replayed(tmp_path, kind):
    cases, resources = _uncopyable_cases(tmp_path)
    value, statement, once, why = cases[kind]
    try:
        m, reading, outcome = _observe(tmp_path, f'''
            def f(value, x: int):
                {statement}
                return x <= 3
        ''', lambda fn: fn(value, 1), old='def f(value, x: int):\n    return x <= 3\n', axes={'x': [0, 4]})
        assert outcome is True
        assert reading.sample is None and reading.rows == [] and reading.changed == []
        assert reading.actual_inputs['value'] is value and reading.actual[1] is True
        assert reading.reasons == ['not JSON data']
        _unavailable(m, reading)
        assert once(value), 'the replay acted on the test\'s own object'
    finally:
        for resource in resources:
            (resource.shutdown if hasattr(resource, 'shutdown') else resource.close)()


def test_a_sqlite_blob_argument_is_not_replayed(tmp_path):
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE b(v BLOB)')
        db.execute('INSERT INTO b VALUES (zeroblob(1))')
        blob = db.blobopen('b', 'v', 1)
        m, reading, outcome = _observe(tmp_path, '''
            def f(blob, x: int):
                blob.seek(0)
                n = blob.read(1)[0]
                blob.seek(0)
                blob.write(bytes([n + 1]))
                return x <= 3
        ''', lambda fn: fn(blob, 1), axes={'x': [0, 4]})
        blob.close()
        assert db.execute('SELECT v FROM b').fetchone()[0] == b'\x01'      # the real call only
    assert reading.sample is None and reading.actual_inputs['blob'] is blob
    _unavailable(m, reading)


def test_a_sqlite_connection_at_any_depth_is_protected(tmp_path):
    db = _hires(tmp_path / 'deep.db')
    db.commit()
    class Repository:
        def __init__(self, db):
            self.db = db
    context = {'a': {'b': [Repository(db)]}}
    m, reading, outcome = _observe(tmp_path, '''
        def f(context, x: int):
            context['a']['b'][0].db.execute("insert into hires values (1)")
            return x <= 3
    ''', lambda fn: fn(context, 1), old='def f(context, x: int):\n    return x <= 3\n', axes={'x': [0, 4]})
    assert outcome is True
    assert db.execute('SELECT count(*) FROM hires').fetchone()[0] == 1
    assert reading.sample is None and reading.actual_inputs['context'] is context
    _unavailable(m, reading)
    assert db.execute('SELECT count(*) FROM hires').fetchone()[0] == 1


def test_an_argument_too_large_to_look_through_is_not_replayed(tmp_path, monkeypatch):
    items = [{'n': index} for index in range(100)]
    m, reading, outcome = _observe(tmp_path, 'def f(items, x: int):\n    return x <= 3\n',
                                   lambda fn: fn(items, 1), axes={'x': [0, 4]})
    assert outcome is True and reading.sample['inputs']['items'] == items
    assert len(reading.sample['inputs']['items']) == 100
    assert _sealed(m, reading) == {'status': 'ok', 'value': True}
    # Strict JSON checks the whole input, so an opaque value beyond the old 50-object
    # inspection budget is refused, rather than hidden behind a traversal limit.
    with open(tmp_path / 'hidden.txt', 'w') as stream:
        items[-1]['resource'] = stream
        runtime = Runtime(tmp_path, previous={})
        with runtime.hook(m.f):
            assert m.f(items, 1) is True
        hidden = runtime.readings[-1]
        assert hidden.sample is None and hidden.actual_inputs['items'] is items
        assert hidden.reasons == ['not JSON data']
        _unavailable(m, hidden)
        assert stream.tell() == 0 and not stream.closed



# ---- process-wide state: the random module and the working directory --------------------------------------

def test_the_random_state_after_the_call_is_the_one_real_calls(tmp_path):
    import random
    random.seed(7)
    random.random()
    expected = random.random()
    random.seed(7)
    m, reading, outcome = _observe(tmp_path, '''
        import random
        def f(x: int):
            random.random()
            return x <= 3
    ''', lambda fn: fn(1), axes={'x': [0, 4]})
    assert outcome is True and reading.actual == ({'x': 1}, True)
    _unavailable(m, reading)
    assert random.random() == expected


# ---- explicit writes to module state, through modules, classes, aliases and standard calls --------------------

MODULE_STATE = '''
import bisect
import heapq
import random
import r19_settings
CALLS = []
CACHE = {}
ITEMS = [{'n': 0}]
TICKETS = iter(range(100))
class Stats:
    calls = 0
    seen = []
def module_attribute(x: int):
    r19_settings.LIMIT += 1
    return x <= 3
def module_item(x: int):
    r19_settings.ITEMS.append(x)
    return x <= 3
def class_attribute(x: int):
    Stats.calls += 1
    return x <= 3
def class_item(x: int):
    Stats.seen.append(x)
    return x <= 3
def local_alias(x: int):
    cache = CACHE
    cache['k'] = x
    return x <= 3
def module_alias(x: int):
    settings = r19_settings
    settings.LIMIT = x
    return x <= 3
def body_import(x: int):
    import r19_settings as settings
    settings.LIMIT = x
    return x <= 3
def loop_alias(x: int):
    for item in ITEMS:
        item['n'] += 1
    return x <= 3
def heap(x: int):
    heapq.heappush(CALLS, x)
    return x <= 3
def insort(x: int):
    bisect.insort(CALLS, x)
    return x <= 3
def unbound(x: int):
    list.append(CALLS, x)
    return x <= 3
def consumed(x: int):
    next(TICKETS)
    return x <= 3
def shuffled(x: int):
    random.shuffle(CALLS)
    return x <= 3
def set_attribute(x: int):
    setattr(r19_settings, 'LIMIT', x)
    return x <= 3
'''


@pytest.mark.parametrize('name,statement,after', [
    ('module_attribute', 'r19_settings.LIMIT += 1', lambda m, s: s.LIMIT == 4),
    ('module_item', 'r19_settings.ITEMS.append(x)', lambda m, s: s.ITEMS == [1]),
    ('class_attribute', 'Stats.calls += 1', lambda m, s: m.Stats.calls == 1),
    ('class_item', 'Stats.seen.append(x)', lambda m, s: m.Stats.seen == [1]),
    ('local_alias', "cache['k'] = x", lambda m, s: m.CACHE == {'k': 1}),
    ('module_alias', 'settings.LIMIT = x', lambda m, s: s.LIMIT == 1),
    ('body_import', 'settings.LIMIT = x', lambda m, s: s.LIMIT == 1),
    ('loop_alias', "item['n'] += 1", lambda m, s: m.ITEMS == [{'n': 1}]),
    ('heap', 'heapq.heappush(CALLS, x)', lambda m, s: m.CALLS == [1]),
    ('insort', 'bisect.insort(CALLS, x)', lambda m, s: m.CALLS == [1]),
    ('unbound', 'list.append(CALLS, x)', lambda m, s: m.CALLS == [1]),
    ('consumed', 'next(TICKETS)', lambda m, s: next(m.TICKETS) == 1),
    ('shuffled', 'random.shuffle(CALLS)', lambda m, s: m.CALLS == []),
    ('set_attribute', "setattr(r19_settings, 'LIMIT', x)", lambda m, s: s.LIMIT == 1),
])
def test_writes_through_modules_classes_aliases_and_standard_calls_stay_grey(tmp_path, monkeypatch, name, statement, after):
    (tmp_path / 'r19_settings.py').write_text('LIMIT = 3\nITEMS = []\n')
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, 'r19_settings', raising=False)
    import r19_settings
    m, reading, outcome = _observe(tmp_path, MODULE_STATE, lambda fn: fn(1), axes={'x': [0, 4]}, name=name)
    assert outcome is True and after(m, r19_settings), 'the replay changed module state'
    lines = MODULE_STATE.splitlines()
    line = next(index for index, text in enumerate(lines, 1) if text.strip() == statement
                and any(lines[i].startswith(f'def {name}(') for i in range(max(0, index - 4), index)))
    assert reading.actual == ({'x': 1}, True)
    if name in ('local_alias', 'loop_alias'):
        assert _sealed(m, reading, name=name) == {'status': 'ok', 'value': True}
    else:
        _unavailable(m, reading, name=name)
    if name == 'consumed':
        # The original `after` check above already consumed item 1 itself.
        assert next(m.TICKETS) == 2
    else:
        assert after(m, r19_settings), 'sealed comparison changed live module state'


def test_reads_dates_days_and_calls_on_fresh_objects_stay_replayable(tmp_path, monkeypatch):
    (tmp_path / 'r19_settings.py').write_text('LIMIT = 3\nITEMS = [1]\n')
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, 'r19_settings', raising=False)
    from datetime import date
    m, reading, outcome = _observe(tmp_path, '''
        import collections
        import math
        import os
        from datetime import date
        import r19_settings
        CACHE = {'k': 1}
        class Stats:
            calls = 3
        def f(x: int, today: date):
            window = r19_settings.LIMIT + Stats.calls + len(CACHE) + CACHE.get('k', 0) + len(r19_settings.ITEMS)
            counts = collections.Counter([x])
            counts.update([x])
            days = (today - date(2026, 1, 1)).days
            return math.floor(x) + window + counts[x] + days > 0 and bool(os.path.join('a', 'b'))
    ''', lambda fn: fn(1, date(2026, 11, 9)), axes={'x': [0, 4]})
    assert outcome is True
    assert reading.sample is None and reading.actual_inputs['today'] == date(2026, 11, 9)
    _unavailable(m, reading)


# ---- the guard's own restoring: grey first, every connection restored, the real call still runs -------------

def test_a_reading_stays_grey_when_the_replay_does_not_finish(tmp_path, monkeypatch):
    def broken(source, qual, imports=None):
        raise RuntimeError('FlowGuard itself failed')
    m = module(tmp_path, 'CALLS = 0\ndef f(x: int):\n    global CALLS\n    CALLS += 1\n    return x <= 3\n')
    runtime = Runtime(tmp_path, previous={})
    with runtime.hook(m.f):
        assert m.f(1) is True
    reading = runtime.readings[-1]
    monkeypatch.setattr(R, '_closed', broken)
    with pytest.raises(RuntimeError, match='FlowGuard itself failed'):
        _sealed(m, reading)
    assert reading.actual == ({'x': 1}, True) and m.CALLS == 1
    assert reading.rows == [] and reading.changed == []
    assert R._CALLING == 0 and R._LOCAL.guard is None



# Called through getattr, which the static check does not follow: what the guard does at run time.
HELPERS = '''
def unlock(db):
    getattr(db, 'set_authorizer')(None)
    db.commit()
def shut(db):
    getattr(db, 'close')()
'''


def test_a_replay_that_ends_the_savepoint_is_grey_and_the_real_call_still_runs(tmp_path):
    db = _hires(tmp_path / 'unlock.db')
    db.commit()
    source = HELPERS + '''
def f(db, x: int):
    unlock(db)
    db.execute("insert into hires values (?)", (x,))
    db.commit()
    return x <= 3
'''
    m, reading, outcome = _observe(tmp_path, source, lambda fn: fn(db, 1), old=HELPERS + 'def f(db, x: int):\n    return x <= 3\n',
                                   axes={'x': [0, 4]})
    assert outcome is True
    assert db.execute('SELECT item_id FROM hires').fetchall() == [(1,)]        # the real call's row only
    assert reading.sample is None and reading.actual[1] is True
    _unavailable(m, reading)
    assert db.execute('SELECT item_id FROM hires').fetchall() == [(1,)]
    assert not db.in_transaction and db.execute('PRAGMA query_only').fetchone()[0] == 0
    db.execute('INSERT INTO hires VALUES (5)')          # no authorizer was left behind


def test_a_connection_a_replay_closes_does_not_keep_the_others_protected(tmp_path):
    a, b = _hires(tmp_path / 'a.db'), _hires(tmp_path / 'b.db')
    a.commit()
    b.commit()
    source = HELPERS + '''
def f(a, b, x: int):
    if x != 1:
        shut(b)
    return a.execute("select count(*) from hires").fetchone()[0] <= x
'''
    m, reading, outcome = _observe(tmp_path, source, lambda fn: fn(a, b, 1),
                                   old=HELPERS + 'def f(a, b, x: int):\n    return a.execute("select count(*) from hires").fetchone()[0] <= x\n',
                                   axes={'x': [0, 4]})
    assert outcome is True
    assert reading.sample is None and reading.actual_inputs['a'] is a and reading.actual_inputs['b'] is b
    _unavailable(m, reading)
    assert b.execute('SELECT count(*) FROM hires').fetchone()[0] == 0
    # The connection that stayed open has its usual behaviour back: no authorizer, no savepoint, writable.
    assert not a.in_transaction and a.execute('PRAGMA query_only').fetchone()[0] == 0
    a.execute('INSERT INTO hires VALUES (5)')
    a.commit()
    assert a.execute('SELECT count(*) FROM hires').fetchone()[0] == 1


@pytest.mark.parametrize('body,line,where', [
    ('if x != 1:\n        db.close()', 7, 'db method close'),
    ('if x != 1:\n        shut(db)', 3, 'connection method close'),        # followed into the helper
    ('if x != 1:\n        db.row_factory = sqlite3.Row', 7, 'db row_factory'),
    ("if x != 1:\n        db.create_function('leak', 0, len)", 7, 'db method create_function'),
])
def test_a_change_to_a_shared_connection_is_an_explicit_write(tmp_path, body, line, where):
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE t(n)')
        m, reading, outcome = _observe(tmp_path, f'''
def shut(connection):
    connection.close()
def f(db, x: int):
    {body}
    return x <= 3
'''.replace('def f', 'import sqlite3\ndef f', 1), lambda fn: fn(db, 1), axes={'x': [0, 4]})
        assert outcome is True
        assert db.execute('SELECT count(*) FROM t').fetchone()[0] == 0 and db.row_factory is None      # untouched
    assert reading.sample is None and reading.actual_inputs['db'] is db
    _unavailable(m, reading)


# ---- sqlite3: connections bound before the replay, backups, Blobs and callbacks -------------------------------

def test_a_connection_opened_through_an_alias_is_refused_before_it_opens(tmp_path):
    path = tmp_path / 'alias.db'
    _hires(path).close()
    m, reading, outcome = _observe(tmp_path, f'''
        from sqlite3 import connect
        def f(x: int):
            db = connect({str(path)!r})
            db.execute("insert into hires values (1)")
            db.commit()
            db.close()
            return x <= 3
    ''', lambda fn: fn(1), axes={'x': [0, 4]})
    assert outcome is True
    assert sqlite3.connect(path).execute('SELECT count(*) FROM hires').fetchone()[0] == 1
    assert reading.actual == ({'x': 1}, True)
    _unavailable(m, reading)
    assert sqlite3.connect(path).execute('SELECT count(*) FROM hires').fetchone()[0] == 1


@pytest.mark.parametrize('direction', ['into a new connection', 'into the shared connection'])
def test_a_backup_into_a_protected_connection_is_refused(tmp_path, direction):
    target = tmp_path / 'target.db'
    with sqlite3.connect(target) as setup:
        setup.execute('CREATE TABLE marker(n)')
    db = sqlite3.connect(target if direction == 'into the shared connection' else ':memory:')
    if direction == 'into a new connection':
        db.execute('CREATE TABLE copied(n)')
    copy = (f'copy(db, sqlite3.connect({str(target)!r}))' if direction == 'into a new connection'
            else 'copy(sqlite3.connect(":memory:"), db)')
    source = f'''
import sqlite3
def copy(source, target):
    getattr(source, 'backup')(target)
def f(db, x: int):
    if x != 1:
        {copy}
    return x <= 3
'''
    m, reading, outcome = _observe(tmp_path, source, lambda fn: fn(db, 1), axes={'x': [0, 4]})
    assert outcome is True
    db.close()
    assert [row[0] for row in sqlite3.connect(target).execute('SELECT name FROM sqlite_master')] == ['marker']
    assert reading.sample is None and reading.actual_inputs['db'] is db
    _unavailable(m, reading)
    assert [row[0] for row in sqlite3.connect(target).execute('SELECT name FROM sqlite_master')] == ['marker']


def test_a_blob_write_on_a_shared_connection_is_refused(tmp_path):
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE b(v BLOB)')
        db.execute('INSERT INTO b VALUES (zeroblob(1))')
        db.commit()
        m, reading, outcome = _observe(tmp_path, '''
            def bump(db):
                with getattr(db, 'blobopen')('b', 'v', 1) as blob:
                    blob.write(b'\\x05')
            def f(db, x: int):
                if x != 1:
                    bump(db)
                return x <= 3
        ''', lambda fn: fn(db, 1), axes={'x': [0, 4]})
        assert db.execute('SELECT v FROM b').fetchone()[0] == b'\x00'
    assert reading.sample is None and reading.actual[1] is True
    _unavailable(m, reading)


@pytest.mark.parametrize('change', ["getattr(db, 'create_function')('leak', 0, len)",
                                    "getattr(db, 'set_trace_callback')(print)"])
def test_a_callback_a_replay_gives_a_shared_connection_voids_the_replay(tmp_path, change, capsys):
    with sqlite3.connect(':memory:') as db:
        m, reading, outcome = _observe(tmp_path, f'''
            def f(db, x: int):
                if x != 1:
                    {change}
                return x <= 3
        ''', lambda fn: fn(db, 1), axes={'x': [0, 4]})
        assert outcome is True
        assert reading.sample is None
        _unavailable(m, reading)
        if 'create_function' in change:
            with pytest.raises(sqlite3.OperationalError, match='no such function: leak'):
                db.execute("SELECT leak('x')")
        else:
            assert db.execute('SELECT 1').fetchone() == (1,)
            assert capsys.readouterr().out == ''


# ---- open resources in module state; log records ------------------------------------------------------------

def test_open_resources_in_module_state_are_not_replayed_and_connections_there_are_protected(tmp_path):
    log, store = tmp_path / 'global.log', tmp_path / 'global.db'
    _hires(store).close()
    m, reading, outcome = _observe(tmp_path, f'''
        import sqlite3
        LOG = open({str(log)!r}, 'a')
        DB = sqlite3.connect({str(store)!r})
        def note():
            print('called', file=LOG, flush=True)
        def written(x: int):
            note()
            return x <= 3
        def stored(x: int):
            DB.execute("insert into hires values (1)")
            return x <= 3
        def counted(x: int):
            return DB.execute("select count(*) from hires").fetchone()[0] <= x
    ''', lambda fn: fn(1), axes={'x': [0, 4]}, name='written')
    assert outcome is True and len(log.read_text().splitlines()) == 1
    _unavailable(m, reading, name='written')
    assert len(log.read_text().splitlines()) == 1
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': (tmp_path / 'r19_candidate.py').read_text()})
    with runtime.hook(m.stored, axes={'x': [0, 4]}):
        assert m.stored(1) is True
    m.DB.commit()
    assert sqlite3.connect(store).execute('SELECT count(*) FROM hires').fetchone()[0] == 1
    _unavailable(m, runtime.readings[-1], name='stored')
    assert sqlite3.connect(store).execute('SELECT count(*) FROM hires').fetchone()[0] == 1
    with runtime.hook(m.counted, axes={'x': [0, 4]}):
        assert m.counted(1) is True
    assert runtime.readings[-1].actual == ({'x': 1}, True)
    _unavailable(m, runtime.readings[-1], name='counted')
    m.LOG.close()
    m.DB.close()


def test_log_records_of_a_replayed_call_are_dropped(tmp_path, caplog):
    import logging
    caplog.set_level(logging.WARNING)
    m, reading, outcome = _observe(tmp_path, '''
        import logging
        def f(x: int):
            logging.getLogger('flowguard.test.replay').warning('checked %s', x)
            return x <= 3
    ''', lambda fn: fn(1), axes={'x': [0, 4]})
    assert outcome is True and reading.actual == ({'x': 1}, True)
    _unavailable(m, reading)
    assert [record.getMessage() for record in caplog.records] == ['checked 1']


# ---- clocks, recursion and time --------------------------------------------------------------------------

def test_a_clock_reading_function_is_grey_on_a_coarse_clock(tmp_path, monkeypatch):
    import time
    real = time.time
    monkeypatch.setattr(time, 'time', lambda: (real() * 64 // 1) / 64)     # Windows' 1/64 second
    for _ in range(5):
        m, reading, outcome = _observe(tmp_path, '''
            import time
            def f(x: int) -> float:
                return time.time() + x
        ''', lambda fn: fn(1), axes={'x': [0, 4]})
        assert type(outcome) is float and reading.actual[1] == outcome
        _unavailable(m, reading)


def test_a_replay_that_runs_too_long_is_interrupted_and_grey(tmp_path, monkeypatch):
    from flowguard.intent import owners
    monkeypatch.setattr(owners, 'TIMEOUT', 0.3)
    m, reading, outcome = _observe(tmp_path, '''
        def f(x: int):
            while x != 1:
                pass
            return True
    ''', lambda fn: fn(1), old='def f(x: int):\n    return True\n', axes={'x': [0, 4]})
    assert outcome is True
    assert reading.actual == ({'x': 1}, True)
    assert _sealed(m, reading) == {'status': 'ok', 'value': True}
    assert R.sealed(Path(m.__file__).read_text(), 'f', [0], {}) == {
        'status': 'unavailable', 'reason': 'exceeded 0.3 seconds without completion'}
    assert R._CALLING == 0 and R._LOCAL.guard is None


def test_a_replay_that_recurses_too_deeply_is_grey(tmp_path):
    m, reading, outcome = _observe(tmp_path, '''
        def f(x: int):
            if x == 1:
                return True
            return f(x)
    ''', lambda fn: fn(1), axes={'x': [0, 4]})
    assert outcome is True
    assert reading.actual == ({'x': 1}, True)
    assert _sealed(m, reading) == {'status': 'ok', 'value': True}
    answer = R.sealed(Path(m.__file__).read_text(), 'f', [0], {})
    assert answer['status'] == 'raised' and answer['error']['type'] == 'RecursionError'
    assert R._CALLING == 0 and R._LOCAL.guard is None


def test_an_interruption_that_arrived_leaves_a_traced_thread_running(tmp_path):
    # Withdrawing a delivered interruption with a NULL exception left Python 3.11's eval breaker set: the
    # next call of a traced thread (coverage, FlowGuard's own 3.11 observer) looped at its first instruction.
    script = textwrap.dedent('''
        import sys
        sys.path.insert(0, sys.argv[1])
        from flowguard.intent import owners
        def trace(frame, event, arg):
            return trace
        sys.settrace(trace)
        def helper():
            return 'still running'
        try:
            with owners.watchdog(0.05):
                while True:
                    pass
        except owners._Timeout:
            pass
        print(helper())
    ''')
    result = subprocess.run([sys.executable, '-c', script, str(Path(__file__).resolve().parents[2])],
                            capture_output=True, text=True, timeout=60)
    assert result.stdout.strip() == 'still running', result.stdout + result.stderr
