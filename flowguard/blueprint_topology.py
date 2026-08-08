"""Typed parent/child and producer/consumer topology for target blueprints."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Any, Mapping, Sequence

from .evidence_receipts import fingerprint_value
from .hierarchy import ChildModelEvidence, ChildReattachmentContract


TOPOLOGY_DISPOSITIONS = {
    "connected",
    "intentional_leaf",
    "delegated_or_supporting",
    "scoped_out",
}
TOPOLOGY_STRUCTURAL_ROLES = {"root", "child", "peer", "external"}
TOPOLOGY_ROOT_SENTINEL = "topology-root:none"
TOPOLOGY_RELATION_KINDS = {
    "child_to_parent",
    "produces_for",
    "delegates_to",
    "supports",
    "cross_boundary_support",
    "feedback",
    "retry",
    "repair",
    "shared_resource",
    "affected_sibling",
}
TOPOLOGY_PROGRESS_KINDS = {
    "finite_bound",
    "progress_measure",
    "repair_token",
    "terminal_blocker",
    "fairness",
}
STRUCTURAL_RELATION_KINDS = {"child_to_parent", "delegates_to", "supports"}
FEEDBACK_RELATION_KINDS = {"produces_for", "feedback", "retry", "repair"}
CROSS_BOUNDARY_RELATION_KINDS = TOPOLOGY_RELATION_KINDS - STRUCTURAL_RELATION_KINDS


class BlueprintTopologyError(ValueError):
    pass


def _text(value: Any, context: str) -> str:
    text = str(value).strip()
    if not text:
        raise BlueprintTopologyError(f"{context} is required")
    return text


def _tuple(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({_text(value, "topology identity") for value in values}))


def _fingerprint_registry(
    values: Mapping[str, str],
    context: str,
) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_evidence_id, raw_fingerprint in values.items():
        evidence_id = _text(raw_evidence_id, f"{context} evidence id")
        fingerprint = _text(raw_fingerprint, f"{context} evidence fingerprint")
        if evidence_id in normalized:
            raise BlueprintTopologyError(
                f"{context} duplicates normalized evidence id {evidence_id}"
            )
        normalized[evidence_id] = fingerprint
    return normalized


def _owner_evidence_bindings(
    values: Mapping[str, Mapping[str, str]],
) -> dict[str, dict[str, str]]:
    normalized: dict[str, dict[str, str]] = {}
    for raw_owner_id, raw_binding in values.items():
        owner_id = _text(raw_owner_id, "evidence owner id")
        if owner_id in normalized:
            raise BlueprintTopologyError(
                f"evidence bindings duplicate normalized owner id {owner_id}"
            )
        if not isinstance(raw_binding, Mapping):
            raise BlueprintTopologyError(
                f"evidence binding for {owner_id} must be an id-to-fingerprint mapping"
            )
        normalized[owner_id] = _fingerprint_registry(
            raw_binding,
            f"evidence binding for {owner_id}",
        )
    return normalized


@dataclass(frozen=True)
class BlueprintTopologyPort:
    port_id: str
    schema_id: str
    schema_fingerprint: str
    required: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "port_id", _text(self.port_id, "topology port id"))
        object.__setattr__(self, "schema_id", _text(self.schema_id, "topology schema id"))
        object.__setattr__(
            self,
            "schema_fingerprint",
            _text(self.schema_fingerprint, "topology schema fingerprint"),
        )
        if not isinstance(self.required, bool):
            raise BlueprintTopologyError("topology port required flag must be boolean")

    def to_dict(self) -> dict[str, Any]:
        return {
            "port_id": self.port_id,
            "schema_id": self.schema_id,
            "schema_fingerprint": self.schema_fingerprint,
            "required": self.required,
        }


@dataclass(frozen=True)
class BlueprintTopologyPortMapping:
    producer_output_id: str
    consumer_input_id: str
    refinement_id: str = ""
    refinement_fingerprint: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "producer_output_id",
            _text(self.producer_output_id, "producer output id"),
        )
        object.__setattr__(
            self,
            "consumer_input_id",
            _text(self.consumer_input_id, "consumer input id"),
        )
        if bool(self.refinement_id) != bool(self.refinement_fingerprint):
            raise BlueprintTopologyError(
                "topology refinement id and fingerprint must be supplied together"
            )

    def to_dict(self) -> dict[str, str]:
        return {
            "producer_output_id": self.producer_output_id,
            "consumer_input_id": self.consumer_input_id,
            "refinement_id": self.refinement_id,
            "refinement_fingerprint": self.refinement_fingerprint,
        }


@dataclass(frozen=True)
class BlueprintTopologyProgressContract:
    contract_id: str
    contract_kind: str
    evidence_fingerprint: str
    finite_bound: int = 0
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "contract_id", _text(self.contract_id, "progress contract id"))
        if self.contract_kind not in TOPOLOGY_PROGRESS_KINDS:
            raise BlueprintTopologyError("unknown topology progress contract kind")
        object.__setattr__(
            self,
            "evidence_fingerprint",
            _text(self.evidence_fingerprint, "progress evidence fingerprint"),
        )
        object.__setattr__(self, "rationale", _text(self.rationale, "progress rationale"))
        if not isinstance(self.finite_bound, int) or self.finite_bound < 0:
            raise BlueprintTopologyError("topology progress finite bound is invalid")
        if self.contract_kind == "finite_bound" and self.finite_bound < 1:
            raise BlueprintTopologyError("finite-bound progress requires a positive bound")

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "contract_kind": self.contract_kind,
            "evidence_fingerprint": self.evidence_fingerprint,
            "finite_bound": self.finite_bound,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class BlueprintTopologyNode:
    node_id: str
    disposition: str
    structural_role: str
    purpose: str
    structural_parent_id: str = ""
    cross_boundary_parent_ids: tuple[str, ...] = ()
    implementation_surface_ids: tuple[str, ...] = ()
    input_ports: tuple[BlueprintTopologyPort, ...] = ()
    output_ports: tuple[BlueprintTopologyPort, ...] = ()
    state_owned: tuple[str, ...] = ()
    side_effects_owned: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", _text(self.node_id, "topology node id"))
        object.__setattr__(self, "purpose", _text(self.purpose, "topology node purpose"))
        if self.disposition not in TOPOLOGY_DISPOSITIONS:
            raise BlueprintTopologyError("unknown topology node disposition")
        if self.structural_role not in TOPOLOGY_STRUCTURAL_ROLES:
            raise BlueprintTopologyError("unknown topology structural role")
        structural_parent_id = str(self.structural_parent_id).strip()
        object.__setattr__(self, "structural_parent_id", structural_parent_id)
        normalized_cross_boundary_parents = tuple(
            sorted(
                _text(value, "cross-boundary parent id")
                for value in self.cross_boundary_parent_ids
            )
        )
        if len(normalized_cross_boundary_parents) != len(
            set(normalized_cross_boundary_parents)
        ):
            raise BlueprintTopologyError(
                "topology node duplicates a cross-boundary parent identity"
            )
        object.__setattr__(
            self,
            "cross_boundary_parent_ids",
            normalized_cross_boundary_parents,
        )
        object.__setattr__(self, "implementation_surface_ids", _tuple(self.implementation_surface_ids))
        object.__setattr__(self, "state_owned", _tuple(self.state_owned))
        object.__setattr__(self, "side_effects_owned", _tuple(self.side_effects_owned))
        for field_name in ("input_ports", "output_ports"):
            ports = tuple(sorted(getattr(self, field_name), key=lambda row: row.port_id))
            port_ids = tuple(row.port_id for row in ports)
            if len(port_ids) != len(set(port_ids)):
                raise BlueprintTopologyError(f"topology node duplicates {field_name}")
            object.__setattr__(self, field_name, ports)

    @property
    def input_by_id(self) -> dict[str, BlueprintTopologyPort]:
        return {row.port_id: row for row in self.input_ports}

    @property
    def output_by_id(self) -> dict[str, BlueprintTopologyPort]:
        return {row.port_id: row for row in self.output_ports}

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "disposition": self.disposition,
            "structural_role": self.structural_role,
            "purpose": self.purpose,
            "structural_parent_id": self.structural_parent_id,
            "cross_boundary_parent_ids": list(self.cross_boundary_parent_ids),
            "implementation_surface_ids": list(self.implementation_surface_ids),
            "input_ports": [row.to_dict() for row in self.input_ports],
            "output_ports": [row.to_dict() for row in self.output_ports],
            "state_owned": list(self.state_owned),
            "side_effects_owned": list(self.side_effects_owned),
        }


@dataclass(frozen=True)
class BlueprintTopologyRelation:
    relation_id: str
    producer_id: str
    consumer_id: str
    relation_kind: str
    interface_mappings: tuple[BlueprintTopologyPortMapping, ...]
    evidence_fingerprint: str
    rationale: str
    consumed_child_evidence_id: str = ""
    consumed_runtime_path_evidence_ids: tuple[str, ...] = ()
    progress_contract: BlueprintTopologyProgressContract | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "relation_id",
            "producer_id",
            "consumer_id",
            "evidence_fingerprint",
            "rationale",
        ):
            object.__setattr__(self, field_name, _text(getattr(self, field_name), field_name))
        if self.relation_kind not in TOPOLOGY_RELATION_KINDS:
            raise BlueprintTopologyError("unknown topology relation kind")
        mappings = tuple(
            sorted(
                self.interface_mappings,
                key=lambda row: (row.producer_output_id, row.consumer_input_id),
            )
        )
        if not mappings:
            raise BlueprintTopologyError("topology relation requires exact interface mappings")
        identities = tuple(
            (row.producer_output_id, row.consumer_input_id) for row in mappings
        )
        if len(identities) != len(set(identities)):
            raise BlueprintTopologyError("topology relation duplicates an interface mapping")
        object.__setattr__(self, "interface_mappings", mappings)
        object.__setattr__(
            self,
            "consumed_runtime_path_evidence_ids",
            _tuple(self.consumed_runtime_path_evidence_ids),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "producer_id": self.producer_id,
            "consumer_id": self.consumer_id,
            "relation_kind": self.relation_kind,
            "interface_mappings": [row.to_dict() for row in self.interface_mappings],
            "evidence_fingerprint": self.evidence_fingerprint,
            "consumed_child_evidence_id": self.consumed_child_evidence_id,
            "consumed_runtime_path_evidence_ids": list(
                self.consumed_runtime_path_evidence_ids
            ),
            "progress_contract": (
                self.progress_contract.to_dict() if self.progress_contract else None
            ),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class BlueprintTopologyFinding:
    code: str
    message: str
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _text(self.code, "topology finding code"))
        object.__setattr__(self, "message", _text(self.message, "topology finding message"))
        object.__setattr__(self, "subject_ids", _tuple(self.subject_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "subject_ids": list(self.subject_ids),
        }


@dataclass(frozen=True)
class BlueprintTopologyReport:
    topology_id: str
    root_sentinel: str
    nodes: tuple[BlueprintTopologyNode, ...]
    relations: tuple[BlueprintTopologyRelation, ...]
    findings: tuple[BlueprintTopologyFinding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings

    @cached_property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "flowguard.blueprint_topology.v3",
            "topology_id": self.topology_id,
            "root_sentinel": self.root_sentinel,
            "ok": self.ok,
            "nodes": [row.to_dict() for row in self.nodes],
            "relations": [row.to_dict() for row in self.relations],
            "findings": [row.to_dict() for row in self.findings],
        }


def _cyclic_components(
    node_ids: Sequence[str],
    relations: Sequence[BlueprintTopologyRelation],
) -> tuple[frozenset[str], ...]:
    adjacency = {node_id: set() for node_id in node_ids}
    for relation in relations:
        if relation.producer_id in adjacency and relation.consumer_id in adjacency:
            adjacency[relation.producer_id].add(relation.consumer_id)
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[frozenset[str]] = []

    def visit(node_id: str) -> None:
        nonlocal index
        indices[node_id] = index
        lowlinks[node_id] = index
        index += 1
        stack.append(node_id)
        on_stack.add(node_id)
        for child_id in adjacency[node_id]:
            if child_id not in indices:
                visit(child_id)
                lowlinks[node_id] = min(lowlinks[node_id], lowlinks[child_id])
            elif child_id in on_stack:
                lowlinks[node_id] = min(lowlinks[node_id], indices[child_id])
        if lowlinks[node_id] == indices[node_id]:
            members: set[str] = set()
            while stack:
                member = stack.pop()
                on_stack.remove(member)
                members.add(member)
                if member == node_id:
                    break
            cyclic = len(members) > 1 or any(
                relation.producer_id == node_id and relation.consumer_id == node_id
                for relation in relations
            )
            if cyclic:
                components.append(frozenset(members))

    for node_id in node_ids:
        if node_id not in indices:
            visit(node_id)
    return tuple(components)


def review_blueprint_topology(
    *,
    topology_id: str,
    nodes: Sequence[BlueprintTopologyNode],
    relations: Sequence[BlueprintTopologyRelation],
    required_owner_ids: Sequence[str],
    required_surface_ids_by_owner: Mapping[str, Sequence[str]],
    child_models: Sequence[ChildModelEvidence],
    reattachment_contracts: Sequence[ChildReattachmentContract],
    current_evidence_fingerprints: Mapping[str, str],
    declared_evidence_fingerprints_by_owner: Mapping[str, Mapping[str, str]],
    current_relation_evidence_fingerprints: Mapping[str, str],
    current_refinement_fingerprints: Mapping[str, str],
    current_progress_evidence_fingerprints: Mapping[str, str],
    root_sentinel: str = TOPOLOGY_ROOT_SENTINEL,
) -> BlueprintTopologyReport:
    ordered_nodes = tuple(sorted(nodes, key=lambda row: row.node_id))
    ordered_relations = tuple(sorted(relations, key=lambda row: row.relation_id))
    findings: list[BlueprintTopologyFinding] = []
    current_root_sentinel = _text(root_sentinel, "topology root sentinel")

    def add(code: str, message: str, *subject_ids: str) -> None:
        findings.append(BlueprintTopologyFinding(code, message, tuple(subject_ids)))

    current_evidence_by_id = _fingerprint_registry(
        current_evidence_fingerprints,
        "current evidence registry",
    )
    evidence_by_owner = _owner_evidence_bindings(
        declared_evidence_fingerprints_by_owner
    )
    owners_by_evidence_id: dict[str, set[str]] = {}
    for owner_id, binding in evidence_by_owner.items():
        for evidence_id in binding:
            owners_by_evidence_id.setdefault(evidence_id, set()).add(owner_id)
    for evidence_id, owner_ids in sorted(owners_by_evidence_id.items()):
        if len(owner_ids) > 1:
            add(
                "topology_evidence_owner_duplicated",
                "one evidence identity is declared by multiple owners",
                evidence_id,
                *sorted(owner_ids),
            )

    def validate_evidence_reference(
        *,
        evidence_id: str,
        expected_owner_id: str,
        reference_kind: str,
        source_id: str,
    ) -> None:
        normalized_evidence_id = str(evidence_id).strip()
        if not normalized_evidence_id:
            add(
                "topology_evidence_reference_missing",
                f"{reference_kind} does not declare an evidence identity",
                source_id,
                expected_owner_id,
            )
            return

        declared_fingerprint = evidence_by_owner.get(expected_owner_id, {}).get(
            normalized_evidence_id
        )
        declared_owners = owners_by_evidence_id.get(normalized_evidence_id, set())
        if declared_fingerprint is None:
            if declared_owners:
                message = (
                    f"{reference_kind} belongs to another owner instead of the exact "
                    "child owner"
                )
            else:
                message = (
                    f"{reference_kind} is not declared by the exact child owner"
                )
            add(
                "topology_evidence_owner_mismatch",
                message,
                source_id,
                expected_owner_id,
                normalized_evidence_id,
                *sorted(declared_owners),
            )

        current_fingerprint = current_evidence_by_id.get(normalized_evidence_id)
        if current_fingerprint is None:
            add(
                "topology_evidence_ghost",
                f"{reference_kind} has no entry in the current evidence registry",
                source_id,
                expected_owner_id,
                normalized_evidence_id,
            )
        elif (
            declared_fingerprint is not None
            and declared_fingerprint != current_fingerprint
        ):
            add(
                "topology_evidence_fingerprint_stale",
                f"{reference_kind} fingerprint differs from the current registry",
                source_id,
                expected_owner_id,
                normalized_evidence_id,
            )

    def add_cross_revision(
        *,
        source_id: str,
        owner_id: str,
        observed_ids: Sequence[str],
        expected_ids: Sequence[str],
        reference_kind: str,
    ) -> None:
        observed = {str(item).strip() for item in observed_ids if str(item).strip()}
        expected = {str(item).strip() for item in expected_ids if str(item).strip()}
        if observed != expected:
            add(
                "topology_evidence_cross_revision",
                f"{reference_kind} consumes a different evidence revision than the child",
                source_id,
                owner_id,
                *sorted(observed | expected),
            )

    node_ids = tuple(row.node_id for row in ordered_nodes)
    if len(node_ids) != len(set(node_ids)):
        add("duplicate_topology_node", "topology node identity is duplicated", *node_ids)
    node_by_id = {row.node_id: row for row in ordered_nodes}
    root_ids = tuple(
        row.node_id
        for row in ordered_nodes
        if row.structural_parent_id == current_root_sentinel
    )
    if len(root_ids) != 1:
        add(
            "topology_root_count_invalid",
            "topology must declare exactly one node with the current root sentinel",
            current_root_sentinel,
            *root_ids,
        )
    for node in ordered_nodes:
        structural_parent_id = node.structural_parent_id
        cross_boundary_parent_ids = set(node.cross_boundary_parent_ids)
        if not structural_parent_id:
            add(
                "topology_structural_parent_missing",
                "non-root topology node has no exact structural parent",
                node.node_id,
            )
        elif structural_parent_id == current_root_sentinel:
            if node.structural_role != "root":
                add(
                    "topology_root_role_mismatch",
                    "node using the root sentinel is not declared as the topology root",
                    node.node_id,
                    current_root_sentinel,
                )
        else:
            if node.structural_role == "root":
                add(
                    "topology_root_role_mismatch",
                    "root-role node names another topology node as its structural parent",
                    node.node_id,
                    structural_parent_id,
                )
            if structural_parent_id not in node_by_id:
                add(
                    "topology_structural_parent_foreign",
                    "topology node names a structural parent outside the current inventory",
                    node.node_id,
                    structural_parent_id,
                )
        if structural_parent_id in cross_boundary_parent_ids:
            add(
                "topology_parent_classification_overlap",
                "one parent is classified as both structural and cross-boundary",
                node.node_id,
                structural_parent_id,
            )
        for parent_id in sorted(cross_boundary_parent_ids):
            if parent_id in {node.node_id, current_root_sentinel}:
                add(
                    "topology_cross_boundary_parent_invalid",
                    "cross-boundary parent is self-referential or names the root sentinel",
                    node.node_id,
                    parent_id,
                )
            elif parent_id not in node_by_id:
                add(
                    "topology_cross_boundary_parent_foreign",
                    "cross-boundary parent is absent from the current topology inventory",
                    node.node_id,
                    parent_id,
                )
    relation_ids = tuple(row.relation_id for row in ordered_relations)
    if len(relation_ids) != len(set(relation_ids)):
        add(
            "duplicate_topology_relation",
            "topology relation identity is duplicated",
            *relation_ids,
        )

    child_ids = tuple(row.model_id for row in child_models)
    if len(child_ids) != len(set(child_ids)):
        add("duplicate_child_evidence", "child evidence identity is duplicated", *child_ids)
    child_by_id = {row.model_id: row for row in child_models}
    reattachment_ids = tuple(row.child_model_id for row in reattachment_contracts)
    if len(reattachment_ids) != len(set(reattachment_ids)):
        add(
            "duplicate_child_reattachment",
            "child reattachment identity is duplicated",
            *reattachment_ids,
        )
    reattachment_by_id = {
        row.child_model_id: row for row in reattachment_contracts
    }

    for child in child_models:
        if not child.evidence_current:
            add(
                "topology_child_evidence_declared_stale",
                "child model marks its own evidence as no longer current",
                child.model_id,
            )
        expected_evidence_ids = {
            evidence_id
            for evidence_id in (
                child.evidence_id,
                *child.validation_evidence,
                *child.runtime_path_evidence_ids,
            )
            if str(evidence_id).strip()
        }
        owner_binding = evidence_by_owner.get(child.model_id)
        if owner_binding is None:
            add(
                "topology_child_evidence_binding_missing",
                "child model has no exact evidence-id-to-fingerprint binding",
                child.model_id,
            )
        elif set(owner_binding) != expected_evidence_ids:
            add(
                "topology_child_evidence_binding_mismatch",
                "child evidence binding differs from its exact declared evidence set",
                child.model_id,
                *sorted(set(owner_binding) ^ expected_evidence_ids),
            )
        validate_evidence_reference(
            evidence_id=child.evidence_id,
            expected_owner_id=child.model_id,
            reference_kind="child model evidence",
            source_id=child.model_id,
        )
        for evidence_id in child.validation_evidence:
            validate_evidence_reference(
                evidence_id=evidence_id,
                expected_owner_id=child.model_id,
                reference_kind="child validation evidence",
                source_id=child.model_id,
            )
        for evidence_id in child.runtime_path_evidence_ids:
            validate_evidence_reference(
                evidence_id=evidence_id,
                expected_owner_id=child.model_id,
                reference_kind="child runtime-path evidence",
                source_id=child.model_id,
            )

    structural_parent_counts: dict[str, set[str]] = {}
    consumed_outputs: dict[str, set[str]] = {}
    for relation in ordered_relations:
        producer = node_by_id.get(relation.producer_id)
        consumer = node_by_id.get(relation.consumer_id)
        unknown = tuple(
            node_id
            for node_id, node in (
                (relation.producer_id, producer),
                (relation.consumer_id, consumer),
            )
            if node is None
        )
        if unknown:
            add(
                "topology_endpoint_missing",
                "producer or consumer is absent from the topology inventory",
                *unknown,
            )
        current_relation = current_relation_evidence_fingerprints.get(
            relation.relation_id
        )
        if current_relation is None:
            add(
                "topology_relation_evidence_missing",
                "relation has no current evidence identity",
                relation.relation_id,
            )
        elif current_relation != relation.evidence_fingerprint:
            add(
                "topology_relation_evidence_stale",
                "relation evidence differs from the current exact fingerprint",
                relation.relation_id,
            )
        if producer is None or consumer is None:
            continue
        for mapping in relation.interface_mappings:
            output = producer.output_by_id.get(mapping.producer_output_id)
            target_input = consumer.input_by_id.get(mapping.consumer_input_id)
            if output is None:
                add(
                    "topology_producer_output_missing",
                    "relation references an undeclared producer output",
                    relation.relation_id,
                    mapping.producer_output_id,
                )
            if target_input is None:
                add(
                    "topology_consumer_input_missing",
                    "relation references an undeclared consumer input",
                    relation.relation_id,
                    mapping.consumer_input_id,
                )
            if output is not None and target_input is not None:
                if output.schema_fingerprint != target_input.schema_fingerprint:
                    if not mapping.refinement_id:
                        add(
                            "topology_schema_mismatch",
                            "mapped port schemas differ without an exact refinement",
                            relation.relation_id,
                            mapping.producer_output_id,
                            mapping.consumer_input_id,
                        )
                    else:
                        current_refinement = current_refinement_fingerprints.get(
                            mapping.refinement_id
                        )
                        if current_refinement is None:
                            add(
                                "topology_refinement_evidence_missing",
                                "schema refinement has no current evidence",
                                mapping.refinement_id,
                            )
                        elif current_refinement != mapping.refinement_fingerprint:
                            add(
                                "topology_refinement_evidence_stale",
                                "schema refinement fingerprint is stale",
                                mapping.refinement_id,
                            )
                consumed_outputs.setdefault(relation.producer_id, set()).add(
                    mapping.producer_output_id
                )
        if relation.relation_kind in STRUCTURAL_RELATION_KINDS:
            structural_parent_counts.setdefault(relation.producer_id, set()).add(
                relation.consumer_id
            )
        if relation.relation_kind == "child_to_parent":
            child = child_by_id.get(relation.producer_id)
            if child is None:
                add(
                    "topology_child_evidence_missing",
                    "child-to-parent relation has no child model evidence",
                    relation.producer_id,
                )
                continue
            if not child.evidence_current or relation.consumed_child_evidence_id != child.evidence_id:
                add(
                    "topology_child_evidence_stale",
                    "relation does not consume the exact current child evidence",
                    relation.relation_id,
                    relation.producer_id,
                )
            add_cross_revision(
                source_id=relation.relation_id,
                owner_id=child.model_id,
                observed_ids=(relation.consumed_child_evidence_id,),
                expected_ids=(child.evidence_id,),
                reference_kind="relation child evidence",
            )
            validate_evidence_reference(
                evidence_id=relation.consumed_child_evidence_id,
                expected_owner_id=child.model_id,
                reference_kind="relation-consumed child evidence",
                source_id=relation.relation_id,
            )
            if set(relation.consumed_runtime_path_evidence_ids) != set(
                child.runtime_path_evidence_ids
            ):
                add(
                    "topology_runtime_evidence_stale",
                    "relation runtime-path evidence differs from the current child evidence",
                    relation.relation_id,
                    relation.producer_id,
                )
            add_cross_revision(
                source_id=relation.relation_id,
                owner_id=child.model_id,
                observed_ids=relation.consumed_runtime_path_evidence_ids,
                expected_ids=child.runtime_path_evidence_ids,
                reference_kind="relation runtime-path evidence",
            )
            for evidence_id in relation.consumed_runtime_path_evidence_ids:
                validate_evidence_reference(
                    evidence_id=evidence_id,
                    expected_owner_id=child.model_id,
                    reference_kind="relation-consumed runtime-path evidence",
                    source_id=relation.relation_id,
                )
            reattachment = reattachment_by_id.get(relation.producer_id)
            if reattachment is None:
                add(
                    "topology_child_reattachment_missing",
                    "child-to-parent relation has no exact reattachment contract",
                    relation.producer_id,
                )
                continue
            reattachment_source_id = f"reattachment:{reattachment.child_model_id}"
            add_cross_revision(
                source_id=reattachment_source_id,
                owner_id=child.model_id,
                observed_ids=(reattachment.consumed_evidence_id,),
                expected_ids=(child.evidence_id,),
                reference_kind="reattachment child evidence",
            )
            validate_evidence_reference(
                evidence_id=reattachment.consumed_evidence_id,
                expected_owner_id=child.model_id,
                reference_kind="reattachment-consumed child evidence",
                source_id=reattachment_source_id,
            )
            add_cross_revision(
                source_id=reattachment_source_id,
                owner_id=child.model_id,
                observed_ids=reattachment.consumed_runtime_path_evidence_ids,
                expected_ids=child.runtime_path_evidence_ids,
                reference_kind="reattachment runtime-path evidence",
            )
            for evidence_id in reattachment.consumed_runtime_path_evidence_ids:
                validate_evidence_reference(
                    evidence_id=evidence_id,
                    expected_owner_id=child.model_id,
                    reference_kind="reattachment-consumed runtime-path evidence",
                    source_id=reattachment_source_id,
                )
            exact_checks = (
                (reattachment.consumed_evidence_id, child.evidence_id),
                (
                    set(reattachment.consumed_runtime_path_evidence_ids),
                    set(child.runtime_path_evidence_ids),
                ),
                (set(reattachment.expected_state_owned), set(child.state_owned)),
                (
                    set(reattachment.expected_side_effects_owned),
                    set(child.side_effects_owned),
                ),
                (set(reattachment.expected_contracts_out), set(child.contracts_out)),
            )
            if any(observed != expected for observed, expected in exact_checks):
                add(
                    "topology_child_reattachment_stale",
                    "child reattachment contract differs from current child evidence",
                    relation.producer_id,
                )
            expected_inputs = set(reattachment.expected_inputs)
            child_inputs = set(child.inputs_accepted)
            expected_outputs = set(reattachment.expected_outputs)
            child_outputs = set(child.outputs_emitted)
            if (
                (not reattachment.allow_extra_inputs and expected_inputs != child_inputs)
                or (reattachment.allow_extra_inputs and not expected_inputs.issubset(child_inputs))
                or (not reattachment.allow_extra_outputs and expected_outputs != child_outputs)
                or (reattachment.allow_extra_outputs and not expected_outputs.issubset(child_outputs))
            ):
                add(
                    "topology_child_reattachment_stale",
                    "child input/output reattachment differs from current child evidence",
                    relation.producer_id,
                )
            if (
                set(producer.input_by_id) != child_inputs
                or set(producer.output_by_id) != child_outputs
                or set(producer.state_owned) != set(child.state_owned)
                or set(producer.side_effects_owned) != set(child.side_effects_owned)
            ):
                add(
                    "topology_child_node_contract_mismatch",
                    "topology node differs from the current child contract",
                    relation.producer_id,
                )

    for child_id, parents in structural_parent_counts.items():
        if len(parents) > 1:
            add(
                "topology_multiple_structural_parents",
                "one structural child is attached to multiple parents",
                child_id,
                *parents,
            )
    structural_relations_by_child: dict[str, set[str]] = {}
    cross_boundary_relations_by_child: dict[str, set[str]] = {}
    for relation in ordered_relations:
        if relation.relation_kind in STRUCTURAL_RELATION_KINDS:
            structural_relations_by_child.setdefault(relation.producer_id, set()).add(
                relation.consumer_id
            )
        elif relation.relation_kind in CROSS_BOUNDARY_RELATION_KINDS:
            cross_boundary_relations_by_child.setdefault(
                relation.producer_id, set()
            ).add(relation.consumer_id)
    for node in ordered_nodes:
        declared_parent = node.structural_parent_id
        relation_parents = structural_relations_by_child.get(node.node_id, set())
        if declared_parent == current_root_sentinel:
            if relation_parents:
                add(
                    "topology_root_has_structural_parent",
                    "topology root also emits a structural parent relation",
                    node.node_id,
                    *sorted(relation_parents),
                )
        elif declared_parent:
            if not relation_parents:
                add(
                    "topology_structural_relation_missing",
                    "declared structural parent has no matching typed structural relation",
                    node.node_id,
                    declared_parent,
                )
            elif relation_parents != {declared_parent}:
                add(
                    "topology_structural_parent_mismatch",
                    "typed structural relation set differs from the node's exact parent",
                    node.node_id,
                    declared_parent,
                    *sorted(relation_parents),
                )
        missing_cross_boundary_relations = set(
            node.cross_boundary_parent_ids
        ) - cross_boundary_relations_by_child.get(node.node_id, set())
        if missing_cross_boundary_relations:
            add(
                "topology_cross_boundary_relation_missing",
                "declared cross-boundary parent has no matching typed relation",
                node.node_id,
                *sorted(missing_cross_boundary_relations),
            )
    for child_id, child in child_by_id.items():
        unconsumed = set(child.outputs_emitted) - consumed_outputs.get(child_id, set())
        if unconsumed:
            add(
                "topology_child_output_unconsumed",
                "required child output is not reattached to a consumer input",
                child_id,
                *sorted(unconsumed),
            )

    required_owners = {str(item) for item in required_owner_ids}
    missing_owners = tuple(sorted(required_owners - set(node_by_id)))
    if missing_owners:
        add(
            "topology_owner_missing",
            "declared behavior owners are absent from the topology",
            *missing_owners,
        )
    connected_ids = {
        node_id
        for relation in ordered_relations
        for node_id in (relation.producer_id, relation.consumer_id)
    }
    for owner_id in sorted(required_owners & set(node_by_id)):
        node = node_by_id[owner_id]
        if set(node.implementation_surface_ids) != set(
            required_surface_ids_by_owner.get(owner_id, ())
        ):
            add(
                "topology_surface_binding_mismatch",
                "topology owner does not bind its exact implementation surface set",
                owner_id,
            )
        if node.disposition != "intentional_leaf" and owner_id not in connected_ids:
            add(
                "topology_owner_disconnected",
                "non-leaf owner has no parent or consumer interface relation",
                owner_id,
            )

    structural_relations = tuple(
        row for row in ordered_relations if row.relation_kind in STRUCTURAL_RELATION_KINDS
    )
    for component in _cyclic_components(node_ids, structural_relations):
        add(
            "topology_structural_cycle",
            "structural parent/delegation relations contain a cycle",
            *sorted(component),
        )

    for node in ordered_nodes:
        if not node.structural_parent_id:
            continue
        visited: set[str] = set()
        cursor = node
        while cursor.structural_parent_id != current_root_sentinel:
            if cursor.node_id in visited:
                break
            visited.add(cursor.node_id)
            parent = node_by_id.get(cursor.structural_parent_id)
            if parent is None:
                break
            cursor = parent
        else:
            continue
        if cursor.node_id not in visited:
            add(
                "topology_structural_unreachable",
                "topology node does not reach the sole declared structural root",
                node.node_id,
            )

    feedback_relations = tuple(
        row
        for row in ordered_relations
        if row.relation_kind in FEEDBACK_RELATION_KINDS
    )
    for component in _cyclic_components(node_ids, feedback_relations):
        internal = tuple(
            row
            for row in feedback_relations
            if row.producer_id in component and row.consumer_id in component
        )
        for relation in internal:
            progress = relation.progress_contract
            if progress is None:
                add(
                    "topology_feedback_progress_missing",
                    "feedback relation in a cycle has no progress contract",
                    relation.relation_id,
                )
                continue
            current_progress = current_progress_evidence_fingerprints.get(
                progress.contract_id
            )
            if current_progress is None:
                add(
                    "topology_feedback_progress_missing",
                    "feedback progress contract has no current evidence",
                    relation.relation_id,
                    progress.contract_id,
                )
            elif current_progress != progress.evidence_fingerprint:
                add(
                    "topology_feedback_progress_stale",
                    "feedback progress evidence is stale",
                    relation.relation_id,
                    progress.contract_id,
                )

    unique = {
        (row.code, row.message, row.subject_ids): row for row in findings
    }
    ordered_findings = tuple(unique[key] for key in sorted(unique))
    return BlueprintTopologyReport(
        topology_id=_text(topology_id, "topology id"),
        root_sentinel=current_root_sentinel,
        nodes=ordered_nodes,
        relations=ordered_relations,
        findings=ordered_findings,
    )


__all__ = [
    "BlueprintTopologyError",
    "BlueprintTopologyFinding",
    "BlueprintTopologyNode",
    "BlueprintTopologyPort",
    "BlueprintTopologyPortMapping",
    "BlueprintTopologyProgressContract",
    "BlueprintTopologyRelation",
    "BlueprintTopologyReport",
    "CROSS_BOUNDARY_RELATION_KINDS",
    "FEEDBACK_RELATION_KINDS",
    "STRUCTURAL_RELATION_KINDS",
    "TOPOLOGY_ROOT_SENTINEL",
    "review_blueprint_topology",
]
