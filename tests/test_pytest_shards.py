from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import flowguard

import pytest

from flowguard.pytest_shards import (
    aggregate_pytest_projections,
    nodeid_fingerprint,
    partition_nodeids,
    validate_partition,
)


def test_hash_fallback_is_stable_when_unrelated_nodes_are_added():
    nodeids = tuple(f"tests/test_{index}.py::test_case" for index in range(40))
    first = partition_nodeids(nodeids, 4)
    second = partition_nodeids(nodeids, 4)
    expanded = partition_nodeids(nodeids + ("tests/test_new.py::test_new",), 4)

    assert first == second
    assert len(first) <= 4
    assert validate_partition(nodeids, first)["exact_union"] is True
    assert all(set(left).isdisjoint(right) for index, left in enumerate(first) for right in first[index + 1 :])
    owners = {
        nodeid: index
        for index, shard in enumerate(first)
        for nodeid in shard
    }
    expanded_owners = {
        nodeid: index
        for index, shard in enumerate(expanded)
        for nodeid in shard
    }
    assert all(expanded_owners[nodeid] == owners[nodeid] for nodeid in nodeids)
    assert nodeid_fingerprint(nodeids) != nodeid_fingerprint(nodeids + ("new",))


def test_aggregate_requires_exact_union_and_preserves_native_counters():
    expected = ("tests/test_a.py::test_a", "tests/test_b.py::test_b")
    projections = [
        {
            "node_ids": [expected[0]],
            "selected": 1,
            "passed": 1,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "xfailed": 0,
            "xpassed": 0,
            "skip_details": [],
            "optional_metadata_unverified": False,
        },
        {
            "node_ids": [expected[1]],
            "selected": 1,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 1,
            "xfailed": 0,
            "xpassed": 0,
            "skip_details": [{"node_id": expected[1], "required": True}],
            "optional_metadata_unverified": False,
        },
    ]
    aggregate = aggregate_pytest_projections(projections, expected)
    assert aggregate["selected"] == 2
    assert aggregate["passed"] == 1
    assert aggregate["skipped"] == 1
    assert aggregate["node_ids"] == list(expected)

    with pytest.raises(ValueError, match="overlap"):
        aggregate_pytest_projections([projections[0], projections[0]], expected)


def _recorder_copy():
    path = Path(flowguard.__file__).with_name("pytest_nodeid_recorder.py")
    spec = importlib.util.spec_from_file_location("recorder_copy_for_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)   # separate globals: the live session's recorder is untouched
    return module


def test_recorder_keeps_the_worst_phase_outcome():
    rec = _recorder_copy()
    report = lambda when, outcome: SimpleNamespace(nodeid="t.py::a", when=when, passed=outcome == "passed",
                                                   failed=outcome == "failed", skipped=outcome == "skipped",duration=.1)
    rec.pytest_runtest_logreport(report("setup", "passed"))
    rec.pytest_runtest_logreport(report("call", "skipped"))
    rec.pytest_runtest_logreport(report("teardown", "passed"))
    assert rec._STATUSES == {"t.py::a": "skipped"}
    assert rec._SECONDS["t.py::a"]==pytest.approx(.3)
    rec.pytest_runtest_logreport(SimpleNamespace(nodeid="t.py::b", when="teardown", passed=False, failed=True, skipped=False))
    assert rec._STATUSES["t.py::b"] == "error"
    rec.pytest_collectreport(SimpleNamespace(nodeid="t2.py", passed=False, skipped=True))
    assert rec._NODEIDS == ["t.py::a", "t.py::b", "t2.py"] and rec._STATUSES["t2.py"] == "skipped"


def test_recorder_writes_node_outcomes_and_resets_each_run(tmp_path, monkeypatch):
    rec = _recorder_copy()
    session = SimpleNamespace(config=SimpleNamespace(rootpath=tmp_path, option=SimpleNamespace(xmlpath=None)))
    target = tmp_path / "nodeids.json"
    monkeypatch.setenv("FLOWGUARD_PYTEST_NODEIDS", str(target))
    rec.pytest_sessionstart(session)
    rec.pytest_runtest_logreport(SimpleNamespace(nodeid="t.py::a", when="call", passed=True, failed=False, skipped=False,duration=.25))
    rec.pytest_sessionfinish(session, 0)
    record = json.loads(target.read_text())
    assert record["nodeids"] == ["t.py::a"] and record["statuses"] == {"t.py::a": "passed"}
    assert record["seconds"]=={"t.py::a":.25}
    assert "input_digest_before" not in record
    rec.pytest_sessionstart(session)
    assert rec._NODEIDS == [] and rec._STATUSES == {} and rec._SECONDS=={}


def test_partition_is_exact_and_a_union_of_subtrees(tmp_path):
    import runpy
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.tree import build_tree
    from flowguard.map.testtree import test_units,test_positions
    base=Path(__file__).parents[1]/'.flowguard'
    helper=base/'target/models/_testtree_fixture.py'
    if not helper.exists():helper=base/'models/_testtree_fixture.py'
    data,nodeids=runpy.run_path(str(helper))['fixture'](tmp_path)
    inv=build_inventory(tmp_path,DEFAULT_IGNORE,write_cache=False);tree=build_tree(tmp_path,data,inv)
    weights=dict.fromkeys(nodeids,1)
    units=test_units(tmp_path,data,inv,tree,nodeids,weights,2)
    assert 'core' in units and len(units['core'])==2
    assert test_positions(tmp_path,data,inv,tree,nodeids)[nodeids[-1]]=='other'
    shards=partition_nodeids(nodeids,2,units=units,weights=weights)
    assert len(shards)<=2 and validate_partition(nodeids,shards)['exact_union']
    assert all(any(set(unit)<=set(shard) for shard in shards) for unit in units.values())
    assert any(set(units['other'])<=set(shard) for shard in shards)
    expanded=nodeids+tuple('tests/test_big.py::test_big_'+str(index) for index in range(41))
    heavy=test_units(tmp_path,data,inv,tree,expanded,dict.fromkeys(expanded,1),4)
    assert all(len(items)<=len(expanded)/4 for items in heavy.values())
    assert any('test_big.py::test_big_' in name for name in heavy)
    assert validate_partition(expanded,partition_nodeids(expanded,4,units=heavy))['exact_union']
    cases=(nodeids[0]+'[one]',nodeids[0]+'[two]',*nodeids[1:])
    case_units=test_units(tmp_path,data,inv,tree,cases,dict.fromkeys(cases,1),2)
    assert any(cases[0] in unit and cases[1] in unit for unit in case_units.values())
