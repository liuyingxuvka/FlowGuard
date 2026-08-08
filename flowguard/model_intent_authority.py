"""Single direct-current authority for cumulative model intent.

Revision-local intent contributions remain deltas.  This module folds those
deltas into one current effective view embedded in the accepted revision set.
The explicit bootstrap path audits an existing bootstrap/v4 authority lineage
but never guesses current intent from historical deltas: callers must supply
the current design contribution owned by every current model purpose.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .model_authority import (
    ModelAuthorityError,
    ModelAuthorityHead,
    ModelSystemSnapshot,
    _array,
    _id,
    _ids,
    _sha,
    _strict,
    _text,
    canonical_fingerprint,
)
from .model_intent import (
    ModelIntentContribution,
    ModelIntentDisposition,
    ModelIntentSourceIdentity,
    verify_model_intent_sources,
)
from ._wire import (
    wire_integer as _wire_integer,
    wire_string as _wire_string,
    wire_strings as _wire_strings,
)


EFFECTIVE_INTENT_TRANSITION_SCHEMA = (
    "flowguard.effective_intent_transition.v1"
)
EFFECTIVE_INTENT_OWNER_BINDING_SCHEMA = (
    "flowguard.effective_intent_owner_binding.v1"
)
LEGACY_INTENT_AUDIT_ENTRY_SCHEMA = (
    "flowguard.legacy_intent_audit_entry.v1"
)
LEGACY_INTENT_BOOTSTRAP_DISPOSITION_SCHEMA = (
    "flowguard.legacy_intent_bootstrap_disposition.v1"
)
EFFECTIVE_INTENT_BOOTSTRAP_RECEIPT_SCHEMA = (
    "flowguard.effective_intent_bootstrap_receipt.v1"
)
CURRENT_EFFECTIVE_INTENT_VIEW_SCHEMA = (
    "flowguard.current_effective_intent_view.v1"
)

EFFECTIVE_INTENT_TRANSITION_ACTIONS = frozenset(
    {"retain", "supersede", "retire"}
)
LEGACY_CURRENT_REVISION_SCHEMA = "flowguard.model_revision_set.v4"
INITIAL_AUTHORITY_BOOTSTRAP_SCHEMA = "flowguard.model_authority_bootstrap.v1"
_HISTORICAL_REVISION_SCHEMAS = frozenset(
    f"flowguard.model_revision_set.v{version}" for version in range(1, 5)
)


def _optional_sha(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    return _sha(text, field_name) if text else ""


def _wire_id_fingerprint_pair(
    value: Any,
    field_name: str,
) -> tuple[str, str]:
    data = _strict(value, field_name, ("contribution_id", "fingerprint"))
    return (
        _wire_string(data["contribution_id"], f"{field_name} contribution_id"),
        _wire_string(data["fingerprint"], f"{field_name} fingerprint"),
    )


def _strict_model_intent_contribution(
    value: Any,
) -> ModelIntentContribution:
    """Parse an intent contribution without accepting JSON scalar coercion."""

    if not isinstance(value, Mapping):
        raise ModelAuthorityError(
            "model_intent_contribution must be a JSON object"
        )
    scalar_fields = (
        "schema",
        "contribution_id",
        "source_kind",
        "source_ref",
        "source_fingerprint",
        "subject_lane",
        "subject_role",
        "lifecycle_state",
        "decision_state",
        "logical_model_id",
        "unresolved_owner_id",
        "effective_revision",
        "rationale",
        "work_context_id",
        "work_context_fingerprint",
        "native_owner_id",
        "fingerprint",
    )
    array_fields = (
        "supersedes_contribution_ids",
        "conflicts_with_contribution_ids",
        "target_obligation_ids",
        "target_state_ids",
        "target_transition_ids",
        "target_invariant_ids",
        "target_relation_ids",
        "desired_terminal_state_ids",
        "target_output_ids",
        "declared_consumer_ids",
    )
    for field_name in scalar_fields:
        if field_name in value:
            _wire_string(value[field_name], field_name)
    for field_name in array_fields:
        if field_name in value:
            _wire_strings(value[field_name], field_name)
    return ModelIntentContribution.from_dict(value)


def _strict_model_intent_disposition(
    value: Any,
) -> ModelIntentDisposition:
    """Parse an intent disposition without accepting JSON scalar coercion."""

    if not isinstance(value, Mapping):
        raise ModelAuthorityError(
            "model_intent_disposition must be a JSON object"
        )
    for field_name in (
        "schema",
        "contribution_id",
        "contribution_fingerprint",
        "disposition",
        "reason",
        "fingerprint",
    ):
        if field_name in value:
            _wire_string(value[field_name], field_name)
    for field_name in (
        "changed_obligation_ids",
        "changed_state_ids",
        "changed_transition_ids",
        "changed_invariant_ids",
        "changed_relation_ids",
        "scoped_gap_ids",
        "conflict_ids",
        "unresolved_effect_ids",
        "unreachable_terminal_state_ids",
        "unconsumed_output_ids",
    ):
        if field_name in value:
            _wire_strings(value[field_name], field_name)
    return ModelIntentDisposition.from_dict(value)


def _strict_model_intent_source_identity(
    value: Any,
) -> ModelIntentSourceIdentity:
    """Parse an intent source identity with exact JSON string types."""

    if not isinstance(value, Mapping):
        raise ModelAuthorityError(
            "model_intent_source_identity must be a JSON object"
        )
    for field_name in (
        "schema",
        "contribution_id",
        "authority_kind",
        "source_ref",
        "source_fingerprint",
        "resolved_project_ref",
        "work_context_id",
        "work_context_fingerprint",
        "native_owner_id",
        "work_context_artifact_id",
        "fingerprint",
    ):
        if field_name in value:
            _wire_string(value[field_name], field_name)
    return ModelIntentSourceIdentity.from_dict(value)


def _normalized_logical_model_id(value: str) -> str:
    model_id = _id(value, "logical_model_id")
    if model_id.startswith("model:"):
        model_id = model_id.removeprefix("model:")
    return _id(model_id, "logical_model_id")


def _sha_pairs(
    values: Iterable[tuple[str, str]],
    *,
    key_name: str,
    value_name: str,
) -> tuple[tuple[str, str], ...]:
    result = tuple(
        sorted(
            (
                _id(key, key_name),
                _sha(value, value_name),
            )
            for key, value in values
        )
    )
    keys = tuple(key for key, _value in result)
    if len(keys) != len(set(keys)):
        raise ModelAuthorityError(f"{key_name} values must be unique")
    return result


def active_intent_contribution_inventory_fingerprint(
    contributions: Iterable[ModelIntentContribution],
) -> str:
    items = tuple(sorted(contributions, key=lambda item: item.contribution_id))
    if any(not isinstance(item, ModelIntentContribution) for item in items):
        raise ModelAuthorityError(
            "effective intent inventory requires typed current contributions"
        )
    ids = tuple(item.contribution_id for item in items)
    if len(ids) != len(set(ids)):
        raise ModelAuthorityError(
            "effective intent contribution ids must be unique"
        )
    return canonical_fingerprint(
        {
            "schema": "flowguard.active_intent_contribution_inventory.v1",
            "contributions": [item.to_dict() for item in items],
        }
    )


@dataclass(frozen=True)
class EffectiveIntentTransition:
    prior_contribution_id: str
    prior_contribution_fingerprint: str
    action: str
    replacement_contribution_ids: tuple[str, ...]
    reason: str
    schema: str = EFFECTIVE_INTENT_TRANSITION_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "prior_contribution_id",
            _id(self.prior_contribution_id, "prior_contribution_id"),
        )
        object.__setattr__(
            self,
            "prior_contribution_fingerprint",
            _sha(
                self.prior_contribution_fingerprint,
                "prior_contribution_fingerprint",
            ),
        )
        if self.action not in EFFECTIVE_INTENT_TRANSITION_ACTIONS:
            raise ModelAuthorityError(
                f"unsupported effective intent transition: {self.action}"
            )
        replacements = _ids(
            self.replacement_contribution_ids,
            "replacement_contribution_id",
        )
        if self.action == "supersede" and not replacements:
            raise ModelAuthorityError(
                "supersede transition requires an explicit replacement"
            )
        if self.action != "supersede" and replacements:
            raise ModelAuthorityError(
                "retain and retire transitions cannot name replacements"
            )
        if self.prior_contribution_id in replacements:
            raise ModelAuthorityError(
                "effective intent transition cannot replace an id with itself"
            )
        object.__setattr__(self, "replacement_contribution_ids", replacements)
        object.__setattr__(
            self,
            "reason",
            _text(self.reason, "effective intent transition reason", minimum=20),
        )
        if self.schema != EFFECTIVE_INTENT_TRANSITION_SCHEMA:
            raise ModelAuthorityError(
                "effective intent transition schema must be "
                f"{EFFECTIVE_INTENT_TRANSITION_SCHEMA}"
            )

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.identity_payload())

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "prior_contribution_id": self.prior_contribution_id,
            "prior_contribution_fingerprint": (
                self.prior_contribution_fingerprint
            ),
            "action": self.action,
            "replacement_contribution_ids": list(
                self.replacement_contribution_ids
            ),
            "reason": self.reason,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: Any) -> "EffectiveIntentTransition":
        data = _strict(
            value,
            "effective_intent_transition",
            (
                "schema",
                "prior_contribution_id",
                "prior_contribution_fingerprint",
                "action",
                "replacement_contribution_ids",
                "reason",
                "fingerprint",
            ),
        )
        result = cls(
            prior_contribution_id=_wire_string(
                data["prior_contribution_id"], "prior_contribution_id"
            ),
            prior_contribution_fingerprint=_wire_string(
                data["prior_contribution_fingerprint"],
                "prior_contribution_fingerprint",
            ),
            action=_wire_string(data["action"], "transition action"),
            replacement_contribution_ids=_wire_strings(
                data["replacement_contribution_ids"],
                "replacement_contribution_ids",
            ),
            reason=_wire_string(data["reason"], "transition reason"),
            schema=_wire_string(data["schema"], "transition schema"),
        )
        if _wire_string(data["fingerprint"], "transition fingerprint") != result.fingerprint:
            raise ModelAuthorityError(
                "stale effective intent transition fingerprint"
            )
        return result


@dataclass(frozen=True)
class EffectiveIntentOwnerBinding:
    model_owner_id: str
    logical_model_id: str
    realization_relation_id: str
    realization_relation_fingerprint: str
    contribution_ids: tuple[str, ...]
    schema: str = EFFECTIVE_INTENT_OWNER_BINDING_SCHEMA

    def __post_init__(self) -> None:
        logical_model_id = _normalized_logical_model_id(self.logical_model_id)
        model_owner_id = _id(self.model_owner_id, "model_owner_id")
        expected_owner_id = f"model-obligation:{logical_model_id}"
        if model_owner_id != expected_owner_id:
            raise ModelAuthorityError(
                "effective intent owner id must be the exact model obligation: "
                f"{expected_owner_id}"
            )
        expected_relation_id = (
            f"relation:model-realizes-purpose:{logical_model_id}"
        )
        relation_id = _id(
            self.realization_relation_id,
            "realization_relation_id",
        )
        if relation_id != expected_relation_id:
            raise ModelAuthorityError(
                "effective intent owner binding must use its exact "
                f"model-realizes-purpose relation: {expected_relation_id}"
            )
        contribution_ids = _ids(
            self.contribution_ids,
            "effective_intent_contribution_id",
        )
        if not contribution_ids:
            raise ModelAuthorityError(
                "every current model owner requires at least one current design intent"
            )
        object.__setattr__(self, "logical_model_id", logical_model_id)
        object.__setattr__(self, "model_owner_id", model_owner_id)
        object.__setattr__(self, "realization_relation_id", relation_id)
        object.__setattr__(
            self,
            "realization_relation_fingerprint",
            _sha(
                self.realization_relation_fingerprint,
                "realization_relation_fingerprint",
            ),
        )
        object.__setattr__(self, "contribution_ids", contribution_ids)
        if self.schema != EFFECTIVE_INTENT_OWNER_BINDING_SCHEMA:
            raise ModelAuthorityError(
                "effective intent owner binding schema must be "
                f"{EFFECTIVE_INTENT_OWNER_BINDING_SCHEMA}"
            )

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.identity_payload())

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "model_owner_id": self.model_owner_id,
            "logical_model_id": self.logical_model_id,
            "realization_relation_id": self.realization_relation_id,
            "realization_relation_fingerprint": (
                self.realization_relation_fingerprint
            ),
            "contribution_ids": list(self.contribution_ids),
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: Any) -> "EffectiveIntentOwnerBinding":
        data = _strict(
            value,
            "effective_intent_owner_binding",
            (
                "schema",
                "model_owner_id",
                "logical_model_id",
                "realization_relation_id",
                "realization_relation_fingerprint",
                "contribution_ids",
                "fingerprint",
            ),
        )
        result = cls(
            model_owner_id=_wire_string(data["model_owner_id"], "model_owner_id"),
            logical_model_id=_wire_string(data["logical_model_id"], "logical_model_id"),
            realization_relation_id=_wire_string(
                data["realization_relation_id"], "realization_relation_id"
            ),
            realization_relation_fingerprint=_wire_string(
                data["realization_relation_fingerprint"],
                "realization_relation_fingerprint",
            ),
            contribution_ids=_wire_strings(
                data["contribution_ids"], "contribution_ids"
            ),
            schema=_wire_string(data["schema"], "owner binding schema"),
        )
        if _wire_string(data["fingerprint"], "owner binding fingerprint") != result.fingerprint:
            raise ModelAuthorityError(
                "stale effective intent owner binding fingerprint"
            )
        return result


def effective_intent_owner_binding_inventory_fingerprint(
    bindings: Iterable[EffectiveIntentOwnerBinding],
) -> str:
    items = tuple(sorted(bindings, key=lambda item: item.model_owner_id))
    if any(not isinstance(item, EffectiveIntentOwnerBinding) for item in items):
        raise ModelAuthorityError(
            "effective intent owner inventory requires typed bindings"
        )
    owner_ids = tuple(item.model_owner_id for item in items)
    if len(owner_ids) != len(set(owner_ids)):
        raise ModelAuthorityError(
            "effective intent owner binding ids must be unique"
        )
    return canonical_fingerprint(
        {
            "schema": "flowguard.effective_intent_owner_inventory.v1",
            "bindings": [item.to_dict() for item in items],
        }
    )


def _current_model_owner_relations(
    snapshot: ModelSystemSnapshot,
) -> tuple[tuple[str, str, str, str], ...]:
    if not isinstance(snapshot, ModelSystemSnapshot):
        raise ModelAuthorityError(
            "current intent denominator requires a typed candidate snapshot"
        )
    expected_relation_ids = {
        f"relation:model-realizes-purpose:{item.logical_model_id}"
        for item in snapshot.model_instances
    }
    observed = tuple(
        relation
        for relation in snapshot.relations
        if relation.relation_id.startswith("relation:model-realizes-purpose:")
    )
    observed_ids = tuple(item.relation_id for item in observed)
    if set(observed_ids) != expected_relation_ids or len(observed_ids) != len(
        expected_relation_ids
    ):
        missing = tuple(sorted(expected_relation_ids - set(observed_ids)))
        extra = tuple(sorted(set(observed_ids) - expected_relation_ids))
        raise ModelAuthorityError(
            "candidate model-owner denominator requires exactly one "
            "model-realizes-purpose relation per model; "
            f"missing={missing}, extra={extra}"
        )
    relation_by_id = {item.relation_id: item for item in observed}
    rows: list[tuple[str, str, str, str]] = []
    for instance in sorted(
        snapshot.model_instances,
        key=lambda item: item.logical_model_id,
    ):
        model_id = instance.logical_model_id
        relation_id = f"relation:model-realizes-purpose:{model_id}"
        relation = relation_by_id[relation_id]
        if (
            relation.kind != "realizes"
            or relation.source.endpoint_kind != "model_instance"
            or relation.source.endpoint_id != f"model:{model_id}"
            or relation.source.fingerprint != instance.fingerprint
            or relation.target.endpoint_kind != "parent_closure"
            or relation.target.endpoint_id != f"purpose:{model_id}"
            or relation.target.fingerprint
            != instance.purpose_closure_fingerprint
        ):
            raise ModelAuthorityError(
                "candidate model owner uses an inexact or fallback purpose "
                f"relation: {relation_id}"
            )
        rows.append(
            (
                f"model-obligation:{model_id}",
                model_id,
                relation_id,
                canonical_fingerprint(relation.to_dict()),
            )
        )
    return tuple(rows)


def derive_effective_intent_owner_bindings(
    candidate_snapshot: ModelSystemSnapshot,
    active_contributions: Iterable[ModelIntentContribution],
) -> tuple[EffectiveIntentOwnerBinding, ...]:
    contributions = tuple(
        sorted(active_contributions, key=lambda item: item.contribution_id)
    )
    if any(not isinstance(item, ModelIntentContribution) for item in contributions):
        raise ModelAuthorityError(
            "current owner bindings require typed current design contributions"
        )
    contribution_ids = tuple(item.contribution_id for item in contributions)
    if len(contribution_ids) != len(set(contribution_ids)):
        raise ModelAuthorityError(
            "current design contribution ids must be unique"
        )
    by_model: dict[str, list[str]] = {}
    for contribution in contributions:
        if contribution.decision_state != "accepted":
            raise ModelAuthorityError(
                "current effective intent contains a contribution that is not accepted: "
                f"{contribution.contribution_id}"
            )
        if contribution.unresolved_owner_id or not contribution.logical_model_id:
            raise ModelAuthorityError(
                "current effective intent requires one exact logical model owner: "
                f"{contribution.contribution_id}"
            )
        model_id = _normalized_logical_model_id(
            contribution.logical_model_id
        )
        by_model.setdefault(model_id, []).append(contribution.contribution_id)

    owner_rows = _current_model_owner_relations(candidate_snapshot)
    denominator_model_ids = {row[1] for row in owner_rows}
    foreign_model_ids = tuple(sorted(set(by_model) - denominator_model_ids))
    if foreign_model_ids:
        raise ModelAuthorityError(
            "current design intent names models outside the candidate denominator: "
            + ", ".join(foreign_model_ids)
        )
    missing_model_ids = tuple(
        sorted(denominator_model_ids - set(by_model))
    )
    if missing_model_ids:
        raise ModelAuthorityError(
            "current model owners lack a direct current design contribution: "
            + ", ".join(missing_model_ids)
        )
    return tuple(
        EffectiveIntentOwnerBinding(
            model_owner_id=owner_id,
            logical_model_id=model_id,
            realization_relation_id=relation_id,
            realization_relation_fingerprint=relation_fingerprint,
            contribution_ids=tuple(by_model[model_id]),
        )
        for owner_id, model_id, relation_id, relation_fingerprint in owner_rows
    )


@dataclass(frozen=True)
class LegacyIntentAuditEntry:
    generation: int
    revision_set_fingerprint: str
    contribution_id: str
    contribution_fingerprint: str
    schema: str = LEGACY_INTENT_AUDIT_ENTRY_SCHEMA

    def __post_init__(self) -> None:
        if (
            not isinstance(self.generation, int)
            or isinstance(self.generation, bool)
            or self.generation < 2
        ):
            raise ModelAuthorityError(
                "legacy intent audit generation must be at least two"
            )
        object.__setattr__(
            self,
            "revision_set_fingerprint",
            _sha(self.revision_set_fingerprint, "revision_set_fingerprint"),
        )
        object.__setattr__(
            self,
            "contribution_id",
            _id(self.contribution_id, "contribution_id"),
        )
        object.__setattr__(
            self,
            "contribution_fingerprint",
            _sha(
                self.contribution_fingerprint,
                "contribution_fingerprint",
            ),
        )
        if self.schema != LEGACY_INTENT_AUDIT_ENTRY_SCHEMA:
            raise ModelAuthorityError(
                "legacy intent audit entry schema must be "
                f"{LEGACY_INTENT_AUDIT_ENTRY_SCHEMA}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "generation": self.generation,
            "revision_set_fingerprint": self.revision_set_fingerprint,
            "contribution_id": self.contribution_id,
            "contribution_fingerprint": self.contribution_fingerprint,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "LegacyIntentAuditEntry":
        data = _strict(
            value,
            "legacy_intent_audit_entry",
            (
                "schema",
                "generation",
                "revision_set_fingerprint",
                "contribution_id",
                "contribution_fingerprint",
            ),
        )
        return cls(
            generation=_wire_integer(data["generation"], "legacy generation"),
            revision_set_fingerprint=_wire_string(
                data["revision_set_fingerprint"], "revision_set_fingerprint"
            ),
            contribution_id=_wire_string(data["contribution_id"], "contribution_id"),
            contribution_fingerprint=_wire_string(
                data["contribution_fingerprint"], "contribution_fingerprint"
            ),
            schema=_wire_string(data["schema"], "legacy audit entry schema"),
        )

    @property
    def identity_key(self) -> tuple[int, str, str, str]:
        return (
            self.generation,
            self.revision_set_fingerprint,
            self.contribution_id,
            self.contribution_fingerprint,
        )


@dataclass(frozen=True)
class LegacyIntentBootstrapDisposition:
    generation: int
    revision_set_fingerprint: str
    contribution_id: str
    contribution_fingerprint: str
    action: str
    replacement_contribution_ids: tuple[str, ...]
    reason: str
    schema: str = LEGACY_INTENT_BOOTSTRAP_DISPOSITION_SCHEMA

    def __post_init__(self) -> None:
        if (
            not isinstance(self.generation, int)
            or isinstance(self.generation, bool)
            or self.generation < 2
        ):
            raise ModelAuthorityError(
                "legacy intent disposition generation must be at least two"
            )
        object.__setattr__(
            self,
            "revision_set_fingerprint",
            _sha(self.revision_set_fingerprint, "revision_set_fingerprint"),
        )
        object.__setattr__(
            self,
            "contribution_id",
            _id(self.contribution_id, "contribution_id"),
        )
        object.__setattr__(
            self,
            "contribution_fingerprint",
            _sha(self.contribution_fingerprint, "contribution_fingerprint"),
        )
        if self.action not in EFFECTIVE_INTENT_TRANSITION_ACTIONS:
            raise ModelAuthorityError(
                f"unsupported legacy intent bootstrap disposition: {self.action}"
            )
        replacements = _ids(
            self.replacement_contribution_ids,
            "replacement_contribution_id",
        )
        if self.action == "supersede" and not replacements:
            raise ModelAuthorityError(
                "legacy supersession requires an explicit current-design replacement"
            )
        if self.action != "supersede" and replacements:
            raise ModelAuthorityError(
                "legacy retain and retire dispositions cannot name replacements"
            )
        if self.contribution_id in replacements:
            raise ModelAuthorityError(
                "legacy intent replacement must use a new contribution id"
            )
        object.__setattr__(self, "replacement_contribution_ids", replacements)
        object.__setattr__(
            self,
            "reason",
            _text(self.reason, "legacy intent disposition reason", minimum=20),
        )
        if self.schema != LEGACY_INTENT_BOOTSTRAP_DISPOSITION_SCHEMA:
            raise ModelAuthorityError(
                "legacy intent bootstrap disposition schema must be "
                f"{LEGACY_INTENT_BOOTSTRAP_DISPOSITION_SCHEMA}"
            )

    @property
    def identity_key(self) -> tuple[int, str, str, str]:
        return (
            self.generation,
            self.revision_set_fingerprint,
            self.contribution_id,
            self.contribution_fingerprint,
        )

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.identity_payload())

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "generation": self.generation,
            "revision_set_fingerprint": self.revision_set_fingerprint,
            "contribution_id": self.contribution_id,
            "contribution_fingerprint": self.contribution_fingerprint,
            "action": self.action,
            "replacement_contribution_ids": list(
                self.replacement_contribution_ids
            ),
            "reason": self.reason,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: Any) -> "LegacyIntentBootstrapDisposition":
        data = _strict(
            value,
            "legacy_intent_bootstrap_disposition",
            (
                "schema",
                "generation",
                "revision_set_fingerprint",
                "contribution_id",
                "contribution_fingerprint",
                "action",
                "replacement_contribution_ids",
                "reason",
                "fingerprint",
            ),
        )
        result = cls(
            generation=_wire_integer(data["generation"], "legacy disposition generation"),
            revision_set_fingerprint=_wire_string(
                data["revision_set_fingerprint"], "revision_set_fingerprint"
            ),
            contribution_id=_wire_string(data["contribution_id"], "contribution_id"),
            contribution_fingerprint=_wire_string(
                data["contribution_fingerprint"], "contribution_fingerprint"
            ),
            action=_wire_string(data["action"], "legacy disposition action"),
            replacement_contribution_ids=_wire_strings(
                data["replacement_contribution_ids"],
                "replacement_contribution_ids",
            ),
            reason=_wire_string(data["reason"], "legacy disposition reason"),
            schema=_wire_string(data["schema"], "legacy disposition schema"),
        )
        if _wire_string(data["fingerprint"], "legacy disposition fingerprint") != result.fingerprint:
            raise ModelAuthorityError(
                "stale legacy intent bootstrap disposition fingerprint"
            )
        return result


def validate_legacy_intent_bootstrap_dispositions(
    ancestry_entries: Iterable[LegacyIntentAuditEntry],
    current_design_contributions: Iterable[ModelIntentContribution],
    dispositions: Iterable[LegacyIntentBootstrapDisposition],
) -> tuple[LegacyIntentBootstrapDisposition, ...]:
    """Account explicitly for every exact historical intent delta row."""

    entries = tuple(ancestry_entries)
    if any(not isinstance(item, LegacyIntentAuditEntry) for item in entries):
        raise ModelAuthorityError(
            "legacy intent disposition validation requires typed ancestry entries"
        )
    entry_keys = tuple(item.identity_key for item in entries)
    if len(entry_keys) != len(set(entry_keys)):
        raise ModelAuthorityError(
            "legacy intent ancestry contains duplicate exact entry identities"
        )

    current = tuple(current_design_contributions)
    if any(not isinstance(item, ModelIntentContribution) for item in current):
        raise ModelAuthorityError(
            "legacy intent disposition validation requires typed current designs"
        )
    current_by_id: dict[str, ModelIntentContribution] = {}
    for contribution in current:
        if contribution.contribution_id in current_by_id:
            raise ModelAuthorityError(
                "current design contribution ids must be unique during bootstrap"
            )
        if contribution.decision_state != "accepted":
            raise ModelAuthorityError(
                "current design bootstrap contribution is not accepted: "
                f"{contribution.contribution_id}"
            )
        current_by_id[contribution.contribution_id] = contribution

    legacy_ids = {item.contribution_id for item in entries}
    current_ids = set(current_by_id)
    superseders_by_prior: dict[str, list[str]] = {}
    for contribution in current:
        unknown_supersedes = set(contribution.supersedes_contribution_ids) - legacy_ids
        if unknown_supersedes:
            raise ModelAuthorityError(
                "current design bootstrap supersedes an unknown legacy intent id: "
                + ", ".join(sorted(unknown_supersedes))
            )
        unknown_conflicts = set(contribution.conflicts_with_contribution_ids) - (
            legacy_ids | current_ids
        )
        if unknown_conflicts:
            raise ModelAuthorityError(
                "current design bootstrap conflicts with an unknown intent id: "
                + ", ".join(sorted(unknown_conflicts))
            )
        active_conflicts = set(contribution.conflicts_with_contribution_ids) & current_ids
        if active_conflicts:
            raise ModelAuthorityError(
                "current design bootstrap leaves an unresolved active conflict: "
                f"{contribution.contribution_id} -> {sorted(active_conflicts)}"
            )
        for prior_id in contribution.supersedes_contribution_ids:
            superseders_by_prior.setdefault(prior_id, []).append(
                contribution.contribution_id
            )

    normalized = tuple(
        sorted(dispositions, key=lambda item: item.identity_key)
    )
    if any(
        not isinstance(item, LegacyIntentBootstrapDisposition)
        for item in normalized
    ):
        raise ModelAuthorityError(
            "legacy intent bootstrap dispositions must be typed records"
        )
    disposition_keys = tuple(item.identity_key for item in normalized)
    if len(disposition_keys) != len(set(disposition_keys)):
        raise ModelAuthorityError(
            "legacy intent bootstrap dispositions contain a duplicate exact entry"
        )
    if set(disposition_keys) != set(entry_keys):
        missing = sorted(set(entry_keys) - set(disposition_keys))
        unknown = sorted(set(disposition_keys) - set(entry_keys))
        raise ModelAuthorityError(
            "legacy intent bootstrap disposition inventory must equal the exact "
            f"ancestry entry set; missing={missing}; unknown={unknown}"
        )

    for disposition in normalized:
        current_same_id = current_by_id.get(disposition.contribution_id)
        superseders = tuple(
            sorted(superseders_by_prior.get(disposition.contribution_id, ()))
        )
        if (
            current_same_id is not None
            and current_same_id.fingerprint
            != disposition.contribution_fingerprint
        ):
            raise ModelAuthorityError(
                "legacy intent bootstrap blocks silent contribution-id replacement: "
                f"{disposition.contribution_id}; use a new id and explicit supersession"
            )
        if disposition.action == "retain":
            if (
                current_same_id is None
                or current_same_id.fingerprint
                != disposition.contribution_fingerprint
            ):
                raise ModelAuthorityError(
                    "legacy retain disposition lacks the exact current design: "
                    f"{disposition.contribution_id}"
                )
            if superseders:
                raise ModelAuthorityError(
                    "legacy retain disposition conflicts with current superseders: "
                    f"{disposition.contribution_id} -> {list(superseders)}"
                )
        elif disposition.action == "supersede":
            replacements = tuple(
                sorted(disposition.replacement_contribution_ids)
            )
            unknown_replacements = tuple(
                item for item in replacements if item not in current_by_id
            )
            if unknown_replacements:
                raise ModelAuthorityError(
                    "legacy supersession names unknown current-design replacements: "
                    f"{list(unknown_replacements)}"
                )
            if replacements != superseders:
                raise ModelAuthorityError(
                    "legacy supersession replacements must exactly match current "
                    "designs that declare the predecessor: "
                    f"{disposition.contribution_id}; declared={list(replacements)}; "
                    f"current={list(superseders)}"
                )
            if current_same_id is not None:
                raise ModelAuthorityError(
                    "legacy supersession cannot leave the predecessor active: "
                    f"{disposition.contribution_id}"
                )
        else:
            if current_same_id is not None or superseders:
                raise ModelAuthorityError(
                    "legacy retirement conflicts with an active current design or "
                    f"replacement: {disposition.contribution_id}"
                )
    return normalized


@dataclass(frozen=True)
class EffectiveIntentBootstrapReceipt:
    receipt_id: str
    system_id: str
    expected_head_fingerprint: str
    source_snapshot_fingerprint: str
    candidate_snapshot_fingerprint: str
    source_head_generation: int
    source_revision_schema: str
    source_current_revision_set_fingerprint: str
    bootstrap_authority_fingerprint: str
    ancestry_activation_receipt_fingerprints: tuple[str, ...]
    ancestry_revision_set_fingerprints: tuple[str, ...]
    ancestry_intent_entries: tuple[LegacyIntentAuditEntry, ...]
    legacy_entry_dispositions: tuple[LegacyIntentBootstrapDisposition, ...]
    current_design_contribution_inventory_fingerprint: str
    current_design_contribution_fingerprints: tuple[tuple[str, str], ...]
    current_design_source_identity_fingerprints: tuple[tuple[str, str], ...]
    current_model_owner_ids: tuple[str, ...]
    owner_binding_inventory_fingerprint: str
    rationale: str
    claim_boundary: str
    status: str = "audited"
    schema: str = EFFECTIVE_INTENT_BOOTSTRAP_RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_id", _id(self.receipt_id, "receipt_id"))
        object.__setattr__(self, "system_id", _id(self.system_id, "system_id"))
        for name in (
            "expected_head_fingerprint",
            "source_snapshot_fingerprint",
            "candidate_snapshot_fingerprint",
            "current_design_contribution_inventory_fingerprint",
            "owner_binding_inventory_fingerprint",
        ):
            object.__setattr__(self, name, _sha(getattr(self, name), name))
        if (
            not isinstance(self.source_head_generation, int)
            or isinstance(self.source_head_generation, bool)
            or self.source_head_generation < 1
        ):
            raise ModelAuthorityError(
                "bootstrap receipt source generation must be positive"
            )
        current_revision_fingerprint = _optional_sha(
            self.source_current_revision_set_fingerprint,
            "source_current_revision_set_fingerprint",
        )
        bootstrap_fingerprint = _sha(
            self.bootstrap_authority_fingerprint,
            "bootstrap_authority_fingerprint",
        )
        activations = tuple(
            _sha(item, "ancestry_activation_receipt_fingerprint")
            for item in self.ancestry_activation_receipt_fingerprints
        )
        revisions = tuple(
            _sha(item, "ancestry_revision_set_fingerprint")
            for item in self.ancestry_revision_set_fingerprints
        )
        if len(activations) != len(set(activations)) or len(revisions) != len(
            set(revisions)
        ):
            raise ModelAuthorityError(
                "bootstrap ancestry activation and revision ids must be unique"
            )
        if len(activations) != len(revisions):
            raise ModelAuthorityError(
                "bootstrap ancestry requires one revision per activation"
            )
        if len(revisions) != self.source_head_generation - 1:
            raise ModelAuthorityError(
                "bootstrap ancestry length must match the exact source generation"
            )
        if self.source_head_generation == 1:
            if (
                self.source_revision_schema != INITIAL_AUTHORITY_BOOTSTRAP_SCHEMA
                or current_revision_fingerprint
                or revisions
            ):
                raise ModelAuthorityError(
                    "generation-one intent bootstrap must bind only the initial authority receipt"
                )
        elif (
            self.source_revision_schema != LEGACY_CURRENT_REVISION_SCHEMA
            or not current_revision_fingerprint
            or not revisions
            or revisions[0] != current_revision_fingerprint
        ):
            raise ModelAuthorityError(
                "legacy intent bootstrap must bind the exact current v4 revision"
            )
        entries = tuple(
            sorted(
                self.ancestry_intent_entries,
                key=lambda item: (
                    -item.generation,
                    item.revision_set_fingerprint,
                    item.contribution_id,
                    item.contribution_fingerprint,
                ),
            )
        )
        if any(not isinstance(item, LegacyIntentAuditEntry) for item in entries):
            raise ModelAuthorityError(
                "bootstrap ancestry intent entries must be typed audit rows"
            )
        entry_keys = tuple(item.identity_key for item in entries)
        if len(entry_keys) != len(set(entry_keys)):
            raise ModelAuthorityError(
                "bootstrap ancestry contains duplicate exact intent entries"
            )
        if any(item.revision_set_fingerprint not in revisions for item in entries):
            raise ModelAuthorityError(
                "bootstrap intent audit entry is outside the exact ancestry"
            )
        dispositions = tuple(
            sorted(
                self.legacy_entry_dispositions,
                key=lambda item: item.identity_key,
            )
        )
        if any(
            not isinstance(item, LegacyIntentBootstrapDisposition)
            for item in dispositions
        ):
            raise ModelAuthorityError(
                "bootstrap legacy intent dispositions must be typed records"
            )
        disposition_keys = tuple(item.identity_key for item in dispositions)
        if len(disposition_keys) != len(set(disposition_keys)):
            raise ModelAuthorityError(
                "bootstrap legacy intent dispositions contain duplicate exact entries"
            )
        if set(disposition_keys) != set(entry_keys):
            missing = tuple(sorted(set(entry_keys) - set(disposition_keys)))
            unknown = tuple(sorted(set(disposition_keys) - set(entry_keys)))
            raise ModelAuthorityError(
                "bootstrap legacy intent dispositions must cover the exact ancestry; "
                f"missing={missing}; unknown={unknown}"
            )
        contribution_fingerprints = _sha_pairs(
            self.current_design_contribution_fingerprints,
            key_name="current_design_contribution_id",
            value_name="current_design_contribution_fingerprint",
        )
        source_identities = _sha_pairs(
            self.current_design_source_identity_fingerprints,
            key_name="current_design_contribution_id",
            value_name="current_design_source_identity_fingerprint",
        )
        owner_ids = _ids(self.current_model_owner_ids, "current_model_owner_id")
        if not contribution_fingerprints or not source_identities or not owner_ids:
            raise ModelAuthorityError(
                "bootstrap receipt requires current designs and model owners"
            )
        if tuple(key for key, _value in contribution_fingerprints) != tuple(
            key for key, _value in source_identities
        ):
            raise ModelAuthorityError(
                "bootstrap receipt contribution and source identities must cover "
                "the same current design ids exactly"
            )
        current_fingerprint_by_id = dict(contribution_fingerprints)
        current_ids = set(current_fingerprint_by_id)
        for disposition in dispositions:
            if disposition.action == "retain":
                if (
                    current_fingerprint_by_id.get(disposition.contribution_id)
                    != disposition.contribution_fingerprint
                ):
                    raise ModelAuthorityError(
                        "bootstrap retain disposition lacks its exact current design: "
                        f"{disposition.contribution_id}"
                    )
            elif disposition.action == "supersede":
                unknown_replacements = tuple(
                    sorted(
                        set(disposition.replacement_contribution_ids)
                        - current_ids
                    )
                )
                if unknown_replacements:
                    raise ModelAuthorityError(
                        "bootstrap supersession names unknown current designs: "
                        + ", ".join(unknown_replacements)
                    )
            elif disposition.contribution_id in current_ids:
                raise ModelAuthorityError(
                    "bootstrap retirement leaves its predecessor current: "
                    f"{disposition.contribution_id}"
                )
        object.__setattr__(
            self,
            "source_current_revision_set_fingerprint",
            current_revision_fingerprint,
        )
        object.__setattr__(
            self,
            "bootstrap_authority_fingerprint",
            bootstrap_fingerprint,
        )
        object.__setattr__(
            self,
            "ancestry_activation_receipt_fingerprints",
            activations,
        )
        object.__setattr__(
            self,
            "ancestry_revision_set_fingerprints",
            revisions,
        )
        object.__setattr__(self, "ancestry_intent_entries", entries)
        object.__setattr__(self, "legacy_entry_dispositions", dispositions)
        object.__setattr__(
            self,
            "current_design_contribution_fingerprints",
            contribution_fingerprints,
        )
        object.__setattr__(
            self,
            "current_design_source_identity_fingerprints",
            source_identities,
        )
        object.__setattr__(self, "current_model_owner_ids", owner_ids)
        object.__setattr__(
            self,
            "rationale",
            _text(self.rationale, "bootstrap rationale", minimum=40),
        )
        object.__setattr__(
            self,
            "claim_boundary",
            _text(self.claim_boundary, "bootstrap claim boundary", minimum=40),
        )
        if self.status != "audited":
            raise ModelAuthorityError(
                "effective intent bootstrap receipt must be audited"
            )
        if self.schema != EFFECTIVE_INTENT_BOOTSTRAP_RECEIPT_SCHEMA:
            raise ModelAuthorityError(
                "effective intent bootstrap receipt schema must be "
                f"{EFFECTIVE_INTENT_BOOTSTRAP_RECEIPT_SCHEMA}"
            )

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.identity_payload())

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "receipt_id": self.receipt_id,
            "system_id": self.system_id,
            "expected_head_fingerprint": self.expected_head_fingerprint,
            "source_snapshot_fingerprint": self.source_snapshot_fingerprint,
            "candidate_snapshot_fingerprint": (
                self.candidate_snapshot_fingerprint
            ),
            "source_head_generation": self.source_head_generation,
            "source_revision_schema": self.source_revision_schema,
            "source_current_revision_set_fingerprint": (
                self.source_current_revision_set_fingerprint
            ),
            "bootstrap_authority_fingerprint": (
                self.bootstrap_authority_fingerprint
            ),
            "ancestry_activation_receipt_fingerprints": list(
                self.ancestry_activation_receipt_fingerprints
            ),
            "ancestry_revision_set_fingerprints": list(
                self.ancestry_revision_set_fingerprints
            ),
            "ancestry_intent_entries": [
                item.to_dict() for item in self.ancestry_intent_entries
            ],
            "legacy_entry_dispositions": [
                item.to_dict() for item in self.legacy_entry_dispositions
            ],
            "current_design_contribution_inventory_fingerprint": (
                self.current_design_contribution_inventory_fingerprint
            ),
            "current_design_contribution_fingerprints": [
                {"contribution_id": key, "fingerprint": value}
                for key, value in self.current_design_contribution_fingerprints
            ],
            "current_design_source_identity_fingerprints": [
                {"contribution_id": key, "fingerprint": value}
                for key, value in self.current_design_source_identity_fingerprints
            ],
            "current_model_owner_ids": list(self.current_model_owner_ids),
            "owner_binding_inventory_fingerprint": (
                self.owner_binding_inventory_fingerprint
            ),
            "rationale": self.rationale,
            "claim_boundary": self.claim_boundary,
            "status": self.status,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: Any) -> "EffectiveIntentBootstrapReceipt":
        data = _strict(
            value,
            "effective_intent_bootstrap_receipt",
            (
                "schema",
                "receipt_id",
                "system_id",
                "expected_head_fingerprint",
                "source_snapshot_fingerprint",
                "candidate_snapshot_fingerprint",
                "source_head_generation",
                "source_revision_schema",
                "source_current_revision_set_fingerprint",
                "bootstrap_authority_fingerprint",
                "ancestry_activation_receipt_fingerprints",
                "ancestry_revision_set_fingerprints",
                "ancestry_intent_entries",
                "legacy_entry_dispositions",
                "current_design_contribution_inventory_fingerprint",
                "current_design_contribution_fingerprints",
                "current_design_source_identity_fingerprints",
                "current_model_owner_ids",
                "owner_binding_inventory_fingerprint",
                "rationale",
                "claim_boundary",
                "status",
                "fingerprint",
            ),
        )
        result = cls(
            receipt_id=_wire_string(data["receipt_id"], "bootstrap receipt_id"),
            system_id=_wire_string(data["system_id"], "bootstrap system_id"),
            expected_head_fingerprint=_wire_string(
                data["expected_head_fingerprint"], "expected_head_fingerprint"
            ),
            source_snapshot_fingerprint=_wire_string(
                data["source_snapshot_fingerprint"], "source_snapshot_fingerprint"
            ),
            candidate_snapshot_fingerprint=_wire_string(
                data["candidate_snapshot_fingerprint"],
                "candidate_snapshot_fingerprint",
            ),
            source_head_generation=_wire_integer(
                data["source_head_generation"], "source_head_generation"
            ),
            source_revision_schema=_wire_string(
                data["source_revision_schema"], "source_revision_schema"
            ),
            source_current_revision_set_fingerprint=_wire_string(
                data["source_current_revision_set_fingerprint"],
                "source_current_revision_set_fingerprint",
            ),
            bootstrap_authority_fingerprint=_wire_string(
                data["bootstrap_authority_fingerprint"],
                "bootstrap_authority_fingerprint",
            ),
            ancestry_activation_receipt_fingerprints=_wire_strings(
                data["ancestry_activation_receipt_fingerprints"],
                "ancestry_activation_receipt_fingerprints",
            ),
            ancestry_revision_set_fingerprints=_wire_strings(
                data["ancestry_revision_set_fingerprints"],
                "ancestry_revision_set_fingerprints",
            ),
            ancestry_intent_entries=tuple(
                LegacyIntentAuditEntry.from_dict(item)
                for item in _array(
                    data["ancestry_intent_entries"],
                    "ancestry_intent_entries",
                )
            ),
            legacy_entry_dispositions=tuple(
                LegacyIntentBootstrapDisposition.from_dict(item)
                for item in _array(
                    data["legacy_entry_dispositions"],
                    "legacy_entry_dispositions",
                )
            ),
            current_design_contribution_inventory_fingerprint=_wire_string(
                data["current_design_contribution_inventory_fingerprint"],
                "current_design_contribution_inventory_fingerprint",
            ),
            current_design_contribution_fingerprints=tuple(
                _wire_id_fingerprint_pair(
                    item, "current_design_contribution_fingerprint"
                )
                for item in _array(
                    data["current_design_contribution_fingerprints"],
                    "current_design_contribution_fingerprints",
                )
            ),
            current_design_source_identity_fingerprints=tuple(
                _wire_id_fingerprint_pair(
                    item, "current_design_source_identity"
                )
                for item in _array(
                    data["current_design_source_identity_fingerprints"],
                    "current_design_source_identity_fingerprints",
                )
            ),
            current_model_owner_ids=_wire_strings(
                data["current_model_owner_ids"], "current_model_owner_ids"
            ),
            owner_binding_inventory_fingerprint=_wire_string(
                data["owner_binding_inventory_fingerprint"],
                "owner_binding_inventory_fingerprint",
            ),
            rationale=_wire_string(data["rationale"], "bootstrap rationale"),
            claim_boundary=_wire_string(
                data["claim_boundary"], "bootstrap claim_boundary"
            ),
            status=_wire_string(data["status"], "bootstrap status"),
            schema=_wire_string(data["schema"], "bootstrap schema"),
        )
        if _wire_string(data["fingerprint"], "bootstrap fingerprint") != result.fingerprint:
            raise ModelAuthorityError(
                "stale effective intent bootstrap receipt fingerprint"
            )
        return result


@dataclass(frozen=True)
class CurrentEffectiveIntentView:
    system_id: str
    subject_lane: str
    candidate_snapshot_fingerprint: str
    base_effective_intent_view_fingerprint: str
    active_contributions: tuple[ModelIntentContribution, ...]
    verified_source_identities: tuple[ModelIntentSourceIdentity, ...]
    model_owner_ids: tuple[str, ...]
    owner_bindings: tuple[EffectiveIntentOwnerBinding, ...]
    transitions: tuple[EffectiveIntentTransition, ...]
    bootstrap_receipt: EffectiveIntentBootstrapReceipt | None = None
    schema: str = CURRENT_EFFECTIVE_INTENT_VIEW_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "system_id", _id(self.system_id, "system_id"))
        object.__setattr__(
            self,
            "subject_lane",
            _id(self.subject_lane, "subject_lane"),
        )
        object.__setattr__(
            self,
            "candidate_snapshot_fingerprint",
            _sha(
                self.candidate_snapshot_fingerprint,
                "candidate_snapshot_fingerprint",
            ),
        )
        base_fingerprint = _optional_sha(
            self.base_effective_intent_view_fingerprint,
            "base_effective_intent_view_fingerprint",
        )
        if bool(base_fingerprint) == bool(self.bootstrap_receipt):
            raise ModelAuthorityError(
                "current effective intent requires exactly one base view or bootstrap receipt"
            )
        if self.bootstrap_receipt is not None and not isinstance(
            self.bootstrap_receipt,
            EffectiveIntentBootstrapReceipt,
        ):
            raise ModelAuthorityError(
                "current effective intent bootstrap must be a typed receipt"
            )
        contributions = tuple(
            sorted(
                self.active_contributions,
                key=lambda item: item.contribution_id,
            )
        )
        if not contributions or any(
            not isinstance(item, ModelIntentContribution)
            for item in contributions
        ):
            raise ModelAuthorityError(
                "current effective intent requires typed active contributions"
            )
        contribution_ids = tuple(item.contribution_id for item in contributions)
        if len(contribution_ids) != len(set(contribution_ids)):
            raise ModelAuthorityError(
                "current effective intent contribution ids must be unique"
            )
        active_id_set = set(contribution_ids)
        for contribution in contributions:
            if contribution.decision_state != "accepted":
                raise ModelAuthorityError(
                    "current effective intent contribution is not accepted: "
                    f"{contribution.contribution_id}"
                )
            active_conflicts = active_id_set & set(
                contribution.conflicts_with_contribution_ids
            )
            active_superseded = active_id_set & set(
                contribution.supersedes_contribution_ids
            )
            if active_conflicts or active_superseded:
                raise ModelAuthorityError(
                    "current effective intent contains an active conflict or superseded predecessor: "
                    f"{contribution.contribution_id}"
                )
        sources = tuple(
            sorted(
                self.verified_source_identities,
                key=lambda item: item.contribution_id,
            )
        )
        if any(not isinstance(item, ModelIntentSourceIdentity) for item in sources):
            raise ModelAuthorityError(
                "current effective intent sources must be typed identities"
            )
        if tuple(item.contribution_id for item in sources) != contribution_ids:
            raise ModelAuthorityError(
                "current effective intent sources must cover active contributions exactly"
            )
        contribution_by_id = {
            item.contribution_id: item for item in contributions
        }
        for source in sources:
            contribution = contribution_by_id[source.contribution_id]
            if (
                source.source_ref != contribution.source_ref
                or source.source_fingerprint != contribution.source_fingerprint
                or source.work_context_id != contribution.work_context_id
                or source.work_context_fingerprint
                != contribution.work_context_fingerprint
                or source.native_owner_id != contribution.native_owner_id
            ):
                raise ModelAuthorityError(
                    "current effective intent source identity does not match its contribution: "
                    f"{source.contribution_id}"
                )
        owner_ids = _ids(self.model_owner_ids, "current_model_owner_id")
        bindings = tuple(
            sorted(self.owner_bindings, key=lambda item: item.model_owner_id)
        )
        if any(not isinstance(item, EffectiveIntentOwnerBinding) for item in bindings):
            raise ModelAuthorityError(
                "current effective intent owner bindings must be typed"
            )
        if tuple(item.model_owner_id for item in bindings) != owner_ids:
            raise ModelAuthorityError(
                "current effective intent owner bindings must cover the model denominator exactly"
            )
        bound_contribution_ids = tuple(
            item_id for binding in bindings for item_id in binding.contribution_ids
        )
        if (
            set(bound_contribution_ids) != active_id_set
            or len(bound_contribution_ids) != len(active_id_set)
        ):
            raise ModelAuthorityError(
                "every active current design contribution must bind exactly one model owner"
            )
        transitions = tuple(
            sorted(
                self.transitions,
                key=lambda item: item.prior_contribution_id,
            )
        )
        if any(not isinstance(item, EffectiveIntentTransition) for item in transitions):
            raise ModelAuthorityError(
                "current effective intent transitions must be typed"
            )
        transition_ids = tuple(
            item.prior_contribution_id for item in transitions
        )
        if len(transition_ids) != len(set(transition_ids)):
            raise ModelAuthorityError(
                "current effective intent transitions require unique predecessors"
            )
        if self.bootstrap_receipt is not None:
            receipt = self.bootstrap_receipt
            validate_legacy_intent_bootstrap_dispositions(
                receipt.ancestry_intent_entries,
                contributions,
                receipt.legacy_entry_dispositions,
            )
            contribution_fingerprints = tuple(
                (item.contribution_id, item.fingerprint)
                for item in contributions
            )
            source_fingerprints = tuple(
                (item.contribution_id, item.fingerprint) for item in sources
            )
            if (
                receipt.system_id != self.system_id
                or receipt.candidate_snapshot_fingerprint
                != self.candidate_snapshot_fingerprint
                or receipt.current_design_contribution_inventory_fingerprint
                != active_intent_contribution_inventory_fingerprint(contributions)
                or receipt.current_design_contribution_fingerprints
                != contribution_fingerprints
                or receipt.current_design_source_identity_fingerprints
                != source_fingerprints
                or receipt.current_model_owner_ids != owner_ids
                or receipt.owner_binding_inventory_fingerprint
                != effective_intent_owner_binding_inventory_fingerprint(bindings)
                or transitions
            ):
                raise ModelAuthorityError(
                    "effective intent bootstrap receipt does not bind the exact current view"
                )
        object.__setattr__(
            self,
            "base_effective_intent_view_fingerprint",
            base_fingerprint,
        )
        object.__setattr__(self, "active_contributions", contributions)
        object.__setattr__(self, "verified_source_identities", sources)
        object.__setattr__(self, "model_owner_ids", owner_ids)
        object.__setattr__(self, "owner_bindings", bindings)
        object.__setattr__(self, "transitions", transitions)
        if self.schema != CURRENT_EFFECTIVE_INTENT_VIEW_SCHEMA:
            raise ModelAuthorityError(
                "current effective intent view schema must be "
                f"{CURRENT_EFFECTIVE_INTENT_VIEW_SCHEMA}"
            )

    @property
    def complete(self) -> bool:
        return True

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.identity_payload())

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "system_id": self.system_id,
            "subject_lane": self.subject_lane,
            "candidate_snapshot_fingerprint": (
                self.candidate_snapshot_fingerprint
            ),
            "base_effective_intent_view_fingerprint": (
                self.base_effective_intent_view_fingerprint
            ),
            "active_contributions": [
                item.to_dict() for item in self.active_contributions
            ],
            "verified_source_identities": [
                item.to_dict() for item in self.verified_source_identities
            ],
            "model_owner_ids": list(self.model_owner_ids),
            "owner_bindings": [item.to_dict() for item in self.owner_bindings],
            "transitions": [item.to_dict() for item in self.transitions],
            "bootstrap_receipt": (
                self.bootstrap_receipt.to_dict()
                if self.bootstrap_receipt is not None
                else None
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: Any) -> "CurrentEffectiveIntentView":
        data = _strict(
            value,
            "current_effective_intent_view",
            (
                "schema",
                "system_id",
                "subject_lane",
                "candidate_snapshot_fingerprint",
                "base_effective_intent_view_fingerprint",
                "active_contributions",
                "verified_source_identities",
                "model_owner_ids",
                "owner_bindings",
                "transitions",
                "bootstrap_receipt",
                "fingerprint",
            ),
        )
        bootstrap_value = data["bootstrap_receipt"]
        if bootstrap_value is not None and not isinstance(
            bootstrap_value,
            Mapping,
        ):
            raise ModelAuthorityError(
                "current effective intent bootstrap receipt must be an object or null"
            )
        result = cls(
            system_id=_wire_string(data["system_id"], "system_id"),
            subject_lane=_wire_string(data["subject_lane"], "subject_lane"),
            candidate_snapshot_fingerprint=_wire_string(
                data["candidate_snapshot_fingerprint"],
                "candidate_snapshot_fingerprint",
            ),
            base_effective_intent_view_fingerprint=_wire_string(
                data["base_effective_intent_view_fingerprint"],
                "base_effective_intent_view_fingerprint",
            ),
            active_contributions=tuple(
                _strict_model_intent_contribution(item)
                for item in _array(
                    data["active_contributions"],
                    "active_contributions",
                )
            ),
            verified_source_identities=tuple(
                _strict_model_intent_source_identity(item)
                for item in _array(
                    data["verified_source_identities"],
                    "verified_source_identities",
                )
            ),
            model_owner_ids=_wire_strings(
                data["model_owner_ids"], "model_owner_ids"
            ),
            owner_bindings=tuple(
                EffectiveIntentOwnerBinding.from_dict(item)
                for item in _array(data["owner_bindings"], "owner_bindings")
            ),
            transitions=tuple(
                EffectiveIntentTransition.from_dict(item)
                for item in _array(data["transitions"], "transitions")
            ),
            bootstrap_receipt=(
                EffectiveIntentBootstrapReceipt.from_dict(bootstrap_value)
                if bootstrap_value is not None
                else None
            ),
            schema=_wire_string(data["schema"], "current effective intent schema"),
        )
        if _wire_string(
            data["fingerprint"], "current effective intent fingerprint"
        ) != result.fingerprint:
            raise ModelAuthorityError(
                "stale current effective intent view fingerprint"
            )
        return result


def fold_effective_intent_contributions(
    base_view: CurrentEffectiveIntentView,
    revision_contributions: Iterable[ModelIntentContribution],
    revision_dispositions: Iterable[ModelIntentDisposition],
    transitions: Iterable[EffectiveIntentTransition],
) -> tuple[ModelIntentContribution, ...]:
    if not isinstance(base_view, CurrentEffectiveIntentView):
        raise ModelAuthorityError(
            "effective intent fold requires the exact prior current view"
        )
    delta = tuple(
        sorted(revision_contributions, key=lambda item: item.contribution_id)
    )
    dispositions = tuple(
        sorted(revision_dispositions, key=lambda item: item.contribution_id)
    )
    if any(not isinstance(item, ModelIntentContribution) for item in delta) or any(
        not isinstance(item, ModelIntentDisposition) for item in dispositions
    ):
        raise ModelAuthorityError(
            "effective intent fold requires typed revision-local intent"
        )
    delta_by_id = {item.contribution_id: item for item in delta}
    disposition_by_id = {item.contribution_id: item for item in dispositions}
    if len(delta_by_id) != len(delta) or len(disposition_by_id) != len(dispositions):
        raise ModelAuthorityError(
            "effective intent fold requires unique revision-local ids"
        )
    if set(delta_by_id) != set(disposition_by_id):
        raise ModelAuthorityError(
            "effective intent fold requires one exact disposition per revision contribution"
        )
    for contribution_id, disposition in disposition_by_id.items():
        if disposition.contribution_fingerprint != delta_by_id[contribution_id].fingerprint:
            raise ModelAuthorityError(
                "effective intent fold disposition fingerprint mismatch: "
                f"{contribution_id}"
            )
    accepted_delta = {
        contribution_id: delta_by_id[contribution_id]
        for contribution_id, disposition in disposition_by_id.items()
        if disposition.disposition == "accepted"
    }
    base_by_id = {
        item.contribution_id: item for item in base_view.active_contributions
    }
    duplicate_ids = tuple(sorted(set(base_by_id) & set(delta_by_id)))
    if duplicate_ids:
        changed_ids = tuple(
            item_id
            for item_id in duplicate_ids
            if base_by_id[item_id].fingerprint != delta_by_id[item_id].fingerprint
        )
        if changed_ids:
            raise ModelAuthorityError(
                "effective intent contribution id changed content; use a new id "
                "and explicit supersession: " + ", ".join(changed_ids)
            )
        raise ModelAuthorityError(
            "prior active intent must use retain rather than revision-local re-emission: "
            + ", ".join(duplicate_ids)
        )
    transition_items = tuple(
        sorted(transitions, key=lambda item: item.prior_contribution_id)
    )
    if any(not isinstance(item, EffectiveIntentTransition) for item in transition_items):
        raise ModelAuthorityError(
            "effective intent fold requires typed lineage transitions"
        )
    transition_by_id = {
        item.prior_contribution_id: item for item in transition_items
    }
    if len(transition_by_id) != len(transition_items):
        raise ModelAuthorityError(
            "effective intent fold transitions require unique predecessors"
        )
    if set(transition_by_id) != set(base_by_id):
        missing = tuple(sorted(set(base_by_id) - set(transition_by_id)))
        extra = tuple(sorted(set(transition_by_id) - set(base_by_id)))
        raise ModelAuthorityError(
            "every prior active intent requires retain, supersede, or retire; "
            f"missing={missing}, extra={extra}"
        )
    final_by_id: dict[str, ModelIntentContribution] = {}
    for prior_id, transition in transition_by_id.items():
        prior = base_by_id[prior_id]
        if transition.prior_contribution_fingerprint != prior.fingerprint:
            raise ModelAuthorityError(
                "effective intent transition does not bind the exact prior contribution: "
                f"{prior_id}"
            )
        if transition.action == "retain":
            final_by_id[prior_id] = prior
            continue
        if transition.action == "retire":
            continue
        for replacement_id in transition.replacement_contribution_ids:
            replacement = accepted_delta.get(replacement_id)
            if replacement is None:
                raise ModelAuthorityError(
                    "effective intent supersession requires an accepted revision-local replacement: "
                    f"{prior_id} -> {replacement_id}"
                )
            if prior_id not in replacement.supersedes_contribution_ids:
                raise ModelAuthorityError(
                    "replacement contribution does not explicitly supersede its predecessor: "
                    f"{replacement_id} -> {prior_id}"
                )
    base_ids = set(base_by_id)
    delta_ids = set(delta_by_id)
    for contribution_id, contribution in accepted_delta.items():
        prior_targets = set(contribution.supersedes_contribution_ids) & base_ids
        expected_prior_targets = {
            prior_id
            for prior_id, transition in transition_by_id.items()
            if contribution_id in transition.replacement_contribution_ids
        }
        if prior_targets != expected_prior_targets:
            raise ModelAuthorityError(
                "accepted replacement and prior transition lineage disagree: "
                f"{contribution_id}"
            )
        if contribution.supersedes_contribution_ids and not prior_targets:
            local_targets = set(contribution.supersedes_contribution_ids) & delta_ids
            unknown_targets = set(contribution.supersedes_contribution_ids) - (
                base_ids | delta_ids
            )
            if unknown_targets:
                raise ModelAuthorityError(
                    "accepted contribution supersedes an unknown lineage id: "
                    + ", ".join(sorted(unknown_targets))
                )
            if local_targets:
                local_rows = {
                    item_id: disposition_by_id[item_id].disposition
                    for item_id in local_targets
                }
                if any(value != "superseded" for value in local_rows.values()):
                    raise ModelAuthorityError(
                        "revision-local supersession target is not disposed as superseded: "
                        f"{contribution_id}"
                    )
        final_by_id[contribution_id] = contribution
    active_ids = set(final_by_id)
    for contribution in final_by_id.values():
        if active_ids & set(contribution.conflicts_with_contribution_ids):
            raise ModelAuthorityError(
                "effective intent fold leaves an active conflict: "
                f"{contribution.contribution_id}"
            )
        if active_ids & set(contribution.supersedes_contribution_ids):
            raise ModelAuthorityError(
                "effective intent fold leaves a superseded predecessor active: "
                f"{contribution.contribution_id}"
            )
    return tuple(sorted(final_by_id.values(), key=lambda item: item.contribution_id))


def _reject_duplicate_json_keys(
    pairs: Iterable[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ModelAuthorityError(
                f"duplicate JSON key in intent ancestry artifact: {key}"
            )
        result[key] = value
    return result


def _read_json(path: Path, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=lambda item: (_ for _ in ()).throw(
                ModelAuthorityError(f"non-finite JSON number: {item}")
            ),
        )
    except (OSError, json.JSONDecodeError, ModelAuthorityError) as exc:
        raise ModelAuthorityError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise ModelAuthorityError(f"{label} must be a JSON object")
    return value


def _verify_content_addressed_payload(
    path: Path,
    payload: Mapping[str, Any],
    *,
    label: str,
    derived_fields: Iterable[str],
) -> str:
    expected = "sha256:" + path.stem
    if payload.get("fingerprint") != expected:
        raise ModelAuthorityError(
            f"{label} fingerprint does not match its content-addressed path"
        )
    identity = {
        key: value
        for key, value in payload.items()
        if key not in set(derived_fields)
    }
    if canonical_fingerprint(identity) != expected:
        raise ModelAuthorityError(f"{label} content fingerprint is stale")
    return expected


@dataclass(frozen=True)
class _BootstrapSourceAudit:
    source_revision_schema: str
    source_current_revision_set_fingerprint: str
    bootstrap_authority_fingerprint: str
    ancestry_activation_receipt_fingerprints: tuple[str, ...]
    ancestry_revision_set_fingerprints: tuple[str, ...]
    ancestry_intent_entries: tuple[LegacyIntentAuditEntry, ...]


_HISTORICAL_REVISION_V1_FIELDS = frozenset(
    {
        "schema",
        "revision_set_id",
        "task_id",
        "expected_head_fingerprint",
        "base_snapshot_fingerprint",
        "candidate_snapshot_fingerprint",
        "members",
        "affected_closure_ids",
        "affected_closure_fingerprint",
        "changed_relation_ids",
        "changed_source_surface_ids",
        "changed_commitment_ids",
        "changed_field_ids",
        "changed_side_effect_ids",
        "changed_contract_ids",
        "changed_test_ids",
        "changed_system_property_ids",
        "required_evidence_refs",
        "completed_evidence_refs",
        "prediction_replay_refs",
        "implementation_bundle_fingerprint",
        "rollback_contract_fingerprint",
        "status",
        "decision_reason",
        "evidence_complete",
        "fingerprint",
    }
)
_HISTORICAL_REVISION_V2_ADDITIONS = frozenset(
    {
        "affected_edge_ids",
        "affected_owner_bindings",
        "snapshot_diff_fingerprint",
        "changed_root_ids",
        "changed_coverage_ids",
        "changed_gap_ids",
        "changed_owner_artifact_ids",
        "added_ids",
        "removed_ids",
        "fingerprint_changed_ids",
        "removal_dispositions",
        "originating_revision_set_fingerprint",
        "originating_activation_receipt_fingerprint",
    }
)
_HISTORICAL_REVISION_V3_ADDITIONS = frozenset(
    {
        "intent_contributions",
        "intent_dispositions",
        "intent_contribution_inventory_fingerprint",
        "intent_conflict_ids",
        "intent_unresolved_ids",
        "intent_acceptance_ready",
    }
)
_HISTORICAL_REVISION_V4_ADDITIONS = frozenset(
    {
        "no_declared_intent_rationale_id",
        "no_declared_intent_evidence_fingerprints",
        "no_declared_intent_rationale",
    }
)
_HISTORICAL_REVISION_FIELDS = {
    "flowguard.model_revision_set.v1": _HISTORICAL_REVISION_V1_FIELDS,
    "flowguard.model_revision_set.v2": (
        _HISTORICAL_REVISION_V1_FIELDS
        | _HISTORICAL_REVISION_V2_ADDITIONS
    ),
    "flowguard.model_revision_set.v3": (
        _HISTORICAL_REVISION_V1_FIELDS
        | _HISTORICAL_REVISION_V2_ADDITIONS
        | _HISTORICAL_REVISION_V3_ADDITIONS
    ),
    "flowguard.model_revision_set.v4": (
        _HISTORICAL_REVISION_V1_FIELDS
        | _HISTORICAL_REVISION_V2_ADDITIONS
        | _HISTORICAL_REVISION_V3_ADDITIONS
        | _HISTORICAL_REVISION_V4_ADDITIONS
    ),
}
_HISTORICAL_BOOLEAN_FIELDS = frozenset(
    {"current", "eligible", "evidence_complete", "intent_acceptance_ready"}
)


def _validate_historical_wire_value(
    value: Any,
    *,
    field_name: str,
) -> None:
    if field_name in _HISTORICAL_BOOLEAN_FIELDS:
        if not isinstance(value, bool):
            raise ModelAuthorityError(
                f"historical {field_name} must be a JSON boolean"
            )
        return
    if isinstance(value, Mapping):
        for child_name, child_value in value.items():
            _validate_historical_wire_value(
                child_value,
                field_name=child_name,
            )
        return
    if isinstance(value, list):
        for item in value:
            if isinstance(item, Mapping):
                _validate_historical_wire_value(
                    item,
                    field_name=field_name,
                )
            elif not isinstance(item, str):
                raise ModelAuthorityError(
                    f"historical {field_name} items must be JSON strings or objects"
                )
        return
    if not isinstance(value, str):
        raise ModelAuthorityError(
            f"historical {field_name} must be a JSON string, array, or object"
        )


def _validate_historical_revision_payload(
    payload: Mapping[str, Any],
    *,
    generation: int,
) -> str:
    schema = payload.get("schema")
    if not isinstance(schema, str) or schema not in _HISTORICAL_REVISION_FIELDS:
        raise ModelAuthorityError(
            "explicit intent migration accepts only historical revision schemas v1-v4"
        )
    expected_fields = _HISTORICAL_REVISION_FIELDS[schema]
    missing = expected_fields - set(payload)
    unknown = set(payload) - expected_fields
    if missing or unknown:
        raise ModelAuthorityError(
            f"historical revision generation {generation} has a non-exact shape; "
            f"missing={sorted(missing)}; unknown={sorted(unknown)}"
        )
    for field_name, value in payload.items():
        _validate_historical_wire_value(value, field_name=field_name)
    if payload["status"] != "accepted" or payload["evidence_complete"] is not True:
        raise ModelAuthorityError(
            f"historical revision generation {generation} is not accepted with complete evidence"
        )
    if (
        "intent_acceptance_ready" in payload
        and payload["intent_acceptance_ready"] is not True
    ):
        raise ModelAuthorityError(
            f"historical revision generation {generation} has unresolved intent"
        )
    for raw_contribution in payload.get("intent_contributions", ()):
        _strict_model_intent_contribution(raw_contribution)
    for raw_disposition in payload.get("intent_dispositions", ()):
        _strict_model_intent_disposition(raw_disposition)
    return schema


def _bootstrap_source_audit(
    root: Path,
    head: ModelAuthorityHead,
    snapshot: ModelSystemSnapshot,
) -> _BootstrapSourceAudit:
    mesh_root = root / ".flowguard" / "model-mesh"
    if (
        snapshot.fingerprint != head.snapshot_fingerprint
        or snapshot.system_id != head.system_id
        or snapshot.subject_revision != head.subject_revision
    ):
        raise ModelAuthorityError(
            "legacy bootstrap audit snapshot does not match the authority head"
        )

    def bootstrap_head_from_path(path: Path) -> ModelAuthorityHead:
        payload = _read_json(path, "model authority bootstrap")
        fingerprint = _verify_content_addressed_payload(
            path,
            payload,
            label="model authority bootstrap",
            derived_fields=("fingerprint",),
        )
        required = {
            "schema",
            "system_id",
            "snapshot_fingerprint",
            "subject_revision",
            "evidence_fingerprint",
            "claim_boundary",
            "fingerprint",
        }
        if set(payload) != required or any(
            not isinstance(payload[name], str) for name in required
        ):
            raise ModelAuthorityError(
                "generation-one bootstrap has an invalid wire shape"
            )
        if (
            payload["schema"] != INITIAL_AUTHORITY_BOOTSTRAP_SCHEMA
            or payload["system_id"] != head.system_id
        ):
            raise ModelAuthorityError(
                "generation-one bootstrap belongs to another authority"
            )
        _sha(payload["snapshot_fingerprint"], "bootstrap snapshot fingerprint")
        _sha(payload["evidence_fingerprint"], "bootstrap evidence fingerprint")
        return ModelAuthorityHead(
            system_id=payload["system_id"],
            snapshot_fingerprint=payload["snapshot_fingerprint"],
            subject_revision=payload["subject_revision"],
            generation=1,
            accepted_revision_set_fingerprint=fingerprint,
            previous_snapshot_fingerprint="",
            activation_receipt_fingerprint=fingerprint,
        )

    if head.generation == 1:
        fingerprint = head.accepted_revision_set_fingerprint
        if head.activation_receipt_fingerprint != fingerprint:
            raise ModelAuthorityError(
                "generation-one authority must bind one bootstrap fingerprint"
            )
        path = mesh_root / "bootstraps" / f"{fingerprint.split(':', 1)[1]}.json"
        bootstrap_head = bootstrap_head_from_path(path)
        if bootstrap_head != head:
            raise ModelAuthorityError(
                "generation-one bootstrap does not match current model authority"
            )
        return _BootstrapSourceAudit(
            source_revision_schema=INITIAL_AUTHORITY_BOOTSTRAP_SCHEMA,
            source_current_revision_set_fingerprint="",
            bootstrap_authority_fingerprint=fingerprint,
            ancestry_activation_receipt_fingerprints=(),
            ancestry_revision_set_fingerprints=(),
            ancestry_intent_entries=(),
        )

    from .model_revision_set import (
        ModelActivationReceipt,
        ModelRollbackContract,
        ModelRollbackReceipt,
    )

    activation_root = mesh_root / "activations"
    rollback_root = mesh_root / "rollbacks"
    contract_root = mesh_root / "rollback-contracts"
    revision_root = mesh_root / "revisions"
    snapshot_root = mesh_root / "snapshots"

    def load_activation(
        path: Path,
    ) -> tuple[str, ModelActivationReceipt]:
        payload = _read_json(path, "activation receipt")
        fingerprint = _verify_content_addressed_payload(
            path,
            payload,
            label="activation receipt",
            derived_fields=("fingerprint",),
        )
        receipt = ModelActivationReceipt.from_dict(
            {
                key: value
                for key, value in payload.items()
                if key != "fingerprint"
            }
        )
        if receipt.fingerprint != fingerprint:
            raise ModelAuthorityError("activation receipt fingerprint is stale")
        return fingerprint, receipt

    def load_rollback_contract(
        fingerprint: str,
    ) -> ModelRollbackContract:
        path = contract_root / f"{fingerprint.split(':', 1)[1]}.json"
        payload = _read_json(path, "rollback contract")
        verified = _verify_content_addressed_payload(
            path,
            payload,
            label="rollback contract",
            derived_fields=("fingerprint",),
        )
        contract = ModelRollbackContract.from_dict(
            {
                key: value
                for key, value in payload.items()
                if key != "fingerprint"
            }
        )
        if contract.fingerprint != verified:
            raise ModelAuthorityError("rollback contract fingerprint is stale")
        return contract

    def load_rollback(
        path: Path,
    ) -> tuple[str, ModelRollbackReceipt, ModelRollbackContract]:
        payload = _read_json(path, "rollback receipt")
        fingerprint = _verify_content_addressed_payload(
            path,
            payload,
            label="rollback receipt",
            derived_fields=("fingerprint",),
        )
        receipt = ModelRollbackReceipt.from_dict(
            {
                key: value
                for key, value in payload.items()
                if key != "fingerprint"
            }
        )
        if receipt.fingerprint != fingerprint:
            raise ModelAuthorityError("rollback receipt fingerprint is stale")
        return fingerprint, receipt, load_rollback_contract(
            receipt.contract_fingerprint
        )

    def load_snapshot(fingerprint: str) -> ModelSystemSnapshot:
        path = snapshot_root / f"{fingerprint.split(':', 1)[1]}.json"
        loaded = ModelSystemSnapshot.from_dict(
            _read_json(path, "authority ancestry snapshot")
        )
        if loaded.fingerprint != fingerprint:
            raise ModelAuthorityError(
                "authority ancestry snapshot fingerprint is stale"
            )
        return loaded

    def activation_head(
        fingerprint: str,
        receipt: ModelActivationReceipt,
    ) -> ModelAuthorityHead:
        return ModelAuthorityHead(
            system_id=receipt.system_id,
            snapshot_fingerprint=receipt.candidate_snapshot_fingerprint,
            subject_revision=receipt.subject_revision,
            generation=receipt.next_generation,
            accepted_revision_set_fingerprint=(
                receipt.revision_set_fingerprint
            ),
            previous_snapshot_fingerprint=(
                receipt.previous_snapshot_fingerprint
            ),
            activation_receipt_fingerprint=fingerprint,
        )

    def rollback_head(
        fingerprint: str,
        receipt: ModelRollbackReceipt,
        contract: ModelRollbackContract,
        generation: int,
    ) -> ModelAuthorityHead:
        target = load_snapshot(contract.to_snapshot_fingerprint)
        return ModelAuthorityHead(
            system_id=target.system_id,
            snapshot_fingerprint=target.fingerprint,
            subject_revision=target.subject_revision,
            generation=generation,
            accepted_revision_set_fingerprint=(
                receipt.reverse_revision_set_fingerprint
            ),
            previous_snapshot_fingerprint=contract.from_snapshot_fingerprint,
            activation_receipt_fingerprint=fingerprint,
        )

    def load_transition(
        fingerprint: str,
        generation: int,
    ) -> tuple[
        str,
        ModelAuthorityHead,
        ModelActivationReceipt | ModelRollbackReceipt,
        ModelRollbackContract | None,
    ]:
        digest = fingerprint.split(":", 1)[1]
        activation_path = activation_root / f"{digest}.json"
        rollback_path = rollback_root / f"{digest}.json"
        present = tuple(
            kind
            for kind, path in (
                ("activation", activation_path),
                ("rollback", rollback_path),
            )
            if path.is_file()
        )
        if len(present) != 1:
            raise ModelAuthorityError(
                "authority ancestry requires exactly one typed transition receipt"
            )
        if present[0] == "activation":
            verified, receipt = load_activation(activation_path)
            return (
                "activation",
                activation_head(verified, receipt),
                receipt,
                None,
            )
        verified, receipt, contract = load_rollback(rollback_path)
        return (
            "rollback",
            rollback_head(verified, receipt, contract, generation),
            receipt,
            contract,
        )

    def exact_predecessor(
        *,
        generation: int,
        expected_fingerprint: str,
    ) -> ModelAuthorityHead:
        matches: list[ModelAuthorityHead] = []
        if generation == 1:
            for path in (mesh_root / "bootstraps").glob("*.json"):
                try:
                    candidate = bootstrap_head_from_path(path)
                except ModelAuthorityError:
                    continue
                if candidate.fingerprint == expected_fingerprint:
                    matches.append(candidate)
        else:
            for path in activation_root.glob("*.json"):
                try:
                    fingerprint, receipt = load_activation(path)
                    if receipt.next_generation != generation:
                        continue
                    candidate = activation_head(fingerprint, receipt)
                except ModelAuthorityError:
                    continue
                if candidate.fingerprint == expected_fingerprint:
                    matches.append(candidate)
            for path in rollback_root.glob("*.json"):
                try:
                    fingerprint, receipt, contract = load_rollback(path)
                    candidate = rollback_head(
                        fingerprint,
                        receipt,
                        contract,
                        generation,
                    )
                except ModelAuthorityError:
                    continue
                if candidate.fingerprint == expected_fingerprint:
                    matches.append(candidate)
        if len(matches) != 1:
            raise ModelAuthorityError(
                "current transition ancestry is missing or ambiguous at "
                f"generation {generation}"
            )
        return matches[0]

    def load_revision(
        fingerprint: str,
        generation: int,
    ) -> tuple[Mapping[str, Any], str]:
        path = revision_root / f"{fingerprint.split(':', 1)[1]}.json"
        payload = _read_json(path, f"revision generation {generation}")
        _verify_content_addressed_payload(
            path,
            payload,
            label=f"revision generation {generation}",
            derived_fields=(
                "fingerprint",
                "evidence_complete",
                "intent_acceptance_ready",
            ),
        )
        return payload, _validate_historical_revision_payload(
            payload,
            generation=generation,
        )

    transitions: list[str] = []
    revisions: list[str] = []
    entries: list[LegacyIntentAuditEntry] = []
    cursor_head = head
    bootstrap_fingerprint = ""
    current_revision_schema = ""

    for generation in range(head.generation, 1, -1):
        (
            transition_kind,
            produced_head,
            transition_receipt,
            rollback_contract,
        ) = load_transition(
            cursor_head.activation_receipt_fingerprint,
            generation,
        )
        if produced_head != cursor_head:
            raise ModelAuthorityError(
                f"transition generation {generation} does not produce the exact authority head"
            )
        revision_fingerprint = cursor_head.accepted_revision_set_fingerprint
        revision_payload, revision_schema = load_revision(
            revision_fingerprint,
            generation,
        )
        if generation == head.generation:
            current_revision_schema = revision_schema
            if current_revision_schema != LEGACY_CURRENT_REVISION_SCHEMA:
                raise ModelAuthorityError(
                    "explicit intent migration requires the current head to reference v4"
                )
        if (
            revision_payload["candidate_snapshot_fingerprint"]
            != cursor_head.snapshot_fingerprint
            or revision_payload["base_snapshot_fingerprint"]
            != cursor_head.previous_snapshot_fingerprint
        ):
            raise ModelAuthorityError(
                f"revision generation {generation} is not bound to its transition"
            )
        if transition_kind == "activation":
            if not isinstance(transition_receipt, ModelActivationReceipt):
                raise ModelAuthorityError("typed activation receipt was lost")
            expected_predecessor_fingerprint = (
                transition_receipt.expected_head_fingerprint
            )
            if (
                transition_receipt.revision_set_fingerprint
                != revision_fingerprint
                or revision_payload["expected_head_fingerprint"]
                != expected_predecessor_fingerprint
            ):
                raise ModelAuthorityError(
                    f"activation generation {generation} is not bound to its revision"
                )
        else:
            if (
                not isinstance(transition_receipt, ModelRollbackReceipt)
                or rollback_contract is None
            ):
                raise ModelAuthorityError("typed rollback receipt was lost")
            expected_predecessor_fingerprint = (
                rollback_contract.expected_head_fingerprint
            )
            if (
                transition_receipt.reverse_revision_set_fingerprint
                != revision_fingerprint
                or transition_receipt.result == "forward_repair"
                or tuple(transition_receipt.completed_evidence_fingerprints)
                != rollback_contract.required_evidence_fingerprints
                or rollback_contract.from_snapshot_fingerprint
                != cursor_head.previous_snapshot_fingerprint
                or rollback_contract.to_snapshot_fingerprint
                != cursor_head.snapshot_fingerprint
                or revision_payload["expected_head_fingerprint"]
                != expected_predecessor_fingerprint
                or revision_payload["rollback_contract_fingerprint"]
                != rollback_contract.fingerprint
                or revision_payload[
                    "originating_revision_set_fingerprint"
                ]
                != rollback_contract.originating_revision_set_fingerprint
                or revision_payload[
                    "originating_activation_receipt_fingerprint"
                ]
                != rollback_contract.originating_activation_receipt_fingerprint
            ):
                raise ModelAuthorityError(
                    f"rollback generation {generation} is not bound to its revision and contract"
                )
            if (
                transition_receipt.result == "exact"
                and not rollback_contract.exact_rollback_possible
            ) or (
                transition_receipt.result == "compensated"
                and any(
                    effect.disposition == "irreversible"
                    for effect in rollback_contract.effects
                )
            ):
                raise ModelAuthorityError(
                    f"rollback generation {generation} overclaims its result"
                )
        for raw_contribution in revision_payload.get(
            "intent_contributions",
            (),
        ):
            contribution = _strict_model_intent_contribution(raw_contribution)
            entries.append(
                LegacyIntentAuditEntry(
                    generation=generation,
                    revision_set_fingerprint=revision_fingerprint,
                    contribution_id=contribution.contribution_id,
                    contribution_fingerprint=contribution.fingerprint,
                )
            )
        transitions.append(cursor_head.activation_receipt_fingerprint)
        revisions.append(revision_fingerprint)
        predecessor = exact_predecessor(
            generation=generation - 1,
            expected_fingerprint=expected_predecessor_fingerprint,
        )
        if (
            predecessor.snapshot_fingerprint
            != cursor_head.previous_snapshot_fingerprint
        ):
            raise ModelAuthorityError(
                f"transition generation {generation} predecessor snapshot is stale"
            )
        if rollback_contract is not None and (
            rollback_contract.originating_revision_set_fingerprint
            != predecessor.accepted_revision_set_fingerprint
            or rollback_contract.originating_activation_receipt_fingerprint
            != predecessor.activation_receipt_fingerprint
        ):
            raise ModelAuthorityError(
                f"rollback generation {generation} origin is not the exact predecessor"
            )
        cursor_head = predecessor
        if generation == 2:
            bootstrap_fingerprint = predecessor.accepted_revision_set_fingerprint

    if (
        transitions[0] != head.activation_receipt_fingerprint
        or revisions[0] != head.accepted_revision_set_fingerprint
    ):
        raise ModelAuthorityError(
            "legacy intent ancestry does not begin at the current authority head"
        )
    return _BootstrapSourceAudit(
        source_revision_schema=current_revision_schema,
        source_current_revision_set_fingerprint=revisions[0],
        bootstrap_authority_fingerprint=bootstrap_fingerprint,
        ancestry_activation_receipt_fingerprints=tuple(transitions),
        ancestry_revision_set_fingerprints=tuple(revisions),
        ancestry_intent_entries=tuple(entries),
    )


def _build_current_intent_bootstrap_receipt_from_source(
    root: str | Path,
    *,
    source_head: ModelAuthorityHead,
    source_snapshot: ModelSystemSnapshot,
    receipt_id: str,
    candidate_snapshot: ModelSystemSnapshot,
    current_design_contributions: Iterable[ModelIntentContribution],
    verified_source_identities: Iterable[ModelIntentSourceIdentity] | None = None,
    rationale: str,
    legacy_entry_dispositions: Iterable[
        LegacyIntentBootstrapDisposition
    ] = (),
    claim_boundary: str = (
        "This receipt proves exact ancestry audit and current design coverage "
        "for one explicit migration; historical deltas are not current intent."
    ),
) -> EffectiveIntentBootstrapReceipt:
    """Build one receipt from an already selected exact source authority."""

    root_path = Path(root).resolve()
    contributions = tuple(
        sorted(
            current_design_contributions,
            key=lambda item: item.contribution_id,
        )
    )
    sources = (
        tuple(verified_source_identities)
        if verified_source_identities is not None
        else verify_model_intent_sources(root_path, contributions)
    )
    bindings = derive_effective_intent_owner_bindings(
        candidate_snapshot,
        contributions,
    )
    if (
        candidate_snapshot.system_id != source_head.system_id
        or candidate_snapshot.subject_lane != source_snapshot.subject_lane
    ):
        raise ModelAuthorityError(
            "intent bootstrap candidate belongs to another model authority"
        )
    audit = _bootstrap_source_audit(root_path, source_head, source_snapshot)
    validated_dispositions = validate_legacy_intent_bootstrap_dispositions(
        audit.ancestry_intent_entries,
        contributions,
        legacy_entry_dispositions,
    )
    return EffectiveIntentBootstrapReceipt(
        receipt_id=receipt_id,
        system_id=source_head.system_id,
        expected_head_fingerprint=source_head.fingerprint,
        source_snapshot_fingerprint=source_snapshot.fingerprint,
        candidate_snapshot_fingerprint=candidate_snapshot.fingerprint,
        source_head_generation=source_head.generation,
        source_revision_schema=audit.source_revision_schema,
        source_current_revision_set_fingerprint=(
            audit.source_current_revision_set_fingerprint
        ),
        bootstrap_authority_fingerprint=(
            audit.bootstrap_authority_fingerprint
        ),
        ancestry_activation_receipt_fingerprints=(
            audit.ancestry_activation_receipt_fingerprints
        ),
        ancestry_revision_set_fingerprints=(
            audit.ancestry_revision_set_fingerprints
        ),
        ancestry_intent_entries=audit.ancestry_intent_entries,
        legacy_entry_dispositions=validated_dispositions,
        current_design_contribution_inventory_fingerprint=(
            active_intent_contribution_inventory_fingerprint(contributions)
        ),
        current_design_contribution_fingerprints=tuple(
            (item.contribution_id, item.fingerprint)
            for item in contributions
        ),
        current_design_source_identity_fingerprints=tuple(
            (item.contribution_id, item.fingerprint) for item in sources
        ),
        current_model_owner_ids=tuple(
            item.model_owner_id for item in bindings
        ),
        owner_binding_inventory_fingerprint=(
            effective_intent_owner_binding_inventory_fingerprint(bindings)
        ),
        rationale=rationale,
        claim_boundary=claim_boundary,
    )


def build_current_intent_bootstrap_receipt(
    root: str | Path,
    *,
    receipt_id: str,
    candidate_snapshot: ModelSystemSnapshot,
    current_design_contributions: Iterable[ModelIntentContribution],
    rationale: str,
    legacy_entry_dispositions: Iterable[
        LegacyIntentBootstrapDisposition
    ] = (),
    claim_boundary: str = (
        "This receipt proves exact ancestry audit and current design coverage "
        "for one explicit migration; historical deltas are not current intent."
    ),
) -> EffectiveIntentBootstrapReceipt:
    """Audit the exact current bootstrap/v4 lineage and bind current designs.

    This is the only public helper allowed to read a v4 current revision for
    intent migration.  It does not derive active intent from historical deltas.
    """

    root_path = Path(root).resolve()
    from .model_authority_store import load_observed_model_system

    source_head, source_snapshot = load_observed_model_system(root_path)
    return _build_current_intent_bootstrap_receipt_from_source(
        root_path,
        source_head=source_head,
        source_snapshot=source_snapshot,
        receipt_id=receipt_id,
        candidate_snapshot=candidate_snapshot,
        current_design_contributions=current_design_contributions,
        rationale=rationale,
        legacy_entry_dispositions=legacy_entry_dispositions,
        claim_boundary=claim_boundary,
    )


def bootstrap_current_effective_intent_view(
    candidate_snapshot: ModelSystemSnapshot,
    active_contributions: Iterable[ModelIntentContribution],
    verified_source_identities: Iterable[ModelIntentSourceIdentity],
    bootstrap_receipt: EffectiveIntentBootstrapReceipt,
) -> CurrentEffectiveIntentView:
    contributions = tuple(active_contributions)
    sources = tuple(verified_source_identities)
    bindings = derive_effective_intent_owner_bindings(
        candidate_snapshot,
        contributions,
    )
    return CurrentEffectiveIntentView(
        system_id=candidate_snapshot.system_id,
        subject_lane=candidate_snapshot.subject_lane,
        candidate_snapshot_fingerprint=candidate_snapshot.fingerprint,
        base_effective_intent_view_fingerprint="",
        active_contributions=contributions,
        verified_source_identities=sources,
        model_owner_ids=tuple(item.model_owner_id for item in bindings),
        owner_bindings=bindings,
        transitions=(),
        bootstrap_receipt=bootstrap_receipt,
    )


def build_current_effective_intent_view(
    base_view: CurrentEffectiveIntentView,
    candidate_snapshot: ModelSystemSnapshot,
    active_contributions: Iterable[ModelIntentContribution],
    verified_source_identities: Iterable[ModelIntentSourceIdentity],
    transitions: Iterable[EffectiveIntentTransition],
) -> CurrentEffectiveIntentView:
    if not isinstance(base_view, CurrentEffectiveIntentView):
        raise ModelAuthorityError(
            "current effective intent construction requires a typed base view"
        )
    contributions = tuple(active_contributions)
    bindings = derive_effective_intent_owner_bindings(
        candidate_snapshot,
        contributions,
    )
    return CurrentEffectiveIntentView(
        system_id=candidate_snapshot.system_id,
        subject_lane=candidate_snapshot.subject_lane,
        candidate_snapshot_fingerprint=candidate_snapshot.fingerprint,
        base_effective_intent_view_fingerprint=base_view.fingerprint,
        active_contributions=contributions,
        verified_source_identities=tuple(verified_source_identities),
        model_owner_ids=tuple(item.model_owner_id for item in bindings),
        owner_bindings=bindings,
        transitions=tuple(transitions),
    )


def validate_current_effective_intent_view(
    candidate_snapshot: ModelSystemSnapshot,
    view: CurrentEffectiveIntentView,
) -> None:
    if not isinstance(view, CurrentEffectiveIntentView):
        raise ModelAuthorityError(
            "candidate revision lacks a typed current effective intent view"
        )
    if (
        view.system_id != candidate_snapshot.system_id
        or view.subject_lane != candidate_snapshot.subject_lane
        or view.candidate_snapshot_fingerprint != candidate_snapshot.fingerprint
    ):
        raise ModelAuthorityError(
            "current effective intent view does not match the candidate snapshot"
        )
    expected_bindings = derive_effective_intent_owner_bindings(
        candidate_snapshot,
        view.active_contributions,
    )
    if (
        view.owner_bindings != expected_bindings
        or view.model_owner_ids
        != tuple(item.model_owner_id for item in expected_bindings)
    ):
        raise ModelAuthorityError(
            "current effective intent owner denominator or binding is stale"
        )


def validate_candidate_intent_source_input_bindings(
    candidate_snapshot: ModelSystemSnapshot,
    active_contributions: Iterable[ModelIntentContribution],
    verified_source_identities: Iterable[ModelIntentSourceIdentity],
) -> None:
    """Require each local intent identity on its exact candidate owner input.

    This is a new-candidate gate rather than an unconditional legacy-view
    loader invariant.  The distinction keeps the sole pre-upgrade authority
    readable while preventing any newly accepted authority from preserving the
    detached source-to-owner boundary.
    """

    contributions = tuple(active_contributions)
    sources = tuple(verified_source_identities)
    contribution_by_id = {
        item.contribution_id: item for item in contributions
    }
    instance_by_id = {
        item.logical_model_id: item
        for item in candidate_snapshot.model_instances
    }
    if len(contribution_by_id) != len(contributions) or set(
        contribution_by_id
    ) != {item.contribution_id for item in sources}:
        raise ModelAuthorityError(
            "candidate intent-source identity denominator is incomplete"
        )
    for source in sources:
        if source.authority_kind == "work_context":
            continue
        contribution = contribution_by_id[source.contribution_id]
        owner = contribution.logical_model_id
        if not owner.startswith("model:"):
            raise ModelAuthorityError(
                "candidate intent source has no exact logical model owner: "
                f"{source.contribution_id} -> {owner}"
            )
        logical_model_id = owner.split("model:", 1)[1]
        instance = instance_by_id.get(logical_model_id)
        if instance is None:
            raise ModelAuthorityError(
                "candidate intent source names an unknown logical model owner: "
                f"{source.contribution_id} -> {owner}"
            )
        inputs = {item.path: item.sha256 for item in instance.inputs}
        actual = inputs.get(source.resolved_project_ref)
        if actual != source.source_fingerprint:
            raise ModelAuthorityError(
                "candidate logical model omits or mismatches its exact intent-source "
                f"input: owner={owner}; source={source.resolved_project_ref}; "
                f"expected={source.source_fingerprint}; actual={actual or 'missing'}"
            )


def _validate_current_effective_intent_refinement_with_sources(
    root: str | Path,
    *,
    base_view: CurrentEffectiveIntentView,
    candidate_snapshot: ModelSystemSnapshot,
    revision_contributions: Iterable[ModelIntentContribution],
    revision_dispositions: Iterable[ModelIntentDisposition],
    candidate_view: CurrentEffectiveIntentView,
    verified_source_identities: Iterable[ModelIntentSourceIdentity],
) -> None:
    """Replay one refinement against an explicitly selected source inventory.

    The candidate view is never accepted merely because it names the prior view
    fingerprint.  Its complete active inventory must be reproducible from the
    revision-local delta, dispositions, and one transition for every prior
    active contribution.  The selected source inventory is used to rebuild the
    canonical view for exact equality; callers decide whether it was freshly
    reverified or loaded from the immutable accepted view.
    """

    if not isinstance(base_view, CurrentEffectiveIntentView):
        raise ModelAuthorityError(
            "effective intent refinement requires the typed current base view"
        )
    if not isinstance(candidate_view, CurrentEffectiveIntentView):
        raise ModelAuthorityError(
            "effective intent refinement requires a typed candidate view"
        )
    if candidate_view.bootstrap_receipt is not None:
        raise ModelAuthorityError(
            "effective intent refinement cannot replace lineage with a bootstrap receipt"
        )
    if (
        candidate_view.base_effective_intent_view_fingerprint
        != base_view.fingerprint
    ):
        raise ModelAuthorityError(
            "effective intent view does not refine the exact current base view"
        )

    contributions = tuple(revision_contributions)
    dispositions = tuple(revision_dispositions)
    expected_active = fold_effective_intent_contributions(
        base_view,
        contributions,
        dispositions,
        candidate_view.transitions,
    )
    if expected_active != candidate_view.active_contributions:
        raise ModelAuthorityError(
            "effective intent view active inventory is not the exact replay result"
        )

    verified_sources = tuple(verified_source_identities)
    expected_view = build_current_effective_intent_view(
        base_view,
        candidate_snapshot,
        expected_active,
        verified_sources,
        candidate_view.transitions,
    )
    if expected_view != candidate_view:
        raise ModelAuthorityError(
            "effective intent view is stale, foreign, or not canonically reproducible"
        )
    validate_current_effective_intent_view(candidate_snapshot, candidate_view)


def validate_current_effective_intent_refinement(
    root: str | Path,
    *,
    base_view: CurrentEffectiveIntentView,
    candidate_snapshot: ModelSystemSnapshot,
    revision_contributions: Iterable[ModelIntentContribution],
    revision_dispositions: Iterable[ModelIntentDisposition],
    candidate_view: CurrentEffectiveIntentView,
) -> None:
    """Replay one refinement and independently reverify all active sources."""

    contributions = tuple(revision_contributions)
    dispositions = tuple(revision_dispositions)
    expected_active = fold_effective_intent_contributions(
        base_view,
        contributions,
        dispositions,
        candidate_view.transitions,
    )
    verified_sources = verify_model_intent_sources(
        Path(root).resolve(),
        expected_active,
    )
    _validate_current_effective_intent_refinement_with_sources(
        root,
        base_view=base_view,
        candidate_snapshot=candidate_snapshot,
        revision_contributions=contributions,
        revision_dispositions=dispositions,
        candidate_view=candidate_view,
        verified_source_identities=verified_sources,
    )


__all__ = [
    "CURRENT_EFFECTIVE_INTENT_VIEW_SCHEMA",
    "EFFECTIVE_INTENT_BOOTSTRAP_RECEIPT_SCHEMA",
    "EFFECTIVE_INTENT_OWNER_BINDING_SCHEMA",
    "EFFECTIVE_INTENT_TRANSITION_ACTIONS",
    "EFFECTIVE_INTENT_TRANSITION_SCHEMA",
    "EffectiveIntentBootstrapReceipt",
    "EffectiveIntentOwnerBinding",
    "EffectiveIntentTransition",
    "CurrentEffectiveIntentView",
    "LegacyIntentAuditEntry",
    "LegacyIntentBootstrapDisposition",
    "active_intent_contribution_inventory_fingerprint",
    "bootstrap_current_effective_intent_view",
    "build_current_effective_intent_view",
    "build_current_intent_bootstrap_receipt",
    "derive_effective_intent_owner_bindings",
    "effective_intent_owner_binding_inventory_fingerprint",
    "fold_effective_intent_contributions",
    "validate_candidate_intent_source_input_bindings",
    "validate_current_effective_intent_refinement",
    "validate_current_effective_intent_view",
    "validate_legacy_intent_bootstrap_dispositions",
]
