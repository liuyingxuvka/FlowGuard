"""Plan-intake, evidence-adapter, and claim-chain hardening helpers.

These helpers sit before or beside the existing FlowGuard route reports. They
do not parse project files, run tests, or replace Model-Test Alignment, Model
Miss Review, DevelopmentProcessFlow, or Risk Evidence Ledger. Their job is to
make under-declared plans, lossy evidence adapters, false-negative closure
gaps, weak mutation evidence, and over-broad confidence claims visible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable
from .risk_evidence_ledger import (
    RISK_CONFIDENCE_BLOCKED,
    RISK_CONFIDENCE_FULL,
    RISK_CONFIDENCE_SCOPED,
    RISK_PROOF_STATUS_ERROR,
    RISK_PROOF_STATUS_FAILED,
    RISK_PROOF_STATUS_NOT_RUN,
    RISK_PROOF_STATUS_PASSED,
    RISK_PROOF_STATUS_PROGRESS_ONLY,
    RISK_PROOF_STATUS_RUNNING,
    RISK_PROOF_STATUS_SKIPPED,
    RISK_PROOF_STATUS_STALE,
)


PLAN_INTAKE_DECISION_FULL = "plan_intake_full_confidence"
PLAN_INTAKE_DECISION_SCOPED = "plan_intake_scoped_confidence"
PLAN_INTAKE_DECISION_BLOCKED = "plan_intake_blocked"
PLAN_INTAKE_CONFIDENCE_FULL = RISK_CONFIDENCE_FULL
PLAN_INTAKE_CONFIDENCE_SCOPED = RISK_CONFIDENCE_SCOPED
PLAN_INTAKE_CONFIDENCE_BLOCKED = RISK_CONFIDENCE_BLOCKED

ADAPTER_CONFORMANCE_DECISION_FULL = "evidence_adapter_conformance_full_confidence"
ADAPTER_CONFORMANCE_DECISION_SCOPED = "evidence_adapter_conformance_scoped_confidence"
ADAPTER_CONFORMANCE_DECISION_BLOCKED = "evidence_adapter_conformance_blocked"
ADAPTER_DECISION_FULL = ADAPTER_CONFORMANCE_DECISION_FULL
ADAPTER_DECISION_SCOPED = ADAPTER_CONFORMANCE_DECISION_SCOPED

FALSE_NEGATIVE_DECISION_FULL = "false_negative_backpropagation_full_confidence"
FALSE_NEGATIVE_DECISION_SCOPED = "false_negative_backpropagation_scoped_confidence"
FALSE_NEGATIVE_DECISION_BLOCKED = "false_negative_backpropagation_blocked"

PLAN_MUTATION_DECISION_FULL = "plan_mutation_review_full_confidence"
PLAN_MUTATION_DECISION_SCOPED = "plan_mutation_review_scoped_confidence"
PLAN_MUTATION_DECISION_BLOCKED = "plan_mutation_review_blocked"

CLAIM_CHAIN_DECISION_FULL = "flowguard_claim_chain_full_confidence"
CLAIM_CHAIN_DECISION_SCOPED = "flowguard_claim_chain_scoped_confidence"
CLAIM_CHAIN_DECISION_BLOCKED = "flowguard_claim_chain_blocked"

CLAIM_SCOPE_PLAN_VALID_ONLY = "plan_valid_only"
CLAIM_SCOPE_MODEL_VALID = "model_valid"
CLAIM_SCOPE_CODE_BOUNDARY_VALID = "code_boundary_valid"
CLAIM_SCOPE_TEST_ALIGNMENT_VALID = "test_alignment_valid"
CLAIM_SCOPE_RUNTIME_REPLAY_VALID = "runtime_replay_valid"
CLAIM_SCOPE_RISK_EVIDENCE_VALID = "risk_evidence_valid"
CLAIM_SCOPE_ADAPTER_CONFORMANCE_VALID = "adapter_conformance_valid"
CLAIM_SCOPE_ADAPTER_CONFORMANT = CLAIM_SCOPE_ADAPTER_CONFORMANCE_VALID
CLAIM_SCOPE_FALSE_NEGATIVE_CLOSED = "false_negative_closed"
CLAIM_SCOPE_MUTATION_REVIEW_VALID = "mutation_review_valid"
CLAIM_SCOPE_PRODUCTION_CONFIDENCE = "production_confidence"
CLAIM_SCOPE_ORDER = (
    CLAIM_SCOPE_PLAN_VALID_ONLY,
    CLAIM_SCOPE_MODEL_VALID,
    CLAIM_SCOPE_CODE_BOUNDARY_VALID,
    CLAIM_SCOPE_TEST_ALIGNMENT_VALID,
    CLAIM_SCOPE_RUNTIME_REPLAY_VALID,
    CLAIM_SCOPE_RISK_EVIDENCE_VALID,
    CLAIM_SCOPE_ADAPTER_CONFORMANCE_VALID,
    CLAIM_SCOPE_FALSE_NEGATIVE_CLOSED,
    CLAIM_SCOPE_MUTATION_REVIEW_VALID,
    CLAIM_SCOPE_PRODUCTION_CONFIDENCE,
)

CLAIM_DEPENDENCY_STATUS_PASSED = RISK_PROOF_STATUS_PASSED
CLAIM_DEPENDENCY_STATUS_FAILED = RISK_PROOF_STATUS_FAILED
CLAIM_DEPENDENCY_STATUS_STALE = RISK_PROOF_STATUS_STALE
CLAIM_DEPENDENCY_STATUS_NOT_RUN = RISK_PROOF_STATUS_NOT_RUN
CLAIM_DEPENDENCY_STATUS_SCOPED = "scoped"
CLAIM_DEPENDENCY_STATUS_BLOCKED = "blocked"
CLAIM_STATUS_PASSED = CLAIM_DEPENDENCY_STATUS_PASSED
CLAIM_STATUS_FAILED = CLAIM_DEPENDENCY_STATUS_FAILED
CLAIM_STATUS_STALE = CLAIM_DEPENDENCY_STATUS_STALE
CLAIM_STATUS_NOT_RUN = CLAIM_DEPENDENCY_STATUS_NOT_RUN
CLAIM_STATUS_SCOPED = CLAIM_DEPENDENCY_STATUS_SCOPED
CLAIM_STATUS_BLOCKED = CLAIM_DEPENDENCY_STATUS_BLOCKED
PASSING_CLAIM_STATUSES = {CLAIM_STATUS_PASSED}
NON_PASSING_CLAIM_STATUSES = {
    CLAIM_STATUS_FAILED,
    CLAIM_STATUS_STALE,
    CLAIM_STATUS_NOT_RUN,
    CLAIM_STATUS_BLOCKED,
}

MUTATION_EXPECTED_FAIL = "fail"
MUTATION_EXPECTED_PASS = "pass"
MUTATION_RESULT_PASSED = RISK_PROOF_STATUS_PASSED
MUTATION_RESULT_FAILED = RISK_PROOF_STATUS_FAILED
MUTATION_RESULT_BLOCKED = "blocked"
MUTATION_RESULT_NOT_OK = "not_ok"
MUTATION_RESULT_NOT_RUN = RISK_PROOF_STATUS_NOT_RUN
MUTATION_RESULT_STALE = RISK_PROOF_STATUS_STALE

FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING = "model_input_missing"
FALSE_NEGATIVE_CAUSE_INVARIANT_TOO_WEAK = "invariant_too_weak"
FALSE_NEGATIVE_CAUSE_ORACLE_GAP = "oracle_gap"
FALSE_NEGATIVE_CAUSE_ADAPTER_MAPPING_LOSS = "adapter_mapping_loss"
FALSE_NEGATIVE_CAUSE_STALE_EVIDENCE = "stale_evidence"
FALSE_NEGATIVE_CAUSE_CLAIM_SCOPE_OVERPROMOTION = "claim_scope_overpromotion"
FALSE_NEGATIVE_CAUSE_OMITTED_INPUT = FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING
FALSE_NEGATIVE_CAUSE_WEAK_INVARIANT = FALSE_NEGATIVE_CAUSE_INVARIANT_TOO_WEAK
FALSE_NEGATIVE_CAUSE_ORACLE_TOO_PERMISSIVE = FALSE_NEGATIVE_CAUSE_ORACLE_GAP
FALSE_NEGATIVE_CAUSE_STALE_EVIDENCE_ACCEPTED = FALSE_NEGATIVE_CAUSE_STALE_EVIDENCE
FALSE_NEGATIVE_CAUSE_SCOPE_OVERCLAIM = FALSE_NEGATIVE_CAUSE_CLAIM_SCOPE_OVERPROMOTION
FALSE_NEGATIVE_CAUSES = {
    FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING,
    FALSE_NEGATIVE_CAUSE_INVARIANT_TOO_WEAK,
    FALSE_NEGATIVE_CAUSE_ORACLE_GAP,
    FALSE_NEGATIVE_CAUSE_ADAPTER_MAPPING_LOSS,
    FALSE_NEGATIVE_CAUSE_STALE_EVIDENCE,
    FALSE_NEGATIVE_CAUSE_CLAIM_SCOPE_OVERPROMOTION,
}

EVIDENCE_CLASSIFICATION_PASSED = RISK_PROOF_STATUS_PASSED
EVIDENCE_CLASSIFICATION_FAILED = RISK_PROOF_STATUS_FAILED
EVIDENCE_CLASSIFICATION_STALE = RISK_PROOF_STATUS_STALE
EVIDENCE_CLASSIFICATION_PROGRESS_ONLY = RISK_PROOF_STATUS_PROGRESS_ONLY
EVIDENCE_CLASSIFICATION_SKIPPED = RISK_PROOF_STATUS_SKIPPED
EVIDENCE_CLASSIFICATION_UNKNOWN = "unknown"
EVIDENCE_CLASSIFICATION_INTERNAL_PATH = "internal_path"

INTAKE_SOURCE_KIND_CODE = "code"
INTAKE_SOURCE_KIND_HISTORY = "history"
INTAKE_SOURCE_KIND_LOG = "log"
INTAKE_SOURCE_KIND_MANUAL = "manual"
INTAKE_SOURCE_KIND_RUNTIME = "runtime"
INTAKE_SOURCE_KIND_TEST = "test"

PLAN_SURFACE_KIND_CODE = "code"
PLAN_SURFACE_KIND_HISTORY = "history"
PLAN_SURFACE_KIND_LOG = "log"
PLAN_SURFACE_KIND_MANUAL = "manual"
PLAN_SURFACE_KIND_RUNTIME = "runtime"
PLAN_SURFACE_KIND_TEST = "test"
PLAN_SURFACE_KIND_USER_RISK = "user_risk"

PASSING_CLASSIFICATIONS = {RISK_PROOF_STATUS_PASSED}
LOSSY_RAW_CLASSIFICATIONS = {
    RISK_PROOF_STATUS_STALE,
    RISK_PROOF_STATUS_PROGRESS_ONLY,
    RISK_PROOF_STATUS_SKIPPED,
    RISK_PROOF_STATUS_NOT_RUN,
    RISK_PROOF_STATUS_RUNNING,
    RISK_PROOF_STATUS_ERROR,
    RISK_PROOF_STATUS_FAILED,
}


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


@dataclass(frozen=True)
class PlanSourceEvidence:
    """One source artifact used to construct a FlowGuard plan intake."""

    source_id: str
    source_kind: str = INTAKE_SOURCE_KIND_CODE
    current: bool = True
    supports_surface_ids: tuple[str, ...] = ()
    summary: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", str(self.source_id))
        object.__setattr__(self, "source_kind", str(self.source_kind))
        object.__setattr__(self, "supports_surface_ids", _as_tuple(self.supports_surface_ids))
        object.__setattr__(self, "summary", str(self.summary))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_kind": self.source_kind,
            "current": self.current,
            "supports_surface_ids": list(self.supports_surface_ids),
            "summary": self.summary,
            "metadata": to_jsonable(dict(self.metadata)),
        }


def _has_blockers(findings: Sequence[Any]) -> bool:
    return any(finding.severity == "blocker" for finding in findings)


def _confidence_for(findings: Sequence[Any]) -> tuple[bool, str]:
    if _has_blockers(findings):
        return False, RISK_CONFIDENCE_BLOCKED
    if findings:
        return True, RISK_CONFIDENCE_SCOPED
    return True, RISK_CONFIDENCE_FULL


def _decision_for(findings: Sequence[Any], *, full: str, scoped: str, blocked: str) -> tuple[bool, str, str]:
    ok, confidence = _confidence_for(findings)
    if not ok:
        blockers = tuple(finding for finding in findings if finding.severity == "blocker")
        return False, blockers[0].code if blockers else blocked, confidence
    if confidence == RISK_CONFIDENCE_SCOPED:
        return True, scoped, confidence
    return True, full, confidence


@dataclass(frozen=True)
class PlanIntakeRiskSurface:
    """One declared user-visible or historical risk surface in a plan."""

    surface_id: str
    surface_kind: str = PLAN_SURFACE_KIND_USER_RISK
    description: str = ""
    in_scope: bool = True
    included: bool = True
    reviewed: bool = True
    source_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    out_of_scope_reason: str = ""
    omission_reason: str = ""
    recurring: bool = False
    high_risk: bool = False
    observed_failure_ids: tuple[str, ...] = ()
    same_class_case_ids: tuple[str, ...] = ()
    historical_holdout_ids: tuple[str, ...] = ()
    scoped_reasons: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "surface_id", str(self.surface_id))
        object.__setattr__(self, "surface_kind", str(self.surface_kind))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "source_ids", _as_tuple(self.source_ids))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))
        object.__setattr__(self, "out_of_scope_reason", str(self.out_of_scope_reason))
        object.__setattr__(self, "omission_reason", str(self.omission_reason))
        object.__setattr__(self, "observed_failure_ids", _as_tuple(self.observed_failure_ids))
        object.__setattr__(self, "same_class_case_ids", _as_tuple(self.same_class_case_ids))
        object.__setattr__(self, "historical_holdout_ids", _as_tuple(self.historical_holdout_ids))
        object.__setattr__(self, "scoped_reasons", _as_tuple(self.scoped_reasons))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def has_mapping(self) -> bool:
        return bool(self.source_ids or self.evidence_ids)

    def needs_history(self) -> bool:
        return self.recurring or self.high_risk

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface_id": self.surface_id,
            "surface_kind": self.surface_kind,
            "description": self.description,
            "in_scope": self.in_scope,
            "included": self.included,
            "reviewed": self.reviewed,
            "source_ids": list(self.source_ids),
            "evidence_ids": list(self.evidence_ids),
            "out_of_scope_reason": self.out_of_scope_reason,
            "omission_reason": self.omission_reason,
            "recurring": self.recurring,
            "high_risk": self.high_risk,
            "observed_failure_ids": list(self.observed_failure_ids),
            "same_class_case_ids": list(self.same_class_case_ids),
            "historical_holdout_ids": list(self.historical_holdout_ids),
            "scoped_reasons": list(self.scoped_reasons),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class PlanIntakeCompletenessPlan:
    """Structured plan-intake evidence before broad confidence is claimed."""

    plan_id: str
    sources: tuple[PlanSourceEvidence, ...] = ()
    surfaces: tuple[PlanIntakeRiskSurface, ...] = ()
    source_evidence: tuple[PlanSourceEvidence, ...] = ()
    source_evidence_ids: tuple[str, ...] = ()
    source_evidence_current: bool = True
    risk_surfaces: tuple[PlanIntakeRiskSurface, ...] = ()
    required_surface_kinds: tuple[str, ...] = ()
    recurring_or_high_risk: bool = False
    happy_path_only: bool = False
    observed_failure_case_id: str = ""
    same_class_case_id: str = ""
    historical_holdout_case_id: str = ""
    allow_scoped_confidence: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "sources", tuple(self.sources))
        object.__setattr__(self, "surfaces", tuple(self.surfaces))
        object.__setattr__(self, "source_evidence", tuple(self.source_evidence))
        object.__setattr__(self, "source_evidence_ids", _as_tuple(self.source_evidence_ids))
        object.__setattr__(self, "risk_surfaces", tuple(self.risk_surfaces))
        object.__setattr__(self, "required_surface_kinds", _as_tuple(self.required_surface_kinds))
        object.__setattr__(self, "observed_failure_case_id", str(self.observed_failure_case_id))
        object.__setattr__(self, "same_class_case_id", str(self.same_class_case_id))
        object.__setattr__(self, "historical_holdout_case_id", str(self.historical_holdout_case_id))

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "sources": [source.to_dict() for source in self.sources],
            "surfaces": [surface.to_dict() for surface in self.surfaces],
            "source_evidence": [source.to_dict() for source in self.source_evidence],
            "source_evidence_ids": list(self.source_evidence_ids),
            "source_evidence_current": self.source_evidence_current,
            "risk_surfaces": [surface.to_dict() for surface in self.risk_surfaces],
            "required_surface_kinds": list(self.required_surface_kinds),
            "recurring_or_high_risk": self.recurring_or_high_risk,
            "happy_path_only": self.happy_path_only,
            "observed_failure_case_id": self.observed_failure_case_id,
            "same_class_case_id": self.same_class_case_id,
            "historical_holdout_case_id": self.historical_holdout_case_id,
            "allow_scoped_confidence": self.allow_scoped_confidence,
        }


@dataclass(frozen=True)
class PlanIntakeFinding:
    """One plan-intake completeness gap."""

    code: str
    message: str
    severity: str = "blocker"
    surface_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "surface_id", str(self.surface_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "surface_id": self.surface_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class PlanIntakeCompletenessReport:
    """Structured result of a plan-intake completeness review."""

    ok: bool
    plan_id: str
    decision: str
    confidence: str
    findings: tuple[PlanIntakeFinding, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "findings", tuple(self.findings))
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
            "=== flowguard plan intake completeness ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"plan: {self.plan_id}",
            f"decision: {self.decision}",
            f"confidence: {self.confidence}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"surface: {finding.surface_id or '(none)'}",
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
            "summary": self.summary,
        }


def _plan_finding(
    code: str,
    message: str,
    *,
    surface_id: str = "",
    severity: str = "blocker",
    metadata: Mapping[str, Any] | None = None,
) -> PlanIntakeFinding:
    return PlanIntakeFinding(
        code,
        message,
        severity=severity,
        surface_id=surface_id,
        metadata=metadata or {},
    )


def review_plan_intake_completeness(plan: PlanIntakeCompletenessPlan) -> PlanIntakeCompletenessReport:
    """Review whether a FlowGuard-backed plan declared its important surfaces."""

    findings: list[PlanIntakeFinding] = []
    sources = plan.sources + plan.source_evidence
    surfaces = plan.surfaces + plan.risk_surfaces
    source_ids = tuple(dict.fromkeys(plan.source_evidence_ids + tuple(source.source_id for source in sources)))
    if not source_ids:
        findings.append(_plan_finding("missing_current_source_evidence", "plan has no source evidence ids"))
    elif not plan.source_evidence_current:
        findings.append(
            _plan_finding(
                "source_evidence_not_current",
                "plan source evidence is stale or not tied to the current artifact set",
            )
        )
    for source in sources:
        if not source.current:
            findings.append(
                _plan_finding(
                    "source_evidence_not_current",
                    f"source evidence {source.source_id!r} is stale",
                    metadata={"source": source.to_dict()},
                )
            )
    if plan.happy_path_only:
        findings.append(_plan_finding("happy_path_only_plan", "plan is marked happy-path only"))

    seen: set[str] = set()
    surface_kinds = {surface.surface_kind for surface in surfaces}
    for required_kind in plan.required_surface_kinds:
        if required_kind not in surface_kinds:
            findings.append(
                _plan_finding(
                    "missing_required_surface_kind",
                    f"required surface kind {required_kind!r} is not present",
                    metadata={"surface_kind": required_kind},
                )
            )

    for surface in surfaces:
        if surface.surface_id in seen:
            findings.append(
                _plan_finding(
                    "duplicate_plan_intake_surface_id",
                    f"risk surface {surface.surface_id!r} appears more than once",
                    surface_id=surface.surface_id,
                )
            )
        seen.add(surface.surface_id)

        if not surface.in_scope:
            reason = surface.out_of_scope_reason or surface.omission_reason
            severity = "warning" if plan.allow_scoped_confidence and reason else "blocker"
            findings.append(
                _plan_finding(
                    "scoped_out_surface" if severity == "warning" else "scoped_out_surface_without_reason",
                    reason or "risk surface is out of scope without a reason",
                    surface_id=surface.surface_id,
                    severity=severity,
                )
            )
            continue

        if not surface.reviewed:
            findings.append(
                _plan_finding(
                    "in_scope_surface_not_reviewed",
                    "in-scope risk surface was not reviewed",
                    surface_id=surface.surface_id,
                )
            )
        if not surface.included:
            findings.append(
                _plan_finding(
                    "omitted_in_scope_surface",
                    "in-scope risk surface was omitted from the plan",
                    surface_id=surface.surface_id,
                )
            )
        if surface.included and not surface.has_mapping():
            findings.append(
                _plan_finding(
                    "missing_surface_evidence_mapping",
                    "included risk surface has no source or evidence mapping",
                    surface_id=surface.surface_id,
                )
            )
        if surface.needs_history() or plan.recurring_or_high_risk:
            if not surface.observed_failure_ids:
                findings.append(
                    _plan_finding(
                        "recurring_history_missing_observed_failure",
                        "recurring or high-risk surface has no observed failure reference",
                        surface_id=surface.surface_id,
                    )
                )
                if not plan.observed_failure_case_id:
                    findings.append(
                        _plan_finding(
                            "missing_observed_failure_case",
                            "recurring or high-risk surface has no observed failure reference",
                            surface_id=surface.surface_id,
                        )
                    )
            if not surface.same_class_case_ids and not plan.same_class_case_id:
                findings.append(
                    _plan_finding(
                        "recurring_history_missing_same_class_case",
                        "recurring or high-risk surface has no same-class case reference",
                        surface_id=surface.surface_id,
                    )
                )
                findings.append(
                    _plan_finding(
                        "missing_same_class_case",
                        "recurring or high-risk surface has no same-class case reference",
                        surface_id=surface.surface_id,
                    )
                )
            if not surface.historical_holdout_ids and not plan.historical_holdout_case_id:
                findings.append(
                    _plan_finding(
                        "recurring_history_missing_historical_holdout",
                        "recurring or high-risk surface has no historical holdout reference",
                        surface_id=surface.surface_id,
                    )
                )
                findings.append(
                    _plan_finding(
                        "missing_historical_holdout_case",
                        "recurring or high-risk surface has no historical holdout reference",
                        surface_id=surface.surface_id,
                    )
                )
        if surface.scoped_reasons:
            severity = "warning" if plan.allow_scoped_confidence else "blocker"
            findings.append(
                _plan_finding(
                    "plan_intake_scoped_surface",
                    "risk surface remains explicitly scoped",
                    surface_id=surface.surface_id,
                    severity=severity,
                    metadata={"scoped_reasons": list(surface.scoped_reasons)},
                )
            )

    ok, decision, confidence = _decision_for(
        findings,
        full=PLAN_INTAKE_DECISION_FULL,
        scoped=PLAN_INTAKE_DECISION_SCOPED,
        blocked=PLAN_INTAKE_DECISION_BLOCKED,
    )
    return PlanIntakeCompletenessReport(
        ok=ok,
        plan_id=plan.plan_id,
        decision=decision,
        confidence=confidence,
        findings=tuple(findings),
    )


@dataclass(frozen=True)
class EvidenceAdapterMapping:
    """One raw-artifact to FlowGuard-evidence adapter mapping row."""

    mapping_id: str
    raw_artifact_id: str = ""
    mapped_evidence_id: str = ""
    mapped_evidence_ids: tuple[str, ...] = ()
    raw_kind: str = "test"
    expected_classification: str = RISK_PROOF_STATUS_PASSED
    mapped_classification: str = RISK_PROOF_STATUS_PASSED
    raw_current: bool = True
    mapped_current: bool = True
    freshness_preserved: bool = True
    known_bad_fixture: bool = False
    adapter_rejected_known_bad: bool = False
    rejected: bool | None = None
    scoped_reasons: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "mapping_id", str(self.mapping_id))
        raw_artifact_id = str(self.raw_artifact_id or self.mapping_id)
        mapped_evidence_ids = _as_tuple(self.mapped_evidence_ids)
        mapped_evidence_id = str(self.mapped_evidence_id or (mapped_evidence_ids[0] if mapped_evidence_ids else ""))
        object.__setattr__(self, "raw_artifact_id", raw_artifact_id)
        object.__setattr__(self, "mapped_evidence_id", mapped_evidence_id)
        object.__setattr__(self, "mapped_evidence_ids", mapped_evidence_ids)
        object.__setattr__(self, "raw_kind", str(self.raw_kind))
        object.__setattr__(self, "expected_classification", str(self.expected_classification))
        object.__setattr__(self, "mapped_classification", str(self.mapped_classification))
        if self.rejected is not None:
            object.__setattr__(self, "adapter_rejected_known_bad", bool(self.rejected))
        object.__setattr__(self, "scoped_reasons", _as_tuple(self.scoped_reasons))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def mapped_as_current_pass(self) -> bool:
        return self.mapped_current and self.mapped_classification in PASSING_CLASSIFICATIONS

    def to_dict(self) -> dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "raw_artifact_id": self.raw_artifact_id,
            "mapped_evidence_id": self.mapped_evidence_id,
            "mapped_evidence_ids": list(self.mapped_evidence_ids),
            "raw_kind": self.raw_kind,
            "expected_classification": self.expected_classification,
            "mapped_classification": self.mapped_classification,
            "raw_current": self.raw_current,
            "mapped_current": self.mapped_current,
            "freshness_preserved": self.freshness_preserved,
            "known_bad_fixture": self.known_bad_fixture,
            "adapter_rejected_known_bad": self.adapter_rejected_known_bad,
            "rejected": self.rejected,
            "scoped_reasons": list(self.scoped_reasons),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class EvidenceAdapterConformancePlan:
    """Review plan for evidence adapter mappings."""

    adapter_id: str
    mappings: tuple[EvidenceAdapterMapping, ...] = ()
    allow_scoped_confidence: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "adapter_id", str(self.adapter_id))
        object.__setattr__(self, "mappings", tuple(self.mappings))

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "mappings": [mapping.to_dict() for mapping in self.mappings],
            "allow_scoped_confidence": self.allow_scoped_confidence,
        }


@dataclass(frozen=True)
class EvidenceAdapterFinding:
    """One evidence-adapter conformance gap."""

    code: str
    message: str
    severity: str = "blocker"
    mapping_id: str = ""
    raw_artifact_id: str = ""
    mapped_evidence_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "mapping_id", str(self.mapping_id))
        object.__setattr__(self, "raw_artifact_id", str(self.raw_artifact_id))
        object.__setattr__(self, "mapped_evidence_id", str(self.mapped_evidence_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "mapping_id": self.mapping_id,
            "raw_artifact_id": self.raw_artifact_id,
            "mapped_evidence_id": self.mapped_evidence_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class EvidenceAdapterConformanceReport:
    """Structured result of evidence-adapter conformance review."""

    ok: bool
    adapter_id: str
    decision: str
    confidence: str
    findings: tuple[EvidenceAdapterFinding, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "adapter_id", str(self.adapter_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "findings", tuple(self.findings))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: adapter={self.adapter_id} decision={self.decision} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard evidence adapter conformance ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"adapter: {self.adapter_id}",
            f"decision: {self.decision}",
            f"confidence: {self.confidence}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"mapping: {finding.mapping_id or '(none)'}",
                    f"raw: {finding.raw_artifact_id or '(none)'}",
                    f"mapped: {finding.mapped_evidence_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "adapter_id": self.adapter_id,
            "decision": self.decision,
            "confidence": self.confidence,
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
        }


def _adapter_finding(
    code: str,
    message: str,
    mapping: EvidenceAdapterMapping,
    *,
    severity: str = "blocker",
    metadata: Mapping[str, Any] | None = None,
) -> EvidenceAdapterFinding:
    return EvidenceAdapterFinding(
        code,
        message,
        severity=severity,
        mapping_id=mapping.mapping_id,
        raw_artifact_id=mapping.raw_artifact_id,
        mapped_evidence_id=mapping.mapped_evidence_id,
        metadata=metadata or {},
    )


def review_evidence_adapter_conformance(
    plan: EvidenceAdapterConformancePlan,
) -> EvidenceAdapterConformanceReport:
    """Review whether evidence adapter rows preserve identity, freshness, and status."""

    findings: list[EvidenceAdapterFinding] = []
    seen_mapping_ids: set[str] = set()
    seen_evidence_ids: set[str] = set()
    for mapping in plan.mappings:
        if mapping.mapping_id in seen_mapping_ids:
            findings.append(_adapter_finding("duplicate_adapter_mapping_id", "mapping id appears more than once", mapping))
        seen_mapping_ids.add(mapping.mapping_id)
        if mapping.mapped_evidence_id in seen_evidence_ids:
            findings.append(_adapter_finding("duplicate_mapped_evidence_id", "mapped evidence id appears more than once", mapping))
        seen_evidence_ids.add(mapping.mapped_evidence_id)

        if not mapping.raw_artifact_id:
            findings.append(_adapter_finding("missing_raw_artifact_id", "mapping has no raw artifact id", mapping))
        if not mapping.mapped_evidence_id:
            findings.append(_adapter_finding("missing_mapped_evidence_id", "mapping has no mapped FlowGuard evidence id", mapping))
        if mapping.known_bad_fixture and not mapping.adapter_rejected_known_bad:
            findings.append(
                _adapter_finding(
                    "known_bad_fixture_passed",
                    "known-bad adapter fixture was not rejected",
                    mapping,
                )
            )
            findings.append(
                _adapter_finding(
                    "known_bad_fixture_not_rejected",
                    "known-bad adapter fixture was not rejected",
                    mapping,
                )
            )
        if mapping.expected_classification != mapping.mapped_classification:
            findings.append(
                _adapter_finding(
                    "classification_loss",
                    "mapped evidence classification differs from raw expected classification",
                    mapping,
                    metadata={
                        "expected": mapping.expected_classification,
                        "mapped": mapping.mapped_classification,
                    },
                )
            )
            findings.append(
                _adapter_finding(
                    "adapter_classification_loss",
                    "mapped evidence classification differs from raw expected classification",
                    mapping,
                    metadata={
                        "expected": mapping.expected_classification,
                        "mapped": mapping.mapped_classification,
                    },
                )
            )
        if mapping.expected_classification in LOSSY_RAW_CLASSIFICATIONS and mapping.mapped_as_current_pass():
            findings.append(
                _adapter_finding(
                    "progress_or_stale_mapped_as_passing",
                    "non-passing raw evidence was mapped as current passing evidence",
                    mapping,
                    metadata={
                        "expected": mapping.expected_classification,
                        "mapped": mapping.mapped_classification,
                    },
                )
            )
            findings.append(
                _adapter_finding(
                    "non_passing_raw_mapped_as_passed",
                    "non-passing raw evidence was mapped as current passing evidence",
                    mapping,
                    metadata={
                        "expected": mapping.expected_classification,
                        "mapped": mapping.mapped_classification,
                    },
                )
            )
        if not mapping.raw_current and mapping.mapped_current:
            findings.append(
                _adapter_finding(
                    "freshness_loss",
                    "stale raw artifact was mapped as current evidence",
                    mapping,
                )
            )
        if not mapping.freshness_preserved:
            findings.append(
                _adapter_finding(
                    "freshness_not_preserved",
                    "adapter mapping does not preserve freshness metadata",
                    mapping,
                )
            )
        if mapping.scoped_reasons:
            severity = "warning" if plan.allow_scoped_confidence else "blocker"
            findings.append(
                _adapter_finding(
                    "adapter_conformance_scoped_mapping",
                    "adapter mapping remains explicitly scoped",
                    mapping,
                    severity=severity,
                    metadata={"scoped_reasons": list(mapping.scoped_reasons)},
                )
            )

    ok, decision, confidence = _decision_for(
        findings,
        full=ADAPTER_CONFORMANCE_DECISION_FULL,
        scoped=ADAPTER_CONFORMANCE_DECISION_SCOPED,
        blocked=ADAPTER_CONFORMANCE_DECISION_BLOCKED,
    )
    return EvidenceAdapterConformanceReport(
        ok=ok,
        adapter_id=plan.adapter_id,
        decision=decision,
        confidence=confidence,
        findings=tuple(findings),
    )


@dataclass(frozen=True)
class FalseNegativeCase:
    """One post-green miss that must be backpropagated before closure."""

    case_id: str
    previous_claim_id: str
    observed_failure_id: str
    cause: str
    would_have_failed_if: tuple[str, ...] = ()
    adapter_gap_ids: tuple[str, ...] = ()
    generalized_case_id: str = ""
    new_model_obligation_id: str = ""
    new_plan_item_ids: tuple[str, ...] = ()
    closure_evidence_ids: tuple[str, ...] = ()
    repair_evidence_ids: tuple[str, ...] = ()
    scoped_reasons: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", str(self.case_id))
        object.__setattr__(self, "previous_claim_id", str(self.previous_claim_id))
        object.__setattr__(self, "observed_failure_id", str(self.observed_failure_id))
        object.__setattr__(self, "cause", str(self.cause))
        object.__setattr__(self, "would_have_failed_if", _as_tuple(self.would_have_failed_if))
        object.__setattr__(self, "adapter_gap_ids", _as_tuple(self.adapter_gap_ids))
        object.__setattr__(self, "generalized_case_id", str(self.generalized_case_id))
        object.__setattr__(self, "new_model_obligation_id", str(self.new_model_obligation_id))
        object.__setattr__(self, "new_plan_item_ids", _as_tuple(self.new_plan_item_ids))
        object.__setattr__(self, "closure_evidence_ids", _as_tuple(self.closure_evidence_ids))
        object.__setattr__(self, "repair_evidence_ids", _as_tuple(self.repair_evidence_ids))
        object.__setattr__(self, "scoped_reasons", _as_tuple(self.scoped_reasons))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "previous_claim_id": self.previous_claim_id,
            "observed_failure_id": self.observed_failure_id,
            "cause": self.cause,
            "would_have_failed_if": list(self.would_have_failed_if),
            "adapter_gap_ids": list(self.adapter_gap_ids),
            "generalized_case_id": self.generalized_case_id,
            "new_model_obligation_id": self.new_model_obligation_id,
            "new_plan_item_ids": list(self.new_plan_item_ids),
            "closure_evidence_ids": list(self.closure_evidence_ids),
            "repair_evidence_ids": list(self.repair_evidence_ids),
            "scoped_reasons": list(self.scoped_reasons),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class FalseNegativeBackpropagationPlan:
    """Review plan for one or more post-green misses."""

    plan_id: str
    cases: tuple[FalseNegativeCase, ...] = ()
    recurring_or_high_risk: bool = False
    allow_scoped_confidence: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "cases", tuple(self.cases))

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "cases": [case.to_dict() for case in self.cases],
            "recurring_or_high_risk": self.recurring_or_high_risk,
            "allow_scoped_confidence": self.allow_scoped_confidence,
        }


@dataclass(frozen=True)
class FalseNegativeFinding:
    """One false-negative backpropagation gap."""

    code: str
    message: str
    severity: str = "blocker"
    case_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "case_id", str(self.case_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "case_id": self.case_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class FalseNegativeBackpropagationReport:
    """Structured result of a false-negative backpropagation review."""

    ok: bool
    plan_id: str
    decision: str
    confidence: str
    findings: tuple[FalseNegativeFinding, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "findings", tuple(self.findings))
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
            "=== flowguard false-negative backpropagation ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"plan: {self.plan_id}",
            f"decision: {self.decision}",
            f"confidence: {self.confidence}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"case: {finding.case_id or '(none)'}",
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
            "summary": self.summary,
        }


def _false_negative_finding(
    code: str,
    message: str,
    *,
    case_id: str = "",
    severity: str = "blocker",
    metadata: Mapping[str, Any] | None = None,
) -> FalseNegativeFinding:
    return FalseNegativeFinding(
        code,
        message,
        severity=severity,
        case_id=case_id,
        metadata=metadata or {},
    )


def review_false_negative_backpropagation(
    plan: FalseNegativeBackpropagationPlan,
) -> FalseNegativeBackpropagationReport:
    """Review whether post-green misses were traced back into a failing condition."""

    findings: list[FalseNegativeFinding] = []
    seen: set[str] = set()
    for case in plan.cases:
        if case.case_id in seen:
            findings.append(
                _false_negative_finding(
                    "duplicate_false_negative_case_id",
                    f"false-negative case {case.case_id!r} appears more than once",
                    case_id=case.case_id,
                )
            )
        seen.add(case.case_id)
        if not case.previous_claim_id:
            findings.append(
                _false_negative_finding(
                    "missing_previous_passing_claim",
                    "false-negative case has no prior passing claim id",
                    case_id=case.case_id,
                )
            )
        if not case.observed_failure_id:
            findings.append(
                _false_negative_finding(
                    "missing_observed_failure",
                    "false-negative case has no observed failure id",
                    case_id=case.case_id,
                )
            )
        if not case.cause:
            findings.append(
                _false_negative_finding(
                    "missing_false_negative_cause",
                    "false-negative case has no supported cause",
                    case_id=case.case_id,
                )
            )
        if not case.would_have_failed_if:
            findings.append(
                _false_negative_finding(
                    "missing_would_have_failed_if",
                    "false-negative case has no condition that would have failed before closure",
                    case_id=case.case_id,
                )
            )
        if not (case.new_plan_item_ids or case.new_model_obligation_id or case.repair_evidence_ids):
            findings.append(
                _false_negative_finding(
                    "missing_backprop_plan_update",
                    "false-negative case has no new plan or model item that captures the miss",
                    case_id=case.case_id,
                )
            )
            findings.append(
                _false_negative_finding(
                    "missing_new_model_obligation",
                    "false-negative case has no new model obligation or repair evidence that captures the miss",
                    case_id=case.case_id,
                )
            )
        if not case.closure_evidence_ids:
            findings.append(
                _false_negative_finding(
                    "missing_false_negative_closure_evidence",
                    "false-negative case has no closure evidence for the repaired plan/model/test gap",
                    case_id=case.case_id,
                )
            )
        if plan.recurring_or_high_risk and not case.generalized_case_id:
            findings.append(
                _false_negative_finding(
                    "missing_generalized_false_negative_case",
                    "recurring or high-risk false negative has no generalized same-class case",
                    case_id=case.case_id,
                )
            )
        if case.cause == FALSE_NEGATIVE_CAUSE_ADAPTER_MAPPING_LOSS and not case.adapter_gap_ids:
            findings.append(
                _false_negative_finding(
                    "missing_adapter_gap_for_adapter_cause",
                    "adapter-mapping false negative has no adapter gap id",
                    case_id=case.case_id,
                )
            )
        if case.scoped_reasons:
            severity = "warning" if plan.allow_scoped_confidence else "blocker"
            findings.append(
                _false_negative_finding(
                    "false_negative_backpropagation_scoped_case",
                    "false-negative closure remains explicitly scoped",
                    case_id=case.case_id,
                    severity=severity,
                    metadata={"scoped_reasons": list(case.scoped_reasons)},
                )
            )

    ok, decision, confidence = _decision_for(
        findings,
        full=FALSE_NEGATIVE_DECISION_FULL,
        scoped=FALSE_NEGATIVE_DECISION_SCOPED,
        blocked=FALSE_NEGATIVE_DECISION_BLOCKED,
    )
    return FalseNegativeBackpropagationReport(
        ok=ok,
        plan_id=plan.plan_id,
        decision=decision,
        confidence=confidence,
        findings=tuple(findings),
    )


@dataclass(frozen=True)
class PlanMutationCase:
    """One known-bad or expected-good plan mutation probe."""

    mutation_id: str
    target_id: str = ""
    mutation_kind: str = ""
    expected_to_fail: bool | None = None
    observed_ok: bool | None = None
    observed_decision: str = ""
    evidence_id: str = ""
    expected_result: str = MUTATION_EXPECTED_FAIL
    observed_result: str = MUTATION_RESULT_NOT_RUN
    check_id: str = ""
    current: bool = True
    description: str = ""
    scoped_reasons: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "mutation_id", str(self.mutation_id))
        object.__setattr__(self, "target_id", str(self.target_id))
        object.__setattr__(self, "mutation_kind", str(self.mutation_kind))
        object.__setattr__(self, "observed_decision", str(self.observed_decision))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        expected_result = self.expected_result
        if self.expected_to_fail is not None:
            expected_result = MUTATION_EXPECTED_FAIL if self.expected_to_fail else MUTATION_EXPECTED_PASS
        observed_result = self.observed_result
        if self.observed_ok is not None:
            observed_result = MUTATION_RESULT_PASSED if self.observed_ok else MUTATION_RESULT_FAILED
        object.__setattr__(self, "expected_result", str(expected_result))
        object.__setattr__(self, "observed_result", str(observed_result))
        object.__setattr__(self, "check_id", str(self.check_id))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "scoped_reasons", _as_tuple(self.scoped_reasons))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "mutation_id": self.mutation_id,
            "target_id": self.target_id,
            "mutation_kind": self.mutation_kind,
            "expected_to_fail": self.expected_to_fail,
            "observed_ok": self.observed_ok,
            "observed_decision": self.observed_decision,
            "evidence_id": self.evidence_id,
            "expected_result": self.expected_result,
            "observed_result": self.observed_result,
            "check_id": self.check_id,
            "current": self.current,
            "description": self.description,
            "scoped_reasons": list(self.scoped_reasons),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class PlanMutationReviewPlan:
    """Review plan for known-bad plan/model/check mutations."""

    review_id: str
    mutations: tuple[PlanMutationCase, ...] = ()
    allow_scoped_confidence: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "review_id", str(self.review_id))
        object.__setattr__(self, "mutations", tuple(self.mutations))

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "mutations": [mutation.to_dict() for mutation in self.mutations],
            "allow_scoped_confidence": self.allow_scoped_confidence,
        }


@dataclass(frozen=True)
class PlanMutationFinding:
    """One plan mutation review gap."""

    code: str
    message: str
    severity: str = "blocker"
    mutation_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "mutation_id", str(self.mutation_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "mutation_id": self.mutation_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class PlanMutationReviewReport:
    """Structured result of known-bad mutation review."""

    ok: bool
    review_id: str
    decision: str
    confidence: str
    findings: tuple[PlanMutationFinding, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "review_id", str(self.review_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "findings", tuple(self.findings))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: review={self.review_id} decision={self.decision} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard plan mutation review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"review: {self.review_id}",
            f"decision: {self.decision}",
            f"confidence: {self.confidence}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"mutation: {finding.mutation_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "review_id": self.review_id,
            "decision": self.decision,
            "confidence": self.confidence,
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
        }


def _mutation_finding(
    code: str,
    message: str,
    *,
    mutation_id: str = "",
    severity: str = "blocker",
    metadata: Mapping[str, Any] | None = None,
) -> PlanMutationFinding:
    return PlanMutationFinding(
        code,
        message,
        severity=severity,
        mutation_id=mutation_id,
        metadata=metadata or {},
    )


def review_plan_mutations(plan: PlanMutationReviewPlan) -> PlanMutationReviewReport:
    """Review whether known-bad mutations fail before broad confidence is claimed."""

    findings: list[PlanMutationFinding] = []
    seen: set[str] = set()
    for mutation in plan.mutations:
        if mutation.mutation_id in seen:
            findings.append(
                _mutation_finding(
                    "duplicate_plan_mutation_id",
                    f"mutation {mutation.mutation_id!r} appears more than once",
                    mutation_id=mutation.mutation_id,
                )
            )
        seen.add(mutation.mutation_id)
        if not mutation.current or mutation.observed_result == MUTATION_RESULT_STALE:
            findings.append(
                _mutation_finding(
                    "stale_plan_mutation_result",
                    "mutation result is stale",
                    mutation_id=mutation.mutation_id,
                )
            )
        if mutation.observed_result in {MUTATION_RESULT_NOT_RUN, RISK_PROOF_STATUS_SKIPPED}:
            findings.append(
                _mutation_finding(
                    "plan_mutation_not_run",
                    "mutation has no current observed result",
                    mutation_id=mutation.mutation_id,
                )
            )
        if mutation.expected_result == MUTATION_EXPECTED_FAIL:
            if mutation.observed_result in {MUTATION_RESULT_PASSED, "ok"}:
                findings.append(
                    _mutation_finding(
                        "known_bad_mutation_passed",
                        "known-bad mutation passed instead of failing",
                        mutation_id=mutation.mutation_id,
                    )
                )
        elif mutation.expected_result == MUTATION_EXPECTED_PASS:
            if mutation.observed_result not in {MUTATION_RESULT_PASSED, "ok"}:
                findings.append(
                    _mutation_finding(
                        "expected_good_mutation_failed",
                        "expected-good mutation did not pass",
                        mutation_id=mutation.mutation_id,
                    )
                )
        else:
            findings.append(
                _mutation_finding(
                    "unknown_plan_mutation_expectation",
                    "mutation expected_result must be pass or fail",
                    mutation_id=mutation.mutation_id,
                    metadata={"expected_result": mutation.expected_result},
                )
            )
        if mutation.scoped_reasons:
            severity = "warning" if plan.allow_scoped_confidence else "blocker"
            findings.append(
                _mutation_finding(
                    "plan_mutation_scoped_result",
                    "mutation review remains explicitly scoped",
                    mutation_id=mutation.mutation_id,
                    severity=severity,
                    metadata={"scoped_reasons": list(mutation.scoped_reasons)},
                )
            )

    ok, decision, confidence = _decision_for(
        findings,
        full=PLAN_MUTATION_DECISION_FULL,
        scoped=PLAN_MUTATION_DECISION_SCOPED,
        blocked=PLAN_MUTATION_DECISION_BLOCKED,
    )
    return PlanMutationReviewReport(
        ok=ok,
        review_id=plan.review_id,
        decision=decision,
        confidence=confidence,
        findings=tuple(findings),
    )


@dataclass(frozen=True)
class FlowGuardClaim:
    """One typed FlowGuard claim in a claim-promotion graph."""

    claim_id: str
    claim_scope: str
    result_status: str = CLAIM_STATUS_PASSED
    confidence: str = RISK_CONFIDENCE_FULL
    current: bool = True
    evidence_ids: tuple[str, ...] = ()
    supports_claim_ids: tuple[str, ...] = ()
    report_id: str = ""
    scoped_reasons: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", str(self.claim_id))
        object.__setattr__(self, "claim_scope", str(self.claim_scope))
        object.__setattr__(self, "result_status", str(self.result_status))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))
        object.__setattr__(self, "supports_claim_ids", _as_tuple(self.supports_claim_ids))
        object.__setattr__(self, "report_id", str(self.report_id))
        object.__setattr__(self, "scoped_reasons", _as_tuple(self.scoped_reasons))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dependency(self) -> "FlowGuardClaimDependency":
        return FlowGuardClaimDependency(
            self.claim_id,
            self.claim_scope,
            status=self.result_status,
            current=self.current,
            confidence=self.confidence,
            report_id=self.report_id,
            evidence_id=self.evidence_ids[0] if self.evidence_ids else "",
            scoped_reasons=self.scoped_reasons,
            metadata=self.metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_scope": self.claim_scope,
            "result_status": self.result_status,
            "confidence": self.confidence,
            "current": self.current,
            "evidence_ids": list(self.evidence_ids),
            "supports_claim_ids": list(self.supports_claim_ids),
            "report_id": self.report_id,
            "scoped_reasons": list(self.scoped_reasons),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class FlowGuardClaimDependency:
    """One lower-scope report or evidence item used by a broader claim."""

    dependency_id: str
    claim_scope: str
    status: str = CLAIM_DEPENDENCY_STATUS_PASSED
    current: bool = True
    confidence: str = RISK_CONFIDENCE_FULL
    report_id: str = ""
    evidence_id: str = ""
    scoped_reasons: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "dependency_id", str(self.dependency_id))
        object.__setattr__(self, "claim_scope", str(self.claim_scope))
        object.__setattr__(self, "status", str(self.status))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "report_id", str(self.report_id))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "scoped_reasons", _as_tuple(self.scoped_reasons))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "dependency_id": self.dependency_id,
            "claim_scope": self.claim_scope,
            "status": self.status,
            "current": self.current,
            "confidence": self.confidence,
            "report_id": self.report_id,
            "evidence_id": self.evidence_id,
            "scoped_reasons": list(self.scoped_reasons),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class FlowGuardClaimChainPlan:
    """Review plan for promoting FlowGuard reports into a target claim scope."""

    claim_id: str
    target_scope: str = ""
    dependencies: tuple[FlowGuardClaimDependency, ...] = ()
    claims: tuple[FlowGuardClaim, ...] = ()
    target_claim_id: str = ""
    required_scope: str = ""
    allow_scoped_confidence: bool = True
    runtime_replay_required: bool = True
    risk_evidence_required: bool = True
    plan_intake_required: bool = True
    adapter_conformance_required: bool = False
    false_negative_backprop_required: bool = False
    mutation_review_required: bool = False
    require_false_negative_closure: bool = False
    require_mutation_review: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", str(self.claim_id))
        target_scope = str(self.target_scope or self.required_scope)
        claims = tuple(self.claims)
        if claims and self.target_claim_id:
            target = next((claim for claim in claims if claim.claim_id == self.target_claim_id), None)
            if target is not None and not target_scope:
                target_scope = target.claim_scope
        object.__setattr__(self, "target_scope", target_scope)
        object.__setattr__(self, "dependencies", tuple(self.dependencies))
        object.__setattr__(self, "claims", claims)
        object.__setattr__(self, "target_claim_id", str(self.target_claim_id))
        object.__setattr__(self, "required_scope", str(self.required_scope))

    def required_scopes(self) -> tuple[str, ...]:
        if self.target_scope != CLAIM_SCOPE_PRODUCTION_CONFIDENCE:
            return ()
        scopes: list[str] = []
        if self.plan_intake_required:
            scopes.append(CLAIM_SCOPE_PLAN_VALID_ONLY)
        if self.runtime_replay_required:
            scopes.append(CLAIM_SCOPE_RUNTIME_REPLAY_VALID)
        if self.risk_evidence_required:
            scopes.append(CLAIM_SCOPE_RISK_EVIDENCE_VALID)
        if self.adapter_conformance_required:
            scopes.append(CLAIM_SCOPE_ADAPTER_CONFORMANCE_VALID)
        if self.false_negative_backprop_required or self.require_false_negative_closure:
            scopes.append(CLAIM_SCOPE_FALSE_NEGATIVE_CLOSED)
        if self.mutation_review_required or self.require_mutation_review:
            scopes.append(CLAIM_SCOPE_MUTATION_REVIEW_VALID)
        return tuple(scopes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "target_scope": self.target_scope,
            "dependencies": [dependency.to_dict() for dependency in self.dependencies],
            "claims": [claim.to_dict() for claim in self.claims],
            "target_claim_id": self.target_claim_id,
            "required_scope": self.required_scope,
            "allow_scoped_confidence": self.allow_scoped_confidence,
            "runtime_replay_required": self.runtime_replay_required,
            "risk_evidence_required": self.risk_evidence_required,
            "plan_intake_required": self.plan_intake_required,
            "adapter_conformance_required": self.adapter_conformance_required,
            "false_negative_backprop_required": self.false_negative_backprop_required,
            "mutation_review_required": self.mutation_review_required,
            "require_false_negative_closure": self.require_false_negative_closure,
            "require_mutation_review": self.require_mutation_review,
        }


@dataclass(frozen=True)
class FlowGuardClaimChainFinding:
    """One unsupported claim-chain promotion gap."""

    code: str
    message: str
    severity: str = "blocker"
    dependency_id: str = ""
    claim_scope: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "dependency_id", str(self.dependency_id))
        object.__setattr__(self, "claim_scope", str(self.claim_scope))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "dependency_id": self.dependency_id,
            "claim_scope": self.claim_scope,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class FlowGuardClaimChainReport:
    """Structured result of a typed FlowGuard claim-chain review."""

    ok: bool
    claim_id: str
    target_scope: str
    decision: str
    confidence: str
    findings: tuple[FlowGuardClaimChainFinding, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", str(self.claim_id))
        object.__setattr__(self, "target_scope", str(self.target_scope))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "findings", tuple(self.findings))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: claim={self.claim_id} target={self.target_scope} decision={self.decision} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard typed claim chain ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"claim: {self.claim_id}",
            f"target: {self.target_scope}",
            f"decision: {self.decision}",
            f"confidence: {self.confidence}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"dependency: {finding.dependency_id or '(none)'}",
                    f"scope: {finding.claim_scope or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "claim_id": self.claim_id,
            "target_scope": self.target_scope,
            "decision": self.decision,
            "confidence": self.confidence,
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
        }


def _claim_finding(
    code: str,
    message: str,
    *,
    dependency_id: str = "",
    claim_scope: str = "",
    severity: str = "blocker",
    metadata: Mapping[str, Any] | None = None,
) -> FlowGuardClaimChainFinding:
    return FlowGuardClaimChainFinding(
        code,
        message,
        severity=severity,
        dependency_id=dependency_id,
        claim_scope=claim_scope,
        metadata=metadata or {},
    )


def _scope_rank(scope: str) -> int:
    try:
        return CLAIM_SCOPE_ORDER.index(scope)
    except ValueError:
        return -1


def review_flowguard_claim_chain(plan: FlowGuardClaimChainPlan) -> FlowGuardClaimChainReport:
    """Review whether lower-scope reports support the requested target claim."""

    findings: list[FlowGuardClaimChainFinding] = []
    claim_by_id = {claim.claim_id: claim for claim in plan.claims}
    target_claim = claim_by_id.get(plan.target_claim_id) if plan.target_claim_id else None
    dependencies_from_claims: tuple[FlowGuardClaimDependency, ...] = ()
    if target_claim is not None:
        required_scope = plan.required_scope or plan.target_scope or target_claim.claim_scope
        if _scope_rank(target_claim.claim_scope) < _scope_rank(required_scope):
            findings.append(
                _claim_finding(
                    "target_scope_too_narrow",
                    f"target claim {target_claim.claim_id} is {target_claim.claim_scope}, not {required_scope}",
                    dependency_id=target_claim.claim_id,
                    claim_scope=target_claim.claim_scope,
                    metadata={"required_scope": required_scope},
                )
            )
        dependencies_from_claims = tuple(
            claim_by_id[claim_id].to_dependency()
            for claim_id in target_claim.supports_claim_ids
            if claim_id in claim_by_id
        )
        missing_support_ids = tuple(
            claim_id for claim_id in target_claim.supports_claim_ids if claim_id not in claim_by_id
        )
        for claim_id in missing_support_ids:
            findings.append(
                _claim_finding(
                    "unknown_supported_claim",
                    f"target claim references unknown support claim {claim_id!r}",
                    dependency_id=target_claim.claim_id,
                    claim_scope=target_claim.claim_scope,
                    metadata={"missing_claim_id": claim_id},
                )
            )
    elif plan.claims and plan.target_claim_id:
        findings.append(
            _claim_finding(
                "missing_target_claim",
                f"target claim {plan.target_claim_id!r} is not present",
                dependency_id=plan.target_claim_id,
            )
        )

    dependencies = plan.dependencies + dependencies_from_claims
    seen: set[str] = set()
    current_by_scope: dict[str, list[FlowGuardClaimDependency]] = {}
    for dependency in dependencies:
        if dependency.dependency_id in seen:
            findings.append(
                _claim_finding(
                    "duplicate_claim_dependency_id",
                    f"claim dependency {dependency.dependency_id!r} appears more than once",
                    dependency_id=dependency.dependency_id,
                    claim_scope=dependency.claim_scope,
                )
            )
        seen.add(dependency.dependency_id)
        current_by_scope.setdefault(dependency.claim_scope, []).append(dependency)
        if not dependency.current:
            findings.append(
                _claim_finding(
                    "stale_claim_dependency",
                    "claim dependency is stale",
                    dependency_id=dependency.dependency_id,
                    claim_scope=dependency.claim_scope,
                )
            )
        if dependency.status == CLAIM_DEPENDENCY_STATUS_SCOPED:
            severity = "warning" if plan.allow_scoped_confidence else "blocker"
            findings.append(
                _claim_finding(
                    "scoped_claim_dependency",
                    "claim dependency is explicitly scoped",
                    dependency_id=dependency.dependency_id,
                    claim_scope=dependency.claim_scope,
                    severity=severity,
                )
            )
        elif dependency.status != CLAIM_DEPENDENCY_STATUS_PASSED:
            findings.append(
                _claim_finding(
                    "claim_dependency_not_passing",
                    f"claim dependency status is {dependency.status}",
                    dependency_id=dependency.dependency_id,
                    claim_scope=dependency.claim_scope,
                )
            )
        if dependency.confidence in {RISK_CONFIDENCE_SCOPED, "partial"} or dependency.scoped_reasons:
            severity = "warning" if plan.allow_scoped_confidence else "blocker"
            findings.append(
                _claim_finding(
                    "scoped_claim_dependency",
                    "claim dependency confidence is scoped",
                    dependency_id=dependency.dependency_id,
                    claim_scope=dependency.claim_scope,
                    severity=severity,
                    metadata={"scoped_reasons": list(dependency.scoped_reasons)},
                )
            )
        if dependency.confidence == RISK_CONFIDENCE_BLOCKED:
            findings.append(
                _claim_finding(
                    "blocked_claim_dependency",
                    "claim dependency confidence is blocked",
                    dependency_id=dependency.dependency_id,
                    claim_scope=dependency.claim_scope,
                )
            )

    for required_scope in plan.required_scopes():
        candidates = current_by_scope.get(required_scope, [])
        usable = tuple(
            dependency
            for dependency in candidates
            if dependency.current
            and dependency.status in {CLAIM_DEPENDENCY_STATUS_PASSED, CLAIM_DEPENDENCY_STATUS_SCOPED}
            and dependency.confidence != RISK_CONFIDENCE_BLOCKED
        )
        if not usable:
            findings.append(
                _claim_finding(
                    "missing_required_claim_scope",
                    f"target claim {plan.target_scope} lacks current support for {required_scope}",
                    claim_scope=required_scope,
                    metadata={"target_scope": plan.target_scope},
                )
            )

    ok, decision, confidence = _decision_for(
        findings,
        full=CLAIM_CHAIN_DECISION_FULL,
        scoped=CLAIM_CHAIN_DECISION_SCOPED,
        blocked=CLAIM_CHAIN_DECISION_BLOCKED,
    )
    return FlowGuardClaimChainReport(
        ok=ok,
        claim_id=plan.claim_id,
        target_scope=plan.target_scope,
        decision=decision,
        confidence=confidence,
        findings=tuple(findings),
    )


__all__ = [
    "ADAPTER_CONFORMANCE_DECISION_BLOCKED",
    "ADAPTER_CONFORMANCE_DECISION_FULL",
    "ADAPTER_CONFORMANCE_DECISION_SCOPED",
    "ADAPTER_DECISION_FULL",
    "ADAPTER_DECISION_SCOPED",
    "CLAIM_CHAIN_DECISION_BLOCKED",
    "CLAIM_CHAIN_DECISION_FULL",
    "CLAIM_CHAIN_DECISION_SCOPED",
    "CLAIM_DEPENDENCY_STATUS_BLOCKED",
    "CLAIM_DEPENDENCY_STATUS_FAILED",
    "CLAIM_DEPENDENCY_STATUS_NOT_RUN",
    "CLAIM_DEPENDENCY_STATUS_PASSED",
    "CLAIM_DEPENDENCY_STATUS_SCOPED",
    "CLAIM_DEPENDENCY_STATUS_STALE",
    "CLAIM_SCOPE_ADAPTER_CONFORMANT",
    "CLAIM_SCOPE_ADAPTER_CONFORMANCE_VALID",
    "CLAIM_SCOPE_CODE_BOUNDARY_VALID",
    "CLAIM_SCOPE_FALSE_NEGATIVE_CLOSED",
    "CLAIM_SCOPE_MODEL_VALID",
    "CLAIM_SCOPE_MUTATION_REVIEW_VALID",
    "CLAIM_SCOPE_ORDER",
    "CLAIM_SCOPE_PLAN_VALID_ONLY",
    "CLAIM_SCOPE_PRODUCTION_CONFIDENCE",
    "CLAIM_SCOPE_RISK_EVIDENCE_VALID",
    "CLAIM_SCOPE_RUNTIME_REPLAY_VALID",
    "CLAIM_SCOPE_TEST_ALIGNMENT_VALID",
    "CLAIM_STATUS_BLOCKED",
    "CLAIM_STATUS_FAILED",
    "CLAIM_STATUS_NOT_RUN",
    "CLAIM_STATUS_PASSED",
    "CLAIM_STATUS_SCOPED",
    "CLAIM_STATUS_STALE",
    "EVIDENCE_CLASSIFICATION_FAILED",
    "EVIDENCE_CLASSIFICATION_INTERNAL_PATH",
    "EVIDENCE_CLASSIFICATION_PASSED",
    "EVIDENCE_CLASSIFICATION_PROGRESS_ONLY",
    "EVIDENCE_CLASSIFICATION_SKIPPED",
    "EVIDENCE_CLASSIFICATION_STALE",
    "EVIDENCE_CLASSIFICATION_UNKNOWN",
    "EvidenceAdapterConformancePlan",
    "EvidenceAdapterConformanceReport",
    "EvidenceAdapterFinding",
    "EvidenceAdapterMapping",
    "FALSE_NEGATIVE_CAUSES",
    "FALSE_NEGATIVE_CAUSE_ADAPTER_MAPPING_LOSS",
    "FALSE_NEGATIVE_CAUSE_CLAIM_SCOPE_OVERPROMOTION",
    "FALSE_NEGATIVE_CAUSE_INVARIANT_TOO_WEAK",
    "FALSE_NEGATIVE_CAUSE_MODEL_INPUT_MISSING",
    "FALSE_NEGATIVE_CAUSE_OMITTED_INPUT",
    "FALSE_NEGATIVE_CAUSE_ORACLE_GAP",
    "FALSE_NEGATIVE_CAUSE_ORACLE_TOO_PERMISSIVE",
    "FALSE_NEGATIVE_CAUSE_SCOPE_OVERCLAIM",
    "FALSE_NEGATIVE_CAUSE_STALE_EVIDENCE",
    "FALSE_NEGATIVE_CAUSE_STALE_EVIDENCE_ACCEPTED",
    "FALSE_NEGATIVE_CAUSE_WEAK_INVARIANT",
    "FALSE_NEGATIVE_DECISION_BLOCKED",
    "FALSE_NEGATIVE_DECISION_FULL",
    "FALSE_NEGATIVE_DECISION_SCOPED",
    "FalseNegativeBackpropagationPlan",
    "FalseNegativeBackpropagationReport",
    "FalseNegativeCase",
    "FalseNegativeFinding",
    "FlowGuardClaim",
    "FlowGuardClaimChainFinding",
    "FlowGuardClaimChainPlan",
    "FlowGuardClaimChainReport",
    "FlowGuardClaimDependency",
    "INTAKE_SOURCE_KIND_CODE",
    "INTAKE_SOURCE_KIND_HISTORY",
    "INTAKE_SOURCE_KIND_LOG",
    "INTAKE_SOURCE_KIND_MANUAL",
    "INTAKE_SOURCE_KIND_RUNTIME",
    "INTAKE_SOURCE_KIND_TEST",
    "MUTATION_EXPECTED_FAIL",
    "MUTATION_EXPECTED_PASS",
    "MUTATION_RESULT_BLOCKED",
    "MUTATION_RESULT_FAILED",
    "MUTATION_RESULT_NOT_OK",
    "MUTATION_RESULT_NOT_RUN",
    "MUTATION_RESULT_PASSED",
    "MUTATION_RESULT_STALE",
    "NON_PASSING_CLAIM_STATUSES",
    "PASSING_CLAIM_STATUSES",
    "PLAN_INTAKE_CONFIDENCE_BLOCKED",
    "PLAN_INTAKE_CONFIDENCE_FULL",
    "PLAN_INTAKE_CONFIDENCE_SCOPED",
    "PLAN_INTAKE_DECISION_BLOCKED",
    "PLAN_INTAKE_DECISION_FULL",
    "PLAN_INTAKE_DECISION_SCOPED",
    "PLAN_MUTATION_DECISION_BLOCKED",
    "PLAN_MUTATION_DECISION_FULL",
    "PLAN_MUTATION_DECISION_SCOPED",
    "PLAN_SURFACE_KIND_CODE",
    "PLAN_SURFACE_KIND_HISTORY",
    "PLAN_SURFACE_KIND_LOG",
    "PLAN_SURFACE_KIND_MANUAL",
    "PLAN_SURFACE_KIND_RUNTIME",
    "PLAN_SURFACE_KIND_TEST",
    "PLAN_SURFACE_KIND_USER_RISK",
    "PlanIntakeCompletenessPlan",
    "PlanIntakeCompletenessReport",
    "PlanIntakeFinding",
    "PlanIntakeRiskSurface",
    "PlanMutationCase",
    "PlanMutationFinding",
    "PlanMutationReviewPlan",
    "PlanMutationReviewReport",
    "PlanSourceEvidence",
    "review_evidence_adapter_conformance",
    "review_false_negative_backpropagation",
    "review_flowguard_claim_chain",
    "review_plan_intake_completeness",
    "review_plan_mutations",
]
