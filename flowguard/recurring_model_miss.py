"""Model-miss behavior backfeed and UI failure review helpers.

Observed failures are bound to the exact existing behavior commitment and owner
model, or recorded as an explicit same-plane coverage gap. Same-class closure is
owned by ContractExhaustion and model growth is owned by ModelMaturation; this
module does not define another recurring-defect gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Sequence

from ._normalization import string_sequence as _as_tuple
from .behavior_commitment import (
    BCL_BEHAVIOR_PLANES,
    BCL_HIT_ROLE_PRIMARY,
    BCL_LOOKUP_STATUS_PERFORMED,
    BehaviorCommitmentLedger,
)
from .behavior_commitment_lookup import (
    BehaviorCommitmentHit,
    BehaviorLookupQuery,
    query_behavior_commitments,
)
from .export import to_jsonable

UI_MODEL_MISS_EVIDENCE_OVERCLAIMED = "evidence_overclaimed"
UI_MODEL_MISS_BOUNDARY_MISSING = "boundary_missing"
UI_MODEL_MISS_STATE_TOO_COARSE = "state_too_coarse"
UI_MODEL_MISS_INPUT_BRANCH_MISSING = "input_branch_missing"
UI_MODEL_MISS_CODE_BOUNDARY_MISMATCH = "code_boundary_mismatch"
UI_MODEL_MISS_AFFORDANCE_MISMATCH = "affordance_mismatch"
UI_MODEL_MISS_ACTION_GRAMMAR_CONFLICT = "action_grammar_conflict"
UI_MODEL_MISS_DIALOG_RETURN_MISSING = "dialog_return_missing"
UI_MODEL_MISS_KEYBOARD_FOCUS_MISSING = "keyboard_focus_missing"
UI_MODEL_MISS_REGION_SEMANTICS_CONFLICT = "region_semantics_conflict"
UI_MODEL_MISS_HUMAN_WALKTHROUGH_FAILED = "human_walkthrough_failed"
UI_MODEL_MISS_TYPES = (
    UI_MODEL_MISS_EVIDENCE_OVERCLAIMED,
    UI_MODEL_MISS_BOUNDARY_MISSING,
    UI_MODEL_MISS_STATE_TOO_COARSE,
    UI_MODEL_MISS_INPUT_BRANCH_MISSING,
    UI_MODEL_MISS_CODE_BOUNDARY_MISMATCH,
    UI_MODEL_MISS_AFFORDANCE_MISMATCH,
    UI_MODEL_MISS_ACTION_GRAMMAR_CONFLICT,
    UI_MODEL_MISS_DIALOG_RETURN_MISSING,
    UI_MODEL_MISS_KEYBOARD_FOCUS_MISSING,
    UI_MODEL_MISS_REGION_SEMANTICS_CONFLICT,
    UI_MODEL_MISS_HUMAN_WALKTHROUGH_FAILED,
)
UI_MODEL_MISS_PROMISED_CAPABILITY_TYPES = (
    UI_MODEL_MISS_EVIDENCE_OVERCLAIMED,
    UI_MODEL_MISS_BOUNDARY_MISSING,
)

MODEL_MISS_BACKFEED_REUSE_EXISTING = "reuse_existing_commitment"
MODEL_MISS_BACKFEED_COVERAGE_GAP = "coverage_gap_candidate"
MODEL_MISS_BACKFEED_AMBIGUOUS = "plane_or_commitment_ambiguous"
MODEL_MISS_BACKFEED_BLOCKED = "lookup_blocked"
MODEL_MISS_BACKFEED_DISPOSITIONS = (
    MODEL_MISS_BACKFEED_REUSE_EXISTING,
    MODEL_MISS_BACKFEED_COVERAGE_GAP,
    MODEL_MISS_BACKFEED_AMBIGUOUS,
    MODEL_MISS_BACKFEED_BLOCKED,
)

@dataclass(frozen=True)
class ModelMissBehaviorContext:
    """One primary or typed-related commitment bound to an observed miss."""

    commitment_id: str
    behavior_plane: str
    primary_owner_model_id: str
    hit_role: str = BCL_HIT_ROLE_PRIMARY
    relation_type: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "commitment_id", str(self.commitment_id))
        object.__setattr__(self, "behavior_plane", str(self.behavior_plane))
        object.__setattr__(self, "primary_owner_model_id", str(self.primary_owner_model_id))
        object.__setattr__(self, "hit_role", str(self.hit_role))
        object.__setattr__(self, "relation_type", str(self.relation_type))

    @classmethod
    def from_hit(cls, hit: BehaviorCommitmentHit) -> "ModelMissBehaviorContext":
        return cls(
            hit.commitment_id,
            hit.behavior_plane,
            hit.primary_owner_model_id,
            hit.hit_role,
            hit.relation_type,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "commitment_id": self.commitment_id,
            "behavior_plane": self.behavior_plane,
            "primary_owner_model_id": self.primary_owner_model_id,
            "hit_role": self.hit_role,
            "relation_type": self.relation_type,
        }


def _coerce_behavior_context(
    value: ModelMissBehaviorContext | Mapping[str, Any],
) -> ModelMissBehaviorContext:
    if isinstance(value, ModelMissBehaviorContext):
        return value
    return ModelMissBehaviorContext(**dict(value))


@dataclass(frozen=True)
class ModelMissBehaviorBackfeed:
    """Same-plane-first Model Miss lookup and registration decision."""

    disposition: str
    lookup_status: str
    primary_context: ModelMissBehaviorContext | None = None
    related_context: tuple[ModelMissBehaviorContext, ...] = ()
    candidate_context: tuple[ModelMissBehaviorContext, ...] = ()
    ledger_fingerprint: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        if self.disposition not in MODEL_MISS_BACKFEED_DISPOSITIONS:
            raise ValueError(f"unknown model-miss backfeed disposition: {self.disposition!r}")
        object.__setattr__(self, "lookup_status", str(self.lookup_status))
        object.__setattr__(self, "related_context", tuple(self.related_context))
        object.__setattr__(self, "candidate_context", tuple(self.candidate_context))
        object.__setattr__(self, "ledger_fingerprint", str(self.ledger_fingerprint))
        object.__setattr__(self, "reason", str(self.reason))

    @property
    def reuses_existing_commitment(self) -> bool:
        return (
            self.disposition == MODEL_MISS_BACKFEED_REUSE_EXISTING
            and self.primary_context is not None
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "disposition": self.disposition,
            "lookup_status": self.lookup_status,
            "primary_context": self.primary_context.to_dict() if self.primary_context else None,
            "related_context": [item.to_dict() for item in self.related_context],
            "candidate_context": [item.to_dict() for item in self.candidate_context],
            "ledger_fingerprint": self.ledger_fingerprint,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class UIModelMissRecord:
    """User-observed UI failure after prior green FlowGuard evidence."""

    miss_id: str
    previous_claim_id: str = ""
    previous_green_reason: str = ""
    observed_failure: str = ""
    observed_failure_evidence_ref: str = ""
    miss_type: str = UI_MODEL_MISS_EVIDENCE_OVERCLAIMED
    missing_promised_capability_ids: tuple[str, ...] = ()
    affected_capability_ids: tuple[str, ...] = ()
    affected_control_ids: tuple[str, ...] = ()
    affected_field_ids: tuple[str, ...] = ()
    same_class_capability_ids: tuple[str, ...] = ()
    same_class_control_ids: tuple[str, ...] = ()
    same_class_field_ids: tuple[str, ...] = ()
    required_test_ids: tuple[str, ...] = ()
    required_implementation_evidence_ids: tuple[str, ...] = ()
    affected_behavior_plane: str = ""
    affected_commitment_id: str = ""
    primary_owner_model_id: str = ""
    related_behavior_context: tuple[ModelMissBehaviorContext | Mapping[str, Any], ...] = ()
    error_signatures: tuple[str, ...] = ()
    error_evidence_ids: tuple[str, ...] = ()
    behavior_lookup_status: str = ""
    behavior_ledger_fingerprint: str = ""
    behavior_coverage_gap_candidate: bool = False
    root_cause_backpropagation: str = ""
    code_owner: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "miss_id", str(self.miss_id))
        object.__setattr__(self, "previous_claim_id", str(self.previous_claim_id))
        object.__setattr__(self, "previous_green_reason", str(self.previous_green_reason))
        object.__setattr__(self, "observed_failure", str(self.observed_failure))
        object.__setattr__(self, "observed_failure_evidence_ref", str(self.observed_failure_evidence_ref))
        object.__setattr__(self, "miss_type", str(self.miss_type))
        object.__setattr__(
            self,
            "missing_promised_capability_ids",
            _as_tuple(self.missing_promised_capability_ids),
        )
        object.__setattr__(self, "affected_capability_ids", _as_tuple(self.affected_capability_ids))
        object.__setattr__(self, "affected_control_ids", _as_tuple(self.affected_control_ids))
        object.__setattr__(self, "affected_field_ids", _as_tuple(self.affected_field_ids))
        object.__setattr__(self, "same_class_capability_ids", _as_tuple(self.same_class_capability_ids))
        object.__setattr__(self, "same_class_control_ids", _as_tuple(self.same_class_control_ids))
        object.__setattr__(self, "same_class_field_ids", _as_tuple(self.same_class_field_ids))
        object.__setattr__(self, "required_test_ids", _as_tuple(self.required_test_ids))
        object.__setattr__(
            self,
            "required_implementation_evidence_ids",
            _as_tuple(self.required_implementation_evidence_ids),
        )
        object.__setattr__(self, "affected_behavior_plane", str(self.affected_behavior_plane))
        object.__setattr__(self, "affected_commitment_id", str(self.affected_commitment_id))
        object.__setattr__(self, "primary_owner_model_id", str(self.primary_owner_model_id))
        object.__setattr__(
            self,
            "related_behavior_context",
            tuple(_coerce_behavior_context(value) for value in self.related_behavior_context),
        )
        object.__setattr__(self, "error_signatures", _as_tuple(self.error_signatures))
        object.__setattr__(self, "error_evidence_ids", _as_tuple(self.error_evidence_ids))
        object.__setattr__(self, "behavior_lookup_status", str(self.behavior_lookup_status))
        object.__setattr__(self, "behavior_ledger_fingerprint", str(self.behavior_ledger_fingerprint))
        object.__setattr__(
            self,
            "behavior_coverage_gap_candidate",
            bool(self.behavior_coverage_gap_candidate),
        )
        object.__setattr__(self, "root_cause_backpropagation", str(self.root_cause_backpropagation))
        object.__setattr__(self, "code_owner", str(self.code_owner))
        object.__setattr__(self, "rationale", str(self.rationale))

    def has_same_class_scope(self) -> bool:
        return bool(self.same_class_capability_ids or self.same_class_control_ids or self.same_class_field_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "miss_id": self.miss_id,
            "previous_claim_id": self.previous_claim_id,
            "previous_green_reason": self.previous_green_reason,
            "observed_failure": self.observed_failure,
            "observed_failure_evidence_ref": self.observed_failure_evidence_ref,
            "miss_type": self.miss_type,
            "missing_promised_capability_ids": list(self.missing_promised_capability_ids),
            "affected_capability_ids": list(self.affected_capability_ids),
            "affected_control_ids": list(self.affected_control_ids),
            "affected_field_ids": list(self.affected_field_ids),
            "same_class_capability_ids": list(self.same_class_capability_ids),
            "same_class_control_ids": list(self.same_class_control_ids),
            "same_class_field_ids": list(self.same_class_field_ids),
            "required_test_ids": list(self.required_test_ids),
            "required_implementation_evidence_ids": list(self.required_implementation_evidence_ids),
            "affected_behavior_plane": self.affected_behavior_plane,
            "affected_commitment_id": self.affected_commitment_id,
            "primary_owner_model_id": self.primary_owner_model_id,
            "related_behavior_context": [
                context.to_dict() for context in self.related_behavior_context
            ],
            "error_signatures": list(self.error_signatures),
            "error_evidence_ids": list(self.error_evidence_ids),
            "behavior_lookup_status": self.behavior_lookup_status,
            "behavior_ledger_fingerprint": self.behavior_ledger_fingerprint,
            "behavior_coverage_gap_candidate": self.behavior_coverage_gap_candidate,
            "root_cause_backpropagation": self.root_cause_backpropagation,
            "code_owner": self.code_owner,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class UIModelMissReviewPlan:
    """Review plan for UI-specific model misses after green evidence."""

    plan_id: str
    ui_misses: tuple[UIModelMissRecord, ...] = ()
    require_same_class_evidence: bool = True
    require_behavior_binding: bool = False
    allow_scoped_confidence: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "ui_misses", tuple(self.ui_misses))
        object.__setattr__(self, "require_behavior_binding", bool(self.require_behavior_binding))

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "ui_misses": [miss.to_dict() for miss in self.ui_misses],
            "require_same_class_evidence": self.require_same_class_evidence,
            "require_behavior_binding": self.require_behavior_binding,
            "allow_scoped_confidence": self.allow_scoped_confidence,
        }


def backfeed_model_miss_to_behavior_ledger(
    miss: UIModelMissRecord,
    ledger: BehaviorCommitmentLedger | Mapping[str, Any],
    *,
    top_k: int = 5,
) -> ModelMissBehaviorBackfeed:
    """Find an existing same-plane commitment before proposing a new promise."""

    canonical_terms = (
        (miss.affected_commitment_id,) if miss.affected_commitment_id else ()
    )
    report = query_behavior_commitments(
        ledger,
        BehaviorLookupQuery(
            task_summary=miss.observed_failure,
            primary_plane=miss.affected_behavior_plane,
            canonical_terms=canonical_terms,
            error_signatures=miss.error_signatures,
            top_k=top_k,
        ),
    )
    related = tuple(ModelMissBehaviorContext.from_hit(hit) for hit in report.related_hits)
    candidates = tuple(ModelMissBehaviorContext.from_hit(hit) for hit in report.candidate_hits)
    if report.status != BCL_LOOKUP_STATUS_PERFORMED:
        disposition = MODEL_MISS_BACKFEED_BLOCKED
        reason = report.fallback_reason or "behavior ledger lookup did not run"
        primary = None
    elif report.plane_ambiguity:
        disposition = MODEL_MISS_BACKFEED_AMBIGUOUS
        reason = report.fallback_reason or "behavior plane or commitment is ambiguous"
        primary = None
    elif report.primary_hits:
        disposition = MODEL_MISS_BACKFEED_REUSE_EXISTING
        primary = ModelMissBehaviorContext.from_hit(report.primary_hits[0])
        reason = "reuse the existing same-plane behavior commitment and owner model"
    else:
        disposition = MODEL_MISS_BACKFEED_COVERAGE_GAP
        primary = None
        reason = "no registered same-plane promise matched; coverage-gap registration is required"
    return ModelMissBehaviorBackfeed(
        disposition,
        report.status,
        primary_context=primary,
        related_context=related,
        candidate_context=candidates,
        ledger_fingerprint=report.ledger_fingerprint,
        reason=reason,
    )


def apply_model_miss_behavior_backfeed(
    miss: UIModelMissRecord,
    backfeed: ModelMissBehaviorBackfeed,
) -> UIModelMissRecord:
    """Return a record bound to lookup evidence; never creates a commitment."""

    primary = backfeed.primary_context
    return replace(
        miss,
        affected_behavior_plane=(
            primary.behavior_plane if primary is not None else miss.affected_behavior_plane
        ),
        affected_commitment_id=(
            primary.commitment_id if primary is not None else miss.affected_commitment_id
        ),
        primary_owner_model_id=(
            primary.primary_owner_model_id if primary is not None else miss.primary_owner_model_id
        ),
        related_behavior_context=backfeed.related_context,
        behavior_lookup_status=backfeed.lookup_status,
        behavior_ledger_fingerprint=backfeed.ledger_fingerprint,
        behavior_coverage_gap_candidate=(
            backfeed.disposition == MODEL_MISS_BACKFEED_COVERAGE_GAP
        ),
    )


@dataclass(frozen=True)
class UIModelMissFinding:
    """One UI model-miss review gap."""

    code: str
    message: str
    severity: str = "blocker"
    miss_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "miss_id", str(self.miss_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "miss_id": self.miss_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class UIModelMissReviewReport:
    """Structured review result for UI model-miss records."""

    ok: bool
    plan_id: str
    findings: tuple[UIModelMissFinding, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "findings", tuple(self.findings))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: ui_model_miss_review={self.plan_id} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "plan_id": self.plan_id,
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
        }


def review_ui_model_misses(plan: UIModelMissReviewPlan) -> UIModelMissReviewReport:
    """Review UI failures that escaped after prior green FlowGuard evidence."""

    findings: list[UIModelMissFinding] = []
    if not plan.plan_id:
        findings.append(UIModelMissFinding("missing_ui_model_miss_plan_id", "UI model miss review has no plan id"))
    if not plan.ui_misses:
        findings.append(UIModelMissFinding("missing_ui_model_miss_records", "UI model miss review has no miss records"))

    seen: set[str] = set()
    for miss in plan.ui_misses:
        if miss.miss_id in seen:
            findings.append(
                UIModelMissFinding(
                    "duplicate_ui_model_miss_id",
                    f"UI model miss {miss.miss_id} is declared more than once",
                    miss_id=miss.miss_id,
                )
            )
        seen.add(miss.miss_id)
        if not miss.previous_claim_id:
            findings.append(
                UIModelMissFinding(
                    "ui_model_miss_missing_previous_claim",
                    "UI model miss must preserve the previous green claim id",
                    miss_id=miss.miss_id,
                )
            )
        if not miss.previous_green_reason:
            findings.append(
                UIModelMissFinding(
                    "ui_model_miss_missing_previous_green_reason",
                    "UI model miss must record why previous evidence looked green",
                    miss_id=miss.miss_id,
                )
            )
        if not miss.observed_failure:
            findings.append(
                UIModelMissFinding(
                    "ui_model_miss_missing_observed_failure",
                    "UI model miss must record the user-observed failure",
                    miss_id=miss.miss_id,
                )
            )
        if not miss.observed_failure_evidence_ref:
            findings.append(
                UIModelMissFinding(
                    "ui_model_miss_missing_observed_evidence",
                    "UI model miss must preserve observed failure evidence",
                    miss_id=miss.miss_id,
                )
            )
        if miss.miss_type not in UI_MODEL_MISS_TYPES:
            findings.append(
                UIModelMissFinding(
                    "ui_model_miss_unknown_type",
                    f"UI model miss type {miss.miss_type!r} is not recognized",
                    miss_id=miss.miss_id,
                )
            )
        behavior_binding_declared = bool(
            miss.affected_behavior_plane
            or miss.affected_commitment_id
            or miss.primary_owner_model_id
            or miss.related_behavior_context
            or miss.error_signatures
            or miss.error_evidence_ids
            or miss.behavior_lookup_status
            or miss.behavior_ledger_fingerprint
            or miss.behavior_coverage_gap_candidate
        )
        if plan.require_behavior_binding or behavior_binding_declared:
            if miss.affected_behavior_plane not in BCL_BEHAVIOR_PLANES:
                findings.append(
                    UIModelMissFinding(
                        "ui_model_miss_behavior_plane_missing_or_invalid",
                        "Model Miss must identify the execution plane whose promise failed.",
                        miss_id=miss.miss_id,
                        metadata={"affected_behavior_plane": miss.affected_behavior_plane},
                    )
                )
            if miss.behavior_coverage_gap_candidate:
                findings.append(
                    UIModelMissFinding(
                        "ui_model_miss_behavior_coverage_gap_unregistered",
                        "No existing same-plane promise matched; register and model the coverage gap before closure.",
                        miss_id=miss.miss_id,
                    )
                )
            if not miss.affected_commitment_id:
                findings.append(
                    UIModelMissFinding(
                        "ui_model_miss_commitment_missing",
                        "Model Miss must map the failure to an existing commitment before creating a new one.",
                        miss_id=miss.miss_id,
                    )
                )
            if not miss.primary_owner_model_id:
                findings.append(
                    UIModelMissFinding(
                        "ui_model_miss_owner_model_missing",
                        "Model Miss must preserve the selected commitment's primary owner model.",
                        miss_id=miss.miss_id,
                    )
                )
            if miss.behavior_lookup_status != BCL_LOOKUP_STATUS_PERFORMED:
                findings.append(
                    UIModelMissFinding(
                        "ui_model_miss_behavior_lookup_not_performed",
                        "Model Miss behavior lookup must be performed before broad repair closure.",
                        miss_id=miss.miss_id,
                        metadata={"behavior_lookup_status": miss.behavior_lookup_status},
                    )
                )
            if not miss.behavior_ledger_fingerprint:
                findings.append(
                    UIModelMissFinding(
                        "ui_model_miss_behavior_ledger_fingerprint_missing",
                        "Model Miss binding must identify the ledger revision it queried.",
                        miss_id=miss.miss_id,
                    )
                )
            if not miss.error_signatures:
                findings.append(
                    UIModelMissFinding(
                        "ui_model_miss_error_signature_missing",
                        "Model Miss binding must retain a bounded observed error signature.",
                        miss_id=miss.miss_id,
                    )
                )
            if miss.error_signatures and not miss.error_evidence_ids:
                findings.append(
                    UIModelMissFinding(
                        "ui_model_miss_error_signature_evidence_missing",
                        "Every error-signature set must be bound to observed evidence.",
                        miss_id=miss.miss_id,
                    )
                )
            related_ids: set[str] = set()
            for context in miss.related_behavior_context:
                if context.commitment_id == miss.affected_commitment_id:
                    findings.append(
                        UIModelMissFinding(
                            "ui_model_miss_related_context_promoted_to_primary",
                            "Typed related context must stay separate from the failed primary commitment.",
                            miss_id=miss.miss_id,
                            metadata={"context": context.to_dict()},
                        )
                    )
                if context.commitment_id in related_ids:
                    findings.append(
                        UIModelMissFinding(
                            "ui_model_miss_related_context_duplicate",
                            "The same related commitment is recorded more than once.",
                            miss_id=miss.miss_id,
                            metadata={"context": context.to_dict()},
                        )
                    )
                related_ids.add(context.commitment_id)
                if context.behavior_plane not in BCL_BEHAVIOR_PLANES:
                    findings.append(
                        UIModelMissFinding(
                            "ui_model_miss_related_context_plane_invalid",
                            "Related commitment context must retain a valid execution plane.",
                            miss_id=miss.miss_id,
                            metadata={"context": context.to_dict()},
                        )
                    )
        if not (miss.affected_capability_ids or miss.affected_control_ids or miss.affected_field_ids):
            findings.append(
                UIModelMissFinding(
                    "ui_model_miss_missing_affected_surface",
                    "UI model miss must identify affected capabilities, controls, or fields",
                    miss_id=miss.miss_id,
                )
            )
        if miss.missing_promised_capability_ids:
            duplicate_capabilities = sorted(
                {
                    capability_id
                    for capability_id in miss.missing_promised_capability_ids
                    if miss.missing_promised_capability_ids.count(capability_id) > 1
                }
            )
            if duplicate_capabilities:
                findings.append(
                    UIModelMissFinding(
                        "ui_model_miss_duplicate_missing_capability",
                        "UI model miss lists the same missing promised capability more than once",
                        miss_id=miss.miss_id,
                        metadata={"capability_ids": duplicate_capabilities},
                    )
                )
            if not set(miss.missing_promised_capability_ids).issubset(set(miss.affected_capability_ids)):
                findings.append(
                    UIModelMissFinding(
                        "ui_model_miss_missing_capability_not_affected",
                        "Missing promised UI capabilities must also be listed as affected capabilities",
                        miss_id=miss.miss_id,
                        metadata={"capability_ids": list(miss.missing_promised_capability_ids)},
                    )
                )
            if miss.miss_type not in UI_MODEL_MISS_PROMISED_CAPABILITY_TYPES:
                findings.append(
                    UIModelMissFinding(
                        "ui_model_miss_missing_capability_misclassified",
                        "Missing promised UI capabilities must be classified as boundary_missing or evidence_overclaimed",
                        miss_id=miss.miss_id,
                        metadata={
                            "capability_ids": list(miss.missing_promised_capability_ids),
                            "miss_type": miss.miss_type,
                        },
                    )
                )
        if plan.require_same_class_evidence and not miss.has_same_class_scope():
            findings.append(
                UIModelMissFinding(
                    "ui_model_miss_missing_same_class_scope",
                    "UI model miss must bind the finite same-class capability, control, or field scope before broad closure",
                    miss_id=miss.miss_id,
                )
            )
        if plan.require_same_class_evidence and not (miss.required_test_ids or miss.required_implementation_evidence_ids):
            findings.append(
                UIModelMissFinding(
                    "ui_model_miss_missing_same_class_evidence",
                    "UI model miss must name same-class tests or implementation evidence",
                    miss_id=miss.miss_id,
                )
            )
        if not miss.root_cause_backpropagation:
            findings.append(
                UIModelMissFinding(
                    "ui_model_miss_missing_backpropagation",
                    "UI model miss must backpropagate the root cause into model/test/validation gaps",
                    miss_id=miss.miss_id,
                )
            )
        if not miss.code_owner:
            findings.append(
                UIModelMissFinding(
                    "ui_model_miss_missing_code_owner",
                    "UI model miss must bind the repaired behavior to a code owner",
                    miss_id=miss.miss_id,
                )
            )
        if not miss.rationale:
            findings.append(
                UIModelMissFinding(
                    "ui_model_miss_missing_rationale",
                    "UI model miss must include rationale",
                    miss_id=miss.miss_id,
                )
            )

    blockers = tuple(finding for finding in findings if finding.severity == "blocker")
    return UIModelMissReviewReport(ok=not blockers, plan_id=plan.plan_id, findings=tuple(findings))


__all__ = [
    "MODEL_MISS_BACKFEED_AMBIGUOUS",
    "MODEL_MISS_BACKFEED_BLOCKED",
    "MODEL_MISS_BACKFEED_COVERAGE_GAP",
    "MODEL_MISS_BACKFEED_DISPOSITIONS",
    "MODEL_MISS_BACKFEED_REUSE_EXISTING",
    "UI_MODEL_MISS_ACTION_GRAMMAR_CONFLICT",
    "UI_MODEL_MISS_AFFORDANCE_MISMATCH",
    "UI_MODEL_MISS_BOUNDARY_MISSING",
    "UI_MODEL_MISS_CODE_BOUNDARY_MISMATCH",
    "UI_MODEL_MISS_DIALOG_RETURN_MISSING",
    "UI_MODEL_MISS_EVIDENCE_OVERCLAIMED",
    "UI_MODEL_MISS_HUMAN_WALKTHROUGH_FAILED",
    "UI_MODEL_MISS_INPUT_BRANCH_MISSING",
    "UI_MODEL_MISS_KEYBOARD_FOCUS_MISSING",
    "UI_MODEL_MISS_PROMISED_CAPABILITY_TYPES",
    "UI_MODEL_MISS_REGION_SEMANTICS_CONFLICT",
    "UI_MODEL_MISS_STATE_TOO_COARSE",
    "UI_MODEL_MISS_TYPES",
    "ModelMissBehaviorBackfeed",
    "ModelMissBehaviorContext",
    "UIModelMissFinding",
    "UIModelMissRecord",
    "UIModelMissReviewPlan",
    "UIModelMissReviewReport",
    "apply_model_miss_behavior_backfeed",
    "backfeed_model_miss_to_behavior_ledger",
    "review_ui_model_misses",
]
