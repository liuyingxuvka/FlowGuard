"""Executable FlowGuard closure contract review.

This module coordinates existing FlowGuard evidence for broad done, release,
publish, or production-confidence claims. It does not replace the owning
review helpers; it checks whether their current evidence chain is complete
enough to support the final claim.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .core import FrozenMetadata, freeze_metadata
from .export import to_jsonable


CLOSURE_CONFIDENCE_FULL = "full"
CLOSURE_CONFIDENCE_SCOPED = "scoped"
CLOSURE_CONFIDENCE_BLOCKED = "blocked"

CLOSURE_DECISION_FULL = "flowguard_closure_full_confidence"
CLOSURE_DECISION_SCOPED = "flowguard_closure_scoped_confidence"
CLOSURE_DECISION_BLOCKED = "flowguard_closure_blocked"

CLOSURE_REPORT_RUNTIME_GATEWAY = "runtime_gateway_adoption"
CLOSURE_REPORT_RISK_LEDGER = "risk_evidence_ledger"
CLOSURE_REPORT_MODEL_FRESHNESS = "model_impact_freshness"
CLOSURE_REPORT_MODEL_MATURATION = "model_maturation"
CLOSURE_REPORT_MODEL_ANGLE = "model_angle_deliberation"
CLOSURE_REPORT_MODEL_TEST_ALIGNMENT = "model_test_alignment"
CLOSURE_REPORT_FIELD_LIFECYCLE = "field_lifecycle_mesh"
CLOSURE_REPORT_RUNTIME_PATH_ALIGNMENT = "runtime_path_alignment"
CLOSURE_REPORT_DEFECT_FAMILY = "defect_family_gate"
CLOSURE_REPORT_CONFORMANCE_REPLAY = "conformance_replay"
CLOSURE_REPORT_UI_SOURCE_BASELINE_ALIGNMENT = "ui_source_baseline_alignment"
CLOSURE_REPORT_UI_DONE_CLAIM = "ui_done_claim_review"
CLOSURE_REPORT_UI_HUMAN_OPERABILITY = "ui_human_operability_review"
CLOSURE_REPORT_UI_FUNCTIONAL_CAPABILITY_COVERAGE = "ui_functional_capability_coverage"

CLOSURE_REPORT_KINDS = (
    CLOSURE_REPORT_RUNTIME_GATEWAY,
    CLOSURE_REPORT_RISK_LEDGER,
    CLOSURE_REPORT_MODEL_FRESHNESS,
    CLOSURE_REPORT_MODEL_MATURATION,
    CLOSURE_REPORT_MODEL_ANGLE,
    CLOSURE_REPORT_MODEL_TEST_ALIGNMENT,
    CLOSURE_REPORT_FIELD_LIFECYCLE,
    CLOSURE_REPORT_RUNTIME_PATH_ALIGNMENT,
    CLOSURE_REPORT_DEFECT_FAMILY,
    CLOSURE_REPORT_CONFORMANCE_REPLAY,
    CLOSURE_REPORT_UI_SOURCE_BASELINE_ALIGNMENT,
    CLOSURE_REPORT_UI_DONE_CLAIM,
    CLOSURE_REPORT_UI_HUMAN_OPERABILITY,
    CLOSURE_REPORT_UI_FUNCTIONAL_CAPABILITY_COVERAGE,
)

CLOSURE_RESULT_PASSED = "passed"
CLOSURE_RESULT_FAILED = "failed"
CLOSURE_RESULT_STALE = "stale"
CLOSURE_RESULT_SKIPPED = "skipped"
CLOSURE_RESULT_NOT_RUN = "not_run"
CLOSURE_RESULT_RUNNING = "running"
CLOSURE_RESULT_PROGRESS_ONLY = "progress_only"
CLOSURE_RESULT_ERROR = "error"

CLOSURE_PASSING_RESULTS = (CLOSURE_RESULT_PASSED, "pass", "ok")

MODEL_QUALITY_HIDDEN_STATE = "hidden_state"
MODEL_QUALITY_MISSING_SIDE_EFFECT = "missing_side_effect"
MODEL_QUALITY_OWNER_AMBIGUITY = "owner_ambiguity"
MODEL_QUALITY_HELPER_ONLY_PROOF = "helper_only_proof"
MODEL_QUALITY_MISSING_PUBLIC_BOUNDARY = "missing_public_boundary"
MODEL_QUALITY_PARENT_CHILD_GAP = "parent_child_evidence_gap"

MODEL_QUALITY_SIGNAL_TYPES = (
    MODEL_QUALITY_HIDDEN_STATE,
    MODEL_QUALITY_MISSING_SIDE_EFFECT,
    MODEL_QUALITY_OWNER_AMBIGUITY,
    MODEL_QUALITY_HELPER_ONLY_PROOF,
    MODEL_QUALITY_MISSING_PUBLIC_BOUNDARY,
    MODEL_QUALITY_PARENT_CHILD_GAP,
)


def _as_tuple(values: Sequence[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,) if values else ()
    return tuple(str(value) for value in values if str(value))


def _metadata(metadata: Mapping[str, Any] | Sequence[tuple[str, Any]] | None) -> FrozenMetadata:
    return freeze_metadata(metadata)


def _result_status(value: str) -> str:
    return str(value or "").lower()


@dataclass(frozen=True)
class ClosureEvidenceReport:
    """Summary of an existing FlowGuard report consumed by closure review."""

    report_id: str
    report_kind: str
    decision: str = ""
    ok: bool = True
    current: bool = True
    confidence: str = CLOSURE_CONFIDENCE_FULL
    result_status: str = CLOSURE_RESULT_PASSED
    proof_artifact_ids: tuple[str, ...] = ()
    summary: str = ""
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        report_id = str(self.report_id)
        if not report_id:
            raise ValueError("report_id is required")
        report_kind = str(self.report_kind)
        if not report_kind:
            raise ValueError("report_kind is required")
        object.__setattr__(self, "report_id", report_id)
        object.__setattr__(self, "report_kind", report_kind)
        object.__setattr__(self, "decision", str(self.decision or ""))
        object.__setattr__(self, "ok", bool(self.ok))
        object.__setattr__(self, "current", bool(self.current))
        object.__setattr__(self, "confidence", str(self.confidence or CLOSURE_CONFIDENCE_BLOCKED))
        object.__setattr__(self, "result_status", _result_status(self.result_status))
        object.__setattr__(self, "proof_artifact_ids", _as_tuple(self.proof_artifact_ids))
        object.__setattr__(self, "summary", str(self.summary or ""))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def supports_full_confidence(self) -> bool:
        return (
            self.ok
            and self.current
            and self.result_status in CLOSURE_PASSING_RESULTS
            and self.confidence == CLOSURE_CONFIDENCE_FULL
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "report_kind": self.report_kind,
            "decision": self.decision,
            "ok": self.ok,
            "current": self.current,
            "confidence": self.confidence,
            "result_status": self.result_status,
            "proof_artifact_ids": list(self.proof_artifact_ids),
            "summary": self.summary,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class RuntimeTraceMapping:
    """Runtime trace evidence mapped back to a model obligation."""

    trace_id: str
    model_obligation_id: str = ""
    source_evidence_id: str = ""
    current: bool = True
    result_status: str = CLOSURE_RESULT_PASSED
    in_scope: bool = True
    required: bool = True
    out_of_scope_reason: str = ""
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        trace_id = str(self.trace_id)
        if not trace_id:
            raise ValueError("trace_id is required")
        object.__setattr__(self, "trace_id", trace_id)
        object.__setattr__(self, "model_obligation_id", str(self.model_obligation_id or ""))
        object.__setattr__(self, "source_evidence_id", str(self.source_evidence_id or ""))
        object.__setattr__(self, "current", bool(self.current))
        object.__setattr__(self, "result_status", _result_status(self.result_status))
        object.__setattr__(self, "in_scope", bool(self.in_scope))
        object.__setattr__(self, "required", bool(self.required))
        object.__setattr__(self, "out_of_scope_reason", str(self.out_of_scope_reason or ""))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "model_obligation_id": self.model_obligation_id,
            "source_evidence_id": self.source_evidence_id,
            "current": self.current,
            "result_status": self.result_status,
            "in_scope": self.in_scope,
            "required": self.required,
            "out_of_scope_reason": self.out_of_scope_reason,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class ArtifactInvalidation:
    """Artifact change that may invalidate dependent FlowGuard evidence."""

    artifact_id: str
    changed: bool = True
    dependent_evidence_ids: tuple[str, ...] = ()
    revalidation_evidence_ids: tuple[str, ...] = ()
    current: bool = True
    result_status: str = CLOSURE_RESULT_PASSED
    evidence_area: str = ""
    stale_evidence_ids: tuple[str, ...] = ()
    required: bool = True
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        artifact_id = str(self.artifact_id)
        if not artifact_id:
            raise ValueError("artifact_id is required")
        object.__setattr__(self, "artifact_id", artifact_id)
        object.__setattr__(self, "changed", bool(self.changed))
        object.__setattr__(self, "dependent_evidence_ids", _as_tuple(self.dependent_evidence_ids))
        object.__setattr__(self, "revalidation_evidence_ids", _as_tuple(self.revalidation_evidence_ids))
        object.__setattr__(self, "current", bool(self.current))
        object.__setattr__(self, "result_status", _result_status(self.result_status))
        object.__setattr__(self, "evidence_area", str(self.evidence_area or ""))
        object.__setattr__(self, "stale_evidence_ids", _as_tuple(self.stale_evidence_ids))
        object.__setattr__(self, "required", bool(self.required))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "changed": self.changed,
            "dependent_evidence_ids": list(self.dependent_evidence_ids),
            "revalidation_evidence_ids": list(self.revalidation_evidence_ids),
            "current": self.current,
            "result_status": self.result_status,
            "evidence_area": self.evidence_area,
            "stale_evidence_ids": list(self.stale_evidence_ids),
            "required": self.required,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class ModelQualitySignal:
    """Model quality signal that can limit or block full confidence."""

    signal_id: str
    signal_type: str
    model_id: str = ""
    description: str = ""
    resolved: bool = False
    current: bool = True
    in_scope: bool = True
    required: bool = True
    resolution_evidence_ids: tuple[str, ...] = ()
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        signal_id = str(self.signal_id)
        if not signal_id:
            raise ValueError("signal_id is required")
        object.__setattr__(self, "signal_id", signal_id)
        object.__setattr__(self, "signal_type", str(self.signal_type or ""))
        object.__setattr__(self, "model_id", str(self.model_id or ""))
        object.__setattr__(self, "description", str(self.description or ""))
        object.__setattr__(self, "resolved", bool(self.resolved))
        object.__setattr__(self, "current", bool(self.current))
        object.__setattr__(self, "in_scope", bool(self.in_scope))
        object.__setattr__(self, "required", bool(self.required))
        object.__setattr__(self, "resolution_evidence_ids", _as_tuple(self.resolution_evidence_ids))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "signal_type": self.signal_type,
            "model_id": self.model_id,
            "description": self.description,
            "resolved": self.resolved,
            "current": self.current,
            "in_scope": self.in_scope,
            "required": self.required,
            "resolution_evidence_ids": list(self.resolution_evidence_ids),
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class SameClassMissClosure:
    """Observed model miss and same-class closure evidence."""

    miss_id: str
    observed_failure_evidence_id: str = ""
    same_class_proof_evidence_id: str = ""
    model_obligation_id: str = ""
    defect_family_id: str = ""
    current: bool = True
    result_status: str = CLOSURE_RESULT_PASSED
    in_scope: bool = True
    required: bool = True
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        miss_id = str(self.miss_id)
        if not miss_id:
            raise ValueError("miss_id is required")
        object.__setattr__(self, "miss_id", miss_id)
        object.__setattr__(self, "observed_failure_evidence_id", str(self.observed_failure_evidence_id or ""))
        object.__setattr__(self, "same_class_proof_evidence_id", str(self.same_class_proof_evidence_id or ""))
        object.__setattr__(self, "model_obligation_id", str(self.model_obligation_id or ""))
        object.__setattr__(self, "defect_family_id", str(self.defect_family_id or ""))
        object.__setattr__(self, "current", bool(self.current))
        object.__setattr__(self, "result_status", _result_status(self.result_status))
        object.__setattr__(self, "in_scope", bool(self.in_scope))
        object.__setattr__(self, "required", bool(self.required))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "miss_id": self.miss_id,
            "observed_failure_evidence_id": self.observed_failure_evidence_id,
            "same_class_proof_evidence_id": self.same_class_proof_evidence_id,
            "model_obligation_id": self.model_obligation_id,
            "defect_family_id": self.defect_family_id,
            "current": self.current,
            "result_status": self.result_status,
            "in_scope": self.in_scope,
            "required": self.required,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class RuntimeGatewayInventoryClosure:
    """Runtime gateway inventory support at the closure boundary."""

    closure_id: str
    inventory_source_evidence_ids: tuple[str, ...] = ()
    gateway_report_evidence_id: str = ""
    current: bool = True
    result_status: str = CLOSURE_RESULT_PASSED
    unresolved_path_owner_conflicts: tuple[str, ...] = ()
    in_scope: bool = True
    required: bool = True
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        closure_id = str(self.closure_id)
        if not closure_id:
            raise ValueError("closure_id is required")
        object.__setattr__(self, "closure_id", closure_id)
        object.__setattr__(self, "inventory_source_evidence_ids", _as_tuple(self.inventory_source_evidence_ids))
        object.__setattr__(self, "gateway_report_evidence_id", str(self.gateway_report_evidence_id or ""))
        object.__setattr__(self, "current", bool(self.current))
        object.__setattr__(self, "result_status", _result_status(self.result_status))
        object.__setattr__(
            self,
            "unresolved_path_owner_conflicts",
            _as_tuple(self.unresolved_path_owner_conflicts),
        )
        object.__setattr__(self, "in_scope", bool(self.in_scope))
        object.__setattr__(self, "required", bool(self.required))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "closure_id": self.closure_id,
            "inventory_source_evidence_ids": list(self.inventory_source_evidence_ids),
            "gateway_report_evidence_id": self.gateway_report_evidence_id,
            "current": self.current,
            "result_status": self.result_status,
            "unresolved_path_owner_conflicts": list(self.unresolved_path_owner_conflicts),
            "in_scope": self.in_scope,
            "required": self.required,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class FlowGuardClosureContractPlan:
    """Evidence package for a broad FlowGuard confidence claim."""

    claim_id: str
    claim_scope: str = "production_confidence"
    runtime_trace_mappings: tuple[RuntimeTraceMapping, ...] = ()
    artifact_invalidations: tuple[ArtifactInvalidation, ...] = ()
    model_quality_signals: tuple[ModelQualitySignal, ...] = ()
    same_class_miss_closures: tuple[SameClassMissClosure, ...] = ()
    runtime_gateway_closures: tuple[RuntimeGatewayInventoryClosure, ...] = ()
    field_lifecycle_reports: tuple[Any, ...] = ()
    model_angle_reports: tuple[Any, ...] = ()
    evidence_reports: tuple[ClosureEvidenceReport, ...] = ()
    require_runtime_trace_mapping: bool = True
    require_artifact_freshness: bool = True
    require_model_quality_review: bool = True
    require_same_class_miss_closure: bool = True
    require_runtime_gateway_closure: bool = True
    require_field_lifecycle: bool = False
    require_model_angle_review: bool = False
    require_runtime_path_alignment: bool = False
    require_risk_ledger: bool = True
    require_ui_source_baseline_alignment: bool = False
    require_ui_done_claim_review: bool = False
    require_ui_human_operability_review: bool = False
    require_ui_functional_capability_coverage: bool = False
    allow_scoped_confidence: bool = True
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        claim_id = str(self.claim_id)
        if not claim_id:
            raise ValueError("claim_id is required")
        object.__setattr__(self, "claim_id", claim_id)
        object.__setattr__(self, "claim_scope", str(self.claim_scope or ""))
        object.__setattr__(self, "runtime_trace_mappings", tuple(self.runtime_trace_mappings))
        object.__setattr__(self, "artifact_invalidations", tuple(self.artifact_invalidations))
        object.__setattr__(self, "model_quality_signals", tuple(self.model_quality_signals))
        object.__setattr__(self, "same_class_miss_closures", tuple(self.same_class_miss_closures))
        object.__setattr__(self, "runtime_gateway_closures", tuple(self.runtime_gateway_closures))
        object.__setattr__(self, "field_lifecycle_reports", tuple(self.field_lifecycle_reports))
        object.__setattr__(self, "model_angle_reports", tuple(self.model_angle_reports))
        object.__setattr__(self, "evidence_reports", tuple(self.evidence_reports))
        object.__setattr__(self, "require_runtime_trace_mapping", bool(self.require_runtime_trace_mapping))
        object.__setattr__(self, "require_artifact_freshness", bool(self.require_artifact_freshness))
        object.__setattr__(self, "require_model_quality_review", bool(self.require_model_quality_review))
        object.__setattr__(self, "require_same_class_miss_closure", bool(self.require_same_class_miss_closure))
        object.__setattr__(self, "require_runtime_gateway_closure", bool(self.require_runtime_gateway_closure))
        object.__setattr__(self, "require_field_lifecycle", bool(self.require_field_lifecycle))
        object.__setattr__(self, "require_model_angle_review", bool(self.require_model_angle_review))
        object.__setattr__(self, "require_runtime_path_alignment", bool(self.require_runtime_path_alignment))
        object.__setattr__(self, "require_risk_ledger", bool(self.require_risk_ledger))
        object.__setattr__(
            self,
            "require_ui_source_baseline_alignment",
            bool(self.require_ui_source_baseline_alignment),
        )
        object.__setattr__(self, "require_ui_done_claim_review", bool(self.require_ui_done_claim_review))
        object.__setattr__(
            self,
            "require_ui_human_operability_review",
            bool(self.require_ui_human_operability_review),
        )
        object.__setattr__(
            self,
            "require_ui_functional_capability_coverage",
            bool(self.require_ui_functional_capability_coverage),
        )
        object.__setattr__(self, "allow_scoped_confidence", bool(self.allow_scoped_confidence))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_scope": self.claim_scope,
            "runtime_trace_mappings": [item.to_dict() for item in self.runtime_trace_mappings],
            "artifact_invalidations": [item.to_dict() for item in self.artifact_invalidations],
            "model_quality_signals": [item.to_dict() for item in self.model_quality_signals],
            "same_class_miss_closures": [item.to_dict() for item in self.same_class_miss_closures],
            "runtime_gateway_closures": [item.to_dict() for item in self.runtime_gateway_closures],
            "field_lifecycle_reports": [_to_dict_or_value(item) for item in self.field_lifecycle_reports],
            "model_angle_reports": [_to_dict_or_value(item) for item in self.model_angle_reports],
            "evidence_reports": [item.to_dict() for item in self.evidence_reports],
            "require_runtime_trace_mapping": self.require_runtime_trace_mapping,
            "require_artifact_freshness": self.require_artifact_freshness,
            "require_model_quality_review": self.require_model_quality_review,
            "require_same_class_miss_closure": self.require_same_class_miss_closure,
            "require_runtime_gateway_closure": self.require_runtime_gateway_closure,
            "require_field_lifecycle": self.require_field_lifecycle,
            "require_model_angle_review": self.require_model_angle_review,
            "require_runtime_path_alignment": self.require_runtime_path_alignment,
            "require_risk_ledger": self.require_risk_ledger,
            "require_ui_source_baseline_alignment": self.require_ui_source_baseline_alignment,
            "require_ui_done_claim_review": self.require_ui_done_claim_review,
            "require_ui_human_operability_review": self.require_ui_human_operability_review,
            "require_ui_functional_capability_coverage": self.require_ui_functional_capability_coverage,
            "allow_scoped_confidence": self.allow_scoped_confidence,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class FlowGuardClosureFinding:
    """One closure contract gap."""

    code: str
    message: str
    severity: str = "blocker"
    evidence_id: str = ""
    model_obligation_id: str = ""
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        severity = str(self.severity or "blocker").lower()
        if severity not in ("blocker", "warning"):
            raise ValueError("severity must be 'blocker' or 'warning'")
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "evidence_id", str(self.evidence_id or ""))
        object.__setattr__(self, "model_obligation_id", str(self.model_obligation_id or ""))
        object.__setattr__(self, "metadata", _metadata(self.metadata))

    @property
    def blocks_full_confidence(self) -> bool:
        return self.severity == "blocker"

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "evidence_id": self.evidence_id,
            "model_obligation_id": self.model_obligation_id,
            "blocks_full_confidence": self.blocks_full_confidence,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class FlowGuardClosureContractReport:
    """Structured closure contract result."""

    plan: FlowGuardClosureContractPlan
    findings: tuple[FlowGuardClosureFinding, ...] = ()
    decision: str = ""
    confidence: str = ""
    summary: str = ""

    def __post_init__(self) -> None:
        findings = tuple(self.findings)
        object.__setattr__(self, "findings", findings)
        if not self.decision or not self.confidence:
            decision, confidence = _decision_for(self.plan, findings)
            object.__setattr__(self, "decision", self.decision or decision)
            object.__setattr__(self, "confidence", self.confidence or confidence)
        if not self.summary:
            object.__setattr__(self, "summary", _summary(self.plan, findings, self.decision))

    @property
    def ok(self) -> bool:
        return self.decision != CLOSURE_DECISION_BLOCKED

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard closure contract ===",
            f"claim: {self.plan.claim_id}",
            f"scope: {self.plan.claim_scope}",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"decision: {self.decision}",
            f"confidence: {self.confidence}",
            self.summary,
        ]
        for finding in self.findings[:max_findings]:
            lines.append(f"- {finding.severity.upper()} {finding.code}: {finding.message}")
        if len(self.findings) > max_findings:
            lines.append(f"- ... {len(self.findings) - max_findings} more")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_closure_contract_report",
            "ok": self.ok,
            "decision": self.decision,
            "confidence": self.confidence,
            "summary": self.summary,
            "plan": self.plan.to_dict(),
            "findings": [finding.to_dict() for finding in self.findings],
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def review_flowguard_closure_contract(
    plan: FlowGuardClosureContractPlan,
) -> FlowGuardClosureContractReport:
    """Review whether current FlowGuard evidence supports a broad claim."""

    if not isinstance(plan, FlowGuardClosureContractPlan):
        plan = FlowGuardClosureContractPlan(**plan)

    findings: list[FlowGuardClosureFinding] = []
    reports_by_kind: dict[str, list[ClosureEvidenceReport]] = {}
    reports_by_id: dict[str, ClosureEvidenceReport] = {}
    for report in plan.evidence_reports:
        reports_by_kind.setdefault(report.report_kind, []).append(report)
        reports_by_id[report.report_id] = report
        if not report.current:
            findings.append(_finding("closure_report_stale", "closure report is not current", report.report_id, report.to_dict()))
        if report.result_status not in CLOSURE_PASSING_RESULTS:
            findings.append(_finding("closure_report_not_passing", "closure report is not passing", report.report_id, report.to_dict()))
        if not report.ok:
            findings.append(_finding("closure_report_blocked", "closure report is blocked", report.report_id, report.to_dict()))
        if report.confidence != CLOSURE_CONFIDENCE_FULL:
            severity = "warning" if plan.allow_scoped_confidence and report.confidence == CLOSURE_CONFIDENCE_SCOPED else "blocker"
            findings.append(
                _finding(
                    "closure_report_not_full_confidence",
                    "closure report does not support full confidence",
                    report.report_id,
                    report.to_dict(),
                    severity=severity,
                )
            )

    if plan.require_runtime_trace_mapping and not plan.runtime_trace_mappings:
        findings.append(_finding("missing_runtime_trace_mapping", "no runtime trace mapping evidence was supplied"))
    for trace in plan.runtime_trace_mappings:
        findings.extend(_review_trace_mapping(trace, plan.allow_scoped_confidence))

    if plan.require_artifact_freshness and not plan.artifact_invalidations:
        findings.append(_finding("missing_artifact_freshness_evidence", "no artifact invalidation/freshness evidence was supplied"))
    for invalidation in plan.artifact_invalidations:
        findings.extend(_review_artifact_invalidation(invalidation))

    if plan.require_model_quality_review and not plan.model_quality_signals:
        findings.append(_finding("missing_model_quality_review", "no model-quality review evidence was supplied"))
    for signal in plan.model_quality_signals:
        findings.extend(_review_model_quality_signal(signal, plan.allow_scoped_confidence))

    if plan.require_same_class_miss_closure and not plan.same_class_miss_closures:
        findings.append(_finding("missing_same_class_miss_review", "no same-class model-miss closure evidence was supplied"))
    for closure in plan.same_class_miss_closures:
        findings.extend(_review_same_class_miss(closure, plan.allow_scoped_confidence))

    if plan.require_runtime_gateway_closure and not plan.runtime_gateway_closures:
        findings.append(_finding("missing_runtime_gateway_closure", "no runtime gateway inventory closure evidence was supplied"))
    for gateway_closure in plan.runtime_gateway_closures:
        findings.extend(_review_gateway_closure(gateway_closure, reports_by_id, plan.allow_scoped_confidence))

    field_lifecycle_evidence_reports = reports_by_kind.get(CLOSURE_REPORT_FIELD_LIFECYCLE, [])
    if plan.require_field_lifecycle and not plan.field_lifecycle_reports and not field_lifecycle_evidence_reports:
        findings.append(_finding("missing_field_lifecycle_evidence", "no Field Lifecycle Mesh report was supplied"))
    for field_report in plan.field_lifecycle_reports:
        findings.extend(_review_field_lifecycle_report(field_report, plan.allow_scoped_confidence))
    if field_lifecycle_evidence_reports and not any(report.supports_full_confidence() for report in field_lifecycle_evidence_reports):
        severity = "warning" if plan.allow_scoped_confidence else "blocker"
        findings.append(
            _finding(
                "field_lifecycle_evidence_not_full_confidence",
                "Field Lifecycle Mesh evidence does not support full confidence",
                field_lifecycle_evidence_reports[0].report_id,
                {"field_lifecycle_reports": [report.to_dict() for report in field_lifecycle_evidence_reports]},
                severity=severity,
            )
        )

    model_angle_evidence_reports = reports_by_kind.get(CLOSURE_REPORT_MODEL_ANGLE, [])
    if plan.require_model_angle_review and not plan.model_angle_reports and not model_angle_evidence_reports:
        findings.append(_finding("missing_model_angle_review", "no model-angle deliberation report was supplied"))
    for model_angle_report in plan.model_angle_reports:
        findings.extend(_review_model_angle_report(model_angle_report, plan.allow_scoped_confidence))
    if model_angle_evidence_reports and not any(report.supports_full_confidence() for report in model_angle_evidence_reports):
        severity = "warning" if plan.allow_scoped_confidence else "blocker"
        findings.append(
            _finding(
                "model_angle_evidence_not_full_confidence",
                "model-angle deliberation evidence does not support full confidence",
                model_angle_evidence_reports[0].report_id,
                {"model_angle_reports": [report.to_dict() for report in model_angle_evidence_reports]},
                severity=severity,
            )
        )

    if plan.require_runtime_path_alignment:
        runtime_path_reports = reports_by_kind.get(CLOSURE_REPORT_RUNTIME_PATH_ALIGNMENT, [])
        if not runtime_path_reports:
            findings.append(_finding("missing_runtime_path_alignment", "no Runtime Path Alignment report was supplied"))
        elif not any(report.supports_full_confidence() for report in runtime_path_reports):
            severity = "warning" if plan.allow_scoped_confidence else "blocker"
            findings.append(
                _finding(
                    "runtime_path_alignment_not_full_confidence",
                    "Runtime Path Alignment does not support full confidence",
                    runtime_path_reports[0].report_id,
                    {"runtime_path_reports": [report.to_dict() for report in runtime_path_reports]},
                    severity=severity,
                )
            )

    if plan.require_risk_ledger:
        risk_reports = reports_by_kind.get(CLOSURE_REPORT_RISK_LEDGER, [])
        if not risk_reports:
            findings.append(_finding("missing_risk_evidence_ledger", "no Risk Evidence Ledger report was supplied"))
        elif not any(report.supports_full_confidence() for report in risk_reports):
            severity = "warning" if plan.allow_scoped_confidence else "blocker"
            findings.append(
                _finding(
                    "risk_ledger_not_full_confidence",
                    "Risk Evidence Ledger does not support full confidence",
                    risk_reports[0].report_id,
                    {"risk_reports": [report.to_dict() for report in risk_reports]},
                    severity=severity,
                )
            )

    if plan.require_ui_source_baseline_alignment:
        ui_source_reports = reports_by_kind.get(CLOSURE_REPORT_UI_SOURCE_BASELINE_ALIGNMENT, [])
        if not ui_source_reports:
            findings.append(
                _finding(
                    "missing_ui_source_baseline_alignment",
                    "no UI source-baseline alignment report was supplied",
                )
            )
        elif not any(report.supports_full_confidence() for report in ui_source_reports):
            severity = "warning" if plan.allow_scoped_confidence else "blocker"
            findings.append(
                _finding(
                    "ui_source_baseline_alignment_not_full_confidence",
                    "UI source-baseline alignment does not support full confidence",
                    ui_source_reports[0].report_id,
                    {"ui_source_baseline_alignment_reports": [report.to_dict() for report in ui_source_reports]},
                    severity=severity,
                )
            )

    if plan.require_ui_done_claim_review:
        ui_done_reports = reports_by_kind.get(CLOSURE_REPORT_UI_DONE_CLAIM, [])
        if not ui_done_reports:
            findings.append(
                _finding(
                    "missing_ui_done_claim_review",
                    "no UI Done Claim review report was supplied",
                )
            )
        elif not any(report.supports_full_confidence() for report in ui_done_reports):
            severity = "warning" if plan.allow_scoped_confidence else "blocker"
            findings.append(
                _finding(
                    "ui_done_claim_review_not_full_confidence",
                    "UI Done Claim review does not support full confidence",
                    ui_done_reports[0].report_id,
                    {"ui_done_claim_reports": [report.to_dict() for report in ui_done_reports]},
                    severity=severity,
                )
            )

    if plan.require_ui_human_operability_review:
        ui_human_reports = reports_by_kind.get(CLOSURE_REPORT_UI_HUMAN_OPERABILITY, [])
        if not ui_human_reports:
            findings.append(
                _finding(
                    "missing_ui_human_operability_review",
                    "no UI human-operability review report was supplied",
                )
            )
        elif not any(report.supports_full_confidence() for report in ui_human_reports):
            severity = "warning" if plan.allow_scoped_confidence else "blocker"
            findings.append(
                _finding(
                    "ui_human_operability_review_not_full_confidence",
                    "UI human-operability review does not support full confidence",
                    ui_human_reports[0].report_id,
                    {"ui_human_operability_reports": [report.to_dict() for report in ui_human_reports]},
                    severity=severity,
                )
            )

    if plan.require_ui_functional_capability_coverage:
        ui_capability_reports = reports_by_kind.get(CLOSURE_REPORT_UI_FUNCTIONAL_CAPABILITY_COVERAGE, [])
        if not ui_capability_reports:
            findings.append(
                _finding(
                    "missing_ui_functional_capability_coverage",
                    "no UI functional capability coverage report was supplied",
                )
            )
        elif not any(report.supports_full_confidence() for report in ui_capability_reports):
            severity = "warning" if plan.allow_scoped_confidence else "blocker"
            findings.append(
                _finding(
                    "ui_functional_capability_coverage_not_full_confidence",
                    "UI functional capability coverage does not support full confidence",
                    ui_capability_reports[0].report_id,
                    {"ui_functional_capability_coverage_reports": [report.to_dict() for report in ui_capability_reports]},
                    severity=severity,
                )
            )

    return FlowGuardClosureContractReport(plan=plan, findings=tuple(findings))


def _finding(
    code: str,
    message: str,
    evidence_id: str = "",
    metadata: Mapping[str, Any] | None = None,
    *,
    severity: str = "blocker",
    model_obligation_id: str = "",
) -> FlowGuardClosureFinding:
    return FlowGuardClosureFinding(
        code=code,
        message=message,
        severity=severity,
        evidence_id=evidence_id,
        model_obligation_id=model_obligation_id,
        metadata=metadata or {},
    )


def _review_trace_mapping(
    trace: RuntimeTraceMapping,
    allow_scoped: bool,
) -> tuple[FlowGuardClosureFinding, ...]:
    findings: list[FlowGuardClosureFinding] = []
    if not trace.in_scope:
        severity = "warning" if allow_scoped and trace.out_of_scope_reason else "blocker"
        findings.append(_finding("runtime_trace_scoped_out", trace.out_of_scope_reason or "runtime trace was scoped out without a reason", trace.trace_id, trace.to_dict(), severity=severity))
        return tuple(findings)
    if not trace.current:
        findings.append(_finding("runtime_trace_mapping_stale", "runtime trace mapping is not current", trace.trace_id, trace.to_dict()))
    if trace.result_status not in CLOSURE_PASSING_RESULTS:
        findings.append(_finding("runtime_trace_mapping_not_passing", "runtime trace mapping is not passing", trace.trace_id, trace.to_dict()))
    if trace.required and not trace.model_obligation_id:
        findings.append(_finding("runtime_trace_unmapped_model_obligation", "in-scope runtime trace does not map to a model obligation", trace.trace_id, trace.to_dict()))
    return tuple(findings)


def _review_artifact_invalidation(
    invalidation: ArtifactInvalidation,
) -> tuple[FlowGuardClosureFinding, ...]:
    if not invalidation.changed:
        return ()
    findings: list[FlowGuardClosureFinding] = []
    if invalidation.required and not invalidation.dependent_evidence_ids:
        findings.append(_finding("artifact_change_missing_dependent_evidence", "changed artifact does not name dependent evidence", invalidation.artifact_id, invalidation.to_dict()))
    if invalidation.required and not invalidation.revalidation_evidence_ids:
        findings.append(_finding("artifact_change_missing_revalidation", "changed artifact does not have revalidation evidence", invalidation.artifact_id, invalidation.to_dict()))
    if not invalidation.current:
        findings.append(_finding("artifact_revalidation_stale", "artifact revalidation evidence is not current", invalidation.artifact_id, invalidation.to_dict()))
    if invalidation.result_status not in CLOSURE_PASSING_RESULTS:
        findings.append(_finding("artifact_revalidation_not_passing", "artifact revalidation evidence is not passing", invalidation.artifact_id, invalidation.to_dict()))
    if invalidation.stale_evidence_ids:
        findings.append(_finding("artifact_change_stales_evidence", "changed artifact still lists stale dependent evidence", invalidation.artifact_id, invalidation.to_dict()))
    return tuple(findings)


def _review_model_quality_signal(
    signal: ModelQualitySignal,
    allow_scoped: bool,
) -> tuple[FlowGuardClosureFinding, ...]:
    findings: list[FlowGuardClosureFinding] = []
    if not signal.in_scope:
        severity = "warning" if allow_scoped else "blocker"
        findings.append(_finding("model_quality_signal_scoped_out", "model-quality signal is out of scope", signal.signal_id, signal.to_dict(), severity=severity))
        return tuple(findings)
    if not signal.current:
        findings.append(_finding("model_quality_signal_stale", "model-quality signal is not current", signal.signal_id, signal.to_dict()))
    if signal.signal_type not in MODEL_QUALITY_SIGNAL_TYPES:
        findings.append(_finding("unknown_model_quality_signal", "model-quality signal type is unknown", signal.signal_id, signal.to_dict()))
    if signal.required and not signal.resolved:
        findings.append(_finding("model_quality_gap_open", "required model-quality gap remains unresolved", signal.signal_id, signal.to_dict()))
    if signal.resolved and not signal.resolution_evidence_ids:
        findings.append(_finding("model_quality_resolution_missing_evidence", "resolved model-quality signal lacks resolution evidence", signal.signal_id, signal.to_dict()))
    return tuple(findings)


def _review_same_class_miss(
    closure: SameClassMissClosure,
    allow_scoped: bool,
) -> tuple[FlowGuardClosureFinding, ...]:
    findings: list[FlowGuardClosureFinding] = []
    if not closure.in_scope:
        severity = "warning" if allow_scoped else "blocker"
        findings.append(_finding("same_class_miss_scoped_out", "same-class model miss closure is out of scope", closure.miss_id, closure.to_dict(), severity=severity))
        return tuple(findings)
    if not closure.current:
        findings.append(_finding("same_class_miss_closure_stale", "same-class model miss closure is not current", closure.miss_id, closure.to_dict()))
    if closure.result_status not in CLOSURE_PASSING_RESULTS:
        findings.append(_finding("same_class_miss_closure_not_passing", "same-class model miss closure is not passing", closure.miss_id, closure.to_dict()))
    if closure.required and not closure.observed_failure_evidence_id:
        findings.append(_finding("missing_observed_failure_evidence", "model miss closure lacks observed failure evidence", closure.miss_id, closure.to_dict()))
    if closure.required and not closure.same_class_proof_evidence_id:
        findings.append(_finding("missing_same_class_proof_evidence", "model miss closure lacks same-class proof evidence", closure.miss_id, closure.to_dict()))
    return tuple(findings)


def _review_gateway_closure(
    gateway_closure: RuntimeGatewayInventoryClosure,
    reports_by_id: Mapping[str, ClosureEvidenceReport],
    allow_scoped: bool,
) -> tuple[FlowGuardClosureFinding, ...]:
    findings: list[FlowGuardClosureFinding] = []
    if not gateway_closure.in_scope:
        severity = "warning" if allow_scoped else "blocker"
        findings.append(_finding("runtime_gateway_scoped_out", "runtime gateway closure is out of scope", gateway_closure.closure_id, gateway_closure.to_dict(), severity=severity))
        return tuple(findings)
    if not gateway_closure.current:
        findings.append(_finding("runtime_gateway_closure_stale", "runtime gateway closure is not current", gateway_closure.closure_id, gateway_closure.to_dict()))
    if gateway_closure.result_status not in CLOSURE_PASSING_RESULTS:
        findings.append(_finding("runtime_gateway_closure_not_passing", "runtime gateway closure is not passing", gateway_closure.closure_id, gateway_closure.to_dict()))
    if gateway_closure.required and not gateway_closure.inventory_source_evidence_ids:
        findings.append(_finding("missing_runtime_gateway_inventory_source", "runtime gateway closure lacks writer inventory source evidence", gateway_closure.closure_id, gateway_closure.to_dict()))
    if gateway_closure.required and not gateway_closure.gateway_report_evidence_id:
        findings.append(_finding("missing_runtime_gateway_report", "runtime gateway closure lacks gateway adoption report evidence", gateway_closure.closure_id, gateway_closure.to_dict()))
    report = reports_by_id.get(gateway_closure.gateway_report_evidence_id)
    if gateway_closure.gateway_report_evidence_id and report is None:
        findings.append(_finding("unknown_runtime_gateway_report", "runtime gateway closure references unknown report evidence", gateway_closure.closure_id, gateway_closure.to_dict()))
    elif report is not None and not report.supports_full_confidence():
        findings.append(_finding("runtime_gateway_report_not_full_confidence", "runtime gateway report does not support full confidence", report.report_id, report.to_dict()))
    if gateway_closure.unresolved_path_owner_conflicts:
        findings.append(_finding("runtime_gateway_path_owner_conflict", "runtime gateway path-owner conflicts remain unresolved", gateway_closure.closure_id, gateway_closure.to_dict()))
    return tuple(findings)


def _decision_for(
    plan: FlowGuardClosureContractPlan,
    findings: tuple[FlowGuardClosureFinding, ...],
) -> tuple[str, str]:
    blockers = [finding for finding in findings if finding.blocks_full_confidence]
    if blockers:
        return CLOSURE_DECISION_BLOCKED, CLOSURE_CONFIDENCE_BLOCKED
    if findings:
        if not plan.allow_scoped_confidence:
            return CLOSURE_DECISION_BLOCKED, CLOSURE_CONFIDENCE_BLOCKED
        return CLOSURE_DECISION_SCOPED, CLOSURE_CONFIDENCE_SCOPED
    return CLOSURE_DECISION_FULL, CLOSURE_CONFIDENCE_FULL


def _summary(
    plan: FlowGuardClosureContractPlan,
    findings: tuple[FlowGuardClosureFinding, ...],
    decision: str,
) -> str:
    blockers = sum(1 for finding in findings if finding.blocks_full_confidence)
    warnings = len(findings) - blockers
    return (
        f"{decision}: traces={len(plan.runtime_trace_mappings)} "
        f"invalidations={len(plan.artifact_invalidations)} "
        f"quality_signals={len(plan.model_quality_signals)} "
        f"misses={len(plan.same_class_miss_closures)} "
        f"gateways={len(plan.runtime_gateway_closures)} "
        f"field_lifecycle={len(plan.field_lifecycle_reports)} "
        f"model_angle={len(plan.model_angle_reports)} "
        f"reports={len(plan.evidence_reports)} "
        f"blockers={blockers} warnings={warnings}"
    )


def _to_dict_or_value(value: Any) -> Any:
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return to_jsonable(value)


def _review_field_lifecycle_report(
    report: Any,
    allow_scoped: bool,
) -> tuple[FlowGuardClosureFinding, ...]:
    findings: list[FlowGuardClosureFinding] = []
    report_id = str(getattr(report, "mesh_id", "") or getattr(report, "report_id", "") or "")
    metadata = _to_dict_or_value(report)
    ok = bool(getattr(report, "ok", False))
    confidence = str(getattr(report, "confidence", "") or "")
    decision = str(getattr(report, "decision", "") or "")
    if not ok:
        findings.append(
            _finding(
                "field_lifecycle_report_blocked",
                "Field Lifecycle Mesh report is blocked",
                report_id,
                metadata,
            )
        )
    if confidence != CLOSURE_CONFIDENCE_FULL:
        severity = "warning" if allow_scoped and confidence == CLOSURE_CONFIDENCE_SCOPED else "blocker"
        findings.append(
            _finding(
                "field_lifecycle_not_full_confidence",
                "Field Lifecycle Mesh report does not support full confidence",
                report_id,
                metadata,
                severity=severity,
            )
        )
    if not decision:
        findings.append(
            _finding(
                "field_lifecycle_missing_decision",
                "Field Lifecycle Mesh report lacks a decision",
                report_id,
                metadata,
            )
        )
    return tuple(findings)


def _review_model_angle_report(
    report: Any,
    allow_scoped: bool,
) -> tuple[FlowGuardClosureFinding, ...]:
    findings: list[FlowGuardClosureFinding] = []
    report_id = str(getattr(report, "review_id", "") or getattr(report, "report_id", "") or "")
    metadata = _to_dict_or_value(report)
    ok = bool(getattr(report, "ok", False))
    confidence = str(getattr(report, "confidence", "") or "")
    decision = str(getattr(report, "decision", "") or "")
    unresolved = tuple(getattr(report, "unresolved_angle_ids", ()) or ())
    if not ok:
        findings.append(
            _finding(
                "model_angle_report_blocked",
                "model-angle deliberation report is blocked",
                report_id,
                metadata,
            )
        )
    if confidence != CLOSURE_CONFIDENCE_FULL:
        severity = "warning" if allow_scoped and confidence == CLOSURE_CONFIDENCE_SCOPED else "blocker"
        findings.append(
            _finding(
                "model_angle_not_full_confidence",
                "model-angle deliberation report does not support full confidence",
                report_id,
                metadata,
                severity=severity,
            )
        )
    if unresolved:
        findings.append(
            _finding(
                "model_angle_unresolved",
                "model-angle deliberation has unresolved required angles",
                report_id,
                metadata,
            )
        )
    if not decision:
        findings.append(
            _finding(
                "model_angle_missing_decision",
                "model-angle deliberation report lacks a decision",
                report_id,
                metadata,
            )
        )
    return tuple(findings)


__all__ = [
    "CLOSURE_CONFIDENCE_BLOCKED",
    "CLOSURE_CONFIDENCE_FULL",
    "CLOSURE_CONFIDENCE_SCOPED",
    "CLOSURE_DECISION_BLOCKED",
    "CLOSURE_DECISION_FULL",
    "CLOSURE_DECISION_SCOPED",
    "CLOSURE_PASSING_RESULTS",
    "CLOSURE_REPORT_CONFORMANCE_REPLAY",
    "CLOSURE_REPORT_DEFECT_FAMILY",
    "CLOSURE_REPORT_FIELD_LIFECYCLE",
    "CLOSURE_REPORT_KINDS",
    "CLOSURE_REPORT_MODEL_FRESHNESS",
    "CLOSURE_REPORT_MODEL_ANGLE",
    "CLOSURE_REPORT_MODEL_MATURATION",
    "CLOSURE_REPORT_MODEL_TEST_ALIGNMENT",
    "CLOSURE_REPORT_RUNTIME_PATH_ALIGNMENT",
    "CLOSURE_REPORT_RISK_LEDGER",
    "CLOSURE_REPORT_RUNTIME_GATEWAY",
    "CLOSURE_REPORT_UI_SOURCE_BASELINE_ALIGNMENT",
    "CLOSURE_REPORT_UI_DONE_CLAIM",
    "CLOSURE_REPORT_UI_HUMAN_OPERABILITY",
    "CLOSURE_REPORT_UI_FUNCTIONAL_CAPABILITY_COVERAGE",
    "CLOSURE_RESULT_ERROR",
    "CLOSURE_RESULT_FAILED",
    "CLOSURE_RESULT_NOT_RUN",
    "CLOSURE_RESULT_PASSED",
    "CLOSURE_RESULT_PROGRESS_ONLY",
    "CLOSURE_RESULT_RUNNING",
    "CLOSURE_RESULT_SKIPPED",
    "CLOSURE_RESULT_STALE",
    "MODEL_QUALITY_HELPER_ONLY_PROOF",
    "MODEL_QUALITY_HIDDEN_STATE",
    "MODEL_QUALITY_MISSING_PUBLIC_BOUNDARY",
    "MODEL_QUALITY_MISSING_SIDE_EFFECT",
    "MODEL_QUALITY_OWNER_AMBIGUITY",
    "MODEL_QUALITY_PARENT_CHILD_GAP",
    "MODEL_QUALITY_SIGNAL_TYPES",
    "ArtifactInvalidation",
    "ClosureEvidenceReport",
    "FlowGuardClosureContractPlan",
    "FlowGuardClosureContractReport",
    "FlowGuardClosureFinding",
    "ModelQualitySignal",
    "RuntimeGatewayInventoryClosure",
    "RuntimeTraceMapping",
    "SameClassMissClosure",
    "review_flowguard_closure_contract",
]
