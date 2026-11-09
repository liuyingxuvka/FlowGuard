"""Independent runtime-level guarantees replacing retired execution mechanics."""
import importlib.util
import inspect
from pathlib import Path
import sqlite3
import sys

import pytest

from flowguard.intent import cells
from flowguard.intent.runtime import Runtime


def module(tmp_path, source, name='r19_candidate'):
    file = tmp_path / (name + '.py')
    file.write_text(source)
    spec = importlib.util.spec_from_file_location(name, file)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def test_before_real_call_observes_equal_boundary_and_exact_alias(tmp_path):
    old = 'def can_hire(db, item_id: int, stock: int, reserved: int):\n    return stock > reserved\n'
    now = old.replace('stock > reserved', 'stock >= reserved')
    m = module(tmp_path, now)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    alias = m.can_hire
    code = alias.__code__
    with runtime.hook(m.can_hire, name='AVAILABLE', axes={'stock': [0, 1], 'reserved': [0, 1]}):
        assert alias(None, 99, 1, 1) is True
    assert alias is m.can_hire and alias.__code__ is code
    changed = runtime.readings[0].changed
    assert any(row['stock'] == row['reserved'] and before is False and after is True
               for row, before, after in changed)
    assert runtime.readings[0].context == ('db', 'item_id')


def test_side_effect_gate_does_not_replay_database_writes(tmp_path):
    source = '''def hire_count(db, x: int):
    db.execute("UPDATE count SET n = n + 1")
    return db.execute("SELECT n FROM count").fetchone()[0]
'''
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    with sqlite3.connect(':memory:') as db:
        db.executescript('CREATE TABLE count(n); INSERT INTO count VALUES (0)')
        with runtime.hook(m.hire_count, axes={'x': [0, 1, 2]}):
            assert m.hire_count(db, 1) == 1
        assert db.execute('SELECT n FROM count').fetchone()[0] == 1
    assert runtime.readings[0].status == 'grey'
    assert runtime.readings[0].rows == []
    assert runtime.readings[0].reasons[0].startswith('回放被拦住：r19_candidate.py:2 ') and 'UPDATE count' in runtime.readings[0].reasons[0]


def test_old_helper_and_old_constant_are_swapped_then_restored(tmp_path):
    old = '''GRACE_DAYS = 3
def within(days):
    return days <= GRACE_DAYS
def standing(days: int, suspended: bool):
    return within(days) and not suspended
'''
    m = module(tmp_path, old.replace('GRACE_DAYS = 3', 'GRACE_DAYS = 7'))
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with runtime.hook(m.standing, axes={'days': range(0, 10), 'suspended': [False, True]}):
        assert m.standing(0, False)
    assert m.GRACE_DAYS == 7
    changed = runtime.readings[0].changed
    assert {row['days'] for row, before, after in changed} == {4, 5, 6, 7}
    assert all(not row['suspended'] and before is False and after is True for row, before, after in changed)


def test_default_grid_includes_old_new_constants_actual_and_neighbours(tmp_path):
    old = 'LIMIT = 3\ndef allowed(x: int):\n    return x <= LIMIT\n'
    m = module(tmp_path, old.replace('LIMIT = 3', 'LIMIT = 7'))
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    runtime.register(m.allowed)
    bound = inspect.signature(m.allowed).bind(100)
    grid = runtime.axes(m.allowed, bound)
    assert {2, 3, 4, 6, 7, 8, 99, 100, 101} <= set(grid['x'])


def test_same_database_object_is_observed_before_each_real_call(tmp_path):
    old = '''def allowed(db, x: int):
    owed = db.execute("SELECT n FROM debt").fetchone()
    return owed is None or owed[0] < x
'''
    m = module(tmp_path, old.replace('owed[0] < x', 'owed[0] <= x'))
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE debt(n)')
        with runtime.hook(m.allowed, axes={'x': [0, 1, 2]}):
            assert m.allowed(db, 1)
            db.execute('INSERT INTO debt VALUES (1)')
            assert m.allowed(db, 1)
    assert len(runtime.readings) == 2
    assert runtime.readings[0].changed == []
    assert any(row['x'] == 1 and before is False and after is True
               for row, before, after in runtime.readings[1].changed)


def test_real_exception_keeps_native_identity_and_traceback(tmp_path):
    source = '''def decision(x: int):
    if x < 0:
        raise ValueError("native negative")
    return x <= 3
'''
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    with runtime.hook(m.decision, axes={'x': [-1, 0, 1]}):
        with pytest.raises(ValueError, match='native negative') as error:
            m.decision(-1)
    assert error.value.__traceback__ is not None
    assert any(isinstance(value, cells.Raised) and type(value.error) is ValueError
               for _, value in runtime.readings[0].rows)


def test_prior_code_restores_all_state_even_after_exception(tmp_path):
    old = 'LIMIT = 3\ndef f(x=3):\n    return x <= LIMIT\n'
    m = module(tmp_path, old.replace('= 3', '= 7').replace('x=3', 'x=7'))
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    runtime.register(m.f)
    before = (m.f.__code__, m.f.__defaults__)
    with pytest.raises(RuntimeError):
        with runtime.old_code():
            assert m.LIMIT == 3 and m.f.__defaults__ == (3,)
            raise RuntimeError('leave scope')
    assert m.LIMIT == 7 and (m.f.__code__, m.f.__defaults__) == before


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
    with runtime.hook(m.f, axes={'x': [2, 4]}):
        assert m.f(2) is True
    reading = runtime.readings[0]
    assert reading.status == 'ok' and reading.rows
    assert reading.comparison_status == 'grey'
    assert reading.changed == []


def test_old_side_effect_is_rejected_before_it_can_write(tmp_path):
    old = '''def f(db, x: int):
    db.execute("UPDATE count SET n = n + 1")
    return x <= 3
'''
    source = 'def f(db, x: int):\n    return x <= 3\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with sqlite3.connect(':memory:') as db:
        db.executescript('CREATE TABLE count(n); INSERT INTO count VALUES (0)')
        with runtime.hook(m.f, axes={'x': [2, 4]}):
            assert m.f(db, 2) is True
        assert db.execute('SELECT n FROM count').fetchone()[0] == 0
    reading = runtime.readings[0]
    assert reading.status == 'ok' and reading.rows
    assert reading.comparison_status == 'grey'
    assert '写数据库 UPDATE count' in reading.comparison_reasons[0]


def test_private_constraint_observation_reuses_the_same_replay_gate(tmp_path):
    from flowguard.intent.runtime import _PRIVATE
    m = module(tmp_path, 'def f(x: int):\n    return x <= 3\n')
    runtime = Runtime(tmp_path, previous={})
    token = _PRIVATE.set(True)
    try:
        with runtime.hook(m.f, axes={'x': [2, 4]}, private=True):
            assert m.f(2) is True
    finally:
        _PRIVATE.reset(token)
    assert runtime.readings[0].status == 'ok'
    assert any(row['x'] == 4 and value is False for row, value in runtime.readings[0].rows)


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
def test_imported_constant_uses_the_previous_source_value(tmp_path, style):
    settings = module(tmp_path, 'GRACE_DAYS = 7\n', 'r19_settings')
    source = ('from r19_settings import GRACE_DAYS\ndef f(x: int):\n    return x <= GRACE_DAYS\n'
              if style == 'alias' else 'import r19_settings\ndef f(x: int):\n    return x <= r19_settings.GRACE_DAYS\n')
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_settings.py': 'GRACE_DAYS = 3\n', 'r19_candidate.py': source})
    with runtime.hook(m.f, axes={'x': range(0, 10)}):
        assert m.f(0)
    assert settings.GRACE_DAYS == 7
    reading = runtime.readings[0]
    assert reading.comparison_status == 'ok'
    assert {row['x'] for row, before, after in reading.changed} == {4, 5, 6, 7}


def test_dynamic_old_global_cannot_borrow_the_current_value(tmp_path):
    source = 'LIMIT = 7\ndef f(x: int):\n    return x <= LIMIT\n'
    m = module(tmp_path, source)
    old = 'LIMIT = 3\nLIMIT = int("4")\ndef f(x: int):\n    return x <= LIMIT\n'
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with runtime.hook(m.f, axes={'x': range(0, 10)}):
        assert m.f(0)
    reading = runtime.readings[0]
    assert reading.status == 'ok' and reading.comparison_status == 'grey'
    assert reading.changed == []


def test_old_decimal_constructor_is_resolved_from_source_import_not_spelling(tmp_path):
    source = 'from decimal import Decimal as D\nLIMIT = D("7")\ndef f(x: int):\n    return x <= LIMIT\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source.replace('D("7")', 'D("3")')})
    with runtime.hook(m.f, axes={'x': range(0, 10)}):
        assert m.f(0)
    assert runtime.readings[0].comparison_status == 'ok'
    assert {row['x'] for row, before, after in runtime.readings[0].changed} == {4, 5, 6, 7}
    old = 'def D(value):\n    return 5\nLIMIT = D("3")\ndef f(x: int):\n    return x <= LIMIT\n'
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with runtime.hook(m.f, axes={'x': range(0, 10)}):
        assert m.f(0)
    assert runtime.readings[0].comparison_status == 'grey'
    assert runtime.readings[0].changed == []


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
    with runtime.hook(m.valid, axes={'x': [0, 4]}):
        assert m.valid(0) is True
    assert runtime.readings[-1].status == 'ok' and runtime.readings[-1].rows


def test_overridden_container_read_method_is_not_assumed_inert(tmp_path):
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
    with runtime.hook(m.allowed, axes={'x': [0, 4]}):
        assert m.allowed(config, 0) is True
    assert config['hits'] == 1                 # replays ran on deep copies of the argument
    assert runtime.readings[0].status == 'ok' and runtime.readings[0].rows


@pytest.mark.parametrize('query,register,safe', [('SELECT n FROM debt', False, True),
                                             ('SELECT COUNT(*) FROM debt', False, True),
                                             ('SELECT touch()', True, False),
                                             ('SELECT "touch"()', True, False),
                                             ('SELECT touch/**/()', True, False),
                                             ('SELECT COUNT(*) FROM debt', True, False)])
def test_sql_unknown_or_overridden_functions_are_not_replayed(tmp_path, query, register, safe):
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
        with runtime.hook(m.allowed, axes={'x': [0, 1, 2]}):
            assert m.allowed(db, 1) is True
    reading = runtime.readings[0]
    assert reading.status == ('ok' if safe else 'grey')
    assert bool(reading.rows) is safe
    if register:
        assert hits == [1]


def test_module_literal_container_is_swapped_and_dynamic_data_does_not_borrow_current(tmp_path):
    settings = module(tmp_path, 'POLICY = {"grace": 7}\n', 'r19_settings')
    source = 'import r19_settings\ndef f(x: int):\n    return x <= r19_settings.POLICY["grace"]\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source, 'r19_settings.py': 'POLICY = {"grace": 3}\n'})
    with runtime.hook(m.f, axes={'x': range(0, 10)}):
        assert m.f(0)
    assert runtime.readings[0].comparison_status == 'ok'
    assert {row['x'] for row, before, after in runtime.readings[0].changed} == {4, 5, 6, 7}
    assert settings.POLICY == {'grace': 7}
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source, 'r19_settings.py': 'POLICY = dict(grace=3)\n'})
    with runtime.hook(m.f, axes={'x': range(0, 10)}):
        assert m.f(0)
    assert runtime.readings[0].comparison_status == 'grey'
    assert runtime.readings[0].changed == []


def test_historical_code_keeps_current_anchor_identity_and_separate_old_line(tmp_path):
    from flowguard.intent import anchors
    from flowguard.intent.flow import Capture
    old = '# flowguard: sensor LIMIT(x: count) -> allowed: bool\ndef f(x: int):\n    return x <= 3\n'
    source = '\n\n' + old.replace('x <= 3', 'x <= 7')
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    patch = runtime.register(m.f)
    assert patch.node.lineno == 2
    assert patch.code.co_firstlineno == m.f.__code__.co_firstlineno == 4
    index = anchors.collect_sources(tmp_path, [('r19_candidate.py', 'r19_candidate')])
    capture = Capture(tmp_path, index, 'historical')
    with runtime.old_code(), runtime.record({patch.code: 'LIMIT'}, callback=capture.on_trace, private=True):
        assert m.f(5) is False
    assert [event.phase for event in capture.events] == ['call', 'return']
    assert capture.events[-1].result is False and capture.issues == []
    assert m.f(5) is True


def test_explicit_axes_cannot_make_a_mutating_numeric_subclass_simple(tmp_path):
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
    with runtime.hook(m.f, axes={'x': [0, 1, 2]}):
        assert m.f(x) is True
    assert x.hits == [1]
    assert runtime.readings[0].status == 'grey' and runtime.readings[0].rows == []


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


def test_axis_provider_uses_each_real_context_and_is_not_called_by_private_probes(tmp_path):
    from flowguard.intent.runtime import _PRIVATE
    m = module(tmp_path, 'def f(config, x: int):\n    return x <= config["limit"]\n')
    runtime = Runtime(tmp_path, previous={})
    seen = []
    def provider(original, bound):
        seen.append(bound.arguments['config']['limit'])
        return {'x': [0, bound.arguments['config']['limit']]}
    with runtime.hook(m.f, axes=provider):
        assert m.f({'limit': 3}, 2) is True
        assert m.f({'limit': 7}, 5) is True
        token = _PRIVATE.set(True)
        try:
            assert m.f({'limit': 9}, 5) is True
        finally:
            _PRIVATE.reset(token)
    assert seen == [3, 7]
    assert len(runtime.readings) == 2


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


def test_axis_provider_cannot_recursively_reenter_instrumented_tool_helpers(tmp_path):
    from flowguard.intent.runtime import _PRIVATE
    source = 'def f(x: int):\n    return x <= 3\ndef analyse(x: int):\n    return x + 1\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={})
    seen = []
    def provider(original, bound):
        seen.append(_PRIVATE.get())
        assert m.analyse(2) == 3
        return {'x': [0, 4]}
    with runtime.hook(m.analyse, axes=provider), runtime.hook(m.f, axes=provider):
        assert m.f(2) is True
    assert seen == [True]
    assert len(runtime.readings) == 1 and runtime.readings[0].target.endswith(':f')


def test_fixture_global_override_is_the_same_context_for_equivalent_refactor(tmp_path):
    old = 'LIMIT = 3\ndef f(x: int):\n    return x <= LIMIT\n'
    source = 'LIMIT = 3\ndef f(x: int):\n    if x > LIMIT:\n        return False\n    return True\n'
    m = module(tmp_path, source)
    m.LIMIT = 100
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with runtime.hook(m.f, axes={'x': [2, 3, 4, 7, 8, 99, 100, 101]}):
        assert m.f(6) is True
    assert m.LIMIT == 100
    assert runtime.readings[0].comparison_status == 'ok'
    assert runtime.readings[0].changed == []


def test_fixture_global_override_is_rechecked_for_each_context_in_one_runtime(tmp_path):
    old = 'LIMIT = 3\ndef f(x: int):\n    return x <= LIMIT\n'
    m = module(tmp_path, old.replace('LIMIT = 3', 'LIMIT = 7'))
    m.LIMIT = 100
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with runtime.hook(m.f, axes={'x': range(0, 10)}):
        assert m.f(2) is True
        m.LIMIT = 7
        assert m.f(2) is True
    assert runtime.readings[0].changed == []
    assert {row['x'] for row, before, after in runtime.readings[1].changed} == {4, 5, 6, 7}
    assert m.LIMIT == 7


@pytest.mark.parametrize('style', ['alias', 'module'])
def test_imported_fixture_global_override_uses_current_source_then_actual_context(tmp_path, style):
    settings = module(tmp_path, 'LIMIT = 7\n', 'r19_settings')
    source = ('from r19_settings import LIMIT\ndef f(x: int):\n    return x <= LIMIT\n'
              if style == 'alias' else 'import r19_settings\ndef f(x: int):\n    return x <= r19_settings.LIMIT\n')
    m = module(tmp_path, source)
    context = m if style == 'alias' else settings
    context.LIMIT = 100
    runtime = Runtime(tmp_path, previous={'r19_settings.py': 'LIMIT = 3\n', 'r19_candidate.py': source})
    with runtime.hook(m.f, axes={'x': range(0, 10)}):
        assert m.f(2) is True
        context.LIMIT = 7
        assert m.f(2) is True
    assert runtime.readings[0].changed == []
    assert {row['x'] for row, before, after in runtime.readings[1].changed} == {4, 5, 6, 7}


def test_deleted_current_constant_is_added_only_for_old_code_then_removed(tmp_path):
    old = 'LIMIT = 4\ndef f(x: int):\n    return x <= LIMIT\n'
    m = module(tmp_path, 'def f(x: int):\n    return x <= 3\n')
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with runtime.hook(m.f, axes={'x': range(0, 8)}):
        assert m.f(2) is True
    reading = runtime.readings[0]
    assert reading.comparison_status == 'ok'
    assert [(row['x'], before, after) for row, before, after in reading.changed] == [(4, True, False)]
    assert 'LIMIT' not in vars(m)


def test_unreadable_current_constant_source_does_not_get_an_invented_old_value(tmp_path):
    old = 'LIMIT = 3\ndef f(x: int):\n    return x <= LIMIT\n'
    m = module(tmp_path, old.replace('LIMIT = 3', 'LIMIT = int("7")'))
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with runtime.hook(m.f, axes={'x': range(0, 10)}):
        assert m.f(2) is True
    reading = runtime.readings[0]
    assert reading.status == 'ok' and reading.rows
    assert reading.comparison_status == 'grey' and reading.changed == []


def test_changed_import_alias_cannot_borrow_the_current_helper_as_old(tmp_path):
    helpers = 'def before(x: int):\n    return x <= 4\ndef after(x: int):\n    return x <= 3\n'
    module(tmp_path, helpers, 'r19_alias_helpers')
    old = 'from r19_alias_helpers import before as decide\ndef f(x: int):\n    return decide(x)\n'
    source = old.replace('import before as decide', 'import after as decide')
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old, 'r19_alias_helpers.py': helpers})
    with runtime.hook(m.f, axes={'x': range(0, 8)}):
        assert m.f(2) is True
    reading = runtime.readings[0]
    assert reading.status == 'ok' and any(row['x'] == 4 and value is False for row, value in reading.rows)
    assert reading.comparison_status == 'grey' and reading.changed == []
    assert any('binding changed' in reason for reason in reading.comparison_reasons)


def test_unchanged_import_alias_still_compares_the_changed_real_helper(tmp_path):
    helpers = 'def before(x: int):\n    return x <= 4\n'
    module(tmp_path, helpers.replace('<= 4', '<= 3'), 'r19_alias_helpers')
    source = 'from r19_alias_helpers import before as decide\ndef f(x: int):\n    return decide(x)\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source, 'r19_alias_helpers.py': helpers})
    with runtime.hook(m.f, axes={'x': range(0, 8)}):
        assert m.f(2) is True
    reading = runtime.readings[0]
    assert reading.comparison_status == 'ok'
    assert [(row['x'], before, after) for row, before, after in reading.changed] == [(4, True, False)]


def test_changed_module_import_and_callable_assignment_bindings_are_unavailable(tmp_path):
    module(tmp_path, 'def allowed(x: int):\n    return x <= 4\n', 'r19_old_rules')
    module(tmp_path, 'def allowed(x: int):\n    return x <= 3\n', 'r19_new_rules')
    old = 'import r19_old_rules as rules\ndef f(x: int):\n    return rules.allowed(x)\n'
    m = module(tmp_path, old.replace('r19_old_rules', 'r19_new_rules'))
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with runtime.hook(m.f, axes={'x': [3, 4]}):
        assert m.f(2) is True
    assert runtime.readings[0].comparison_status == 'grey'
    old = 'from r19_old_rules import allowed as before\nfrom r19_new_rules import allowed as after\ndecide = before\ndef f(x: int):\n    return decide(x)\n'
    m = module(tmp_path, old.replace('decide = before', 'decide = after'))
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with runtime.hook(m.f, axes={'x': [3, 4]}):
        assert m.f(2) is True
    assert runtime.readings[0].comparison_status == 'grey'


def test_changed_exception_class_structure_is_not_the_old_class_by_assumption(tmp_path):
    old = 'class Denied(ValueError):\n    pass\ndef f(x: bool):\n    if x:\n        raise Denied("native")\n    return False\n'
    m = module(tmp_path, old.replace('Denied(ValueError)', 'Denied(RuntimeError)'))
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    with runtime.hook(m.f, axes={'x': [False, True]}):
        assert m.f(False) is False
    assert runtime.readings[0].status == 'ok'
    assert runtime.readings[0].comparison_status == 'grey'


def test_dependency_inside_project_venv_is_not_project_code(tmp_path):
    venv = tmp_path / '.venv'
    (venv / 'lib/python3.12/site-packages').mkdir(parents=True)
    (venv / 'pyvenv.cfg').write_text('home=/external/python\n')
    external = module(venv / 'lib/python3.12/site-packages', 'def helper(x: int):\n    return x <= 4\n', 'r19_external')
    own = module(tmp_path, 'from r19_external import helper\ndef f(x: int):\n    return helper(x)\n')
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': (tmp_path/'r19_candidate.py').read_text()})
    assert runtime._project(own.f)
    assert not runtime._project(external.helper)
    runtime.register(own.f)
    assert external.helper not in runtime.patches
    assert runtime.safety(own.f, {'x': 2}) == ''      # the external helper is not read as project code


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
    with runtime.hook(m.f, axes={'x': range(0, 10)}):
        assert m.f(2) is True
    assert {row['x'] for row, before, after in runtime.readings[0].changed} == {4, 5, 6, 7}


def test_a_missing_baseline_does_not_silently_appear_later(tmp_path):
    from flowguard.map.common import git_run
    source = 'LIMIT = 3\ndef f(x: int):\n    return x <= LIMIT\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path)
    assert runtime.baseline is None
    git_run(tmp_path, 'init', '-q')
    git_run(tmp_path, 'add', '.')
    git_run(tmp_path, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'later')
    with runtime.hook(m.f, axes={'x': [2, 4]}):
        assert m.f(2) is True
    assert runtime.readings[0].status == 'ok' and runtime.readings[0].rows
    assert runtime.readings[0].comparison_status == 'grey'
    assert runtime.readings[0].changed == []


def test_explicit_previous_sources_do_not_consult_git(tmp_path, monkeypatch):
    from flowguard.map import common
    source = 'def f(x: int):\n    return x <= 3\n'
    m = module(tmp_path, source)
    def forbidden(*args, **kwargs):
        raise AssertionError('an explicit source fixture must not consult Git')
    monkeypatch.setattr(common, 'git_run', forbidden)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    with runtime.hook(m.f, axes={'x': [2, 4]}):
        assert m.f(2) is True
    assert runtime.readings[0].comparison_status == 'ok'


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


def test_grey_metadata_restores_private_before_the_one_real_native_exception(tmp_path, monkeypatch):
    from flowguard.intent.runtime import _PRIVATE
    source = 'def f(x: int):\n    raise ValueError("real native error")\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={})
    phases = []
    def safety(original, arguments=None, seen=None, historical=False):
        phases.append(_PRIVATE.get())
        return 'test metadata is unavailable'
    monkeypatch.setattr(runtime, 'safety', safety)
    with runtime.hook(m.f, axes={'x': [0, 1]}) as original:
        def callback(frame, event, arg):
            return None
        with runtime.record({original.__code__: 'F'}, callback=callback):
            with pytest.raises(ValueError, match='real native error'):
                m.f(1)
    assert phases and all(phases)
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


def test_hook_registration_is_private_but_actual_body_reads_ordinary_context(tmp_path, monkeypatch):
    from flowguard.intent.runtime import _PRIVATE
    m = module(tmp_path, 'def f(x: int):\n    return _PRIVATE.get()\n')
    m._PRIVATE = _PRIVATE
    runtime = Runtime(tmp_path, previous={})
    flags = []
    register = runtime.register
    def watched(function):
        flags.append(_PRIVATE.get())
        return register(function)
    monkeypatch.setattr(runtime, 'register', watched)
    with runtime.hook(m.f, axes={'x': [0, 1]}):
        assert m.f(1) is False
    assert flags and all(flags) and not _PRIVATE.get()


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


def test_explicit_partition_keeps_every_representative_and_actual_without_cross_field_constants(tmp_path):
    old = "GRACE = 3\nDEBT = 20\ndef standing(days: int, owed: int, suspended: bool):\n    return days <= GRACE and owed <= DEBT and not suspended\n"
    m = module(tmp_path, old.replace('GRACE = 3', 'GRACE = 7'))
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': old})
    runtime.register(m.standing)
    bound = inspect.signature(m.standing).bind(100, 20, False)
    axes = runtime.axes(m.standing, bound, {'days': [0, 3, 4, 7, 8], 'owed': [0, 20, 21], 'suspended': [False, True]})
    assert axes == {'days': [0, 3, 4, 7, 8, 100], 'owed': [0, 20, 21], 'suspended': [False, True]}
    with runtime.hook(m.standing, axes={'days': range(10), 'owed': [0, 20, 21], 'suspended': [False, True]}):
        assert m.standing(0, 0, False)
    reading = runtime.readings[0]
    original = {(days, owed, suspended) for days in range(10) for owed in (0, 20, 21) for suspended in (False, True)}
    actual = {(row['days'], row['owed'], row['suspended']) for row, value in reading.rows}
    assert original <= actual
    assert actual - original == {(-1, 0, False), (0, -1, False), (0, 1, False)}
    assert len(reading.rows) == len(actual) == 63
    assert {row['days'] for row, old, new in reading.changed} == {4, 5, 6, 7}
    assert all(not row['suspended'] and row['owed'] <= 20 for row, old, new in reading.changed)


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
