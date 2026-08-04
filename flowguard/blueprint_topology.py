"""Exact parent/child and producer/consumer topology for target blueprints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .evidence_receipts import fingerprint_value


TOPOLOGY_DISPOSITIONS = {
    "connected",
    "intentional_leaf",
    "delegated_or_supporting",
    "scoped_out",
}


class BlueprintTopologyError(ValueError):
    pass


def _tuple(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


@dataclass(frozen=True)
class BlueprintTopologyNode:
    node_id: str
    disposition: str
    purpose: str
    implementation_surface_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.node_id or not self.purpose.strip():
            raise BlueprintTopologyError("topology node identity and purpose are required")
        if self.disposition not in TOPOLOGY_DISPOSITIONS:
            raise BlueprintTopologyError("unknown topology node disposition")
        object.__setattr__(
            self, "implementation_surface_ids", _tuple(self.implementation_surface_ids)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "disposition": self.disposition,
            "purpose": self.purpose,
            "implementation_surface_ids": list(self.implementation_surface_ids),
        }


@dataclass(frozen=True)
class BlueprintTopologyRelation:
    relation_id: str
    producer_id: str
    consumer_id: str
    relation_kind: str
    interface_mappings: tuple[tuple[str, str], ...]
    evidence_fingerprint: str
    rationale: str

    def __post_init__(self) -> None:
        if not all(
            (
                self.relation_id,
                self.producer_id,
                self.consumer_id,
                self.relation_kind,
                self.evidence_fingerprint,
                self.rationale.strip(),
            )
        ):
            raise BlueprintTopologyError("topology relation identity is incomplete")
        if self.relation_kind not in {
            "child_to_parent",
            "produces_for",
            "delegates_to",
            "supports",
        }:
            raise BlueprintTopologyError("unknown topology relation kind")
        mappings = tuple(
            sorted((str(output_id), str(input_id)) for output_id, input_id in self.interface_mappings)
        )
        if not mappings or any(not output_id or not input_id for output_id, input_id in mappings):
            raise BlueprintTopologyError(
                "topology relation requires exact producer-output to consumer-input mappings"
            )
        if len(mappings) != len(set(mappings)):
            raise BlueprintTopologyError("topology relation duplicates an interface mapping")
        object.__setattr__(self, "interface_mappings", mappings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "producer_id": self.producer_id,
            "consumer_id": self.consumer_id,
            "relation_kind": self.relation_kind,
            "interface_mappings": [
                {"producer_output_id": output_id, "consumer_input_id": input_id}
                for output_id, input_id in self.interface_mappings
            ],
            "evidence_fingerprint": self.evidence_fingerprint,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class BlueprintTopologyFinding:
    code: str
    message: str
    subject_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "subject_ids": list(self.subject_ids),
        }


@dataclass(frozen=True)
class BlueprintTopologyReport:
    topology_id: str
    nodes: tuple[BlueprintTopologyNode, ...]
    relations: tuple[BlueprintTopologyRelation, ...]
    findings: tuple[BlueprintTopologyFinding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "flowguard.blueprint_topology.v1",
            "topology_id": self.topology_id,
            "ok": self.ok,
            "nodes": [row.to_dict() for row in self.nodes],
            "relations": [row.to_dict() for row in self.relations],
            "findings": [row.to_dict() for row in self.findings],
        }


def review_blueprint_topology(
    *,
    topology_id: str,
    nodes: Sequence[BlueprintTopologyNode],
    relations: Sequence[BlueprintTopologyRelation],
    required_owner_ids: Sequence[str],
    required_surface_ids_by_owner: Mapping[str, Sequence[str]],
) -> BlueprintTopologyReport:
    ordered_nodes = tuple(sorted(nodes, key=lambda row: row.node_id))
    ordered_relations = tuple(sorted(relations, key=lambda row: row.relation_id))
    findings: list[BlueprintTopologyFinding] = []
    node_ids = tuple(row.node_id for row in ordered_nodes)
    if len(node_ids) != len(set(node_ids)):
        findings.append(
            BlueprintTopologyFinding(
                "duplicate_topology_node", "topology node identity is duplicated", node_ids
            )
        )
    node_by_id = {row.node_id: row for row in ordered_nodes}
    relation_ids = tuple(row.relation_id for row in ordered_relations)
    if len(relation_ids) != len(set(relation_ids)):
        findings.append(
            BlueprintTopologyFinding(
                "duplicate_topology_relation",
                "topology relation identity is duplicated",
                relation_ids,
            )
        )
    for relation in ordered_relations:
        unknown = tuple(
            node_id
            for node_id in (relation.producer_id, relation.consumer_id)
            if node_id not in node_by_id
        )
        if unknown:
            findings.append(
                BlueprintTopologyFinding(
                    "topology_endpoint_missing",
                    "producer or consumer is absent from the topology inventory",
                    unknown,
                )
            )
    required_owners = {str(item) for item in required_owner_ids}
    missing_owners = tuple(sorted(required_owners - set(node_by_id)))
    if missing_owners:
        findings.append(
            BlueprintTopologyFinding(
                "topology_owner_missing",
                "declared behavior owners are absent from the topology",
                missing_owners,
            )
        )
    connected_ids = {
        node_id
        for relation in ordered_relations
        for node_id in (relation.producer_id, relation.consumer_id)
    }
    for owner_id in sorted(required_owners & set(node_by_id)):
        node = node_by_id[owner_id]
        expected_surfaces = set(required_surface_ids_by_owner.get(owner_id, ()))
        if set(node.implementation_surface_ids) != expected_surfaces:
            findings.append(
                BlueprintTopologyFinding(
                    "topology_surface_binding_mismatch",
                    "topology owner does not bind its exact implementation surface set",
                    (owner_id,),
                )
            )
        if node.disposition != "intentional_leaf" and owner_id not in connected_ids:
            findings.append(
                BlueprintTopologyFinding(
                    "topology_owner_disconnected",
                    "non-leaf owner has no parent or consumer interface relation",
                    (owner_id,),
                )
            )
    return BlueprintTopologyReport(
        topology_id=str(topology_id),
        nodes=ordered_nodes,
        relations=ordered_relations,
        findings=tuple(findings),
    )


__all__ = [
    "BlueprintTopologyError",
    "BlueprintTopologyFinding",
    "BlueprintTopologyNode",
    "BlueprintTopologyRelation",
    "BlueprintTopologyReport",
    "review_blueprint_topology",
]
