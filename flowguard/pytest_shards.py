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
PYTEST_LEAF_PLAN_SCHEMA = "flowguard.pytest_leaf_plan.v1"
PYTEST_LEAF_PLAN_VERSION = 1


_NON_SEMANTIC_IDENTITY_FIELDS = frozenset(
    {
        "checked_at",
        "finished_at",
        "head",
        "installation_head",
        "log_path",
        "output_path",
        "receipt_hash",
        "receipt_id",
        "report_path",
        "run_id",
        "started_at",
        "stderr_path",
        "stdout_path",
    }
)


def _strip_non_semantic_identity_fields(value: Any) -> Any:
    """Remove evidence-location and observation-time fields from an identity.

    A leaf's source/runtime identity must not change merely because a parent
    stores its report in another directory or observes it at another time.
    This is deliberately a small, structural filter; callers still have to
    provide the interpreter, environment, config, arguments, inputs,
    timeout, plugins, and instrumentation that affect execution.
    """

    if isinstance(value, Mapping):
        return {
            str(key): _strip_non_semantic_identity_fields(item)
            for key, item in value.items()
            if str(key) not in _NON_SEMANTIC_IDENTITY_FIELDS
        }
    if isinstance(value, (list, tuple)):
        return [_strip_non_semantic_identity_fields(item) for item in value]
    return value


def pytest_leaf_identity(identity: Mapping[str, Any] | str) -> dict[str, Any]:
    """Return one bounded, source-semantic pytest execution identity.

    The identity intentionally keeps timeout *result* separate from the
    declared timeout.  A timeout, cancellation, failed execution, or old
    scope can therefore never be mistaken for a current passing leaf merely
    because its node id is the same.
    """

    if isinstance(identity, str):
        value: Any = {"identity_fingerprint": identity}
    elif isinstance(identity, Mapping):
        value = dict(identity)
    else:
        raise ValueError("pytest leaf identity must be an object or fingerprint")
    value = _strip_non_semantic_identity_fields(value)
    if not value:
        raise ValueError("pytest leaf identity is empty")
    return dict(value)


def pytest_leaf_identity_fingerprint(identity: Mapping[str, Any] | str) -> str:
    """Fingerprint only execution-semantic identity fields."""

    return "sha256:" + hashlib.sha256(
        json.dumps(
            pytest_leaf_identity(identity),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def pytest_leaf_key(
    nodeid: str,
    identity: Mapping[str, Any] | str,
) -> str:
    """Return the exact deduplication key for one pytest execution leaf."""

    normalized_nodeid = str(nodeid).strip()
    if not normalized_nodeid:
        raise ValueError("pytest leaf node id is empty")
    payload = {
        "schema_version": PYTEST_LEAF_PLAN_SCHEMA,
        "nodeid": normalized_nodeid,
        "identity": pytest_leaf_identity(identity),
    }
    return "sha256:" + hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _declaration_nodeids(declaration: Mapping[str, Any]) -> tuple[str, ...]:
    raw = declaration.get("node_ids", declaration.get("nodeids", ()))
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        raise ValueError("pytest leaf declaration node ids must be a sequence")
    return normalize_nodeids(tuple(raw))


def _declaration_identity(declaration: Mapping[str, Any]) -> dict[str, Any]:
    raw = declaration.get("identity", declaration.get("execution_identity"))
    if raw is None:
        # Keep the public helper useful for declarations that spell the
        # fields directly, while still refusing an accidentally empty key.
        raw = {
            key: value
            for key, value in declaration.items()
            if key
            not in {
                "owner_id",
                "obligation_ids",
                "node_ids",
                "nodeids",
                "identity",
                "execution_identity",
            }
        }
    return pytest_leaf_identity(raw)


def freeze_pytest_leaf_plan(
    declarations: Sequence[Mapping[str, Any]],
    *,
    required_obligation_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Freeze one exact leaf table and map every logical obligation to it.

    Declarations are owner-level projections.  Repeated declarations do not
    create another producer: they append an obligation/owner assignment to
    the already existing leaf row.  Different runtime identity fields remain
    different leaves even when the node id is identical.
    """

    if not isinstance(declarations, Sequence) or isinstance(
        declarations, (str, bytes, bytearray)
    ):
        raise ValueError("pytest leaf declarations must be a sequence")
    leaves_by_key: dict[str, dict[str, Any]] = {}
    assignments: list[dict[str, Any]] = []
    covered: set[str] = set()
    owner_ids: set[str] = set()
    for declaration in declarations:
        if not isinstance(declaration, Mapping):
            raise ValueError("pytest leaf declaration must be an object")
        owner_id = str(declaration.get("owner_id", "")).strip()
        if not owner_id:
            raise ValueError("pytest leaf declaration owner id is empty")
        raw_obligations = declaration.get("obligation_ids", ())
        if isinstance(raw_obligations, (str, bytes, bytearray)) or not isinstance(
            raw_obligations, Sequence
        ):
            raise ValueError("pytest leaf declaration obligations must be a sequence")
        obligation_ids = tuple(
            dict.fromkeys(
                str(value).strip()
                for value in raw_obligations
                if str(value).strip()
            )
        )
        if not obligation_ids:
            raise ValueError(f"pytest leaf declaration has no obligations: {owner_id}")
        identity = _declaration_identity(declaration)
        identity_fingerprint = pytest_leaf_identity_fingerprint(identity)
        nodeids = _declaration_nodeids(declaration)
        owner_ids.add(owner_id)
        covered.update(obligation_ids)
        for nodeid in nodeids:
            key = pytest_leaf_key(nodeid, identity)
            leaf = leaves_by_key.get(key)
            if leaf is None:
                leaf = {
                    "leaf_id": "leaf:" + key.split(":", 1)[1][:32],
                    "leaf_key": key,
                    "nodeid": nodeid,
                    "identity_fingerprint": identity_fingerprint,
                    "identity": identity,
                    "owner_ids": [],
                    "obligation_ids": [],
                    "assignments": [],
                    "status": "not_run",
                    "scope": "current",
                    "evidence_refs": [],
                }
                leaves_by_key[key] = leaf
            if owner_id not in leaf["owner_ids"]:
                leaf["owner_ids"].append(owner_id)
            for obligation_id in obligation_ids:
                if obligation_id not in leaf["obligation_ids"]:
                    leaf["obligation_ids"].append(obligation_id)
            assignment = {
                "owner_id": owner_id,
                "obligation_ids": list(obligation_ids),
                "nodeid": nodeid,
                "leaf_id": leaf["leaf_id"],
                "leaf_key": key,
            }
            leaf["assignments"].append(assignment)
            assignments.append(assignment)

    required = tuple(
        dict.fromkeys(str(value).strip() for value in required_obligation_ids if str(value).strip())
    )
    missing_required = sorted(set(required) - covered)
    leaves = [leaves_by_key[key] for key in sorted(leaves_by_key)]
    plan = {
        "schema_version": PYTEST_LEAF_PLAN_SCHEMA,
        "plan_version": PYTEST_LEAF_PLAN_VERSION,
        "status": "passed" if not missing_required else "blocked",
        "owner_ids": sorted(owner_ids),
        "required_obligation_ids": list(required),
        "covered_obligation_ids": sorted(covered),
        "missing_obligation_ids": missing_required,
        "leaf_count": len(leaves),
        "execution_count": len(leaves),
        "logical_assignment_count": len(assignments),
        "duplicate_assignment_count": max(0, len(assignments) - len(leaves)),
        "leaves": leaves,
        "assignments": assignments,
        "claim_boundary": (
            "The table deduplicates only exact node-id/runtime identities. "
            "It does not turn missing, failed, timed-out, or old-scope leaves into pass evidence."
        ),
    }
    plan["plan_hash"] = pytest_leaf_plan_fingerprint(plan)
    return plan


def pytest_leaf_plan_fingerprint(plan: Mapping[str, Any]) -> str:
    """Hash a plan without its derived hash field."""

    payload = {
        str(key): value
        for key, value in plan.items()
        if str(key) not in {"plan_hash", "observation_hash", "observed_leaf_count"}
    }
    raw_leaves = payload.get("leaves")
    if isinstance(raw_leaves, list):
        payload["leaves"] = [
            {
                str(key): value
                for key, value in row.items()
                if str(key) not in {"status", "scope", "evidence_refs"}
            }
            if isinstance(row, Mapping)
            else row
            for row in raw_leaves
        ]
    return "sha256:" + hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def observe_pytest_leaf_plan(
    plan: Mapping[str, Any],
    observations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Attach terminal leaf observations without changing plan identity."""

    if plan.get("schema_version") != PYTEST_LEAF_PLAN_SCHEMA:
        raise ValueError("pytest leaf plan schema invalid")
    observed = json.loads(json.dumps(dict(plan), ensure_ascii=False))
    leaves = observed.get("leaves")
    if not isinstance(leaves, list):
        raise ValueError("pytest leaf plan leaves invalid")
    by_id = {
        str(row.get("leaf_id", "")): row
        for row in leaves
        if isinstance(row, Mapping) and str(row.get("leaf_id", ""))
    }
    seen: set[str] = set()
    allowed_statuses = {"pass", "fail", "blocked", "not_run", "old_scope"}
    for raw in observations:
        if not isinstance(raw, Mapping):
            raise ValueError("pytest leaf observation must be an object")
        leaf_id = str(raw.get("leaf_id", "")).strip()
        if leaf_id not in by_id:
            raise ValueError(f"pytest leaf observation is not in frozen plan: {leaf_id}")
        if leaf_id in seen:
            raise ValueError(f"pytest leaf observation duplicated: {leaf_id}")
        status = str(raw.get("status", "")).strip()
        if status not in allowed_statuses:
            raise ValueError(f"pytest leaf observation status invalid: {status}")
        row = by_id[leaf_id]
        row["status"] = status
        row["scope"] = str(raw.get("scope", "current"))
        refs = raw.get("evidence_refs", raw.get("evidence_ref", ()))
        if isinstance(refs, str):
            refs = [refs] if refs else []
        if not isinstance(refs, Sequence) or isinstance(refs, (bytes, bytearray)):
            raise ValueError(f"pytest leaf evidence refs invalid: {leaf_id}")
        row["evidence_refs"] = [str(value) for value in refs if str(value)]
        seen.add(leaf_id)
    observed["observed_leaf_count"] = len(seen)
    observed["observation_hash"] = pytest_leaf_plan_fingerprint(
        {"plan_hash": observed.get("plan_hash", ""), "leaves": observed["leaves"]}
    )
    return observed


def validate_pytest_leaf_plan(
    plan: Mapping[str, Any],
    *,
    required_obligation_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Validate unique keys, complete assignments, and obligation coverage."""

    findings: list[str] = []
    if plan.get("schema_version") != PYTEST_LEAF_PLAN_SCHEMA:
        findings.append("schema_invalid")
    leaves = plan.get("leaves", ())
    assignments = plan.get("assignments", ())
    if not isinstance(leaves, list) or not isinstance(assignments, list):
        findings.append("shape_invalid")
        leaves = []
        assignments = []
    leaf_ids = [str(row.get("leaf_id", "")) for row in leaves if isinstance(row, Mapping)]
    leaf_keys = [str(row.get("leaf_key", "")) for row in leaves if isinstance(row, Mapping)]
    if len(leaf_ids) != len(set(leaf_ids)) or len(leaf_keys) != len(set(leaf_keys)):
        findings.append("duplicate_leaf_identity")
    leaf_by_id = {
        str(row.get("leaf_id", "")): row
        for row in leaves
        if isinstance(row, Mapping)
    }
    assignment_keys: set[tuple[str, str, str]] = set()
    covered: set[str] = set()
    for assignment in assignments:
        if not isinstance(assignment, Mapping):
            findings.append("assignment_invalid")
            continue
        key = (
            str(assignment.get("owner_id", "")),
            str(assignment.get("nodeid", "")),
            str(assignment.get("leaf_id", "")),
        )
        if key in assignment_keys:
            findings.append("duplicate_assignment")
        assignment_keys.add(key)
        leaf = leaf_by_id.get(key[2])
        if leaf is None or leaf.get("nodeid") != key[1]:
            findings.append("assignment_leaf_mismatch")
        covered.update(
            str(value)
            for value in assignment.get("obligation_ids", ())
            if str(value)
        )
    required = tuple(
        str(value)
        for value in (
            required_obligation_ids
            if required_obligation_ids is not None
            else plan.get("required_obligation_ids", ())
        )
        if str(value)
    )
    missing = sorted(set(required) - covered)
    if missing:
        findings.append("required_obligation_coverage_missing")
    expected_count = len(leaf_ids)
    if plan.get("execution_count") != expected_count:
        findings.append("execution_count_mismatch")
    return {
        "schema_version": PYTEST_LEAF_PLAN_SCHEMA,
        "ok": not findings,
        "findings": findings,
        "leaf_count": expected_count,
        "assignment_count": len(assignments),
        "execution_count": expected_count,
        "duplicate_assignment_count": max(0, len(assignments) - expected_count),
        "covered_obligation_ids": sorted(covered),
        "missing_obligation_ids": missing,
    }


def pytest_leaf_plan_current_pass(
    plan: Mapping[str, Any],
    *,
    required_obligation_ids: Sequence[str] | None = None,
) -> bool:
    """Return true only when every required logical leaf is current and passing."""

    if validate_pytest_leaf_plan(
        plan, required_obligation_ids=required_obligation_ids
    )["ok"] is not True:
        return False
    required = set(
        str(value)
        for value in (
            required_obligation_ids
            if required_obligation_ids is not None
            else plan.get("required_obligation_ids", ())
        )
        if str(value)
    )
    leaves = [row for row in plan.get("leaves", ()) if isinstance(row, Mapping)]
    for leaf in leaves:
        obligations = {
            str(value) for value in leaf.get("obligation_ids", ()) if str(value)
        }
        if not obligations & required:
            continue
        if (
            leaf.get("status") != "pass"
            or leaf.get("scope", "current") != "current"
            or not leaf.get("evidence_refs")
        ):
            return False
    return bool(required) and all(
        any(
            isinstance(leaf, Mapping)
            and obligation in {
                str(value) for value in leaf.get("obligation_ids", ())
            }
            and leaf.get("status") == "pass"
            and leaf.get("scope", "current") == "current"
            and bool(leaf.get("evidence_refs"))
            for leaf in leaves
        )
        for obligation in required
    )


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
    node_statuses: dict[str, str] = {}
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
        raw_statuses = projection.get("node_statuses", {})
        if isinstance(raw_statuses, Mapping):
            for raw_nodeid, raw_status in raw_statuses.items():
                nodeid = str(raw_nodeid).strip()
                status = str(raw_status).strip()
                if nodeid and status:
                    if nodeid in node_statuses:
                        raise ValueError("pytest shard projections overlap on a node status")
                    node_statuses[nodeid] = status
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
        "node_statuses": node_statuses,
        "optional_metadata_unverified": optional_metadata_unverified,
        "inventory_fingerprint": nodeid_fingerprint(expected),
    }


__all__ = [
    "PARTITION_ALGORITHM",
    "PYTEST_LEAF_PLAN_SCHEMA",
    "PYTEST_LEAF_PLAN_VERSION",
    "aggregate_pytest_projections",
    "nodeid_fingerprint",
    "normalize_nodeids",
    "partition_nodeids",
    "freeze_pytest_leaf_plan",
    "observe_pytest_leaf_plan",
    "pytest_leaf_identity",
    "pytest_leaf_identity_fingerprint",
    "pytest_leaf_key",
    "pytest_leaf_plan_current_pass",
    "pytest_leaf_plan_fingerprint",
    "validate_pytest_leaf_plan",
    "validate_partition",
]
