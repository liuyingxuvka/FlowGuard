"""Every collected node id is assigned once, within the requested shard bound.

The design allows any valid partition. Conformance inspects the real hash-based
partitioner's output; it does not duplicate that implementation.
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
PARENT = "test-mesh"
IMPLEMENTED_BY = {"Partition": "flowguard/pytest_shards.py:partition_nodeids"}
USES={'Units':'flowguard/map/testtree.py:test_units','Run':'flowguard/pytest_shards_cli.py:run'}
NOT_MODELED={'flowguard/pytest_shards_cli.py:main':'argument parsing only; run, which this model replays, does the work'}
TESTED_BY = {
 'shard_is_union_of_subtrees':['tests/test_pytest_shards.py:test_partition_is_exact_and_a_union_of_subtrees'],
 'unbound_tests_stay_in_their_component':['tests/test_pytest_shards.py:test_partition_is_exact_and_a_union_of_subtrees'],
 'hash_partition_without_usable_record':['tests/test_pytest_shard_runner.py:test_no_partial_or_corrupt_record_uses_the_hash_line'],
 'durations_recorded_after_a_completed_run':['tests/test_pytest_shard_runner.py:test_record_is_written_after_a_run_and_not_when_blocked'],
    "every_id_exactly_once": [
        "tests/test_pytest_shards.py:test_partition_is_exact_and_a_union_of_subtrees",
    ],
    "bounded_shard_count": [
        "tests/test_pytest_shards.py:test_partition_is_exact_and_a_union_of_subtrees",
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
    subtrees: bool = True
    placed: bool = True
    fallback: bool = True
    recorded: bool = True


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
    Invariant('hash_partition_without_usable_record','full duration records select subtree balancing; otherwise hash',lambda s,t:s.fallback),
    Invariant('durations_recorded_after_a_completed_run','completed runs record durations; blocked collection does not',lambda s,t:s.recorded),
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
        observed = PartitionState(request.nodeids, request.shard_count, shards, self.fault!='subtrees',self.fault!='placed',self.fault!='fallback',self.fault!='recorded')
        return (FunctionResult(shards, observed, label="partitioned"),)


def _explorer(fault=""):
    return Explorer(Workflow((Partition(fault),)), initial_states=(PartitionState(),), external_inputs=CASES,
                    invariants=RULES, max_sequence_length=1, progress_steps=0)


def build_explorer():
    return _explorer()


def broken_variants():
    return {"drops_a_collected_id": _explorer("drop"), "duplicates_an_id_in_extra_shards": _explorer("duplicate"), "splits_a_light_subtree":_explorer("subtrees"), "unbound_test_moved_to_another_component":_explorer("placed"), "hashes_despite_full_record":_explorer("fallback"), "records_blocked_run":_explorer("recorded")}


def conformance():
    facts = []
    for index, request in enumerate(CASES):
        shards = partition_nodeids(request.nodeids, request.shard_count)
        observed = PartitionState(request.nodeids, request.shard_count, shards)
        facts.append(Fact(f"case{index}:every_id_exactly_once", _each_once(observed, None), repr(shards)))
        facts.append(Fact(f"case{index}:bounded_shard_count", _bounded(observed, None), repr(shards)))
    from _testtree_fixture import fixture,runner_cases
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
    with TemporaryDirectory(prefix='fg-shard-run-') as directory:
        rows=runner_cases(Path(directory))
        facts.append(Fact('fallback',rows['first_code']==rows['second_code']==0 and rows['first'].get('balance')=='hash' and rows['second'].get('balance')=='seconds',repr(rows)))
        facts.append(Fact('recorded',rows['recorded'] and rows['preserved'] and rows['blocked'].get('status')=='blocked',repr(rows)))
    return CodeFactsReport(tuple(facts))
