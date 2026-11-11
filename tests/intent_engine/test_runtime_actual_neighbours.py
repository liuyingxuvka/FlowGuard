"""Neighbour values never run a project operator, and opaque numbers are not recorded."""
import inspect

from flowguard.intent.runtime import Runtime
from tests.intent_engine.test_runtime_candidate import module


def test_opaque_numeric_subclass_runs_only_its_real_operator_and_is_not_recorded(tmp_path):
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
    with runtime.hook(m.decision):
        assert m.decision(m.Trap(100)) is True
    assert m.Trap.hits == ['compare']          # no neighbour arithmetic ran on the subclass
    reading, = runtime.readings
    assert reading.sample is None and reading.reasons == ['not JSON data'] and reading.rows == []


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


def test_decimal_neighbour_overflow_without_a_trap_does_not_inject_infinity_or_replay(tmp_path):
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
        assert runtime.observe(m.decision, inspect.signature(m.decision).bind(actual))
        reading, = runtime.readings
        # A Decimal is not JSON: the real call is kept, nothing is replayed or recorded for comparison.
        assert reading.actual == ({'x': actual}, True) and reading.rows == []
        assert reading.sample is None and reading.reasons == ['not JSON data']
