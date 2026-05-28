"""Obligation-family parity and provenance gates.

This helper keeps same-class routes from overclaiming broad confidence when
only one sibling member has evidence, or when the evidence proves only a
post-event state instead of the mechanism that produced it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable
from .proof_artifact import ProofArtifactRef, coerce_proof_artifact_ref, proof_artifact_gap_codes


FAMILY_EVIDENCE_STATUS_PASSED = "passed"
FAMILY_EVIDENCE_STATUS_FAILED = "failed"
FAMILY_EVIDENCE_STATUS_SKIPPED = "skipped"
FAMILY_EVIDENCE_STATUS_STALE = "stale"
FAMILY_EVIDENCE_STATUS_NOT_RUN = "not_run"
FAMILY_EVIDENCE_STATUS_RUNNING = "running"
FAMILY_EVIDENCE_STATUS_PROGRESS_ONLY = "progress_only"
FAMILY_EVIDENCE_STATUS_ERROR = "error"

PASSING_FAMILY_EVIDENCE_STATUSES = {FAMILY_EVIDENCE_STATUS_PASSED}
NON_PASSING_FAMILY_EVIDENCE_STATUSES = {
    FAMILY_EVIDENCE_STATUS_FAILED,
    FAMILY_EVIDENCE_STATUS_SKIPPED,
    FAMILY_EVIDENCE_STATUS_STALE,
    FAMILY_EVIDENCE_STATUS_NOT_RUN,
    FAMILY_EVIDENCE_STATUS_RUNNING,
    FAMILY_EVIDENCE_STATUS_PROGRESS_ONLY,
    FAMILY_EVIDENCE_STATUS_ERROR,
}

FAMILY_EVIDENCE_SCOPE_EXTERNAL_CONTRACT = "external_contract"
FAMILY_EVIDENCE_SCOPE_INTERNAL_PATH = "internal_path"
FAMILY_EVIDENCE_SCOPE_MIXED = "mixed"
FAMILY_EVIDENCE_SCOPE_UNKNOWN = "unknown"

FAMILY_EVIDENCE_PROVENANCE_UNSPECIFIED = ""
FAMILY_EVIDENCE_PROVENANCE_DURABLE_RECONCILIATION = "durable_reconciliation"
FAMILY_EVIDENCE_PROVENANCE_CONTROLLER_RECEIPT_FOLDED = "controller_receipt_folded"
FAMILY_EVIDENCE_PROVENANCE_RUNTIME_OBSERVED = "runtime_observed"
FAMILY_EVIDENCE_PROVENANCE_MANUAL_EVENT = "manual_event"
FAMILY_EVIDENCE_PROVENANCE_TEST_INJECTED = "test_injected"
FAMILY_EVIDENCE_PROVENANCE_DERIVED_FROM_CACHE = "derived_from_cache"

FAMILY_CONFIDENCE_FULL = "full"
FAMILY_CONFIDENCE_SCOPED = "scoped"
FAMILY_CONFIDENCE_BLOCKED = "blocked"

FAMILY_PARITY_DECISION_FULL = "obligation_family_parity_full_confidence"
FAMILY_PARITY_DECISION_SCOPED = "obligation_family_parity_scoped_confidence"
FAMILY_PARITY_DECISION_BLOCKED = "obligation_family_parity_blocked"

ANALOGOUS_SCAN_RADIUS_MUST_SCAN = "must_scan"
ANALOGOUS_SCAN_RADIUS_SHOULD_SCAN = "should_scan"
ANALOGOUS_SCAN_RADIUS_RECORD_ONLY = "record_only"
ANALOGOUS_SCAN_RADII = (
    ANALOGOUS_SCAN_RADIUS_MUST_SCAN,
    ANALOGOUS_SCAN_RADIUS_SHOULD_SCAN,
    ANALOGOUS_SCAN_RADIUS_RECORD_ONLY,
)

ANALOGOUS_DISPOSITION_UNREVIEWED = "unreviewed"
ANALOGOUS_DISPOSITION_COVERED_CURRENT = "covered_current"
ANALOGOUS_DISPOSITION_NEEDS_REPAIR_NOW = "needs_repair_now"
ANALOGOUS_DISPOSITION_NEEDS_MODEL_UPGRADE = "needs_model_upgrade"
ANALOGOUS_DISPOSITION_SEPARATE_CHANGE = "separate_change"
ANALOGOUS_DISPOSITION_EXCLUDED_WITH_REASON = "excluded_with_reason"
ANALOGOUS_SCAN_DISPOSITIONS = (
    ANALOGOUS_DISPOSITION_UNREVIEWED,
    ANALOGOUS_DISPOSITION_COVERED_CURRENT,
    ANALOGOUS_DISPOSITION_NEEDS_REPAIR_NOW,
    ANALOGOUS_DISPOSITION_NEEDS_MODEL_UPGRADE,
    ANALOGOUS_DISPOSITION_SEPARATE_CHANGE,
    ANALOGOUS_DISPOSITION_EXCLUDED_WITH_REASON,
)

ANALOGOUS_SCAN_DECISION_COMPLETE = "analogous_defect_scan_complete"
ANALOGOUS_SCAN_DECISION_SCOPED = "analogous_defect_scan_scoped"
ANALOGOUS_SCAN_DECISION_BLOCKED = "analogous_defect_scan_blocked"

COVERAGE_CELL_COVERED = "covered"
COVERAGE_CELL_MISSING = "missing"
COVERAGE_CELL_INVALID_PROVENANCE = "invalid_provenance"
COVERAGE_CELL_NOT_CURRENT = "not_current"
COVERAGE_CELL_NON_PASSING = "non_passing"
COVERAGE_CELL_EXEMPT = "exempt"


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


@dataclass(frozen=True)
class ObligationFamilyMember:
    """One sibling member in a same-class obligation family."""

    member_id: str
    description: str = ""
    obligation_ids: tuple[str, ...] = ()
    required: bool = True
    exception_reason: str = ""
    required_mechanisms: tuple[str, ...] = ()
    allowed_provenance: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "member_id", str(self.member_id))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "obligation_ids", _as_tuple(self.obligation_ids))
        object.__setattr__(self, "exception_reason", str(self.exception_reason))
        object.__setattr__(self, "required_mechanisms", _as_tuple(self.required_mechanisms))
        object.__setattr__(self, "allowed_provenance", _as_tuple(self.allowed_provenance))

    def to_dict(self) -> dict[str, Any]:
        return {
            "member_id": self.member_id,
            "description": self.description,
            "obligation_ids": list(self.obligation_ids),
            "required": self.required,
            "exception_reason": self.exception_reason,
            "required_mechanisms": list(self.required_mechanisms),
            "allowed_provenance": list(self.allowed_provenance),
        }


@dataclass(frozen=True)
class ObligationFamily:
    """A same-class family whose members should share declared mechanisms."""

    family_id: str
    description: str = ""
    members: tuple[ObligationFamilyMember, ...] = ()
    required_mechanisms: tuple[str, ...] = ()
    allowed_provenance: tuple[str, ...] = ()
    required: bool = True
    require_external_evidence: bool = True
    require_proof_artifacts: bool = False
    allow_scoped_confidence: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "family_id", str(self.family_id))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "members", tuple(self.members))
        object.__setattr__(self, "required_mechanisms", _as_tuple(self.required_mechanisms))
        object.__setattr__(self, "allowed_provenance", _as_tuple(self.allowed_provenance))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def mechanisms_for(self, member: ObligationFamilyMember) -> tuple[str, ...]:
        return member.required_mechanisms or self.required_mechanisms

    def provenance_for(self, member: ObligationFamilyMember) -> tuple[str, ...]:
        return member.allowed_provenance or self.allowed_provenance

    def to_dict(self) -> dict[str, Any]:
        return {
            "family_id": self.family_id,
            "description": self.description,
            "members": [member.to_dict() for member in self.members],
            "required_mechanisms": list(self.required_mechanisms),
            "allowed_provenance": list(self.allowed_provenance),
            "required": self.required,
            "require_external_evidence": self.require_external_evidence,
            "require_proof_artifacts": self.require_proof_artifacts,
            "allow_scoped_confidence": self.allow_scoped_confidence,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ObligationFamilyEvidence:
    """Proof for one family member and one shared mechanism."""

    evidence_id: str
    family_id: str
    member_id: str
    mechanism_id: str
    provenance: str = FAMILY_EVIDENCE_PROVENANCE_UNSPECIFIED
    result_status: str = FAMILY_EVIDENCE_STATUS_NOT_RUN
    current: bool = True
    assertion_scope: str = FAMILY_EVIDENCE_SCOPE_EXTERNAL_CONTRACT
    covered_obligations: tuple[str, ...] = ()
    command: str = ""
    summary: str = ""
    proof_artifact: ProofArtifactRef | Mapping[str, Any] | None = None
    stale_reasons: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "family_id", str(self.family_id))
        object.__setattr__(self, "member_id", str(self.member_id))
        object.__setattr__(self, "mechanism_id", str(self.mechanism_id))
        object.__setattr__(self, "provenance", str(self.provenance))
        object.__setattr__(self, "result_status", str(self.result_status))
        object.__setattr__(self, "assertion_scope", str(self.assertion_scope))
        object.__setattr__(self, "covered_obligations", _as_tuple(self.covered_obligations))
        object.__setattr__(self, "command", str(self.command))
        object.__setattr__(self, "summary", str(self.summary))
        object.__setattr__(self, "proof_artifact", coerce_proof_artifact_ref(self.proof_artifact))
        object.__setattr__(self, "stale_reasons", _as_tuple(self.stale_reasons))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def has_current_pass(self) -> bool:
        return self.result_status in PASSING_FAMILY_EVIDENCE_STATUSES and self.current

    def has_external_scope(self) -> bool:
        return self.assertion_scope in {
            FAMILY_EVIDENCE_SCOPE_EXTERNAL_CONTRACT,
            FAMILY_EVIDENCE_SCOPE_MIXED,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "family_id": self.family_id,
            "member_id": self.member_id,
            "mechanism_id": self.mechanism_id,
            "provenance": self.provenance,
            "result_status": self.result_status,
            "current": self.current,
            "assertion_scope": self.assertion_scope,
            "covered_obligations": list(self.covered_obligations),
            "command": self.command,
            "summary": self.summary,
            "proof_artifact": self.proof_artifact.to_dict() if self.proof_artifact else None,
            "stale_reasons": list(self.stale_reasons),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class FamilyBadCaseSeed:
    """Observed same-class miss seed used to derive sibling bad cases."""

    seed_id: str
    family_id: str
    source_member_id: str
    mechanism_id: str
    failure_mode: str
    description: str = ""
    source_case_id: str = ""
    exclude_member_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "seed_id", str(self.seed_id))
        object.__setattr__(self, "family_id", str(self.family_id))
        object.__setattr__(self, "source_member_id", str(self.source_member_id))
        object.__setattr__(self, "mechanism_id", str(self.mechanism_id))
        object.__setattr__(self, "failure_mode", str(self.failure_mode))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "source_case_id", str(self.source_case_id))
        object.__setattr__(self, "exclude_member_ids", _as_tuple(self.exclude_member_ids))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed_id": self.seed_id,
            "family_id": self.family_id,
            "source_member_id": self.source_member_id,
            "mechanism_id": self.mechanism_id,
            "failure_mode": self.failure_mode,
            "description": self.description,
            "source_case_id": self.source_case_id,
            "exclude_member_ids": list(self.exclude_member_ids),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class DerivedFamilyBadCase:
    """A generated same-class bad case for one sibling member."""

    case_id: str
    family_id: str
    member_id: str
    mechanism_id: str
    failure_mode: str
    source_member_id: str = ""
    source_case_id: str = ""
    description: str = ""
    expected_status: str = "must_fail_before_repair"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", str(self.case_id))
        object.__setattr__(self, "family_id", str(self.family_id))
        object.__setattr__(self, "member_id", str(self.member_id))
        object.__setattr__(self, "mechanism_id", str(self.mechanism_id))
        object.__setattr__(self, "failure_mode", str(self.failure_mode))
        object.__setattr__(self, "source_member_id", str(self.source_member_id))
        object.__setattr__(self, "source_case_id", str(self.source_case_id))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "expected_status", str(self.expected_status))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "family_id": self.family_id,
            "member_id": self.member_id,
            "mechanism_id": self.mechanism_id,
            "failure_mode": self.failure_mode,
            "source_member_id": self.source_member_id,
            "source_case_id": self.source_case_id,
            "description": self.description,
            "expected_status": self.expected_status,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class AnalogousDefectCandidate:
    """One possible same-shape defect location discovered after an observed miss."""

    candidate_id: str
    family_id: str
    member_id: str
    mechanism_id: str
    failure_mode: str = ""
    radius: str = ANALOGOUS_SCAN_RADIUS_MUST_SCAN
    description: str = ""
    disposition: str = ANALOGOUS_DISPOSITION_UNREVIEWED
    disposition_reason: str = ""
    evidence_ids: tuple[str, ...] = ()
    source: str = "family_member"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", str(self.candidate_id))
        object.__setattr__(self, "family_id", str(self.family_id))
        object.__setattr__(self, "member_id", str(self.member_id))
        object.__setattr__(self, "mechanism_id", str(self.mechanism_id))
        object.__setattr__(self, "failure_mode", str(self.failure_mode))
        object.__setattr__(self, "radius", str(self.radius))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "disposition", str(self.disposition))
        object.__setattr__(self, "disposition_reason", str(self.disposition_reason))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))
        object.__setattr__(self, "source", str(self.source))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "family_id": self.family_id,
            "member_id": self.member_id,
            "mechanism_id": self.mechanism_id,
            "failure_mode": self.failure_mode,
            "radius": self.radius,
            "description": self.description,
            "disposition": self.disposition,
            "disposition_reason": self.disposition_reason,
            "evidence_ids": list(self.evidence_ids),
            "source": self.source,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class AnalogousDefectScanFinding:
    """One gap found while scanning same-shape defect candidates."""

    code: str
    message: str
    severity: str = "blocker"
    candidate_id: str = ""
    family_id: str = ""
    member_id: str = ""
    mechanism_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "candidate_id", str(self.candidate_id))
        object.__setattr__(self, "family_id", str(self.family_id))
        object.__setattr__(self, "member_id", str(self.member_id))
        object.__setattr__(self, "mechanism_id", str(self.mechanism_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "candidate_id": self.candidate_id,
            "family_id": self.family_id,
            "member_id": self.member_id,
            "mechanism_id": self.mechanism_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class AnalogousDefectScanReport:
    """Review result for same-shape defect radius scanning."""

    ok: bool
    decision: str
    confidence: str
    seed: FamilyBadCaseSeed | None = None
    candidates: tuple[AnalogousDefectCandidate, ...] = ()
    findings: tuple[AnalogousDefectScanFinding, ...] = ()
    derived_bad_cases: tuple[DerivedFamilyBadCase, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "derived_bad_cases", tuple(self.derived_bad_cases))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: decision={self.decision} findings={len(self.findings)} candidates={len(self.candidates)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard analogous defect scan ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"decision: {self.decision}",
            f"confidence: {self.confidence}",
            f"candidates: {len(self.candidates)}",
            f"findings: {len(self.findings)}",
            f"derived_bad_cases: {len(self.derived_bad_cases)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"candidate: {finding.candidate_id}",
                    f"family: {finding.family_id}",
                    f"member: {finding.member_id}",
                    f"mechanism: {finding.mechanism_id}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "decision": self.decision,
            "confidence": self.confidence,
            "seed": self.seed.to_dict() if self.seed else None,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "findings": [finding.to_dict() for finding in self.findings],
            "derived_bad_cases": [case.to_dict() for case in self.derived_bad_cases],
            "summary": self.summary,
        }


@dataclass(frozen=True)
class ObligationFamilyCoverageCell:
    """One member x mechanism cell in the family coverage matrix."""

    family_id: str
    member_id: str
    mechanism_id: str
    status: str
    evidence_ids: tuple[str, ...] = ()
    accepted_provenance: tuple[str, ...] = ()
    scoped_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "family_id", str(self.family_id))
        object.__setattr__(self, "member_id", str(self.member_id))
        object.__setattr__(self, "mechanism_id", str(self.mechanism_id))
        object.__setattr__(self, "status", str(self.status))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))
        object.__setattr__(self, "accepted_provenance", _as_tuple(self.accepted_provenance))
        object.__setattr__(self, "scoped_reasons", _as_tuple(self.scoped_reasons))

    def to_dict(self) -> dict[str, Any]:
        return {
            "family_id": self.family_id,
            "member_id": self.member_id,
            "mechanism_id": self.mechanism_id,
            "status": self.status,
            "evidence_ids": list(self.evidence_ids),
            "accepted_provenance": list(self.accepted_provenance),
            "scoped_reasons": list(self.scoped_reasons),
        }


@dataclass(frozen=True)
class ObligationFamilyParityFinding:
    """One family parity, provenance, or claim-scope finding."""

    code: str
    message: str
    severity: str = "blocker"
    family_id: str = ""
    member_id: str = ""
    mechanism_id: str = ""
    evidence_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "family_id", str(self.family_id))
        object.__setattr__(self, "member_id", str(self.member_id))
        object.__setattr__(self, "mechanism_id", str(self.mechanism_id))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "family_id": self.family_id,
            "member_id": self.member_id,
            "mechanism_id": self.mechanism_id,
            "evidence_id": self.evidence_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ObligationFamilyParityReport:
    """Structured family parity review result."""

    ok: bool
    decision: str
    confidence: str
    findings: tuple[ObligationFamilyParityFinding, ...] = ()
    coverage_matrix: tuple[ObligationFamilyCoverageCell, ...] = ()
    derived_bad_cases: tuple[DerivedFamilyBadCase, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "coverage_matrix", tuple(self.coverage_matrix))
        object.__setattr__(self, "derived_bad_cases", tuple(self.derived_bad_cases))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: decision={self.decision} findings={len(self.findings)} cells={len(self.coverage_matrix)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard obligation family parity ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"decision: {self.decision}",
            f"confidence: {self.confidence}",
            f"findings: {len(self.findings)}",
            f"coverage_cells: {len(self.coverage_matrix)}",
            f"derived_bad_cases: {len(self.derived_bad_cases)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"family: {finding.family_id}",
                    f"member: {finding.member_id}",
                    f"mechanism: {finding.mechanism_id}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "decision": self.decision,
            "confidence": self.confidence,
            "findings": [finding.to_dict() for finding in self.findings],
            "coverage_matrix": [cell.to_dict() for cell in self.coverage_matrix],
            "derived_bad_cases": [case.to_dict() for case in self.derived_bad_cases],
            "summary": self.summary,
        }


def _finding(
    code: str,
    message: str,
    *,
    severity: str = "blocker",
    family_id: str = "",
    member_id: str = "",
    mechanism_id: str = "",
    evidence_id: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> ObligationFamilyParityFinding:
    return ObligationFamilyParityFinding(
        code=code,
        message=message,
        severity=severity,
        family_id=family_id,
        member_id=member_id,
        mechanism_id=mechanism_id,
        evidence_id=evidence_id,
        metadata=metadata or {},
    )


def derive_same_class_bad_cases(
    family: ObligationFamily,
    seed: FamilyBadCaseSeed,
) -> tuple[DerivedFamilyBadCase, ...]:
    """Derive sibling same-class bad cases from one observed family miss."""

    excluded = {seed.source_member_id, *seed.exclude_member_ids}
    cases: list[DerivedFamilyBadCase] = []
    for member in family.members:
        if not member.required or member.member_id in excluded:
            continue
        if seed.mechanism_id and seed.mechanism_id not in family.mechanisms_for(member):
            continue
        case_id = f"{seed.seed_id}:{member.member_id}:{seed.mechanism_id}"
        description = seed.description or (
            f"{member.member_id} has same-class failure {seed.failure_mode} "
            f"for mechanism {seed.mechanism_id}"
        )
        cases.append(
            DerivedFamilyBadCase(
                case_id=case_id,
                family_id=family.family_id,
                member_id=member.member_id,
                mechanism_id=seed.mechanism_id,
                failure_mode=seed.failure_mode,
                source_member_id=seed.source_member_id,
                source_case_id=seed.source_case_id,
                description=description,
                metadata={"seed_id": seed.seed_id, **dict(seed.metadata)},
            )
        )
    return tuple(cases)


def _scan_finding(
    code: str,
    message: str,
    *,
    severity: str = "blocker",
    candidate_id: str = "",
    family_id: str = "",
    member_id: str = "",
    mechanism_id: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> AnalogousDefectScanFinding:
    return AnalogousDefectScanFinding(
        code=code,
        message=message,
        severity=severity,
        candidate_id=candidate_id,
        family_id=family_id,
        member_id=member_id,
        mechanism_id=mechanism_id,
        metadata=metadata or {},
    )


def _scan_severity(radius: str) -> str:
    if radius == ANALOGOUS_SCAN_RADIUS_MUST_SCAN:
        return "blocker"
    if radius == ANALOGOUS_SCAN_RADIUS_SHOULD_SCAN:
        return "warning"
    return "info"


def _analogous_candidate_from_case(case: DerivedFamilyBadCase) -> AnalogousDefectCandidate:
    return AnalogousDefectCandidate(
        candidate_id=f"{case.case_id}:scan",
        family_id=case.family_id,
        member_id=case.member_id,
        mechanism_id=case.mechanism_id,
        failure_mode=case.failure_mode,
        radius=ANALOGOUS_SCAN_RADIUS_MUST_SCAN,
        description=case.description,
        source="derived_same_class_bad_case",
        metadata={"source_case_id": case.source_case_id, **dict(case.metadata)},
    )


def _scan_decision_for(findings: Sequence[AnalogousDefectScanFinding]) -> tuple[str, str, bool]:
    blockers = tuple(finding for finding in findings if finding.severity == "blocker")
    if blockers:
        return ANALOGOUS_SCAN_DECISION_BLOCKED, FAMILY_CONFIDENCE_BLOCKED, False
    if findings:
        return ANALOGOUS_SCAN_DECISION_SCOPED, FAMILY_CONFIDENCE_SCOPED, True
    return ANALOGOUS_SCAN_DECISION_COMPLETE, FAMILY_CONFIDENCE_FULL, True


def review_analogous_defect_scan(
    families: Sequence[ObligationFamily],
    seed: FamilyBadCaseSeed,
    candidates: Sequence[AnalogousDefectCandidate] = (),
) -> AnalogousDefectScanReport:
    """Scan where an observed same-shape model miss may recur.

    The helper turns the seed into mandatory sibling candidates and lets callers
    add wider-radius candidates for related surfaces. Full confidence requires
    each must-scan candidate to be covered, explicitly excluded with a reason,
    or assigned to a separate change with a reason.
    """

    family_by_id, family_findings = _index_families(families)
    findings: list[AnalogousDefectScanFinding] = [
        _scan_finding(
            finding.code,
            finding.message,
            severity=finding.severity,
            family_id=finding.family_id,
            member_id=finding.member_id,
            mechanism_id=finding.mechanism_id,
            metadata={"family_finding": finding.to_dict()},
        )
        for finding in family_findings
    ]
    family = family_by_id.get(seed.family_id)
    if family is None:
        findings.append(
            _scan_finding(
                "unknown_analogous_scan_seed_family",
                "analogous defect scan seed references an unknown family",
                family_id=seed.family_id,
                member_id=seed.source_member_id,
                mechanism_id=seed.mechanism_id,
            )
        )
        decision, confidence, ok = _scan_decision_for(findings)
        return AnalogousDefectScanReport(
            ok=ok,
            decision=decision,
            confidence=confidence,
            seed=seed,
            candidates=tuple(candidates),
            findings=tuple(findings),
        )

    derived_cases = derive_same_class_bad_cases(family, seed)
    auto_candidates = tuple(_analogous_candidate_from_case(case) for case in derived_cases)
    all_candidates = auto_candidates + tuple(candidates)
    indexed_candidates: dict[str, AnalogousDefectCandidate] = {}
    for candidate in all_candidates:
        if not candidate.candidate_id:
            findings.append(
                _scan_finding(
                    "missing_analogous_scan_candidate_id",
                    "analogous defect scan candidate has no id",
                    severity=_scan_severity(candidate.radius),
                    family_id=candidate.family_id,
                    member_id=candidate.member_id,
                    mechanism_id=candidate.mechanism_id,
                )
            )
            continue
        if candidate.candidate_id in indexed_candidates:
            existing = indexed_candidates[candidate.candidate_id]
            if (
                existing.source == "derived_same_class_bad_case"
                and candidate.source != "derived_same_class_bad_case"
            ):
                indexed_candidates[candidate.candidate_id] = candidate
                continue
            findings.append(
                _scan_finding(
                    "duplicate_analogous_scan_candidate_id",
                    "analogous defect scan candidate id is duplicated",
                    candidate_id=candidate.candidate_id,
                    severity=_scan_severity(candidate.radius),
                    family_id=candidate.family_id,
                    member_id=candidate.member_id,
                    mechanism_id=candidate.mechanism_id,
                )
            )
            continue
        indexed_candidates[candidate.candidate_id] = candidate

    for candidate in indexed_candidates.values():
        severity = _scan_severity(candidate.radius)
        if candidate.radius not in ANALOGOUS_SCAN_RADII:
            findings.append(
                _scan_finding(
                    "invalid_analogous_scan_radius",
                    "analogous defect scan candidate has an unknown scan radius",
                    candidate_id=candidate.candidate_id,
                    severity="blocker",
                    family_id=candidate.family_id,
                    member_id=candidate.member_id,
                    mechanism_id=candidate.mechanism_id,
                    metadata={"radius": candidate.radius},
                )
            )
        if candidate.disposition not in ANALOGOUS_SCAN_DISPOSITIONS:
            findings.append(
                _scan_finding(
                    "invalid_analogous_scan_disposition",
                    "analogous defect scan candidate has an unknown disposition",
                    candidate_id=candidate.candidate_id,
                    severity=severity,
                    family_id=candidate.family_id,
                    member_id=candidate.member_id,
                    mechanism_id=candidate.mechanism_id,
                    metadata={"disposition": candidate.disposition},
                )
            )
            continue
        if candidate.disposition == ANALOGOUS_DISPOSITION_UNREVIEWED:
            findings.append(
                _scan_finding(
                    "unreviewed_analogous_defect_candidate",
                    "analogous defect candidate has not been reviewed or dispositioned",
                    candidate_id=candidate.candidate_id,
                    severity=severity,
                    family_id=candidate.family_id,
                    member_id=candidate.member_id,
                    mechanism_id=candidate.mechanism_id,
                )
            )
        elif candidate.disposition == ANALOGOUS_DISPOSITION_COVERED_CURRENT:
            if not candidate.evidence_ids:
                findings.append(
                    _scan_finding(
                        "analogous_scan_coverage_without_evidence",
                        "candidate is marked covered but no current evidence id is attached",
                        candidate_id=candidate.candidate_id,
                        severity=severity,
                        family_id=candidate.family_id,
                        member_id=candidate.member_id,
                        mechanism_id=candidate.mechanism_id,
                    )
                )
        elif candidate.disposition in {
            ANALOGOUS_DISPOSITION_SEPARATE_CHANGE,
            ANALOGOUS_DISPOSITION_EXCLUDED_WITH_REASON,
        }:
            if not candidate.disposition_reason:
                findings.append(
                    _scan_finding(
                        "analogous_scan_disposition_reason_missing",
                        "candidate disposition requires a concrete reason",
                        candidate_id=candidate.candidate_id,
                        severity=severity,
                        family_id=candidate.family_id,
                        member_id=candidate.member_id,
                        mechanism_id=candidate.mechanism_id,
                        metadata={"disposition": candidate.disposition},
                    )
                )
            elif candidate.disposition == ANALOGOUS_DISPOSITION_SEPARATE_CHANGE:
                findings.append(
                    _scan_finding(
                        "analogous_scan_candidate_scoped_to_separate_change",
                        "candidate is dispositioned to a separate change, so the current closure is scoped",
                        candidate_id=candidate.candidate_id,
                        severity="warning",
                        family_id=candidate.family_id,
                        member_id=candidate.member_id,
                        mechanism_id=candidate.mechanism_id,
                        metadata={"disposition": candidate.disposition},
                    )
                )
            elif candidate.radius != ANALOGOUS_SCAN_RADIUS_MUST_SCAN:
                findings.append(
                    _scan_finding(
                        "analogous_scan_candidate_excluded_from_wider_radius",
                        "wider-radius candidate is excluded with a reason, so the scope remains visible",
                        candidate_id=candidate.candidate_id,
                        severity=_scan_severity(candidate.radius),
                        family_id=candidate.family_id,
                        member_id=candidate.member_id,
                        mechanism_id=candidate.mechanism_id,
                        metadata={"disposition": candidate.disposition},
                    )
                )
        elif candidate.disposition in {
            ANALOGOUS_DISPOSITION_NEEDS_REPAIR_NOW,
            ANALOGOUS_DISPOSITION_NEEDS_MODEL_UPGRADE,
        }:
            findings.append(
                _scan_finding(
                    "analogous_defect_candidate_open_action",
                    "candidate still requires repair or model upgrade before broad closure",
                    candidate_id=candidate.candidate_id,
                    severity=severity,
                    family_id=candidate.family_id,
                    member_id=candidate.member_id,
                    mechanism_id=candidate.mechanism_id,
                    metadata={"disposition": candidate.disposition},
                )
            )

    decision, confidence, ok = _scan_decision_for(findings)
    return AnalogousDefectScanReport(
        ok=ok,
        decision=decision,
        confidence=confidence,
        seed=seed,
        candidates=tuple(indexed_candidates.values()),
        findings=tuple(findings),
        derived_bad_cases=derived_cases,
    )


def _decision_for(findings: Sequence[ObligationFamilyParityFinding]) -> tuple[str, str, bool]:
    blockers = tuple(finding for finding in findings if finding.severity == "blocker")
    if blockers:
        return FAMILY_PARITY_DECISION_BLOCKED, FAMILY_CONFIDENCE_BLOCKED, False
    if findings:
        return FAMILY_PARITY_DECISION_SCOPED, FAMILY_CONFIDENCE_SCOPED, True
    return FAMILY_PARITY_DECISION_FULL, FAMILY_CONFIDENCE_FULL, True


def _index_families(
    families: Sequence[ObligationFamily],
) -> tuple[dict[str, ObligationFamily], list[ObligationFamilyParityFinding]]:
    indexed: dict[str, ObligationFamily] = {}
    findings: list[ObligationFamilyParityFinding] = []
    for family in families:
        if not family.family_id:
            findings.append(_finding("missing_family_id", "obligation family has no id"))
            continue
        if family.family_id in indexed:
            findings.append(
                _finding(
                    "duplicate_family_id",
                    "obligation family id is duplicated",
                    family_id=family.family_id,
                )
            )
            continue
        indexed[family.family_id] = family
    return indexed, findings


def _member_index(
    family: ObligationFamily,
) -> tuple[dict[str, ObligationFamilyMember], list[ObligationFamilyParityFinding]]:
    indexed: dict[str, ObligationFamilyMember] = {}
    findings: list[ObligationFamilyParityFinding] = []
    if not family.members and family.required:
        findings.append(
            _finding(
                "missing_family_members",
                "required obligation family has no members",
                family_id=family.family_id,
            )
        )
    for member in family.members:
        if not member.member_id:
            findings.append(
                _finding(
                    "missing_family_member_id",
                    "obligation family member has no id",
                    family_id=family.family_id,
                )
            )
            continue
        if member.member_id in indexed:
            findings.append(
                _finding(
                    "duplicate_family_member_id",
                    "obligation family member id is duplicated",
                    family_id=family.family_id,
                    member_id=member.member_id,
                )
            )
            continue
        indexed[member.member_id] = member
    return indexed, findings


def _evidence_index(
    evidence: Sequence[ObligationFamilyEvidence],
) -> tuple[dict[str, ObligationFamilyEvidence], list[ObligationFamilyParityFinding]]:
    indexed: dict[str, ObligationFamilyEvidence] = {}
    findings: list[ObligationFamilyParityFinding] = []
    for item in evidence:
        if not item.evidence_id:
            findings.append(
                _finding(
                    "missing_family_evidence_id",
                    "obligation family evidence has no id",
                    family_id=item.family_id,
                    member_id=item.member_id,
                    mechanism_id=item.mechanism_id,
                )
            )
            continue
        if item.evidence_id in indexed:
            findings.append(
                _finding(
                    "duplicate_family_evidence_id",
                    "obligation family evidence id is duplicated",
                    family_id=item.family_id,
                    member_id=item.member_id,
                    mechanism_id=item.mechanism_id,
                    evidence_id=item.evidence_id,
                )
            )
            continue
        indexed[item.evidence_id] = item
    return indexed, findings


def _cell_for(
    *,
    family: ObligationFamily,
    member: ObligationFamilyMember,
    mechanism_id: str,
    matching_evidence: Sequence[ObligationFamilyEvidence],
    allowed_provenance: tuple[str, ...],
    findings: list[ObligationFamilyParityFinding],
) -> ObligationFamilyCoverageCell:
    accepted: list[ObligationFamilyEvidence] = []
    wrong_provenance: list[ObligationFamilyEvidence] = []
    not_current: list[ObligationFamilyEvidence] = []
    non_passing: list[ObligationFamilyEvidence] = []
    internal_only: list[ObligationFamilyEvidence] = []

    for item in matching_evidence:
        if item.result_status not in PASSING_FAMILY_EVIDENCE_STATUSES:
            non_passing.append(item)
            continue
        if not item.current:
            not_current.append(item)
            continue
        if family.require_external_evidence and not item.has_external_scope():
            internal_only.append(item)
            continue
        if allowed_provenance and item.provenance not in allowed_provenance:
            wrong_provenance.append(item)
            continue
        gaps = proof_artifact_gap_codes(item.proof_artifact) if family.require_proof_artifacts else ()
        if gaps:
            findings.append(
                _finding(
                    "family_evidence_proof_artifact_gap",
                    "family evidence proof artifact is incomplete",
                    family_id=family.family_id,
                    member_id=member.member_id,
                    mechanism_id=mechanism_id,
                    evidence_id=item.evidence_id,
                    metadata={"gap_codes": gaps},
                )
            )
            continue
        accepted.append(item)

    if accepted:
        return ObligationFamilyCoverageCell(
            family_id=family.family_id,
            member_id=member.member_id,
            mechanism_id=mechanism_id,
            status=COVERAGE_CELL_COVERED,
            evidence_ids=_unique(tuple(item.evidence_id for item in accepted)),
            accepted_provenance=_unique(tuple(item.provenance for item in accepted)),
        )

    if wrong_provenance:
        for item in wrong_provenance:
            findings.append(
                _finding(
                    "invalid_family_evidence_provenance",
                    "family evidence provenance does not prove the required mechanism",
                    family_id=family.family_id,
                    member_id=member.member_id,
                    mechanism_id=mechanism_id,
                    evidence_id=item.evidence_id,
                    metadata={
                        "actual_provenance": item.provenance,
                        "allowed_provenance": list(allowed_provenance),
                    },
                )
            )
        return ObligationFamilyCoverageCell(
            family_id=family.family_id,
            member_id=member.member_id,
            mechanism_id=mechanism_id,
            status=COVERAGE_CELL_INVALID_PROVENANCE,
            evidence_ids=_unique(tuple(item.evidence_id for item in wrong_provenance)),
            scoped_reasons=("invalid_family_evidence_provenance",),
        )

    if internal_only:
        for item in internal_only:
            findings.append(
                _finding(
                    "family_evidence_internal_path_only",
                    "family evidence is internal-path-only but external contract evidence is required",
                    family_id=family.family_id,
                    member_id=member.member_id,
                    mechanism_id=mechanism_id,
                    evidence_id=item.evidence_id,
                )
            )
        return ObligationFamilyCoverageCell(
            family_id=family.family_id,
            member_id=member.member_id,
            mechanism_id=mechanism_id,
            status=COVERAGE_CELL_INVALID_PROVENANCE,
            evidence_ids=_unique(tuple(item.evidence_id for item in internal_only)),
            scoped_reasons=("family_evidence_internal_path_only",),
        )

    if not_current:
        for item in not_current:
            findings.append(
                _finding(
                    "stale_family_evidence",
                    "family evidence is not current",
                    family_id=family.family_id,
                    member_id=member.member_id,
                    mechanism_id=mechanism_id,
                    evidence_id=item.evidence_id,
                    metadata={"stale_reasons": list(item.stale_reasons)},
                )
            )
        return ObligationFamilyCoverageCell(
            family_id=family.family_id,
            member_id=member.member_id,
            mechanism_id=mechanism_id,
            status=COVERAGE_CELL_NOT_CURRENT,
            evidence_ids=_unique(tuple(item.evidence_id for item in not_current)),
            scoped_reasons=("stale_family_evidence",),
        )

    if non_passing:
        for item in non_passing:
            findings.append(
                _finding(
                    "family_evidence_not_passing",
                    "family evidence is not a current passing proof",
                    family_id=family.family_id,
                    member_id=member.member_id,
                    mechanism_id=mechanism_id,
                    evidence_id=item.evidence_id,
                    metadata={"result_status": item.result_status},
                )
            )
        return ObligationFamilyCoverageCell(
            family_id=family.family_id,
            member_id=member.member_id,
            mechanism_id=mechanism_id,
            status=COVERAGE_CELL_NON_PASSING,
            evidence_ids=_unique(tuple(item.evidence_id for item in non_passing)),
            scoped_reasons=("family_evidence_not_passing",),
        )

    findings.append(
        _finding(
            "missing_family_member_mechanism_evidence",
            "required family member has no current passing evidence for the mechanism",
            family_id=family.family_id,
            member_id=member.member_id,
            mechanism_id=mechanism_id,
        )
    )
    return ObligationFamilyCoverageCell(
        family_id=family.family_id,
        member_id=member.member_id,
        mechanism_id=mechanism_id,
        status=COVERAGE_CELL_MISSING,
        scoped_reasons=("missing_family_member_mechanism_evidence",),
    )


def review_obligation_family_parity(
    families: Sequence[ObligationFamily],
    evidence: Sequence[ObligationFamilyEvidence] = (),
    bad_case_seeds: Sequence[FamilyBadCaseSeed] = (),
) -> ObligationFamilyParityReport:
    """Review whether same-class obligation family members are equally covered."""

    family_by_id, findings = _index_families(families)
    evidence_by_id, evidence_findings = _evidence_index(evidence)
    findings.extend(evidence_findings)
    coverage_matrix: list[ObligationFamilyCoverageCell] = []

    family_member_indexes: dict[str, dict[str, ObligationFamilyMember]] = {}
    for family in families:
        member_by_id, member_findings = _member_index(family)
        family_member_indexes[family.family_id] = member_by_id
        findings.extend(member_findings)

    for item in evidence_by_id.values():
        family = family_by_id.get(item.family_id)
        if family is None:
            findings.append(
                _finding(
                    "unknown_family_evidence",
                    "family evidence references an unknown family",
                    family_id=item.family_id,
                    member_id=item.member_id,
                    mechanism_id=item.mechanism_id,
                    evidence_id=item.evidence_id,
                )
            )
            continue
        member = family_member_indexes[family.family_id].get(item.member_id)
        if member is None:
            findings.append(
                _finding(
                    "unknown_family_member_evidence",
                    "family evidence references an unknown member",
                    family_id=item.family_id,
                    member_id=item.member_id,
                    mechanism_id=item.mechanism_id,
                    evidence_id=item.evidence_id,
                )
            )
            continue
        if item.mechanism_id not in family.mechanisms_for(member):
            findings.append(
                _finding(
                    "unknown_family_mechanism_evidence",
                    "family evidence references a mechanism outside the member contract",
                    family_id=item.family_id,
                    member_id=item.member_id,
                    mechanism_id=item.mechanism_id,
                    evidence_id=item.evidence_id,
                )
            )

    for family in families:
        for member in family.members:
            mechanisms = family.mechanisms_for(member)
            if not member.required:
                for mechanism_id in mechanisms:
                    coverage_matrix.append(
                        ObligationFamilyCoverageCell(
                            family_id=family.family_id,
                            member_id=member.member_id,
                            mechanism_id=mechanism_id,
                            status=COVERAGE_CELL_EXEMPT,
                            scoped_reasons=(member.exception_reason,) if member.exception_reason else (),
                        )
                    )
                if not member.exception_reason:
                    findings.append(
                        _finding(
                            "family_member_exception_reason_missing",
                            "non-required family member should explain its exception",
                            family_id=family.family_id,
                            member_id=member.member_id,
                            severity="warning" if family.allow_scoped_confidence else "blocker",
                        )
                    )
                continue
            if not mechanisms:
                findings.append(
                    _finding(
                        "missing_family_required_mechanism",
                        "required family member has no mechanism contract",
                        family_id=family.family_id,
                        member_id=member.member_id,
                    )
                )
                continue
            allowed_provenance = family.provenance_for(member)
            for mechanism_id in mechanisms:
                matching = tuple(
                    item
                    for item in evidence_by_id.values()
                    if item.family_id == family.family_id
                    and item.member_id == member.member_id
                    and item.mechanism_id == mechanism_id
                )
                coverage_matrix.append(
                    _cell_for(
                        family=family,
                        member=member,
                        mechanism_id=mechanism_id,
                        matching_evidence=matching,
                        allowed_provenance=allowed_provenance,
                        findings=findings,
                    )
                )

    derived_cases: list[DerivedFamilyBadCase] = []
    for seed in bad_case_seeds:
        family = family_by_id.get(seed.family_id)
        if family is None:
            findings.append(
                _finding(
                    "unknown_bad_case_seed_family",
                    "same-class bad-case seed references an unknown family",
                    family_id=seed.family_id,
                    member_id=seed.source_member_id,
                    mechanism_id=seed.mechanism_id,
                )
            )
            continue
        derived_cases.extend(derive_same_class_bad_cases(family, seed))

    decision, confidence, ok = _decision_for(findings)
    return ObligationFamilyParityReport(
        ok=ok,
        decision=decision,
        confidence=confidence,
        findings=tuple(findings),
        coverage_matrix=tuple(coverage_matrix),
        derived_bad_cases=tuple(derived_cases),
    )


__all__ = [
    "ANALOGOUS_DISPOSITION_COVERED_CURRENT",
    "ANALOGOUS_DISPOSITION_EXCLUDED_WITH_REASON",
    "ANALOGOUS_DISPOSITION_NEEDS_MODEL_UPGRADE",
    "ANALOGOUS_DISPOSITION_NEEDS_REPAIR_NOW",
    "ANALOGOUS_DISPOSITION_SEPARATE_CHANGE",
    "ANALOGOUS_DISPOSITION_UNREVIEWED",
    "ANALOGOUS_SCAN_DECISION_BLOCKED",
    "ANALOGOUS_SCAN_DECISION_COMPLETE",
    "ANALOGOUS_SCAN_DECISION_SCOPED",
    "ANALOGOUS_SCAN_DISPOSITIONS",
    "ANALOGOUS_SCAN_RADII",
    "ANALOGOUS_SCAN_RADIUS_MUST_SCAN",
    "ANALOGOUS_SCAN_RADIUS_RECORD_ONLY",
    "ANALOGOUS_SCAN_RADIUS_SHOULD_SCAN",
    "AnalogousDefectCandidate",
    "AnalogousDefectScanFinding",
    "AnalogousDefectScanReport",
    "COVERAGE_CELL_COVERED",
    "COVERAGE_CELL_EXEMPT",
    "COVERAGE_CELL_INVALID_PROVENANCE",
    "COVERAGE_CELL_MISSING",
    "COVERAGE_CELL_NON_PASSING",
    "COVERAGE_CELL_NOT_CURRENT",
    "DerivedFamilyBadCase",
    "FAMILY_CONFIDENCE_BLOCKED",
    "FAMILY_CONFIDENCE_FULL",
    "FAMILY_CONFIDENCE_SCOPED",
    "FAMILY_EVIDENCE_PROVENANCE_CONTROLLER_RECEIPT_FOLDED",
    "FAMILY_EVIDENCE_PROVENANCE_DERIVED_FROM_CACHE",
    "FAMILY_EVIDENCE_PROVENANCE_DURABLE_RECONCILIATION",
    "FAMILY_EVIDENCE_PROVENANCE_MANUAL_EVENT",
    "FAMILY_EVIDENCE_PROVENANCE_RUNTIME_OBSERVED",
    "FAMILY_EVIDENCE_PROVENANCE_TEST_INJECTED",
    "FAMILY_EVIDENCE_PROVENANCE_UNSPECIFIED",
    "FAMILY_EVIDENCE_SCOPE_EXTERNAL_CONTRACT",
    "FAMILY_EVIDENCE_SCOPE_INTERNAL_PATH",
    "FAMILY_EVIDENCE_SCOPE_MIXED",
    "FAMILY_EVIDENCE_SCOPE_UNKNOWN",
    "FAMILY_EVIDENCE_STATUS_ERROR",
    "FAMILY_EVIDENCE_STATUS_FAILED",
    "FAMILY_EVIDENCE_STATUS_NOT_RUN",
    "FAMILY_EVIDENCE_STATUS_PASSED",
    "FAMILY_EVIDENCE_STATUS_PROGRESS_ONLY",
    "FAMILY_EVIDENCE_STATUS_RUNNING",
    "FAMILY_EVIDENCE_STATUS_SKIPPED",
    "FAMILY_EVIDENCE_STATUS_STALE",
    "FAMILY_PARITY_DECISION_BLOCKED",
    "FAMILY_PARITY_DECISION_FULL",
    "FAMILY_PARITY_DECISION_SCOPED",
    "FamilyBadCaseSeed",
    "NON_PASSING_FAMILY_EVIDENCE_STATUSES",
    "ObligationFamily",
    "ObligationFamilyCoverageCell",
    "ObligationFamilyEvidence",
    "ObligationFamilyMember",
    "ObligationFamilyParityFinding",
    "ObligationFamilyParityReport",
    "PASSING_FAMILY_EVIDENCE_STATUSES",
    "derive_same_class_bad_cases",
    "review_analogous_defect_scan",
    "review_obligation_family_parity",
]
