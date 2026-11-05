"""Native pytest partitioning retains real directory and parameter-case boundaries."""
from flowguard.map.testtree import test_units as units_for
from flowguard.pytest_shards import partition_nodeids, validate_partition


def test_directory_subtrees_partition_without_a_model_registry():
    nodes = ("tests/core/test_a.py::test_a", "tests/core/test_b.py::test_b",
             "tests/ui/test_ui.py::test_ui", "tests/ui/test_ui.py::test_other")
    weights = dict.fromkeys(nodes, 1)
    units = units_for(nodes, weights, 2)
    assert units == {"tests/core": nodes[:2], "tests/ui": nodes[2:]}
    shards = partition_nodeids(nodes, 2, units=units, weights=weights)
    assert validate_partition(nodes, shards)["exact_union"]
    assert all(any(set(unit) <= set(shard) for shard in shards) for unit in units.values())


def test_heavy_files_split_by_function_while_parameter_cases_stay_together():
    nodes = ("tests/test_big.py::TestBig::test_a[one]", "tests/test_big.py::TestBig::test_a[two]",
             "tests/test_big.py::TestBig::test_b", "tests/test_small.py::test_c")
    weights = dict.fromkeys(nodes, 1)
    units = units_for(nodes, weights, 3)
    assert any(nodes[0] in unit and nodes[1] in unit for unit in units.values())
    assert any("test_b" in label for label in units)
    shards = partition_nodeids(nodes, 3, units=units, weights=weights)
    assert validate_partition(nodes, shards)["exact_union"]
