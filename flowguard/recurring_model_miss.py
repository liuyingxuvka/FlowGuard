"""Recurring model-miss defect-family gate helpers.

This module keeps repeated same-class model misses inside the existing
Model-Miss Review, Model-Test Alignment, DevelopmentProcessFlow, TestMesh, and
Risk Evidence Ledger route family. It is a small helper API, not a new
FlowGuard skill or product-specific closure route.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Sequence

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
from .legacy_path_disposition import LEGACY_PATH_KIND_FIELD, LegacyPathDisposition, review_legacy_path_dispositions
from .proof_artifact import ProofArtifactRef, coerce_proof_artifact_ref, proof_artifact_gap_codes
from .risk_evidence_ledger import (
    RISK_CONFIDENCE_BLOCKED,
    RISK_CONFIDENCE_FULL,
    RISK_CONFIDENCE_SCOPED,
    RISK_PROOF_SCOPE_EXTERNAL_CONTRACT,
    RISK_PROOF_SCOPE_MIXED,
    RISK_PROOF_STATUS_ERROR,
    RISK_PROOF_STATUS_FAILED,
    RISK_PROOF_STATUS_NOT_RUN,
    RISK_PROOF_STATUS_PASSED,
    RISK_PROOF_STATUS_PROGRESS_ONLY,
    RISK_PROOF_STATUS_RUNNING,
    RISK_PROOF_STATUS_SKIPPED,
    RISK_PROOF_STATUS_STALE,
)


DEFECT_FAMILY_DECISION_FULL = "defect_family_gate_full_confidence"
DEFECT_FAMILY_DECISION_SCOPED = "defect_family_gate_scoped_confidence"
DEFECT_FAMILY_DECISION_BLOCKED = "defect_family_gate_blocked"
DEFECT_CASE_ROLE_OBSERVED_FAILURE = "observed_failure"
DEFECT_CASE_ROLE_SAME_CLASS_GENERALIZED = "same_class_generalized"
DEFECT_CASE_ROLE_HISTORICAL_HOLDOUT = "historical_holdout"
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

PASSING_DEFECT_FAMILY_STATUSES = {RISK_PROOF_STATUS_PASSED}
NON_PASSING_DEFECT_FAMILY_STATUSES = {
    RISK_PROOF_STATUS_FAILED,
    RISK_PROOF_STATUS_SKIPPED,
    RISK_PROOF_STATUS_STALE,
    RISK_PROOF_STATUS_NOT_RUN,
    RISK_PROOF_STATUS_RUNNING,
    RISK_PROOF_STATUS_PROGRESS_ONLY,
    RISK_PROOF_STATUS_ERROR,
}


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


@dataclass(frozen=True)
class DefectFamilyEvidence:
    """Current proof evidence for a promoted recurring model-miss family."""

    evidence_id: str
    result_status: str = RISK_PROOF_STATUS_NOT_RUN
    current: bool = True
    assertion_scope: str = RISK_PROOF_SCOPE_EXTERNAL_CONTRACT
    producer_route: str = ""
    command: str = ""
    summary: str = ""
    proof_artifact: ProofArtifactRef | Mapping[str, Any] | None = None
    stale_reasons: tuple[str, ...] = ()
    route_gap_codes: tuple[str, ...] = ()
    route_evidence_current: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "result_status", str(self.result_status))
        object.__setattr__(self, "assertion_scope", str(self.assertion_scope))
        object.__setattr__(self, "producer_route", str(self.producer_route))
        object.__setattr__(self, "command", str(self.command))
        object.__setattr__(self, "summary", str(self.summary))
        object.__setattr__(self, "proof_artifact", coerce_proof_artifact_ref(self.proof_artifact))
        object.__setattr__(self, "stale_reasons", _as_tuple(self.stale_reasons))
        object.__setattr__(self, "route_gap_codes", _as_tuple(self.route_gap_codes))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def has_current_pass(self) -> bool:
        return (
            self.result_status in PASSING_DEFECT_FAMILY_STATUSES
            and self.current
            and self.route_evidence_current
        )

    def has_external_scope(self) -> bool:
        return self.assertion_scope in {
            RISK_PROOF_SCOPE_EXTERNAL_CONTRACT,
            RISK_PROOF_SCOPE_MIXED,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "result_status": self.result_status,
            "current": self.current,
            "assertion_scope": self.assertion_scope,
            "producer_route": self.producer_route,
            "command": self.command,
            "summary": self.summary,
            "proof_artifact": self.proof_artifact.to_dict() if self.proof_artifact else None,
            "stale_reasons": list(self.stale_reasons),
            "route_gap_codes": list(self.route_gap_codes),
            "route_evidence_current": self.route_evidence_current,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class DefectFamilyCase:
    """One observed, generalized, or holdout case for a defect family."""

    case_id: str
    role: str
    description: str = ""
    source: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", str(self.case_id))
        object.__setattr__(self, "role", str(self.role))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "source", str(self.source))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "role": self.role,
            "description": self.description,
            "source": self.source,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class DefectFamilyGate:
    """A promoted same-class family that recurring model-miss closure depends on."""

    gate_id: str
    family_name: str = ""
    description: str = ""
    recurrence_count: int = 1
    high_risk: bool = False
    required: bool = False
    promoted: bool = False
    model_obligation_id: str = ""
    authority_boundary: str = ""
    cases: tuple[DefectFamilyCase, ...] = ()
    observed_failure_case_id: str = ""
    same_class_generalized_case_id: str = ""
    historical_holdout_case_id: str = ""
    proof_evidence_ids: tuple[str, ...] = ()
    legacy_path_dispositions: tuple[LegacyPathDisposition, ...] = ()
    root_cause_field_ids: tuple[str, ...] = ()
    same_class_field_ids: tuple[str, ...] = ()
    old_field_ids: tuple[str, ...] = ()
    affected_model_ids: tuple[str, ...] = ()
    affected_behavior_plane: str = ""
    affected_commitment_id: str = ""
    primary_owner_model_id: str = ""
    related_commitment_ids: tuple[str, ...] = ()
    error_signatures: tuple[str, ...] = ()
    error_evidence_ids: tuple[str, ...] = ()
    root_cause_dimension_ids: tuple[str, ...] = ()
    interaction_group_ids: tuple[str, ...] = ()
    observed_combination_case_id: str = ""
    generated_combination_case_ids: tuple[str, ...] = ()
    coverage_receipt_ids: tuple[str, ...] = ()
    scoped_confidence_reasons: tuple[str, ...] = ()
    next_actions: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "gate_id", str(self.gate_id))
        object.__setattr__(self, "family_name", str(self.family_name))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "recurrence_count", int(self.recurrence_count))
        object.__setattr__(self, "model_obligation_id", str(self.model_obligation_id))
        object.__setattr__(self, "authority_boundary", str(self.authority_boundary))
        object.__setattr__(self, "cases", tuple(self.cases))
        object.__setattr__(self, "observed_failure_case_id", str(self.observed_failure_case_id))
        object.__setattr__(
            self,
            "same_class_generalized_case_id",
            str(self.same_class_generalized_case_id),
        )
        object.__setattr__(self, "historical_holdout_case_id", str(self.historical_holdout_case_id))
        object.__setattr__(self, "proof_evidence_ids", _as_tuple(self.proof_evidence_ids))
        object.__setattr__(self, "legacy_path_dispositions", tuple(self.legacy_path_dispositions))
        object.__setattr__(self, "root_cause_field_ids", _as_tuple(self.root_cause_field_ids))
        object.__setattr__(self, "same_class_field_ids", _as_tuple(self.same_class_field_ids))
        object.__setattr__(self, "old_field_ids", _as_tuple(self.old_field_ids))
        object.__setattr__(self, "affected_model_ids", _as_tuple(self.affected_model_ids))
        object.__setattr__(self, "affected_behavior_plane", str(self.affected_behavior_plane))
        object.__setattr__(self, "affected_commitment_id", str(self.affected_commitment_id))
        object.__setattr__(self, "primary_owner_model_id", str(self.primary_owner_model_id))
        object.__setattr__(self, "related_commitment_ids", _as_tuple(self.related_commitment_ids))
        object.__setattr__(self, "error_signatures", _as_tuple(self.error_signatures))
        object.__setattr__(self, "error_evidence_ids", _as_tuple(self.error_evidence_ids))
        object.__setattr__(self, "root_cause_dimension_ids", _as_tuple(self.root_cause_dimension_ids))
        object.__setattr__(self, "interaction_group_ids", _as_tuple(self.interaction_group_ids))
        object.__setattr__(self, "observed_combination_case_id", str(self.observed_combination_case_id))
        object.__setattr__(self, "generated_combination_case_ids", _as_tuple(self.generated_combination_case_ids))
        object.__setattr__(self, "coverage_receipt_ids", _as_tuple(self.coverage_receipt_ids))
        object.__setattr__(
            self,
            "scoped_confidence_reasons",
            _as_tuple(self.scoped_confidence_reasons),
        )
        object.__setattr__(self, "next_actions", _as_tuple(self.next_actions))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def promotion_required(self) -> bool:
        return self.required or self.recurrence_count > 1 or self.high_risk

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "family_name": self.family_name,
            "description": self.description,
            "recurrence_count": self.recurrence_count,
            "high_risk": self.high_risk,
            "required": self.required,
            "promoted": self.promoted,
            "model_obligation_id": self.model_obligation_id,
            "authority_boundary": self.authority_boundary,
            "cases": [case.to_dict() for case in self.cases],
            "observed_failure_case_id": self.observed_failure_case_id,
            "same_class_generalized_case_id": self.same_class_generalized_case_id,
            "historical_holdout_case_id": self.historical_holdout_case_id,
            "proof_evidence_ids": list(self.proof_evidence_ids),
            "legacy_path_dispositions": [disposition.to_dict() for disposition in self.legacy_path_dispositions],
            "root_cause_field_ids": list(self.root_cause_field_ids),
            "same_class_field_ids": list(self.same_class_field_ids),
            "old_field_ids": list(self.old_field_ids),
            "affected_model_ids": list(self.affected_model_ids),
            "affected_behavior_plane": self.affected_behavior_plane,
            "affected_commitment_id": self.affected_commitment_id,
            "primary_owner_model_id": self.primary_owner_model_id,
            "related_commitment_ids": list(self.related_commitment_ids),
            "error_signatures": list(self.error_signatures),
            "error_evidence_ids": list(self.error_evidence_ids),
            "root_cause_dimension_ids": list(self.root_cause_dimension_ids),
            "interaction_group_ids": list(self.interaction_group_ids),
            "observed_combination_case_id": self.observed_combination_case_id,
            "generated_combination_case_ids": list(self.generated_combination_case_ids),
            "coverage_receipt_ids": list(self.coverage_receipt_ids),
            "scoped_confidence_reasons": list(self.scoped_confidence_reasons),
            "next_actions": list(self.next_actions),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class DefectFamilyGatePlan:
    """Review plan for recurring or high-risk model-miss family gates."""

    plan_id: str
    gates: tuple[DefectFamilyGate, ...] = ()
    proof_evidence: tuple[DefectFamilyEvidence, ...] = ()
    require_proof_artifacts: bool = False
    require_legacy_path_dispositions: bool = False
    allow_scoped_confidence: bool = True
    require_behavior_binding: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "gates", tuple(self.gates))
        object.__setattr__(self, "proof_evidence", tuple(self.proof_evidence))
        object.__setattr__(self, "require_behavior_binding", bool(self.require_behavior_binding))

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "gates": [gate.to_dict() for gate in self.gates],
            "proof_evidence": [evidence.to_dict() for evidence in self.proof_evidence],
            "require_proof_artifacts": self.require_proof_artifacts,
            "require_legacy_path_dispositions": self.require_legacy_path_dispositions,
            "allow_scoped_confidence": self.allow_scoped_confidence,
            "require_behavior_binding": self.require_behavior_binding,
        }


@dataclass(frozen=True)
class DefectFamilyGateFinding:
    """One recurring model-miss family gate gap."""

    code: str
    message: str
    severity: str = "blocker"
    gate_id: str = ""
    evidence_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "gate_id", str(self.gate_id))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "gate_id": self.gate_id,
            "evidence_id": self.evidence_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class DefectFamilyGateReport:
    """Structured review result for recurring model-miss family gates."""

    ok: bool
    plan_id: str
    decision: str
    confidence: str
    findings: tuple[DefectFamilyGateFinding, ...] = ()
    passed_gate_ids: tuple[str, ...] = ()
    scoped_gate_ids: tuple[str, ...] = ()
    blocked_gate_ids: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "passed_gate_ids", _as_tuple(self.passed_gate_ids))
        object.__setattr__(self, "scoped_gate_ids", _as_tuple(self.scoped_gate_ids))
        object.__setattr__(self, "blocked_gate_ids", _as_tuple(self.blocked_gate_ids))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: plan={self.plan_id} decision={self.decision} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard recurring model-miss defect-family gates ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"plan: {self.plan_id}",
            f"decision: {self.decision}",
            f"confidence: {self.confidence}",
            f"passed gates: {', '.join(self.passed_gate_ids) or '(none)'}",
            f"scoped gates: {', '.join(self.scoped_gate_ids) or '(none)'}",
            f"blocked gates: {', '.join(self.blocked_gate_ids) or '(none)'}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"gate: {finding.gate_id or '(none)'}",
                    f"evidence: {finding.evidence_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "plan_id": self.plan_id,
            "decision": self.decision,
            "confidence": self.confidence,
            "findings": [finding.to_dict() for finding in self.findings],
            "passed_gate_ids": list(self.passed_gate_ids),
            "scoped_gate_ids": list(self.scoped_gate_ids),
            "blocked_gate_ids": list(self.blocked_gate_ids),
            "summary": self.summary,
        }


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
                    "ui_model_miss_missing_same_class_scan",
                    "UI model miss must identify same-class capabilities, controls, or fields before broad closure",
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


def _finding(
    code: str,
    message: str,
    *,
    gate_id: str = "",
    evidence_id: str = "",
    severity: str = "blocker",
    metadata: Mapping[str, Any] | None = None,
) -> DefectFamilyGateFinding:
    return DefectFamilyGateFinding(
        code,
        message,
        severity=severity,
        gate_id=gate_id,
        evidence_id=evidence_id,
        metadata=metadata or {},
    )


def _decision_for(findings: Sequence[DefectFamilyGateFinding]) -> tuple[str, str, bool]:
    blockers = tuple(finding for finding in findings if finding.severity == "blocker")
    if not blockers:
        if findings:
            return DEFECT_FAMILY_DECISION_SCOPED, RISK_CONFIDENCE_SCOPED, True
        return DEFECT_FAMILY_DECISION_FULL, RISK_CONFIDENCE_FULL, True
    priority = (
        "recurring_miss_not_promoted",
        "duplicate_defect_family_gate_id",
        "duplicate_defect_family_evidence_id",
        "missing_defect_family_model_obligation",
        "missing_defect_family_authority_boundary",
        "missing_observed_failure_case",
        "missing_same_class_generalized_case",
        "missing_same_class_field_case",
        "missing_old_field_disposition",
        "missing_historical_holdout_case",
        "missing_defect_family_proof_evidence",
        "unknown_defect_family_evidence",
        "defect_family_route_gap_visible",
        "stale_defect_family_proof",
        "defect_family_proof_not_passing",
        "missing_current_defect_family_proof",
        "defect_family_proof_internal_path_only",
        "defect_family_scoped_confidence",
    )
    blocker_codes = {finding.code for finding in blockers}
    for code in priority:
        if code in blocker_codes:
            return code, RISK_CONFIDENCE_BLOCKED, False
    return DEFECT_FAMILY_DECISION_BLOCKED, RISK_CONFIDENCE_BLOCKED, False


def review_defect_family_gates(plan: DefectFamilyGatePlan) -> DefectFamilyGateReport:
    """Review recurring same-class model-miss families before broad closure claims."""

    findings: list[DefectFamilyGateFinding] = []

    gate_ids: set[str] = set()
    for gate in plan.gates:
        if gate.gate_id in gate_ids:
            findings.append(
                _finding(
                    "duplicate_defect_family_gate_id",
                    f"defect-family gate id {gate.gate_id!r} appears more than once",
                    gate_id=gate.gate_id,
                )
            )
        gate_ids.add(gate.gate_id)

    evidence_by_id: dict[str, DefectFamilyEvidence] = {}
    seen_evidence: set[str] = set()
    for evidence in plan.proof_evidence:
        if evidence.evidence_id in seen_evidence:
            findings.append(
                _finding(
                    "duplicate_defect_family_evidence_id",
                    f"defect-family evidence id {evidence.evidence_id!r} appears more than once",
                    evidence_id=evidence.evidence_id,
                )
            )
        seen_evidence.add(evidence.evidence_id)
        evidence_by_id[evidence.evidence_id] = evidence

    gate_blocked: dict[str, bool] = {gate.gate_id: False for gate in plan.gates}
    gate_scoped: dict[str, bool] = {gate.gate_id: False for gate in plan.gates}

    def add_gap(gate_id: str, finding: DefectFamilyGateFinding) -> None:
        findings.append(finding)
        if finding.severity == "blocker":
            gate_blocked[gate_id] = True
        else:
            gate_scoped[gate_id] = True

    required_fields = (
        ("model_obligation_id", "missing_defect_family_model_obligation", "promoted family has no owner model obligation"),
        ("authority_boundary", "missing_defect_family_authority_boundary", "promoted family has no authority boundary"),
    )

    for gate in plan.gates:
        promotion_required = gate.promotion_required()
        if promotion_required and not gate.promoted:
            add_gap(
                gate.gate_id,
                _finding(
                    "recurring_miss_not_promoted",
                    "recurring or high-risk same-class model miss has not been promoted to a defect-family gate",
                    gate_id=gate.gate_id,
                    metadata={"recurrence_count": gate.recurrence_count, "high_risk": gate.high_risk},
                ),
            )
            continue

        if not gate.promoted:
            continue

        for field_name, code, message in required_fields:
            if not getattr(gate, field_name):
                add_gap(gate.gate_id, _finding(code, message, gate_id=gate.gate_id))

        behavior_binding_declared = bool(
            gate.affected_behavior_plane
            or gate.affected_commitment_id
            or gate.primary_owner_model_id
            or gate.related_commitment_ids
            or gate.error_signatures
            or gate.error_evidence_ids
        )
        if plan.require_behavior_binding or behavior_binding_declared:
            if gate.affected_behavior_plane not in BCL_BEHAVIOR_PLANES:
                add_gap(
                    gate.gate_id,
                    _finding(
                        "defect_family_behavior_plane_missing_or_invalid",
                        "recurring miss family must retain the execution plane whose promise failed",
                        gate_id=gate.gate_id,
                        metadata={"affected_behavior_plane": gate.affected_behavior_plane},
                    ),
                )
            if not gate.affected_commitment_id:
                add_gap(
                    gate.gate_id,
                    _finding(
                        "defect_family_commitment_missing",
                        "recurring miss family must bind to the existing behavior commitment",
                        gate_id=gate.gate_id,
                    ),
                )
            if not gate.primary_owner_model_id:
                add_gap(
                    gate.gate_id,
                    _finding(
                        "defect_family_primary_owner_model_missing",
                        "recurring miss family must retain the commitment's primary owner model",
                        gate_id=gate.gate_id,
                    ),
                )
            if (
                gate.primary_owner_model_id
                and gate.affected_model_ids
                and gate.primary_owner_model_id not in gate.affected_model_ids
            ):
                add_gap(
                    gate.gate_id,
                    _finding(
                        "defect_family_primary_owner_not_affected",
                        "the commitment owner model must be present in affected_model_ids",
                        gate_id=gate.gate_id,
                    ),
                )
            if not gate.error_signatures:
                add_gap(
                    gate.gate_id,
                    _finding(
                        "defect_family_error_signature_missing",
                        "recurring miss family must retain bounded error signatures",
                        gate_id=gate.gate_id,
                    ),
                )
            if gate.error_signatures and not gate.error_evidence_ids:
                add_gap(
                    gate.gate_id,
                    _finding(
                        "defect_family_error_signature_evidence_missing",
                        "recurring miss error signatures must be bound to observed evidence",
                        gate_id=gate.gate_id,
                    ),
                )
            if gate.affected_commitment_id in set(gate.related_commitment_ids):
                add_gap(
                    gate.gate_id,
                    _finding(
                        "defect_family_related_commitment_is_primary",
                        "typed related commitments must stay separate from the failed primary commitment",
                        gate_id=gate.gate_id,
                    ),
                )

        case_roles = {case.role for case in gate.cases}
        has_observed_case = bool(gate.observed_failure_case_id) or DEFECT_CASE_ROLE_OBSERVED_FAILURE in case_roles
        has_same_class_case = (
            bool(gate.same_class_generalized_case_id)
            or DEFECT_CASE_ROLE_SAME_CLASS_GENERALIZED in case_roles
        )
        has_holdout_case = bool(gate.historical_holdout_case_id) or DEFECT_CASE_ROLE_HISTORICAL_HOLDOUT in case_roles
        if not has_observed_case:
            add_gap(
                gate.gate_id,
                _finding(
                    "missing_observed_failure_case",
                    "promoted family has no observed failure case",
                    gate_id=gate.gate_id,
                ),
            )
        if not has_same_class_case:
            add_gap(
                gate.gate_id,
                _finding(
                    "missing_same_class_generalized_case",
                    "promoted family has no same-class generalized case",
                    gate_id=gate.gate_id,
                ),
            )
        if gate.root_cause_field_ids and not gate.same_class_field_ids:
            add_gap(
                gate.gate_id,
                _finding(
                    "missing_same_class_field_case",
                    "field-root-cause model miss has no same-class field case ids",
                    gate_id=gate.gate_id,
                    metadata={"root_cause_field_ids": list(gate.root_cause_field_ids)},
                ),
            )
        if gate.observed_combination_case_id and not gate.interaction_group_ids:
            add_gap(
                gate.gate_id,
                _finding(
                    "missing_combination_interaction_group",
                    "combination-root-cause model miss has no interaction group id to deepen",
                    gate_id=gate.gate_id,
                    metadata={
                        "observed_combination_case_id": gate.observed_combination_case_id,
                        "affected_model_ids": list(gate.affected_model_ids),
                    },
                ),
            )
        if gate.observed_combination_case_id and not gate.coverage_receipt_ids:
            add_gap(
                gate.gate_id,
                _finding(
                    "missing_combination_coverage_receipt",
                    "combination-root-cause model miss has no coverage receipt proving the upgraded matrix",
                    gate_id=gate.gate_id,
                    metadata={
                        "observed_combination_case_id": gate.observed_combination_case_id,
                        "generated_combination_case_ids": list(gate.generated_combination_case_ids),
                    },
                ),
            )
        if not has_holdout_case:
            add_gap(
                gate.gate_id,
                _finding(
                    "missing_historical_holdout_case",
                    "promoted family has no historical holdout case",
                    gate_id=gate.gate_id,
                ),
            )

        if not gate.proof_evidence_ids:
            add_gap(
                gate.gate_id,
                _finding(
                    "missing_defect_family_proof_evidence",
                    "promoted family has no current proof evidence",
                    gate_id=gate.gate_id,
                ),
            )
            continue

        current_any_pass = False
        current_external_pass = False
        for evidence_id in gate.proof_evidence_ids:
            evidence = evidence_by_id.get(evidence_id)
            if evidence is None:
                add_gap(
                    gate.gate_id,
                    _finding(
                        "unknown_defect_family_evidence",
                        f"defect-family gate references unknown evidence {evidence_id!r}",
                        gate_id=gate.gate_id,
                        evidence_id=evidence_id,
                    ),
                )
                continue

            if evidence.route_gap_codes:
                add_gap(
                    gate.gate_id,
                    _finding(
                        "defect_family_route_gap_visible",
                        "defect-family proof route still has unresolved gaps",
                        gate_id=gate.gate_id,
                        evidence_id=evidence_id,
                        metadata={"route_gap_codes": evidence.route_gap_codes},
                    ),
                )
            if not evidence.current or evidence.stale_reasons or not evidence.route_evidence_current:
                add_gap(
                    gate.gate_id,
                    _finding(
                        "stale_defect_family_proof",
                        "defect-family proof evidence is stale or its route evidence is stale",
                        gate_id=gate.gate_id,
                        evidence_id=evidence_id,
                        metadata={"stale_reasons": evidence.stale_reasons},
                    ),
                )
            if evidence.result_status in NON_PASSING_DEFECT_FAMILY_STATUSES:
                add_gap(
                    gate.gate_id,
                    _finding(
                        "defect_family_proof_not_passing",
                        f"defect-family proof evidence status is {evidence.result_status}",
                        gate_id=gate.gate_id,
                        evidence_id=evidence_id,
                    ),
                )
            if plan.require_proof_artifacts:
                for code, message in proof_artifact_gap_codes(
                    evidence.proof_artifact,
                    declared_status=evidence.result_status,
                    required_obligation_ids=(gate.model_obligation_id,),
                    require_result_path=True,
                    require_fingerprints=True,
                    require_external_scope=True,
                ):
                    add_gap(
                        gate.gate_id,
                        _finding(
                            code.replace("proof_artifact", "defect_family_proof_artifact"),
                            message,
                            gate_id=gate.gate_id,
                            evidence_id=evidence_id,
                            metadata={"evidence": evidence.to_dict()},
                        ),
                    )
            if evidence.has_current_pass():
                current_any_pass = True
                if evidence.has_external_scope():
                    current_external_pass = True

        if gate.proof_evidence_ids and not current_any_pass:
            add_gap(
                gate.gate_id,
                _finding(
                    "missing_current_defect_family_proof",
                    "defect-family gate has no current passing proof evidence",
                    gate_id=gate.gate_id,
                ),
            )
        if gate.proof_evidence_ids and current_any_pass and not current_external_pass:
            add_gap(
                gate.gate_id,
                _finding(
                    "defect_family_proof_internal_path_only",
                    "passing defect-family proof does not exercise the external authority boundary",
                    gate_id=gate.gate_id,
                ),
            )

        if plan.require_legacy_path_dispositions:
            if not gate.legacy_path_dispositions:
                add_gap(
                    gate.gate_id,
                    _finding(
                        "missing_legacy_path_disposition",
                        "promoted defect-family gate does not dispose old or alternate paths",
                        gate_id=gate.gate_id,
                    ),
                )
            legacy_report = review_legacy_path_dispositions(
                gate.legacy_path_dispositions,
                require_proof_artifacts=plan.require_proof_artifacts,
            )
            for finding in legacy_report.findings:
                add_gap(
                    gate.gate_id,
                    _finding(
                        finding.code,
                        finding.message,
                        gate_id=gate.gate_id,
                        metadata={"legacy_path": finding.to_dict()},
                    ),
                )
            if gate.old_field_ids:
                dispositioned_old_fields = {
                    disposition.field_id
                    for disposition in gate.legacy_path_dispositions
                    if disposition.path_kind == LEGACY_PATH_KIND_FIELD and disposition.field_id
                }
                for field_id in sorted(set(gate.old_field_ids) - dispositioned_old_fields):
                    add_gap(
                        gate.gate_id,
                        _finding(
                            "missing_old_field_disposition",
                            "promoted field-root-cause gate does not dispose an old field",
                            gate_id=gate.gate_id,
                            metadata={
                                "old_field_id": field_id,
                                "old_field_ids": list(gate.old_field_ids),
                            },
                        ),
                    )

        if gate.scoped_confidence_reasons:
            severity = "warning" if plan.allow_scoped_confidence else "blocker"
            add_gap(
                gate.gate_id,
                _finding(
                    "defect_family_scoped_confidence",
                    "defect-family gate has explicit scoped-confidence reasons",
                    gate_id=gate.gate_id,
                    severity=severity,
                    metadata={"scoped_confidence_reasons": gate.scoped_confidence_reasons},
                ),
            )

    decision, confidence, ok = _decision_for(findings)
    blocked_gate_ids = tuple(gate_id for gate_id, blocked in gate_blocked.items() if blocked)
    scoped_gate_ids = tuple(
        gate_id
        for gate_id, scoped in gate_scoped.items()
        if scoped and not gate_blocked.get(gate_id, False)
    )
    passed_gate_ids = tuple(
        gate.gate_id
        for gate in plan.gates
        if gate.promoted and not gate_blocked.get(gate.gate_id, False) and not gate_scoped.get(gate.gate_id, False)
    )
    return DefectFamilyGateReport(
        ok=ok,
        plan_id=plan.plan_id,
        decision=decision,
        confidence=confidence,
        findings=tuple(findings),
        passed_gate_ids=passed_gate_ids,
        scoped_gate_ids=scoped_gate_ids,
        blocked_gate_ids=blocked_gate_ids,
    )


DefectFamilyFinding = DefectFamilyGateFinding


__all__ = [
    "DEFECT_CASE_ROLE_HISTORICAL_HOLDOUT",
    "DEFECT_CASE_ROLE_OBSERVED_FAILURE",
    "DEFECT_CASE_ROLE_SAME_CLASS_GENERALIZED",
    "DEFECT_FAMILY_DECISION_BLOCKED",
    "DEFECT_FAMILY_DECISION_FULL",
    "DEFECT_FAMILY_DECISION_SCOPED",
    "MODEL_MISS_BACKFEED_AMBIGUOUS",
    "MODEL_MISS_BACKFEED_BLOCKED",
    "MODEL_MISS_BACKFEED_COVERAGE_GAP",
    "MODEL_MISS_BACKFEED_DISPOSITIONS",
    "MODEL_MISS_BACKFEED_REUSE_EXISTING",
    "UI_MODEL_MISS_BOUNDARY_MISSING",
    "UI_MODEL_MISS_ACTION_GRAMMAR_CONFLICT",
    "UI_MODEL_MISS_AFFORDANCE_MISMATCH",
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
    "DefectFamilyCase",
    "DefectFamilyEvidence",
    "DefectFamilyFinding",
    "DefectFamilyGate",
    "DefectFamilyGateFinding",
    "DefectFamilyGatePlan",
    "DefectFamilyGateReport",
    "NON_PASSING_DEFECT_FAMILY_STATUSES",
    "PASSING_DEFECT_FAMILY_STATUSES",
    "ModelMissBehaviorBackfeed",
    "ModelMissBehaviorContext",
    "UIModelMissFinding",
    "UIModelMissRecord",
    "UIModelMissReviewPlan",
    "UIModelMissReviewReport",
    "apply_model_miss_behavior_backfeed",
    "backfeed_model_miss_to_behavior_ledger",
    "review_defect_family_gates",
    "review_ui_model_misses",
]
