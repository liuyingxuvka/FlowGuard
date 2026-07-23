"""Atomic model-system revision, activation, and rollback contracts."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable

from .model_authority import (
    LIFECYCLE_ACTIVE,
    MODEL_ACTIVATION_RECEIPT_SCHEMA,
    MODEL_PREDICTION_REPLAY_REF_SCHEMA,
    MODEL_REVISION_EVIDENCE_SCHEMA,
    MODEL_REVISION_MEMBER_SCHEMA,
    MODEL_REVISION_SET_SCHEMA,
    MODEL_ROLLBACK_CONTRACT_SCHEMA,
    MODEL_ROLLBACK_EFFECT_SCHEMA,
    MODEL_ROLLBACK_RECEIPT_SCHEMA,
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
    ModelAuthorityError,
    ModelAuthorityHead,
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


@dataclass(frozen=True)
class RevisionEvidenceRef:
    receipt_id: str
    receipt_fingerprint: str
    owner_route: str
    subject_fingerprint: str
    obligation_ids: tuple[str, ...]
    status: str
    current: bool
    eligible: bool
    schema: str = MODEL_REVISION_EVIDENCE_SCHEMA

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
        if self.schema != MODEL_REVISION_EVIDENCE_SCHEMA:
            raise ModelAuthorityError(
                f"revision evidence schema must be {MODEL_REVISION_EVIDENCE_SCHEMA}"
            )

    @property
    def identity_key(self) -> tuple[Any, ...]:
        return (
            self.receipt_id,
            self.receipt_fingerprint,
            self.owner_route,
            self.subject_fingerprint,
            self.obligation_ids,
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
                "status",
                "current",
                "eligible",
            ),
        )
        return cls(
            receipt_id=data["receipt_id"],
            receipt_fingerprint=data["receipt_fingerprint"],
            owner_route=data["owner_route"],
            subject_fingerprint=data["subject_fingerprint"],
            obligation_ids=tuple(
                _array(data["obligation_ids"], "obligation_ids")
            ),
            status=data["status"],
            current=data["current"],
            eligible=data["eligible"],
            schema=data["schema"],
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
            replay_id=data["replay_id"],
            replay_fingerprint=data["replay_fingerprint"],
            prediction_id=data["prediction_id"],
            prediction_fingerprint=data["prediction_fingerprint"],
            observation_boundary_id=data["observation_boundary_id"],
            candidate_instance_fingerprint=data[
                "candidate_instance_fingerprint"
            ],
            status=data["status"],
            schema=data["schema"],
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
            member_id=data["member_id"],
            operation=data["operation"],
            base_instance_fingerprint=data["base_instance_fingerprint"],
            candidate_instance_fingerprint=data[
                "candidate_instance_fingerprint"
            ],
            changed_element_ids=tuple(
                _array(data["changed_element_ids"], "changed_element_ids")
            ),
            schema=data["schema"],
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
    changed_relation_ids: tuple[str, ...] = ()
    changed_commitment_ids: tuple[str, ...] = ()
    changed_field_ids: tuple[str, ...] = ()
    changed_side_effect_ids: tuple[str, ...] = ()
    changed_contract_ids: tuple[str, ...] = ()
    changed_test_ids: tuple[str, ...] = ()
    changed_system_property_ids: tuple[str, ...] = ()
    required_evidence_refs: tuple[RevisionEvidenceRef, ...] = ()
    completed_evidence_refs: tuple[RevisionEvidenceRef, ...] = ()
    prediction_replay_refs: tuple[PredictionReplayRef, ...] = ()
    implementation_bundle_fingerprint: str = ""
    rollback_contract_fingerprint: str = ""
    status: str = REVISION_PROPOSED
    decision_reason: str = ""
    schema: str = MODEL_REVISION_SET_SCHEMA

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
        if not members:
            raise ModelAuthorityError("revision set requires at least one member")
        member_ids = tuple(item.member_id for item in members)
        if len(member_ids) != len(set(member_ids)):
            raise ModelAuthorityError("revision member ids must be unique")
        object.__setattr__(self, "members", members)
        for name in (
            "affected_closure_ids",
            "changed_relation_ids",
            "changed_commitment_ids",
            "changed_field_ids",
            "changed_side_effect_ids",
            "changed_contract_ids",
            "changed_test_ids",
            "changed_system_property_ids",
        ):
            object.__setattr__(self, name, _ids(getattr(self, name), name))
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
        if not required:
            raise ModelAuthorityError(
                "revision set requires evidence refs"
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
        required_keys = tuple(item.identity_key for item in required)
        completed_keys = tuple(item.identity_key for item in completed)
        if len(required_keys) != len(set(required_keys)):
            raise ModelAuthorityError("required revision evidence must be unique")
        if len(completed_keys) != len(set(completed_keys)):
            raise ModelAuthorityError("completed revision evidence must be unique")
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
        for name in (
            "implementation_bundle_fingerprint",
            "rollback_contract_fingerprint",
        ):
            if getattr(self, name):
                object.__setattr__(
                    self,
                    name,
                    _sha(getattr(self, name), name),
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
        if self.status != REVISION_PROPOSED and not self.decision_reason:
            raise ModelAuthorityError(
                "terminal revision set requires a decision reason"
            )
        if self.schema != MODEL_REVISION_SET_SCHEMA:
            raise ModelAuthorityError(
                f"revision set schema must be {MODEL_REVISION_SET_SCHEMA}"
            )

    @property
    def evidence_complete(self) -> bool:
        required = tuple(item.identity_key for item in self.required_evidence_refs)
        completed = tuple(item.identity_key for item in self.completed_evidence_refs)
        return (
            required == completed
            and all(item.passing for item in self.completed_evidence_refs)
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
            "changed_relation_ids": list(self.changed_relation_ids),
            "changed_commitment_ids": list(self.changed_commitment_ids),
            "changed_field_ids": list(self.changed_field_ids),
            "changed_side_effect_ids": list(self.changed_side_effect_ids),
            "changed_contract_ids": list(self.changed_contract_ids),
            "changed_test_ids": list(self.changed_test_ids),
            "changed_system_property_ids": list(
                self.changed_system_property_ids
            ),
            "required_evidence_refs": [
                item.to_dict() for item in self.required_evidence_refs
            ],
            "completed_evidence_refs": [
                item.to_dict() for item in self.completed_evidence_refs
            ],
            "prediction_replay_refs": [
                item.to_dict() for item in self.prediction_replay_refs
            ],
            "implementation_bundle_fingerprint": (
                self.implementation_bundle_fingerprint
            ),
            "rollback_contract_fingerprint": (
                self.rollback_contract_fingerprint
            ),
            "status": self.status,
            "decision_reason": self.decision_reason,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "evidence_complete": self.evidence_complete,
            "fingerprint": self.fingerprint,
        }

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
                "changed_relation_ids",
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
            ),
        )
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
            changed_relation_ids=tuple(
                _array(data["changed_relation_ids"], "changed_relation_ids")
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
            implementation_bundle_fingerprint=data[
                "implementation_bundle_fingerprint"
            ],
            rollback_contract_fingerprint=data[
                "rollback_contract_fingerprint"
            ],
            status=data["status"],
            decision_reason=data["decision_reason"],
            schema=data["schema"],
        )
        if bool(data["evidence_complete"]) != result.evidence_complete:
            raise ModelAuthorityError("stale revision evidence_complete")
        if data["fingerprint"] != result.fingerprint:
            raise ModelAuthorityError("stale revision-set fingerprint")
        return result


def derive_affected_closure_fingerprint(
    *,
    affected_closure_ids: Iterable[str],
    members: Iterable[RevisionMemberChange],
    changed_relation_ids: Iterable[str] = (),
    changed_commitment_ids: Iterable[str] = (),
    changed_field_ids: Iterable[str] = (),
    changed_side_effect_ids: Iterable[str] = (),
    changed_contract_ids: Iterable[str] = (),
    changed_test_ids: Iterable[str] = (),
    changed_system_property_ids: Iterable[str] = (),
) -> str:
    payload = {
        "affected_closure_ids": list(
            _ids(affected_closure_ids, "affected_closure_id")
        ),
        "members": [
            item.to_dict()
            for item in sorted(members, key=lambda value: value.member_id)
        ],
        "changed_relation_ids": list(
            _ids(changed_relation_ids, "changed_relation_id")
        ),
        "changed_commitment_ids": list(
            _ids(changed_commitment_ids, "changed_commitment_id")
        ),
        "changed_field_ids": list(
            _ids(changed_field_ids, "changed_field_id")
        ),
        "changed_side_effect_ids": list(
            _ids(changed_side_effect_ids, "changed_side_effect_id")
        ),
        "changed_contract_ids": list(
            _ids(changed_contract_ids, "changed_contract_id")
        ),
        "changed_test_ids": list(_ids(changed_test_ids, "changed_test_id")),
        "changed_system_property_ids": list(
            _ids(
                changed_system_property_ids,
                "changed_system_property_id",
            )
        ),
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
    if base_snapshot.system_id != candidate_snapshot.system_id:
        raise ModelAuthorityError("revision snapshots belong to different systems")

    base_models = {
        item.logical_model_id: item for item in base_snapshot.model_instances
    }
    candidate_models = {
        item.logical_model_id: item
        for item in candidate_snapshot.model_instances
    }
    observed: dict[str, tuple[str, str, str]] = {}
    for model_id in sorted(set(base_models) | set(candidate_models)):
        base = base_models.get(model_id)
        candidate = candidate_models.get(model_id)
        if base is None:
            observed[model_id] = ("add", "", candidate.fingerprint)
        elif candidate is None:
            observed[model_id] = ("remove", base.fingerprint, "")
        elif base.fingerprint != candidate.fingerprint:
            observed[model_id] = (
                "replace",
                base.fingerprint,
                candidate.fingerprint,
            )
    declared = {
        item.member_id: (
            item.operation,
            item.base_instance_fingerprint,
            item.candidate_instance_fingerprint,
        )
        for item in revision_set.members
    }
    if declared != observed:
        raise ModelAuthorityError(
            "revision members do not exactly match the snapshot model diff"
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
    if changed_relations != revision_set.changed_relation_ids:
        raise ModelAuthorityError(
            "revision changed_relation_ids do not match the snapshot relation diff"
        )
    expected_closure_fingerprint = derive_affected_closure_fingerprint(
        affected_closure_ids=revision_set.affected_closure_ids,
        members=revision_set.members,
        changed_relation_ids=revision_set.changed_relation_ids,
        changed_commitment_ids=revision_set.changed_commitment_ids,
        changed_field_ids=revision_set.changed_field_ids,
        changed_side_effect_ids=revision_set.changed_side_effect_ids,
        changed_contract_ids=revision_set.changed_contract_ids,
        changed_test_ids=revision_set.changed_test_ids,
        changed_system_property_ids=revision_set.changed_system_property_ids,
    )
    if (
        revision_set.affected_closure_fingerprint
        != expected_closure_fingerprint
    ):
        raise ModelAuthorityError(
            "revision affected closure fingerprint is stale or incomplete"
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
            receipt_id=data["receipt_id"],
            system_id=data["system_id"],
            revision_set_fingerprint=data["revision_set_fingerprint"],
            expected_head_fingerprint=data["expected_head_fingerprint"],
            previous_snapshot_fingerprint=data[
                "previous_snapshot_fingerprint"
            ],
            candidate_snapshot_fingerprint=data[
                "candidate_snapshot_fingerprint"
            ],
            subject_revision=data["subject_revision"],
            next_generation=data["next_generation"],
            schema=data["schema"],
        )


def validate_activation_plan(
    current_head: ModelAuthorityHead,
    base_snapshot: ModelSystemSnapshot,
    candidate_snapshot: ModelSystemSnapshot,
    revision_set: ModelRevisionSet,
    *,
    receipt_id: str,
) -> tuple[ModelAuthorityHead, ModelActivationReceipt]:
    """Pure validation only; durable CAS is owned by model_authority_store."""

    if revision_set.status != REVISION_ACCEPTED:
        raise ModelAuthorityError("revision set must be accepted before activation")
    validate_revision_set_snapshots(
        base_snapshot,
        candidate_snapshot,
        revision_set,
    )
    if not revision_set.evidence_complete:
        raise ModelAuthorityError("revision-set evidence is incomplete")
    if current_head.fingerprint != revision_set.expected_head_fingerprint:
        raise ModelAuthorityError("observed authority head changed; rebase required")
    if (
        current_head.snapshot_fingerprint
        != revision_set.base_snapshot_fingerprint
    ):
        raise ModelAuthorityError("revision base does not match observed snapshot")
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
            effect_id=data["effect_id"],
            kind=data["kind"],
            disposition=data["disposition"],
            required_evidence_fingerprints=tuple(
                _array(
                    data["required_evidence_fingerprints"],
                    "required_evidence_fingerprints",
                )
            ),
            schema=data["schema"],
        )


@dataclass(frozen=True)
class ModelRollbackContract:
    contract_id: str
    from_snapshot_fingerprint: str
    to_snapshot_fingerprint: str
    effects: tuple[ModelRollbackEffect, ...]
    old_snapshot_conformance_evidence_fingerprints: tuple[str, ...]
    schema: str = MODEL_ROLLBACK_CONTRACT_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "contract_id", _id(self.contract_id, "contract_id"))
        object.__setattr__(
            self,
            "from_snapshot_fingerprint",
            _sha(self.from_snapshot_fingerprint, "from_snapshot_fingerprint"),
        )
        object.__setattr__(
            self,
            "to_snapshot_fingerprint",
            _sha(self.to_snapshot_fingerprint, "to_snapshot_fingerprint"),
        )
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
        if self.schema != MODEL_ROLLBACK_CONTRACT_SCHEMA:
            raise ModelAuthorityError(
                f"rollback contract schema must be {MODEL_ROLLBACK_CONTRACT_SCHEMA}"
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
                "from_snapshot_fingerprint",
                "to_snapshot_fingerprint",
                "effects",
                "old_snapshot_conformance_evidence_fingerprints",
                "exact_rollback_possible",
            ),
        )
        result = cls(
            contract_id=data["contract_id"],
            from_snapshot_fingerprint=data["from_snapshot_fingerprint"],
            to_snapshot_fingerprint=data["to_snapshot_fingerprint"],
            effects=tuple(
                ModelRollbackEffect.from_dict(item)
                for item in _array(data["effects"], "effects")
            ),
            old_snapshot_conformance_evidence_fingerprints=tuple(
                _array(
                    data[
                        "old_snapshot_conformance_evidence_fingerprints"
                    ],
                    "old_snapshot_conformance_evidence_fingerprints",
                )
            ),
            schema=data["schema"],
        )
        if (
            bool(data["exact_rollback_possible"])
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
    result: str
    completed_evidence_fingerprints: tuple[str, ...]
    reason: str
    schema: str = MODEL_ROLLBACK_RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_id", _id(self.receipt_id, "receipt_id"))
        object.__setattr__(
            self,
            "contract_fingerprint",
            _sha(self.contract_fingerprint, "contract_fingerprint"),
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
        if self.schema != MODEL_ROLLBACK_RECEIPT_SCHEMA:
            raise ModelAuthorityError(
                f"rollback receipt schema must be {MODEL_ROLLBACK_RECEIPT_SCHEMA}"
            )

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "receipt_id": self.receipt_id,
            "contract_fingerprint": self.contract_fingerprint,
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
                "result",
                "completed_evidence_fingerprints",
                "reason",
            ),
        )
        return cls(
            receipt_id=data["receipt_id"],
            contract_fingerprint=data["contract_fingerprint"],
            result=data["result"],
            completed_evidence_fingerprints=tuple(
                _array(
                    data["completed_evidence_fingerprints"],
                    "completed_evidence_fingerprints",
                )
            ),
            reason=data["reason"],
            schema=data["schema"],
        )


def validate_operational_rollback(
    current_head: ModelAuthorityHead,
    contract: ModelRollbackContract,
    *,
    completed_evidence_fingerprints: Iterable[str],
    requested_result: str,
    receipt_id: str,
    reason: str,
) -> ModelRollbackReceipt:
    """Validate real-world restoration before any observed pointer rewind."""

    if current_head.snapshot_fingerprint != contract.from_snapshot_fingerprint:
        raise ModelAuthorityError(
            "authority head advanced; create a forward revision instead"
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
        result=requested_result,
        completed_evidence_fingerprints=completed,
        reason=reason,
    )



__all__ = [
    "ModelActivationReceipt",
    "ModelRevisionSet",
    "ModelRollbackContract",
    "ModelRollbackEffect",
    "ModelRollbackReceipt",
    "PredictionReplayRef",
    "RevisionEvidenceRef",
    "RevisionMemberChange",
    "derive_affected_closure_fingerprint",
    "validate_activation_plan",
    "validate_operational_rollback",
    "validate_revision_set_snapshots",
]
