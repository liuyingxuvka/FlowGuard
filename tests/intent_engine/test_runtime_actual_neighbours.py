"""Actual-call neighbours supplement every proved source partition."""
import inspect

from flowguard.intent import anchors
from flowguard.intent.config import load_config
from flowguard.intent.plugin import Observations
from flowguard.intent.runtime import Runtime
from tests.intent_engine.test_runtime_candidate import module


def partition(root, function, source, arguments):
    index = anchors.collect_sources(root, [('r19_candidate.py', 'r19_candidate', False)])
    anchor = next(entry for entry in index.entries if entry.qual == function.__qualname__)
    observation = object.__new__(Observations)
    observation.cfg = load_config(root)
    observation.runtime = runtime = Runtime(root, previous={'r19_candidate.py': source})
    observation.metadata = {}
    runtime.register(function)
    point = dict(anchor=anchor, file=anchor.file, fn=function)
    bound = inspect.signature(function).bind(*arguments)
    axes, part, unknown = observation._partition(point, function, bound)
    return runtime, bound, axes, part, unknown


def test_closed_partition_retains_actual_integer_and_both_its_neighbours(tmp_path):
    source = '# flowguard: sensor LIMIT(x: count) -> allowed: bool\ndef decision(x: int) -> bool:\n    return x <= 3\n'
    m = module(tmp_path, source)
    runtime, bound, axes, part, unknown = partition(tmp_path, m.decision, source, (100,))
    assert part.complete and unknown == []
    assert runtime.observe(m.decision, bound, axes=axes) is False
    reading = runtime.readings[0]
    assert reading.status == 'ok'
    points = {row['x'] for row, value in reading.rows}
    assert set(axes['x']) <= points
    assert {99, 100, 101} <= points


def test_neighbours_are_single_axis_witnesses_without_removing_the_closed_grid(tmp_path):
    import itertools
    source = '# flowguard: sensor LIMIT(x: count, y: count) -> allowed: bool\ndef decision(x: int, y: int) -> bool:\n    return x <= 3 and y <= 20\n'
    m = module(tmp_path, source)
    runtime, bound, axes, part, unknown = partition(tmp_path, m.decision, source, (100, 200))
    assert part.complete and unknown == []
    assert runtime.observe(m.decision, bound, axes=axes) is False
    points = {tuple(row[name] for name in ('x', 'y')) for row, value in runtime.readings[0].rows}
    old_grid = set(itertools.product([*axes['x'], 100], [*axes['y'], 200]))
    assert old_grid <= points
    assert points - old_grid == {(99, 200), (101, 200), (100, 199), (100, 201)}


def test_reused_database_context_is_read_again_for_actual_neighbour_witnesses(tmp_path):
    import sqlite3
    source = '''# flowguard: sensor LIMIT(x: count; db) -> allowed: bool
def decision(db, x: int) -> bool:
    debt = db.execute('SELECT n FROM debt').fetchone()
    return debt is None or debt[0] < x
'''
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE debt(n INTEGER)')
        with runtime.hook(m.decision, axes={'x': [2, 4]}):
            assert m.decision(db, 100) is True
            db.execute('INSERT INTO debt VALUES (101)')
            assert m.decision(db, 100) is False
    assert len(runtime.readings) == 2
    for reading in runtime.readings:
        assert reading.status == 'ok' and reading.context == ('db',)
        assert {2, 4, 99, 100, 101} == {row['x'] for row, value in reading.rows}
    assert all(value is True for row, value in runtime.readings[0].rows)
    assert all(value is False for row, value in runtime.readings[1].rows)


def test_opaque_numeric_subclass_runs_only_its_real_operator(tmp_path):
    source = '''class Trap(int):
    hits = []
    def __le__(self, other):
        self.hits.append('compare')
        return True
    def __add__(self, other):
        self.hits.append('add')
        return self
    def __sub__(self, other):
        self.hits.append('subtract')
        return self
def decision(x: int):
    return x <= 3
'''
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    with runtime.hook(m.decision, axes={'x': [0, 3, 4]}):
        assert m.decision(m.Trap(100)) is True
    assert m.Trap.hits == ['compare']
    assert runtime.readings[0].status == 'grey' and runtime.readings[0].rows == []


def test_native_date_endpoints_skip_only_the_unrepresentable_neighbour(tmp_path):
    from datetime import date, timedelta
    source = 'from datetime import date\ndef decision(x: date):\n    return x <= date(2000, 1, 1)\n'
    m = module(tmp_path, source)
    for actual, neighbour in ((date.min, date.min + timedelta(days=1)), (date.max, date.max - timedelta(days=1))):
        runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
        bound = inspect.signature(m.decision).bind(actual)
        assert runtime.observe(m.decision, bound, axes={'x': [actual]}) is (actual == date.min)
        assert {row['x'] for row, value in runtime.readings[0].rows} == {actual, neighbour}


def test_finite_enum_boolean_and_none_inputs_do_not_gain_arithmetic_values(tmp_path):
    source = '''from enum import IntEnum
class Level(IntEnum):
    LOW = 1
    HIGH = 2
def decision(x: Level):
    return x is Level.LOW
def optional(x: int | None):
    return x is None or x <= 3
def boolean(x: bool):
    return x
'''
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    bound = inspect.signature(m.decision).bind(m.Level.LOW)
    finite = runtime.axes(m.decision, bound, {'x': [m.Level.LOW, m.Level.HIGH]})
    generic = runtime.axes(m.decision, bound)
    assert finite['x'] == [m.Level.LOW, m.Level.HIGH]
    assert generic['x'] == [m.Level.LOW]
    assert all(type(value) is m.Level for value in [*finite['x'], *generic['x']])
    cases = [(m.optional, None, [None, 0, 4]), (m.boolean, False, [False, True])]
    for function, actual, representatives in cases:
        runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
        bound = inspect.signature(function).bind(actual)
        runtime.observe(function, bound, axes={'x': representatives})
        assert runtime.readings[0].status == 'ok'
        points = [row['x'] for row, value in runtime.readings[0].rows]
        assert len(points) == len(representatives)
        assert all(any(value is expected or type(value) is type(expected) and value == expected for expected in representatives)
                   for value in points)


def test_native_neighbour_type_gate_does_not_call_a_metaclass_equality_hook():
    from flowguard.intent.runtime import _neighbours
    hits = []
    class Meta(type):
        def __eq__(cls, other):
            hits.append(other)
            return False
    class Opaque(metaclass=Meta):
        pass
    assert list(_neighbours(Opaque())) == []
    assert hits == []


def test_decimal_neighbour_overflow_without_a_trap_does_not_inject_infinity(tmp_path):
    from decimal import Decimal, Overflow, localcontext
    from flowguard.intent.runtime import _neighbours
    source = 'from decimal import Decimal\ndef decision(x: Decimal):\n    return x < Decimal("1000")\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    with localcontext() as context:
        context.Emax = 2
        context.traps[Overflow] = False
        actual = Decimal('999')
        assert list(_neighbours(actual)) == [Decimal('998')]
        assert runtime.observe(m.decision, inspect.signature(m.decision).bind(actual), axes={'x': [actual]})
        reading = runtime.readings[0]
        assert reading.status == 'ok'
        points = {row['x'] for row, value in reading.rows}
        assert points == {Decimal('998'), Decimal('999')}
        assert all(value.is_finite() for value in points)
