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

RISK_GATE_DEFECT_FAMILY = "defect_family"
RISK_GATE_MODEL_SPLIT = "model_split"
RISK_GATE_TEST_SPLIT = "test_split"
RISK_GATE_FAMILY = "family"
RISK_GATE_ANALOGOUS_SCAN = "analogous_scan"
RISK_GATE_TOPOLOGY_HAZARD = "topology_hazard"
RISK_GATE_MODEL_ANGLE_REVIEW = "model_angle_review"
RISK_GATE_PARENT_MODEL_EVIDENCE = "parent_model_evidence"
RISK_GATE_MAINTENANCE_OBLIGATION = "maintenance_obligation"
RISK_GATE_UI_IMPLEMENTATION = "ui_implementation"
RISK_GATE_UI_REAL_SURFACE = "ui_real_surface"
RISK_GATE_UI_FUNCTIONAL_CHAIN = "ui_functional_chain"
RISK_GATE_UI_DONE_CLAIM = "ui_done_claim"
RISK_GATE_UI_HUMAN_OPERABILITY = "ui_human_operability"
RISK_GATE_UI_SOURCE_BASELINE_INTERACTION = "ui_source_baseline_interaction"
RISK_GATE_ARTIFACT_PAYLOAD = "artifact_payload"

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
class RiskEvidenceGate:
    """One optional route-specific gate for a user-meaningful risk."""

    kind: str = ""
    evidence_id: str = ""
    required: bool = True
    current: bool = True
    confidence: str = RISK_CONFIDENCE_FULL
    scoped_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", str(self.kind))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "scoped_reasons", _as_tuple(self.scoped_reasons))

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "evidence_id": self.evidence_id,
            "required": self.required,
            "current": self.current,
            "confidence": self.confidence,
            "scoped_reasons": list(self.scoped_reasons),
        }


def _coerce_risk_gate(gate: RiskEvidenceGate | Mapping[str, Any]) -> RiskEvidenceGate:
    if isinstance(gate, RiskEvidenceGate):
        return gate
    return RiskEvidenceGate(**dict(gate))


@dataclass(frozen=True)
class RiskEvidenceRow:
    """One user-meaningful risk and the evidence expected to support it."""

    risk_id: str
    required: bool = True
    in_scope: bool = True
    out_of_scope_reason: str = ""
    model_obligation_id: str = ""
    code_contract_id: str = ""
    proof_evidence_ids: tuple[str, ...] = ()
    require_external_proof: bool = True
    gates: tuple[RiskEvidenceGate, ...] = ()
    maintenance_obligation_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "risk_id", str(self.risk_id))
        object.__setattr__(self, "out_of_scope_reason", str(self.out_of_scope_reason))
        object.__setattr__(self, "model_obligation_id", str(self.model_obligation_id))
        object.__setattr__(self, "code_contract_id", str(self.code_contract_id))
        object.__setattr__(self, "proof_evidence_ids", _as_tuple(self.proof_evidence_ids))
        object.__setattr__(self, "gates", tuple(_coerce_risk_gate(gate) for gate in self.gates))
        object.__setattr__(self, "maintenance_obligation_ids", _as_tuple(self.maintenance_obligation_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_id": self.risk_id,
            "required": self.required,
            "in_scope": self.in_scope,
            "out_of_scope_reason": self.out_of_scope_reason,
            "model_obligation_id": self.model_obligation_id,
            "code_contract_id": self.code_contract_id,
            "proof_evidence_ids": list(self.proof_evidence_ids),
            "require_external_proof": self.require_external_proof,
            "gates": [gate.to_dict() for gate in self.gates],
            "maintenance_obligation_ids": list(self.maintenance_obligation_ids),
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
        "unknown_risk_gate_kind",
        "unknown_evidence_reference",
        "unknown_maintenance_obligation_reference",
        "missing_model_obligation",
        "missing_code_contract",
        "missing_maintenance_obligation",
        "missing_parent_model_evidence",
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
        "missing_topology_hazard_review",
        "topology_hazard_review_not_current",
        "topology_hazard_review_blocked",
        "missing_model_angle_review",
        "model_angle_review_not_current",
        "model_angle_review_blocked",
        "missing_model_split_gate",
        "model_split_gate_not_current",
        "model_split_gate_blocked",
        "missing_test_split_gate",
        "test_split_gate_not_current",
        "test_split_gate_blocked",
        "missing_ui_implementation_gate",
        "ui_implementation_gate_not_current",
        "ui_implementation_gate_blocked",
        "missing_artifact_payload_gate",
        "artifact_payload_gate_not_current",
        "artifact_payload_gate_blocked",
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
        "ui_implementation_gate_scoped_confidence",
        "artifact_payload_gate_scoped_confidence",
        "maintenance_obligation_scoped_confidence",
        "maintenance_obligation_missing_resolution_evidence",
        "scoped_out_required_risk",
    )
    blocker_codes = {finding.code for finding in blockers}
    for code in priority:
        if code in blocker_codes:
            return code, RISK_CONFIDENCE_BLOCKED, False
    return blockers[0].code, RISK_CONFIDENCE_BLOCKED, False


GATE_CODE_MAP = {
    RISK_GATE_DEFECT_FAMILY: (
        "missing_defect_family_gate",
        "defect_family_gate_not_current",
        "defect_family_gate_blocked",
        "defect_family_gate_scoped_confidence",
        "required risk has no recurring defect-family gate owner",
        "required defect-family gate evidence is stale or has not been rerun",
        "required defect-family gate is blocked",
        "defect-family gate remains explicitly scoped",
    ),
    RISK_GATE_FAMILY: (
        "missing_family_gate",
        "family_gate_not_current",
        "family_gate_blocked",
        "family_gate_scoped_confidence",
        "required risk has no obligation-family parity gate owner",
        "required obligation-family parity gate evidence is stale or has not been rerun",
        "required obligation-family parity gate is blocked",
        "obligation-family parity gate remains explicitly scoped",
    ),
    RISK_GATE_ANALOGOUS_SCAN: (
        "missing_analogous_scan",
        "analogous_scan_not_current",
        "analogous_scan_blocked",
        "analogous_scan_scoped_confidence",
        "required risk has no analogous defect scan owner",
        "required analogous defect scan evidence is stale or has not been rerun",
        "required analogous defect scan is blocked",
        "analogous defect scan remains explicitly scoped",
    ),
    RISK_GATE_TOPOLOGY_HAZARD: (
        "missing_topology_hazard_review",
        "topology_hazard_review_not_current",
        "topology_hazard_review_blocked",
        "topology_hazard_review_scoped_confidence",
        "required risk has no model-topology hazard review owner",
        "required model-topology hazard review evidence is stale or has not been rerun",
        "required model-topology hazard review is blocked",
        "model-topology hazard review remains explicitly scoped",
    ),
    RISK_GATE_MODEL_ANGLE_REVIEW: (
        "missing_model_angle_review",
        "model_angle_review_not_current",
        "model_angle_review_blocked",
        "model_angle_review_scoped_confidence",
        "required risk has no model-angle deliberation review owner",
        "required model-angle deliberation evidence is stale or has not been rerun",
        "required model-angle deliberation review is blocked",
        "model-angle deliberation remains explicitly scoped",
    ),
    RISK_GATE_MODEL_SPLIT: (
        "missing_model_split_gate",
        "model_split_gate_not_current",
        "model_split_gate_blocked",
        "model_split_gate_scoped_confidence",
        "required risk has no current model split gate owner",
        "required model split gate evidence is stale or missing",
        "required model split gate is blocked",
        "required model split gate remains explicitly scoped",
    ),
    RISK_GATE_TEST_SPLIT: (
        "missing_test_split_gate",
        "test_split_gate_not_current",
        "test_split_gate_blocked",
        "test_split_gate_scoped_confidence",
        "required risk has no current test split gate owner",
        "required test split gate evidence is stale or missing",
        "required test split gate is blocked",
        "required test split gate remains explicitly scoped",
    ),
    RISK_GATE_UI_IMPLEMENTATION: (
        "missing_ui_implementation_gate",
        "ui_implementation_gate_not_current",
        "ui_implementation_gate_blocked",
        "ui_implementation_gate_scoped_confidence",
        "required risk has no runnable UI implementation evidence gate",
        "required UI implementation evidence is stale or missing",
        "required UI implementation evidence gate is blocked",
        "required UI implementation evidence remains explicitly scoped",
    ),
    RISK_GATE_UI_REAL_SURFACE: (
        "missing_ui_real_surface_gate",
        "ui_real_surface_gate_not_current",
        "ui_real_surface_gate_blocked",
        "ui_real_surface_gate_scoped_confidence",
        "required risk has no observed real UI surface inventory gate",
        "required observed real UI surface evidence is stale or missing",
        "required observed real UI surface gate is blocked",
        "required observed real UI surface evidence remains explicitly scoped",
    ),
    RISK_GATE_UI_FUNCTIONAL_CHAIN: (
        "missing_ui_functional_chain_gate",
        "ui_functional_chain_gate_not_current",
        "ui_functional_chain_gate_blocked",
        "ui_functional_chain_gate_scoped_confidence",
        "required risk has no enabled-control functional-chain gate",
        "required enabled-control functional-chain evidence is stale or missing",
        "required enabled-control functional-chain gate is blocked",
        "required enabled-control functional-chain evidence remains explicitly scoped",
    ),
    RISK_GATE_UI_DONE_CLAIM: (
        "missing_ui_done_claim_gate",
        "ui_done_claim_gate_not_current",
        "ui_done_claim_gate_blocked",
        "ui_done_claim_gate_scoped_confidence",
        "required risk has no final UI done-claim review gate",
        "required final UI done-claim evidence is stale or missing",
        "required final UI done-claim gate is blocked",
        "required final UI done-claim evidence remains explicitly scoped",
    ),
    RISK_GATE_UI_HUMAN_OPERABILITY: (
        "missing_ui_human_operability_gate",
        "ui_human_operability_gate_not_current",
        "ui_human_operability_gate_blocked",
        "ui_human_operability_gate_scoped_confidence",
        "required risk has no UI human-operability evidence gate",
        "required UI human-operability evidence is stale or missing",
        "required UI human-operability gate is blocked",
        "required UI human-operability evidence remains explicitly scoped",
    ),
    RISK_GATE_UI_SOURCE_BASELINE_INTERACTION: (
        "missing_ui_source_baseline_interaction_gate",
        "ui_source_baseline_interaction_gate_not_current",
        "ui_source_baseline_interaction_gate_blocked",
        "ui_source_baseline_interaction_gate_scoped_confidence",
        "required risk has no UI source-baseline interaction semantics gate",
        "required UI source-baseline interaction evidence is stale or missing",
        "required UI source-baseline interaction gate is blocked",
        "required UI source-baseline interaction evidence remains explicitly scoped",
    ),
    RISK_GATE_ARTIFACT_PAYLOAD: (
        "missing_artifact_payload_gate",
        "artifact_payload_gate_not_current",
        "artifact_payload_gate_blocked",
        "artifact_payload_gate_scoped_confidence",
        "required risk has no artifact payload validation evidence gate",
        "required artifact payload validation evidence is stale or missing",
        "required artifact payload validation evidence gate is blocked",
        "required artifact payload validation evidence remains explicitly scoped",
    ),
    RISK_GATE_PARENT_MODEL_EVIDENCE: (
        "missing_parent_model_evidence",
        "parent_model_evidence_gap",
        "parent_model_evidence_blocked",
        "parent_model_evidence_scoped_confidence",
        "required risk has no parent model evidence owner",
        "child model evidence has not been consumed by current parent evidence",
        "required parent model evidence is blocked",
        "parent model evidence remains explicitly scoped",
    ),
}


def _generic_gate_findings(
    row: RiskEvidenceRow,
    gate: RiskEvidenceGate,
    *,
    allow_scoped_confidence: bool,
) -> list[RiskEvidenceFinding]:
    codes = GATE_CODE_MAP.get(gate.kind)
    if codes is None:
        return [
            _finding(
                "unknown_risk_gate_kind",
                f"risk gate kind {gate.kind!r} is not recognized",
                risk_id=row.risk_id,
                metadata={"gate": gate.to_dict()},
            )
        ]
    missing_code, stale_code, blocked_code, scoped_code, missing_msg, stale_msg, blocked_msg, scoped_msg = codes
    findings: list[RiskEvidenceFinding] = []
    metadata = {"gate": gate.to_dict()}
    if gate.required and not gate.evidence_id:
        findings.append(_finding(missing_code, missing_msg, risk_id=row.risk_id, metadata=metadata))
    if gate.required and gate.evidence_id and not gate.current:
        findings.append(_finding(stale_code, stale_msg, risk_id=row.risk_id, metadata=metadata))
    if gate.required and gate.evidence_id and gate.confidence == RISK_CONFIDENCE_BLOCKED:
        findings.append(_finding(blocked_code, blocked_msg, risk_id=row.risk_id, metadata=metadata))
    elif gate.required and gate.evidence_id and gate.confidence in {RISK_CONFIDENCE_SCOPED, RISK_CONFIDENCE_PARTIAL}:
        severity = "warning" if allow_scoped_confidence else "blocker"
        findings.append(_finding(scoped_code, scoped_msg, risk_id=row.risk_id, severity=severity, metadata=metadata))
    if gate.scoped_reasons:
        severity = "warning" if allow_scoped_confidence else "blocker"
        findings.append(_finding(scoped_code, scoped_msg, risk_id=row.risk_id, severity=severity, metadata=metadata))
    return findings


def _maintenance_obligation_findings(
    row: RiskEvidenceRow,
    obligation_id: str,
    obligation_by_id: Mapping[str, MaintenanceObligation],
    allow_scoped_confidence: bool,
) -> list[RiskEvidenceFinding]:
    obligation = obligation_by_id.get(obligation_id)
    if obligation is None:
        return [
            _finding(
                "unknown_maintenance_obligation_reference",
                f"risk references unknown maintenance obligation {obligation_id!r}",
                risk_id=row.risk_id,
                metadata={"obligation_id": obligation_id},
            )
        ]
    findings: list[RiskEvidenceFinding] = []
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
        severity = "warning" if allow_scoped_confidence else "blocker"
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
    return findings


def _maintenance_gate_findings(
    row: RiskEvidenceRow,
    gate: RiskEvidenceGate,
    obligation_by_id: Mapping[str, MaintenanceObligation],
    *,
    allow_scoped_confidence: bool,
) -> list[RiskEvidenceFinding]:
    if gate.required and not gate.evidence_id:
        return [
            _finding(
                "missing_maintenance_obligation",
                "required risk has no remembered maintenance obligation owner",
                risk_id=row.risk_id,
                metadata={"gate": gate.to_dict()},
            )
        ]
    findings: list[RiskEvidenceFinding] = []
    if gate.evidence_id:
        if gate.required and not gate.current:
            findings.append(
                _finding(
                    "maintenance_obligation_not_current",
                    "required maintenance obligation memory is stale or has not been rerun",
                    risk_id=row.risk_id,
                    metadata={"gate": gate.to_dict()},
                )
            )
        if gate.required and gate.confidence == RISK_CONFIDENCE_BLOCKED:
            findings.append(
                _finding(
                    "open_maintenance_obligation",
                    "required maintenance obligation gate is blocked",
                    risk_id=row.risk_id,
                    metadata={"gate": gate.to_dict()},
                )
            )
        elif gate.required and gate.confidence in {RISK_CONFIDENCE_SCOPED, RISK_CONFIDENCE_PARTIAL}:
            severity = "warning" if allow_scoped_confidence else "blocker"
            findings.append(
                _finding(
                    "maintenance_obligation_scoped_confidence",
                    "maintenance obligation gate remains explicitly scoped",
                    risk_id=row.risk_id,
                    severity=severity,
                    metadata={"gate": gate.to_dict()},
                )
            )
        findings.extend(_maintenance_obligation_findings(row, gate.evidence_id, obligation_by_id, allow_scoped_confidence))
    if gate.scoped_reasons:
        severity = "warning" if allow_scoped_confidence else "blocker"
        findings.append(
            _finding(
                "maintenance_obligation_scoped_confidence",
                "maintenance obligation memory remains explicitly scoped",
                risk_id=row.risk_id,
                severity=severity,
                metadata={"gate": gate.to_dict()},
            )
        )
    return findings


def _risk_gate_findings(
    row: RiskEvidenceRow,
    obligation_by_id: Mapping[str, MaintenanceObligation],
    *,
    allow_scoped_confidence: bool,
) -> list[RiskEvidenceFinding]:
    findings: list[RiskEvidenceFinding] = []
    for gate in row.gates:
        if gate.kind == RISK_GATE_MAINTENANCE_OBLIGATION:
            findings.extend(
                _maintenance_gate_findings(
                    row,
                    gate,
                    obligation_by_id,
                    allow_scoped_confidence=allow_scoped_confidence,
                )
            )
        else:
            findings.extend(_generic_gate_findings(row, gate, allow_scoped_confidence=allow_scoped_confidence))
    for obligation_id in row.maintenance_obligation_ids:
        findings.extend(_maintenance_obligation_findings(row, obligation_id, obligation_by_id, allow_scoped_confidence))
    return findings


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

        findings.extend(
            _risk_gate_findings(
                row,
                obligation_by_id,
                allow_scoped_confidence=plan.allow_scoped_confidence,
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
    "RISK_GATE_ANALOGOUS_SCAN",
    "RISK_GATE_ARTIFACT_PAYLOAD",
    "RISK_GATE_DEFECT_FAMILY",
    "RISK_GATE_FAMILY",
    "RISK_GATE_MAINTENANCE_OBLIGATION",
    "RISK_GATE_MODEL_ANGLE_REVIEW",
    "RISK_GATE_MODEL_SPLIT",
    "RISK_GATE_PARENT_MODEL_EVIDENCE",
    "RISK_GATE_TEST_SPLIT",
    "RISK_GATE_TOPOLOGY_HAZARD",
    "RISK_GATE_UI_SOURCE_BASELINE_INTERACTION",
    "RISK_GATE_UI_DONE_CLAIM",
    "RISK_GATE_UI_FUNCTIONAL_CHAIN",
    "RISK_GATE_UI_HUMAN_OPERABILITY",
    "RISK_GATE_UI_IMPLEMENTATION",
    "RISK_GATE_UI_REAL_SURFACE",
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
    "RiskEvidenceGate",
    "RiskEvidenceFinding",
    "RiskEvidenceLedgerPlan",
    "RiskEvidenceLedgerReport",
    "RiskEvidenceProof",
    "RiskEvidenceRow",
    "review_risk_evidence_ledger",
]
