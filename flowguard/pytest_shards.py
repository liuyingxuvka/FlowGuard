"""Deterministic finite partitioning for FlowGuard's full pytest owner.

The full validation owner must know exactly which pytest node owns each
execution.  This module deliberately contains only pure inventory/partition
logic; process launching and JUnit interpretation stay with the native runner
and the parent validation composer respectively.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence


PARTITION_ALGORITHM = "sha256-nodeid-modulo-v1"


def normalize_nodeids(values: Sequence[Any]) -> tuple[str, ...]:
    """Return exact non-empty node ids and reject ambiguous inventories."""

    normalized = tuple(
        str(value).strip()
        for value in values
        if isinstance(value, str) and str(value).strip()
    )
    if len(normalized) != len(values):
        raise ValueError("node-id inventory contains a non-string or empty id")
    if len(set(normalized)) != len(normalized):
        raise ValueError("node-id inventory contains duplicate ids")
    return normalized


def nodeid_fingerprint(nodeids: Sequence[str]) -> str:
    """Fingerprint the ordered node-id manifest, not a display projection."""

    normalized = normalize_nodeids(tuple(nodeids))
    payload = json.dumps(
        list(normalized),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def partition_nodeids(
    nodeids: Sequence[str],
    shard_count: int,
) -> tuple[tuple[str, ...], ...]:
    """Assign every node to one stable, finite shard.

    Hash assignment keeps an unchanged node in the same shard when unrelated
    nodes are added.  The original collection order is retained inside each
    shard, so pytest's local ordering remains the native order.  Empty tail
    shards are omitted only when the inventory is smaller than the requested
    count; a non-empty full inventory therefore has at most the fixed bounded
    number of requested producers.
    """

    if not isinstance(shard_count, int) or isinstance(shard_count, bool):
        raise ValueError("shard_count must be an integer")
    if shard_count < 1 or shard_count > 32:
        raise ValueError("shard_count must be between 1 and 32")
    normalized = normalize_nodeids(tuple(nodeids))
    if not normalized:
        return ()
    buckets: list[list[str]] = [[] for _ in range(min(shard_count, len(normalized)))]
    for nodeid in normalized:
        digest = hashlib.sha256(nodeid.encode("utf-8")).digest()
        index = int.from_bytes(digest[:8], "big") % len(buckets)
        buckets[index].append(nodeid)
    return tuple(tuple(bucket) for bucket in buckets)


def validate_partition(
    nodeids: Sequence[str],
    shards: Sequence[Sequence[str]],
) -> dict[str, Any]:
    """Validate exact union/disjointness and return bounded audit facts."""

    expected = normalize_nodeids(tuple(nodeids))
    normalized_shards = tuple(normalize_nodeids(tuple(shard)) for shard in shards)
    expected_set = set(expected)
    seen: list[str] = []
    for shard in normalized_shards:
        seen.extend(shard)
    seen_set = set(seen)
    duplicates = sorted(
        nodeid for nodeid in seen_set if seen.count(nodeid) > 1
    )
    missing = sorted(expected_set - seen_set)
    unknown = sorted(seen_set - expected_set)
    return {
        "algorithm": PARTITION_ALGORITHM,
        "expected_count": len(expected),
        "shard_count": len(normalized_shards),
        "assigned_count": len(seen),
        "duplicates": duplicates,
        "missing": missing,
        "unknown": unknown,
        "disjoint": not duplicates,
        "exact_union": not duplicates and not missing and not unknown,
        "inventory_fingerprint": nodeid_fingerprint(expected),
    }


def aggregate_pytest_projections(
    projections: Sequence[Mapping[str, Any]],
    expected_nodeids: Sequence[str],
) -> dict[str, Any]:
    """Aggregate native shard projections after exact identity validation."""

    expected = normalize_nodeids(tuple(expected_nodeids))
    expected_set = set(expected)
    observed: list[str] = []
    counters = {
        "selected": 0,
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "xfailed": 0,
        "xpassed": 0,
    }
    skip_details: list[dict[str, Any]] = []
    optional_metadata_unverified = False
    for projection in projections:
        raw_ids = projection.get("node_ids", ())
        if not isinstance(raw_ids, Sequence) or isinstance(raw_ids, (str, bytes)):
            raise ValueError("pytest shard projection has no node-id sequence")
        nodeids = normalize_nodeids(tuple(raw_ids))
        observed.extend(nodeids)
        for field in counters:
            value = projection.get(field, 0)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"pytest shard projection has invalid {field}")
            counters[field] += value
        details = projection.get("skip_details", ())
        if isinstance(details, Sequence) and not isinstance(details, (str, bytes)):
            for item in details:
                if isinstance(item, Mapping):
                    skip_details.append(dict(item))
        optional_metadata_unverified = optional_metadata_unverified or bool(
            projection.get("optional_metadata_unverified", False)
        )
    if len(observed) != len(set(observed)):
        raise ValueError("pytest shard projections overlap on a node id")
    observed_set = set(observed)
    if observed_set != expected_set:
        raise ValueError(
            "pytest shard projections do not form the exact collected inventory"
        )
    if counters["selected"] != len(observed):
        raise ValueError("pytest shard selected count disagrees with node ids")
    return {
        "schema_version": "flowguard.pytest_execution.v2",
        **counters,
        "skip_details": skip_details,
        "node_ids": list(expected),
        "optional_metadata_unverified": optional_metadata_unverified,
        "inventory_fingerprint": nodeid_fingerprint(expected),
    }


__all__ = [
    "PARTITION_ALGORITHM",
    "aggregate_pytest_projections",
    "nodeid_fingerprint",
    "normalize_nodeids",
    "partition_nodeids",
    "validate_partition",
]
