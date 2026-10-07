"""Content-addressed intent lineage for one existing model authority.

Intent contributions preserve where a desired change came from and how the
current revision owner disposed it.  They are provenance records, not a second
model head: only :class:`flowguard.model_revision_set.ModelRevisionSet` may
accept them into a candidate revision.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import stat
from typing import Any, Iterable, Mapping

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
from .source_identity import assert_current_source_path, source_file_fingerprint


MODEL_INTENT_CONTRIBUTION_SCHEMA = "flowguard.model_intent_contribution.v1"
MODEL_INTENT_DISPOSITION_SCHEMA = "flowguard.model_intent_disposition.v1"
MODEL_INTENT_MAPPING_SCHEMA = "flowguard.work_context_intent_mapping.v1"
MODEL_INTENT_FINDING_SCHEMA = "flowguard.model_intent_finding.v1"
MODEL_INTENT_REVIEW_SCHEMA = "flowguard.model_intent_review.v1"
MODEL_INTENT_INVENTORY_SCHEMA = "flowguard.model_intent_inventory.v1"
MODEL_INTENT_SOURCE_IDENTITY_SCHEMA = (
    "flowguard.model_intent_source_identity.v1"
)

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
class ModelIntentSourceIdentity:
    """One exact-current source identity frozen for revision construction.

    Direct project files and WorkContext artifacts deliberately remain
    different authority kinds.  The former use FlowGuard's canonical source
    fingerprint; the latter retain the provider-neutral artifact fingerprint
    plus the complete current WorkContext lineage that produced it.
    """

    contribution_id: str
    authority_kind: str
    source_ref: str
    source_fingerprint: str
    resolved_project_ref: str = ""
    work_context_id: str = ""
    work_context_fingerprint: str = ""
    native_owner_id: str = ""
    work_context_artifact_id: str = ""
    schema: str = MODEL_INTENT_SOURCE_IDENTITY_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "contribution_id",
            _id(self.contribution_id, "contribution_id"),
        )
        if self.authority_kind not in {"project_file", "work_context"}:
            raise ModelAuthorityError(
                "intent source authority kind must be project_file or work_context"
            )
        object.__setattr__(self, "source_ref", _text(self.source_ref, "source_ref"))
        object.__setattr__(
            self,
            "source_fingerprint",
            _sha(self.source_fingerprint, "source_fingerprint"),
        )
        for name in (
            "resolved_project_ref",
            "work_context_id",
            "work_context_fingerprint",
            "native_owner_id",
            "work_context_artifact_id",
        ):
            object.__setattr__(self, name, str(getattr(self, name) or ""))
        if self.authority_kind == "project_file":
            if not self.resolved_project_ref or any(
                (
                    self.work_context_id,
                    self.work_context_fingerprint,
                    self.native_owner_id,
                    self.work_context_artifact_id,
                )
            ):
                raise ModelAuthorityError(
                    "project-file intent identity must bind only one resolved project ref"
                )
        else:
            if self.resolved_project_ref or not all(
                (
                    self.work_context_id,
                    self.work_context_fingerprint,
                    self.native_owner_id,
                    self.work_context_artifact_id,
                )
            ):
                raise ModelAuthorityError(
                    "WorkContext intent identity requires exact context, owner, and artifact"
                )
            object.__setattr__(
                self,
                "work_context_fingerprint",
                _sha(
                    self.work_context_fingerprint,
                    "work_context_fingerprint",
                ),
            )
        if self.schema != MODEL_INTENT_SOURCE_IDENTITY_SCHEMA:
            raise ModelAuthorityError(
                "intent source identity schema must be "
                f"{MODEL_INTENT_SOURCE_IDENTITY_SCHEMA}"
            )

    def identity_payload(self) -> dict[str, str]:
        return {
            "schema": self.schema,
            "contribution_id": self.contribution_id,
            "authority_kind": self.authority_kind,
            "source_ref": self.source_ref,
            "source_fingerprint": self.source_fingerprint,
            "resolved_project_ref": self.resolved_project_ref,
            "work_context_id": self.work_context_id,
            "work_context_fingerprint": self.work_context_fingerprint,
            "native_owner_id": self.native_owner_id,
            "work_context_artifact_id": self.work_context_artifact_id,
        }

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.identity_payload())

    def to_dict(self) -> dict[str, str]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: Any) -> "ModelIntentSourceIdentity":
        data = _strict(
            value,
            "model_intent_source_identity",
            (
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
            ),
        )
        result = cls(
            contribution_id=data["contribution_id"],
            authority_kind=data["authority_kind"],
            source_ref=data["source_ref"],
            source_fingerprint=data["source_fingerprint"],
            resolved_project_ref=data["resolved_project_ref"],
            work_context_id=data["work_context_id"],
            work_context_fingerprint=data["work_context_fingerprint"],
            native_owner_id=data["native_owner_id"],
            work_context_artifact_id=data["work_context_artifact_id"],
            schema=data["schema"],
        )
        if data["fingerprint"] != result.fingerprint:
            raise ModelAuthorityError("stale intent source identity fingerprint")
        return result


def _resolved_project_source(
    root: Path,
    contribution: "ModelIntentContribution",
) -> tuple[Path, str]:
    reference = Path(contribution.source_ref)
    if reference.is_absolute() or reference.drive:
        raise ModelAuthorityError(
            "intent source must be a relative project path: "
            f"{contribution.contribution_id}"
        )
    try:
        lexical = root.joinpath(reference)
        resolved = lexical.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ModelAuthorityError(
            "intent source is missing or cannot be resolved: "
            f"{contribution.contribution_id}: {contribution.source_ref}"
        ) from exc
    if resolved != root and root not in resolved.parents:
        raise ModelAuthorityError(
            "intent source escapes project root or reaches an external link: "
            f"{contribution.contribution_id}: {contribution.source_ref}"
        )
    try:
        source_stat = resolved.stat()
    except OSError as exc:
        raise ModelAuthorityError(
            "intent source cannot be inspected: "
            f"{contribution.contribution_id}: {contribution.source_ref}"
        ) from exc
    if not stat.S_ISREG(source_stat.st_mode):
        raise ModelAuthorityError(
            "intent source is not a regular file: "
            f"{contribution.contribution_id}: {contribution.source_ref}"
        )
    project_ref = resolved.relative_to(root).as_posix()
    try:
        assert_current_source_path(project_ref)
    except ValueError as exc:
        raise ModelAuthorityError(str(exc)) from exc
    return resolved, project_ref


def verify_model_intent_sources(
    root: str | Path,
    contributions: Iterable["ModelIntentContribution"],
    *, read_context=None,
) -> tuple[ModelIntentSourceIdentity, ...]:
    """Re-resolve every contribution against its current source authority.

    The returned immutable rows are suitable for a build-time freeze and an
    exact pre-publication comparison.  This function never refreshes a stale
    contribution, guesses another path, or treats provider status as evidence.
    """

    root_path = Path(root).expanduser().resolve()
    if read_context is not None and read_context.root != root_path:
        raise ModelAuthorityError("intent source read context belongs to another root")
    if not root_path.is_dir():
        raise ModelAuthorityError("intent source project root is not a directory")
    items = tuple(sorted(contributions, key=lambda item: item.contribution_id))
    if any(not isinstance(item, ModelIntentContribution) for item in items):
        raise ModelAuthorityError(
            "intent source verification requires typed current contributions"
        )
    contribution_ids = tuple(item.contribution_id for item in items)
    if len(contribution_ids) != len(set(contribution_ids)):
        raise ModelAuthorityError(
            "intent source verification requires unique contribution ids"
        )

    context_items = tuple(item for item in items if item.work_context_id)
    contexts_by_id: dict[str, Any] = {}
    if context_items:
        # Local import avoids making work_context -> model_intent projection a
        # module-import cycle.  The current project declarations, not a caller
        # supplied context object or provider status, are the sole resolver.
        from .work_context import read_project_work_contexts

        project_review = read_project_work_contexts(root_path)
        if not project_review.ok:
            codes = tuple(sorted({item.code for item in project_review.findings}))
            raise ModelAuthorityError(
                "current project WorkContext declarations are invalid: "
                + ", ".join(codes)
            )
        contexts_by_id = {
            context.context_id: context for context in project_review.contexts
        }

    frozen: list[ModelIntentSourceIdentity] = []
    for item in items:
        source_ref = item.source_ref.replace("\\", "/")
        if source_ref.startswith((".flowguard/", "work/flowguard")):
            try:
                assert_current_source_path(source_ref)
            except ValueError as exc:
                raise ModelAuthorityError(str(exc)) from exc
        if not item.work_context_id:
            resolved, project_ref = _resolved_project_source(root_path, item)
            try:
                if read_context is None:
                    current_fingerprint = source_file_fingerprint(resolved)
                else:
                    from .source_identity import CANONICAL_TEXT_SUFFIXES
                    import hashlib
                    raw = read_context.artifact_bytes(resolved.relative_to(root_path).as_posix())
                    canonical = raw
                    if resolved.suffix.casefold() in CANONICAL_TEXT_SUFFIXES:
                        try:
                            canonical = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
                        except UnicodeDecodeError:
                            pass
                    current_fingerprint = "sha256:" + hashlib.sha256(canonical).hexdigest()
            except OSError as exc:
                raise ModelAuthorityError(
                    "intent source cannot be read: "
                    f"{item.contribution_id}: {item.source_ref}"
                ) from exc
            if current_fingerprint != item.source_fingerprint:
                raise ModelAuthorityError(
                    "intent source fingerprint is stale: "
                    f"{item.contribution_id}: {item.source_ref}"
                )
            frozen.append(
                ModelIntentSourceIdentity(
                    contribution_id=item.contribution_id,
                    authority_kind="project_file",
                    source_ref=item.source_ref,
                    source_fingerprint=current_fingerprint,
                    resolved_project_ref=project_ref,
                )
            )
            continue

        context = contexts_by_id.get(item.work_context_id)
        if context is None:
            raise ModelAuthorityError(
                "intent WorkContext is not declared by the current project: "
                f"{item.contribution_id}: {item.work_context_id}"
            )
        if context.context_fingerprint != item.work_context_fingerprint:
            raise ModelAuthorityError(
                "intent WorkContext fingerprint is stale or foreign: "
                f"{item.contribution_id}: {item.work_context_id}"
            )
        if context.native_owner_id != item.native_owner_id:
            raise ModelAuthorityError(
                "intent WorkContext native owner is stale or foreign: "
                f"{item.contribution_id}: {item.native_owner_id}"
            )
        artifacts = tuple(
            artifact
            for artifact in context.artifacts
            if artifact.source_ref == item.source_ref
        )
        if len(artifacts) != 1:
            raise ModelAuthorityError(
                "intent WorkContext source reference is missing or ambiguous: "
                f"{item.contribution_id}: {item.source_ref}"
            )
        artifact = artifacts[0]
        if artifact.content_fingerprint != item.source_fingerprint:
            raise ModelAuthorityError(
                "intent WorkContext artifact fingerprint is stale or foreign: "
                f"{item.contribution_id}: {item.source_ref}"
            )
        frozen.append(
            ModelIntentSourceIdentity(
                contribution_id=item.contribution_id,
                authority_kind="work_context",
                source_ref=item.source_ref,
                source_fingerprint=artifact.content_fingerprint,
                work_context_id=context.context_id,
                work_context_fingerprint=context.context_fingerprint,
                native_owner_id=context.native_owner_id,
                work_context_artifact_id=artifact.artifact_id,
            )
        )
    return tuple(frozen)


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
    known_external_contribution_ids: Iterable[str] = (),
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
    known_external_ids = set(
        _ids(
            known_external_contribution_ids,
            "known_external_contribution_id",
        )
    )
    if known_external_ids & set(contribution_by_id):
        raise ModelAuthorityError(
            "external intent lineage ids cannot also be revision-local contributions"
        )
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
            and target_id not in known_external_ids
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
    if enforce_changed_targets and contribution_items:
        accepted_changed_ids = {
            item_id
            for row in disposition_items
            if row.disposition == "accepted"
            for item_id in row.changed_model_ids
        }
        unmapped_changed_ids = tuple(
            sorted(allowed_changed_ids - accepted_changed_ids)
        )
        if unmapped_changed_ids:
            findings.append(
                ModelIntentFinding(
                    "intent_changed_target_unmapped",
                    (
                        "exact revision diff contains changed model identities "
                        "not mapped by any accepted intent disposition"
                    ),
                    unmapped_changed_ids,
                )
            )
            unresolved_ids.update(unmapped_changed_ids)
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
    "MODEL_INTENT_SOURCE_IDENTITY_SCHEMA",
    "MODEL_INTENT_SOURCE_KINDS",
    "MODEL_INTENT_SUBJECT_ROLES",
    "ModelIntentContribution",
    "ModelIntentDisposition",
    "ModelIntentFinding",
    "ModelIntentReview",
    "ModelIntentSourceIdentity",
    "WorkContextIntentMapping",
    "model_intent_inventory_fingerprint",
    "review_model_intent_inventory",
    "verify_model_intent_sources",
]

ARCHITECTURE_OBJECTIVE_SOURCE_SCHEMA = "flowguard.architecture_objective_source.v1"


@dataclass(frozen=True)
class ArchitectureObjective:
    objective_id: str
    required: bool
    model_ids: tuple[str, ...]
    responsibility_ids: tuple[str, ...]
    applicable_input_class_ids: tuple[str, ...]
    constraint_kind: str
    constraint_values: Any
    native_owner_id: str
    protected_failure_ids: tuple[str, ...]

    def __post_init__(self):
        from .model_path_quality import _validate_json_value, PATH_COST_DIMENSIONS
        _id(self.objective_id, "objective_id")
        _id(self.native_owner_id, "native_owner_id")
        if type(self.required) is not bool:
            raise ModelAuthorityError("objective required must be boolean")
        for name in ("model_ids", "responsibility_ids", "applicable_input_class_ids", "protected_failure_ids"):
            object.__setattr__(self, name, _ids(getattr(self, name), name))
            if not getattr(self, name):
                raise ModelAuthorityError(f"objective {name} missing")
        if not self.objective_id.startswith("objective:"):
            raise ModelAuthorityError("objective ID must use objective namespace")
        values = self.constraint_values
        _validate_json_value(values, "objective constraint values")
        fields_by_kind = {
            "unique_owner": {"owner_id"},
            "allowed_layers": {"layer_ids"},
            "shared_mechanism": {"canonical_mechanism_id", "canonical_owner_code_contract_id", "mechanism_fingerprint", "consumer_responsibility_ids", "required_delegation_relation_ids"},
            "cost_bound": {"dimension", "bound", "unit", "measurement_evidence_ref"},
            "functional_obligations": {"required_obligation_ids", "required_code_contract_ids", "native_case_pairs"},
        }
        if self.constraint_kind not in fields_by_kind or not isinstance(values, dict) or set(values) != fields_by_kind[self.constraint_kind]:
            raise ModelAuthorityError("objective constraint fields/kind invalid")
        if self.constraint_kind == "unique_owner":
            _id(values["owner_id"], "owner_id")
        elif self.constraint_kind == "allowed_layers":
            if not _ids(values["layer_ids"], "layer_ids"):
                raise ModelAuthorityError("allowed layers missing")
        elif self.constraint_kind == "shared_mechanism":
            for name in ("canonical_mechanism_id", "canonical_owner_code_contract_id"):
                _id(values[name], name)
            _sha(values["mechanism_fingerprint"], "mechanism_fingerprint")
            for name in ("consumer_responsibility_ids", "required_delegation_relation_ids"):
                if not _ids(values[name], name):
                    raise ModelAuthorityError("shared mechanism exact closure missing")
            if set(values["consumer_responsibility_ids"]) != set(self.responsibility_ids):
                raise ModelAuthorityError("shared mechanism consumer scope mismatch")
        elif self.constraint_kind == "functional_obligations":
            for name in ("required_obligation_ids", "required_code_contract_ids"):
                if not isinstance(values[name], list) or not values[name]:
                    raise ModelAuthorityError("functional objective exact arrays missing")
                ids = _ids(values[name], name)
                if list(ids) != values[name]:
                    raise ModelAuthorityError("functional objective IDs must be canonical")
            pairs = values["native_case_pairs"]
            if not isinstance(pairs, list) or not pairs:
                raise ModelAuthorityError("functional objective native pairs missing")
            keys = []
            for pair in pairs:
                if not isinstance(pair, dict) or set(pair) != {"owner_id", "source_case_id", "satisfied_observed_status"}:
                    raise ModelAuthorityError("functional objective native pair exact fields required")
                for name in pair:
                    if not isinstance(pair[name], str) or _id(pair[name], name) != pair[name]:
                        raise ModelAuthorityError("functional objective native pair requires canonical nonempty strings")
                keys.append((pair["owner_id"], pair["source_case_id"]))
            if keys != sorted(set(keys)):
                raise ModelAuthorityError("functional objective native pairs must be canonical and unique")
        else:
            import math
            if values["dimension"] not in PATH_COST_DIMENSIONS or type(values["bound"]) not in {int, float} or not math.isfinite(values["bound"]) or values["bound"] < 0:
                raise ModelAuthorityError("cost bound invalid")
            _text(values["unit"], "unit")
            _text(values["measurement_evidence_ref"], "measurement evidence")
        import json
        object.__setattr__(self, "constraint_values", json.loads(json.dumps(values, allow_nan=False)))

    def to_dict(self):
        from dataclasses import fields
        return {f.name: list(getattr(self, f.name)) if f.name.endswith("_ids") else getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, value):
        from dataclasses import fields
        names = {f.name for f in fields(cls)}
        if not isinstance(value, dict) or set(value) != names:
            raise ModelAuthorityError("architecture objective exact fields required")
        return cls(**value)


@dataclass(frozen=True)
class ArchitectureObjectiveSource:
    objectives: tuple[ArchitectureObjective, ...]
    schema: str = ARCHITECTURE_OBJECTIVE_SOURCE_SCHEMA

    def __post_init__(self):
        if self.schema != ARCHITECTURE_OBJECTIVE_SOURCE_SCHEMA:
            raise ModelAuthorityError("architecture objective source schema invalid")
        rows = tuple(x if isinstance(x, ArchitectureObjective) else ArchitectureObjective.from_dict(x) for x in self.objectives)
        if len({x.objective_id for x in rows}) != len(rows):
            raise ModelAuthorityError("duplicate architecture objective")
        object.__setattr__(self, "objectives", tuple(sorted(rows, key=lambda x: x.objective_id)))

    def to_dict(self):
        return {"schema": self.schema, "objectives": [x.to_dict() for x in self.objectives]}

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != {"schema", "objectives"} or not isinstance(value["objectives"], list):
            raise ModelAuthorityError("architecture objective source exact fields required")
        return cls(**value)

    @classmethod
    def from_source_bytes(cls, source_bytes):
        import json, re
        if not isinstance(source_bytes, bytes):
            raise ModelAuthorityError("architecture source requires verified UTF8 bytes")
        try:
            text = source_bytes.decode("utf-8", errors="strict").replace("\r\n", "\n").replace("\r", "\n")
            markers = re.findall(r"(?m)^```flowguard-architecture-objectives[ \t]*$", text)
            blocks = re.findall(r"(?m)^```flowguard-architecture-objectives[ \t]*\r?\n(.*?)^```[ \t]*$", text, re.S)
            if len(markers) != 1 or len(blocks) != 1:
                raise ModelAuthorityError("architecture_objective_source_missing or duplicate fence")
            def unique(pairs):
                out = {}
                for key, value in pairs:
                    if key in out: raise ModelAuthorityError("duplicate objective source JSON key")
                    out[key] = value
                return out
            def nonfinite(value):
                raise ModelAuthorityError("nonfinite objective source JSON")
            return cls.from_dict(json.loads(blocks[0], object_pairs_hook=unique, parse_constant=nonfinite))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ModelAuthorityError("architecture_objective_source_invalid") from exc


@dataclass(frozen=True)
class BoundArchitectureObjective:
    objective: ArchitectureObjective
    contribution_id: str
    source_identity_fingerprint: str
    source_ref: str
    source_fingerprint: str
    effective_intent_view_fingerprint: str

    def __post_init__(self):
        if not isinstance(self.objective, ArchitectureObjective):
            raise ModelAuthorityError("typed bound objective required")
        _id(self.contribution_id, "contribution_id")
        _text(self.source_ref, "source_ref")
        for name in ("source_identity_fingerprint", "source_fingerprint", "effective_intent_view_fingerprint"):
            _sha(getattr(self, name), name)

    def to_dict(self):
        from dataclasses import fields
        return {f.name: self.objective.to_dict() if f.name == "objective" else getattr(self, f.name) for f in fields(self)}


def derive_architecture_objective_projection(effective_intent_view, *, source_bytes_by_contribution_id):
    """Project only already verified, complete current normative sources.

    Byte maps are an explicit provider boundary: project files are reverified
    against functional source identity; WorkContext artifacts require the
    exact bytes resolved by the native provider, never artifact-summary prose.
    """
    from .model_intent_authority import CurrentEffectiveIntentView
    import hashlib
    if not isinstance(effective_intent_view, CurrentEffectiveIntentView):
        raise ModelAuthorityError("effective_intent_identity_mismatch")
    identities = {x.contribution_id: x for x in effective_intent_view.verified_source_identities}
    bound = []
    for contribution in effective_intent_view.active_contributions:
        admitted = {x for x in contribution.target_invariant_ids if x.startswith("objective:")}
        raw = source_bytes_by_contribution_id.get(contribution.contribution_id)
        if raw is None:
            if admitted: raise ModelAuthorityError("architecture_objective_source_missing")
            continue
        identity = identities.get(contribution.contribution_id)
        if identity is None or identity.source_ref != contribution.source_ref or identity.source_fingerprint != contribution.source_fingerprint:
            raise ModelAuthorityError("effective_intent_identity_mismatch")
        if identity.authority_kind == "project_file":
            if "sha256:" + hashlib.sha256(raw.decode("utf-8", errors="strict").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")).hexdigest() != identity.source_fingerprint:
                raise ModelAuthorityError("architecture_objective_source_invalid")
        elif not isinstance(raw, bytes):
            raise ModelAuthorityError("architecture_objective_source_invalid")
        elif "sha256:" + hashlib.sha256(raw).hexdigest() != identity.source_fingerprint:
            raise ModelAuthorityError("architecture_objective_source_invalid")
        if b"```flowguard-architecture-objectives" not in raw:
            if admitted: raise ModelAuthorityError("architecture_objective_source_missing")
            continue
        source = ArchitectureObjectiveSource.from_source_bytes(raw)
        if {x.objective_id for x in source.objectives} != admitted:
            raise ModelAuthorityError("architecture_objective_unadmitted")
        for objective in source.objectives:
            if contribution.subject_lane != "normative_target" or objective.native_owner_id != (contribution.native_owner_id or "model:" + contribution.logical_model_id.removeprefix("model:")):
                raise ModelAuthorityError("architecture_objective_unadmitted")
            bound.append(BoundArchitectureObjective(objective, contribution.contribution_id, identity.fingerprint, identity.source_ref, identity.source_fingerprint, effective_intent_view.fingerprint))
    by_id = {}
    for item in bound:
        prior = by_id.get(item.objective.objective_id)
        if prior and prior.objective.to_dict() != item.objective.to_dict():
            raise ModelAuthorityError("architecture objective conflicting accepted sources")
        by_id[item.objective.objective_id] = item
    return tuple(sorted(bound, key=lambda x: (x.objective.objective_id, x.contribution_id)))

@dataclass(frozen=True, init=False)
class _ArchitectureSourceObservation:
    """Invocation-local byte observation; callers cannot inject a hash."""

    source_bytes: bytes
    authority_kind: str
    source_fingerprint: str

    def __new__(cls):
        raise TypeError("architecture source observations are derived from bytes")

    @classmethod
    def from_bytes(cls, source_bytes, authority_kind):
        import hashlib
        if not isinstance(source_bytes, bytes) or authority_kind not in {"project_file", "work_context"}:
            raise ModelAuthorityError("architecture source observation bytes/kind invalid")
        normalized = source_bytes
        if authority_kind == "project_file":
            try: normalized = source_bytes.decode("utf-8", errors="strict").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
            except UnicodeDecodeError as exc: raise ModelAuthorityError("architecture_objective_source_invalid") from exc
        result = object.__new__(cls)
        object.__setattr__(result, "source_bytes", source_bytes)
        object.__setattr__(result, "authority_kind", authority_kind)
        object.__setattr__(result, "source_fingerprint", "sha256:" + hashlib.sha256(normalized).hexdigest())
        return result


def bind_architecture_objective_source(contribution, source_identity, *, effective_intent_view_fingerprint, source_bytes, source_observation=None):
    """Selected projection from an independently authenticated complete view."""
    import hashlib
    if not isinstance(contribution, ModelIntentContribution) or not isinstance(source_identity, ModelIntentSourceIdentity):
        raise ModelAuthorityError("effective_intent_identity_mismatch")
    _sha(effective_intent_view_fingerprint, "complete effective intent fingerprint")
    if source_identity.contribution_id != contribution.contribution_id or source_identity.source_ref != contribution.source_ref or source_identity.source_fingerprint != contribution.source_fingerprint or contribution.decision_state != "accepted" or contribution.subject_lane != "normative_target" or not isinstance(source_bytes, bytes):
        raise ModelAuthorityError("effective_intent_identity_mismatch")
    observation = source_observation
    if observation is None:
        observation = _ArchitectureSourceObservation.from_bytes(source_bytes, source_identity.authority_kind)
    if not isinstance(observation, _ArchitectureSourceObservation) or observation.source_bytes != source_bytes or observation.authority_kind != source_identity.authority_kind or observation.source_fingerprint != source_identity.source_fingerprint:
        raise ModelAuthorityError("architecture_objective_source_invalid")
    admitted = {x for x in contribution.target_invariant_ids if x.startswith("objective:")}
    if b"```flowguard-architecture-objectives" not in source_bytes:
        if admitted: raise ModelAuthorityError("architecture_objective_source_missing")
        return ()
    document = ArchitectureObjectiveSource.from_source_bytes(source_bytes)
    if {x.objective_id for x in document.objectives} != admitted:
        raise ModelAuthorityError("architecture_objective_unadmitted")
    native_owner = contribution.native_owner_id or "model:" + contribution.logical_model_id.removeprefix("model:")
    if any(x.native_owner_id != native_owner for x in document.objectives):
        raise ModelAuthorityError("architecture_objective_unadmitted")
    return tuple(BoundArchitectureObjective(x, contribution.contribution_id, source_identity.fingerprint, source_identity.source_ref, source_identity.source_fingerprint, effective_intent_view_fingerprint) for x in document.objectives)


@dataclass(frozen=True)
class ArchitectureCompromiseSource:
    """Current-source annotations; they never waive a normative objective."""

    compromises: tuple[Mapping[str, Any], ...]
    schema: str = "flowguard.architecture_compromises.v1"

    def __post_init__(self):
        from .model_path_quality import _exact_object, _canonical_ids, _require_string, _require_fingerprint
        names = ("compromise_id", "contribution_id", "objective_ids", "responsibility_ids", "element_ids", "applicable_input_class_ids", "functional_impact", "rationale", "next_owner_ids", "revisit_triggers")
        if self.schema != "flowguard.architecture_compromises.v1":
            raise ModelAuthorityError("architecture compromise schema invalid")
        rows = []
        for raw in self.compromises:
            row = _exact_object(raw, names, "architecture compromise")
            for name in ("compromise_id", "contribution_id", "rationale"):
                _require_string(row[name], name)
            for name in ("objective_ids", "responsibility_ids", "element_ids", "applicable_input_class_ids", "next_owner_ids"):
                row[name] = list(_canonical_ids(row[name], name))
                if not row[name]: raise ModelAuthorityError("architecture compromise scope missing: " + name)
            impact = _exact_object(row["functional_impact"], ("outcome_ids", "obligation_ids", "description"), "functional impact")
            for name in ("outcome_ids", "obligation_ids"):
                impact[name] = list(_canonical_ids(impact[name], name))
                if not impact[name]: raise ModelAuthorityError("architecture compromise impact missing: " + name)
            _require_string(impact["description"], "functional impact description")
            row["functional_impact"] = impact
            triggers = []
            for value in row["revisit_triggers"]:
                trigger = _exact_object(value, ("trigger_id", "source_ref", "source_fingerprint", "condition_ref"), "revisit trigger")
                for name in ("trigger_id", "source_ref", "condition_ref"): _require_string(trigger[name], name)
                _require_fingerprint(trigger["source_fingerprint"], "source fingerprint")
                triggers.append(trigger)
            if not triggers or len({x["trigger_id"] for x in triggers}) != len(triggers):
                raise ModelAuthorityError("architecture compromise triggers missing/duplicate")
            row["revisit_triggers"] = sorted(triggers, key=lambda x: x["trigger_id"])
            rows.append(row)
        if len({x["compromise_id"] for x in rows}) != len(rows):
            raise ModelAuthorityError("duplicate architecture compromise")
        object.__setattr__(self, "compromises", tuple(sorted(rows, key=lambda x: x["compromise_id"])))

    def to_dict(self):
        import json
        return json.loads(json.dumps({"schema": self.schema, "compromises": list(self.compromises)}))

    @classmethod
    def from_source_bytes(cls, source_bytes):
        import json, re
        if not isinstance(source_bytes, bytes): raise ModelAuthorityError("architecture compromise requires source bytes")
        try:
            text = source_bytes.decode("utf-8", errors="strict").replace("\r\n", "\n").replace("\r", "\n")
            markers = re.findall(r"(?m)^```flowguard-architecture-compromises[ \t]*$", text)
            blocks = re.findall(r"(?m)^```flowguard-architecture-compromises[ \t]*\r?\n(.*?)^```[ \t]*$", text, re.S)
            if len(markers) != 1 or len(blocks) != 1: raise ModelAuthorityError("architecture_compromise_source_missing or duplicate fence")
            def unique(pairs):
                out = {}
                for key, value in pairs:
                    if key in out: raise ModelAuthorityError("duplicate compromise source JSON key")
                    out[key] = value
                return out
            def nonfinite(value): raise ModelAuthorityError("nonfinite compromise source JSON")
            value = json.loads(blocks[0], object_pairs_hook=unique, parse_constant=nonfinite)
            if not isinstance(value, dict) or set(value) != {"schema", "compromises"} or not isinstance(value["compromises"], list):
                raise ModelAuthorityError("architecture compromise source exact fields required")
            return cls(**value)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ModelAuthorityError("architecture_compromise_source_invalid") from exc


def derive_architecture_compromise_projection(effective_intent_view, *, source_bytes_by_contribution_id, objectives=(), responsibilities=(), subjects=()):
    """Derive annotations from the same admitted current normative source."""
    from .model_intent_authority import CurrentEffectiveIntentView
    import hashlib
    if not isinstance(effective_intent_view, CurrentEffectiveIntentView): raise ModelAuthorityError("effective_intent_identity_mismatch")
    identities = {x.contribution_id: x for x in effective_intent_view.verified_source_identities}
    objective_by_id = {x.objective.objective_id: x for x in objectives}
    fact_by_id = {x.responsibility_id: x for x in responsibilities}
    subject_by_id = {x.model_id: x for x in subjects}
    bound, seen = [], set()
    for contribution in effective_intent_view.active_contributions:
        raw = source_bytes_by_contribution_id.get(contribution.contribution_id)
        if raw is None: continue
        if not isinstance(raw, bytes): raise ModelAuthorityError("architecture_compromise_source_invalid")
        identity = identities.get(contribution.contribution_id)
        if identity is None or identity.source_ref != contribution.source_ref or identity.source_fingerprint != contribution.source_fingerprint:
            raise ModelAuthorityError("effective_intent_identity_mismatch")
        normalized = raw
        if identity.authority_kind == "project_file":
            try: normalized = raw.decode("utf-8", errors="strict").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
            except UnicodeDecodeError as exc: raise ModelAuthorityError("architecture_compromise_source_invalid") from exc
        if "sha256:" + hashlib.sha256(normalized).hexdigest() != identity.source_fingerprint:
            raise ModelAuthorityError("architecture_compromise_source_invalid")
        if b"```flowguard-architecture-compromises" not in raw: continue
        document = ArchitectureCompromiseSource.from_source_bytes(raw)
        for row in document.compromises:
            if row["compromise_id"] in seen: raise ModelAuthorityError("conflicting architecture compromise")
            seen.add(row["compromise_id"])
            if contribution.subject_lane != "normative_target" or row["contribution_id"] != contribution.contribution_id:
                raise ModelAuthorityError("architecture_compromise_unadmitted")
            scoped_objectives = [objective_by_id.get(key) for key in row["objective_ids"]]
            scoped_facts = [fact_by_id.get(key) for key in row["responsibility_ids"]]
            if (any(x is None for x in scoped_objectives + scoped_facts)
                    or any(x.contribution_id != contribution.contribution_id or x.effective_intent_view_fingerprint != effective_intent_view.fingerprint or x.source_fingerprint != identity.source_fingerprint for x in scoped_objectives)):
                raise ModelAuthorityError("architecture_compromise_scope_unknown")
            if (not set(row["element_ids"]) <= {key for x in scoped_facts for key in x.element_ids}
                    or any(not set(row["applicable_input_class_ids"]) <= set(x.applicable_input_class_ids) for x in scoped_facts)
                    or not set(row["next_owner_ids"]) <= ({x.owner_id for x in scoped_facts} | {x.objective.native_owner_id for x in scoped_objectives})
                    or not set(row["responsibility_ids"]) <= {key for x in scoped_objectives for key in x.objective.responsibility_ids}
                    or any(x.model_id not in subject_by_id or subject_by_id[x.model_id].intent_fingerprint != effective_intent_view.fingerprint for x in scoped_facts)
                    or not set(row["functional_impact"]["obligation_ids"]) <= set(contribution.target_obligation_ids)
                    or not set(row["functional_impact"]["outcome_ids"]) <= set(contribution.target_output_ids)):
                raise ModelAuthorityError("architecture_compromise_scope_unknown")
            # Triggers name anchors in this same source; a source hash embedded
            # in itself would be circular. The accepted hash is bound below.
            for trigger in row["revisit_triggers"]:
                if trigger["source_ref"] != identity.source_ref or trigger["condition_ref"] not in _architecture_markdown_anchors(raw.decode("utf-8")):
                    raise ModelAuthorityError("architecture_compromise_trigger_unknown")
            triggers = [{**x, "source_fingerprint": identity.source_fingerprint} for x in row["revisit_triggers"]]
            bound.append({**row, "revisit_triggers": triggers, "source_ref": identity.source_ref, "source_fingerprint": identity.source_fingerprint,
                "source_identity_fingerprint": identity.fingerprint, "effective_intent_view_fingerprint": effective_intent_view.fingerprint})
    return tuple(sorted(bound, key=lambda x: x["compromise_id"]))


def _architecture_markdown_anchors(text):
    """Resolve declared Markdown headings/anchors outside fenced source JSON."""
    import re
    anchors, counts = set(), {}
    fence = None
    for line in text.splitlines():
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            kind = marker.group(1)[0]
            if fence is None:
                fence = kind
            elif kind == fence:
                fence = None
            continue
        if fence is not None:
            continue
        for value in re.findall(r'<(?:a|h[1-6])\b[^>]*\bid=["\']([^"\']+)["\']', line):
            anchors.add("#" + value)
        heading = re.match(r"^\s{0,3}#{1,6}[ \t]+(.+?)[ \t]*#*[ \t]*$", line)
        if heading:
            label = re.sub(r"<[^>]+>", "", heading.group(1)).lower()
            slug = re.sub(r"[^\w\- ]", "", label).replace(" ", "-")
            if slug:
                count = counts.get(slug, 0)
                counts[slug] = count + 1
                anchors.add("#" + slug + ("-" + str(count) if count else ""))
    return anchors
