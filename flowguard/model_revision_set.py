"""Atomic model-system revision, activation, and rollback contracts."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping

from .model_authority import (
    LIFECYCLE_ACTIVE,
    MODEL_ACTIVATION_RECEIPT_SCHEMA,
    MODEL_PREDICTION_REPLAY_REF_SCHEMA,
    MODEL_REVISION_MEMBER_SCHEMA,
    MODEL_ROLLBACK_EFFECT_SCHEMA,
    REVISION_ACCEPTED,
    REVISION_EVIDENCE_PASS,
    REVISION_EVIDENCE_REQUIRED,
    REVISION_OPERATIONS,
    REVISION_PROPOSED,
    REVISION_STATUSES,
    ROLLBACK_EFFECT_DISPOSITIONS,
    ROLLBACK_RESULT_COMPENSATED,
    ROLLBACK_RESULT_EXACT,
    ROLLBACK_RESULT_FORWARD_REPAIR,
    ROLLBACK_RESULTS,
    SUBJECT_OBSERVED_IMPLEMENTATION,
    AuthorityEndpointRef,
    ModelAuthorityError,
    ModelAuthorityHead,
    ModelRelation,
    ModelSystemSnapshot,
    _array,
    _id,
    _ids,
    _sha,
    _shas,
    _strict,
    _text,
    canonical_fingerprint,
)
from .model_intent import (
    ModelIntentContribution,
    ModelIntentDisposition,
    ModelIntentReview,
    model_intent_inventory_fingerprint,
    review_model_intent_inventory,
)
from .model_intent_authority import (
    CurrentEffectiveIntentView,
    _strict_model_intent_contribution,
    _strict_model_intent_disposition,
    validate_current_effective_intent_view,
)
from .model_path_quality import (
    PathQualityResult,
    PathQualitySubject,
    normalize_path_quality_material,
    path_quality_result_set_fingerprint,
)
from ._wire import (
    wire_boolean as _wire_boolean,
    wire_integer as _wire_integer,
    wire_string as _wire_string,
    wire_strings as _wire_strings,
)

MODEL_REVISION_EVIDENCE_CURRENT_SCHEMA = "flowguard.model_revision_evidence.v2"
MODEL_REVISION_SET_CURRENT_SCHEMA = "flowguard.model_revision_set.v5"
MODEL_ROLLBACK_CONTRACT_CURRENT_SCHEMA = "flowguard.model_rollback_contract.v2"
MODEL_ROLLBACK_RECEIPT_CURRENT_SCHEMA = "flowguard.model_rollback_receipt.v2"
REVISION_REMOVAL_DISPOSITION_SCHEMA = (
    "flowguard.revision_removal_disposition.v1"
)
REVISION_REMOVAL_DISPOSITIONS = frozenset(
    {"replace", "retire", "migrate", "scope_out"}
)


def _wire_pair(
    value: Any,
    field_name: str,
    first_name: str,
    second_name: str,
) -> tuple[str, str]:
    data = _strict(value, field_name, (first_name, second_name))
    return (
        _wire_string(data[first_name], f"{field_name} {first_name}"),
        _wire_string(data[second_name], f"{field_name} {second_name}"),
    )


@dataclass(frozen=True)
class RevisionEvidenceRef:
    receipt_id: str
    receipt_fingerprint: str
    owner_route: str
    subject_fingerprint: str
    obligation_ids: tuple[str, ...]
    affected_closure_fingerprint: str
    covered_affected_ids: tuple[str, ...]
    candidate_snapshot_fingerprint: str
    toolchain_fingerprint: str
    environment_fingerprint: str
    status: str
    current: bool
    eligible: bool
    schema: str = MODEL_REVISION_EVIDENCE_CURRENT_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_id", _id(self.receipt_id, "receipt_id"))
        object.__setattr__(
            self,
            "receipt_fingerprint",
            _sha(self.receipt_fingerprint, "receipt_fingerprint"),
        )
        object.__setattr__(
            self,
            "owner_route",
            _id(self.owner_route, "owner_route"),
        )
        object.__setattr__(
            self,
            "subject_fingerprint",
            _sha(self.subject_fingerprint, "subject_fingerprint"),
        )
        object.__setattr__(
            self,
            "obligation_ids",
            _ids(self.obligation_ids, "obligation_id"),
        )
        if not self.obligation_ids:
            raise ModelAuthorityError(
                "revision evidence requires obligation ids"
            )
        for name in (
            "affected_closure_fingerprint",
            "candidate_snapshot_fingerprint",
            "toolchain_fingerprint",
            "environment_fingerprint",
        ):
            object.__setattr__(self, name, _sha(getattr(self, name), name))
        object.__setattr__(
            self,
            "covered_affected_ids",
            _ids(self.covered_affected_ids, "covered_affected_id"),
        )
        if not self.covered_affected_ids:
            raise ModelAuthorityError(
                "revision evidence requires explicit affected-closure coverage"
            )
        if self.status not in {
            REVISION_EVIDENCE_REQUIRED,
            REVISION_EVIDENCE_PASS,
        }:
            raise ModelAuthorityError(
                f"unsupported revision evidence status: {self.status}"
            )
        if not isinstance(self.current, bool) or not isinstance(
            self.eligible, bool
        ):
            raise ModelAuthorityError(
                "revision evidence current and eligible must be booleans"
            )
        if self.schema != MODEL_REVISION_EVIDENCE_CURRENT_SCHEMA:
            raise ModelAuthorityError(
                "revision evidence schema must be "
                f"{MODEL_REVISION_EVIDENCE_CURRENT_SCHEMA}"
            )

    @property
    def identity_key(self) -> tuple[Any, ...]:
        return (
            self.receipt_id,
            self.receipt_fingerprint,
            self.owner_route,
            self.subject_fingerprint,
            self.obligation_ids,
            self.affected_closure_fingerprint,
            self.covered_affected_ids,
            self.candidate_snapshot_fingerprint,
            self.toolchain_fingerprint,
            self.environment_fingerprint,
        )

    @property
    def passing(self) -> bool:
        return (
            self.status == REVISION_EVIDENCE_PASS
            and self.current
            and self.eligible
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "receipt_id": self.receipt_id,
            "receipt_fingerprint": self.receipt_fingerprint,
            "owner_route": self.owner_route,
            "subject_fingerprint": self.subject_fingerprint,
            "obligation_ids": list(self.obligation_ids),
            "affected_closure_fingerprint": (
                self.affected_closure_fingerprint
            ),
            "covered_affected_ids": list(self.covered_affected_ids),
            "candidate_snapshot_fingerprint": (
                self.candidate_snapshot_fingerprint
            ),
            "toolchain_fingerprint": self.toolchain_fingerprint,
            "environment_fingerprint": self.environment_fingerprint,
            "status": self.status,
            "current": self.current,
            "eligible": self.eligible,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "RevisionEvidenceRef":
        data = _strict(
            value,
            "revision_evidence",
            (
                "schema",
                "receipt_id",
                "receipt_fingerprint",
                "owner_route",
                "subject_fingerprint",
                "obligation_ids",
                "affected_closure_fingerprint",
                "covered_affected_ids",
                "candidate_snapshot_fingerprint",
                "toolchain_fingerprint",
                "environment_fingerprint",
                "status",
                "current",
                "eligible",
            ),
        )
        return cls(
            receipt_id=_wire_string(data["receipt_id"], "revision receipt_id"),
            receipt_fingerprint=_wire_string(
                data["receipt_fingerprint"], "revision receipt_fingerprint"
            ),
            owner_route=_wire_string(data["owner_route"], "revision owner_route"),
            subject_fingerprint=_wire_string(
                data["subject_fingerprint"], "revision subject_fingerprint"
            ),
            obligation_ids=_wire_strings(data["obligation_ids"], "obligation_ids"),
            affected_closure_fingerprint=_wire_string(
                data["affected_closure_fingerprint"],
                "affected_closure_fingerprint",
            ),
            covered_affected_ids=_wire_strings(
                data["covered_affected_ids"], "covered_affected_ids"
            ),
            candidate_snapshot_fingerprint=_wire_string(
                data["candidate_snapshot_fingerprint"],
                "candidate_snapshot_fingerprint",
            ),
            toolchain_fingerprint=_wire_string(
                data["toolchain_fingerprint"], "toolchain_fingerprint"
            ),
            environment_fingerprint=_wire_string(
                data["environment_fingerprint"], "environment_fingerprint"
            ),
            status=_wire_string(data["status"], "revision evidence status"),
            current=_wire_boolean(data["current"], "revision evidence current"),
            eligible=_wire_boolean(data["eligible"], "revision evidence eligible"),
            schema=_wire_string(data["schema"], "revision evidence schema"),
        )


@dataclass(frozen=True)
class PredictionReplayRef:
    replay_id: str
    replay_fingerprint: str
    prediction_id: str
    prediction_fingerprint: str
    observation_boundary_id: str
    candidate_instance_fingerprint: str
    status: str
    schema: str = MODEL_PREDICTION_REPLAY_REF_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "replay_id", _id(self.replay_id, "replay_id"))
        object.__setattr__(
            self,
            "prediction_id",
            _id(self.prediction_id, "prediction_id"),
        )
        object.__setattr__(
            self,
            "observation_boundary_id",
            _id(self.observation_boundary_id, "observation_boundary_id"),
        )
        for name in (
            "replay_fingerprint",
            "prediction_fingerprint",
            "candidate_instance_fingerprint",
        ):
            object.__setattr__(self, name, _sha(getattr(self, name), name))
        if self.status != "pass":
            raise ModelAuthorityError(
                "revision-set replay bindings must be terminal pass evidence"
            )
        if self.schema != MODEL_PREDICTION_REPLAY_REF_SCHEMA:
            raise ModelAuthorityError(
                f"prediction replay schema must be {MODEL_PREDICTION_REPLAY_REF_SCHEMA}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "replay_id": self.replay_id,
            "replay_fingerprint": self.replay_fingerprint,
            "prediction_id": self.prediction_id,
            "prediction_fingerprint": self.prediction_fingerprint,
            "observation_boundary_id": self.observation_boundary_id,
            "candidate_instance_fingerprint": (
                self.candidate_instance_fingerprint
            ),
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "PredictionReplayRef":
        data = _strict(
            value,
            "prediction_replay_ref",
            (
                "schema",
                "replay_id",
                "replay_fingerprint",
                "prediction_id",
                "prediction_fingerprint",
                "observation_boundary_id",
                "candidate_instance_fingerprint",
                "status",
            ),
        )
        return cls(
            replay_id=_wire_string(data["replay_id"], "replay_id"),
            replay_fingerprint=_wire_string(
                data["replay_fingerprint"], "replay_fingerprint"
            ),
            prediction_id=_wire_string(data["prediction_id"], "prediction_id"),
            prediction_fingerprint=_wire_string(
                data["prediction_fingerprint"], "prediction_fingerprint"
            ),
            observation_boundary_id=_wire_string(
                data["observation_boundary_id"], "observation_boundary_id"
            ),
            candidate_instance_fingerprint=_wire_string(
                data["candidate_instance_fingerprint"],
                "candidate_instance_fingerprint",
            ),
            status=_wire_string(data["status"], "prediction replay status"),
            schema=_wire_string(data["schema"], "prediction replay schema"),
        )


@dataclass(frozen=True)
class RevisionMemberChange:
    member_id: str
    operation: str
    base_instance_fingerprint: str
    candidate_instance_fingerprint: str
    changed_element_ids: tuple[str, ...]
    schema: str = MODEL_REVISION_MEMBER_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "member_id", _id(self.member_id, "member_id"))
        if self.operation not in REVISION_OPERATIONS:
            raise ModelAuthorityError(
                f"unsupported revision member operation: {self.operation}"
            )
        if self.operation != "add":
            object.__setattr__(
                self,
                "base_instance_fingerprint",
                _sha(
                    self.base_instance_fingerprint,
                    "base_instance_fingerprint",
                ),
            )
        elif self.base_instance_fingerprint:
            raise ModelAuthorityError("add member cannot name a base instance")
        if self.operation != "remove":
            object.__setattr__(
                self,
                "candidate_instance_fingerprint",
                _sha(
                    self.candidate_instance_fingerprint,
                    "candidate_instance_fingerprint",
                ),
            )
        elif self.candidate_instance_fingerprint:
            raise ModelAuthorityError(
                "remove member cannot name a candidate instance"
            )
        if (
            self.operation == "replace"
            and self.base_instance_fingerprint
            == self.candidate_instance_fingerprint
        ):
            raise ModelAuthorityError(
                "replace member must change the instance fingerprint"
            )
        object.__setattr__(
            self,
            "changed_element_ids",
            _ids(self.changed_element_ids, "changed_element_id"),
        )
        if not self.changed_element_ids:
            raise ModelAuthorityError(
                "revision member requires changed element ids"
            )
        if self.schema != MODEL_REVISION_MEMBER_SCHEMA:
            raise ModelAuthorityError(
                f"revision member schema must be {MODEL_REVISION_MEMBER_SCHEMA}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "member_id": self.member_id,
            "operation": self.operation,
            "base_instance_fingerprint": self.base_instance_fingerprint,
            "candidate_instance_fingerprint": (
                self.candidate_instance_fingerprint
            ),
            "changed_element_ids": list(self.changed_element_ids),
        }

    @classmethod
    def from_dict(cls, value: Any) -> "RevisionMemberChange":
        data = _strict(
            value,
            "revision_member",
            (
                "schema",
                "member_id",
                "operation",
                "base_instance_fingerprint",
                "candidate_instance_fingerprint",
                "changed_element_ids",
            ),
        )
        return cls(
            member_id=_wire_string(data["member_id"], "revision member_id"),
            operation=_wire_string(data["operation"], "revision operation"),
            base_instance_fingerprint=_wire_string(
                data["base_instance_fingerprint"], "base_instance_fingerprint"
            ),
            candidate_instance_fingerprint=_wire_string(
                data["candidate_instance_fingerprint"],
                "candidate_instance_fingerprint",
            ),
            changed_element_ids=_wire_strings(
                data["changed_element_ids"], "changed_element_ids"
            ),
            schema=_wire_string(data["schema"], "revision member schema"),
        )


def _endpoint_closure_id(endpoint: AuthorityEndpointRef) -> str:
    return f"{endpoint.endpoint_kind}:{endpoint.endpoint_id}"


def _model_endpoint_id(model_id: str) -> str:
    return f"model_instance:model:{model_id}"


_MODEL_MESH_AFFECTED_ID_PREFIXES = (
    "root:model:",
    "model_relation:",
    "coverage:",
    "unresolved_gap:",
    "system_property:",
)


def _native_owner_route_for_affected_id(
    affected_id: str,
    endpoint_routes: Mapping[str, str],
) -> str:
    """Resolve one affected identity without a generic owner fallback.

    Endpoint identities carry their native route in the model-system snapshot.
    The five canonical revision-accounting categories below are the explicit
    model-topology responsibility of ModelMesh.  Any later category must be
    classified deliberately before it can enter an affected closure.
    """

    endpoint_route = endpoint_routes.get(affected_id)
    if endpoint_route is not None:
        return endpoint_route
    if affected_id.startswith(_MODEL_MESH_AFFECTED_ID_PREFIXES):
        return "model_mesh_maintenance"
    raise ModelAuthorityError(
        f"affected id has no native owner route: {affected_id}"
    )


@dataclass(frozen=True)
class RevisionSnapshotDiff:
    """Complete independently derived canonical base-to-candidate diff."""

    members: tuple[RevisionMemberChange, ...]
    changed_root_ids: tuple[str, ...]
    changed_relation_ids: tuple[str, ...]
    changed_source_surface_ids: tuple[str, ...]
    changed_commitment_ids: tuple[str, ...]
    changed_field_ids: tuple[str, ...]
    changed_side_effect_ids: tuple[str, ...]
    changed_contract_ids: tuple[str, ...]
    changed_test_ids: tuple[str, ...]
    changed_system_property_ids: tuple[str, ...]
    changed_coverage_ids: tuple[str, ...]
    changed_gap_ids: tuple[str, ...]
    changed_owner_artifact_ids: tuple[str, ...]
    added_ids: tuple[str, ...]
    removed_ids: tuple[str, ...]
    fingerprint_changed_ids: tuple[str, ...]

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "members": [item.to_dict() for item in self.members],
            "changed_root_ids": list(self.changed_root_ids),
            "changed_relation_ids": list(self.changed_relation_ids),
            "changed_source_surface_ids": list(
                self.changed_source_surface_ids
            ),
            "changed_commitment_ids": list(self.changed_commitment_ids),
            "changed_field_ids": list(self.changed_field_ids),
            "changed_side_effect_ids": list(self.changed_side_effect_ids),
            "changed_contract_ids": list(self.changed_contract_ids),
            "changed_test_ids": list(self.changed_test_ids),
            "changed_system_property_ids": list(
                self.changed_system_property_ids
            ),
            "changed_coverage_ids": list(self.changed_coverage_ids),
            "changed_gap_ids": list(self.changed_gap_ids),
            "changed_owner_artifact_ids": list(
                self.changed_owner_artifact_ids
            ),
            "added_ids": list(self.added_ids),
            "removed_ids": list(self.removed_ids),
            "fingerprint_changed_ids": list(
                self.fingerprint_changed_ids
            ),
        }


@dataclass(frozen=True)
class RevisionAffectedClosure:
    """Deterministic fixed-point slice and its exact typed edge basis."""

    affected_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    owner_bindings: tuple[tuple[str, str], ...]

    @property
    def fingerprint(self) -> str:
        return derive_affected_closure_fingerprint(
            affected_closure_ids=self.affected_ids,
            affected_edge_ids=self.edge_ids,
            affected_owner_bindings=self.owner_bindings,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "affected_ids": list(self.affected_ids),
            "edge_ids": list(self.edge_ids),
            "owner_bindings": [
                {"affected_id": affected_id, "owner_route": owner_route}
                for affected_id, owner_route in self.owner_bindings
            ],
            "fingerprint": self.fingerprint,
        }


def _coverage_rows(snapshot: ModelSystemSnapshot) -> dict[str, Mapping[str, bool]]:
    rows: dict[str, Mapping[str, bool]] = {}
    for dimension in snapshot.coverage.dimensions:
        all_ids = set(dimension.required_ids)
        all_ids.update(dimension.covered_ids)
        all_ids.update(dimension.excluded_ids)
        all_ids.update(dimension.unresolved_ids)
        for item_id in all_ids:
            rows[f"coverage:{dimension.dimension_id}:{item_id}"] = {
                "required": item_id in dimension.required_ids,
                "covered": item_id in dimension.covered_ids,
                "excluded": item_id in dimension.excluded_ids,
                "unresolved": item_id in dimension.unresolved_ids,
            }
    rows["coverage:universe"] = {
        "boundary": snapshot.coverage.boundary_id,
        "source_inventory": snapshot.coverage.source_inventory_fingerprint,
        "claim_boundary": snapshot.coverage.claim_boundary,
    }
    return rows


def derive_revision_snapshot_diff(
    base_snapshot: ModelSystemSnapshot,
    candidate_snapshot: ModelSystemSnapshot,
) -> RevisionSnapshotDiff:
    """Derive every governed canonical difference before caller assertions."""

    if base_snapshot.system_id != candidate_snapshot.system_id:
        raise ModelAuthorityError("revision snapshots belong to different systems")
    base_models = {
        item.logical_model_id: item for item in base_snapshot.model_instances
    }
    candidate_models = {
        item.logical_model_id: item
        for item in candidate_snapshot.model_instances
    }
    members: list[RevisionMemberChange] = []
    for model_id in sorted(set(base_models) | set(candidate_models)):
        base = base_models.get(model_id)
        candidate = candidate_models.get(model_id)
        if base is None:
            operation = "add"
        elif candidate is None:
            operation = "remove"
        elif base.fingerprint != candidate.fingerprint:
            operation = "replace"
        else:
            continue
        members.append(
            RevisionMemberChange(
                member_id=model_id,
                operation=operation,
                base_instance_fingerprint=base.fingerprint if base else "",
                candidate_instance_fingerprint=(
                    candidate.fingerprint if candidate else ""
                ),
                changed_element_ids=(_model_endpoint_id(model_id),),
            )
        )

    def root_rows(snapshot: ModelSystemSnapshot) -> dict[str, str]:
        model_by_fingerprint = {
            item.fingerprint: item.logical_model_id
            for item in snapshot.model_instances
        }
        return {
            f"root:model:{model_by_fingerprint[fingerprint]}": fingerprint
            for fingerprint in snapshot.root_instance_fingerprints
        }

    base_roots = root_rows(base_snapshot)
    candidate_roots = root_rows(candidate_snapshot)
    changed_roots = tuple(
        sorted(
            row_id
            for row_id in set(base_roots) | set(candidate_roots)
            if base_roots.get(row_id) != candidate_roots.get(row_id)
        )
    )
    base_relations = {
        item.relation_id: item.to_dict()
        for item in base_snapshot.relations
    }
    candidate_relations = {
        item.relation_id: item.to_dict()
        for item in candidate_snapshot.relations
    }
    changed_relations = tuple(
        sorted(
            relation_id
            for relation_id in set(base_relations) | set(candidate_relations)
            if base_relations.get(relation_id)
            != candidate_relations.get(relation_id)
        )
    )
    base_owners = {
        (item.endpoint_kind, item.endpoint_id): item.to_dict()
        for item in base_snapshot.owner_artifact_refs
    }
    candidate_owners = {
        (item.endpoint_kind, item.endpoint_id): item.to_dict()
        for item in candidate_snapshot.owner_artifact_refs
    }
    changed_owner_keys = tuple(
        sorted(
            key
            for key in set(base_owners) | set(candidate_owners)
            if base_owners.get(key) != candidate_owners.get(key)
        )
    )

    def changed_owner_ids(*endpoint_kinds: str) -> tuple[str, ...]:
        kinds = set(endpoint_kinds)
        return tuple(
            endpoint_id
            for endpoint_kind, endpoint_id in changed_owner_keys
            if endpoint_kind in kinds
        )

    base_coverage = _coverage_rows(base_snapshot)
    candidate_coverage = _coverage_rows(candidate_snapshot)
    changed_coverage = tuple(
        sorted(
            row_id
            for row_id in set(base_coverage) | set(candidate_coverage)
            if base_coverage.get(row_id) != candidate_coverage.get(row_id)
        )
    )
    changed_gaps = tuple(
        sorted(
            set(base_snapshot.unresolved_gap_ids)
            ^ set(candidate_snapshot.unresolved_gap_ids)
        )
    )
    system_fields = (
        "system_id",
        "subject_lane",
        "lifecycle",
        "subject_revision",
        "claim_boundary",
    )
    changed_system_properties = {
        f"system_property:{field_name}"
        for field_name in system_fields
        if getattr(base_snapshot, field_name)
        != getattr(candidate_snapshot, field_name)
    }
    base_entities: dict[str, Any] = {
        _model_endpoint_id(model_id): item.to_dict()
        for model_id, item in base_models.items()
    }
    candidate_entities: dict[str, Any] = {
        _model_endpoint_id(model_id): item.to_dict()
        for model_id, item in candidate_models.items()
    }
    base_entities.update(
        {
            f"root:model:{model_id}": fingerprint
            for model_id, fingerprint in (
                (row_id.split("root:model:", 1)[1], fingerprint)
                for row_id, fingerprint in base_roots.items()
            )
        }
    )
    candidate_entities.update(
        {
            f"root:model:{model_id}": fingerprint
            for model_id, fingerprint in (
                (row_id.split("root:model:", 1)[1], fingerprint)
                for row_id, fingerprint in candidate_roots.items()
            )
        }
    )
    base_entities.update(
        {
            f"model_relation:{relation_id}": payload
            for relation_id, payload in base_relations.items()
        }
    )
    candidate_entities.update(
        {
            f"model_relation:{relation_id}": payload
            for relation_id, payload in candidate_relations.items()
        }
    )
    base_entities.update(
        {
            f"{endpoint_kind}:{endpoint_id}": payload
            for (endpoint_kind, endpoint_id), payload in base_owners.items()
        }
    )
    candidate_entities.update(
        {
            f"{endpoint_kind}:{endpoint_id}": payload
            for (endpoint_kind, endpoint_id), payload in candidate_owners.items()
        }
    )
    base_entities.update(base_coverage)
    candidate_entities.update(candidate_coverage)
    base_entities.update(
        {
            f"unresolved_gap:{gap_id}": True
            for gap_id in base_snapshot.unresolved_gap_ids
        }
    )
    candidate_entities.update(
        {
            f"unresolved_gap:{gap_id}": True
            for gap_id in candidate_snapshot.unresolved_gap_ids
        }
    )
    added_ids = tuple(
        sorted(set(candidate_entities) - set(base_entities))
    )
    removed_ids = tuple(
        sorted(set(base_entities) - set(candidate_entities))
    )
    fingerprint_changed_ids = tuple(
        sorted(
            entity_id
            for entity_id in set(base_entities) & set(candidate_entities)
            if base_entities[entity_id] != candidate_entities[entity_id]
        )
    )
    return RevisionSnapshotDiff(
        members=tuple(members),
        changed_root_ids=changed_roots,
        changed_relation_ids=changed_relations,
        changed_source_surface_ids=changed_owner_ids("external_surface"),
        changed_commitment_ids=changed_owner_ids("behavior_commitment"),
        changed_field_ids=changed_owner_ids("field_inventory"),
        changed_side_effect_ids=changed_owner_ids(
            "side_effect_inventory"
        ),
        changed_contract_ids=changed_owner_ids("code_contract"),
        changed_test_ids=changed_owner_ids("test_evidence"),
        changed_system_property_ids=tuple(
            sorted(changed_system_properties)
        ),
        changed_coverage_ids=changed_coverage,
        changed_gap_ids=changed_gaps,
        changed_owner_artifact_ids=tuple(
            f"{endpoint_kind}:{endpoint_id}"
            for endpoint_kind, endpoint_id in changed_owner_keys
        ),
        added_ids=added_ids,
        removed_ids=removed_ids,
        fingerprint_changed_ids=fingerprint_changed_ids,
    )


def derive_revision_affected_closure(
    base_snapshot: ModelSystemSnapshot,
    candidate_snapshot: ModelSystemSnapshot,
    diff: RevisionSnapshotDiff | None = None,
) -> RevisionAffectedClosure:
    """Close the exact diff over typed relations without parent sibling fanout."""

    current_diff = diff or derive_revision_snapshot_diff(
        base_snapshot,
        candidate_snapshot,
    )
    base_models = {
        item.logical_model_id: item for item in base_snapshot.model_instances
    }
    candidate_models = {
        item.logical_model_id: item
        for item in candidate_snapshot.model_instances
    }
    affected_endpoint_ids = {
        _model_endpoint_id(item.member_id) for item in current_diff.members
    }
    affected_ids = set(affected_endpoint_ids)
    affected_ids.update(current_diff.changed_root_ids)
    affected_ids.update(
        f"model_relation:{item}" for item in current_diff.changed_relation_ids
    )
    affected_ids.update(current_diff.changed_coverage_ids)
    affected_ids.update(
        f"unresolved_gap:{item}" for item in current_diff.changed_gap_ids
    )
    affected_ids.update(current_diff.changed_system_property_ids)
    affected_ids.update(current_diff.changed_owner_artifact_ids)

    def relation_identity(relation: ModelRelation) -> tuple[Any, ...]:
        return (
            relation.relation_id,
            relation.kind,
            relation.source.endpoint_kind,
            relation.source.endpoint_id,
            relation.target.endpoint_kind,
            relation.target.endpoint_id,
        )

    relation_map: dict[tuple[Any, ...], ModelRelation] = {}
    for relation in (*base_snapshot.relations, *candidate_snapshot.relations):
        relation_map[relation_identity(relation)] = relation
    relations = tuple(
        relation_map[key] for key in sorted(relation_map)
    )
    endpoint_routes: dict[str, str] = {}
    for relation in relations:
        for endpoint in (relation.source, relation.target):
            endpoint_routes[_endpoint_closure_id(endpoint)] = (
                "model_test_alignment"
                if endpoint.endpoint_kind == "model_instance"
                else endpoint.owner_route
            )
    changed_relation_ids = set(current_diff.changed_relation_ids)
    edge_ids: set[str] = set()
    for relation in relations:
        if relation.relation_id in changed_relation_ids:
            affected_endpoint_ids.add(
                _endpoint_closure_id(relation.source)
            )
            affected_endpoint_ids.add(
                _endpoint_closure_id(relation.target)
            )
            edge_ids.add(f"model_relation:{relation.relation_id}")

    owner_lookup: dict[tuple[str, str], AuthorityEndpointRef] = {}
    for owner in (
        *base_snapshot.owner_artifact_refs,
        *candidate_snapshot.owner_artifact_refs,
    ):
        owner_lookup[(owner.endpoint_kind, owner.endpoint_id)] = owner
        endpoint_routes[_endpoint_closure_id(owner)] = owner.owner_route
    for model_id in set(base_models) | set(candidate_models):
        endpoint_routes[_model_endpoint_id(model_id)] = (
            "model_test_alignment"
        )
    for owner_key in owner_lookup:
        typed_id = f"{owner_key[0]}:{owner_key[1]}"
        if typed_id in current_diff.changed_owner_artifact_ids:
            affected_endpoint_ids.add(typed_id)

    root_models = {
        item_id.split("root:model:", 1)[1]
        for item_id in current_diff.changed_root_ids
    }
    for model_id in root_models:
        if model_id in base_models or model_id in candidate_models:
            affected_endpoint_ids.add(_model_endpoint_id(model_id))

    bidirectional = {
        "realizes",
        "supersedes",
        "validates",
        "shares_kernel_with",
    }
    reverse_only = {
        "contains",
        "refines",
        "depends_on",
        "delegates_to",
        "consumes",
    }
    forward_only = {"produces_for"}
    changed = True
    while changed:
        changed = False
        for relation in relations:
            source_id = _endpoint_closure_id(relation.source)
            target_id = _endpoint_closure_id(relation.target)
            transfers: tuple[tuple[str, str], ...]
            if relation.kind in bidirectional:
                transfers = ((source_id, target_id), (target_id, source_id))
            elif relation.kind in reverse_only:
                transfers = ((target_id, source_id),)
            elif relation.kind in forward_only:
                transfers = ((source_id, target_id),)
            else:
                transfers = ()
            for trigger_id, reached_id in transfers:
                if (
                    trigger_id in affected_endpoint_ids
                    and reached_id not in affected_endpoint_ids
                ):
                    affected_endpoint_ids.add(reached_id)
                    edge_ids.add(f"model_relation:{relation.relation_id}")
                    changed = True
    affected_ids.update(affected_endpoint_ids)
    affected_ids.update(edge_ids)
    owner_bindings = []
    for affected_id in sorted(affected_ids):
        owner_bindings.append(
            (
                affected_id,
                _native_owner_route_for_affected_id(
                    affected_id,
                    endpoint_routes,
                ),
            )
        )
    return RevisionAffectedClosure(
        affected_ids=tuple(sorted(affected_ids)),
        edge_ids=tuple(sorted(edge_ids)),
        owner_bindings=tuple(owner_bindings),
    )


def _normalize_owner_bindings(
    values: Iterable[tuple[str, str]],
) -> tuple[tuple[str, str], ...]:
    result = tuple(
        sorted(
            (
                _id(affected_id, "affected_owner_id"),
                _id(owner_route, "affected_owner_route"),
            )
            for affected_id, owner_route in values
        )
    )
    ids = tuple(item[0] for item in result)
    if len(ids) != len(set(ids)):
        raise ModelAuthorityError(
            "affected owner bindings require one native owner per id"
        )
    return result


@dataclass(frozen=True)
class RevisionRemovalDisposition:
    removed_id: str
    disposition: str
    reason: str
    replacement_id: str = ""
    schema: str = REVISION_REMOVAL_DISPOSITION_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "removed_id",
            _id(self.removed_id, "removed_id"),
        )
        if self.disposition not in REVISION_REMOVAL_DISPOSITIONS:
            raise ModelAuthorityError(
                f"unsupported removal disposition: {self.disposition}"
            )
        object.__setattr__(
            self,
            "reason",
            _text(self.reason, "removal disposition reason", minimum=20),
        )
        if self.disposition in {"replace", "migrate"}:
            object.__setattr__(
                self,
                "replacement_id",
                _id(self.replacement_id, "replacement_id"),
            )
        elif self.replacement_id:
            raise ModelAuthorityError(
                "retire or scope_out disposition cannot name a replacement"
            )
        if self.schema != REVISION_REMOVAL_DISPOSITION_SCHEMA:
            raise ModelAuthorityError(
                "removal disposition schema must be "
                f"{REVISION_REMOVAL_DISPOSITION_SCHEMA}"
            )

    def to_dict(self) -> dict[str, str]:
        return {
            "schema": self.schema,
            "removed_id": self.removed_id,
            "disposition": self.disposition,
            "reason": self.reason,
            "replacement_id": self.replacement_id,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "RevisionRemovalDisposition":
        data = _strict(
            value,
            "revision_removal_disposition",
            (
                "schema",
                "removed_id",
                "disposition",
                "reason",
                "replacement_id",
            ),
        )
        return cls(
            removed_id=_wire_string(data["removed_id"], "removed_id"),
            disposition=_wire_string(
                data["disposition"], "removal disposition"
            ),
            reason=_wire_string(data["reason"], "removal reason"),
            replacement_id=_wire_string(data["replacement_id"], "replacement_id"),
            schema=_wire_string(data["schema"], "removal disposition schema"),
        )


@dataclass(frozen=True)
class ModelRevisionSet:
    revision_set_id: str
    task_id: str
    expected_head_fingerprint: str
    base_snapshot_fingerprint: str
    candidate_snapshot_fingerprint: str
    members: tuple[RevisionMemberChange, ...]
    affected_closure_ids: tuple[str, ...]
    affected_closure_fingerprint: str
    affected_edge_ids: tuple[str, ...]
    affected_owner_bindings: tuple[tuple[str, str], ...]
    snapshot_diff_fingerprint: str
    changed_root_ids: tuple[str, ...] = ()
    changed_relation_ids: tuple[str, ...] = ()
    changed_source_surface_ids: tuple[str, ...] = ()
    changed_commitment_ids: tuple[str, ...] = ()
    changed_field_ids: tuple[str, ...] = ()
    changed_side_effect_ids: tuple[str, ...] = ()
    changed_contract_ids: tuple[str, ...] = ()
    changed_test_ids: tuple[str, ...] = ()
    changed_system_property_ids: tuple[str, ...] = ()
    changed_coverage_ids: tuple[str, ...] = ()
    changed_gap_ids: tuple[str, ...] = ()
    changed_owner_artifact_ids: tuple[str, ...] = ()
    added_ids: tuple[str, ...] = ()
    removed_ids: tuple[str, ...] = ()
    fingerprint_changed_ids: tuple[str, ...] = ()
    removal_dispositions: tuple[RevisionRemovalDisposition, ...] = ()
    required_evidence_refs: tuple[RevisionEvidenceRef, ...] = ()
    completed_evidence_refs: tuple[RevisionEvidenceRef, ...] = ()
    prediction_replay_refs: tuple[PredictionReplayRef, ...] = ()
    required_path_quality_model_ids: tuple[str, ...] = ()
    path_quality_subjects: tuple[PathQualitySubject, ...] = ()
    path_quality_results: tuple[PathQualityResult, ...] = ()
    path_quality_result_set_fingerprint: str = ""
    intent_contributions: tuple[ModelIntentContribution, ...] = ()
    intent_dispositions: tuple[ModelIntentDisposition, ...] = ()
    current_effective_intent_view: CurrentEffectiveIntentView | None = None
    intent_contribution_inventory_fingerprint: str = ""
    intent_conflict_ids: tuple[str, ...] = ()
    intent_unresolved_ids: tuple[str, ...] = ()
    no_declared_intent_rationale_id: str = ""
    no_declared_intent_evidence_fingerprints: tuple[tuple[str, str], ...] = ()
    no_declared_intent_rationale: str = ""
    implementation_bundle_fingerprint: str = ""
    rollback_contract_fingerprint: str = ""
    originating_revision_set_fingerprint: str = ""
    originating_activation_receipt_fingerprint: str = ""
    status: str = REVISION_PROPOSED
    decision_reason: str = ""
    schema: str = MODEL_REVISION_SET_CURRENT_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "revision_set_id",
            _id(self.revision_set_id, "revision_set_id"),
        )
        object.__setattr__(self, "task_id", _id(self.task_id, "task_id"))
        for name in (
            "expected_head_fingerprint",
            "base_snapshot_fingerprint",
            "candidate_snapshot_fingerprint",
        ):
            object.__setattr__(self, name, _sha(getattr(self, name), name))
        if (
            self.base_snapshot_fingerprint
            == self.candidate_snapshot_fingerprint
        ):
            raise ModelAuthorityError(
                "revision candidate snapshot must differ from base"
            )
        members = tuple(sorted(self.members, key=lambda item: item.member_id))
        member_ids = tuple(item.member_id for item in members)
        if len(member_ids) != len(set(member_ids)):
            raise ModelAuthorityError("revision member ids must be unique")
        object.__setattr__(self, "members", members)
        for name in (
            "affected_closure_ids",
            "affected_edge_ids",
            "changed_root_ids",
            "changed_relation_ids",
            "changed_source_surface_ids",
            "changed_commitment_ids",
            "changed_field_ids",
            "changed_side_effect_ids",
            "changed_contract_ids",
            "changed_test_ids",
            "changed_system_property_ids",
            "changed_coverage_ids",
            "changed_gap_ids",
            "changed_owner_artifact_ids",
            "added_ids",
            "removed_ids",
            "fingerprint_changed_ids",
        ):
            object.__setattr__(self, name, _ids(getattr(self, name), name))
        if not self.members and not any(
            (
                self.changed_root_ids,
                self.changed_relation_ids,
                self.changed_source_surface_ids,
                self.changed_commitment_ids,
                self.changed_field_ids,
                self.changed_side_effect_ids,
                self.changed_contract_ids,
                self.changed_test_ids,
                self.changed_system_property_ids,
                self.changed_coverage_ids,
                self.changed_gap_ids,
                self.changed_owner_artifact_ids,
                self.added_ids,
                self.removed_ids,
                self.fingerprint_changed_ids,
            )
        ):
            raise ModelAuthorityError(
                "revision set requires an independently observable change"
            )
        dispositions = tuple(
            sorted(
                self.removal_dispositions,
                key=lambda item: item.removed_id,
            )
        )
        if any(
            not isinstance(item, RevisionRemovalDisposition)
            for item in dispositions
        ):
            raise ModelAuthorityError(
                "removal dispositions must be typed current records"
            )
        disposition_ids = tuple(item.removed_id for item in dispositions)
        if len(disposition_ids) != len(set(disposition_ids)):
            raise ModelAuthorityError(
                "removal dispositions must identify unique removed ids"
            )
        disposition_required = tuple(
            item_id
            for item_id in self.removed_ids
            if not item_id.startswith("unresolved_gap:")
        )
        if disposition_ids != disposition_required:
            raise ModelAuthorityError(
                "every removed governed id requires one exact disposition"
            )
        object.__setattr__(
            self,
            "removal_dispositions",
            dispositions,
        )
        if not self.affected_closure_ids:
            raise ModelAuthorityError(
                "revision set requires an affected closure"
            )
        object.__setattr__(
            self,
            "affected_closure_fingerprint",
            _sha(
                self.affected_closure_fingerprint,
                "affected_closure_fingerprint",
            ),
        )
        owner_bindings = _normalize_owner_bindings(
            self.affected_owner_bindings
        )
        if tuple(item[0] for item in owner_bindings) != self.affected_closure_ids:
            raise ModelAuthorityError(
                "affected owner bindings must cover the closure exactly"
            )
        object.__setattr__(
            self,
            "affected_owner_bindings",
            owner_bindings,
        )
        object.__setattr__(
            self,
            "snapshot_diff_fingerprint",
            _sha(
                self.snapshot_diff_fingerprint,
                "snapshot_diff_fingerprint",
            ),
        )
        required = tuple(
            sorted(self.required_evidence_refs, key=lambda item: item.identity_key)
        )
        completed = tuple(
            sorted(self.completed_evidence_refs, key=lambda item: item.identity_key)
        )
        if any(not isinstance(item, RevisionEvidenceRef) for item in required + completed):
            raise ModelAuthorityError(
                "revision evidence refs must be RevisionEvidenceRef"
            )
        if any(item.status != REVISION_EVIDENCE_REQUIRED for item in required):
            raise ModelAuthorityError(
                "required revision evidence refs must use required status"
            )
        allowed_subjects = {
            self.candidate_snapshot_fingerprint,
            *(
                item.candidate_instance_fingerprint
                for item in members
                if item.candidate_instance_fingerprint
            ),
        }
        if any(item.subject_fingerprint not in allowed_subjects for item in required + completed):
            raise ModelAuthorityError(
                "revision evidence subject is not bound to the candidate snapshot or member"
            )
        for item in required + completed:
            if (
                item.affected_closure_fingerprint
                != self.affected_closure_fingerprint
            ):
                raise ModelAuthorityError(
                    "revision evidence affected closure fingerprint mismatch"
                )
            if (
                item.candidate_snapshot_fingerprint
                != self.candidate_snapshot_fingerprint
            ):
                raise ModelAuthorityError(
                    "revision evidence candidate snapshot mismatch"
                )
            native_owners = dict(self.affected_owner_bindings)
            if any(
                native_owners[affected_id] != item.owner_route
                for affected_id in item.covered_affected_ids
            ):
                raise ModelAuthorityError(
                    "revision evidence covered id does not match its native owner"
                )
        required_keys = tuple(item.identity_key for item in required)
        completed_keys = tuple(item.identity_key for item in completed)
        if len(required_keys) != len(set(required_keys)):
            raise ModelAuthorityError("required revision evidence must be unique")
        if len(completed_keys) != len(set(completed_keys)):
            raise ModelAuthorityError("completed revision evidence must be unique")
        affected_ids_by_owner: dict[str, tuple[str, ...]] = {}
        for affected_id, owner_route in owner_bindings:
            affected_ids_by_owner.setdefault(owner_route, ())
            affected_ids_by_owner[owner_route] = tuple(
                sorted((*affected_ids_by_owner[owner_route], affected_id))
            )

        def validate_leaf_receipt_ownership(
            refs: tuple[RevisionEvidenceRef, ...],
            label: str,
        ) -> None:
            owner_routes = tuple(item.owner_route for item in refs)
            if len(owner_routes) != len(set(owner_routes)):
                raise ModelAuthorityError(
                    f"{label} revision evidence requires one merged reference "
                    "per native owner"
                )
            receipt_ids = tuple(item.receipt_id for item in refs)
            receipt_fingerprints = tuple(
                item.receipt_fingerprint for item in refs
            )
            if len(receipt_ids) != len(set(receipt_ids)) or len(
                receipt_fingerprints
            ) != len(set(receipt_fingerprints)):
                raise ModelAuthorityError(
                    f"{label} revision evidence leaf receipt cannot be reused "
                    "across native owners"
                )
            for item in refs:
                if item.covered_affected_ids != affected_ids_by_owner.get(
                    item.owner_route, ()
                ):
                    raise ModelAuthorityError(
                        f"{label} revision evidence must use one merged reference "
                        "covering the native owner's exact affected ids"
                    )

        validate_leaf_receipt_ownership(required, "required")
        validate_leaf_receipt_ownership(completed, "completed")
        object.__setattr__(self, "required_evidence_refs", required)
        object.__setattr__(self, "completed_evidence_refs", completed)
        replay_refs = tuple(
            sorted(self.prediction_replay_refs, key=lambda item: item.replay_id)
        )
        if any(not isinstance(item, PredictionReplayRef) for item in replay_refs):
            raise ModelAuthorityError(
                "prediction replay refs must be PredictionReplayRef"
            )
        replay_ids = tuple(item.replay_id for item in replay_refs)
        if len(replay_ids) != len(set(replay_ids)):
            raise ModelAuthorityError("prediction replay ids must be unique")
        if any(
            item.candidate_instance_fingerprint not in allowed_subjects
            for item in replay_refs
        ):
            raise ModelAuthorityError(
                "prediction replay is not bound to a candidate member"
            )
        object.__setattr__(self, "prediction_replay_refs", replay_refs)
        if not isinstance(
            self.current_effective_intent_view,
            CurrentEffectiveIntentView,
        ):
            raise ModelAuthorityError(
                "current revision schema requires one typed current effective intent view"
            )
        if (
            self.current_effective_intent_view.candidate_snapshot_fingerprint
            != self.candidate_snapshot_fingerprint
        ):
            raise ModelAuthorityError(
                "current effective intent view candidate fingerprint mismatch"
            )
        current_candidate_model_ids = tuple(
            sorted(
                binding.logical_model_id
                for binding in self.current_effective_intent_view.owner_bindings
            )
        )
        minimum_path_quality_model_ids = tuple(
            sorted(
                item.member_id
                for item in members
                if item.operation in {"add", "replace"}
            )
        )
        try:
            (
                required_path_quality_model_ids,
                path_quality_subjects,
                path_quality_results,
            ) = normalize_path_quality_material(
                self.required_path_quality_model_ids,
                self.path_quality_subjects,
                self.path_quality_results,
            )
        except ValueError as exc:
            raise ModelAuthorityError(
                f"invalid revision path-quality material: {exc}"
            ) from exc
        explicit_material = bool(path_quality_subjects or path_quality_results)
        subject_model_ids = tuple(
            subject.model_id for subject in path_quality_subjects
        )
        if explicit_material:
            if (
                required_path_quality_model_ids
                and required_path_quality_model_ids != subject_model_ids
            ):
                raise ModelAuthorityError(
                    "explicit revision path-quality denominator must equal its "
                    "subject model ids"
                )
            required_path_quality_model_ids = subject_model_ids
        else:
            if (
                required_path_quality_model_ids
                and required_path_quality_model_ids
                != minimum_path_quality_model_ids
            ):
                raise ModelAuthorityError(
                    "revision without path-quality material must use the added "
                    "or replaced model denominator"
                )
            required_path_quality_model_ids = minimum_path_quality_model_ids
        missing_required_path_quality_model_ids = tuple(
            sorted(
                set(minimum_path_quality_model_ids)
                - set(required_path_quality_model_ids)
            )
        )
        if missing_required_path_quality_model_ids:
            raise ModelAuthorityError(
                "revision path-quality denominator omits added or replaced "
                "model members: "
                + ", ".join(missing_required_path_quality_model_ids)
            )
        foreign_path_quality_model_ids = tuple(
            sorted(
                set(required_path_quality_model_ids)
                - set(current_candidate_model_ids)
            )
        )
        if foreign_path_quality_model_ids:
            raise ModelAuthorityError(
                "revision path-quality denominator contains models outside "
                "the current candidate intent-owner denominator: "
                + ", ".join(foreign_path_quality_model_ids)
            )
        expected_path_quality_fingerprint = path_quality_result_set_fingerprint(
            required_path_quality_model_ids,
            path_quality_subjects,
            path_quality_results,
        )
        supplied_path_quality_fingerprint = str(
            self.path_quality_result_set_fingerprint or ""
        )
        if (
            supplied_path_quality_fingerprint
            and supplied_path_quality_fingerprint
            != expected_path_quality_fingerprint
        ):
            raise ModelAuthorityError(
                "revision path-quality result-set fingerprint is stale or foreign"
            )
        candidate_members = {
            item.member_id: item
            for item in members
            if item.operation in {"add", "replace"}
        }
        subjects_by_fingerprint = {
            subject.fingerprint: subject for subject in path_quality_subjects
        }
        for subject in path_quality_subjects:
            member = candidate_members.get(subject.model_id)
            if member is not None and (
                subject.model_fingerprint
                != member.candidate_instance_fingerprint
            ):
                raise ModelAuthorityError(
                    "revision path-quality subject is not bound to its exact "
                    f"candidate member: {subject.model_id}"
                )
            if subject.currentness_id != self.candidate_snapshot_fingerprint:
                raise ModelAuthorityError(
                    "revision path-quality subject currentness must equal the "
                    f"candidate snapshot: {subject.model_id}"
                )
        for result in path_quality_results:
            subject = subjects_by_fingerprint.get(result.subject_fingerprint)
            if subject is None:
                raise ModelAuthorityError(
                    "revision path-quality result does not participate in its "
                    "explicit subject denominator"
                )
            if (
                not result.current
                or result.currentness_id
                != self.candidate_snapshot_fingerprint
                or result.currentness_id != subject.currentness_id
            ):
                raise ModelAuthorityError(
                    "revision path-quality result is not current for its exact "
                    f"candidate subject: {subject.model_id}"
                )
        object.__setattr__(
            self,
            "required_path_quality_model_ids",
            required_path_quality_model_ids,
        )
        object.__setattr__(self, "path_quality_subjects", path_quality_subjects)
        object.__setattr__(self, "path_quality_results", path_quality_results)
        object.__setattr__(
            self,
            "path_quality_result_set_fingerprint",
            expected_path_quality_fingerprint,
        )
        intent_contributions = tuple(
            sorted(
                self.intent_contributions,
                key=lambda item: item.contribution_id,
            )
        )
        intent_dispositions = tuple(
            sorted(
                self.intent_dispositions,
                key=lambda item: item.contribution_id,
            )
        )
        if any(
            not isinstance(item, ModelIntentContribution)
            for item in intent_contributions
        ) or any(
            not isinstance(item, ModelIntentDisposition)
            for item in intent_dispositions
        ):
            raise ModelAuthorityError(
                "revision intent inventory requires typed current records"
            )
        object.__setattr__(
            self,
            "intent_contributions",
            intent_contributions,
        )
        object.__setattr__(
            self,
            "intent_dispositions",
            intent_dispositions,
        )
        known_external_contribution_ids = tuple(
            item.prior_contribution_id
            for item in self.current_effective_intent_view.transitions
            if item.action == "supersede"
        )
        intent_review = review_model_intent_inventory(
            intent_contributions,
            intent_dispositions,
            changed_model_ids=self._intent_expressible_changed_model_ids(),
            changed_gap_ids=self.changed_gap_ids,
            enforce_changed_targets=True,
            known_external_contribution_ids=known_external_contribution_ids,
        )
        expected_intent_fingerprint = model_intent_inventory_fingerprint(
            intent_contributions,
            intent_dispositions,
        )
        if self.intent_contribution_inventory_fingerprint:
            supplied_intent_fingerprint = _sha(
                self.intent_contribution_inventory_fingerprint,
                "intent_contribution_inventory_fingerprint",
            )
            if supplied_intent_fingerprint != expected_intent_fingerprint:
                raise ModelAuthorityError(
                    "stale intent contribution inventory fingerprint"
                )
        object.__setattr__(
            self,
            "intent_contribution_inventory_fingerprint",
            expected_intent_fingerprint,
        )
        supplied_conflict_ids = _ids(
            self.intent_conflict_ids,
            "intent_conflict_id",
        )
        if supplied_conflict_ids and supplied_conflict_ids != intent_review.conflict_ids:
            raise ModelAuthorityError("stale revision intent conflict ids")
        supplied_unresolved_ids = _ids(
            self.intent_unresolved_ids,
            "intent_unresolved_id",
        )
        if (
            supplied_unresolved_ids
            and supplied_unresolved_ids != intent_review.unresolved_ids
        ):
            raise ModelAuthorityError("stale revision intent unresolved ids")
        object.__setattr__(
            self,
            "intent_conflict_ids",
            intent_review.conflict_ids,
        )
        object.__setattr__(
            self,
            "intent_unresolved_ids",
            intent_review.unresolved_ids,
        )
        no_intent_id = str(self.no_declared_intent_rationale_id or "").strip()
        no_intent_rationale = str(self.no_declared_intent_rationale or "").strip()
        no_intent_evidence: list[tuple[str, str]] = []
        seen_no_intent_roles: set[str] = set()
        for role, fingerprint in self.no_declared_intent_evidence_fingerprints:
            normalized_role = _id(role, "no_declared_intent_evidence_role")
            if normalized_role in seen_no_intent_roles:
                raise ModelAuthorityError(
                    "no-declared-intent evidence roles must be unique"
                )
            seen_no_intent_roles.add(normalized_role)
            no_intent_evidence.append(
                (
                    normalized_role,
                    _sha(
                        fingerprint,
                        "no_declared_intent_evidence_fingerprint",
                    ),
                )
            )
        no_intent_evidence.sort()
        supplied_no_intent = bool(
            no_intent_id or no_intent_rationale or no_intent_evidence
        )
        if supplied_no_intent and not (
            no_intent_id and no_intent_rationale and no_intent_evidence
        ):
            raise ModelAuthorityError(
                "no-declared-intent rationale requires identity, evidence, and rationale"
            )
        if intent_contributions and supplied_no_intent:
            raise ModelAuthorityError(
                "intent contributions and no-declared-intent rationale are exclusive"
            )
        object.__setattr__(
            self,
            "no_declared_intent_rationale_id",
            no_intent_id,
        )
        object.__setattr__(
            self,
            "no_declared_intent_evidence_fingerprints",
            tuple(no_intent_evidence),
        )
        object.__setattr__(
            self,
            "no_declared_intent_rationale",
            no_intent_rationale,
        )
        for name in (
            "implementation_bundle_fingerprint",
            "rollback_contract_fingerprint",
            "originating_revision_set_fingerprint",
            "originating_activation_receipt_fingerprint",
        ):
            if getattr(self, name):
                object.__setattr__(
                    self,
                    name,
                    _sha(getattr(self, name), name),
                )
        origin_fields = (
            self.originating_revision_set_fingerprint,
            self.originating_activation_receipt_fingerprint,
        )
        if any(origin_fields) != all(origin_fields):
            raise ModelAuthorityError(
                "reverse revision origin identities must be complete"
            )
        if self.rollback_contract_fingerprint and not all(origin_fields):
            raise ModelAuthorityError(
                "rollback revision requires originating revision and activation"
            )
        if self.status not in REVISION_STATUSES:
            raise ModelAuthorityError(
                f"unsupported revision-set status: {self.status}"
            )
        object.__setattr__(
            self,
            "decision_reason",
            str(self.decision_reason or "").strip(),
        )
        if self.status == REVISION_ACCEPTED and not self.evidence_complete:
            raise ModelAuthorityError(
                "accepted revision set requires exact evidence closure"
            )
        if self.status == REVISION_ACCEPTED and not self.intent_acceptance_ready:
            raise ModelAuthorityError(
                "accepted revision set requires exact resolved intent closure"
            )
        if self.status == REVISION_ACCEPTED and not self.path_quality_acceptance_ready:
            raise ModelAuthorityError(
                "accepted revision set requires exact current observed path-quality closure"
            )
        if self.status != REVISION_PROPOSED and not self.decision_reason:
            raise ModelAuthorityError(
                "terminal revision set requires a decision reason"
            )
        if self.schema != MODEL_REVISION_SET_CURRENT_SCHEMA:
            raise ModelAuthorityError(
                f"revision set schema must be {MODEL_REVISION_SET_CURRENT_SCHEMA}"
            )

    @staticmethod
    def _coverage_union(
        refs: Iterable[RevisionEvidenceRef],
    ) -> tuple[str, ...] | None:
        values = [
            covered_id
            for item in refs
            for covered_id in item.covered_affected_ids
        ]
        if len(values) != len(set(values)):
            return None
        return tuple(sorted(values))

    @property
    def evidence_complete(self) -> bool:
        required = tuple(item.identity_key for item in self.required_evidence_refs)
        completed = tuple(item.identity_key for item in self.completed_evidence_refs)
        return (
            required == completed
            and all(item.passing for item in self.completed_evidence_refs)
            and self._coverage_union(self.required_evidence_refs)
            == self.affected_closure_ids
            and self._coverage_union(self.completed_evidence_refs)
            == self.affected_closure_ids
        )

    def _intent_expressible_changed_model_ids(self) -> tuple[str, ...]:
        semantic_prefixes = (
            "obligation:",
            "state:",
            "transition:",
            "invariant:",
            "relation:",
        )
        return tuple(
            sorted(
                {
                    _id(item_id, "changed_model_identity_id")
                    for item_id in (
                        *(
                            changed_id
                            for member in self.members
                            for changed_id in member.changed_element_ids
                        ),
                        *self.changed_relation_ids,
                    )
                    if item_id.startswith(semantic_prefixes)
                }
            )
        )

    @property
    def intent_review(self) -> ModelIntentReview:
        known_external_contribution_ids = tuple(
            item.prior_contribution_id
            for item in self.current_effective_intent_view.transitions
            if item.action == "supersede"
        )
        return review_model_intent_inventory(
            self.intent_contributions,
            self.intent_dispositions,
            changed_model_ids=self._intent_expressible_changed_model_ids(),
            changed_gap_ids=self.changed_gap_ids,
            enforce_changed_targets=True,
            known_external_contribution_ids=known_external_contribution_ids,
        )

    @property
    def intent_acceptance_ready(self) -> bool:
        no_intent_complete = bool(
            self.no_declared_intent_rationale_id
            and self.no_declared_intent_evidence_fingerprints
            and self.no_declared_intent_rationale
        )
        return (
            self.current_effective_intent_view.complete
            and self.intent_review.acceptance_ready
            and bool(self.intent_contributions or no_intent_complete)
        )

    @property
    def path_quality_blocked_model_ids(self) -> tuple[str, ...]:
        subjects_by_model = {
            item.model_id: item for item in self.path_quality_subjects
        }
        results_by_subject = {
            item.subject_fingerprint: item for item in self.path_quality_results
        }
        blocked: list[str] = []
        for model_id in self.required_path_quality_model_ids:
            subject = subjects_by_model.get(model_id)
            if subject is None:
                blocked.append(model_id)
                continue
            result = results_by_subject.get(subject.fingerprint)
            if result is None:
                blocked.append(model_id)
                continue
            if (
                not result.current
                or result.currentness_id != self.candidate_snapshot_fingerprint
                or result.currentness_id != subject.currentness_id
                or result.conclusion == "unresolved"
                or result.unresolved_ids
                or result.selected_candidate_lane == "normative_target"
            ):
                blocked.append(model_id)
        return tuple(blocked)

    @property
    def path_quality_acceptance_ready(self) -> bool:
        return (
            len(self.path_quality_subjects)
            == len(self.required_path_quality_model_ids)
            == len(self.path_quality_results)
            and not self.path_quality_blocked_model_ids
        )

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.identity_payload())

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "revision_set_id": self.revision_set_id,
            "task_id": self.task_id,
            "expected_head_fingerprint": self.expected_head_fingerprint,
            "base_snapshot_fingerprint": self.base_snapshot_fingerprint,
            "candidate_snapshot_fingerprint": (
                self.candidate_snapshot_fingerprint
            ),
            "members": [item.to_dict() for item in self.members],
            "affected_closure_ids": list(self.affected_closure_ids),
            "affected_closure_fingerprint": self.affected_closure_fingerprint,
            "affected_edge_ids": list(self.affected_edge_ids),
            "affected_owner_bindings": [
                {
                    "affected_id": affected_id,
                    "owner_route": owner_route,
                }
                for affected_id, owner_route in self.affected_owner_bindings
            ],
            "snapshot_diff_fingerprint": self.snapshot_diff_fingerprint,
            "changed_root_ids": list(self.changed_root_ids),
            "changed_relation_ids": list(self.changed_relation_ids),
            "changed_source_surface_ids": list(
                self.changed_source_surface_ids
            ),
            "changed_commitment_ids": list(self.changed_commitment_ids),
            "changed_field_ids": list(self.changed_field_ids),
            "changed_side_effect_ids": list(self.changed_side_effect_ids),
            "changed_contract_ids": list(self.changed_contract_ids),
            "changed_test_ids": list(self.changed_test_ids),
            "changed_system_property_ids": list(
                self.changed_system_property_ids
            ),
            "changed_coverage_ids": list(self.changed_coverage_ids),
            "changed_gap_ids": list(self.changed_gap_ids),
            "changed_owner_artifact_ids": list(
                self.changed_owner_artifact_ids
            ),
            "added_ids": list(self.added_ids),
            "removed_ids": list(self.removed_ids),
            "fingerprint_changed_ids": list(
                self.fingerprint_changed_ids
            ),
            "removal_dispositions": [
                item.to_dict() for item in self.removal_dispositions
            ],
            "required_evidence_refs": [
                item.to_dict() for item in self.required_evidence_refs
            ],
            "completed_evidence_refs": [
                item.to_dict() for item in self.completed_evidence_refs
            ],
            "prediction_replay_refs": [
                item.to_dict() for item in self.prediction_replay_refs
            ],
            "required_path_quality_model_ids": list(
                self.required_path_quality_model_ids
            ),
            "path_quality_subjects": [
                item.to_dict() for item in self.path_quality_subjects
            ],
            "path_quality_results": [
                item.to_compact_dict() for item in self.path_quality_results
            ],
            "path_quality_result_set_fingerprint": (
                self.path_quality_result_set_fingerprint
            ),
            "intent_contributions": [
                item.to_dict() for item in self.intent_contributions
            ],
            "intent_dispositions": [
                item.to_dict() for item in self.intent_dispositions
            ],
            "current_effective_intent_view": (
                self.current_effective_intent_view.to_dict()
            ),
            "intent_contribution_inventory_fingerprint": (
                self.intent_contribution_inventory_fingerprint
            ),
            "intent_conflict_ids": list(self.intent_conflict_ids),
            "intent_unresolved_ids": list(self.intent_unresolved_ids),
            "no_declared_intent_rationale_id": (
                self.no_declared_intent_rationale_id
            ),
            "no_declared_intent_evidence_fingerprints": [
                {"role": role, "fingerprint": fingerprint}
                for role, fingerprint in self.no_declared_intent_evidence_fingerprints
            ],
            "no_declared_intent_rationale": self.no_declared_intent_rationale,
            "implementation_bundle_fingerprint": (
                self.implementation_bundle_fingerprint
            ),
            "rollback_contract_fingerprint": (
                self.rollback_contract_fingerprint
            ),
            "originating_revision_set_fingerprint": (
                self.originating_revision_set_fingerprint
            ),
            "originating_activation_receipt_fingerprint": (
                self.originating_activation_receipt_fingerprint
            ),
            "status": self.status,
            "decision_reason": self.decision_reason,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}

    def accept(
        self,
        completed_evidence_refs: Iterable[RevisionEvidenceRef],
        *,
        reason: str,
    ) -> "ModelRevisionSet":
        if self.status != REVISION_PROPOSED:
            raise ModelAuthorityError(
                "only a proposed revision set can be accepted"
            )
        if not self.intent_acceptance_ready:
            raise ModelAuthorityError(
                "revision intent conflicts or unresolved effects block acceptance"
            )
        completed = tuple(
            sorted(
                completed_evidence_refs,
                key=lambda item: item.identity_key,
            )
        )
        if any(not isinstance(item, RevisionEvidenceRef) for item in completed):
            raise ModelAuthorityError(
                "acceptance requires typed revision evidence receipts"
            )
        if any(not item.passing for item in completed):
            raise ModelAuthorityError(
                "acceptance evidence must be pass, current, and eligible"
            )
        if tuple(item.identity_key for item in completed) != tuple(
            item.identity_key for item in self.required_evidence_refs
        ):
            raise ModelAuthorityError(
                "revision-set evidence must match the required set exactly"
            )
        return replace(
            self,
            completed_evidence_refs=completed,
            status=REVISION_ACCEPTED,
            decision_reason=_text(reason, "decision reason"),
        )

    def reject(self, reason: str) -> "ModelRevisionSet":
        if self.status != REVISION_PROPOSED:
            raise ModelAuthorityError(
                "only a proposed revision set can be rejected"
            )
        return replace(
            self,
            status=REVISION_REJECTED,
            decision_reason=_text(reason, "decision reason"),
        )

    def withdraw_target(self, reason: str) -> "ModelRevisionSet":
        if self.status not in {REVISION_PROPOSED, REVISION_ACCEPTED}:
            raise ModelAuthorityError(
                "only a proposed or accepted target can be withdrawn"
            )
        return replace(
            self,
            status=REVISION_WITHDRAWN,
            decision_reason=_text(reason, "decision reason"),
        )

    @classmethod
    def from_dict(cls, value: Any) -> "ModelRevisionSet":
        if not isinstance(value, Mapping):
            raise ModelAuthorityError("model_revision_set must be a JSON object")
        if value.get("schema") != MODEL_REVISION_SET_CURRENT_SCHEMA:
            raise ModelAuthorityError(
                "model revision set schema must be "
                f"{MODEL_REVISION_SET_CURRENT_SCHEMA}; legacy current authority "
                "requires explicit intent bootstrap migration"
            )
        data = _strict(
            value,
            "model_revision_set",
            (
                "schema",
                "revision_set_id",
                "task_id",
                "expected_head_fingerprint",
                "base_snapshot_fingerprint",
                "candidate_snapshot_fingerprint",
                "members",
                "affected_closure_ids",
                "affected_closure_fingerprint",
                "affected_edge_ids",
                "affected_owner_bindings",
                "snapshot_diff_fingerprint",
                "changed_root_ids",
                "changed_relation_ids",
                "changed_source_surface_ids",
                "changed_commitment_ids",
                "changed_field_ids",
                "changed_side_effect_ids",
                "changed_contract_ids",
                "changed_test_ids",
                "changed_system_property_ids",
                "changed_coverage_ids",
                "changed_gap_ids",
                "changed_owner_artifact_ids",
                "added_ids",
                "removed_ids",
                "fingerprint_changed_ids",
                "removal_dispositions",
                "required_evidence_refs",
                "completed_evidence_refs",
                "prediction_replay_refs",
                "required_path_quality_model_ids",
                "path_quality_subjects",
                "path_quality_results",
                "path_quality_result_set_fingerprint",
                "intent_contributions",
                "intent_dispositions",
                "current_effective_intent_view",
                "intent_contribution_inventory_fingerprint",
                "intent_conflict_ids",
                "intent_unresolved_ids",
                "no_declared_intent_rationale_id",
                "no_declared_intent_evidence_fingerprints",
                "no_declared_intent_rationale",
                "implementation_bundle_fingerprint",
                "rollback_contract_fingerprint",
                "originating_revision_set_fingerprint",
                "originating_activation_receipt_fingerprint",
                "status",
                "decision_reason",
                "fingerprint",
            ),
        )
        for field_name in (
            "schema",
            "revision_set_id",
            "task_id",
            "expected_head_fingerprint",
            "base_snapshot_fingerprint",
            "candidate_snapshot_fingerprint",
            "affected_closure_fingerprint",
            "snapshot_diff_fingerprint",
            "intent_contribution_inventory_fingerprint",
            "no_declared_intent_rationale_id",
            "no_declared_intent_rationale",
            "implementation_bundle_fingerprint",
            "rollback_contract_fingerprint",
            "originating_revision_set_fingerprint",
            "originating_activation_receipt_fingerprint",
            "status",
            "decision_reason",
            "fingerprint",
            "path_quality_result_set_fingerprint",
        ):
            _wire_string(data[field_name], field_name)
        for field_name in (
            "affected_closure_ids",
            "affected_edge_ids",
            "changed_root_ids",
            "changed_relation_ids",
            "changed_source_surface_ids",
            "changed_commitment_ids",
            "changed_field_ids",
            "changed_side_effect_ids",
            "changed_contract_ids",
            "changed_test_ids",
            "changed_system_property_ids",
            "changed_coverage_ids",
            "changed_gap_ids",
            "changed_owner_artifact_ids",
            "added_ids",
            "removed_ids",
            "fingerprint_changed_ids",
            "intent_conflict_ids",
            "intent_unresolved_ids",
            "required_path_quality_model_ids",
        ):
            _wire_strings(data[field_name], field_name)
        result = cls(
            revision_set_id=data["revision_set_id"],
            task_id=data["task_id"],
            expected_head_fingerprint=data["expected_head_fingerprint"],
            base_snapshot_fingerprint=data["base_snapshot_fingerprint"],
            candidate_snapshot_fingerprint=data[
                "candidate_snapshot_fingerprint"
            ],
            members=tuple(
                RevisionMemberChange.from_dict(item)
                for item in _array(data["members"], "members")
            ),
            affected_closure_ids=tuple(
                _array(data["affected_closure_ids"], "affected_closure_ids")
            ),
            affected_closure_fingerprint=data[
                "affected_closure_fingerprint"
            ],
            affected_edge_ids=tuple(
                _array(data["affected_edge_ids"], "affected_edge_ids")
            ),
            affected_owner_bindings=tuple(
                _wire_pair(
                    item,
                    "affected_owner_binding",
                    "affected_id",
                    "owner_route",
                )
                for item in _array(
                    data["affected_owner_bindings"],
                    "affected_owner_bindings",
                )
            ),
            snapshot_diff_fingerprint=data["snapshot_diff_fingerprint"],
            changed_root_ids=tuple(
                _array(data["changed_root_ids"], "changed_root_ids")
            ),
            changed_relation_ids=tuple(
                _array(data["changed_relation_ids"], "changed_relation_ids")
            ),
            changed_source_surface_ids=tuple(
                _array(
                    data["changed_source_surface_ids"],
                    "changed_source_surface_ids",
                )
            ),
            changed_commitment_ids=tuple(
                _array(
                    data["changed_commitment_ids"],
                    "changed_commitment_ids",
                )
            ),
            changed_field_ids=tuple(
                _array(data["changed_field_ids"], "changed_field_ids")
            ),
            changed_side_effect_ids=tuple(
                _array(
                    data["changed_side_effect_ids"],
                    "changed_side_effect_ids",
                )
            ),
            changed_contract_ids=tuple(
                _array(data["changed_contract_ids"], "changed_contract_ids")
            ),
            changed_test_ids=tuple(
                _array(data["changed_test_ids"], "changed_test_ids")
            ),
            changed_system_property_ids=tuple(
                _array(
                    data["changed_system_property_ids"],
                    "changed_system_property_ids",
                )
            ),
            changed_coverage_ids=tuple(
                _array(
                    data["changed_coverage_ids"],
                    "changed_coverage_ids",
                )
            ),
            changed_gap_ids=tuple(
                _array(data["changed_gap_ids"], "changed_gap_ids")
            ),
            changed_owner_artifact_ids=tuple(
                _array(
                    data["changed_owner_artifact_ids"],
                    "changed_owner_artifact_ids",
                )
            ),
            added_ids=tuple(
                _array(data["added_ids"], "added_ids")
            ),
            removed_ids=tuple(
                _array(data["removed_ids"], "removed_ids")
            ),
            fingerprint_changed_ids=tuple(
                _array(
                    data["fingerprint_changed_ids"],
                    "fingerprint_changed_ids",
                )
            ),
            removal_dispositions=tuple(
                RevisionRemovalDisposition.from_dict(item)
                for item in _array(
                    data["removal_dispositions"],
                    "removal_dispositions",
                )
            ),
            required_evidence_refs=tuple(
                RevisionEvidenceRef.from_dict(item)
                for item in _array(
                    data["required_evidence_refs"],
                    "required_evidence_refs",
                )
            ),
            completed_evidence_refs=tuple(
                RevisionEvidenceRef.from_dict(item)
                for item in _array(
                    data["completed_evidence_refs"],
                    "completed_evidence_refs",
                )
            ),
            prediction_replay_refs=tuple(
                PredictionReplayRef.from_dict(item)
                for item in _array(
                    data["prediction_replay_refs"],
                    "prediction_replay_refs",
                )
            ),
            required_path_quality_model_ids=tuple(
                _array(
                    data["required_path_quality_model_ids"],
                    "required_path_quality_model_ids",
                )
            ),
            path_quality_subjects=tuple(
                PathQualitySubject.from_dict(item)
                for item in _array(
                    data["path_quality_subjects"], "path_quality_subjects"
                )
            ),
            path_quality_results=tuple(
                PathQualityResult.from_dict(item)
                for item in _array(
                    data["path_quality_results"], "path_quality_results"
                )
            ),
            path_quality_result_set_fingerprint=data[
                "path_quality_result_set_fingerprint"
            ],
            intent_contributions=tuple(
                _strict_model_intent_contribution(item)
                for item in _array(
                    data["intent_contributions"],
                    "intent_contributions",
                )
            ),
            intent_dispositions=tuple(
                _strict_model_intent_disposition(item)
                for item in _array(
                    data["intent_dispositions"],
                    "intent_dispositions",
                )
            ),
            current_effective_intent_view=(
                CurrentEffectiveIntentView.from_dict(
                    data["current_effective_intent_view"]
                )
            ),
            intent_contribution_inventory_fingerprint=data[
                "intent_contribution_inventory_fingerprint"
            ],
            intent_conflict_ids=tuple(
                _array(data["intent_conflict_ids"], "intent_conflict_ids")
            ),
            intent_unresolved_ids=tuple(
                _array(
                    data["intent_unresolved_ids"],
                    "intent_unresolved_ids",
                )
            ),
            no_declared_intent_rationale_id=data[
                "no_declared_intent_rationale_id"
            ],
            no_declared_intent_evidence_fingerprints=tuple(
                _wire_pair(
                    item,
                    "no_declared_intent_evidence",
                    "role",
                    "fingerprint",
                )
                for item in _array(
                    data["no_declared_intent_evidence_fingerprints"],
                    "no_declared_intent_evidence_fingerprints",
                )
            ),
            no_declared_intent_rationale=data[
                "no_declared_intent_rationale"
            ],
            implementation_bundle_fingerprint=data[
                "implementation_bundle_fingerprint"
            ],
            rollback_contract_fingerprint=data[
                "rollback_contract_fingerprint"
            ],
            originating_revision_set_fingerprint=data[
                "originating_revision_set_fingerprint"
            ],
            originating_activation_receipt_fingerprint=data[
                "originating_activation_receipt_fingerprint"
            ],
            status=data["status"],
            decision_reason=data["decision_reason"],
            schema=data["schema"],
        )
        if data["fingerprint"] != result.fingerprint:
            raise ModelAuthorityError("stale revision-set fingerprint")
        return result


def derive_affected_closure_fingerprint(
    *,
    affected_closure_ids: Iterable[str],
    affected_edge_ids: Iterable[str],
    affected_owner_bindings: Iterable[tuple[str, str]],
) -> str:
    payload = {
        "affected_closure_ids": list(
            _ids(affected_closure_ids, "affected_closure_id")
        ),
        "affected_edge_ids": list(
            _ids(affected_edge_ids, "affected_edge_id")
        ),
        "affected_owner_bindings": [
            {
                "affected_id": affected_id,
                "owner_route": owner_route,
            }
            for affected_id, owner_route in _normalize_owner_bindings(
                affected_owner_bindings
            )
        ],
    }
    return canonical_fingerprint(payload)


def validate_revision_set_snapshots(
    base_snapshot: ModelSystemSnapshot,
    candidate_snapshot: ModelSystemSnapshot,
    revision_set: ModelRevisionSet,
) -> None:
    """Prove the declared revision is the exact base/candidate snapshot diff."""

    if base_snapshot.fingerprint != revision_set.base_snapshot_fingerprint:
        raise ModelAuthorityError("revision base snapshot fingerprint mismatch")
    if (
        candidate_snapshot.fingerprint
        != revision_set.candidate_snapshot_fingerprint
    ):
        raise ModelAuthorityError(
            "revision candidate snapshot fingerprint mismatch"
        )
    validate_current_effective_intent_view(
        candidate_snapshot,
        revision_set.current_effective_intent_view,
    )
    if base_snapshot.system_id != candidate_snapshot.system_id:
        raise ModelAuthorityError("revision snapshots belong to different systems")

    derived_diff = derive_revision_snapshot_diff(
        base_snapshot,
        candidate_snapshot,
    )
    if revision_set.snapshot_diff_fingerprint != derived_diff.fingerprint:
        raise ModelAuthorityError(
            "revision snapshot diff fingerprint does not match independently derived diff"
        )
    declarations = (
        ("members", revision_set.members, derived_diff.members),
        (
            "changed_root_ids",
            revision_set.changed_root_ids,
            derived_diff.changed_root_ids,
        ),
        (
            "changed_relation_ids",
            revision_set.changed_relation_ids,
            derived_diff.changed_relation_ids,
        ),
        (
            "changed_source_surface_ids",
            revision_set.changed_source_surface_ids,
            derived_diff.changed_source_surface_ids,
        ),
        (
            "changed_commitment_ids",
            revision_set.changed_commitment_ids,
            derived_diff.changed_commitment_ids,
        ),
        (
            "changed_field_ids",
            revision_set.changed_field_ids,
            derived_diff.changed_field_ids,
        ),
        (
            "changed_side_effect_ids",
            revision_set.changed_side_effect_ids,
            derived_diff.changed_side_effect_ids,
        ),
        (
            "changed_contract_ids",
            revision_set.changed_contract_ids,
            derived_diff.changed_contract_ids,
        ),
        (
            "changed_test_ids",
            revision_set.changed_test_ids,
            derived_diff.changed_test_ids,
        ),
        (
            "changed_system_property_ids",
            revision_set.changed_system_property_ids,
            derived_diff.changed_system_property_ids,
        ),
        (
            "changed_coverage_ids",
            revision_set.changed_coverage_ids,
            derived_diff.changed_coverage_ids,
        ),
        (
            "changed_gap_ids",
            revision_set.changed_gap_ids,
            derived_diff.changed_gap_ids,
        ),
        (
            "changed_owner_artifact_ids",
            revision_set.changed_owner_artifact_ids,
            derived_diff.changed_owner_artifact_ids,
        ),
        ("added_ids", revision_set.added_ids, derived_diff.added_ids),
        ("removed_ids", revision_set.removed_ids, derived_diff.removed_ids),
        (
            "fingerprint_changed_ids",
            revision_set.fingerprint_changed_ids,
            derived_diff.fingerprint_changed_ids,
        ),
    )
    for field_name, declared_value, derived_value in declarations:
        if declared_value != derived_value:
            raise ModelAuthorityError(
                f"revision {field_name} do not match the independently derived snapshot diff"
            )
    derived_closure = derive_revision_affected_closure(
        base_snapshot,
        candidate_snapshot,
        derived_diff,
    )
    if revision_set.affected_closure_ids != derived_closure.affected_ids:
        raise ModelAuthorityError(
            "revision affected_closure_ids do not match the independently derived closure"
        )
    if revision_set.affected_edge_ids != derived_closure.edge_ids:
        raise ModelAuthorityError(
            "revision affected_edge_ids do not match the independently derived closure"
        )
    if (
        revision_set.affected_owner_bindings
        != derived_closure.owner_bindings
    ):
        raise ModelAuthorityError(
            "revision affected_owner_bindings do not match native closure owners"
        )
    if (
        revision_set.affected_closure_fingerprint
        != derived_closure.fingerprint
    ):
        raise ModelAuthorityError(
            "revision affected closure fingerprint is stale or incomplete"
        )
    if (
        revision_set._coverage_union(revision_set.required_evidence_refs)
        != derived_closure.affected_ids
    ):
        raise ModelAuthorityError(
            "revision required evidence does not cover the complete derived closure exactly"
        )
    if revision_set.completed_evidence_refs and (
        revision_set._coverage_union(revision_set.completed_evidence_refs)
        != derived_closure.affected_ids
    ):
        raise ModelAuthorityError(
            "revision completed evidence does not cover the complete derived closure exactly"
        )


@dataclass(frozen=True)
class ModelActivationReceipt:
    receipt_id: str
    system_id: str
    revision_set_fingerprint: str
    expected_head_fingerprint: str
    previous_snapshot_fingerprint: str
    candidate_snapshot_fingerprint: str
    subject_revision: str
    next_generation: int
    schema: str = MODEL_ACTIVATION_RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_id", _id(self.receipt_id, "receipt_id"))
        object.__setattr__(self, "system_id", _id(self.system_id, "system_id"))
        for name in (
            "revision_set_fingerprint",
            "expected_head_fingerprint",
            "previous_snapshot_fingerprint",
            "candidate_snapshot_fingerprint",
        ):
            object.__setattr__(self, name, _sha(getattr(self, name), name))
        object.__setattr__(
            self,
            "subject_revision",
            _text(self.subject_revision, "subject_revision"),
        )
        if (
            not isinstance(self.next_generation, int)
            or isinstance(self.next_generation, bool)
            or self.next_generation < 2
        ):
            raise ModelAuthorityError(
                "activation next_generation must be at least two"
            )
        if self.schema != MODEL_ACTIVATION_RECEIPT_SCHEMA:
            raise ModelAuthorityError(
                f"activation receipt schema must be {MODEL_ACTIVATION_RECEIPT_SCHEMA}"
            )

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "receipt_id": self.receipt_id,
            "system_id": self.system_id,
            "revision_set_fingerprint": self.revision_set_fingerprint,
            "expected_head_fingerprint": self.expected_head_fingerprint,
            "previous_snapshot_fingerprint": (
                self.previous_snapshot_fingerprint
            ),
            "candidate_snapshot_fingerprint": (
                self.candidate_snapshot_fingerprint
            ),
            "subject_revision": self.subject_revision,
            "next_generation": self.next_generation,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ModelActivationReceipt":
        data = _strict(
            value,
            "model_activation_receipt",
            (
                "schema",
                "receipt_id",
                "system_id",
                "revision_set_fingerprint",
                "expected_head_fingerprint",
                "previous_snapshot_fingerprint",
                "candidate_snapshot_fingerprint",
                "subject_revision",
                "next_generation",
            ),
        )
        return cls(
            receipt_id=_wire_string(data["receipt_id"], "activation receipt_id"),
            system_id=_wire_string(data["system_id"], "activation system_id"),
            revision_set_fingerprint=_wire_string(
                data["revision_set_fingerprint"], "revision_set_fingerprint"
            ),
            expected_head_fingerprint=_wire_string(
                data["expected_head_fingerprint"], "expected_head_fingerprint"
            ),
            previous_snapshot_fingerprint=_wire_string(
                data["previous_snapshot_fingerprint"],
                "previous_snapshot_fingerprint",
            ),
            candidate_snapshot_fingerprint=_wire_string(
                data["candidate_snapshot_fingerprint"],
                "candidate_snapshot_fingerprint",
            ),
            subject_revision=_wire_string(
                data["subject_revision"], "activation subject_revision"
            ),
            next_generation=_wire_integer(
                data["next_generation"], "activation next_generation"
            ),
            schema=_wire_string(data["schema"], "activation schema"),
        )


def validate_activation_plan(
    current_head: ModelAuthorityHead,
    base_snapshot: ModelSystemSnapshot,
    candidate_snapshot: ModelSystemSnapshot,
    revision_set: ModelRevisionSet,
    *,
    live_candidate_snapshot: ModelSystemSnapshot,
    receipt_id: str,
) -> tuple[ModelAuthorityHead, ModelActivationReceipt]:
    """Pure validation only; durable CAS is owned by model_authority_store."""

    if revision_set.status != REVISION_ACCEPTED:
        raise ModelAuthorityError("revision set must be accepted before activation")
    if current_head.fingerprint != revision_set.expected_head_fingerprint:
        raise ModelAuthorityError("observed authority head changed; rebase required")
    if (
        current_head.snapshot_fingerprint
        != revision_set.base_snapshot_fingerprint
    ):
        raise ModelAuthorityError("revision base does not match observed snapshot")
    if (
        live_candidate_snapshot.identity_payload()
        != candidate_snapshot.identity_payload()
    ):
        raise ModelAuthorityError(
            "re-derived live candidate differs from accepted candidate"
        )
    validate_revision_set_snapshots(
        base_snapshot,
        candidate_snapshot,
        revision_set,
    )
    if not revision_set.evidence_complete:
        raise ModelAuthorityError("revision-set evidence is incomplete")
    if (
        candidate_snapshot.fingerprint
        != revision_set.candidate_snapshot_fingerprint
    ):
        raise ModelAuthorityError(
            "revision candidate does not match candidate snapshot"
        )
    if candidate_snapshot.subject_lane != SUBJECT_OBSERVED_IMPLEMENTATION:
        raise ModelAuthorityError(
            "target or experiment snapshot cannot become observed authority"
        )
    if candidate_snapshot.lifecycle != LIFECYCLE_ACTIVE:
        raise ModelAuthorityError(
            "observed activation requires an active snapshot"
        )
    if candidate_snapshot.system_id != current_head.system_id:
        raise ModelAuthorityError("candidate snapshot belongs to another system")
    receipt = ModelActivationReceipt(
        receipt_id=receipt_id,
        system_id=current_head.system_id,
        revision_set_fingerprint=revision_set.fingerprint,
        expected_head_fingerprint=current_head.fingerprint,
        previous_snapshot_fingerprint=current_head.snapshot_fingerprint,
        candidate_snapshot_fingerprint=candidate_snapshot.fingerprint,
        subject_revision=candidate_snapshot.subject_revision,
        next_generation=current_head.generation + 1,
    )
    next_head = ModelAuthorityHead(
        system_id=current_head.system_id,
        snapshot_fingerprint=candidate_snapshot.fingerprint,
        subject_revision=candidate_snapshot.subject_revision,
        generation=current_head.generation + 1,
        accepted_revision_set_fingerprint=revision_set.fingerprint,
        previous_snapshot_fingerprint=current_head.snapshot_fingerprint,
        activation_receipt_fingerprint=receipt.fingerprint,
    )
    return next_head, receipt


@dataclass(frozen=True)
class ModelRollbackEffect:
    effect_id: str
    kind: str
    disposition: str
    required_evidence_fingerprints: tuple[str, ...]
    schema: str = MODEL_ROLLBACK_EFFECT_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "effect_id", _id(self.effect_id, "effect_id"))
        object.__setattr__(self, "kind", _id(self.kind, "effect kind"))
        if self.disposition not in ROLLBACK_EFFECT_DISPOSITIONS:
            raise ModelAuthorityError(
                f"unsupported rollback effect disposition: {self.disposition}"
            )
        object.__setattr__(
            self,
            "required_evidence_fingerprints",
            _shas(
                self.required_evidence_fingerprints,
                "required_evidence_fingerprint",
            ),
        )
        if not self.required_evidence_fingerprints:
            raise ModelAuthorityError(
                "rollback effect requires evidence obligations"
            )
        if self.schema != MODEL_ROLLBACK_EFFECT_SCHEMA:
            raise ModelAuthorityError(
                f"rollback effect schema must be {MODEL_ROLLBACK_EFFECT_SCHEMA}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "effect_id": self.effect_id,
            "kind": self.kind,
            "disposition": self.disposition,
            "required_evidence_fingerprints": list(
                self.required_evidence_fingerprints
            ),
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ModelRollbackEffect":
        data = _strict(
            value,
            "model_rollback_effect",
            (
                "schema",
                "effect_id",
                "kind",
                "disposition",
                "required_evidence_fingerprints",
            ),
        )
        return cls(
            effect_id=_wire_string(data["effect_id"], "rollback effect_id"),
            kind=_wire_string(data["kind"], "rollback effect kind"),
            disposition=_wire_string(
                data["disposition"], "rollback effect disposition"
            ),
            required_evidence_fingerprints=_wire_strings(
                data["required_evidence_fingerprints"],
                "required_evidence_fingerprints",
            ),
            schema=_wire_string(data["schema"], "rollback effect schema"),
        )


@dataclass(frozen=True)
class ModelRollbackContract:
    contract_id: str
    expected_head_fingerprint: str
    originating_revision_set_fingerprint: str
    originating_activation_receipt_fingerprint: str
    from_snapshot_fingerprint: str
    to_snapshot_fingerprint: str
    effects: tuple[ModelRollbackEffect, ...]
    old_snapshot_conformance_evidence_fingerprints: tuple[str, ...]
    schema: str = MODEL_ROLLBACK_CONTRACT_CURRENT_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "contract_id", _id(self.contract_id, "contract_id"))
        for name in (
            "expected_head_fingerprint",
            "originating_revision_set_fingerprint",
            "originating_activation_receipt_fingerprint",
            "from_snapshot_fingerprint",
            "to_snapshot_fingerprint",
        ):
            object.__setattr__(self, name, _sha(getattr(self, name), name))
        if self.from_snapshot_fingerprint == self.to_snapshot_fingerprint:
            raise ModelAuthorityError(
                "rollback contract must change the snapshot"
            )
        effects = tuple(sorted(self.effects, key=lambda item: item.effect_id))
        if not effects:
            raise ModelAuthorityError(
                "operational rollback contract requires effects"
            )
        effect_ids = tuple(item.effect_id for item in effects)
        if len(effect_ids) != len(set(effect_ids)):
            raise ModelAuthorityError("rollback effect ids must be unique")
        object.__setattr__(self, "effects", effects)
        object.__setattr__(
            self,
            "old_snapshot_conformance_evidence_fingerprints",
            _shas(
                self.old_snapshot_conformance_evidence_fingerprints,
                "old_snapshot_conformance_evidence_fingerprint",
            ),
        )
        if not self.old_snapshot_conformance_evidence_fingerprints:
            raise ModelAuthorityError(
                "rollback requires old-snapshot conformance evidence"
            )
        if self.schema != MODEL_ROLLBACK_CONTRACT_CURRENT_SCHEMA:
            raise ModelAuthorityError(
                "rollback contract schema must be "
                f"{MODEL_ROLLBACK_CONTRACT_CURRENT_SCHEMA}"
            )

    @property
    def exact_rollback_possible(self) -> bool:
        return all(item.disposition == "restore" for item in self.effects)

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.to_dict())

    @property
    def required_evidence_fingerprints(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    *self.old_snapshot_conformance_evidence_fingerprints,
                    *(
                        value
                        for item in self.effects
                        for value in item.required_evidence_fingerprints
                    ),
                }
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "contract_id": self.contract_id,
            "expected_head_fingerprint": self.expected_head_fingerprint,
            "originating_revision_set_fingerprint": (
                self.originating_revision_set_fingerprint
            ),
            "originating_activation_receipt_fingerprint": (
                self.originating_activation_receipt_fingerprint
            ),
            "from_snapshot_fingerprint": self.from_snapshot_fingerprint,
            "to_snapshot_fingerprint": self.to_snapshot_fingerprint,
            "effects": [item.to_dict() for item in self.effects],
            "old_snapshot_conformance_evidence_fingerprints": list(
                self.old_snapshot_conformance_evidence_fingerprints
            ),
            "exact_rollback_possible": self.exact_rollback_possible,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ModelRollbackContract":
        data = _strict(
            value,
            "model_rollback_contract",
            (
                "schema",
                "contract_id",
                "expected_head_fingerprint",
                "originating_revision_set_fingerprint",
                "originating_activation_receipt_fingerprint",
                "from_snapshot_fingerprint",
                "to_snapshot_fingerprint",
                "effects",
                "old_snapshot_conformance_evidence_fingerprints",
                "exact_rollback_possible",
            ),
        )
        result = cls(
            contract_id=_wire_string(data["contract_id"], "rollback contract_id"),
            expected_head_fingerprint=_wire_string(
                data["expected_head_fingerprint"], "expected_head_fingerprint"
            ),
            originating_revision_set_fingerprint=_wire_string(
                data["originating_revision_set_fingerprint"],
                "originating_revision_set_fingerprint",
            ),
            originating_activation_receipt_fingerprint=_wire_string(
                data["originating_activation_receipt_fingerprint"],
                "originating_activation_receipt_fingerprint",
            ),
            from_snapshot_fingerprint=_wire_string(
                data["from_snapshot_fingerprint"], "from_snapshot_fingerprint"
            ),
            to_snapshot_fingerprint=_wire_string(
                data["to_snapshot_fingerprint"], "to_snapshot_fingerprint"
            ),
            effects=tuple(
                ModelRollbackEffect.from_dict(item)
                for item in _array(data["effects"], "effects")
            ),
            old_snapshot_conformance_evidence_fingerprints=_wire_strings(
                data["old_snapshot_conformance_evidence_fingerprints"],
                "old_snapshot_conformance_evidence_fingerprints",
            ),
            schema=_wire_string(data["schema"], "rollback contract schema"),
        )
        if (
            _wire_boolean(
                data["exact_rollback_possible"], "exact_rollback_possible"
            )
            != result.exact_rollback_possible
        ):
            raise ModelAuthorityError(
                "stale rollback exact_rollback_possible"
            )
        return result


@dataclass(frozen=True)
class ModelRollbackReceipt:
    receipt_id: str
    contract_fingerprint: str
    reverse_revision_set_fingerprint: str
    result: str
    completed_evidence_fingerprints: tuple[str, ...]
    reason: str
    schema: str = MODEL_ROLLBACK_RECEIPT_CURRENT_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_id", _id(self.receipt_id, "receipt_id"))
        object.__setattr__(
            self,
            "contract_fingerprint",
            _sha(self.contract_fingerprint, "contract_fingerprint"),
        )
        object.__setattr__(
            self,
            "reverse_revision_set_fingerprint",
            _sha(
                self.reverse_revision_set_fingerprint,
                "reverse_revision_set_fingerprint",
            ),
        )
        if self.result not in ROLLBACK_RESULTS:
            raise ModelAuthorityError(
                f"unsupported rollback result: {self.result}"
            )
        object.__setattr__(
            self,
            "completed_evidence_fingerprints",
            _shas(
                self.completed_evidence_fingerprints,
                "completed_evidence_fingerprint",
            ),
        )
        object.__setattr__(self, "reason", _text(self.reason, "rollback reason"))
        if self.schema != MODEL_ROLLBACK_RECEIPT_CURRENT_SCHEMA:
            raise ModelAuthorityError(
                "rollback receipt schema must be "
                f"{MODEL_ROLLBACK_RECEIPT_CURRENT_SCHEMA}"
            )

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "receipt_id": self.receipt_id,
            "contract_fingerprint": self.contract_fingerprint,
            "reverse_revision_set_fingerprint": (
                self.reverse_revision_set_fingerprint
            ),
            "result": self.result,
            "completed_evidence_fingerprints": list(
                self.completed_evidence_fingerprints
            ),
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ModelRollbackReceipt":
        data = _strict(
            value,
            "model_rollback_receipt",
            (
                "schema",
                "receipt_id",
                "contract_fingerprint",
                "reverse_revision_set_fingerprint",
                "result",
                "completed_evidence_fingerprints",
                "reason",
            ),
        )
        return cls(
            receipt_id=_wire_string(data["receipt_id"], "rollback receipt_id"),
            contract_fingerprint=_wire_string(
                data["contract_fingerprint"], "contract_fingerprint"
            ),
            reverse_revision_set_fingerprint=_wire_string(
                data["reverse_revision_set_fingerprint"],
                "reverse_revision_set_fingerprint",
            ),
            result=_wire_string(data["result"], "rollback result"),
            completed_evidence_fingerprints=_wire_strings(
                data["completed_evidence_fingerprints"],
                "completed_evidence_fingerprints",
            ),
            reason=_wire_string(data["reason"], "rollback reason"),
            schema=_wire_string(data["schema"], "rollback receipt schema"),
        )


def validate_operational_rollback(
    current_head: ModelAuthorityHead,
    contract: ModelRollbackContract,
    reverse_revision_set: ModelRevisionSet,
    *,
    completed_evidence_fingerprints: Iterable[str],
    requested_result: str,
    receipt_id: str,
    reason: str,
) -> ModelRollbackReceipt:
    """Validate real-world restoration before any observed pointer rewind."""

    if current_head.fingerprint != contract.expected_head_fingerprint:
        raise ModelAuthorityError(
            "authority head advanced; create a forward revision instead"
        )
    if current_head.snapshot_fingerprint != contract.from_snapshot_fingerprint:
        raise ModelAuthorityError(
            "rollback contract source snapshot does not match current head"
        )
    if (
        current_head.accepted_revision_set_fingerprint
        != contract.originating_revision_set_fingerprint
        or current_head.activation_receipt_fingerprint
        != contract.originating_activation_receipt_fingerprint
    ):
        raise ModelAuthorityError(
            "rollback origin revision or activation identity is stale"
        )
    if (
        reverse_revision_set.expected_head_fingerprint
        != current_head.fingerprint
        or reverse_revision_set.base_snapshot_fingerprint
        != contract.from_snapshot_fingerprint
        or reverse_revision_set.candidate_snapshot_fingerprint
        != contract.to_snapshot_fingerprint
    ):
        raise ModelAuthorityError(
            "reverse revision does not bind the exact rollback head and snapshots"
        )
    if (
        reverse_revision_set.originating_revision_set_fingerprint
        != contract.originating_revision_set_fingerprint
        or reverse_revision_set.originating_activation_receipt_fingerprint
        != contract.originating_activation_receipt_fingerprint
        or reverse_revision_set.rollback_contract_fingerprint
        != contract.fingerprint
    ):
        raise ModelAuthorityError(
            "reverse revision does not bind the rollback origin and contract"
        )
    if (
        reverse_revision_set.status != REVISION_ACCEPTED
        or not reverse_revision_set.evidence_complete
    ):
        raise ModelAuthorityError(
            "reverse revision requires an accepted exact evidence closure"
        )
    completed = _shas(
        completed_evidence_fingerprints,
        "completed_evidence_fingerprint",
    )
    if completed != contract.required_evidence_fingerprints:
        raise ModelAuthorityError(
            "rollback evidence must match the restore and conformance set exactly"
        )
    if requested_result == ROLLBACK_RESULT_EXACT:
        if not contract.exact_rollback_possible:
            raise ModelAuthorityError(
                "irreversible or compensated effects cannot claim exact rollback"
            )
    elif requested_result == ROLLBACK_RESULT_COMPENSATED:
        if any(
            item.disposition == "irreversible" for item in contract.effects
        ):
            raise ModelAuthorityError(
                "irreversible effects require forward repair"
            )
    elif requested_result != ROLLBACK_RESULT_FORWARD_REPAIR:
        raise ModelAuthorityError(
            f"unsupported rollback result: {requested_result}"
        )
    return ModelRollbackReceipt(
        receipt_id=receipt_id,
        contract_fingerprint=contract.fingerprint,
        reverse_revision_set_fingerprint=reverse_revision_set.fingerprint,
        result=requested_result,
        completed_evidence_fingerprints=completed,
        reason=reason,
    )



__all__ = [
    "ModelActivationReceipt",
    "RevisionAffectedClosure",
    "RevisionSnapshotDiff",
    "ModelRevisionSet",
    "ModelRollbackContract",
    "ModelRollbackEffect",
    "ModelRollbackReceipt",
    "PredictionReplayRef",
    "RevisionEvidenceRef",
    "RevisionMemberChange",
    "RevisionRemovalDisposition",
    "derive_affected_closure_fingerprint",
    "derive_revision_affected_closure",
    "derive_revision_snapshot_diff",
    "validate_activation_plan",
    "validate_operational_rollback",
    "validate_revision_set_snapshots",
]
