"""Implicit Python operators are calls too: the static check never runs them, and an opaque result is not compared."""
import sys

import pytest

from flowguard.intent.runtime import Runtime
from tests.intent_engine.test_runtime_candidate import module


SOURCE = '''hits = []
class C:
    def __class_getitem__(cls, key):
        hits.append('class_getitem')
        return True
class Trap:
    def __getitem__(self, key):
        hits.append('getitem')
        return 3
    def __eq__(self, other):
        hits.append('eq')
        return True
    def __add__(self, other):
        hits.append('add')
        return 3
    def __bool__(self):
        hits.append('bool')
        return True
    @property
    def ready(self):
        hits.append('property')
        return True
TRAP = Trap()
VALUES = [TRAP]
def class_subscription(x): return C[x]
def context_subscription(context, x): return context[0] > x
def global_compare(x): return TRAP == x
def global_binop(x): return TRAP + x > 0
def global_boolop(x): return TRAP and x > 0
def global_attribute(x): return TRAP.ready and x > 0
def container_compare(x): return VALUES == [x]
def local_alias(x):
    value = TRAP
    return value == x
'''


@pytest.mark.parametrize('name', ['class_subscription', 'context_subscription', 'global_compare', 'global_binop',
                                  'global_boolop', 'global_attribute', 'container_compare', 'local_alias'])
def test_the_static_check_runs_no_implicit_operator(tmp_path, name):
    # Only the static check: what a replay of these does is the replay guard's (its in-memory effects
    # are a documented known miss).
    m = module(tmp_path, SOURCE)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': SOURCE})
    arguments = {'context': [m.TRAP], 'x': 1} if name == 'context_subscription' else {'x': 1}
    assert runtime.safety(getattr(m, name), arguments) == ''
    assert m.hits == []


def test_static_resolution_never_reads_a_metaclass_dictionary_property(tmp_path):
    source = '''hits=[]
class Meta(type):
    def __getattribute__(self, name):
        hits.append(name)
        return super().__getattribute__(name)
class Owner(metaclass=Meta):
    limit = 3
def decision(x): return Owner.limit > x
'''
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    assert runtime.safety(m.decision, {'x': 1}) == ''      # the static check runs no project code
    assert m.hits == []


def test_inert_container_and_simple_local_arithmetic_are_replayed(tmp_path):
    source = 'VALUES = [3]\ndef decision(x):\n    net = x - 1\n    return VALUES[0] > net\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    with runtime.hook(m.decision, axes={'x': [0, 1, 4]}):
        assert m.decision(1) is True
    assert runtime.readings[0].status == 'ok' and len(runtime.readings[0].rows) == 4
    assert {row['x']: value for row, value in runtime.readings[0].rows} == {0: True, 1: True, 2: True, 4: False}


def test_body_import_is_rejected_before_it_can_load_a_dependency(tmp_path, monkeypatch):
    from flowguard.intent import anchors
    from tests.intent_engine.test_anchors import source
    root, index = source(tmp_path, '# flowguard: sensor decision(x: count) -> allowed: bool\ndef decision(x: int) -> bool:\n    import r19_side_effect\n    return x > 0\n')
    (root / 'r19_side_effect.py').write_text('from pathlib import Path\nPath("dependency.marker").write_text("bad")\n')
    monkeypatch.chdir(root)
    observed = anchors.observe(root, index.entries[0], {'x': 1})
    # The import runs under the replay guard: the dependency's write is refused before it happens.
    assert observed.status == 'grey' and any('replay refused' in reason and 'dependency.marker' in reason for reason in observed.reasons)
    assert 'r19_side_effect' not in sys.modules and not (root / 'dependency.marker').exists()


def test_an_opaque_result_cannot_run_its_custom_equality_during_recheck(tmp_path):
    source = 'hits=[]\nclass Trap:\n    def __eq__(self, other):\n        hits.append("eq")\n        return True\nVALUE=Trap()\ndef decision(x): return VALUE\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    with runtime.hook(m.decision, axes={'x': [0, 1]}):
        assert m.decision(1) is m.VALUE
    assert m.hits == [] and runtime.readings[0].status == 'grey'
    assert runtime.readings[0].rows == []


def test_variadic_helper_cannot_drop_an_opaque_argument_from_the_source_proof(tmp_path):
    source = 'hits=[]\nclass Trap:\n    def __eq__(self, other):\n        hits.append("eq")\n        return True\nVALUE=Trap()\ndef hidden(*args): return args[-1]\ndef decision(x): return hidden(x, VALUE)\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    with runtime.hook(m.decision, axes={'x': [0, 1]}):
        assert m.decision(1) is m.VALUE
    assert m.hits == [] and runtime.readings[0].status == 'grey'
    assert runtime.readings[0].rows == []


def test_inert_helper_defaults_keep_the_real_binding_and_can_be_replayed(tmp_path):
    source = 'def increment(x, *, step=1): return x + step\ndef decision(x): return increment(x) > 2\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    with runtime.hook(m.decision, axes={'x': [0, 1, 3]}):
        assert m.decision(1) is False
    assert runtime.readings[0].status == 'ok' and len(runtime.readings[0].rows) == 4
    assert {row['x']: value for row, value in runtime.readings[0].rows} == {0: False, 1: False, 2: True, 3: True}


def test_sql_read_with_a_custom_row_callback_is_not_executed_by_metadata_or_grid(tmp_path):
    import sqlite3
    source = 'def decision(db, x):\n    db.execute("SELECT COUNT(*) FROM count").fetchall()\n    return True\n'
    m = module(tmp_path, source)
    calls = []
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE count(n)')
        def row(cursor, values):
            calls.append(values)
            return values
        db.row_factory = row
        runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
        assert runtime.safety(m.decision, {'db': db, 'x': 1}) and calls == []
        with runtime.hook(m.decision, axes={'x': [0, 1]}):
            assert m.decision(db, 1) is True
        assert len(calls) == 1
    assert runtime.readings[0].status == 'grey' and runtime.readings[0].rows == []
