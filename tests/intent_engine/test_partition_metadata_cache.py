"""Static metadata reuse cannot cache an observation or borrow another code/domain."""
import inspect
import sqlite3
from types import SimpleNamespace

from flowguard.intent import anchors, cells, plugin
from flowguard.intent import runtime as R
from tests.intent_engine.test_runtime_candidate import module


def fixture(tmp_path, source, *, parameters=None):
    app = module(tmp_path, source, name='r19_partition_cache')
    runtime = R.Runtime(tmp_path, previous={'r19_partition_cache.py': source})
    runtime.register(app.decision)
    point = dict(anchor=None, parameters=parameters or (anchors.Parameter('x', 'count', 'int'),),
                 fn=app.decision, file='r19_partition_cache.py')
    owner = SimpleNamespace(cfg=SimpleNamespace(root=tmp_path), runtime=runtime, metadata={})
    return app, runtime, point, owner


def partition(owner, point, function, *args):
    return plugin.Observations._partition(owner, point, function, inspect.signature(function).bind(*args))


def count_reads(monkeypatch):
    calls = []
    original = cells.read_predicate
    def measured(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(cells, 'read_predicate', measured)
    return calls


def test_closed_partition_reuses_static_reads_and_isolates_mutable_consumers(tmp_path, monkeypatch):
    app, _, point, owner = fixture(tmp_path, 'def decision(x: int): return x <= 3\n')
    reads = count_reads(monkeypatch)
    axes, part, reasons = partition(owner, point, app.decision, 0)
    assert part.complete and not reasons
    expected = {name: list(values) for name, values in axes.items()}
    axes['x'].append(991)
    part.regions[0].inputs['x'] = 999
    part.reasons.append('consumer mutation')
    again, proof, reasons = partition(owner, point, app.decision, 100)
    assert len(reads) == 2
    assert again == expected and 991 not in again['x']
    assert all(region.inputs['x'] != 999 for region in proof.regions)
    assert proof.complete and not proof.reasons and not reasons


def test_fixture_constant_override_repartitions_and_observes_new_real_outcome(tmp_path, monkeypatch):
    app, runtime, point, owner = fixture(tmp_path, 'LIMIT = 3\ndef decision(x: int): return x <= LIMIT\n')
    reads = count_reads(monkeypatch)
    before, _, _ = partition(owner, point, app.decision, 5)
    bound = inspect.signature(app.decision).bind(5)
    assert runtime.observe(app.decision, bound, axes=before) is False
    app.LIMIT = 7
    after, proof, reasons = partition(owner, point, app.decision, 5)
    assert len(reads) == 4 and proof.complete and not reasons
    assert before != after
    assert runtime.observe(app.decision, bound, axes=after) is True
    assert any(inputs['x'] == 5 and outcome is True for inputs, outcome in runtime.readings[-1].rows)


def test_current_source_bytes_invalidate_metadata_even_when_loaded_code_is_identical(tmp_path, monkeypatch):
    app, _, point, owner = fixture(tmp_path, 'def decision(x: int): return x <= 3\n')
    reads = count_reads(monkeypatch)
    partition(owner, point, app.decision, 0)
    code = app.decision.__code__
    (tmp_path / point['file']).write_text('def decision(x: int): return x <= 7\n')
    partition(owner, point, app.decision, 0)
    assert app.decision.__code__ is code and len(reads) == 4


def test_equal_but_distinct_code_object_does_not_borrow_partition(tmp_path, monkeypatch):
    app, _, point, owner = fixture(tmp_path, 'def decision(x: int): return x <= 3\n')
    reads = count_reads(monkeypatch)
    partition(owner, point, app.decision, 0)
    original = app.decision.__code__
    replaced = original.replace()
    assert replaced == original and replaced is not original
    app.decision.__code__ = replaced
    partition(owner, point, app.decision, 0)
    assert len(reads) == 4


def test_new_baseline_identity_does_not_borrow_partition(tmp_path, monkeypatch):
    app, runtime, point, owner = fixture(tmp_path, 'def decision(x: int): return x <= 3\n')
    reads = count_reads(monkeypatch)
    partition(owner, point, app.decision, 0)
    runtime.baseline = 'another immutable baseline'
    partition(owner, point, app.decision, 0)
    assert len(reads) == 4


def test_inferred_actual_kind_repartitions_int_and_float(tmp_path, monkeypatch):
    parameters = (anchors.Parameter('x', 'count', '?', inferred=True),)
    app, _, point, owner = fixture(tmp_path, 'def decision(x): return x <= 3\n', parameters=parameters)
    reads = count_reads(monkeypatch)
    ints, _, _ = partition(owner, point, app.decision, 1)
    floats, proof, reasons = partition(owner, point, app.decision, 1.5)
    assert len(reads) == 4 and proof.complete and not reasons
    assert all(type(value) is int for value in ints['x'])
    assert any(type(value) is float and not value.is_integer() for value in floats['x'])


def test_actual_value_and_existing_neighbours_stay_fresh_without_reducing_replay(tmp_path, monkeypatch):
    app, runtime, point, owner = fixture(tmp_path, 'def decision(x: int): return x <= 3\n')
    reads = count_reads(monkeypatch)
    values = []
    original = R._value
    def measured(*args, **kwargs):
        values.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(R, '_value', measured)
    axes, _, _ = partition(owner, point, app.decision, 0)
    first = runtime.observe(app.decision, inspect.signature(app.decision).bind(0), axes=axes)
    first_count = len(values)
    fresh, _, _ = partition(owner, point, app.decision, 100)
    second = runtime.observe(app.decision, inspect.signature(app.decision).bind(100), axes=fresh)
    assert first is True and second is False and len(reads) == 2
    assert len(values) - first_count == first_count > 0
    assert any(inputs['x'] == 100 and outcome is False for inputs, outcome in runtime.readings[-1].rows)
    generic = runtime.axes(app.decision, inspect.signature(app.decision).bind(100))
    assert {99, 100, 101} <= set(generic['x'])
    assert axes == fresh  # Actual values do not leak back into static pools.


def test_same_input_and_same_database_object_are_observed_again_after_data_changes(tmp_path, monkeypatch):
    source = ("def decision(db, x: int):\n    debt = db.execute('SELECT amount FROM obligations').fetchone()\n"
              '    return debt is None or x <= 3\n')
    parameters = (anchors.Parameter('db', '', 'sqlite3.Connection', role='context'),
                  anchors.Parameter('x', 'count', 'int'))
    app, runtime, point, owner = fixture(tmp_path, source, parameters=parameters)
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE obligations(amount INTEGER)')
        bound = inspect.signature(app.decision).bind(db, 100)
        axes, _, _ = partition(owner, point, app.decision, db, 100)
        assert runtime.observe(app.decision, bound, axes=axes) is True
        db.execute('INSERT INTO obligations VALUES (1)')
        axes, _, _ = partition(owner, point, app.decision, db, 100)
        assert runtime.observe(app.decision, bound, axes=axes) is False
        assert any(inputs['x'] == 100 and outcome is False for inputs, outcome in runtime.readings[-1].rows)


def test_unknown_numeric_range_is_never_reused_as_a_closed_proof(tmp_path, monkeypatch):
    app, _, point, owner = fixture(tmp_path, 'def decision(x: int): return x * x\n')
    reads = count_reads(monkeypatch)
    for value in (3, 7):
        _, proof, reasons = partition(owner, point, app.decision, value)
        assert proof is None and reasons
    assert len(reads) == 8


def test_noninert_relevant_global_is_not_hashed_compared_or_cached(tmp_path, monkeypatch):
    app, _, point, owner = fixture(tmp_path, 'LIMIT = 3\ndef decision(x: int): return x <= LIMIT\n')
    class Hostile:
        def __hash__(self): raise AssertionError('user hash must not run')
        def __eq__(self, other): raise AssertionError('user equality must not run')
        def __getattribute__(self, name): raise AssertionError('user attribute must not run')
    app.LIMIT = Hostile()
    reads = count_reads(monkeypatch)
    partition(owner, point, app.decision, 0)
    partition(owner, point, app.decision, 0)
    assert len(reads) == 4


def test_declared_role_and_units_are_part_of_the_static_partition_identity(tmp_path, monkeypatch):
    app, _, point, owner = fixture(tmp_path, 'def decision(x: int): return x <= 3\n')
    reads = count_reads(monkeypatch)
    partition(owner, point, app.decision, 0)
    point['parameters'] = (anchors.Parameter('x', 'seconds', 'int'),)
    partition(owner, point, app.decision, 0)
    assert len(reads) == 4
    point['parameters'] = (anchors.Parameter('x', 'seconds', 'int', role='context'),)
    axes, _, _ = partition(owner, point, app.decision, 0)
    assert len(reads) == 6 and axes == {}


def test_functions_in_one_file_share_source_trees_without_sharing_their_partition(tmp_path):
    source = 'def decision(x: int): return x <= 3\ndef peer(x: int): return x <= 7\n'
    app, runtime, point, owner = fixture(tmp_path, source)
    first, _, _ = partition(owner, point, app.decision, 0)
    runtime.register(app.peer)
    peer = dict(point, fn=app.peer)
    second, _, _ = partition(owner, peer, app.peer, 0)
    left = owner.metadata[(point['file'], app.decision.__qualname__)]
    right = owner.metadata[(point['file'], app.peer.__qualname__)]
    assert left['tree'] is right['tree'] and left['old_tree'] is right['old_tree']
    assert left['current'] is not right['current'] and first != second
