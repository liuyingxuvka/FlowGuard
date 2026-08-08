"""Selective, fingerprint-checked reads over a normalized blueprint index."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import cached_property
from typing import Any

from .blueprint_topology import TOPOLOGY_RELATION_KINDS
from .evidence_receipts import fingerprint_value
from .software_blueprint_readiness import (
    BEHAVIOR_COVERAGE_REFERENCE_SHARD_KIND,
    BEHAVIOR_COVERAGE_REFERENCE_SHARD_SCHEMA,
)
from .target_system_blueprint import (
    BlueprintGapRef,
    BlueprintLayerResult,
    ModelPathQualityBlueprintBinding,
    BlueprintNativeReportRef,
    BlueprintReadinessLedger,
)


AFFECTED_BLUEPRINT_READER_SCHEMA = "flowguard.affected_blueprint_reader.v3"
AFFECTED_BLUEPRINT_INDEX_SCHEMA = "flowguard.affected_blueprint_index.v3"
AFFECTED_BLUEPRINT_UNDERSTANDING_SCHEMA = (
    "flowguard.affected_blueprint_understanding.v3"
)
AFFECTED_TOPOLOGY_INVALIDATION_EDGE_SCHEMA = (
    "flowguard.affected_topology_invalidation_edge.v1"
)
AFFECTED_TOPOLOGY_INVALIDATION_KINDS = frozenset(
    {
        "ancestor",
        "affected_sibling",
        "child",
        "cross_boundary_support",
        "delegates_to",
        "feedback",
        "produces_for",
        "repair",
        "relation_consumer",
        "relation_producer",
        "realization_member",
        "realization_owner",
        "retry",
        "shared_resource",
        "sibling",
        "supports",
    }
)
_TOPOLOGY_RELATION_INVALIDATION_DIRECTIONS = {
    "produces_for": "producer_to_consumer",
    "delegates_to": "consumer_to_producer",
    "supports": "producer_to_consumer",
    "cross_boundary_support": "producer_to_consumer",
    "feedback": "producer_to_consumer",
    "retry": "producer_to_consumer",
    "repair": "producer_to_consumer",
    "shared_resource": "producer_to_consumer",
    "affected_sibling": "producer_to_consumer",
}


class AffectedBlueprintReadError(ValueError):
    """Raised when an affected read cannot preserve normalized authority."""


ShardLoader = Callable[[str], Any]
ObjectLoader = Callable[[str], Any]


_MISSING = object()


def _field(value: Any, name: str, default: Any = _MISSING) -> Any:
    if isinstance(value, Mapping):
        if name in value:
            return value[name]
    else:
        namespace = getattr(value, "__dict__", None)
        if isinstance(namespace, dict) and name in namespace:
            return namespace[name]
        try:
            return object.__getattribute__(value, name)
        except AttributeError:
            pass
    if default is _MISSING:
        raise AffectedBlueprintReadError(f"normalized index omits {name}")
    return default


def _strict_object(
    value: Any,
    *,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
    context: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AffectedBlueprintReadError(f"{context} must be an object")
    payload = {str(key): item for key, item in value.items()}
    actual = set(payload)
    missing = sorted(required - actual)
    unknown = sorted(actual - required - optional)
    if missing or unknown:
        raise AffectedBlueprintReadError(
            f"{context} fields are not current: missing={missing}, unknown={unknown}"
        )
    return payload


def _string(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise AffectedBlueprintReadError(f"{context} must be a non-empty string")
    return value


def _string_array(value: Any, *, context: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        raise AffectedBlueprintReadError(f"{context} must be a JSON array")
    rows = tuple(
        _string(item, context=f"{context} member") for item in value
    )
    if len(rows) != len(set(rows)):
        raise AffectedBlueprintReadError(f"{context} contains duplicate ids")
    return rows


def _array_like(value: Any, *, context: str) -> tuple[Any, ...]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        raise AffectedBlueprintReadError(f"{context} must be a JSON array")
    return tuple(value)


def _string_map(value: Any, *, context: str) -> dict[str, str]:
    rows = _index_pairs(value, context=context)
    return {
        _string(key, context=f"{context} key"): _string(
            item, context=f"{context} value"
        )
        for key, item in rows.items()
    }


def _reference_shard(value: Any, *, shard_id: str) -> dict[str, Any]:
    """Require the one direct-current reference-only shard shape."""

    payload = _strict_object(
        value,
        required=frozenset(
            {
                "schema_version",
                "kind",
                "shard_id",
                "coverage_ids",
                "referenced_object_ids",
            }
        ),
        context=f"affected shard {shard_id}",
    )
    if (
        payload["schema_version"]
        != BEHAVIOR_COVERAGE_REFERENCE_SHARD_SCHEMA
        or payload["kind"] != BEHAVIOR_COVERAGE_REFERENCE_SHARD_KIND
    ):
        raise AffectedBlueprintReadError(
            f"affected shard schema is not current: {shard_id}"
        )
    if _string(payload["shard_id"], context="affected shard id") != shard_id:
        raise AffectedBlueprintReadError(
            f"affected shard identity mismatch: {shard_id}"
        )
    coverage_ids = _string_array(
        payload["coverage_ids"],
        context=f"affected shard coverage ids {shard_id}",
    )
    referenced_object_ids = _string_array(
        payload["referenced_object_ids"],
        context=f"affected shard referenced object ids {shard_id}",
    )
    if not coverage_ids or coverage_ids != tuple(sorted(coverage_ids)):
        raise AffectedBlueprintReadError(
            f"affected shard coverage ids are not sorted and non-empty: {shard_id}"
        )
    if referenced_object_ids != coverage_ids:
        raise AffectedBlueprintReadError(
            f"affected shard reference ids differ from coverage ids: {shard_id}"
        )
    return dict(payload)


_EXPLICIT_REFERENCE_KEYS = frozenset(
    {
        "referenced_object_ids",
        "object_ids",
        "shared_object_ids",
    }
)
_EXPLICIT_ANCESTOR_KEYS = frozenset(
    {
        "ancestor_ids",
        "ancestor_object_ids",
        "parent_object_ids",
        "required_ancestor_ids",
    }
)
_INFERRED_REFERENCE_KEYS = frozenset(
    {
        "behavior_block_id",
        "case_id",
        "implementation_surface_id",
        "intent_id",
        "model_element_id",
        "model_obligation_id",
        "node_object_id",
        "oracle_id",
        "oracle_member_id",
        "owner_contract_id",
        "owner_id",
        "parent_object_id",
        "portable_binding_id",
        "receipt_id",
        "resource_id",
        "semantic_spec_id",
        "supporting_surface_id",
        "test_node_id",
        "topology_node_id",
    }
)
_INFERRED_REFERENCE_COLLECTION_KEYS = frozenset(
    {
        "intent_ids",
        "oracle_ids",
        "portable_binding_ids",
        "relation_object_ids",
        "resource_ids",
        "semantic_spec_ids",
        "test_node_ids",
    }
)
_INFERRED_ANCESTOR_KEYS = frozenset(
    {
        "behavior_block_id",
        "model_element_id",
        "owner_contract_id",
        "owner_id",
        "parent_object_id",
        "topology_node_id",
    }
)


def _ids(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return tuple(str(item) for item in value if str(item))
    return ()


def _index_pairs(value: Any, *, context: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        rows = tuple(value.items())
    else:
        try:
            rows = tuple(value)
        except TypeError as exc:
            raise AffectedBlueprintReadError(f"{context} must be an iterable") from exc
    result: dict[str, Any] = {}
    for row in rows:
        if not isinstance(row, Sequence) or isinstance(
            row, (str, bytes, bytearray)
        ) or len(row) != 2:
            raise AffectedBlueprintReadError(
                f"{context} entries must be exact id/value pairs"
            )
        row_id = str(row[0])
        if not row_id:
            raise AffectedBlueprintReadError(f"{context} contains an empty id")
        if row_id in result:
            raise AffectedBlueprintReadError(
                f"{context} contains duplicate id: {row_id}"
            )
        result[row_id] = row[1]
    return result


def _discover_links(
    value: Any,
) -> tuple[set[str], set[str], set[str]]:
    """Return explicit refs, inferred refs, and ancestor refs.

    Explicit reference declarations are authoritative and must resolve. Inferred
    identifiers are only followed when the normalized object index knows them.
    """

    explicit: set[str] = set()
    inferred: set[str] = set()
    ancestors: set[str] = set()

    def visit(node: Any) -> None:
        if isinstance(node, Mapping):
            for raw_key, child in node.items():
                key = str(raw_key)
                if key in _EXPLICIT_REFERENCE_KEYS:
                    explicit.update(_ids(child))
                elif key in _EXPLICIT_ANCESTOR_KEYS:
                    found = set(_ids(child))
                    explicit.update(found)
                    ancestors.update(found)
                elif key in _INFERRED_REFERENCE_KEYS:
                    found = set(_ids(child))
                    inferred.update(found)
                    if key in _INFERRED_ANCESTOR_KEYS:
                        ancestors.update(found)
                elif key in _INFERRED_REFERENCE_COLLECTION_KEYS:
                    inferred.update(_ids(child))
                visit(child)
        elif isinstance(node, Sequence) and not isinstance(
            node, (str, bytes, bytearray)
        ):
            for child in node:
                visit(child)

    visit(value)
    return explicit, inferred, ancestors


@dataclass(frozen=True)
class AffectedTopologyInvalidationEdge:
    """One exact directed reason that expands an affected topology seed."""

    source_id: str
    target_id: str
    edge_kind: str
    evidence_object_ids: tuple[str, ...]
    via_node_id: str = ""

    def __post_init__(self) -> None:
        for name in ("source_id", "target_id"):
            object.__setattr__(
                self,
                name,
                _string(getattr(self, name), context=f"topology edge {name}"),
            )
        if self.source_id == self.target_id:
            raise AffectedBlueprintReadError(
                "topology invalidation edge cannot target its own source"
            )
        if self.edge_kind not in AFFECTED_TOPOLOGY_INVALIDATION_KINDS:
            raise AffectedBlueprintReadError(
                f"unknown topology invalidation edge kind: {self.edge_kind}"
            )
        evidence = tuple(
            sorted(
                _string_array(
                    self.evidence_object_ids,
                    context="topology invalidation evidence objects",
                )
            )
        )
        if not evidence:
            raise AffectedBlueprintReadError(
                "topology invalidation edge requires content-addressed evidence"
            )
        object.__setattr__(self, "evidence_object_ids", evidence)
        if self.via_node_id:
            object.__setattr__(
                self,
                "via_node_id",
                _string(
                    self.via_node_id,
                    context="topology invalidation via node",
                ),
            )
        if self.edge_kind == "sibling" and not self.via_node_id:
            raise AffectedBlueprintReadError(
                "sibling invalidation requires its exact common parent"
            )

    @property
    def schema_version(self) -> str:
        return AFFECTED_TOPOLOGY_INVALIDATION_EDGE_SCHEMA

    @property
    def identity(self) -> tuple[str, str, str, str]:
        return (
            self.source_id,
            self.target_id,
            self.edge_kind,
            self.via_node_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_kind": self.edge_kind,
            "evidence_object_ids": list(self.evidence_object_ids),
            "via_node_id": self.via_node_id,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "AffectedTopologyInvalidationEdge":
        payload = _strict_object(
            value,
            required=frozenset(
                {
                    "schema_version",
                    "source_id",
                    "target_id",
                    "edge_kind",
                    "evidence_object_ids",
                    "via_node_id",
                }
            ),
            context="affected topology invalidation edge",
        )
        if payload["schema_version"] != AFFECTED_TOPOLOGY_INVALIDATION_EDGE_SCHEMA:
            raise AffectedBlueprintReadError(
                "affected topology invalidation edge schema is not current"
            )
        via_node_id = payload["via_node_id"]
        if not isinstance(via_node_id, str):
            raise AffectedBlueprintReadError(
                "topology invalidation via node must be a string"
            )
        return cls(
            source_id=_string(payload["source_id"], context="topology edge source"),
            target_id=_string(payload["target_id"], context="topology edge target"),
            edge_kind=_string(payload["edge_kind"], context="topology edge kind"),
            evidence_object_ids=_string_array(
                payload["evidence_object_ids"],
                context="topology invalidation evidence objects",
            ),
            via_node_id=via_node_id,
        )


@dataclass(frozen=True)
class AffectedBlueprintIndex:
    """Content-addressed affected-read index over one qualified target ledger."""

    blueprint_fingerprint: str
    logical_fingerprint: str
    target_object_id: str
    ledger_row_ids: tuple[str, ...]
    object_fingerprints: tuple[tuple[str, str], ...]
    shard_fingerprints: tuple[tuple[str, str], ...]
    shard_member_ids: tuple[tuple[str, tuple[str, ...]], ...]
    affected_edges: tuple[tuple[str, tuple[str, ...]], ...]
    topology_invalidation_edges: tuple[AffectedTopologyInvalidationEdge, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "blueprint_fingerprint",
            "logical_fingerprint",
            "target_object_id",
        ):
            if not str(getattr(self, name, "")):
                raise AffectedBlueprintReadError(
                    f"affected blueprint index requires {name}"
                )
        object_rows = _index_pairs(
            self.object_fingerprints, context="object fingerprint index"
        )
        shard_rows = _index_pairs(
            self.shard_fingerprints, context="shard fingerprint index"
        )
        shard_members = _index_pairs(
            self.shard_member_ids, context="shard member index"
        )
        edges = _index_pairs(self.affected_edges, context="affected edge index")
        object_ids = frozenset(object_rows)
        shard_ids = frozenset(shard_rows)
        supplied_topology_edges = tuple(self.topology_invalidation_edges)
        if any(
            not isinstance(row, AffectedTopologyInvalidationEdge)
            for row in supplied_topology_edges
        ):
            raise AffectedBlueprintReadError(
                "topology invalidation edges require current typed records"
            )
        topology_edges = tuple(
            sorted(
                supplied_topology_edges,
                key=lambda row: (*row.identity, row.evidence_object_ids),
            )
        )
        topology_edge_ids = tuple(row.identity for row in topology_edges)
        if len(topology_edge_ids) != len(set(topology_edge_ids)):
            raise AffectedBlueprintReadError(
                "topology invalidation edge identity is duplicated"
            )
        object.__setattr__(self, "topology_invalidation_edges", topology_edges)
        if self.target_object_id not in object_rows:
            raise AffectedBlueprintReadError(
                "affected blueprint target object is not content-addressed"
            )
        if not self.ledger_row_ids:
            raise AffectedBlueprintReadError(
                "affected blueprint index requires ordered ledger rows"
            )
        if len(self.ledger_row_ids) != len(set(self.ledger_row_ids)):
            raise AffectedBlueprintReadError(
                "affected blueprint index contains duplicate ledger rows"
            )
        if any(not str(value) for value in object_rows.values()):
            raise AffectedBlueprintReadError(
                "affected blueprint object fingerprint index contains an empty value"
            )
        if any(not str(value) for value in shard_rows.values()):
            raise AffectedBlueprintReadError(
                "affected blueprint shard fingerprint index contains an empty value"
            )
        missing_rows = sorted(set(self.ledger_row_ids) - object_ids)
        if missing_rows:
            raise AffectedBlueprintReadError(
                "affected blueprint index has unaddressed ledger rows: "
                + ", ".join(missing_rows)
            )
        missing_shards = sorted(set(shard_members) - shard_ids)
        if missing_shards:
            raise AffectedBlueprintReadError(
                "affected blueprint shard members have no fingerprint: "
                + ", ".join(missing_shards)
            )
        for affected_id, referenced_ids in edges.items():
            if not affected_id:
                raise AffectedBlueprintReadError(
                    "affected blueprint edge contains an empty affected id"
                )
            refs = _ids(referenced_ids)
            missing = sorted(set(refs) - object_ids)
            if not refs or missing:
                raise AffectedBlueprintReadError(
                    "affected blueprint edge is incomplete for "
                    f"{affected_id}: missing={missing}"
                )
        known_affected_ids = {
            *edges,
            *object_ids,
            *(
                member_id
                for member_ids in shard_members.values()
                for member_id in _ids(member_ids)
            ),
        }
        for edge in topology_edges:
            unknown_endpoints = sorted(
                {edge.source_id, edge.target_id} - known_affected_ids
            )
            missing_evidence = sorted(
                set(edge.evidence_object_ids) - object_ids
            )
            if unknown_endpoints or missing_evidence:
                raise AffectedBlueprintReadError(
                    "topology invalidation edge is incomplete: "
                    f"unknown_endpoints={unknown_endpoints}, "
                    f"missing_evidence={missing_evidence}"
                )

    @property
    def schema_version(self) -> str:
        return AFFECTED_BLUEPRINT_INDEX_SCHEMA

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "blueprint_fingerprint": self.blueprint_fingerprint,
            "logical_fingerprint": self.logical_fingerprint,
            "target_object_id": self.target_object_id,
            "ledger_row_ids": list(self.ledger_row_ids),
            "object_fingerprints": dict(self.object_fingerprints),
            "shard_fingerprints": dict(self.shard_fingerprints),
            "shard_member_ids": {
                shard_id: list(member_ids)
                for shard_id, member_ids in self.shard_member_ids
            },
            "affected_edges": {
                affected_id: list(object_ids)
                for affected_id, object_ids in self.affected_edges
            },
            "topology_invalidation_edges": [
                row.to_dict() for row in self.topology_invalidation_edges
            ],
            "claim_boundary": (
                "This index selects one content-addressed affected closure and its "
                "qualified readiness ledger. It is not a whole-blueprint payload."
            ),
        }

    @cached_property
    def fingerprint(self) -> str:
        return fingerprint_value(self.identity_payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: Any) -> "AffectedBlueprintIndex":
        payload = _strict_object(
            value,
            required=frozenset(
                {
                    "schema_version",
                    "blueprint_fingerprint",
                    "logical_fingerprint",
                    "target_object_id",
                    "ledger_row_ids",
                    "object_fingerprints",
                    "shard_fingerprints",
                    "shard_member_ids",
                    "affected_edges",
                    "topology_invalidation_edges",
                    "claim_boundary",
                    "fingerprint",
                }
            ),
            context="affected blueprint index",
        )
        if payload["schema_version"] != AFFECTED_BLUEPRINT_INDEX_SCHEMA:
            raise AffectedBlueprintReadError(
                "affected blueprint index schema is not current"
            )
        _string(payload["claim_boundary"], context="affected index claim boundary")
        index = cls(
            blueprint_fingerprint=_string(
                payload["blueprint_fingerprint"],
                context="affected index blueprint fingerprint",
            ),
            logical_fingerprint=_string(
                payload["logical_fingerprint"],
                context="affected index logical fingerprint",
            ),
            target_object_id=_string(
                payload["target_object_id"],
                context="affected index target object id",
            ),
            ledger_row_ids=_string_array(
                payload["ledger_row_ids"], context="affected index ledger rows"
            ),
            object_fingerprints=tuple(
                sorted(
                    _string_map(
                        payload["object_fingerprints"],
                        context="object fingerprint index",
                    ).items()
                )
            ),
            shard_fingerprints=tuple(
                sorted(
                    _string_map(
                        payload["shard_fingerprints"],
                        context="shard fingerprint index",
                    ).items()
                )
            ),
            shard_member_ids=tuple(
                sorted(
                    (
                        _string(key, context="shard member index key"),
                        tuple(
                            sorted(
                                _string_array(
                                    item,
                                    context=f"shard member index {key}",
                                )
                            )
                        ),
                    )
                    for key, item in _index_pairs(
                        payload["shard_member_ids"],
                        context="shard member index",
                    ).items()
                )
            ),
            affected_edges=tuple(
                sorted(
                    (
                        _string(key, context="affected edge index key"),
                        tuple(
                            sorted(
                                _string_array(
                                    item,
                                    context=f"affected edge index {key}",
                                )
                            )
                        ),
                    )
                    for key, item in _index_pairs(
                        payload["affected_edges"],
                        context="affected edge index",
                    ).items()
                )
            ),
            topology_invalidation_edges=tuple(
                AffectedTopologyInvalidationEdge.from_dict(item)
                for item in _array_like(
                    payload["topology_invalidation_edges"],
                    context="topology invalidation edge array",
                )
            ),
        )
        if _string(
            payload["fingerprint"], context="affected index fingerprint"
        ) != index.fingerprint:
            raise AffectedBlueprintReadError(
                "affected blueprint index fingerprint mismatch"
            )
        return index


def _put_content_addressed_object(
    objects: dict[str, Any], object_id: str, payload: Any
) -> None:
    existing = objects.get(object_id, _MISSING)
    if existing is not _MISSING and existing != payload:
        raise AffectedBlueprintReadError(
            f"normalized object identity collision: {object_id}"
        )
    objects[object_id] = payload


def _materialize_topology_invalidation_edges(
    objects: Mapping[str, Any],
) -> tuple[
    tuple[AffectedTopologyInvalidationEdge, ...],
    dict[str, set[str]],
]:
    """Project exact typed topology dependencies without scanning target source."""

    nodes: dict[str, tuple[str, tuple[str, ...]]] = {}
    topology_relations: list[tuple[str, str, str, str, str]] = []
    for object_id, value in sorted(objects.items()):
        if not isinstance(value, Mapping):
            continue
        kind = str(value.get("kind", ""))
        if kind == "blueprint_topology_node":
            node_id = _string(
                value.get("node_id"),
                context=f"topology node identity {object_id}",
            )
            if node_id in nodes:
                raise AffectedBlueprintReadError(
                    f"duplicate topology node identity: {node_id}"
                )
            surfaces = tuple(
                sorted(
                    _string_array(
                        value.get("implementation_surface_ids", ()),
                        context=f"topology node surfaces {node_id}",
                    )
                )
            )
            nodes[node_id] = (object_id, surfaces)
        elif kind == "blueprint_topology_relation":
            relation_kind = str(value.get("relation_kind", ""))
            if relation_kind not in TOPOLOGY_RELATION_KINDS:
                # The topology owner retains the unknown-kind finding.  An
                # invalid relation cannot become an invalidation authority.
                continue
            topology_relations.append(
                (
                    _string(
                        value.get("relation_id"),
                        context=f"topology relation identity {object_id}",
                    ),
                    relation_kind,
                    _string(
                        value.get("producer_id"),
                        context=f"topology relation producer {object_id}",
                    ),
                    _string(
                        value.get("consumer_id"),
                        context=f"topology relation consumer {object_id}",
                    ),
                    object_id,
                )
            )

    edge_evidence: dict[tuple[str, str, str, str], set[str]] = {}
    object_edges: dict[str, set[str]] = {}

    def add_edge(
        source_id: str,
        target_id: str,
        edge_kind: str,
        evidence_object_ids: tuple[str, ...],
        *,
        via_node_id: str = "",
    ) -> None:
        object_edges.setdefault(source_id, set()).update(
            evidence_object_ids
        )
        object_edges.setdefault(target_id, set()).update(
            evidence_object_ids
        )
        if source_id == target_id:
            # A feedback self-loop carries evidence but expands no new seed.
            return
        identity = (source_id, target_id, edge_kind, via_node_id)
        edge_evidence.setdefault(identity, set()).update(evidence_object_ids)

    for node_id, (node_object_id, surface_ids) in sorted(nodes.items()):
        object_edges.setdefault(node_id, set()).add(node_object_id)
        for surface_id in surface_ids:
            object_edges.setdefault(surface_id, set()).add(node_object_id)
            add_edge(
                surface_id,
                node_id,
                "realization_owner",
                (node_object_id,),
                via_node_id=node_id,
            )
            add_edge(
                node_id,
                surface_id,
                "realization_member",
                (node_object_id,),
                via_node_id=node_id,
            )

    children_by_parent: dict[str, dict[str, set[str]]] = {}
    for (
        relation_id,
        relation_kind,
        producer_id,
        consumer_id,
        relation_object_id,
    ) in topology_relations:
        if producer_id not in nodes or consumer_id not in nodes:
            # The topology owner retains the exact endpoint gap. An invalid
            # relation cannot become an invalidation authority here.
            continue
        object_edges.setdefault(relation_id, set()).add(relation_object_id)
        add_edge(
            relation_id,
            producer_id,
            "relation_producer",
            (relation_object_id,),
        )
        add_edge(
            relation_id,
            consumer_id,
            "relation_consumer",
            (relation_object_id,),
        )
        if relation_kind == "child_to_parent":
            children_by_parent.setdefault(consumer_id, {}).setdefault(
                producer_id, set()
            ).add(relation_object_id)
            add_edge(
                producer_id,
                consumer_id,
                "ancestor",
                (relation_object_id,),
                via_node_id=consumer_id,
            )
            add_edge(
                consumer_id,
                producer_id,
                "child",
                (relation_object_id,),
                via_node_id=consumer_id,
            )
        else:
            # Producer output and support flow downstream.  Delegation is a
            # dependency in the other direction: a changed delegate invalidates
            # its delegator.  The relation seed above always reviews both ends.
            direction = _TOPOLOGY_RELATION_INVALIDATION_DIRECTIONS.get(relation_kind)
            if direction is None:
                raise AffectedBlueprintReadError(
                    "topology relation has no explicit invalidation direction: "
                    + relation_kind
                )
            invalidation_source_id, invalidation_target_id = (
                (consumer_id, producer_id)
                if direction == "consumer_to_producer"
                else (producer_id, consumer_id)
            )
            add_edge(
                invalidation_source_id,
                invalidation_target_id,
                relation_kind,
                (relation_object_id,),
            )

    for parent_id, child_rows in sorted(children_by_parent.items()):
        ordered_children = sorted(
            (child_id, tuple(sorted(relation_ids)))
            for child_id, relation_ids in child_rows.items()
        )
        if len(ordered_children) < 2:
            continue
        # A canonical star preserves exact sibling reachability from every
        # child while keeping the frozen index linear in sibling count.  The
        # former all-pairs expansion added k*(k-1) rows and duplicated the
        # same parent evidence throughout large, flat model families.
        anchor_id, anchor_relation_ids = ordered_children[0]
        for sibling_id, sibling_relation_ids in ordered_children[1:]:
            evidence_ids = tuple(
                sorted((*anchor_relation_ids, *sibling_relation_ids))
            )
            add_edge(
                anchor_id,
                sibling_id,
                "sibling",
                evidence_ids,
                via_node_id=parent_id,
            )
            add_edge(
                sibling_id,
                anchor_id,
                "sibling",
                evidence_ids,
                via_node_id=parent_id,
            )

    edges = tuple(
        AffectedTopologyInvalidationEdge(
            source_id=source_id,
            target_id=target_id,
            edge_kind=edge_kind,
            evidence_object_ids=tuple(sorted(evidence_ids)),
            via_node_id=via_node_id,
        )
        for (
            source_id,
            target_id,
            edge_kind,
            via_node_id,
        ), evidence_ids in sorted(edge_evidence.items())
    )
    return edges, object_edges


def materialize_affected_blueprint_index(
    projection: Any,
    *,
    target_system_id: str,
    target_profile: str,
    subject_revision: str,
    descriptor_fingerprint: str,
    target_blueprint_fingerprint: str,
    layer_plan_id: str,
    layer_plan_fingerprint: str,
    readiness_ledger: BlueprintReadinessLedger,
    shared_objects: Mapping[str, Any],
    required_path_quality_model_ids: Iterable[str] = (),
) -> tuple[AffectedBlueprintIndex, tuple[tuple[str, Any], ...]]:
    """Add a separately addressed ledger index without mutating base authority."""

    for name, value in (
        ("target system id", target_system_id),
        ("target profile", target_profile),
        ("subject revision", subject_revision),
        ("descriptor fingerprint", descriptor_fingerprint),
        ("target blueprint fingerprint", target_blueprint_fingerprint),
        ("layer plan id", layer_plan_id),
        ("layer plan fingerprint", layer_plan_fingerprint),
    ):
        _string(value, context=f"affected blueprint {name}")
    objects = {str(key): item for key, item in shared_objects.items()}
    base_object_fingerprints = {
        key: str(value)
        for key, value in _index_pairs(
            _field(projection, "object_fingerprints", ()),
            context="object fingerprint index",
        ).items()
    }
    object_fingerprint_by_id: dict[str, str] = {}
    for object_id, expected in base_object_fingerprints.items():
        if object_id not in objects:
            raise AffectedBlueprintReadError(
                f"normalized shared object is missing: {object_id}"
            )
        actual = fingerprint_value(objects[object_id])
        if actual != expected:
            raise AffectedBlueprintReadError(
                f"normalized shared object fingerprint mismatch: {object_id}"
            )
        object_fingerprint_by_id[object_id] = actual

    # A supplied shared-object mapping may contain extra current objects that
    # are not named by the normalized projection. Preserve the existing
    # behavior, but fingerprint each exact payload only once in this invocation.
    for object_id, payload in objects.items():
        if object_id not in object_fingerprint_by_id:
            object_fingerprint_by_id[object_id] = fingerprint_value(payload)

    def put_indexed_object(
        object_id: str,
        payload: Any,
        *,
        precomputed_fingerprint: str | None = None,
    ) -> str:
        _put_content_addressed_object(objects, object_id, payload)
        existing = object_fingerprint_by_id.get(object_id)
        if existing is not None:
            if (
                precomputed_fingerprint is not None
                and precomputed_fingerprint != existing
            ):
                raise AffectedBlueprintReadError(
                    f"normalized object fingerprint collision: {object_id}"
                )
            return existing
        actual = (
            precomputed_fingerprint
            if precomputed_fingerprint is not None
            else fingerprint_value(payload)
        )
        object_fingerprint_by_id[object_id] = actual
        return actual

    native_object_ids: dict[tuple[str, str, str], str] = {}
    for row in readiness_ledger.rows:
        for native in row.native_reports:
            identity = (
                native.owner_id,
                native.report_id,
                native.report_fingerprint,
            )
            if identity in native_object_ids:
                continue
            payload = {
                "kind": "blueprint_native_report",
                "owner_id": native.owner_id,
                "report_id": native.report_id,
                "report_fingerprint": native.report_fingerprint,
            }
            payload_fingerprint = fingerprint_value(payload)
            object_id = (
                "blueprint-native-report:"
                + payload_fingerprint.split(":", 1)[-1]
            )
            put_indexed_object(
                object_id,
                payload,
                precomputed_fingerprint=payload_fingerprint,
            )
            native_object_ids[identity] = object_id

    for gap in readiness_ledger.gaps:
        gap_payload = {
            "kind": "blueprint_gap",
            "gap_id": gap.gap_id,
            **gap.to_dict(),
        }
        put_indexed_object(
            gap.gap_id,
            gap_payload,
        )

    ledger_row_ids: list[str] = []
    for row in readiness_ledger.rows:
        native_ids = tuple(
            native_object_ids[
                (native.owner_id, native.report_id, native.report_fingerprint)
            ]
            for native in row.native_reports
        )
        payload = {
            "kind": "blueprint_readiness_row",
            "layer": row.layer,
            "status": row.status,
            "evidence_ids": list(row.evidence_ids),
            "gap_ids": list(row.gap_ids),
            "native_report_object_ids": list(native_ids),
            "pre_code_status": row.pre_code_status,
            "executed_evidence_status": row.executed_evidence_status,
            "implementation_admitted": row.implementation_admitted,
            "referenced_object_ids": [*row.gap_ids, *native_ids],
        }
        payload_fingerprint = fingerprint_value(payload)
        row_id = (
            "blueprint-readiness-row:"
            + payload_fingerprint.split(":", 1)[-1]
        )
        put_indexed_object(
            row_id,
            payload,
            precomputed_fingerprint=payload_fingerprint,
        )
        ledger_row_ids.append(row_id)

    target_payload = {
        "kind": "affected_blueprint_target",
        "target_system_id": str(target_system_id),
        "target_profile": str(target_profile),
        "subject_revision": str(subject_revision),
        "descriptor_fingerprint": str(descriptor_fingerprint),
        "blueprint_fingerprint": str(target_blueprint_fingerprint),
        "logical_fingerprint": str(_field(projection, "logical_fingerprint")),
        "layer_plan_id": str(layer_plan_id),
        "layer_plan_fingerprint": str(layer_plan_fingerprint),
        "required_path_quality_model_ids": list(
            sorted(
                _string_array(
                    tuple(required_path_quality_model_ids),
                    context="required path-quality model ids",
                )
            )
        ),
        "ledger_row_ids": list(ledger_row_ids),
        "referenced_object_ids": list(ledger_row_ids),
    }
    target_payload_fingerprint = fingerprint_value(target_payload)
    target_object_id = (
        "affected-blueprint-target:"
        + target_payload_fingerprint.split(":", 1)[-1]
    )
    put_indexed_object(
        target_object_id,
        target_payload,
        precomputed_fingerprint=target_payload_fingerprint,
    )

    topology_invalidation_edges, topology_object_edges = (
        _materialize_topology_invalidation_edges(objects)
    )

    shard_members = tuple(
        sorted(
            (str(shard_id), tuple(sorted(set(_ids(member_ids)))))
            for shard_id, member_ids in _index_pairs(
                _field(projection, "shard_member_ids", ()),
                context="shard member index",
            ).items()
        )
    )
    affected_member_ids = {
        member_id for _shard_id, member_ids in shard_members for member_id in member_ids
    } | set(base_object_fingerprints) | set(topology_object_edges)
    # Each affected edge points once to the target object; that object owns the
    # ordered ledger references.  Repeating every row on every edge would make
    # the index grow as affected-members x layers without adding authority.
    affected_object_edges = {
        affected_id: {target_object_id}
        for affected_id in affected_member_ids
    }
    for affected_id, object_ids in topology_object_edges.items():
        affected_object_edges.setdefault(affected_id, {target_object_id}).update(
            object_ids
        )
    index = AffectedBlueprintIndex(
        blueprint_fingerprint=str(target_blueprint_fingerprint),
        logical_fingerprint=str(_field(projection, "logical_fingerprint")),
        target_object_id=target_object_id,
        ledger_row_ids=tuple(ledger_row_ids),
        object_fingerprints=tuple(sorted(object_fingerprint_by_id.items())),
        shard_fingerprints=tuple(
            sorted(
                (str(key), str(value))
                for key, value in _index_pairs(
                    _field(projection, "shard_fingerprints", ()),
                    context="shard fingerprint index",
                ).items()
            )
        ),
        shard_member_ids=shard_members,
        affected_edges=tuple(
            (affected_id, tuple(sorted(object_ids)))
            for affected_id, object_ids in sorted(affected_object_edges.items())
        ),
        topology_invalidation_edges=topology_invalidation_edges,
    )
    return index, tuple(sorted(objects.items()))


@dataclass(frozen=True)
class AffectedBlueprintReadResult:
    blueprint_fingerprint: str
    logical_fingerprint: str
    requested_seed_ids: tuple[str, ...]
    affected_ids: tuple[str, ...]
    propagated_affected_ids: tuple[str, ...]
    shard_ids: tuple[str, ...]
    object_ids: tuple[str, ...]
    ancestor_object_ids: tuple[str, ...]
    shards: tuple[tuple[str, Any], ...]
    objects: tuple[tuple[str, Any], ...]

    @property
    def schema_version(self) -> str:
        return AFFECTED_BLUEPRINT_READER_SCHEMA

    @cached_property
    def fingerprint(self) -> str:
        return fingerprint_value(self.identity_payload())

    @property
    def claim_boundary(self) -> str:
        return (
            "This result proves only the fingerprint-checked affected shards, "
            "their referenced objects, and required ancestors. It neither "
            "constructs nor qualifies the whole blueprint."
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "blueprint_fingerprint": self.blueprint_fingerprint,
            "logical_fingerprint": self.logical_fingerprint,
            "requested_seed_ids": list(self.requested_seed_ids),
            "affected_ids": list(self.affected_ids),
            "propagated_affected_ids": list(self.propagated_affected_ids),
            "shard_ids": list(self.shard_ids),
            "object_ids": list(self.object_ids),
            "ancestor_object_ids": list(self.ancestor_object_ids),
            "shards": dict(self.shards),
            "objects": dict(self.objects),
            "claim_boundary": self.claim_boundary,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}


class AffectedBlueprintReader:
    """Read one exact affected closure without a whole-blueprint fallback."""

    def __init__(
        self,
        projection: Any,
        *,
        load_shard: ShardLoader,
        load_object: ObjectLoader,
    ) -> None:
        if not callable(load_shard) or not callable(load_object):
            raise AffectedBlueprintReadError("shard and object loaders must be callable")
        self._projection = projection
        self._load_shard = load_shard
        self._load_object = load_object
        self._shard_fingerprints = {
            key: str(value)
            for key, value in _index_pairs(
                getattr(projection, "shard_fingerprints", ()),
                context="shard fingerprint index",
            ).items()
        }
        self._object_fingerprints = {
            key: str(value)
            for key, value in _index_pairs(
                getattr(projection, "object_fingerprints", ()),
                context="object fingerprint index",
            ).items()
        }
        raw_members = _index_pairs(
            getattr(projection, "shard_member_ids", ()),
            context="shard member index",
        )
        self._shard_members = {
            shard_id: tuple(sorted(set(_ids(member_ids))))
            for shard_id, member_ids in raw_members.items()
        }
        raw_edges = _index_pairs(
            _field(projection, "affected_edges", ()),
            context="affected edge index",
        )
        self._affected_edges = {
            affected_id: tuple(sorted(set(_ids(object_ids))))
            for affected_id, object_ids in raw_edges.items()
        }
        raw_topology_edges = tuple(
            _field(projection, "topology_invalidation_edges", ())
        )
        if any(
            not isinstance(row, AffectedTopologyInvalidationEdge)
            for row in raw_topology_edges
        ):
            raise AffectedBlueprintReadError(
                "topology invalidation edges require current typed records"
            )
        self._topology_invalidation_edges = tuple(
            sorted(
                raw_topology_edges,
                key=lambda row: (*row.identity, row.evidence_object_ids),
            )
        )
        self._topology_edges_by_source: dict[
            str, tuple[AffectedTopologyInvalidationEdge, ...]
        ] = {}
        grouped_topology_edges: dict[
            str, list[AffectedTopologyInvalidationEdge]
        ] = {}
        for edge in self._topology_invalidation_edges:
            grouped_topology_edges.setdefault(edge.source_id, []).append(edge)
        self._topology_edges_by_source = {
            source_id: tuple(rows)
            for source_id, rows in grouped_topology_edges.items()
        }
        missing_shards = sorted(
            set(self._shard_members) - set(self._shard_fingerprints)
        )
        if missing_shards:
            raise AffectedBlueprintReadError(
                "shard member index has no fingerprint for: "
                + ", ".join(missing_shards)
            )
        missing_edge_objects = sorted(
            {
                object_id
                for object_ids in self._affected_edges.values()
                for object_id in object_ids
                if object_id not in self._object_fingerprints
            }
        )
        if missing_edge_objects:
            raise AffectedBlueprintReadError(
                "affected edge index references unaddressed objects: "
                + ", ".join(missing_edge_objects)
            )
        missing_topology_evidence = sorted(
            {
                object_id
                for edge in self._topology_invalidation_edges
                for object_id in edge.evidence_object_ids
                if object_id not in self._object_fingerprints
            }
        )
        if missing_topology_evidence:
            raise AffectedBlueprintReadError(
                "topology invalidation edges reference unaddressed evidence: "
                + ", ".join(missing_topology_evidence)
            )

    def read(self, affected_ids: Iterable[str]) -> AffectedBlueprintReadResult:
        requested = tuple(sorted({str(value) for value in affected_ids if str(value)}))
        if not requested:
            raise AffectedBlueprintReadError("affected ids must not be empty")

        requested_set = set(requested)
        indexed_members = {
            member_id
            for member_ids in self._shard_members.values()
            for member_id in member_ids
        }
        known_affected_ids = {
            *indexed_members,
            *self._object_fingerprints,
            *self._affected_edges,
            *(edge.source_id for edge in self._topology_invalidation_edges),
            *(edge.target_id for edge in self._topology_invalidation_edges),
        }
        unknown = sorted(requested_set - known_affected_ids)
        if unknown:
            raise AffectedBlueprintReadError(
                "unknown affected ids: " + ", ".join(unknown)
            )

        propagated_set = set(requested_set)
        pending_affected = deque(requested)
        while pending_affected:
            source_id = pending_affected.popleft()
            for edge in self._topology_edges_by_source.get(source_id, ()):
                if edge.target_id in propagated_set:
                    continue
                propagated_set.add(edge.target_id)
                pending_affected.append(edge.target_id)
        affected = tuple(sorted(propagated_set))
        affected_set = set(affected)
        selected_shards = tuple(
            sorted(
                shard_id
                for shard_id, member_ids in self._shard_members.items()
                if affected_set.intersection(member_ids)
            )
        )
        directly_indexed_objects = affected_set.intersection(
            self._object_fingerprints
        )
        edge_indexed_ids = affected_set.intersection(self._affected_edges)

        loaded_shards: list[tuple[str, Any]] = []
        pending_objects: set[str] = set(directly_indexed_objects)
        for affected_id in edge_indexed_ids:
            pending_objects.update(self._affected_edges[affected_id])
        allowed_topology_object_ids = {
            object_id
            for affected_id in edge_indexed_ids
            for object_id in self._affected_edges[affected_id]
            if object_id.startswith("topology-")
        }
        ancestor_ids: set[str] = set()
        for shard_id in selected_shards:
            try:
                payload = self._load_shard(shard_id)
            except Exception as exc:
                raise AffectedBlueprintReadError(
                    f"failed to load affected shard {shard_id}: {exc}"
                ) from exc
            if fingerprint_value(payload) != self._shard_fingerprints[shard_id]:
                raise AffectedBlueprintReadError(
                    f"shard fingerprint mismatch: {shard_id}"
                )
            payload = _reference_shard(payload, shard_id=shard_id)
            loaded_shards.append((shard_id, payload))
            explicit, inferred, ancestors = _discover_links(payload)
            if (
                isinstance(payload, Mapping)
                and payload.get("kind") == "blueprint_topology_index"
            ):
                inferred = {
                    object_id
                    for object_id in inferred
                    if not object_id.startswith("topology-relation:")
                    or object_id in allowed_topology_object_ids
                }
            missing_explicit = sorted(explicit - set(self._object_fingerprints))
            if missing_explicit:
                raise AffectedBlueprintReadError(
                    f"shard {shard_id} references unindexed objects: "
                    + ", ".join(missing_explicit)
                )
            pending_objects.update(explicit)
            pending_objects.update(inferred.intersection(self._object_fingerprints))
            ancestor_ids.update(ancestors.intersection(self._object_fingerprints))

        queue = deque(sorted(pending_objects))
        queued = set(queue)
        loaded_objects: list[tuple[str, Any]] = []
        loaded_object_ids: set[str] = set()
        while queue:
            object_id = queue.popleft()
            if object_id in loaded_object_ids:
                continue
            try:
                payload = self._load_object(object_id)
            except Exception as exc:
                raise AffectedBlueprintReadError(
                    f"failed to load referenced object {object_id}: {exc}"
                ) from exc
            if fingerprint_value(payload) != self._object_fingerprints[object_id]:
                raise AffectedBlueprintReadError(
                    f"object fingerprint mismatch: {object_id}"
                )
            loaded_objects.append((object_id, payload))
            loaded_object_ids.add(object_id)
            explicit, inferred, ancestors = _discover_links(payload)
            if (
                isinstance(payload, Mapping)
                and payload.get("kind") == "blueprint_topology_index"
            ):
                inferred = {
                    discovered_id
                    for discovered_id in inferred
                    if not discovered_id.startswith("topology-relation:")
                    or discovered_id in allowed_topology_object_ids
                }
            missing_explicit = sorted(explicit - set(self._object_fingerprints))
            if missing_explicit:
                raise AffectedBlueprintReadError(
                    f"object {object_id} references unindexed objects: "
                    + ", ".join(missing_explicit)
                )
            discovered = explicit | inferred.intersection(self._object_fingerprints)
            ancestor_ids.update(
                (ancestors - {object_id}).intersection(
                    self._object_fingerprints
                )
            )
            for discovered_id in sorted(discovered):
                if discovered_id not in loaded_object_ids and discovered_id not in queued:
                    queue.append(discovered_id)
                    queued.add(discovered_id)

        return AffectedBlueprintReadResult(
            blueprint_fingerprint=str(
                _field(self._projection, "blueprint_fingerprint", "")
            ),
            logical_fingerprint=str(
                _field(self._projection, "logical_fingerprint", "")
            ),
            requested_seed_ids=requested,
            affected_ids=affected,
            propagated_affected_ids=tuple(
                sorted(affected_set - requested_set)
            ),
            shard_ids=tuple(row[0] for row in loaded_shards),
            object_ids=tuple(row[0] for row in loaded_objects),
            ancestor_object_ids=tuple(
                sorted(ancestor_ids.intersection(loaded_object_ids))
            ),
            shards=tuple(loaded_shards),
            objects=tuple(loaded_objects),
        )


def read_affected_blueprint(
    projection: Any,
    *,
    affected_ids: Iterable[str],
    load_shard: ShardLoader,
    load_object: ObjectLoader,
) -> AffectedBlueprintReadResult:
    """Convenience function for one bounded affected read."""

    return AffectedBlueprintReader(
        projection,
        load_shard=load_shard,
        load_object=load_object,
    ).read(affected_ids)


_TARGET_FIELDS = frozenset(
    {
        "kind",
        "target_system_id",
        "target_profile",
        "subject_revision",
        "descriptor_fingerprint",
        "blueprint_fingerprint",
        "logical_fingerprint",
        "layer_plan_id",
        "layer_plan_fingerprint",
        "required_path_quality_model_ids",
        "ledger_row_ids",
        "referenced_object_ids",
    }
)
_ROW_FIELDS = frozenset(
    {
        "kind",
        "layer",
        "status",
        "evidence_ids",
        "gap_ids",
        "native_report_object_ids",
        "pre_code_status",
        "executed_evidence_status",
        "implementation_admitted",
        "referenced_object_ids",
    }
)
_GAP_FIELDS = frozenset(
    {
        "kind",
        "gap_id",
        "layer",
        "object_kind",
        "object_id",
        "status",
        "owner_id",
        "evidence_ref",
        "expected_fingerprint",
        "observed_fingerprint",
        "message",
    }
)
_NATIVE_REPORT_FIELDS = frozenset(
    {"kind", "owner_id", "report_id", "report_fingerprint"}
)


@dataclass(frozen=True)
class AffectedBlueprintUnderstanding:
    """AI-facing readiness derived only from one loaded affected closure."""

    scope: str
    blueprint_fingerprint: str
    logical_fingerprint: str
    index_fingerprint: str
    target_system_id: str
    target_profile: str
    subject_revision: str
    descriptor_fingerprint: str
    layer_plan_id: str
    layer_plan_fingerprint: str
    requested_seed_ids: tuple[str, ...]
    affected_ids: tuple[str, ...]
    propagated_affected_ids: tuple[str, ...]
    loaded_shard_ids: tuple[str, ...]
    loaded_object_ids: tuple[str, ...]
    layer_statuses: tuple[tuple[str, str], ...]
    status: str
    deepest_proven_layer: str
    first_gap: BlueprintGapRef | None
    gap_ids: tuple[str, ...]
    gap_count: int
    pre_code_status: str
    executed_evidence_status: str
    implementation_admitted: bool
    native_reports: tuple[BlueprintNativeReportRef, ...]
    required_path_quality_model_ids: tuple[str, ...]
    path_quality_bindings: tuple[ModelPathQualityBlueprintBinding, ...]

    @property
    def schema_version(self) -> str:
        return AFFECTED_BLUEPRINT_UNDERSTANDING_SCHEMA

    @property
    def affected_surface_ids(self) -> tuple[str, ...]:
        return self.affected_ids

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    @property
    def claim_boundary(self) -> str:
        return (
            "This readiness result is derived from one fingerprint-checked affected "
            "closure and its loaded canonical ledger. It runs no provider, native "
            "validation owner, whole builder, or implementation action."
        )

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "scope": self.scope,
            "blueprint_fingerprint": self.blueprint_fingerprint,
            "logical_fingerprint": self.logical_fingerprint,
            "index_fingerprint": self.index_fingerprint,
            "target_system_id": self.target_system_id,
            "target_profile": self.target_profile,
            "subject_revision": self.subject_revision,
            "descriptor_fingerprint": self.descriptor_fingerprint,
            "layer_plan_id": self.layer_plan_id,
            "layer_plan_fingerprint": self.layer_plan_fingerprint,
            "requested_seed_ids": list(self.requested_seed_ids),
            "affected_ids": list(self.affected_ids),
            "propagated_affected_ids": list(self.propagated_affected_ids),
            "loaded_shard_ids": list(self.loaded_shard_ids),
            "loaded_object_ids": list(self.loaded_object_ids),
            "layer_statuses": [
                {"layer": layer, "status": status}
                for layer, status in self.layer_statuses
            ],
            "status": self.status,
            "deepest_proven_layer": self.deepest_proven_layer,
            "first_gap": (
                {"gap_id": self.first_gap.gap_id, **self.first_gap.to_dict()}
                if self.first_gap
                else None
            ),
            "gap_ids": list(self.gap_ids),
            "gap_count": self.gap_count,
            "pre_code_status": self.pre_code_status,
            "executed_evidence_status": self.executed_evidence_status,
            "implementation_admitted": self.implementation_admitted,
            "native_reports": [row.to_dict() for row in self.native_reports],
            "required_path_quality_model_ids": list(
                self.required_path_quality_model_ids
            ),
            "path_quality_bindings": [
                row.to_dict() for row in self.path_quality_bindings
            ],
            "claim_boundary": self.claim_boundary,
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload


def _parse_native_report(object_id: str, value: Any) -> BlueprintNativeReportRef:
    payload = _strict_object(
        value,
        required=_NATIVE_REPORT_FIELDS,
        context=f"native report object {object_id}",
    )
    if payload["kind"] != "blueprint_native_report":
        raise AffectedBlueprintReadError(
            f"native report object has the wrong kind: {object_id}"
        )
    try:
        return BlueprintNativeReportRef(
            owner_id=_string(payload["owner_id"], context="native report owner"),
            report_id=_string(payload["report_id"], context="native report id"),
            report_fingerprint=_string(
                payload["report_fingerprint"],
                context="native report fingerprint",
            ),
        )
    except ValueError as exc:
        raise AffectedBlueprintReadError(
            f"native report object is invalid: {object_id}: {exc}"
        ) from exc


def _parse_gap(object_id: str, value: Any) -> BlueprintGapRef:
    payload = _strict_object(
        value,
        required=_GAP_FIELDS,
        context=f"gap object {object_id}",
    )
    if payload["kind"] != "blueprint_gap" or payload["gap_id"] != object_id:
        raise AffectedBlueprintReadError(
            f"gap object identity or kind is invalid: {object_id}"
        )
    try:
        gap = BlueprintGapRef(
            layer=_string(payload["layer"], context="gap layer"),
            object_kind=_string(
                payload["object_kind"], context="gap object kind"
            ),
            object_id=_string(payload["object_id"], context="gap object id"),
            status=_string(payload["status"], context="gap status"),
            owner_id=(
                ""
                if payload["owner_id"] == ""
                else _string(payload["owner_id"], context="gap owner id")
            ),
            evidence_ref=(
                ""
                if payload["evidence_ref"] == ""
                else _string(payload["evidence_ref"], context="gap evidence ref")
            ),
            expected_fingerprint=(
                ""
                if payload["expected_fingerprint"] == ""
                else _string(
                    payload["expected_fingerprint"],
                    context="gap expected fingerprint",
                )
            ),
            observed_fingerprint=(
                ""
                if payload["observed_fingerprint"] == ""
                else _string(
                    payload["observed_fingerprint"],
                    context="gap observed fingerprint",
                )
            ),
            message=_string(payload["message"], context="gap message"),
        )
    except ValueError as exc:
        raise AffectedBlueprintReadError(
            f"gap object is invalid: {object_id}: {exc}"
        ) from exc
    if gap.gap_id != object_id:
        raise AffectedBlueprintReadError(
            f"gap object content does not match its content address: {object_id}"
        )
    return gap


def read_affected_blueprint_understanding(
    index_or_projection: AffectedBlueprintIndex | Mapping[str, Any] | Any,
    *,
    affected_ids: Iterable[str],
    load_shard: ShardLoader,
    load_object: ObjectLoader,
) -> AffectedBlueprintUnderstanding:
    """Derive compact readiness without a whole summary or whole conversion."""

    if isinstance(index_or_projection, Mapping):
        index = AffectedBlueprintIndex.from_dict(index_or_projection)
    elif isinstance(index_or_projection, AffectedBlueprintIndex):
        index = index_or_projection
    else:
        try:
            index = AffectedBlueprintIndex(
                blueprint_fingerprint=str(
                    _field(index_or_projection, "blueprint_fingerprint")
                ),
                logical_fingerprint=str(
                    _field(index_or_projection, "logical_fingerprint")
                ),
                target_object_id=str(
                    _field(index_or_projection, "target_object_id")
                ),
                ledger_row_ids=tuple(
                    _ids(_field(index_or_projection, "ledger_row_ids"))
                ),
                object_fingerprints=tuple(
                    _field(index_or_projection, "object_fingerprints")
                ),
                shard_fingerprints=tuple(
                    _field(index_or_projection, "shard_fingerprints")
                ),
                shard_member_ids=tuple(
                    _field(index_or_projection, "shard_member_ids")
                ),
                affected_edges=tuple(
                    _field(index_or_projection, "affected_edges")
                ),
                topology_invalidation_edges=tuple(
                    _field(index_or_projection, "topology_invalidation_edges")
                ),
            )
        except (TypeError, ValueError) as exc:
            raise AffectedBlueprintReadError(
                "normalized projection has no current affected-read ledger index"
            ) from exc

    read_result = read_affected_blueprint(
        index,
        affected_ids=affected_ids,
        load_shard=load_shard,
        load_object=load_object,
    )
    objects = dict(read_result.objects)
    if index.target_object_id not in objects:
        raise AffectedBlueprintReadError(
            "affected closure omitted the target identity object"
        )
    target = _strict_object(
        objects[index.target_object_id],
        required=_TARGET_FIELDS,
        context="affected blueprint target object",
    )
    if target["kind"] != "affected_blueprint_target":
        raise AffectedBlueprintReadError(
            "affected blueprint target object has the wrong kind"
        )
    target_row_ids = _string_array(
        target["ledger_row_ids"], context="target ledger row ids"
    )
    target_refs = _string_array(
        target["referenced_object_ids"], context="target object references"
    )
    if target_row_ids != index.ledger_row_ids or target_refs != index.ledger_row_ids:
        raise AffectedBlueprintReadError(
            "affected blueprint target omits or reorders readiness ledger rows"
        )
    if (
        _string(
            target["blueprint_fingerprint"],
            context="target blueprint fingerprint",
        )
        != index.blueprint_fingerprint
        or _string(
            target["logical_fingerprint"], context="target logical fingerprint"
        )
        != index.logical_fingerprint
    ):
        raise AffectedBlueprintReadError(
            "affected blueprint target identity differs from the normalized index"
        )

    rows: list[BlueprintLayerResult] = []
    gaps_by_id: dict[str, BlueprintGapRef] = {}
    native_by_identity: dict[tuple[str, str], BlueprintNativeReportRef] = {}
    for row_id in index.ledger_row_ids:
        if row_id not in objects:
            raise AffectedBlueprintReadError(
                f"affected closure omitted readiness ledger row: {row_id}"
            )
        payload = _strict_object(
            objects[row_id],
            required=_ROW_FIELDS,
            context=f"readiness ledger row {row_id}",
        )
        if payload["kind"] != "blueprint_readiness_row":
            raise AffectedBlueprintReadError(
                f"readiness ledger row has the wrong kind: {row_id}"
            )
        gap_ids = _string_array(
            payload["gap_ids"], context=f"readiness row {row_id} gap ids"
        )
        native_object_ids = _string_array(
            payload["native_report_object_ids"],
            context=f"readiness row {row_id} native report object ids",
        )
        expected_refs = (*gap_ids, *native_object_ids)
        if _string_array(
            payload["referenced_object_ids"],
            context=f"readiness row {row_id} references",
        ) != expected_refs:
            raise AffectedBlueprintReadError(
                f"readiness ledger row has incomplete references: {row_id}"
            )
        row_gaps: list[BlueprintGapRef] = []
        for gap_id in gap_ids:
            if gap_id not in objects:
                raise AffectedBlueprintReadError(
                    f"affected closure omitted ledger gap: {gap_id}"
                )
            gap = _parse_gap(gap_id, objects[gap_id])
            gaps_by_id[gap_id] = gap
            row_gaps.append(gap)
        native_reports: list[BlueprintNativeReportRef] = []
        for native_object_id in native_object_ids:
            if native_object_id not in objects:
                raise AffectedBlueprintReadError(
                    "affected closure omitted native report object: "
                    + native_object_id
                )
            native = _parse_native_report(
                native_object_id, objects[native_object_id]
            )
            identity = (native.owner_id, native.report_id)
            existing = native_by_identity.get(identity)
            if existing is not None and existing != native:
                raise AffectedBlueprintReadError(
                    "affected closure contains conflicting native report identities"
                )
            if native.report_fingerprint not in _string_array(
                payload["evidence_ids"],
                context=f"readiness row {row_id} evidence ids",
            ):
                raise AffectedBlueprintReadError(
                    f"readiness row does not consume native report evidence: {row_id}"
                )
            native_by_identity[identity] = native
            native_reports.append(native)
        try:
            rows.append(
                BlueprintLayerResult._derived(
                    layer=_string(
                        payload["layer"],
                        context=f"readiness row {row_id} layer",
                    ),
                    status=_string(
                        payload["status"],
                        context=f"readiness row {row_id} status",
                    ),
                    evidence_ids=_string_array(
                        payload["evidence_ids"],
                        context=f"readiness row {row_id} evidence ids",
                    ),
                    gap_ids=gap_ids,
                    native_reports=tuple(native_reports),
                    pre_code_status=_string(
                        payload["pre_code_status"],
                        context=f"readiness row {row_id} pre-code status",
                    ),
                    executed_evidence_status=_string(
                        payload["executed_evidence_status"],
                        context=f"readiness row {row_id} executed-evidence status",
                    ),
                    implementation_admitted=payload[
                        "implementation_admitted"
                    ],
                )
            )
        except (TypeError, ValueError) as exc:
            raise AffectedBlueprintReadError(
                f"readiness ledger row is invalid: {row_id}: {exc}"
            ) from exc

    ordered_gaps = tuple(
        gap
        for row in rows
        for gap_id in row.gap_ids
        for gap in (gaps_by_id[gap_id],)
    )
    if len({gap.gap_id for gap in ordered_gaps}) != len(ordered_gaps):
        raise AffectedBlueprintReadError(
            "affected readiness ledger reuses one gap in multiple rows"
        )
    try:
        ledger = BlueprintReadinessLedger(
            target_profile=_string(
                target["target_profile"], context="affected target profile"
            ),
            rows=tuple(rows),
            gaps=ordered_gaps,
        )
    except ValueError as exc:
        raise AffectedBlueprintReadError(
            f"affected readiness ledger is invalid: {exc}"
        ) from exc
    required_path_quality_model_ids = tuple(
        sorted(
            _string_array(
                target["required_path_quality_model_ids"],
                context="target required path-quality model ids",
            )
        )
    )
    path_quality_bindings: list[ModelPathQualityBlueprintBinding] = []
    for object_id, value in sorted(objects.items()):
        if not isinstance(value, Mapping) or value.get("kind") != "model_path_quality_binding":
            continue
        payload = dict(value)
        payload.pop("kind")
        try:
            path_quality_bindings.append(
                ModelPathQualityBlueprintBinding.from_dict(payload)
            )
        except ValueError as exc:
            raise AffectedBlueprintReadError(
                f"affected path-quality object is invalid: {object_id}: {exc}"
            ) from exc
    loaded_path_model_ids = tuple(
        row.model_element_id for row in path_quality_bindings
    )
    loaded_model_ids: set[str] = set()
    for object_id, value in objects.items():
        if not isinstance(value, Mapping):
            continue
        if value.get("kind") == "model_element":
            loaded_model_ids.add(str(object_id))
        model_element_id = value.get("model_element_id")
        if isinstance(model_element_id, str) and model_element_id:
            loaded_model_ids.add(model_element_id)
    affected_required_model_ids = set(required_path_quality_model_ids).intersection(
        {*read_result.affected_ids, *loaded_model_ids}
    )
    missing_affected_path_ids = tuple(
        sorted(affected_required_model_ids - set(loaded_path_model_ids))
    )
    duplicate_loaded_path_ids = tuple(
        sorted(
            model_id
            for model_id in set(loaded_path_model_ids)
            if loaded_path_model_ids.count(model_id) > 1
        )
    )
    unresolved_loaded_path_ids = tuple(
        sorted(
            row.model_element_id
            for row in path_quality_bindings
            if not row.ready
        )
    )
    if ledger.ok and (
        missing_affected_path_ids
        or duplicate_loaded_path_ids
        or unresolved_loaded_path_ids
    ):
        raise AffectedBlueprintReadError(
            "affected readiness ledger passes despite incomplete path-quality closure: "
            f"missing={list(missing_affected_path_ids)}, "
            f"duplicate={list(duplicate_loaded_path_ids)}, "
            f"unresolved={list(unresolved_loaded_path_ids)}"
        )
    return AffectedBlueprintUnderstanding(
        scope="affected",
        blueprint_fingerprint=index.blueprint_fingerprint,
        logical_fingerprint=index.logical_fingerprint,
        index_fingerprint=index.fingerprint,
        target_system_id=_string(
            target["target_system_id"], context="affected target system id"
        ),
        target_profile=_string(
            target["target_profile"], context="affected target profile"
        ),
        subject_revision=_string(
            target["subject_revision"], context="affected subject revision"
        ),
        descriptor_fingerprint=_string(
            target["descriptor_fingerprint"],
            context="affected descriptor fingerprint",
        ),
        layer_plan_id=_string(
            target["layer_plan_id"], context="affected layer plan id"
        ),
        layer_plan_fingerprint=_string(
            target["layer_plan_fingerprint"],
            context="affected layer plan fingerprint",
        ),
        requested_seed_ids=read_result.requested_seed_ids,
        affected_ids=read_result.affected_ids,
        propagated_affected_ids=read_result.propagated_affected_ids,
        loaded_shard_ids=read_result.shard_ids,
        loaded_object_ids=read_result.object_ids,
        layer_statuses=tuple((row.layer, row.status) for row in ledger.rows),
        status=ledger.status,
        deepest_proven_layer=ledger.deepest_proven_layer,
        first_gap=ledger.first_gap,
        gap_ids=tuple(gap.gap_id for gap in ledger.gaps),
        gap_count=ledger.gap_count,
        pre_code_status=ledger.pre_code_status,
        executed_evidence_status=ledger.executed_evidence_status,
        implementation_admitted=ledger.implementation_admitted,
        native_reports=tuple(native_by_identity.values()),
        required_path_quality_model_ids=required_path_quality_model_ids,
        path_quality_bindings=tuple(
            sorted(
                path_quality_bindings,
                key=lambda row: (
                    row.model_element_id,
                    row.compact_current_fingerprint,
                ),
            )
        ),
    )


__all__ = [
    "AFFECTED_BLUEPRINT_INDEX_SCHEMA",
    "AFFECTED_BLUEPRINT_READER_SCHEMA",
    "AFFECTED_BLUEPRINT_UNDERSTANDING_SCHEMA",
    "AFFECTED_TOPOLOGY_INVALIDATION_EDGE_SCHEMA",
    "AFFECTED_TOPOLOGY_INVALIDATION_KINDS",
    "AffectedBlueprintIndex",
    "AffectedBlueprintReadError",
    "AffectedBlueprintReadResult",
    "AffectedBlueprintReader",
    "AffectedBlueprintUnderstanding",
    "AffectedTopologyInvalidationEdge",
    "ObjectLoader",
    "ShardLoader",
    "materialize_affected_blueprint_index",
    "read_affected_blueprint",
    "read_affected_blueprint_understanding",
]
