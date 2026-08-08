"""Internal canonical DNA relation handoff.

This module deliberately contains no model-signature builder, lexical search,
pair classifier, maintenance-group inference, review plan, report, route, or
completion claim.  Canonical owners construct exact relations from current
DNA, BCL, or affected-topology identities and consume them under their own
proof rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable


RELATION_SAME_INTENT = "same_intent"
RELATION_SHARED_OWNER = "shared_owner"
RELATION_AFFECTED_SIBLING = "affected_sibling"
RELATION_SHARED_MECHANISM = "shared_mechanism"
RELATION_ADAPTER_ONLY = "adapter_only"
RELATION_DUPLICATE_BOUNDARY = "duplicate_boundary"
RELATION_FALSE_FRIEND = "false_friend"

# Current observed-model relations may be handed through directly.  The
# consumer, not this carrier, owns the decision made from each relation.
CANONICAL_RELATION_TYPES = frozenset(
    {
        RELATION_SAME_INTENT,
        RELATION_SHARED_OWNER,
        RELATION_AFFECTED_SIBLING,
        RELATION_SHARED_MECHANISM,
        RELATION_ADAPTER_ONLY,
        RELATION_DUPLICATE_BOUNDARY,
        RELATION_FALSE_FRIEND,
        "contains",
        "refines",
        "depends_on",
        "delegates_to",
        "consumes",
        "produces_for",
        "realizes",
        "supersedes",
        "validates",
        "shares_kernel_with",
        "implements",
        "invokes",
        "affects",
    }
)


def _identifier(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string canonical identity")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty canonical identity")
    return normalized


def _identities(
    values: Sequence[str] | None,
    field_name: str,
) -> tuple[str, ...]:
    normalized = tuple(_identifier(value, field_name) for value in (values or ()))
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} contains duplicate canonical identities")
    return normalized


@dataclass(frozen=True)
class CanonicalRelation:
    """One exact current relation and the identities that establish it."""

    relation_id: str
    relation_type: str
    source_endpoint_kind: str
    source_endpoint_id: str
    target_endpoint_kind: str
    target_endpoint_id: str
    source_ids: tuple[str, ...]
    typed_commitment_relation_refs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "relation_id", _identifier(self.relation_id, "relation_id"))
        relation_type = _identifier(self.relation_type, "relation_type")
        if relation_type not in CANONICAL_RELATION_TYPES:
            raise ValueError(f"unsupported canonical relation type: {relation_type}")
        object.__setattr__(self, "relation_type", relation_type)
        object.__setattr__(
            self,
            "source_endpoint_kind",
            _identifier(self.source_endpoint_kind, "source_endpoint_kind"),
        )
        object.__setattr__(
            self,
            "source_endpoint_id",
            _identifier(self.source_endpoint_id, "source_endpoint_id"),
        )
        object.__setattr__(
            self,
            "target_endpoint_kind",
            _identifier(self.target_endpoint_kind, "target_endpoint_kind"),
        )
        object.__setattr__(
            self,
            "target_endpoint_id",
            _identifier(self.target_endpoint_id, "target_endpoint_id"),
        )
        source_endpoint = (self.source_endpoint_kind, self.source_endpoint_id)
        target_endpoint = (self.target_endpoint_kind, self.target_endpoint_id)
        if source_endpoint == target_endpoint:
            raise ValueError("canonical relation endpoints must be distinct")
        source_ids = _identities(self.source_ids, "source_ids")
        if not source_ids:
            raise ValueError("canonical relation requires at least one exact source identity")
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(
            self,
            "typed_commitment_relation_refs",
            _identities(
                self.typed_commitment_relation_refs,
                "typed_commitment_relation_refs",
            ),
        )
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "relation_type": self.relation_type,
            "source_endpoint_kind": self.source_endpoint_kind,
            "source_endpoint_id": self.source_endpoint_id,
            "target_endpoint_kind": self.target_endpoint_kind,
            "target_endpoint_id": self.target_endpoint_id,
            "source_ids": list(self.source_ids),
            "typed_commitment_relation_refs": list(
                self.typed_commitment_relation_refs
            ),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class CanonicalRelationHandoff:
    """Compact immutable input consumed directly by current canonical owners."""

    relations: tuple[CanonicalRelation | Mapping[str, Any], ...] = ()
    relation_group_ids: tuple[str, ...] = ()
    affected_model_ids: tuple[str, ...] = ()
    code_obligation_ids: tuple[str, ...] = ()
    test_obligation_ids: tuple[str, ...] = ()
    gap_ids: tuple[str, ...] = ()
    typed_commitment_relation_refs: tuple[str, ...] = ()
    evidence_current: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        relations = tuple(
            relation
            if isinstance(relation, CanonicalRelation)
            else CanonicalRelation(**dict(relation))
            for relation in self.relations
        )
        relation_ids = tuple(relation.relation_id for relation in relations)
        if len(set(relation_ids)) != len(relation_ids):
            raise ValueError("relations contain duplicate relation_id values")
        object.__setattr__(self, "relations", relations)
        for field_name in (
            "relation_group_ids",
            "affected_model_ids",
            "code_obligation_ids",
            "test_obligation_ids",
            "gap_ids",
        ):
            object.__setattr__(
                self,
                field_name,
                _identities(getattr(self, field_name), field_name),
            )
        relation_commitment_refs = tuple(
            ref
            for relation in relations
            for ref in relation.typed_commitment_relation_refs
        )
        explicit_commitment_refs = _identities(
            self.typed_commitment_relation_refs,
            "typed_commitment_relation_refs",
        )
        object.__setattr__(
            self,
            "typed_commitment_relation_refs",
            tuple(dict.fromkeys((*explicit_commitment_refs, *relation_commitment_refs))),
        )
        object.__setattr__(self, "evidence_current", bool(self.evidence_current))
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def relation_ids(self) -> tuple[str, ...]:
        return tuple(relation.relation_id for relation in self.relations)

    def relation_ids_of_type(self, *relation_types: str) -> tuple[str, ...]:
        requested = set(relation_types)
        unknown = requested - CANONICAL_RELATION_TYPES
        if unknown:
            raise ValueError(f"unsupported canonical relation types: {sorted(unknown)}")
        return tuple(
            relation.relation_id
            for relation in self.relations
            if relation.relation_type in requested
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "relations": [relation.to_dict() for relation in self.relations],
            "relation_group_ids": list(self.relation_group_ids),
            "affected_model_ids": list(self.affected_model_ids),
            "code_obligation_ids": list(self.code_obligation_ids),
            "test_obligation_ids": list(self.test_obligation_ids),
            "gap_ids": list(self.gap_ids),
            "typed_commitment_relation_refs": list(
                self.typed_commitment_relation_refs
            ),
            "evidence_current": self.evidence_current,
            "metadata": to_jsonable(dict(self.metadata)),
        }


def normalize_canonical_relation_handoff(
    value: CanonicalRelationHandoff | Mapping[str, Any] | None,
) -> CanonicalRelationHandoff | None:
    """Normalize the one direct-current handoff shape; no old schema is accepted."""

    if value is None:
        return None
    if isinstance(value, CanonicalRelationHandoff):
        return value
    return CanonicalRelationHandoff(**dict(value))


__all__ = [
    "CANONICAL_RELATION_TYPES",
    "CanonicalRelation",
    "CanonicalRelationHandoff",
    "RELATION_ADAPTER_ONLY",
    "RELATION_AFFECTED_SIBLING",
    "RELATION_DUPLICATE_BOUNDARY",
    "RELATION_FALSE_FRIEND",
    "RELATION_SAME_INTENT",
    "RELATION_SHARED_MECHANISM",
    "RELATION_SHARED_OWNER",
    "normalize_canonical_relation_handoff",
]
