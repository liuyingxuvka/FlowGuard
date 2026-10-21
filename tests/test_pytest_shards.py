from __future__ import annotations

import pytest

from flowguard.pytest_shards import (
    aggregate_pytest_projections,
    nodeid_fingerprint,
    partition_nodeids,
    validate_partition,
)


def test_partition_is_finite_disjoint_and_stable_when_unrelated_nodes_are_added():
    nodeids = tuple(f"tests/test_{index}.py::test_case" for index in range(40))
    first = partition_nodeids(nodeids, 4)
    second = partition_nodeids(nodeids, 4)
    expanded = partition_nodeids(nodeids + ("tests/test_new.py::test_new",), 4)

    assert first == second
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
