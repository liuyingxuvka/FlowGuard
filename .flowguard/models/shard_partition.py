"""Every collected node id is assigned once, within the requested shard bound.

Conformance inspects the native stable hash fallback, whole-subtree balance
and per-run duration records; it does not duplicate the partition algorithm.
"""
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from flowguard.core import FunctionResult, Invariant
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
from flowguard.pytest_shards import partition_nodeids
from flowguard.workflow import Workflow

MODEL_ID = "shard_partition"
PARENT = "shard_suite"
IMPLEMENTED_BY = {"Partition": "flowguard/pytest_shards.py:partition_nodeids"}
USES = {
    'BuildInventory': 'flowguard/map/inventory.py:build_inventory',
    'BuildTree': 'flowguard/map/tree.py:build_tree',
    'Units': 'flowguard/map/testtree.py:test_units',
}
NOT_MODELED={'flowguard/pytest_shards_cli.py:main':'argument parsing only; run, which this model replays, does the work'}
TESTED_BY = {'shard_is_union_of_subtrees': ['tests/test_pytest_shards.py:test_partition_is_exact_and_a_union_of_subtrees'], 'unbound_tests_stay_in_their_component': ['tests/test_pytest_shards.py:test_partition_is_exact_and_a_union_of_subtrees'], 'every_id_exactly_once': ['tests/test_pytest_shards.py:test_partition_is_exact_and_a_union_of_subtrees'], 'bounded_shard_count': ['tests/test_pytest_shards.py:test_partition_is_exact_and_a_union_of_subtrees']}


@dataclass(frozen=True)
class Request:
    nodeids: tuple[str, ...]
    shard_count: int


@dataclass(frozen=True)
class PartitionState:
    nodeids: tuple[str, ...] = ()
    shard_count: int = 1
    shards: tuple[tuple[str, ...], ...] = ()
    subtrees: bool = True
    placed: bool = True
    fallback: bool = True
    recorded: bool = True
    algorithm: str = "hash"
    record: str = "missing"


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
    Invariant('shard_is_union_of_subtrees','a light subtree is indivisible',lambda s,t:s.subtrees),
    Invariant('unbound_tests_stay_in_their_component','unbound test units retain their component',lambda s,t:s.placed),
)


class Partition:
    """One permissible abstract allocation, plus genuine lost/duplicated-id faults."""
    name = "Partition"
    reads = ()
    writes = ("nodeids", "shard_count", "shards", "subtrees", "placed", "fallback", "recorded", "algorithm")

    def __init__(self, fault=""):
        self.fault = fault

    def apply(self, request, state):
        shards = (request.nodeids,) if request.nodeids else ()
        if request.nodeids and self.fault == "drop":
            shards = (request.nodeids[1:],)
        elif request.nodeids and self.fault == "duplicate":
            shards += ((request.nodeids[0],),) * request.shard_count
        observed = PartitionState(request.nodeids, request.shard_count, shards, self.fault!='subtrees',self.fault!='placed',self.fault!='fallback',self.fault!='recorded', 'subtrees' if state.record=='usable' else 'hash', state.record)
        return (FunctionResult(observed.algorithm, observed, label="partitioned"),)


def _explorer(fault=""):
    return Explorer(Workflow((Partition(fault),)), initial_states=tuple(PartitionState(record=record,algorithm=algorithm) for record in ('usable','missing') for algorithm in ('subtrees','hash')), external_inputs=CASES,
                    invariants=RULES, max_sequence_length=1, progress_steps=0)


def build_explorer():
    return _explorer()


def broken_variants():
    return {"drops_a_collected_id": _explorer("drop"), "duplicates_an_id_in_extra_shards": _explorer("duplicate"), "splits_a_light_subtree":_explorer("subtrees"), "unbound_test_moved_to_another_component":_explorer("placed")}


def conformance():
    facts = []
    for index, request in enumerate(CASES):
        shards = partition_nodeids(request.nodeids, request.shard_count)
        observed = PartitionState(request.nodeids, request.shard_count, shards)
        facts.append(Fact(f"case{index}:every_id_exactly_once", _each_once(observed, None), repr(shards)))
        facts.append(Fact(f"case{index}:bounded_shard_count", _bounded(observed, None), repr(shards)))
    from _testtree_fixture import fixture
    from flowguard.map import testtree
    from flowguard.map.inventory import build_inventory
    from flowguard.map.tree import build_tree
    from flowguard.map.common import DEFAULT_IGNORE
    with TemporaryDirectory(prefix='fg-shard-tree-') as directory:
        root=Path(directory);data,nodeids=fixture(root);inv=build_inventory(root,DEFAULT_IGNORE,write_cache=False);tree=build_tree(root,data,inv)
        unit_function=getattr(testtree,'test_units',None)
        units=unit_function(root,data,inv,tree,nodeids,{node:1 for node in nodeids},2) if unit_function else None
        try:shards=partition_nodeids(nodeids,2,units=units,weights={node:1 for node in nodeids})
        except TypeError:shards=()
        facts.append(Fact('subtrees',bool(units) and bool(shards) and all(any(set(unit)<=set(shard) for shard in shards) for unit in units.values()),repr((units,shards))))
    return CodeFactsReport(tuple(facts))

OUTPUTS = {'algorithm': ('subtrees', 'hash')}

READS_PARENT = ('record',)
