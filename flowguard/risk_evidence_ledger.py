"""Risk evidence ledger helpers for final FlowGuard confidence claims.

The ledger connects user-meaningful risks to model obligations, owner public
code contracts, proof evidence, freshness, and scoped-out gaps. It summarizes
route-specific evidence; it does not replace Model-Test Alignment, TestMesh,
ModelMesh, DevelopmentProcessFlow, or conformance replay.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable
from .maintenance_obligation import (
    OBLIGATION_STATUS_SCOPED,
    MaintenanceObligation,
    coerce_maintenance_obligation,
)
from .proof_artifact import ProofArtifactRef, coerce_proof_artifact_ref, proof_artifact_gap_codes


RISK_PROOF_KIND_TEST = "test"
RISK_PROOF_KIND_REPLAY = "replay"
RISK_PROOF_KIND_MANUAL = "manual"
RISK_PROOF_KIND_ROUTE_REPORT = "route_report"

RISK_PROOF_STATUS_PASSED = "passed"
RISK_PROOF_STATUS_FAILED = "failed"
RISK_PROOF_STATUS_SKIPPED = "skipped"
RISK_PROOF_STATUS_STALE = "stale"
RISK_PROOF_STATUS_NOT_RUN = "not_run"
RISK_PROOF_STATUS_RUNNING = "running"
RISK_PROOF_STATUS_PROGRESS_ONLY = "progress_only"
RISK_PROOF_STATUS_ERROR = "error"

RISK_PROOF_SCOPE_EXTERNAL_CONTRACT = "external_contract"
RISK_PROOF_SCOPE_INTERNAL_PATH = "internal_path"
RISK_PROOF_SCOPE_MIXED = "mixed"
RISK_PROOF_SCOPE_UNKNOWN = "unknown"

RISK_CONFIDENCE_FULL = "full"
RISK_CONFIDENCE_SCOPED = "scoped"
RISK_CONFIDENCE_PARTIAL = "partial"
RISK_CONFIDENCE_BLOCKED = "blocked"

RISK_LEDGER_DECISION_FULL = "risk_evidence_full_confidence"
RISK_LEDGER_DECISION_SCOPED = "risk_evidence_scoped_confidence"

PASSING_PROOF_STATUSES = {RISK_PROOF_STATUS_PASSED}
NON_PASSING_PROOF_STATUSES = {
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
class RiskEvidenceProof:
    """One test, replay, route report, or manual evidence item."""

    evidence_id: str
    proof_kind: str = RISK_PROOF_KIND_TEST
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
        object.__setattr__(self, "proof_kind", str(self.proof_kind))
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
        return self.result_status in PASSING_PROOF_STATUSES and self.current and self.route_evidence_current

    def has_external_scope(self) -> bool:
        return self.assertion_scope in {
            RISK_PROOF_SCOPE_EXTERNAL_CONTRACT,
            RISK_PROOF_SCOPE_MIXED,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "proof_kind": self.proof_kind,
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
class RiskEvidenceRow:
    """One user-meaningful risk and the evidence expected to support it."""

    risk_id: str
    description: str = ""
    required: bool = True
    in_scope: bool = True
    out_of_scope_reason: str = ""
    model_obligation_id: str = ""
    code_contract_id: str = ""
    code_contract_required: bool = False
    proof_evidence_ids: tuple[str, ...] = ()
    require_external_proof: bool = True
    parent_model_evidence_required: bool = False
    parent_model_evidence_current: bool = True
    defect_family_id: str = ""
    defect_family_gate_required: bool = False
    defect_family_gate_current: bool = True
    defect_family_gate_confidence: str = RISK_CONFIDENCE_FULL
    defect_family_scoped_reasons: tuple[str, ...] = ()
    model_split_gate_id: str = ""
    model_split_gate_required: bool = False
    model_split_gate_current: bool = True
    model_split_gate_confidence: str = RISK_CONFIDENCE_FULL
    model_split_scoped_reasons: tuple[str, ...] = ()
    test_split_gate_id: str = ""
    test_split_gate_required: bool = False
    test_split_gate_current: bool = True
    test_split_gate_confidence: str = RISK_CONFIDENCE_FULL
    test_split_scoped_reasons: tuple[str, ...] = ()
    family_gate_id: str = ""
    family_gate_required: bool = False
    family_gate_current: bool = True
    family_gate_confidence: str = RISK_CONFIDENCE_FULL
    family_gate_scoped_reasons: tuple[str, ...] = ()
    analogous_scan_id: str = ""
    analogous_scan_required: bool = False
    analogous_scan_current: bool = True
    analogous_scan_confidence: str = RISK_CONFIDENCE_FULL
    analogous_scan_scoped_reasons: tuple[str, ...] = ()
    topology_hazard_id: str = ""
    topology_hazard_required: bool = False
    topology_hazard_current: bool = True
    topology_hazard_confidence: str = RISK_CONFIDENCE_FULL
    topology_hazard_scoped_reasons: tuple[str, ...] = ()
    model_angle_review_id: str = ""
    model_angle_review_required: bool = False
    model_angle_review_current: bool = True
    model_angle_review_confidence: str = RISK_CONFIDENCE_FULL
    model_angle_scoped_reasons: tuple[str, ...] = ()
    maintenance_obligation_ids: tuple[str, ...] = ()
    maintenance_obligations_required: bool = False
    maintenance_obligation_scoped_reasons: tuple[str, ...] = ()
    overclaims_full_confidence: bool = False
    next_actions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "risk_id", str(self.risk_id))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "out_of_scope_reason", str(self.out_of_scope_reason))
        object.__setattr__(self, "model_obligation_id", str(self.model_obligation_id))
        object.__setattr__(self, "code_contract_id", str(self.code_contract_id))
        object.__setattr__(self, "proof_evidence_ids", _as_tuple(self.proof_evidence_ids))
        object.__setattr__(self, "defect_family_id", str(self.defect_family_id))
        object.__setattr__(self, "defect_family_gate_confidence", str(self.defect_family_gate_confidence))
        object.__setattr__(self, "defect_family_scoped_reasons", _as_tuple(self.defect_family_scoped_reasons))
        object.__setattr__(self, "model_split_gate_id", str(self.model_split_gate_id))
        object.__setattr__(self, "model_split_gate_confidence", str(self.model_split_gate_confidence))
        object.__setattr__(self, "model_split_scoped_reasons", _as_tuple(self.model_split_scoped_reasons))
        object.__setattr__(self, "test_split_gate_id", str(self.test_split_gate_id))
        object.__setattr__(self, "test_split_gate_confidence", str(self.test_split_gate_confidence))
        object.__setattr__(self, "test_split_scoped_reasons", _as_tuple(self.test_split_scoped_reasons))
        object.__setattr__(self, "family_gate_id", str(self.family_gate_id))
        object.__setattr__(self, "family_gate_confidence", str(self.family_gate_confidence))
        object.__setattr__(self, "family_gate_scoped_reasons", _as_tuple(self.family_gate_scoped_reasons))
        object.__setattr__(self, "analogous_scan_id", str(self.analogous_scan_id))
        object.__setattr__(self, "analogous_scan_confidence", str(self.analogous_scan_confidence))
        object.__setattr__(self, "analogous_scan_scoped_reasons", _as_tuple(self.analogous_scan_scoped_reasons))
        object.__setattr__(self, "topology_hazard_id", str(self.topology_hazard_id))
        object.__setattr__(self, "topology_hazard_confidence", str(self.topology_hazard_confidence))
        object.__setattr__(self, "topology_hazard_scoped_reasons", _as_tuple(self.topology_hazard_scoped_reasons))
        object.__setattr__(self, "model_angle_review_id", str(self.model_angle_review_id))
        object.__setattr__(self, "model_angle_review_confidence", str(self.model_angle_review_confidence))
        object.__setattr__(self, "model_angle_scoped_reasons", _as_tuple(self.model_angle_scoped_reasons))
        object.__setattr__(self, "maintenance_obligation_ids", _as_tuple(self.maintenance_obligation_ids))
        object.__setattr__(
            self,
            "maintenance_obligation_scoped_reasons",
            _as_tuple(self.maintenance_obligation_scoped_reasons),
        )
        object.__setattr__(self, "next_actions", _as_tuple(self.next_actions))

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_id": self.risk_id,
            "description": self.description,
            "required": self.required,
            "in_scope": self.in_scope,
            "out_of_scope_reason": self.out_of_scope_reason,
            "model_obligation_id": self.model_obligation_id,
            "code_contract_id": self.code_contract_id,
            "code_contract_required": self.code_contract_required,
            "proof_evidence_ids": list(self.proof_evidence_ids),
            "require_external_proof": self.require_external_proof,
            "parent_model_evidence_required": self.parent_model_evidence_required,
            "parent_model_evidence_current": self.parent_model_evidence_current,
            "defect_family_id": self.defect_family_id,
            "defect_family_gate_required": self.defect_family_gate_required,
            "defect_family_gate_current": self.defect_family_gate_current,
            "defect_family_gate_confidence": self.defect_family_gate_confidence,
            "defect_family_scoped_reasons": list(self.defect_family_scoped_reasons),
            "model_split_gate_id": self.model_split_gate_id,
            "model_split_gate_required": self.model_split_gate_required,
            "model_split_gate_current": self.model_split_gate_current,
            "model_split_gate_confidence": self.model_split_gate_confidence,
            "model_split_scoped_reasons": list(self.model_split_scoped_reasons),
            "test_split_gate_id": self.test_split_gate_id,
            "test_split_gate_required": self.test_split_gate_required,
            "test_split_gate_current": self.test_split_gate_current,
            "test_split_gate_confidence": self.test_split_gate_confidence,
            "test_split_scoped_reasons": list(self.test_split_scoped_reasons),
            "family_gate_id": self.family_gate_id,
            "family_gate_required": self.family_gate_required,
            "family_gate_current": self.family_gate_current,
            "family_gate_confidence": self.family_gate_confidence,
            "family_gate_scoped_reasons": list(self.family_gate_scoped_reasons),
            "analogous_scan_id": self.analogous_scan_id,
            "analogous_scan_required": self.analogous_scan_required,
            "analogous_scan_current": self.analogous_scan_current,
            "analogous_scan_confidence": self.analogous_scan_confidence,
            "analogous_scan_scoped_reasons": list(self.analogous_scan_scoped_reasons),
            "topology_hazard_id": self.topology_hazard_id,
            "topology_hazard_required": self.topology_hazard_required,
            "topology_hazard_current": self.topology_hazard_current,
            "topology_hazard_confidence": self.topology_hazard_confidence,
            "topology_hazard_scoped_reasons": list(self.topology_hazard_scoped_reasons),
            "model_angle_review_id": self.model_angle_review_id,
            "model_angle_review_required": self.model_angle_review_required,
            "model_angle_review_current": self.model_angle_review_current,
            "model_angle_review_confidence": self.model_angle_review_confidence,
            "model_angle_scoped_reasons": list(self.model_angle_scoped_reasons),
            "maintenance_obligation_ids": list(self.maintenance_obligation_ids),
            "maintenance_obligations_required": self.maintenance_obligations_required,
            "maintenance_obligation_scoped_reasons": list(self.maintenance_obligation_scoped_reasons),
            "overclaims_full_confidence": self.overclaims_full_confidence,
            "next_actions": list(self.next_actions),
        }


@dataclass(frozen=True)
class RiskEvidenceLedgerPlan:
    """A final confidence review over modeled risks and supporting evidence."""

    ledger_id: str
    rows: tuple[RiskEvidenceRow, ...] = ()
    proof_evidence: tuple[RiskEvidenceProof, ...] = ()
    maintenance_obligations: tuple[MaintenanceObligation, ...] = ()
    require_proof_artifacts: bool = False
    allow_scoped_confidence: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "ledger_id", str(self.ledger_id))
        object.__setattr__(self, "rows", tuple(self.rows))
        object.__setattr__(self, "proof_evidence", tuple(self.proof_evidence))
        object.__setattr__(
            self,
            "maintenance_obligations",
            tuple(coerce_maintenance_obligation(item) for item in self.maintenance_obligations),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ledger_id": self.ledger_id,
            "rows": [row.to_dict() for row in self.rows],
            "proof_evidence": [evidence.to_dict() for evidence in self.proof_evidence],
            "maintenance_obligations": [obligation.to_dict() for obligation in self.maintenance_obligations],
            "require_proof_artifacts": self.require_proof_artifacts,
            "allow_scoped_confidence": self.allow_scoped_confidence,
        }


@dataclass(frozen=True)
class RiskEvidenceFinding:
    """One risk ledger confidence gap or scoped boundary."""

    code: str
    message: str
    severity: str = "blocker"
    risk_id: str = ""
    evidence_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "risk_id", str(self.risk_id))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "risk_id": self.risk_id,
            "evidence_id": self.evidence_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class RiskEvidenceLedgerReport:
    """Structured result of a risk evidence ledger review."""

    ok: bool
    ledger_id: str
    decision: str
    confidence: str
    findings: tuple[RiskEvidenceFinding, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "ledger_id", str(self.ledger_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "findings", tuple(self.findings))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: ledger={self.ledger_id} decision={self.decision} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard risk evidence ledger ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"ledger: {self.ledger_id}",
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
                    f"risk: {finding.risk_id or '(none)'}",
                    f"evidence: {finding.evidence_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "ledger_id": self.ledger_id,
            "decision": self.decision,
            "confidence": self.confidence,
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
        }


def _finding(
    code: str,
    message: str,
    *,
    risk_id: str = "",
    evidence_id: str = "",
    severity: str = "blocker",
    metadata: Mapping[str, Any] | None = None,
) -> RiskEvidenceFinding:
    return RiskEvidenceFinding(
        code,
        message,
        severity=severity,
        risk_id=risk_id,
        evidence_id=evidence_id,
        metadata=metadata or {},
    )


def _decision_for(findings: Sequence[RiskEvidenceFinding]) -> tuple[str, str, bool]:
    blockers = tuple(finding for finding in findings if finding.severity == "blocker")
    if not blockers:
        if findings:
            return RISK_LEDGER_DECISION_SCOPED, RISK_CONFIDENCE_SCOPED, True
        return RISK_LEDGER_DECISION_FULL, RISK_CONFIDENCE_FULL, True
    priority = (
        "duplicate_risk_id",
        "duplicate_evidence_id",
        "duplicate_maintenance_obligation_id",
        "unknown_evidence_reference",
        "unknown_maintenance_obligation_reference",
        "missing_model_obligation",
        "missing_code_contract",
        "missing_maintenance_obligation",
        "maintenance_obligation_not_current",
        "open_maintenance_obligation",
        "missing_defect_family_gate",
        "defect_family_gate_not_current",
        "defect_family_gate_blocked",
        "missing_family_gate",
        "family_gate_not_current",
        "family_gate_blocked",
        "missing_analogous_scan",
        "analogous_scan_not_current",
        "analogous_scan_blocked",
        "missing_model_angle_review",
        "model_angle_review_not_current",
        "model_angle_review_blocked",
        "missing_model_split_gate",
        "model_split_gate_not_current",
        "model_split_gate_blocked",
        "missing_test_split_gate",
        "test_split_gate_not_current",
        "test_split_gate_blocked",
        "missing_proof_evidence",
        "parent_model_evidence_gap",
        "route_gap_visible",
        "stale_proof_evidence",
        "proof_evidence_not_passing",
        "missing_current_passing_proof",
        "internal_path_only_evidence",
        "defect_family_gate_scoped_confidence",
        "family_gate_scoped_confidence",
        "analogous_scan_scoped_confidence",
        "model_angle_review_scoped_confidence",
        "model_split_gate_scoped_confidence",
        "test_split_gate_scoped_confidence",
        "maintenance_obligation_scoped_confidence",
        "maintenance_obligation_missing_resolution_evidence",
        "proof_overclaims_full_confidence",
        "scoped_out_required_risk",
    )
    blocker_codes = {finding.code for finding in blockers}
    for code in priority:
        if code in blocker_codes:
            return code, RISK_CONFIDENCE_BLOCKED, False
    return blockers[0].code, RISK_CONFIDENCE_BLOCKED, False


def review_risk_evidence_ledger(plan: RiskEvidenceLedgerPlan) -> RiskEvidenceLedgerReport:
    """Review whether modeled risks are supported by current external evidence."""

    findings: list[RiskEvidenceFinding] = []
    row_ids: set[str] = set()
    for row in plan.rows:
        if row.risk_id in row_ids:
            findings.append(
                _finding(
                    "duplicate_risk_id",
                    f"risk id {row.risk_id!r} appears more than once",
                    risk_id=row.risk_id,
                )
            )
        row_ids.add(row.risk_id)

    proof_by_id = {proof.evidence_id: proof for proof in plan.proof_evidence}
    if len(proof_by_id) != len(plan.proof_evidence):
        seen: set[str] = set()
        for proof in plan.proof_evidence:
            if proof.evidence_id in seen:
                findings.append(
                    _finding(
                        "duplicate_evidence_id",
                        f"evidence id {proof.evidence_id!r} appears more than once",
                        evidence_id=proof.evidence_id,
                    )
                )
            seen.add(proof.evidence_id)

    obligation_by_id = {obligation.obligation_id: obligation for obligation in plan.maintenance_obligations}
    if len(obligation_by_id) != len(plan.maintenance_obligations):
        seen_obligations: set[str] = set()
        for obligation in plan.maintenance_obligations:
            if obligation.obligation_id in seen_obligations:
                findings.append(
                    _finding(
                        "duplicate_maintenance_obligation_id",
                        f"maintenance obligation id {obligation.obligation_id!r} appears more than once",
                        metadata={"obligation_id": obligation.obligation_id},
                    )
                )
            seen_obligations.add(obligation.obligation_id)

    for row in plan.rows:
        if not row.in_scope:
            severity = "warning" if plan.allow_scoped_confidence and row.out_of_scope_reason else "blocker"
            code = "scoped_out_risk" if severity == "warning" else "scoped_out_required_risk"
            findings.append(
                _finding(
                    code,
                    row.out_of_scope_reason or "risk is out of scope without a reason",
                    risk_id=row.risk_id,
                    severity=severity,
                )
            )
            continue

        if row.required and not row.model_obligation_id:
            findings.append(
                _finding(
                    "missing_model_obligation",
                    "required risk has no FlowGuard model obligation owner",
                    risk_id=row.risk_id,
                )
            )

        if row.required and not row.code_contract_id:
            findings.append(
                _finding(
                    "missing_code_contract",
                    "required in-scope risk has no public code contract owner",
                    risk_id=row.risk_id,
                )
            )

        if row.defect_family_gate_required and not row.defect_family_id:
            findings.append(
                _finding(
                    "missing_defect_family_gate",
                    "required risk has no recurring defect-family gate owner",
                    risk_id=row.risk_id,
                )
            )

        if row.defect_family_gate_required and row.defect_family_id and not row.defect_family_gate_current:
            findings.append(
                _finding(
                    "defect_family_gate_not_current",
                    "required defect-family gate evidence is stale or has not been rerun",
                    risk_id=row.risk_id,
                    metadata={"defect_family_id": row.defect_family_id},
                )
            )

        if row.defect_family_gate_required and row.defect_family_id:
            if row.defect_family_gate_confidence == RISK_CONFIDENCE_BLOCKED:
                findings.append(
                    _finding(
                        "defect_family_gate_blocked",
                        "required defect-family gate is blocked",
                        risk_id=row.risk_id,
                        metadata={"defect_family_id": row.defect_family_id},
                    )
                )
            elif row.defect_family_gate_confidence in {RISK_CONFIDENCE_SCOPED, RISK_CONFIDENCE_PARTIAL}:
                severity = "warning" if plan.allow_scoped_confidence else "blocker"
                findings.append(
                    _finding(
                        "defect_family_gate_scoped_confidence",
                        "defect-family gate remains explicitly scoped",
                        risk_id=row.risk_id,
                        severity=severity,
                        metadata={
                            "defect_family_id": row.defect_family_id,
                            "defect_family_gate_confidence": row.defect_family_gate_confidence,
                        },
                    )
                )

        if row.defect_family_scoped_reasons:
            severity = "warning" if plan.allow_scoped_confidence else "blocker"
            findings.append(
                _finding(
                    "defect_family_gate_scoped_confidence",
                    "defect-family gate remains explicitly scoped",
                    risk_id=row.risk_id,
                    severity=severity,
                    metadata={
                        "defect_family_id": row.defect_family_id,
                        "defect_family_scoped_reasons": list(row.defect_family_scoped_reasons),
                    },
                )
            )

        if row.family_gate_required and not row.family_gate_id:
            findings.append(
                _finding(
                    "missing_family_gate",
                    "required risk has no obligation-family parity gate owner",
                    risk_id=row.risk_id,
                )
            )

        if row.family_gate_required and row.family_gate_id and not row.family_gate_current:
            findings.append(
                _finding(
                    "family_gate_not_current",
                    "required obligation-family parity gate evidence is stale or has not been rerun",
                    risk_id=row.risk_id,
                    metadata={"family_gate_id": row.family_gate_id},
                )
            )

        if row.family_gate_required and row.family_gate_id:
            if row.family_gate_confidence == RISK_CONFIDENCE_BLOCKED:
                findings.append(
                    _finding(
                        "family_gate_blocked",
                        "required obligation-family parity gate is blocked",
                        risk_id=row.risk_id,
                        metadata={"family_gate_id": row.family_gate_id},
                    )
                )
            elif row.family_gate_confidence in {RISK_CONFIDENCE_SCOPED, RISK_CONFIDENCE_PARTIAL}:
                severity = "warning" if plan.allow_scoped_confidence else "blocker"
                findings.append(
                    _finding(
                        "family_gate_scoped_confidence",
                        "obligation-family parity gate remains explicitly scoped",
                        risk_id=row.risk_id,
                        severity=severity,
                        metadata={
                            "family_gate_id": row.family_gate_id,
                            "family_gate_confidence": row.family_gate_confidence,
                        },
                    )
                )

        if row.family_gate_scoped_reasons:
            severity = "warning" if plan.allow_scoped_confidence else "blocker"
            findings.append(
                _finding(
                    "family_gate_scoped_confidence",
                    "obligation-family parity gate remains explicitly scoped",
                    risk_id=row.risk_id,
                    severity=severity,
                    metadata={
                        "family_gate_id": row.family_gate_id,
                        "family_gate_scoped_reasons": list(row.family_gate_scoped_reasons),
                    },
                )
            )

        if row.analogous_scan_required and not row.analogous_scan_id:
            findings.append(
                _finding(
                    "missing_analogous_scan",
                    "required risk has no analogous defect scan owner",
                    risk_id=row.risk_id,
                )
            )

        if row.analogous_scan_required and row.analogous_scan_id and not row.analogous_scan_current:
            findings.append(
                _finding(
                    "analogous_scan_not_current",
                    "required analogous defect scan evidence is stale or has not been rerun",
                    risk_id=row.risk_id,
                    metadata={"analogous_scan_id": row.analogous_scan_id},
                )
            )

        if row.analogous_scan_required and row.analogous_scan_id:
            if row.analogous_scan_confidence == RISK_CONFIDENCE_BLOCKED:
                findings.append(
                    _finding(
                        "analogous_scan_blocked",
                        "required analogous defect scan is blocked",
                        risk_id=row.risk_id,
                        metadata={"analogous_scan_id": row.analogous_scan_id},
                    )
                )
            elif row.analogous_scan_confidence in {RISK_CONFIDENCE_SCOPED, RISK_CONFIDENCE_PARTIAL}:
                severity = "warning" if plan.allow_scoped_confidence else "blocker"
                findings.append(
                    _finding(
                        "analogous_scan_scoped_confidence",
                        "analogous defect scan remains explicitly scoped",
                        risk_id=row.risk_id,
                        severity=severity,
                        metadata={
                            "analogous_scan_id": row.analogous_scan_id,
                            "analogous_scan_confidence": row.analogous_scan_confidence,
                        },
                    )
                )

        if row.analogous_scan_scoped_reasons:
            severity = "warning" if plan.allow_scoped_confidence else "blocker"
            findings.append(
                _finding(
                    "analogous_scan_scoped_confidence",
                    "analogous defect scan remains explicitly scoped",
                    risk_id=row.risk_id,
                    severity=severity,
                    metadata={
                        "analogous_scan_id": row.analogous_scan_id,
                        "analogous_scan_scoped_reasons": list(row.analogous_scan_scoped_reasons),
                    },
                )
            )

        if row.topology_hazard_required and not row.topology_hazard_id:
            findings.append(
                _finding(
                    "missing_topology_hazard_review",
                    "required risk has no model-topology hazard review owner",
                    risk_id=row.risk_id,
                )
            )

        if row.topology_hazard_required and row.topology_hazard_id and not row.topology_hazard_current:
            findings.append(
                _finding(
                    "topology_hazard_review_not_current",
                    "required model-topology hazard review evidence is stale or has not been rerun",
                    risk_id=row.risk_id,
                    metadata={"topology_hazard_id": row.topology_hazard_id},
                )
            )

        if row.topology_hazard_required and row.topology_hazard_id:
            if row.topology_hazard_confidence == RISK_CONFIDENCE_BLOCKED:
                findings.append(
                    _finding(
                        "topology_hazard_review_blocked",
                        "required model-topology hazard review is blocked",
                        risk_id=row.risk_id,
                        metadata={"topology_hazard_id": row.topology_hazard_id},
                    )
                )
            elif row.topology_hazard_confidence in {RISK_CONFIDENCE_SCOPED, RISK_CONFIDENCE_PARTIAL}:
                severity = "warning" if plan.allow_scoped_confidence else "blocker"
                findings.append(
                    _finding(
                        "topology_hazard_review_scoped_confidence",
                        "model-topology hazard review remains explicitly scoped",
                        risk_id=row.risk_id,
                        severity=severity,
                        metadata={
                            "topology_hazard_id": row.topology_hazard_id,
                            "topology_hazard_confidence": row.topology_hazard_confidence,
                        },
                    )
                )

        if row.topology_hazard_scoped_reasons:
            severity = "warning" if plan.allow_scoped_confidence else "blocker"
            findings.append(
                _finding(
                    "topology_hazard_review_scoped_confidence",
                    "model-topology hazard review remains explicitly scoped",
                    risk_id=row.risk_id,
                    severity=severity,
                    metadata={
                        "topology_hazard_id": row.topology_hazard_id,
                        "topology_hazard_scoped_reasons": list(row.topology_hazard_scoped_reasons),
                    },
                )
            )

        if row.model_angle_review_required and not row.model_angle_review_id:
            findings.append(
                _finding(
                    "missing_model_angle_review",
                    "required risk has no model-angle deliberation review owner",
                    risk_id=row.risk_id,
                )
            )

        if row.model_angle_review_required and row.model_angle_review_id and not row.model_angle_review_current:
            findings.append(
                _finding(
                    "model_angle_review_not_current",
                    "required model-angle deliberation evidence is stale or has not been rerun",
                    risk_id=row.risk_id,
                    metadata={"model_angle_review_id": row.model_angle_review_id},
                )
            )

        if row.model_angle_review_required and row.model_angle_review_id:
            if row.model_angle_review_confidence == RISK_CONFIDENCE_BLOCKED:
                findings.append(
                    _finding(
                        "model_angle_review_blocked",
                        "required model-angle deliberation review is blocked",
                        risk_id=row.risk_id,
                        metadata={"model_angle_review_id": row.model_angle_review_id},
                    )
                )
            elif row.model_angle_review_confidence in {RISK_CONFIDENCE_SCOPED, RISK_CONFIDENCE_PARTIAL}:
                severity = "warning" if plan.allow_scoped_confidence else "blocker"
                findings.append(
                    _finding(
                        "model_angle_review_scoped_confidence",
                        "model-angle deliberation remains explicitly scoped",
                        risk_id=row.risk_id,
                        severity=severity,
                        metadata={
                            "model_angle_review_id": row.model_angle_review_id,
                            "model_angle_review_confidence": row.model_angle_review_confidence,
                        },
                    )
                )

        if row.model_angle_scoped_reasons:
            severity = "warning" if plan.allow_scoped_confidence else "blocker"
            findings.append(
                _finding(
                    "model_angle_review_scoped_confidence",
                    "model-angle deliberation remains explicitly scoped",
                    risk_id=row.risk_id,
                    severity=severity,
                    metadata={
                        "model_angle_review_id": row.model_angle_review_id,
                        "model_angle_scoped_reasons": list(row.model_angle_scoped_reasons),
                    },
                )
            )

        split_gate_specs = (
            (
                "model",
                row.model_split_gate_required,
                row.model_split_gate_id,
                row.model_split_gate_current,
                row.model_split_gate_confidence,
                row.model_split_scoped_reasons,
            ),
            (
                "test",
                row.test_split_gate_required,
                row.test_split_gate_id,
                row.test_split_gate_current,
                row.test_split_gate_confidence,
                row.test_split_scoped_reasons,
            ),
        )
        for split_kind, required, gate_id, current, confidence, scoped_reasons in split_gate_specs:
            if required and not gate_id:
                findings.append(
                    _finding(
                        f"missing_{split_kind}_split_gate",
                        f"required risk has no current {split_kind} split gate owner",
                        risk_id=row.risk_id,
                    )
                )
            if required and gate_id and not current:
                findings.append(
                    _finding(
                        f"{split_kind}_split_gate_not_current",
                        f"required {split_kind} split gate evidence is stale or missing",
                        risk_id=row.risk_id,
                        metadata={f"{split_kind}_split_gate_id": gate_id},
                    )
                )
            if required and gate_id:
                if confidence == RISK_CONFIDENCE_BLOCKED:
                    findings.append(
                        _finding(
                            f"{split_kind}_split_gate_blocked",
                            f"required {split_kind} split gate is blocked",
                            risk_id=row.risk_id,
                            metadata={f"{split_kind}_split_gate_id": gate_id},
                        )
                    )
                elif confidence in {RISK_CONFIDENCE_SCOPED, RISK_CONFIDENCE_PARTIAL}:
                    severity = "warning" if plan.allow_scoped_confidence else "blocker"
                    findings.append(
                        _finding(
                            f"{split_kind}_split_gate_scoped_confidence",
                            f"required {split_kind} split gate remains explicitly scoped",
                            risk_id=row.risk_id,
                            severity=severity,
                            metadata={
                                f"{split_kind}_split_gate_id": gate_id,
                                f"{split_kind}_split_gate_confidence": confidence,
                            },
                        )
                    )
            if scoped_reasons:
                severity = "warning" if plan.allow_scoped_confidence else "blocker"
                findings.append(
                    _finding(
                        f"{split_kind}_split_gate_scoped_confidence",
                        f"required {split_kind} split gate remains explicitly scoped",
                        risk_id=row.risk_id,
                        severity=severity,
                        metadata={
                            f"{split_kind}_split_gate_id": gate_id,
                            f"{split_kind}_split_scoped_reasons": list(scoped_reasons),
                        },
                    )
                )

        if row.parent_model_evidence_required and not row.parent_model_evidence_current:
            findings.append(
                _finding(
                    "parent_model_evidence_gap",
                    "child model evidence has not been consumed by current parent evidence",
                    risk_id=row.risk_id,
                )
            )

        if row.maintenance_obligations_required and not row.maintenance_obligation_ids:
            findings.append(
                _finding(
                    "missing_maintenance_obligation",
                    "required risk has no remembered maintenance obligation owner",
                    risk_id=row.risk_id,
                )
            )

        for obligation_id in row.maintenance_obligation_ids:
            obligation = obligation_by_id.get(obligation_id)
            if obligation is None:
                findings.append(
                    _finding(
                        "unknown_maintenance_obligation_reference",
                        f"risk references unknown maintenance obligation {obligation_id!r}",
                        risk_id=row.risk_id,
                        metadata={"obligation_id": obligation_id},
                    )
                )
                continue
            if not obligation.current:
                findings.append(
                    _finding(
                        "maintenance_obligation_not_current",
                        "referenced maintenance obligation memory is stale",
                        risk_id=row.risk_id,
                        metadata={"obligation": obligation.to_dict()},
                    )
                )
            if obligation.is_active():
                findings.append(
                    _finding(
                        "open_maintenance_obligation",
                        "referenced maintenance obligation is still open",
                        risk_id=row.risk_id,
                        metadata={"obligation": obligation.to_dict()},
                    )
                )
            elif obligation.status == OBLIGATION_STATUS_SCOPED or obligation.scope_reason:
                severity = "warning" if plan.allow_scoped_confidence else "blocker"
                findings.append(
                    _finding(
                        "maintenance_obligation_scoped_confidence",
                        "referenced maintenance obligation remains explicitly scoped",
                        risk_id=row.risk_id,
                        severity=severity,
                        metadata={"obligation": obligation.to_dict()},
                    )
                )
            elif not obligation.has_resolution_evidence():
                findings.append(
                    _finding(
                        "maintenance_obligation_missing_resolution_evidence",
                        "referenced maintenance obligation has no resolution evidence",
                        risk_id=row.risk_id,
                        metadata={"obligation": obligation.to_dict()},
                    )
                )

        if row.maintenance_obligation_scoped_reasons:
            severity = "warning" if plan.allow_scoped_confidence else "blocker"
            findings.append(
                _finding(
                    "maintenance_obligation_scoped_confidence",
                    "maintenance obligation memory remains explicitly scoped",
                    risk_id=row.risk_id,
                    severity=severity,
                    metadata={
                        "maintenance_obligation_ids": list(row.maintenance_obligation_ids),
                        "maintenance_obligation_scoped_reasons": list(row.maintenance_obligation_scoped_reasons),
                    },
                )
            )

        if row.required and not row.proof_evidence_ids:
            findings.append(
                _finding(
                    "missing_proof_evidence",
                    "required risk has no test, replay, route, or manual proof evidence",
                    risk_id=row.risk_id,
                )
            )
            continue

        current_external_pass = False
        current_any_pass = False
        for evidence_id in row.proof_evidence_ids:
            proof = proof_by_id.get(evidence_id)
            if proof is None:
                findings.append(
                    _finding(
                        "unknown_evidence_reference",
                        f"risk references unknown proof evidence {evidence_id!r}",
                        risk_id=row.risk_id,
                        evidence_id=evidence_id,
                    )
                )
                continue

            if proof.route_gap_codes:
                findings.append(
                    _finding(
                        "route_gap_visible",
                        "referenced route evidence has unresolved gaps",
                        risk_id=row.risk_id,
                        evidence_id=evidence_id,
                        metadata={"route_gap_codes": list(proof.route_gap_codes)},
                    )
                )
            if not proof.current or proof.stale_reasons or not proof.route_evidence_current:
                findings.append(
                    _finding(
                        "stale_proof_evidence",
                        "proof evidence is stale or its route evidence is stale",
                        risk_id=row.risk_id,
                        evidence_id=evidence_id,
                        metadata={"stale_reasons": list(proof.stale_reasons)},
                    )
                )
            if proof.result_status in NON_PASSING_PROOF_STATUSES:
                findings.append(
                    _finding(
                        "proof_evidence_not_passing",
                        f"proof evidence status is {proof.result_status}",
                        risk_id=row.risk_id,
                        evidence_id=evidence_id,
                    )
                )
            if plan.require_proof_artifacts:
                for code, message in proof_artifact_gap_codes(
                    proof.proof_artifact,
                    declared_status=proof.result_status,
                    required_obligation_ids=(row.model_obligation_id,),
                    require_result_path=True,
                    require_fingerprints=True,
                    require_external_scope=row.require_external_proof,
                ):
                    findings.append(
                        _finding(
                            code.replace("proof_artifact", "proof_evidence_artifact"),
                            message,
                            risk_id=row.risk_id,
                            evidence_id=evidence_id,
                            metadata={"proof": proof.to_dict()},
                        )
                    )
            if proof.has_current_pass():
                current_any_pass = True
                if proof.has_external_scope():
                    current_external_pass = True

        if row.required and row.proof_evidence_ids and not current_any_pass:
            findings.append(
                _finding(
                    "missing_current_passing_proof",
                    "required risk has no current passing proof evidence",
                    risk_id=row.risk_id,
                )
            )
        if row.required and row.require_external_proof and row.proof_evidence_ids and current_any_pass and not current_external_pass:
            findings.append(
                _finding(
                    "internal_path_only_evidence",
                    "passing evidence does not exercise the external contract boundary",
                    risk_id=row.risk_id,
                )
            )
        if row.overclaims_full_confidence:
            findings.append(
                _finding(
                    "proof_overclaims_full_confidence",
                    "risk row claims broader confidence than its bound evidence proves",
                    risk_id=row.risk_id,
                )
            )

    decision, confidence, ok = _decision_for(findings)
    return RiskEvidenceLedgerReport(
        ok=ok,
        ledger_id=plan.ledger_id,
        decision=decision,
        confidence=confidence,
        findings=tuple(findings),
    )


__all__ = [
    "NON_PASSING_PROOF_STATUSES",
    "PASSING_PROOF_STATUSES",
    "RISK_CONFIDENCE_BLOCKED",
    "RISK_CONFIDENCE_FULL",
    "RISK_CONFIDENCE_PARTIAL",
    "RISK_CONFIDENCE_SCOPED",
    "RISK_LEDGER_DECISION_FULL",
    "RISK_LEDGER_DECISION_SCOPED",
    "RISK_PROOF_KIND_MANUAL",
    "RISK_PROOF_KIND_REPLAY",
    "RISK_PROOF_KIND_ROUTE_REPORT",
    "RISK_PROOF_KIND_TEST",
    "RISK_PROOF_SCOPE_EXTERNAL_CONTRACT",
    "RISK_PROOF_SCOPE_INTERNAL_PATH",
    "RISK_PROOF_SCOPE_MIXED",
    "RISK_PROOF_SCOPE_UNKNOWN",
    "RISK_PROOF_STATUS_ERROR",
    "RISK_PROOF_STATUS_FAILED",
    "RISK_PROOF_STATUS_NOT_RUN",
    "RISK_PROOF_STATUS_PASSED",
    "RISK_PROOF_STATUS_PROGRESS_ONLY",
    "RISK_PROOF_STATUS_RUNNING",
    "RISK_PROOF_STATUS_SKIPPED",
    "RISK_PROOF_STATUS_STALE",
    "MaintenanceObligation",
    "RiskEvidenceFinding",
    "RiskEvidenceLedgerPlan",
    "RiskEvidenceLedgerReport",
    "RiskEvidenceProof",
    "RiskEvidenceRow",
    "review_risk_evidence_ledger",
]
