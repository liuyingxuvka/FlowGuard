"""Implicit Python operators are calls too: the static check never runs them, and an opaque result is not compared."""
import sys

import pytest

from flowguard.intent.runtime import Runtime, sealed
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
    # Qualification and the closed runner both refuse opaque bindings without inspecting them.
    m = module(tmp_path, SOURCE)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': SOURCE})
    arguments = {'context': [m.TRAP], 'x': 1} if name == 'context_subscription' else {'x': 1}
    reason = {'class_subscription': 'uses unavailable binding C',
              'context_subscription': 'not JSON data',
              'global_attribute': 'uses attribute ready',
              'container_compare': 'uses unavailable binding VALUES'}.get(name, 'uses unavailable binding TRAP')
    assert runtime.safety(getattr(m, name), arguments) == reason
    assert sealed(SOURCE, name, [], arguments) == {'status': 'unavailable', 'reason': reason}
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
    assert runtime.safety(m.decision, {'x': 1}) == 'uses attribute limit'
    assert sealed(source, 'decision', [1], {}) == {'status': 'unavailable', 'reason': 'uses attribute limit'}
    assert m.hits == []


def test_inert_container_and_simple_local_arithmetic_are_replayed(tmp_path):
    source = 'VALUES = [3]\ndef decision(x):\n    net = x - 1\n    return VALUES[0] > net\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    with runtime.hook(m.decision, axes={'x': [0, 1, 4]}):
        assert m.decision(1) is True
    [reading] = runtime.readings
    assert reading.actual == ({'x': 1}, True)
    assert reading.sample == {'args': [1], 'kwargs': {}, 'inputs': {'x': 1}}
    assert reading.json_result is True and reading.rows == []
    # These are explicit closed calls, preserving all four old witnesses, not automatic hot-path replay.
    results = {x: sealed(source, 'decision', [x], {}) for x in (0, 1, 2, 4)}
    assert len(results) == 4
    assert results == {x: {'status': 'ok', 'value': value} for x, value in {0: True, 1: True, 2: True, 4: False}.items()}
    assert m.VALUES == [3]


def test_body_import_is_rejected_before_it_can_load_a_dependency(tmp_path, monkeypatch):
    from flowguard.intent import anchors
    from tests.intent_engine.test_anchors import source
    root, index = source(tmp_path, '# flowguard: sensor decision(x: count) -> allowed: bool\ndef decision(x: int) -> bool:\n    import r19_side_effect\n    return x > 0\n')
    (root / 'r19_side_effect.py').write_text('from pathlib import Path\nPath("dependency.marker").write_text("bad")\n')
    monkeypatch.chdir(root)
    observed = anchors.observe(root, index.entries[0], {'x': 1})
    # The source is refused before its body import can initialize the dependency.
    assert observed.status == 'grey' and observed.reasons == ('unsupported Import',)
    candidate = (root / index.entries[0].file).read_text(encoding='utf-8')
    assert sealed(candidate, 'decision', [1], {}) == {'status': 'unavailable', 'reason': 'unsupported Import'}
    assert 'r19_side_effect' not in sys.modules and not (root / 'dependency.marker').exists()


def test_an_opaque_result_cannot_run_its_custom_equality_during_recheck(tmp_path):
    source = 'hits=[]\nclass Trap:\n    def __eq__(self, other):\n        hits.append("eq")\n        return True\nVALUE=Trap()\ndef decision(x): return VALUE\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    with runtime.hook(m.decision, axes={'x': [0, 1]}):
        assert m.decision(1) is m.VALUE
    [reading] = runtime.readings
    assert reading.actual_inputs == {'x': 1} and reading.actual[1] is m.VALUE
    assert reading.sample is None and reading.reasons == ['not JSON data'] and reading.rows == []
    assert sealed(source, 'decision', [1], {}) == {'status': 'unavailable', 'reason': 'uses unavailable binding VALUE'}
    assert m.hits == []


def test_variadic_helper_cannot_drop_an_opaque_argument_from_the_source_proof(tmp_path):
    source = 'hits=[]\nclass Trap:\n    def __eq__(self, other):\n        hits.append("eq")\n        return True\nVALUE=Trap()\ndef hidden(*args): return args[-1]\ndef decision(x): return hidden(x, VALUE)\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    with runtime.hook(m.decision, axes={'x': [0, 1]}):
        assert m.decision(1) is m.VALUE
    [reading] = runtime.readings
    assert reading.actual_inputs == {'x': 1} and reading.actual[1] is m.VALUE
    assert reading.sample is None and reading.reasons == ['not JSON data'] and reading.rows == []
    assert sealed(source, 'decision', [1], {}) == {'status': 'unavailable', 'reason': 'uses unavailable binding VALUE'}
    assert m.hits == []


def test_inert_helper_defaults_keep_the_real_binding_and_can_be_replayed(tmp_path):
    source = 'def increment(x, *, step=1): return x + step\ndef decision(x): return increment(x) > 2\n'
    m = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    with runtime.hook(m.decision, axes={'x': [0, 1, 3]}):
        assert m.decision(1) is False
    [reading] = runtime.readings
    assert reading.actual == ({'x': 1}, False)
    assert reading.sample == {'args': [1], 'kwargs': {}, 'inputs': {'x': 1}}
    assert reading.json_result is False and reading.rows == []
    # Explicit witnesses still test literal keyword-only defaults through the sole closed runner.
    results = {x: sealed(source, 'decision', [x], {}) for x in (0, 1, 2, 3)}
    assert len(results) == 4
    assert results == {x: {'status': 'ok', 'value': value} for x, value in {0: False, 1: False, 2: True, 3: True}.items()}


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
        assert sealed(source, 'decision', [db, 1], {})['status'] == 'unavailable'
        assert len(calls) == 1
    [reading] = runtime.readings
    assert reading.actual_inputs['db'] is db and reading.actual == ({'db': db, 'x': 1}, True)
    assert reading.sample is None and reading.reasons == ['not JSON data'] and reading.rows == []
