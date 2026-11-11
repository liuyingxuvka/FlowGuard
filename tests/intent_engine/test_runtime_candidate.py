"""Independent runtime-level guarantees replacing retired execution mechanics."""
import importlib.util
import inspect
from pathlib import Path
import sqlite3
import sys

import pytest

from flowguard.intent import cells
from flowguard.intent.runtime import Runtime
from tests.intent_engine._sealed_fixture import comparable, differs, sealed_pair, value

FILE = 'r19_candidate.py'


def module(tmp_path, source, name='r19_candidate'):
    file = tmp_path / (name + '.py')
    file.write_text(source)
    spec = importlib.util.spec_from_file_location(name, file)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def test_recorded_equal_boundary_call_is_changed_and_the_alias_keeps_its_code(tmp_path):
    old = 'def can_hire(db, item_id: int, stock: int, reserved: int):\n    return stock > reserved\n'
    now = old.replace('stock > reserved', 'stock >= reserved')
    m = module(tmp_path, now)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    alias = m.can_hire
    code = alias.__code__
    with runtime.hook(m.can_hire, name='AVAILABLE'):
        assert alias(None, 99, 1, 1) is True
    assert alias is m.can_hire and alias.__code__ is code
    reading, = runtime.readings
    assert reading.rows == [] and reading.sample['inputs'] == dict(db=None, item_id=99, stock=1, reserved=1)
    old_outcome, new_outcome = sealed_pair(runtime, reading, FILE, 'can_hire')
    assert differs(old_outcome, new_outcome) and (value(old_outcome), value(new_outcome)) == (False, True)


def test_a_database_connection_is_not_recorded_and_its_write_happens_once(tmp_path):
    source = '''def hire_count(db, x: int):
    db.execute("UPDATE count SET n = n + 1")
    return db.execute("SELECT n FROM count").fetchone()[0]
'''
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    with sqlite3.connect(':memory:') as db:
        db.executescript('CREATE TABLE count(n); INSERT INTO count VALUES (0)')
        with runtime.hook(m.hire_count):
            assert m.hire_count(db, 1) == 1
        assert db.execute('SELECT n FROM count').fetchone()[0] == 1
    reading, = runtime.readings
    assert reading.rows == [] and reading.sample is None and reading.reasons == ['not JSON data']


def test_old_helper_and_old_constant_come_from_the_baseline_source_without_touching_the_module(tmp_path):
    old = '''GRACE_DAYS = 3
def within(days):
    return days <= GRACE_DAYS
def standing(days: int, suspended: bool):
    return within(days) and not suspended
'''
    m = module(tmp_path, old.replace('GRACE_DAYS = 3', 'GRACE_DAYS = 7'))
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with runtime.hook(m.standing):
        assert m.standing(0, False)
        assert m.standing(5, False)
        assert not m.standing(5, True)
    assert m.GRACE_DAYS == 7
    changed = [(reading.sample['inputs'], *map(value, sealed_pair(runtime, reading, FILE, 'standing')))
               for reading in runtime.readings if differs(*sealed_pair(runtime, reading, FILE, 'standing'))]
    assert changed == [(dict(days=5, suspended=False), False, True)]


def test_each_real_call_with_a_database_object_is_its_own_unrecorded_reading(tmp_path):
    old = '''def allowed(db, x: int):
    owed = db.execute("SELECT n FROM debt").fetchone()
    return owed is None or owed[0] < x
'''
    m = module(tmp_path, old.replace('owed[0] < x', 'owed[0] <= x'))
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE debt(n)')
        with runtime.hook(m.allowed):
            assert m.allowed(db, 1)
            db.execute('INSERT INTO debt VALUES (1)')
            assert m.allowed(db, 1)
        assert db.execute('SELECT count(*) FROM debt').fetchone()[0] == 1
    assert len(runtime.readings) == 2
    assert all(reading.sample is None and reading.reasons == ['not JSON data'] and reading.rows == []
               for reading in runtime.readings)


def test_real_exception_keeps_native_identity_and_traceback(tmp_path):
    source = '''def decision(x: int):
    if x < 0:
        raise ValueError("native negative")
    return x <= 3
'''
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    with runtime.hook(m.decision):
        with pytest.raises(ValueError, match='native negative') as error:
            m.decision(-1)
    assert error.value.__traceback__ is not None
    reading, = runtime.readings
    assert isinstance(reading.actual[1], cells.Raised) and reading.actual[1].error is error.value
    assert reading.sample['inputs'] == {'x': -1} and reading.rows == []


def test_prior_code_scope_never_swaps_the_live_module_even_after_exception(tmp_path):
    from flowguard.intent.runtime import sealed
    old = 'LIMIT = 3\ndef f(x=3):\n    return x <= LIMIT\n'
    m = module(tmp_path, old.replace('= 3', '= 7').replace('x=3', 'x=7'))
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    runtime.register(m.f)
    before = (m.f.__code__, m.f.__defaults__)
    with pytest.raises(RuntimeError):
        with runtime.old_code():
            assert m.LIMIT == 7 and (m.f.__code__, m.f.__defaults__) == before
            raise RuntimeError('leave scope')
    assert m.LIMIT == 7 and (m.f.__code__, m.f.__defaults__) == before
    # The old version runs only sealed, from its own source: its default 3 against its LIMIT 3.
    assert sealed(old, 'f', [], {}) == dict(status='ok', value=True)
    assert sealed(old, 'f', [4], {}) == dict(status='ok', value=False)


def test_old_module_initializer_is_not_executed(tmp_path):
    source = 'def f(x: int):\n    return x <= 3\n'
    m = module(tmp_path, source)
    old = 'raise AssertionError("do not execute old module")\n' + source
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    assert runtime.register(m.f) is not None


def test_monitor_only_records_requested_code_and_distinguishes_escaping_error(tmp_path):
    source = '''def event(x: int):
    if x < 0:
        raise ValueError("native")
    try:
        1 / x
    except ZeroDivisionError:
        return None
    return x
def unrelated():
    return 2
'''
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={})
    with runtime.record({m.event.__code__: 'EVENT'}):
        assert m.event(0) is None
        assert m.unrelated() == 2
        with pytest.raises(ValueError):
            m.event(-1)
        assert m.event(1) == 1
    assert [(e['anchor'], e['phase']) for e in runtime.events] == [
        ('EVENT', 'call'), ('EVENT', 'return'), ('EVENT', 'call'),
        ('EVENT', 'raise'), ('EVENT', 'call'), ('EVENT', 'return')]
    assert runtime.events[0]['values']['x'] == 0
    assert runtime.events[-1]['value'] == 1


def test_external_debugger_is_preserved(tmp_path):
    runtime = Runtime(tmp_path, previous={})
    source = 'def f(x: int):\n    return x\n'
    m = module(tmp_path, source)
    previous = sys.gettrace()
    def trace(frame, event, arg):
        return trace
    sys.settrace(trace)
    try:
        with runtime.record({m.f.__code__: 'F'}):
            assert m.f(1) == 1
        assert sys.gettrace() is trace
    finally:
        sys.settrace(previous)
    if not hasattr(sys, 'monitoring'):
        assert runtime.events == [] and runtime.issues


def test_no_baseline_does_not_discredit_safe_current_reading(tmp_path):
    source = 'def f(x: int):\n    return x <= 3\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={})
    with runtime.hook(m.f):
        assert m.f(2) is True
    reading, = runtime.readings
    assert reading.status == 'ok' and reading.sample['inputs'] == {'x': 2} and reading.json_result is True
    old, new = sealed_pair(runtime, reading, FILE, 'f')
    assert old == dict(status='unavailable', reason='no baseline source') and new == dict(status='ok', value=True)
    assert not comparable(old, new)


def test_old_side_effect_is_never_run_for_a_call_with_a_database_object(tmp_path):
    old = '''def f(db, x: int):
    db.execute("UPDATE count SET n = n + 1")
    return x <= 3
'''
    source = 'def f(db, x: int):\n    return x <= 3\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with sqlite3.connect(':memory:') as db:
        db.executescript('CREATE TABLE count(n); INSERT INTO count VALUES (0)')
        with runtime.hook(m.f):
            assert m.f(db, 2) is True
        assert db.execute('SELECT n FROM count').fetchone()[0] == 0
    reading, = runtime.readings
    assert reading.sample is None and reading.reasons == ['not JSON data'] and reading.rows == []
    from flowguard.intent.runtime import sealed
    # Even a JSON stand-in for the connection cannot reach the old write: the source is refused first.
    assert sealed(old, 'f', [None, 2], {}) == dict(status='unavailable', reason='uses attribute execute')


def test_private_constraint_observation_is_recorded_outside_the_sampling_budget(tmp_path):
    from flowguard.intent.runtime import _PRIVATE
    m = module(tmp_path, 'def f(x: int):\n    return x <= 3\n')
    runtime = Runtime(tmp_path, previous={})
    token = _PRIVATE.set(True)
    try:
        with runtime.hook(m.f, private=True):
            assert m.f(2) is True
    finally:
        _PRIVATE.reset(token)
    reading, = runtime.readings
    assert reading.status == 'ok' and reading.actual == ({'x': 2}, True) and reading.rows == []
    assert runtime._seen == {}


def test_callback_receives_the_real_frame_and_native_escaping_exception(tmp_path):
    source = '''def f(x: int):
    try:
        raise ValueError("native")
    finally:
        y = x + 1
'''
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={})
    seen = []
    def callback(frame, event, arg):
        seen.append((frame.f_code, frame.f_locals['x'], event, arg))
    with runtime.record({m.f.__code__: 'F'}, callback=callback):
        with pytest.raises(ValueError):
            m.f(3)
    assert [event for _, _, event, _ in seen] == ['call', 'exception', 'return']
    assert all(code is m.f.__code__ and x == 3 for code, x, _, _ in seen)
    assert type(seen[1][-1][1]) is ValueError and str(seen[1][-1][1]) == 'native'


def test_observer_failure_cannot_be_mistaken_for_a_business_exception(tmp_path):
    m = module(tmp_path, 'def f(x: int):\n    return x\n')
    runtime = Runtime(tmp_path, previous={})
    def broken(frame, event, arg):
        raise ValueError('observer broke')
    with runtime.record({m.f.__code__: 'F'}, callback=broken):
        assert m.f(3) == 3
    assert runtime.issues == ['observer callback failed: ValueError: observer broke']


@pytest.mark.parametrize('style', ['alias', 'module'])
def test_imported_constant_is_not_compared_and_names_the_import(tmp_path, style):
    settings = module(tmp_path, 'GRACE_DAYS = 7\n', 'r19_settings')
    source = ('from r19_settings import GRACE_DAYS\ndef f(x: int):\n    return x <= GRACE_DAYS\n'
              if style == 'alias' else 'import r19_settings\ndef f(x: int):\n    return x <= r19_settings.GRACE_DAYS\n')
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_settings.py': 'GRACE_DAYS = 3\n', 'r19_candidate.py': source})
    with runtime.hook(m.f):
        assert m.f(5)
    assert settings.GRACE_DAYS == 7
    # The sealed environment loads no project module (4.5): this call is not compared, with its reason.
    reason = 'uses unavailable binding GRACE_DAYS' if style == 'alias' else 'uses attribute GRACE_DAYS'
    old, new = sealed_pair(runtime, runtime.readings[0], FILE, 'f')
    assert old == new == dict(status='unavailable', reason=reason) and not comparable(old, new)


def test_dynamic_old_global_cannot_borrow_the_current_value(tmp_path):
    source = 'LIMIT = 7\ndef f(x: int):\n    return x <= LIMIT\n'
    m = module(tmp_path, source)
    old = 'LIMIT = 3\nLIMIT = int("4")\ndef f(x: int):\n    return x <= LIMIT\n'
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with runtime.hook(m.f):
        assert m.f(5)
    reading, = runtime.readings
    old, new = sealed_pair(runtime, reading, FILE, 'f')
    assert old == dict(status='unavailable', reason='uses unavailable binding LIMIT') and new == dict(status='ok', value=True)
    assert not comparable(old, new)


def test_constructed_module_constant_is_not_a_literal_and_is_not_compared(tmp_path):
    source = 'from decimal import Decimal as D\nLIMIT = D("7")\ndef f(x: int):\n    return x <= LIMIT\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source.replace('D("7")', 'D("3")')})
    with runtime.hook(m.f):
        assert m.f(5)
    # Only constants ast.literal_eval reads enter the sealed environment (4.5); a constructor call is not one.
    old, new = sealed_pair(runtime, runtime.readings[0], FILE, 'f')
    assert old == new == dict(status='unavailable', reason='uses unavailable binding LIMIT')
    old = 'def D(value):\n    return 5\nLIMIT = D("3")\ndef f(x: int):\n    return x <= LIMIT\n'
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with runtime.hook(m.f):
        assert m.f(5)
    old, new = sealed_pair(runtime, runtime.readings[0], FILE, 'f')
    assert old == new == dict(status='unavailable', reason='uses unavailable binding LIMIT')


def test_replay_rejects_actual_active_item(request):
    runtime = Runtime(Path(__file__).parent, previous={})
    result = runtime.replay(request.node)
    assert result['status'] == 'grey' and 'completed test protocol' in result['reasons'][0]


def test_new_collected_child_is_legal_and_finished_child_gets_fresh_fixtures(request, tmp_path):
    file = tmp_path / 'r19_nested_fresh.py'
    file.write_text('''import pytest
SEEN = []
@pytest.fixture
def box():
    result = {"count": 0}
    SEEN.append(result)
    yield result
def test_inner(box):
    assert box["count"] == 0
    box["count"] += 1
''')
    collector = pytest.Module.from_parent(request.node, path=file, nodeid=file.as_posix())
    item = list(collector.collect())[0]
    runtime = Runtime(tmp_path, previous={})
    assert runtime.replay(item, nextitem=request.node)['status'] == 'ok'
    assert runtime.replay(item, nextitem=request.node)['status'] == 'ok'
    assert len(item.module.SEEN) == 2 and item.module.SEEN[0] is not item.module.SEEN[1]


def test_child_cannot_borrow_active_ancestor_builtin_fixture(request, tmp_path):
    file = tmp_path / 'r19_nested_borrow.py'
    file.write_text('def test_inner(tmp_path):\n    pass\n')
    collector = pytest.Module.from_parent(request.node, path=file, nodeid=file.as_posix())
    item = list(collector.collect())[0]
    result = Runtime(tmp_path, previous={}).replay(item, nextitem=request.node)
    assert result['status'] == 'grey' and 'active ancestor' in result['reasons'][0]


def test_shared_fixture_cannot_borrow_builtin_exemption_by_name(request, tmp_path):
    for fixture_name in ['tmp_path_factory', 'pytestconfig']:
        file = tmp_path / ('r19_nested_shared_' + fixture_name + '.py')
        file.write_text(f'import pytest\n@pytest.fixture(scope="session")\ndef {fixture_name}():\n    return {{}}\n'
                        f'def test_inner({fixture_name}):\n    pass\n')
        collector = pytest.Module.from_parent(request.node, path=file, nodeid=file.as_posix())
        item = list(collector.collect())[0]
        result = Runtime(tmp_path, previous={}).replay(item, nextitem=request.node)
        assert result['status'] == 'grey' and 'shared fixture lifecycle' in result['reasons'][0]


def test_repeated_nonrecursive_helper_is_valid(tmp_path):
    source = '''def helper(x):
    return x <= 3
def valid(x: int):
    return helper(x) and helper(x)
'''
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    with runtime.hook(m.valid):
        assert m.valid(0) is True
        assert m.valid(4) is False
    pairs = [sealed_pair(runtime, reading, FILE, 'valid') for reading in runtime.readings]
    assert [(value(old), value(new)) for old, new in pairs] == [(True, True), (False, False)]
    assert all(comparable(*pair) and not differs(*pair) for pair in pairs)


def test_overridden_container_argument_is_not_recorded_and_its_method_runs_once(tmp_path):
    source = '''class Trap(dict):
    def get(self, name):
        self["hits"] += 1
        return True
def allowed(config, x: int):
    return config.get("allowed") and x <= 3
'''
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    config = m.Trap(hits=0)
    with runtime.hook(m.allowed):
        assert m.allowed(config, 0) is True
    assert config['hits'] == 1                 # only the real call ran its method
    reading, = runtime.readings
    assert reading.sample is None and reading.reasons == ['not JSON data'] and reading.rows == []


@pytest.mark.parametrize('query,register', [('SELECT n FROM debt', False),
                                            ('SELECT COUNT(*) FROM debt', False),
                                            ('SELECT touch()', True),
                                            ('SELECT "touch"()', True),
                                            ('SELECT touch/**/()', True),
                                            ('SELECT COUNT(*) FROM debt', True)])
def test_sql_calls_run_only_for_real_and_are_not_recorded(tmp_path, query, register):
    source = f'def allowed(db, x: int):\n    return db.execute({query!r}).fetchone()[0] <= x\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    hits = []
    with sqlite3.connect(':memory:') as db:
        db.executescript('CREATE TABLE debt(n); INSERT INTO debt VALUES(1)')
        if register:
            def called(*args):
                hits.append(1)
                return 1
            db.create_function('touch', 0, called)
            db.create_function('count', 0, called)
        with runtime.hook(m.allowed):
            assert m.allowed(db, 1) is True
    reading, = runtime.readings
    assert reading.sample is None and reading.reasons == ['not JSON data'] and reading.rows == []
    assert hits == ([1] if register else [])


def test_module_literal_container_of_another_module_is_not_compared_or_swapped(tmp_path):
    settings = module(tmp_path, 'POLICY = {"grace": 7}\n', 'r19_settings')
    source = 'import r19_settings\ndef f(x: int):\n    return x <= r19_settings.POLICY["grace"]\n'
    m = module(tmp_path, source)
    for previous in ('POLICY = {"grace": 3}\n', 'POLICY = dict(grace=3)\n'):
        runtime = Runtime(tmp_path, previous={'r19_candidate.py': source, 'r19_settings.py': previous})
        with runtime.hook(m.f):
            assert m.f(5)
        assert settings.POLICY == {'grace': 7}
        old, new = sealed_pair(runtime, runtime.readings[0], FILE, 'f')
        assert old == new == dict(status='unavailable', reason='uses attribute POLICY')


def test_a_mutating_numeric_subclass_argument_is_not_recorded(tmp_path):
    source = '''class Trap(int):
    def __le__(self, other):
        self.hits.append(1)
        return True
def f(x: int):
    return x <= 3
'''
    m = module(tmp_path, source)
    x = m.Trap(0)
    x.hits = []
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    with runtime.hook(m.f):
        assert m.f(x) is True
    assert x.hits == [1]
    reading, = runtime.readings
    assert reading.sample is None and reading.reasons == ['not JSON data'] and reading.rows == []


def test_only_exact_transport_code_is_hidden_and_scope_is_restored(tmp_path):
    from flowguard.intent.runtime import is_transport
    from flowguard.intent import sites
    ambient = sites._TRANSPORT.get()
    source = 'def f(x: int):\n    return x <= 3\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    code = m.f.__code__
    membership = is_transport(code), is_transport(Runtime.observe.__code__)
    with runtime.hook(m.f, axes={'x': [2, 4]}) as original:
        assert is_transport(m.f.__code__)
        assert not is_transport(original.__code__)
        assert is_transport(Runtime.observe.__code__)
        with runtime.record({m.f.__code__: 'STUB', original.__code__: 'ACTUAL'}):
            assert m.f(2) is True
    assert sites._TRANSPORT.get() == ambient
    assert (is_transport(code), is_transport(Runtime.observe.__code__)) == membership
    assert [event['anchor'] for event in runtime.events] == ['ACTUAL', 'ACTUAL']
    assert [event['phase'] for event in runtime.events] == ['call', 'return']


def test_each_real_context_is_recorded_and_private_calls_are_not(tmp_path):
    from flowguard.intent.runtime import _PRIVATE
    m = module(tmp_path, 'def f(config, x: int):\n    return x <= config["limit"]\n')
    runtime = Runtime(tmp_path, previous={})
    with runtime.hook(m.f):
        assert m.f({'limit': 3}, 2) is True
        assert m.f({'limit': 7}, 5) is True
        token = _PRIVATE.set(True)
        try:
            assert m.f({'limit': 9}, 5) is True
        finally:
            _PRIVATE.reset(token)
    assert [reading.sample['inputs'] for reading in runtime.readings] == [
        {'config': {'limit': 3}, 'x': 2}, {'config': {'limit': 7}, 'x': 5}]


def test_raw_recording_does_not_retain_context_or_temporary_locals(tmp_path):
    import gc
    import weakref
    source = '''import weakref
LOCAL = []
class Payload:
    def __init__(self):
        self.data = bytearray(2_000_000)
def event(context, path, x: int):
    temporary = Payload()
    LOCAL.append(weakref.ref(temporary))
    return context
'''
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={})
    context = m.Payload()
    reference = weakref.ref(context)
    path = tmp_path / 'context-path'
    with runtime.record({m.event.__code__: 'EVENT'}):
        assert m.event(context, path, 3) is context
    del context
    gc.collect()
    assert reference() is None and m.LOCAL[0]() is None
    assert [event['phase'] for event in runtime.events] == ['call', 'return']
    assert runtime.events[-1]['value'] == '<Payload>'
    for event in runtime.events:
        assert set(event['values']) == {'context', 'path', 'x'}
        assert event['values']['context'] == '<Payload>'
        assert event['values']['path'] == '<' + type(path).__name__ + '>'
        assert event['values']['x'] == 3


def test_fixture_global_override_does_not_enter_the_equivalent_refactor_comparison(tmp_path):
    old = 'LIMIT = 3\ndef f(x: int):\n    return x <= LIMIT\n'
    source = 'LIMIT = 3\ndef f(x: int):\n    if x > LIMIT:\n        return False\n    return True\n'
    m = module(tmp_path, source)
    m.LIMIT = 100
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with runtime.hook(m.f):
        assert m.f(6) is True
    assert m.LIMIT == 100
    # Both versions run on their source constant (3), never the fixture's live 100: equal, not changed.
    old_outcome, new_outcome = sealed_pair(runtime, runtime.readings[0], FILE, 'f')
    assert comparable(old_outcome, new_outcome) and value(old_outcome) is value(new_outcome) is False


def test_fixture_global_override_never_replaces_the_source_constants_of_either_version(tmp_path):
    old = 'LIMIT = 3\ndef f(x: int):\n    return x <= LIMIT\n'
    m = module(tmp_path, old.replace('LIMIT = 3', 'LIMIT = 7'))
    m.LIMIT = 100
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with runtime.hook(m.f):
        assert m.f(5) is True
        m.LIMIT = 3
        assert m.f(5) is False
    assert m.LIMIT == 3
    pairs = [sealed_pair(runtime, reading, FILE, 'f') for reading in runtime.readings]
    assert [(value(old), value(new)) for old, new in pairs] == [(False, True), (False, True)]


@pytest.mark.parametrize('style', ['alias', 'module'])
def test_imported_fixture_global_override_is_not_compared_and_stays_the_fixture_value(tmp_path, style):
    settings = module(tmp_path, 'LIMIT = 7\n', 'r19_settings')
    source = ('from r19_settings import LIMIT\ndef f(x: int):\n    return x <= LIMIT\n'
              if style == 'alias' else 'import r19_settings\ndef f(x: int):\n    return x <= r19_settings.LIMIT\n')
    m = module(tmp_path, source)
    context = m if style == 'alias' else settings
    context.LIMIT = 100
    runtime = Runtime(tmp_path, previous={'r19_settings.py': 'LIMIT = 3\n', 'r19_candidate.py': source})
    with runtime.hook(m.f):
        assert m.f(2) is True
        context.LIMIT = 7
        assert m.f(2) is True
    assert context.LIMIT == 7
    reason = 'uses unavailable binding LIMIT' if style == 'alias' else 'uses attribute LIMIT'
    for reading in runtime.readings:
        assert sealed_pair(runtime, reading, FILE, 'f') == (dict(status='unavailable', reason=reason),) * 2


def test_deleted_current_constant_is_added_only_for_old_code_then_removed(tmp_path):
    old = 'LIMIT = 4\ndef f(x: int):\n    return x <= LIMIT\n'
    m = module(tmp_path, 'def f(x: int):\n    return x <= 3\n')
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with runtime.hook(m.f):
        assert m.f(2) is True
        assert m.f(4) is False
    changes = [(reading.sample['inputs']['x'], *map(value, sealed_pair(runtime, reading, FILE, 'f')))
               for reading in runtime.readings if differs(*sealed_pair(runtime, reading, FILE, 'f'))]
    assert changes == [(4, True, False)]
    assert 'LIMIT' not in vars(m)


def test_unreadable_current_constant_source_does_not_get_an_invented_old_value(tmp_path):
    old = 'LIMIT = 3\ndef f(x: int):\n    return x <= LIMIT\n'
    m = module(tmp_path, old.replace('LIMIT = 3', 'LIMIT = int("7")'))
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with runtime.hook(m.f):
        assert m.f(5) is True
    old, new = sealed_pair(runtime, runtime.readings[0], FILE, 'f')
    assert old == dict(status='ok', value=False)
    assert new == dict(status='unavailable', reason='uses unavailable binding LIMIT') and not comparable(old, new)


def test_changed_import_alias_cannot_borrow_the_current_helper_as_old(tmp_path):
    helpers = 'def before(x: int):\n    return x <= 4\ndef after(x: int):\n    return x <= 3\n'
    module(tmp_path, helpers, 'r19_alias_helpers')
    old = 'from r19_alias_helpers import before as decide\ndef f(x: int):\n    return decide(x)\n'
    source = old.replace('import before as decide', 'import after as decide')
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old, 'r19_alias_helpers.py': helpers})
    with runtime.hook(m.f):
        assert m.f(4) is False
    old, new = sealed_pair(runtime, runtime.readings[0], FILE, 'f')
    assert old == new == dict(status='unavailable', reason='uses unavailable binding decide')


def test_changed_imported_helper_is_compared_at_its_own_definition(tmp_path):
    helpers = 'def before(x: int):\n    return x <= 4\n'
    imported = module(tmp_path, helpers.replace('<= 4', '<= 3'), 'r19_alias_helpers')
    source = 'from r19_alias_helpers import before as decide\ndef f(x: int):\n    return decide(x)\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source, 'r19_alias_helpers.py': helpers})
    with runtime.hook(imported.before), runtime.hook(m.f):
        assert m.f(4) is False
    caller, = [reading for reading in runtime.readings if reading.target.endswith(':f')]
    helper, = [reading for reading in runtime.readings if reading.target.endswith(':before')]
    # The unchanged caller cannot load the helper's module; the changed helper itself is compared.
    assert sealed_pair(runtime, caller, FILE, 'f') == (dict(status='unavailable', reason='uses unavailable binding decide'),) * 2
    old, new = sealed_pair(runtime, helper, 'r19_alias_helpers.py', 'before')
    assert helper.sample['inputs'] == {'x': 4} and differs(old, new) and (value(old), value(new)) == (True, False)


def test_changed_module_import_and_callable_assignment_bindings_are_unavailable(tmp_path):
    module(tmp_path, 'def allowed(x: int):\n    return x <= 4\n', 'r19_old_rules')
    module(tmp_path, 'def allowed(x: int):\n    return x <= 3\n', 'r19_new_rules')
    old = 'import r19_old_rules as rules\ndef f(x: int):\n    return rules.allowed(x)\n'
    m = module(tmp_path, old.replace('r19_old_rules', 'r19_new_rules'))
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with runtime.hook(m.f):
        assert m.f(4) is False
    assert sealed_pair(runtime, runtime.readings[0], FILE, 'f') == (dict(status='unavailable', reason='uses attribute allowed'),) * 2
    old = 'from r19_old_rules import allowed as before\nfrom r19_new_rules import allowed as after\ndecide = before\ndef f(x: int):\n    return decide(x)\n'
    m = module(tmp_path, old.replace('decide = before', 'decide = after'))
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with runtime.hook(m.f):
        assert m.f(4) is False
    assert sealed_pair(runtime, runtime.readings[0], FILE, 'f') == (dict(status='unavailable', reason='uses unavailable binding decide'),) * 2


def test_changed_exception_class_structure_is_not_the_old_class_by_assumption(tmp_path):
    old = 'class Denied(ValueError):\n    pass\ndef f(x: bool):\n    if x:\n        raise Denied("native")\n    return False\n'
    m = module(tmp_path, old.replace('Denied(ValueError)', 'Denied(RuntimeError)'))
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with runtime.hook(m.f):
        assert m.f(False) is False
        with pytest.raises(RuntimeError, match='native'):
            m.f(True)
    assert runtime.readings[0].status == 'ok' and isinstance(runtime.readings[1].actual[1], cells.Raised)
    for reading in runtime.readings:
        assert sealed_pair(runtime, reading, FILE, 'f') == (dict(status='unavailable', reason='uses unavailable binding Denied'),) * 2


def test_dependency_inside_project_venv_is_not_project_code(tmp_path):
    venv = tmp_path / '.venv'
    (venv / 'lib/python3.12/site-packages').mkdir(parents=True)
    (venv / 'pyvenv.cfg').write_text('home=/external/python\n')
    external = module(venv / 'lib/python3.12/site-packages', 'def helper(x: int):\n    return x <= 4\n', 'r19_external')
    own = module(tmp_path, 'from r19_external import helper\ndef f(x: int):\n    return helper(x)\n')
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': (tmp_path/'r19_candidate.py').read_text()})
    assert runtime._project_file(inspect.getsourcefile(own.f))
    assert not runtime._project_file(inspect.getsourcefile(external.helper))
    runtime.register(own.f)
    assert external.helper not in runtime.patches
    # The external helper is not read as project code, and the sealed environment does not load it.
    assert runtime.safety(own.f, {'x': 2}) == 'uses unavailable binding helper'


def test_symbolic_baseline_is_frozen_before_later_git_commits(tmp_path):
    from flowguard.map.common import git_run
    root = tmp_path / 'repository'
    root.mkdir()
    old = 'LIMIT = 3\ndef f(x: int):\n    return x <= LIMIT\n'
    m = module(root, old)
    git_run(root, 'init', '-q')
    git_run(root, 'add', '.')
    git_run(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'old')
    first = git_run(root, 'rev-parse', 'HEAD').stdout.decode().strip()
    runtime = Runtime(root)
    assert runtime.baseline == first
    (root / 'r19_candidate.py').write_text(old.replace('LIMIT = 3', 'LIMIT = 7'))
    m.LIMIT = 7
    git_run(root, 'add', '.')
    git_run(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'new')
    assert git_run(root, 'rev-parse', 'HEAD').stdout.decode().strip() != first
    with runtime.hook(m.f):
        assert m.f(5) is True
    assert runtime.baseline == first
    old, new = sealed_pair(runtime, runtime.readings[0], FILE, 'f')
    assert differs(old, new) and (value(old), value(new)) == (False, True)


def test_a_missing_baseline_does_not_silently_appear_later(tmp_path):
    from flowguard.map.common import git_run
    source = 'LIMIT = 3\ndef f(x: int):\n    return x <= LIMIT\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path)
    assert runtime.baseline is None
    git_run(tmp_path, 'init', '-q')
    git_run(tmp_path, 'add', '.')
    git_run(tmp_path, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'later')
    with runtime.hook(m.f):
        assert m.f(2) is True
    assert runtime.baseline is None and runtime.readings[0].sample['inputs'] == {'x': 2}
    old, new = sealed_pair(runtime, runtime.readings[0], FILE, 'f')
    assert old == dict(status='unavailable', reason='no baseline source') and not comparable(old, new)


def test_explicit_previous_sources_do_not_consult_git(tmp_path, monkeypatch):
    from flowguard.map import common
    source = 'def f(x: int):\n    return x <= 3\n'
    m = module(tmp_path, source)
    def forbidden(*args, **kwargs):
        raise AssertionError('an explicit source fixture must not consult Git')
    monkeypatch.setattr(common, 'git_run', forbidden)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    with runtime.hook(m.f):
        assert m.f(2) is True
    old, new = sealed_pair(runtime, runtime.readings[0], FILE, 'f')
    assert comparable(old, new) and not differs(old, new)


def test_real_project_source_self_maintenance_metadata_is_private_and_native_call_is_observed():
    from flowguard.structure import paths
    sdk = Path(__file__).resolve().parents[2]
    from flowguard.intent import sites
    native_code = sites.installed_origin(paths.project_code) or paths.project_code.__code__
    ambient = sites._TRANSPORT.get()
    runtime = Runtime(sdk, previous={})
    with runtime.hook(paths.project_code, name='PROJECT_SOURCE'):
        with runtime.record({native_code: 'PROJECT_SOURCE'}, entry_only=True):
            assert paths.project_code(str(Path(paths.__file__).resolve()), sdk) is True
    assert sites._TRANSPORT.get() == ambient
    assert len(runtime.readings) == 1  # metadata did not recursively observe itself
    assert runtime.readings[0].status == 'ok'  # filesystem reads replay under the guard
    assert [event['phase'] for event in runtime.events] == ['call']
    assert [event['anchor'] for event in runtime.events] == ['PROJECT_SOURCE']


def test_recording_never_qualifies_a_call_and_leaves_the_one_real_native_exception(tmp_path, monkeypatch):
    from flowguard.intent.runtime import _PRIVATE
    source = 'def f(x: int):\n    raise ValueError("real native error")\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={})
    def safety(*args, **kwargs):
        raise AssertionError('an ordinary hook never runs a per-call safety analysis')
    monkeypatch.setattr(runtime, 'safety', safety)
    with runtime.hook(m.f) as original:
        def callback(frame, event, arg):
            return None
        with runtime.record({original.__code__: 'F'}, callback=callback):
            with pytest.raises(ValueError, match='real native error') as error:
                m.f(1)
    assert runtime.readings[0].actual[1].error is error.value
    assert [event['phase'] for event in runtime.events] == ['call', 'raise']
    assert not _PRIVATE.get()


def test_hub_predicate_and_callback_helpers_are_private_metadata(tmp_path):
    from flowguard.intent.runtime import _PRIVATE
    m = module(tmp_path, 'def f(x: int):\n    return x <= 3\n')
    runtime = Runtime(tmp_path, previous={})
    seen = []
    def predicate(code):
        assert _PRIVATE.get()
        return code is m.f.__code__
    def callback(frame, event, arg):
        assert _PRIVATE.get()
        seen.append(event)
        return callback
    with runtime.record(predicate=predicate, callback=callback):
        assert m.f(2) is True
    assert seen == ['call', 'return'] and not _PRIVATE.get()


def test_hook_prepares_no_old_code_and_the_actual_body_reads_ordinary_context(tmp_path, monkeypatch):
    from flowguard.intent.runtime import _PRIVATE
    m = module(tmp_path, 'def f(x: int):\n    return _PRIVATE.get()\n')
    m._PRIVATE = _PRIVATE
    runtime = Runtime(tmp_path, previous={})
    def register(function):
        raise AssertionError('recording a real call compiles no old version during the test')
    monkeypatch.setattr(runtime, 'register', register)
    with runtime.hook(m.f):
        assert m.f(1) is False
    assert runtime.readings[0].actual == ({'x': 1}, False) and not _PRIVATE.get()


def test_replay_closes_an_unrelated_inactive_collector_with_native_teardown(request, tmp_path):
    file = tmp_path / 'r19_after_sibling.py'
    file.write_text('CALLS = []\ndef test_inner():\n    CALLS.append("native")\n')
    module_node = pytest.Module.from_parent(request.node, path=file, nodeid=file.as_posix())
    item = list(module_node.collect())[0]
    closed = []
    class Sibling(pytest.Collector):
        def collect(self):
            return []
        def setup(self):
            self.addfinalizer(lambda: closed.append('closed'))
    sibling = Sibling.from_parent(request.node, name='unrelated-collector')
    request.session._setupstate.setup(sibling)
    runtime = Runtime(tmp_path, previous={})
    result = runtime.replay(item, nextitem=request.node)
    assert result['status'] == 'ok' and all(report.passed for report in result['reports'])
    assert closed == ['closed'] and item.module.CALLS == ['native']
    assert request.node in request.session._setupstate.stack


def test_collector_teardown_error_remains_unavailable_and_does_not_run_native_body(request, tmp_path):
    file = tmp_path / 'r19_after_bad_collector.py'
    file.write_text('CALLS = []\ndef test_inner():\n    CALLS.append("native")\n')
    module_node = pytest.Module.from_parent(request.node, path=file, nodeid=file.as_posix())
    item = list(module_node.collect())[0]
    def bad_cleanup():
        raise ValueError('real collector cleanup failed')
    class Sibling(pytest.Collector):
        def collect(self):
            return []
        def setup(self):
            self.addfinalizer(bad_cleanup)
    sibling = Sibling.from_parent(request.node, name='bad-collector')
    request.session._setupstate.setup(sibling)
    result = Runtime(tmp_path, previous={}).replay(item, nextitem=request.node)
    assert result['status'] == 'grey' and result['reports'] == []
    assert [(when, type(error), str(error)) for when, error in result['errors']] == [
        ('teardown', ValueError, 'real collector cleanup failed')]
    assert item.module.CALLS == [] and request.node in request.session._setupstate.stack


def test_replay_does_not_reset_a_shared_collector_needed_by_the_pending_real_item(request, tmp_path, monkeypatch):
    native_file = tmp_path / 'r19_private_target.py'
    native_file.write_text('CALLS = []\ndef test_inner():\n    CALLS.append("native")\n')
    native_module = pytest.Module.from_parent(request.node, path=native_file, nodeid=native_file.as_posix())
    native = list(native_module.collect())[0]
    pending_file = tmp_path / 'r19_pending_real.py'
    pending_file.write_text('def test_pending():\n    pass\n')
    pending_module = pytest.Module.from_parent(request.node, path=pending_file, nodeid=pending_file.as_posix())
    pending = list(pending_module.collect())[0]
    closed = []
    def setup_shared():
        pending_module.addfinalizer(lambda: closed.append('closed'))
    monkeypatch.setattr(pending_module, 'setup', setup_shared)
    request.session._setupstate.setup(pending_module)
    result = Runtime(tmp_path, previous={}).replay(native, nextitem=pending)
    assert result['status'] == 'grey' and 'pending shared collector' in result['reasons'][0]
    assert closed == [] and native.module.CALLS == []
    def verify_real_teardown():
        assert closed == ['closed']
    request.addfinalizer(verify_real_teardown)


def test_builtin_session_fixture_lifecycle_survives_path_replay_before_next_real_test(request, tmp_path):
    """The real builtin definition stays live; merely passing nextitem is insufficient evidence."""
    from _pytest.runner import runtestprotocol
    file = tmp_path / 'r19_builtin_lifecycle.py'
    file.write_text('''FACTORIES = []
LIFETIME = []
def test_first(tmp_path_factory, pytestconfig, request):
    if not FACTORIES:
        FACTORIES.append(tmp_path_factory)
        LIFETIME.append("live")
        definition = request._get_active_fixturedef("tmp_path_factory")
        definition.addfinalizer(lambda: LIFETIME.append("finished"))
        pytestconfig._r19_lifetime = LIFETIME
    assert tmp_path_factory is FACTORIES[0]
    assert pytestconfig._r19_lifetime == ["live"]
def test_second(tmp_path_factory, pytestconfig):
    assert tmp_path_factory is FACTORIES[0]
    assert pytestconfig._r19_lifetime == ["live"]
''')
    module_node = pytest.Module.from_parent(request.node, path=file, nodeid=file.as_posix())
    first, second = list(module_node.collect())
    reports = runtestprotocol(first, log=False, nextitem=second)
    assert all(report.passed for report in reports)
    replay = Runtime(tmp_path, previous={}).replay(first, nextitem=second)
    assert replay['status'] == 'ok' and all(report.passed for report in replay['reports'])
    reports = runtestprotocol(second, log=False, nextitem=request.node)
    assert all(report.passed for report in reports)
    assert module_node.obj.LIFETIME == ['live']
    assert request.config._r19_lifetime is module_node.obj.LIFETIME


def test_private_metadata_skips_ordinary_predicates_but_preserves_the_real_entry(tmp_path):
    from flowguard.intent.runtime import _PRIVATE
    m = module(tmp_path, 'def f(x: int):\n    return x <= 3\n')
    runtime = Runtime(tmp_path, previous={})
    evaluated = []
    def predicate(code):
        evaluated.append(code)
        return False
    with runtime.record({m.f.__code__: 'F'}, predicate=predicate, entry_only=True):
        token = _PRIVATE.set(True)
        try:
            before = len(evaluated)
            for _ in range(100):
                inspect.signature(m.f)
            assert len(evaluated) == before
        finally:
            _PRIVATE.reset(token)
        assert m.f(2) is True
    assert [(event['anchor'], event['phase']) for event in runtime.events] == [('F', 'call')]


def test_mutant_provenance_requires_the_exact_registered_owner_and_active_install(tmp_path):
    from flowguard.intent import sites
    m = module(tmp_path, 'def f(x: int):\n    return x <= 3\ndef g(x: int):\n    return x <= 3\n')
    mutant = next(m for m in sites.mutants_of(sites.sites_of(m.f), set()) if m.how == 'flip')
    code = sites.mutant_code(m.f, mutant)
    duplicate = sites.mutant_code(m.f, mutant)
    assert code is not duplicate and code == duplicate
    with sites.installed(m.f, duplicate):
        assert sites.controlled_mutation(m.f, duplicate)
    assert not sites.controlled_mutation(m.f, code)
    with sites.installed(m.g, code):
        assert not sites.controlled_mutation(m.g, code)
        assert not sites.controlled_mutation(m.f, code)
    with sites.installed(m.f, code):
        assert sites.controlled_mutation(m.f, code)
        assert not sites.controlled_mutation(m.g, code)
    assert not sites.controlled_mutation(m.f, code)
    original = m.f.__code__
    try:
        m.f.__code__ = code
        assert not sites.controlled_mutation(m.f, code)
    finally:
        m.f.__code__ = original


def test_mutant_provenance_does_not_retain_a_function_or_its_source_context(tmp_path):
    import gc
    import weakref
    from flowguard.intent import sites
    m = module(tmp_path, 'def f(x: int):\n    return x <= 3\n', name='r19_weak_mutant')
    function = m.f
    mutant = next(m for m in sites.mutants_of(sites.sites_of(function), set()) if m.how == 'flip')
    code = sites.mutant_code(function, mutant)
    reference = weakref.ref(function)
    sys.modules.pop(m.__name__)
    del function, m
    gc.collect()
    assert reference() is None
    assert not sites.controlled_mutation(lambda: None, code)


def test_equal_code_from_distinct_source_files_keeps_labels_and_transport_identity(tmp_path):
    from flowguard.intent import sites
    first = module(tmp_path, 'def same(x: int):\n    return x + 1\n', name='r19_identity_first').same
    second = module(tmp_path, 'def same(x: int):\n    return x + 1\n', name='r19_identity_second').same
    assert first.__code__ == second.__code__ and first.__code__ is not second.__code__
    runtime = Runtime(tmp_path, previous={})
    with runtime.record([(first.__code__, 'FIRST'), (second.__code__, 'SECOND')]):
        assert first(1) == second(1) == 2
    assert [(event['anchor'], event['phase']) for event in runtime.events] == [
        ('FIRST', 'call'), ('FIRST', 'return'), ('SECOND', 'call'), ('SECOND', 'return')]
    with sites.transport([first.__code__]):
        assert sites.is_transport(first.__code__)
        assert not sites.is_transport(second.__code__)
        with sites.transport([second.__code__]):
            assert sites.is_transport(first.__code__) and sites.is_transport(second.__code__)
        assert not sites.is_transport(second.__code__)
    assert not sites.is_transport(first.__code__) and not sites.is_transport(second.__code__)
    runtime.events.clear()
    with runtime.record([(first.__code__, 'FIRST'), (second.__code__, 'SECOND')], ignored=(first.__code__,)):
        assert first(1) == second(1) == 2
    assert [(event['anchor'], event['phase']) for event in runtime.events] == [('SECOND', 'call'), ('SECOND', 'return')]
