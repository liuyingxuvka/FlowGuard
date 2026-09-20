from __future__ import annotations

import pytest

from flowguard.pytest_shards import (
    aggregate_pytest_projections,
    freeze_pytest_leaf_plan,
    observe_pytest_leaf_plan,
    nodeid_fingerprint,
    partition_nodeids,
    pytest_leaf_plan_current_pass,
    validate_pytest_leaf_plan,
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


def test_leaf_plan_deduplicates_exact_node_identity_but_keeps_runtime_variants():
    nodeid = "tests/test_contract.py::test_contract"
    base = {
        "interpreter": {"implementation": "CPython", "version": "3.12.10"},
        "environment": {"PYTEST_ADDOPTS": ""},
        "config": {"pytest_ini": "sha256:config"},
        "args_semantics": ["-q"],
        "input_identity": "sha256:source",
        "timeout_seconds": 30,
        "timeout_result": "process_exit",
        "plugins": ["pytest-9.0.3"],
        "instrumentation": {"trace": False},
        "report_path": "different-parent-output.json",
    }
    plan = freeze_pytest_leaf_plan(
        [
            {
                "owner_id": "owner:full",
                "obligation_ids": ["obligation:full", "obligation:shared"],
                "node_ids": [nodeid],
                "identity": base,
            },
            {
                "owner_id": "owner:packet",
                "obligation_ids": ["obligation:packet"],
                "node_ids": [nodeid],
                "identity": {**base, "output_path": "another-output.json"},
            },
            {
                "owner_id": "owner:traced",
                "obligation_ids": ["obligation:traced"],
                "node_ids": [nodeid],
                "identity": {**base, "instrumentation": {"trace": True}},
            },
        ],
        required_obligation_ids=(
            "obligation:full",
            "obligation:packet",
            "obligation:traced",
        ),
    )

    assert plan["leaf_count"] == 2
    assert plan["execution_count"] == 2
    assert plan["logical_assignment_count"] == 3
    assert plan["duplicate_assignment_count"] == 1
    assert validate_pytest_leaf_plan(plan)["ok"] is True
    assert {tuple(row["owner_ids"]) for row in plan["leaves"]} == {
        ("owner:full", "owner:packet"),
        ("owner:traced",),
    }

    observed = observe_pytest_leaf_plan(
        plan,
        [
            {
                "leaf_id": plan["leaves"][0]["leaf_id"],
                "status": "pass",
                "evidence_refs": ["leaf-evidence:one"],
            },
            {
                "leaf_id": plan["leaves"][1]["leaf_id"],
                "status": "pass",
                "evidence_refs": ["leaf-evidence:two"],
            },
        ],
    )
    assert pytest_leaf_plan_current_pass(observed) is True


def test_leaf_plan_rejects_not_run_fail_and_old_scope_as_parent_pass():
    plan = freeze_pytest_leaf_plan(
        [
            {
                "owner_id": "owner:full",
                "obligation_ids": ["obligation:full"],
                "node_ids": ["tests/test_a.py::test_a"],
                "identity": {"args_semantics": ["-q"], "timeout_seconds": 30},
            }
        ],
        required_obligation_ids=("obligation:full",),
    )
    for status, scope in (("not_run", "current"), ("fail", "current"), ("pass", "old")):
        observed = observe_pytest_leaf_plan(
            plan,
            [
                {
                    "leaf_id": plan["leaves"][0]["leaf_id"],
                    "status": status,
                    "scope": scope,
                    "evidence_refs": ["evidence"],
                }
            ],
        )
        assert pytest_leaf_plan_current_pass(observed) is False
