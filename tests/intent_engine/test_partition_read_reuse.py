"""Reuse only an unchanged static input domain; observations remain fresh."""
import inspect
from types import SimpleNamespace

from flowguard.intent import anchors, cells, plugin
from flowguard.intent.runtime import Runtime
from tests.intent_engine.test_runtime_candidate import module


def fixture(tmp_path, source):
    actual = module(tmp_path, source)
    runtime = Runtime(tmp_path, previous={'r19_candidate.py': source})
    runtime.register(actual.decision)
    point = dict(anchor=None, parameters=(anchors.Parameter('x', 'count', 'int'),),
                 fn=actual.decision, file='r19_candidate.py')
    owner = SimpleNamespace(cfg=SimpleNamespace(root=tmp_path), runtime=runtime)
    return actual, runtime, point, owner


def test_removed_unknown_numeric_domain_is_reread_and_never_declared_complete(tmp_path, monkeypatch):
    actual, runtime, point, owner = fixture(tmp_path, 'def decision(x: int): return x * x\n')
    calls = []
    original = cells.read_predicate
    def count(*args, **kwargs):
        calls.append(dict(args[1]))
        return original(*args, **kwargs)
    monkeypatch.setattr(cells, 'read_predicate', count)
    bound = inspect.signature(actual.decision).bind(7)
    axes, partition, unknown = plugin.Observations._partition(owner, point, actual.decision, bound)
    assert len(calls) == 4 and calls[-1] == calls[-2] == {}
    assert partition is None and any('no closed range' in reason for reason in unknown)
    assert axes['x']


def test_closed_static_domain_reuses_both_readings_but_actual_value_is_still_appended(tmp_path, monkeypatch):
    actual, runtime, point, owner = fixture(tmp_path, 'def decision(x: int): return x <= 3\n')
    calls = []
    original = cells.read_predicate
    def count(*args, **kwargs):
        calls.append(dict(args[1]))
        return original(*args, **kwargs)
    monkeypatch.setattr(cells, 'read_predicate', count)
    bound = inspect.signature(actual.decision).bind(100)
    axes, partition, unknown = plugin.Observations._partition(owner, point, actual.decision, bound)
    assert len(calls) == 2 and partition.complete and not unknown
    assert 100 not in axes['x']  # The static representatives are not business-result caching.
    assert runtime.observe(actual.decision, bound, axes=axes) is False
    reading = runtime.readings[-1]
    assert any(row['x'] == 100 and value is False for row, value in reading.rows)
    assert reading.status == 'ok'
