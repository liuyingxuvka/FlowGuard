"""Content-addressed intent lineage for one existing model authority.

Intent contributions preserve where a desired change came from and how the
current revision owner disposed it.  They are provenance records, not a second
model head: only :class:`flowguard.model_revision_set.ModelRevisionSet` may
accept them into a candidate revision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .model_authority import (
    LIFECYCLE_STATES,
    SUBJECT_LANES,
    ModelAuthorityError,
    _array,
    _id,
    _ids,
    _sha,
    _strict,
    _text,
    canonical_fingerprint,
)


MODEL_INTENT_CONTRIBUTION_SCHEMA = "flowguard.model_intent_contribution.v1"
MODEL_INTENT_DISPOSITION_SCHEMA = "flowguard.model_intent_disposition.v1"
MODEL_INTENT_MAPPING_SCHEMA = "flowguard.work_context_intent_mapping.v1"
MODEL_INTENT_FINDING_SCHEMA = "flowguard.model_intent_finding.v1"
MODEL_INTENT_REVIEW_SCHEMA = "flowguard.model_intent_review.v1"
MODEL_INTENT_INVENTORY_SCHEMA = "flowguard.model_intent_inventory.v1"

MODEL_INTENT_SOURCE_KINDS = frozenset(
    {
        "requirement",
        "design",
        "plan",
        "history",
        "spark",
        "openspark",
        "changelog",
        "user_decision",
    }
)
MODEL_INTENT_SUBJECT_ROLES = frozenset(
    {
        "scope",
        "requirement",
        "acceptance",
        "design",
        "plan",
        "task",
        "status",
        "history",
        "spark",
        "openspark",
        "changelog",
        "user_decision",
        "other",
    }
)
MODEL_INTENT_DISPOSITIONS = frozenset(
    {
        "accepted",
        "superseded",
        "rejected",
        "deferred",
        "conflicting",
        "unresolved",
    }
)
MODEL_INTENT_DECISION_STATES = frozenset(
    {"proposed", *MODEL_INTENT_DISPOSITIONS}
)


def _optional_id(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    return _id(text, field_name) if text else ""


def _optional_sha(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    return _sha(text, field_name) if text else ""


@dataclass(frozen=True)
class ModelIntentContribution:
    """One immutable statement of desired model evolution.

    ``decision_state`` is the state declared by the source lineage.  It never
    grants model authority.  ``ModelIntentDisposition`` is the independent
    decision made inside a concrete ``ModelRevisionSet``.
    """

    contribution_id: str
    source_kind: str
    source_ref: str
    source_fingerprint: str
    subject_lane: str
    subject_role: str
    lifecycle_state: str
    decision_state: str
    logical_model_id: str
    unresolved_owner_id: str
    supersedes_contribution_ids: tuple[str, ...]
    conflicts_with_contribution_ids: tuple[str, ...]
    target_obligation_ids: tuple[str, ...]
    target_state_ids: tuple[str, ...]
    target_transition_ids: tuple[str, ...]
    target_invariant_ids: tuple[str, ...]
    target_relation_ids: tuple[str, ...]
    desired_terminal_state_ids: tuple[str, ...]
    target_output_ids: tuple[str, ...]
    declared_consumer_ids: tuple[str, ...]
    effective_revision: str
    rationale: str
    work_context_id: str = ""
    work_context_fingerprint: str = ""
    native_owner_id: str = ""
    schema: str = MODEL_INTENT_CONTRIBUTION_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "contribution_id",
            _id(self.contribution_id, "contribution_id"),
        )
        if self.source_kind not in MODEL_INTENT_SOURCE_KINDS:
            raise ModelAuthorityError(
                f"unsupported intent source kind: {self.source_kind}"
            )
        object.__setattr__(
            self,
            "source_ref",
            _text(self.source_ref, "source_ref"),
        )
        object.__setattr__(
            self,
            "source_fingerprint",
            _sha(self.source_fingerprint, "source_fingerprint"),
        )
        if self.subject_lane not in SUBJECT_LANES:
            raise ModelAuthorityError(
                f"unsupported intent subject lane: {self.subject_lane}"
            )
        if self.subject_role not in MODEL_INTENT_SUBJECT_ROLES:
            raise ModelAuthorityError(
                f"unsupported intent subject role: {self.subject_role}"
            )
        if self.lifecycle_state not in LIFECYCLE_STATES:
            raise ModelAuthorityError(
                f"unsupported intent lifecycle state: {self.lifecycle_state}"
            )
        if self.decision_state not in MODEL_INTENT_DECISION_STATES:
            raise ModelAuthorityError(
                f"unsupported intent decision state: {self.decision_state}"
            )
        logical_model_id = _optional_id(
            self.logical_model_id,
            "logical_model_id",
        )
        unresolved_owner_id = _optional_id(
            self.unresolved_owner_id,
            "unresolved_owner_id",
        )
        if bool(logical_model_id) == bool(unresolved_owner_id):
            raise ModelAuthorityError(
                "intent contribution requires exactly one logical model or "
                "explicit unresolved owner"
            )
        object.__setattr__(self, "logical_model_id", logical_model_id)
        object.__setattr__(self, "unresolved_owner_id", unresolved_owner_id)
        for name in (
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
        ):
            object.__setattr__(self, name, _ids(getattr(self, name), name))
        if self.contribution_id in self.supersedes_contribution_ids:
            raise ModelAuthorityError(
                "intent contribution cannot supersede itself"
            )
        if self.contribution_id in self.conflicts_with_contribution_ids:
            raise ModelAuthorityError(
                "intent contribution cannot conflict with itself"
            )
        object.__setattr__(
            self,
            "effective_revision",
            _id(self.effective_revision, "effective_revision"),
        )
        object.__setattr__(
            self,
            "rationale",
            _text(self.rationale, "intent rationale", minimum=20),
        )
        context_id = _optional_id(self.work_context_id, "work_context_id")
        context_fingerprint = _optional_sha(
            self.work_context_fingerprint,
            "work_context_fingerprint",
        )
        native_owner_id = _optional_id(
            self.native_owner_id,
            "native_owner_id",
        )
        if any((context_id, context_fingerprint, native_owner_id)) and not all(
            (context_id, context_fingerprint, native_owner_id)
        ):
            raise ModelAuthorityError(
                "WorkContext intent provenance must bind context id, "
                "fingerprint, and native owner together"
            )
        object.__setattr__(self, "work_context_id", context_id)
        object.__setattr__(
            self,
            "work_context_fingerprint",
            context_fingerprint,
        )
        object.__setattr__(self, "native_owner_id", native_owner_id)
        if self.schema != MODEL_INTENT_CONTRIBUTION_SCHEMA:
            raise ModelAuthorityError(
                "intent contribution schema must be "
                f"{MODEL_INTENT_CONTRIBUTION_SCHEMA}"
            )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "contribution_id": self.contribution_id,
            "source_kind": self.source_kind,
            "source_ref": self.source_ref,
            "source_fingerprint": self.source_fingerprint,
            "subject_lane": self.subject_lane,
            "subject_role": self.subject_role,
            "lifecycle_state": self.lifecycle_state,
            "decision_state": self.decision_state,
            "logical_model_id": self.logical_model_id,
            "unresolved_owner_id": self.unresolved_owner_id,
            "supersedes_contribution_ids": list(
                self.supersedes_contribution_ids
            ),
            "conflicts_with_contribution_ids": list(
                self.conflicts_with_contribution_ids
            ),
            "target_obligation_ids": list(self.target_obligation_ids),
            "target_state_ids": list(self.target_state_ids),
            "target_transition_ids": list(self.target_transition_ids),
            "target_invariant_ids": list(self.target_invariant_ids),
            "target_relation_ids": list(self.target_relation_ids),
            "desired_terminal_state_ids": list(
                self.desired_terminal_state_ids
            ),
            "target_output_ids": list(self.target_output_ids),
            "declared_consumer_ids": list(self.declared_consumer_ids),
            "effective_revision": self.effective_revision,
            "rationale": self.rationale,
            "work_context_id": self.work_context_id,
            "work_context_fingerprint": self.work_context_fingerprint,
            "native_owner_id": self.native_owner_id,
        }

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.identity_payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: Any) -> "ModelIntentContribution":
        fields = (
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
            "effective_revision",
            "rationale",
            "work_context_id",
            "work_context_fingerprint",
            "native_owner_id",
            "fingerprint",
        )
        data = _strict(value, "model_intent_contribution", fields)
        array_fields = {
            name: tuple(_array(data[name], name))
            for name in (
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
        }
        result = cls(
            contribution_id=data["contribution_id"],
            source_kind=data["source_kind"],
            source_ref=data["source_ref"],
            source_fingerprint=data["source_fingerprint"],
            subject_lane=data["subject_lane"],
            subject_role=data["subject_role"],
            lifecycle_state=data["lifecycle_state"],
            decision_state=data["decision_state"],
            logical_model_id=data["logical_model_id"],
            unresolved_owner_id=data["unresolved_owner_id"],
            effective_revision=data["effective_revision"],
            rationale=data["rationale"],
            work_context_id=data["work_context_id"],
            work_context_fingerprint=data["work_context_fingerprint"],
            native_owner_id=data["native_owner_id"],
            schema=data["schema"],
            **array_fields,
        )
        if data["fingerprint"] != result.fingerprint:
            raise ModelAuthorityError("stale intent contribution fingerprint")
        return result


@dataclass(frozen=True)
class ModelIntentDisposition:
    """One revision-owned disposition and its exact modeled effects."""

    contribution_id: str
    contribution_fingerprint: str
    disposition: str
    changed_obligation_ids: tuple[str, ...]
    changed_state_ids: tuple[str, ...]
    changed_transition_ids: tuple[str, ...]
    changed_invariant_ids: tuple[str, ...]
    changed_relation_ids: tuple[str, ...]
    scoped_gap_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]
    unresolved_effect_ids: tuple[str, ...]
    unreachable_terminal_state_ids: tuple[str, ...]
    unconsumed_output_ids: tuple[str, ...]
    reason: str
    schema: str = MODEL_INTENT_DISPOSITION_SCHEMA

    def __post_init__(self) -> None:
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
        if self.disposition not in MODEL_INTENT_DISPOSITIONS:
            raise ModelAuthorityError(
                f"unsupported intent disposition: {self.disposition}"
            )
        for name in (
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
            object.__setattr__(self, name, _ids(getattr(self, name), name))
        object.__setattr__(
            self,
            "reason",
            _text(self.reason, "intent disposition reason", minimum=20),
        )
        if self.schema != MODEL_INTENT_DISPOSITION_SCHEMA:
            raise ModelAuthorityError(
                "intent disposition schema must be "
                f"{MODEL_INTENT_DISPOSITION_SCHEMA}"
            )

    @property
    def changed_model_ids(self) -> tuple[str, ...]:
        return _ids(
            (
                *self.changed_obligation_ids,
                *self.changed_state_ids,
                *self.changed_transition_ids,
                *self.changed_invariant_ids,
                *self.changed_relation_ids,
            ),
            "changed_model_id",
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "contribution_id": self.contribution_id,
            "contribution_fingerprint": self.contribution_fingerprint,
            "disposition": self.disposition,
            "changed_obligation_ids": list(self.changed_obligation_ids),
            "changed_state_ids": list(self.changed_state_ids),
            "changed_transition_ids": list(self.changed_transition_ids),
            "changed_invariant_ids": list(self.changed_invariant_ids),
            "changed_relation_ids": list(self.changed_relation_ids),
            "scoped_gap_ids": list(self.scoped_gap_ids),
            "conflict_ids": list(self.conflict_ids),
            "unresolved_effect_ids": list(self.unresolved_effect_ids),
            "unreachable_terminal_state_ids": list(
                self.unreachable_terminal_state_ids
            ),
            "unconsumed_output_ids": list(self.unconsumed_output_ids),
            "reason": self.reason,
        }

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.identity_payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: Any) -> "ModelIntentDisposition":
        fields = (
            "schema",
            "contribution_id",
            "contribution_fingerprint",
            "disposition",
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
            "reason",
            "fingerprint",
        )
        data = _strict(value, "model_intent_disposition", fields)
        array_fields = {
            name: tuple(_array(data[name], name))
            for name in (
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
            )
        }
        result = cls(
            contribution_id=data["contribution_id"],
            contribution_fingerprint=data["contribution_fingerprint"],
            disposition=data["disposition"],
            reason=data["reason"],
            schema=data["schema"],
            **array_fields,
        )
        if data["fingerprint"] != result.fingerprint:
            raise ModelAuthorityError("stale intent disposition fingerprint")
        return result


@dataclass(frozen=True)
class WorkContextIntentMapping:
    """Explicit admission mapping from one WorkContext artifact to intent."""

    artifact_id: str
    contribution_id: str
    source_kind: str
    subject_role: str
    lifecycle_state: str
    decision_state: str
    logical_model_id: str
    unresolved_owner_id: str
    supersedes_contribution_ids: tuple[str, ...]
    conflicts_with_contribution_ids: tuple[str, ...]
    target_obligation_ids: tuple[str, ...]
    target_state_ids: tuple[str, ...]
    target_transition_ids: tuple[str, ...]
    target_invariant_ids: tuple[str, ...]
    target_relation_ids: tuple[str, ...]
    desired_terminal_state_ids: tuple[str, ...]
    target_output_ids: tuple[str, ...]
    declared_consumer_ids: tuple[str, ...]
    effective_revision: str
    rationale: str
    schema: str = MODEL_INTENT_MAPPING_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "artifact_id",
            _id(self.artifact_id, "artifact_id"),
        )
        # Reuse the contribution's complete semantic validation with bounded
        # placeholder source identities.  Projection replaces these values
        # with the exact artifact and WorkContext fingerprints.
        ModelIntentContribution(
            contribution_id=self.contribution_id,
            source_kind=self.source_kind,
            source_ref="work-context:mapping",
            source_fingerprint=canonical_fingerprint(
                {"artifact_id": self.artifact_id}
            ),
            subject_lane="normative_target",
            subject_role=self.subject_role,
            lifecycle_state=self.lifecycle_state,
            decision_state=self.decision_state,
            logical_model_id=self.logical_model_id,
            unresolved_owner_id=self.unresolved_owner_id,
            supersedes_contribution_ids=self.supersedes_contribution_ids,
            conflicts_with_contribution_ids=self.conflicts_with_contribution_ids,
            target_obligation_ids=self.target_obligation_ids,
            target_state_ids=self.target_state_ids,
            target_transition_ids=self.target_transition_ids,
            target_invariant_ids=self.target_invariant_ids,
            target_relation_ids=self.target_relation_ids,
            desired_terminal_state_ids=self.desired_terminal_state_ids,
            target_output_ids=self.target_output_ids,
            declared_consumer_ids=self.declared_consumer_ids,
            effective_revision=self.effective_revision,
            rationale=self.rationale,
        )
        for name in (
            "contribution_id",
            "logical_model_id",
            "unresolved_owner_id",
            "effective_revision",
        ):
            object.__setattr__(self, name, str(getattr(self, name)).strip())
        for name in (
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
        ):
            object.__setattr__(self, name, _ids(getattr(self, name), name))
        object.__setattr__(
            self,
            "rationale",
            _text(self.rationale, "intent rationale", minimum=20),
        )
        if self.schema != MODEL_INTENT_MAPPING_SCHEMA:
            raise ModelAuthorityError(
                f"intent mapping schema must be {MODEL_INTENT_MAPPING_SCHEMA}"
            )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "artifact_id": self.artifact_id,
            "contribution_id": self.contribution_id,
            "source_kind": self.source_kind,
            "subject_role": self.subject_role,
            "lifecycle_state": self.lifecycle_state,
            "decision_state": self.decision_state,
            "logical_model_id": self.logical_model_id,
            "unresolved_owner_id": self.unresolved_owner_id,
            "supersedes_contribution_ids": list(
                self.supersedes_contribution_ids
            ),
            "conflicts_with_contribution_ids": list(
                self.conflicts_with_contribution_ids
            ),
            "target_obligation_ids": list(self.target_obligation_ids),
            "target_state_ids": list(self.target_state_ids),
            "target_transition_ids": list(self.target_transition_ids),
            "target_invariant_ids": list(self.target_invariant_ids),
            "target_relation_ids": list(self.target_relation_ids),
            "desired_terminal_state_ids": list(
                self.desired_terminal_state_ids
            ),
            "target_output_ids": list(self.target_output_ids),
            "declared_consumer_ids": list(self.declared_consumer_ids),
            "effective_revision": self.effective_revision,
            "rationale": self.rationale,
        }

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.identity_payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: Any) -> "WorkContextIntentMapping":
        fields = (
            "schema",
            "artifact_id",
            "contribution_id",
            "source_kind",
            "subject_role",
            "lifecycle_state",
            "decision_state",
            "logical_model_id",
            "unresolved_owner_id",
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
            "effective_revision",
            "rationale",
            "fingerprint",
        )
        data = _strict(value, "work_context_intent_mapping", fields)
        result = cls(
            artifact_id=data["artifact_id"],
            contribution_id=data["contribution_id"],
            source_kind=data["source_kind"],
            subject_role=data["subject_role"],
            lifecycle_state=data["lifecycle_state"],
            decision_state=data["decision_state"],
            logical_model_id=data["logical_model_id"],
            unresolved_owner_id=data["unresolved_owner_id"],
            effective_revision=data["effective_revision"],
            rationale=data["rationale"],
            schema=data["schema"],
            **{
                name: tuple(_array(data[name], name))
                for name in (
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
            },
        )
        if data["fingerprint"] != result.fingerprint:
            raise ModelAuthorityError("stale intent mapping fingerprint")
        return result


@dataclass(frozen=True)
class ModelIntentFinding:
    code: str
    message: str
    contribution_ids: tuple[str, ...] = ()
    schema: str = MODEL_INTENT_FINDING_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _id(self.code, "intent finding code"))
        object.__setattr__(
            self,
            "message",
            _text(self.message, "intent finding message"),
        )
        object.__setattr__(
            self,
            "contribution_ids",
            _ids(self.contribution_ids, "intent finding contribution id"),
        )
        if self.schema != MODEL_INTENT_FINDING_SCHEMA:
            raise ModelAuthorityError(
                f"intent finding schema must be {MODEL_INTENT_FINDING_SCHEMA}"
            )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "code": self.code,
            "message": self.message,
            "contribution_ids": list(self.contribution_ids),
        }

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.identity_payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: Any) -> "ModelIntentFinding":
        data = _strict(
            value,
            "model_intent_finding",
            ("schema", "code", "message", "contribution_ids", "fingerprint"),
        )
        result = cls(
            code=data["code"],
            message=data["message"],
            contribution_ids=tuple(
                _array(data["contribution_ids"], "contribution_ids")
            ),
            schema=data["schema"],
        )
        if data["fingerprint"] != result.fingerprint:
            raise ModelAuthorityError("stale intent finding fingerprint")
        return result


@dataclass(frozen=True)
class ModelIntentReview:
    contributions: tuple[ModelIntentContribution, ...]
    dispositions: tuple[ModelIntentDisposition, ...]
    findings: tuple[ModelIntentFinding, ...]
    conflict_ids: tuple[str, ...]
    unresolved_ids: tuple[str, ...]
    inventory_fingerprint: str
    changed_model_ids: tuple[str, ...] = ()
    changed_gap_ids: tuple[str, ...] = ()
    enforce_changed_targets: bool = False
    schema: str = MODEL_INTENT_REVIEW_SCHEMA

    def __post_init__(self) -> None:
        contributions = tuple(
            sorted(self.contributions, key=lambda item: item.contribution_id)
        )
        dispositions = tuple(
            sorted(self.dispositions, key=lambda item: item.contribution_id)
        )
        findings = tuple(
            sorted(
                self.findings,
                key=lambda item: (
                    item.code,
                    item.contribution_ids,
                    item.message,
                ),
            )
        )
        if any(
            not isinstance(item, ModelIntentContribution)
            for item in contributions
        ) or any(
            not isinstance(item, ModelIntentDisposition)
            for item in dispositions
        ) or any(
            not isinstance(item, ModelIntentFinding)
            for item in findings
        ):
            raise ModelAuthorityError(
                "intent review requires typed current child records"
            )
        object.__setattr__(self, "contributions", contributions)
        object.__setattr__(self, "dispositions", dispositions)
        object.__setattr__(self, "findings", findings)
        object.__setattr__(
            self,
            "conflict_ids",
            _ids(self.conflict_ids, "intent conflict id"),
        )
        object.__setattr__(
            self,
            "unresolved_ids",
            _ids(self.unresolved_ids, "intent unresolved id"),
        )
        object.__setattr__(
            self,
            "inventory_fingerprint",
            _sha(self.inventory_fingerprint, "intent inventory fingerprint"),
        )
        expected_inventory_fingerprint = model_intent_inventory_fingerprint(
            contributions,
            dispositions,
        )
        if self.inventory_fingerprint != expected_inventory_fingerprint:
            raise ModelAuthorityError("stale intent review inventory fingerprint")
        object.__setattr__(
            self,
            "changed_model_ids",
            _ids(self.changed_model_ids, "changed model id"),
        )
        object.__setattr__(
            self,
            "changed_gap_ids",
            _ids(self.changed_gap_ids, "changed gap id"),
        )
        if not isinstance(self.enforce_changed_targets, bool):
            raise ModelAuthorityError(
                "intent review enforce_changed_targets must be boolean"
            )
        if self.schema != MODEL_INTENT_REVIEW_SCHEMA:
            raise ModelAuthorityError(
                f"intent review schema must be {MODEL_INTENT_REVIEW_SCHEMA}"
            )

    @property
    def ok(self) -> bool:
        return not self.findings

    @property
    def acceptance_ready(self) -> bool:
        return self.ok

    @property
    def finding_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.findings)

    @property
    def accepted_contribution_ids(self) -> tuple[str, ...]:
        return tuple(
            item.contribution_id
            for item in self.dispositions
            if item.disposition == "accepted"
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "inventory_fingerprint": self.inventory_fingerprint,
            "conflict_ids": list(self.conflict_ids),
            "unresolved_ids": list(self.unresolved_ids),
            "changed_model_ids": list(self.changed_model_ids),
            "changed_gap_ids": list(self.changed_gap_ids),
            "enforce_changed_targets": self.enforce_changed_targets,
            "contributions": [item.to_dict() for item in self.contributions],
            "dispositions": [item.to_dict() for item in self.dispositions],
            "findings": [item.to_dict() for item in self.findings],
        }

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.identity_payload())

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "status": "pass" if self.ok else "blocked",
            "ok": self.ok,
            "acceptance_ready": self.acceptance_ready,
            "accepted_contribution_ids": list(
                self.accepted_contribution_ids
            ),
            "fingerprint": self.fingerprint,
            "claim_boundary": (
                "Intent review checks lineage and candidate mapping only. "
                "It does not accept a model revision or update the observed head."
            ),
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ModelIntentReview":
        data = _strict(
            value,
            "model_intent_review",
            (
                "schema",
                "inventory_fingerprint",
                "conflict_ids",
                "unresolved_ids",
                "changed_model_ids",
                "changed_gap_ids",
                "enforce_changed_targets",
                "contributions",
                "dispositions",
                "findings",
                "status",
                "ok",
                "acceptance_ready",
                "accepted_contribution_ids",
                "fingerprint",
                "claim_boundary",
            ),
        )
        if data["schema"] != MODEL_INTENT_REVIEW_SCHEMA:
            raise ModelAuthorityError(
                f"intent review schema must be {MODEL_INTENT_REVIEW_SCHEMA}"
            )
        result = review_model_intent_inventory(
            tuple(
                ModelIntentContribution.from_dict(item)
                for item in _array(data["contributions"], "contributions")
            ),
            tuple(
                ModelIntentDisposition.from_dict(item)
                for item in _array(data["dispositions"], "dispositions")
            ),
            changed_model_ids=tuple(
                _array(data["changed_model_ids"], "changed_model_ids")
            ),
            changed_gap_ids=tuple(
                _array(data["changed_gap_ids"], "changed_gap_ids")
            ),
            enforce_changed_targets=data["enforce_changed_targets"],
        )
        expected = result.to_dict()
        if data != expected:
            raise ModelAuthorityError("stale or non-canonical intent review")
        return result


def model_intent_inventory_fingerprint(
    contributions: Iterable[ModelIntentContribution],
    dispositions: Iterable[ModelIntentDisposition],
) -> str:
    contribution_items = tuple(
        sorted(contributions, key=lambda item: item.contribution_id)
    )
    disposition_items = tuple(
        sorted(dispositions, key=lambda item: item.contribution_id)
    )
    if any(
        not isinstance(item, ModelIntentContribution)
        for item in contribution_items
    ) or any(
        not isinstance(item, ModelIntentDisposition)
        for item in disposition_items
    ):
        raise ModelAuthorityError(
            "intent inventory requires typed current contribution and disposition records"
        )
    return canonical_fingerprint(
        {
            "schema": MODEL_INTENT_INVENTORY_SCHEMA,
            "contributions": [item.to_dict() for item in contribution_items],
            "dispositions": [item.to_dict() for item in disposition_items],
        }
    )


def _supersession_cycle_ids(
    contribution_by_id: dict[str, ModelIntentContribution],
) -> tuple[str, ...]:
    visiting: set[str] = set()
    visited: set[str] = set()
    cycle_ids: set[str] = set()

    def visit(contribution_id: str, path: tuple[str, ...]) -> None:
        if contribution_id in visiting:
            if contribution_id in path:
                cycle_ids.update(path[path.index(contribution_id) :])
            return
        if contribution_id in visited:
            return
        visiting.add(contribution_id)
        item = contribution_by_id[contribution_id]
        for target_id in item.supersedes_contribution_ids:
            if target_id in contribution_by_id:
                visit(target_id, (*path, target_id))
        visiting.remove(contribution_id)
        visited.add(contribution_id)

    for contribution_id in contribution_by_id:
        visit(contribution_id, (contribution_id,))
    return tuple(sorted(cycle_ids))


def review_model_intent_inventory(
    contributions: Iterable[ModelIntentContribution],
    dispositions: Iterable[ModelIntentDisposition],
    *,
    changed_model_ids: Iterable[str] = (),
    changed_gap_ids: Iterable[str] = (),
    enforce_changed_targets: bool = False,
) -> ModelIntentReview:
    """Review exact lineage, dispositions, and optional revision mappings."""

    contribution_items = tuple(
        sorted(contributions, key=lambda item: item.contribution_id)
    )
    disposition_items = tuple(
        sorted(dispositions, key=lambda item: item.contribution_id)
    )
    if any(
        not isinstance(item, ModelIntentContribution)
        for item in contribution_items
    ) or any(
        not isinstance(item, ModelIntentDisposition)
        for item in disposition_items
    ):
        raise ModelAuthorityError(
            "intent review requires typed current contribution and disposition records"
        )
    findings: list[ModelIntentFinding] = []
    conflict_ids: set[str] = set()
    unresolved_ids: set[str] = set()
    contribution_ids = tuple(item.contribution_id for item in contribution_items)
    disposition_ids = tuple(item.contribution_id for item in disposition_items)
    duplicate_contribution_ids = tuple(
        sorted(
            item_id
            for item_id in set(contribution_ids)
            if contribution_ids.count(item_id) > 1
        )
    )
    if duplicate_contribution_ids:
        findings.append(
            ModelIntentFinding(
                "intent_contribution_duplicate",
                "intent contribution ids must be unique",
                duplicate_contribution_ids,
            )
        )
    duplicate_disposition_ids = tuple(
        sorted(
            item_id
            for item_id in set(disposition_ids)
            if disposition_ids.count(item_id) > 1
        )
    )
    if duplicate_disposition_ids:
        findings.append(
            ModelIntentFinding(
                "intent_disposition_duplicate",
                "every contribution requires at most one disposition",
                duplicate_disposition_ids,
            )
        )
    contribution_by_id = {
        item.contribution_id: item for item in contribution_items
    }
    disposition_by_id = {
        item.contribution_id: item for item in disposition_items
    }
    missing_dispositions = tuple(
        sorted(set(contribution_by_id) - set(disposition_by_id))
    )
    if missing_dispositions:
        findings.append(
            ModelIntentFinding(
                "intent_disposition_missing",
                "every admitted contribution requires one exact disposition",
                missing_dispositions,
            )
        )
        unresolved_ids.update(
            f"intent_unresolved:{item_id}" for item_id in missing_dispositions
        )
    foreign_dispositions = tuple(
        sorted(set(disposition_by_id) - set(contribution_by_id))
    )
    if foreign_dispositions:
        findings.append(
            ModelIntentFinding(
                "intent_disposition_foreign",
                "a disposition names a contribution outside this inventory",
                foreign_dispositions,
            )
        )
        unresolved_ids.update(
            f"intent_unresolved:{item_id}" for item_id in foreign_dispositions
        )
    for contribution_id in sorted(
        set(contribution_by_id) & set(disposition_by_id)
    ):
        contribution = contribution_by_id[contribution_id]
        row = disposition_by_id[contribution_id]
        if row.contribution_fingerprint != contribution.fingerprint:
            findings.append(
                ModelIntentFinding(
                    "intent_contribution_fingerprint_mismatch",
                    "disposition does not bind the exact contribution bytes",
                    (contribution_id,),
                )
            )
            unresolved_ids.add(f"intent_unresolved:{contribution_id}")

    for item in contribution_items:
        missing_targets = tuple(
            target_id
            for target_id in item.supersedes_contribution_ids
            if target_id not in contribution_by_id
        )
        if missing_targets:
            findings.append(
                ModelIntentFinding(
                    "intent_supersession_target_missing",
                    "supersession target is outside the exact inventory",
                    (item.contribution_id, *missing_targets),
                )
            )
            unresolved_ids.update(
                f"intent_unresolved:{target_id}" for target_id in missing_targets
            )
        missing_conflicts = tuple(
            target_id
            for target_id in item.conflicts_with_contribution_ids
            if target_id not in contribution_by_id
        )
        if missing_conflicts:
            findings.append(
                ModelIntentFinding(
                    "intent_conflict_target_missing",
                    "declared conflict target is outside the exact inventory",
                    (item.contribution_id, *missing_conflicts),
                )
            )
            unresolved_ids.update(
                f"intent_unresolved:{target_id}" for target_id in missing_conflicts
            )

    cycle_ids = _supersession_cycle_ids(contribution_by_id)
    if cycle_ids:
        findings.append(
            ModelIntentFinding(
                "intent_supersession_cycle",
                "intent supersession must be acyclic",
                cycle_ids,
            )
        )
        unresolved_ids.update(
            f"intent_unresolved:{item_id}" for item_id in cycle_ids
        )

    accepted_ids = {
        item.contribution_id
        for item in disposition_items
        if item.disposition == "accepted"
    }
    for replacement_id in sorted(accepted_ids):
        replacement = contribution_by_id.get(replacement_id)
        if replacement is None:
            continue
        for target_id in replacement.supersedes_contribution_ids:
            target_row = disposition_by_id.get(target_id)
            if target_row is not None and target_row.disposition != "superseded":
                findings.append(
                    ModelIntentFinding(
                        "intent_supersession_disposition_mismatch",
                        "an accepted replacement requires its target to be superseded",
                        (replacement_id, target_id),
                    )
                )
                unresolved_ids.add(f"intent_unresolved:{target_id}")
    for row in disposition_items:
        if row.disposition != "superseded":
            continue
        replacers = tuple(
            item.contribution_id
            for item in contribution_items
            if item.contribution_id in accepted_ids
            and row.contribution_id in item.supersedes_contribution_ids
        )
        if not replacers:
            findings.append(
                ModelIntentFinding(
                    "intent_superseded_without_replacement",
                    "a superseded contribution requires an accepted explicit replacement",
                    (row.contribution_id,),
                )
            )
            unresolved_ids.add(f"intent_unresolved:{row.contribution_id}")

    seen_conflict_pairs: set[tuple[str, str]] = set()
    for item in contribution_items:
        for target_id in item.conflicts_with_contribution_ids:
            pair = tuple(sorted((item.contribution_id, target_id)))
            if pair in seen_conflict_pairs or target_id not in contribution_by_id:
                continue
            seen_conflict_pairs.add(pair)
            if pair[0] in accepted_ids and pair[1] in accepted_ids:
                left = contribution_by_id[pair[0]]
                right = contribution_by_id[pair[1]]
                explicitly_resolved = (
                    right.contribution_id in left.supersedes_contribution_ids
                    or left.contribution_id in right.supersedes_contribution_ids
                )
                if not explicitly_resolved:
                    conflict_id = f"intent_conflict:{pair[0]}:{pair[1]}"
                    conflict_ids.add(conflict_id)
                    findings.append(
                        ModelIntentFinding(
                            "intent_active_conflict",
                            "two accepted contributions declare an unresolved conflict",
                            pair,
                        )
                    )

    allowed_changed_ids = set(
        _ids(changed_model_ids, "changed_model_id")
    )
    allowed_gap_ids = set(_ids(changed_gap_ids, "changed_gap_id"))
    for row in disposition_items:
        contribution = contribution_by_id.get(row.contribution_id)
        if row.disposition == "accepted":
            if contribution is not None and contribution.unresolved_owner_id:
                findings.append(
                    ModelIntentFinding(
                        "intent_owner_unresolved",
                        "accepted contribution still has an unresolved model owner",
                        (row.contribution_id,),
                    )
                )
                unresolved_ids.add(contribution.unresolved_owner_id)
            if not row.changed_model_ids and not row.scoped_gap_ids:
                findings.append(
                    ModelIntentFinding(
                        "intent_contribution_disconnected",
                        "accepted contribution has no changed model identity or explicit gap",
                        (row.contribution_id,),
                    )
                )
                unresolved_ids.add(
                    f"intent_disconnected:{row.contribution_id}"
                )
            if enforce_changed_targets:
                unknown_changed = tuple(
                    item_id
                    for item_id in row.changed_model_ids
                    if item_id not in allowed_changed_ids
                )
                unknown_gaps = tuple(
                    item_id
                    for item_id in row.scoped_gap_ids
                    if item_id not in allowed_gap_ids
                )
                if unknown_changed or unknown_gaps:
                    findings.append(
                        ModelIntentFinding(
                            "intent_changed_target_unknown",
                            "accepted intent mapping is outside the exact revision diff",
                            (
                                row.contribution_id,
                                *unknown_changed,
                                *unknown_gaps,
                            ),
                        )
                    )
                    unresolved_ids.update((*unknown_changed, *unknown_gaps))
            if contribution is not None and (
                contribution.target_output_ids
                and not contribution.declared_consumer_ids
            ):
                findings.append(
                    ModelIntentFinding(
                        "intent_output_without_consumer",
                        "accepted target output has no declared consumer",
                        (row.contribution_id, *contribution.target_output_ids),
                    )
                )
                unresolved_ids.update(contribution.target_output_ids)
        if row.disposition == "conflicting":
            finding_conflicts = row.conflict_ids or (
                f"intent_conflict:{row.contribution_id}",
            )
            conflict_ids.update(finding_conflicts)
            findings.append(
                ModelIntentFinding(
                    "intent_disposition_conflicting",
                    "conflicting contribution blocks revision acceptance",
                    (row.contribution_id,),
                )
            )
        elif row.conflict_ids and row.disposition in {
            "accepted",
            "unresolved",
        }:
            conflict_ids.update(row.conflict_ids)
            findings.append(
                ModelIntentFinding(
                    "intent_disposition_conflicting",
                    "declared candidate conflict blocks revision acceptance",
                    (row.contribution_id,),
                )
            )
        if row.disposition == "unresolved":
            unresolved_ids.add(f"intent_unresolved:{row.contribution_id}")
            findings.append(
                ModelIntentFinding(
                    "intent_disposition_unresolved",
                    "unresolved contribution blocks revision acceptance",
                    (row.contribution_id,),
                )
            )
        if row.unresolved_effect_ids and row.disposition == "accepted":
            unresolved_ids.update(row.unresolved_effect_ids)
            findings.append(
                ModelIntentFinding(
                    "intent_effect_unresolved",
                    "candidate contains unresolved accepted intent effects",
                    (row.contribution_id, *row.unresolved_effect_ids),
                )
            )
        if (
            row.unreachable_terminal_state_ids
            and row.disposition == "accepted"
        ):
            unresolved_ids.update(row.unreachable_terminal_state_ids)
            findings.append(
                ModelIntentFinding(
                    "intent_terminal_unreachable",
                    "desired terminal is unreachable in the candidate model",
                    (
                        row.contribution_id,
                        *row.unreachable_terminal_state_ids,
                    ),
                )
            )
        if row.unconsumed_output_ids and row.disposition == "accepted":
            unresolved_ids.update(row.unconsumed_output_ids)
            findings.append(
                ModelIntentFinding(
                    "intent_output_without_consumer",
                    "target output has no declared candidate consumer",
                    (row.contribution_id, *row.unconsumed_output_ids),
                )
            )

    return ModelIntentReview(
        contributions=contribution_items,
        dispositions=disposition_items,
        findings=tuple(findings),
        conflict_ids=tuple(sorted(conflict_ids)),
        unresolved_ids=tuple(sorted(unresolved_ids)),
        inventory_fingerprint=model_intent_inventory_fingerprint(
            contribution_items,
            disposition_items,
        ),
        changed_model_ids=tuple(sorted(allowed_changed_ids)),
        changed_gap_ids=tuple(sorted(allowed_gap_ids)),
        enforce_changed_targets=enforce_changed_targets,
    )


__all__ = [
    "MODEL_INTENT_CONTRIBUTION_SCHEMA",
    "MODEL_INTENT_DECISION_STATES",
    "MODEL_INTENT_DISPOSITION_SCHEMA",
    "MODEL_INTENT_DISPOSITIONS",
    "MODEL_INTENT_FINDING_SCHEMA",
    "MODEL_INTENT_INVENTORY_SCHEMA",
    "MODEL_INTENT_MAPPING_SCHEMA",
    "MODEL_INTENT_REVIEW_SCHEMA",
    "MODEL_INTENT_SOURCE_KINDS",
    "MODEL_INTENT_SUBJECT_ROLES",
    "ModelIntentContribution",
    "ModelIntentDisposition",
    "ModelIntentFinding",
    "ModelIntentReview",
    "WorkContextIntentMapping",
    "model_intent_inventory_fingerprint",
    "review_model_intent_inventory",
]
