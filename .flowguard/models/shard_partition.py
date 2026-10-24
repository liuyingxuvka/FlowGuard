"""Every collected node id is assigned once, within the requested shard bound.

The design allows any valid partition. Conformance inspects the real hash-based
partitioner's output; it does not duplicate that implementation.
"""
from collections import Counter
from dataclasses import dataclass

from flowguard.core import FunctionResult, Invariant
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
from flowguard.pytest_shards import partition_nodeids
from flowguard.workflow import Workflow

MODEL_ID = "shard_partition"
PARENT = "test-mesh"
IMPLEMENTED_BY = {"Partition": "flowguard/pytest_shards.py:partition_nodeids"}
NOT_MODELED = {
    "flowguard/pytest_shards_cli.py:main": (
        "CLI collection, subprocess lifetimes and JUnit aggregation are covered by native integration tests, "
        "including release orchestration; this model proves only the pure partition function."
    ),
}
TESTED_BY = {
    "every_id_exactly_once": [
        "tests/test_pytest_shards.py:test_partition_is_finite_disjoint_and_stable_when_unrelated_nodes_are_added",
    ],
    "bounded_shard_count": [
        "tests/test_pytest_shards.py:test_partition_is_finite_disjoint_and_stable_when_unrelated_nodes_are_added",
    ],
}


@dataclass(frozen=True)
class Request:
    nodeids: tuple[str, ...]
    shard_count: int


@dataclass(frozen=True)
class PartitionState:
    nodeids: tuple[str, ...] = ()
    shard_count: int = 1
    shards: tuple[tuple[str, ...], ...] = ()


CASES = (
    Request((), 4),
    Request(("tests/test_one.py::test_one",), 1),
    Request(("tests/test_one.py::test_one",), 8),
    Request(("tests/test_a.py::test_a", "tests/test_b.py::test_b", "tests/test_c.py::test_c"), 2),
    Request(("tests/test_unicode.py::test_界面", "tests/test_args.py::test_value[a]",
             "tests/test_args.py::test_value[b]"), 32),
)


def _each_once(state, trace):
    assigned = Counter(node for shard in state.shards for node in shard)
    return assigned == Counter(state.nodeids)


def _bounded(state, trace):
    return len(state.shards) <= state.shard_count


RULES = (
    Invariant("every_id_exactly_once", "every collected unique node id is assigned exactly once", _each_once),
    Invariant("bounded_shard_count", "the number of shards does not exceed the request", _bounded),
)


class Partition:
    """One permissible abstract allocation, plus genuine lost/duplicated-id faults."""
    name = "Partition"
    reads = ()
    writes = ("nodeids", "shard_count", "shards")

    def __init__(self, fault=""):
        self.fault = fault

    def apply(self, request, state):
        shards = (request.nodeids,) if request.nodeids else ()
        if request.nodeids and self.fault == "drop":
            shards = (request.nodeids[1:],)
        elif request.nodeids and self.fault == "duplicate":
            shards += ((request.nodeids[0],),) * request.shard_count
        observed = PartitionState(request.nodeids, request.shard_count, shards)
        return (FunctionResult(shards, observed, label="partitioned"),)


def _explorer(fault=""):
    return Explorer(Workflow((Partition(fault),)), initial_states=(PartitionState(),), external_inputs=CASES,
                    invariants=RULES, max_sequence_length=1, progress_steps=0)


def build_explorer():
    return _explorer()


def broken_variants():
    return {"drops_a_collected_id": _explorer("drop"), "duplicates_an_id_in_extra_shards": _explorer("duplicate")}


def conformance():
    facts = []
    for index, request in enumerate(CASES):
        shards = partition_nodeids(request.nodeids, request.shard_count)
        observed = PartitionState(request.nodeids, request.shard_count, shards)
        facts.append(Fact(f"case{index}:every_id_exactly_once", _each_once(observed, None), repr(shards)))
        facts.append(Fact(f"case{index}:bounded_shard_count", _bounded(observed, None), repr(shards)))
    return CodeFactsReport(tuple(facts))
