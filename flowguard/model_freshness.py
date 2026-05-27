"""Model impact freshness gate for FlowGuard upgrades.

The helper reviews existing FlowGuard models after a framework, architecture,
or route upgrade. It does not blindly rerun every historical model. It requires
each model to be classified, requires current rerun evidence for affected
models, and requires an explicit reuse ticket for unchanged models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable


MODEL_IMPACT_AFFECTED = "affected"
MODEL_IMPACT_NOT_IMPACTED = "not_impacted"
MODEL_IMPACT_DEPRECATED = "deprecated"
MODEL_IMPACT_BLOCKED = "blocked"
MODEL_IMPACT_UNKNOWN = "unknown"

MODEL_IMPACT_CLASSIFICATIONS = (
    MODEL_IMPACT_AFFECTED,
    MODEL_IMPACT_NOT_IMPACTED,
    MODEL_IMPACT_DEPRECATED,
    MODEL_IMPACT_BLOCKED,
    MODEL_IMPACT_UNKNOWN,
)

MODEL_RERUN_STATUS_PASSED = "passed"
MODEL_RERUN_STATUS_FAILED = "failed"
MODEL_RERUN_STATUS_NOT_RUN = "not_run"
MODEL_RERUN_STATUS_STALE = "stale"
MODEL_RERUN_STATUS_RUNNING = "running"
MODEL_RERUN_STATUS_SKIPPED = "skipped"
MODEL_RERUN_STATUS_ERROR = "error"

PASSING_MODEL_RERUN_STATUSES = (MODEL_RERUN_STATUS_PASSED,)
NON_PASSING_MODEL_RERUN_STATUSES = (
    MODEL_RERUN_STATUS_FAILED,
    MODEL_RERUN_STATUS_NOT_RUN,
    MODEL_RERUN_STATUS_STALE,
    MODEL_RERUN_STATUS_RUNNING,
    MODEL_RERUN_STATUS_SKIPPED,
    MODEL_RERUN_STATUS_ERROR,
)

MODEL_FRESHNESS_DECISION_CURRENT = "model_impact_freshness_current"
MODEL_FRESHNESS_DECISION_AFFECTED_RERUN_REQUIRED = "affected_model_needs_rerun"
MODEL_FRESHNESS_DECISION_REUSE_INVALID = "reuse_ticket_invalid"
MODEL_FRESHNESS_DECISION_UNKNOWN = "unknown_model_impact"
MODEL_FRESHNESS_DECISION_DEPRECATED_INVALID = "deprecated_model_needs_replacement"
MODEL_FRESHNESS_DECISION_BLOCKED = "model_freshness_blocked"


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


def _intersection(left: Sequence[str], right: Sequence[str]) -> tuple[str, ...]:
    right_set = set(right)
    return tuple(value for value in left if value in right_set)


@dataclass(frozen=True)
class ModelFreshnessRecord:
    """One existing FlowGuard model in the upgrade inventory."""

    model_id: str
    model_path: str = ""
    dependency_artifact_ids: tuple[str, ...] = ()
    flowguard_semantic_ids: tuple[str, ...] = ()
    previous_evidence_id: str = ""
    last_verified_fingerprint: str = ""
    replacement_model_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "model_path", str(self.model_path))
        object.__setattr__(self, "dependency_artifact_ids", _as_tuple(self.dependency_artifact_ids))
        object.__setattr__(self, "flowguard_semantic_ids", _as_tuple(self.flowguard_semantic_ids))
        object.__setattr__(self, "previous_evidence_id", str(self.previous_evidence_id))
        object.__setattr__(self, "last_verified_fingerprint", str(self.last_verified_fingerprint))
        object.__setattr__(self, "replacement_model_id", str(self.replacement_model_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_path": self.model_path,
            "dependency_artifact_ids": list(self.dependency_artifact_ids),
            "flowguard_semantic_ids": list(self.flowguard_semantic_ids),
            "previous_evidence_id": self.previous_evidence_id,
            "last_verified_fingerprint": self.last_verified_fingerprint,
            "replacement_model_id": self.replacement_model_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class UpgradeImpact:
    """The upgrade surface that may invalidate existing model evidence."""

    upgrade_id: str = ""
    changed_artifact_ids: tuple[str, ...] = ()
    changed_flowguard_semantic_ids: tuple[str, ...] = ()
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "upgrade_id", str(self.upgrade_id))
        object.__setattr__(self, "changed_artifact_ids", _as_tuple(self.changed_artifact_ids))
        object.__setattr__(
            self,
            "changed_flowguard_semantic_ids",
            _as_tuple(self.changed_flowguard_semantic_ids),
        )
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "upgrade_id": self.upgrade_id,
            "changed_artifact_ids": list(self.changed_artifact_ids),
            "changed_flowguard_semantic_ids": list(self.changed_flowguard_semantic_ids),
            "description": self.description,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ModelImpactAssessment:
    """Human or tool classification for one model under the current upgrade."""

    model_id: str
    classification: str = MODEL_IMPACT_UNKNOWN
    rationale: str = ""
    impacted_artifact_ids: tuple[str, ...] = ()
    impacted_semantic_ids: tuple[str, ...] = ()
    replacement_model_id: str = ""
    blocked_reason: str = ""
    reviewer: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "classification", str(self.classification))
        object.__setattr__(self, "rationale", str(self.rationale))
        object.__setattr__(self, "impacted_artifact_ids", _as_tuple(self.impacted_artifact_ids))
        object.__setattr__(self, "impacted_semantic_ids", _as_tuple(self.impacted_semantic_ids))
        object.__setattr__(self, "replacement_model_id", str(self.replacement_model_id))
        object.__setattr__(self, "blocked_reason", str(self.blocked_reason))
        object.__setattr__(self, "reviewer", str(self.reviewer))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "classification": self.classification,
            "rationale": self.rationale,
            "impacted_artifact_ids": list(self.impacted_artifact_ids),
            "impacted_semantic_ids": list(self.impacted_semantic_ids),
            "replacement_model_id": self.replacement_model_id,
            "blocked_reason": self.blocked_reason,
            "reviewer": self.reviewer,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ModelReuseTicket:
    """Proof that an unchanged model may reuse previous evidence."""

    model_id: str
    reason: str = ""
    previous_evidence_id: str = ""
    same_output_proof_id: str = ""
    output_fingerprint: str = ""
    ticket_current: bool = True
    model_fingerprint_current: bool = True
    dependency_fingerprints_current: bool = True
    flowguard_semantics_current: bool = True
    previous_evidence_current: bool = True
    output_fingerprint_matches: bool = True
    checked_by: str = ""
    checked_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "reason", str(self.reason))
        object.__setattr__(self, "previous_evidence_id", str(self.previous_evidence_id))
        object.__setattr__(self, "same_output_proof_id", str(self.same_output_proof_id))
        object.__setattr__(self, "output_fingerprint", str(self.output_fingerprint))
        object.__setattr__(self, "ticket_current", bool(self.ticket_current))
        object.__setattr__(self, "model_fingerprint_current", bool(self.model_fingerprint_current))
        object.__setattr__(self, "dependency_fingerprints_current", bool(self.dependency_fingerprints_current))
        object.__setattr__(self, "flowguard_semantics_current", bool(self.flowguard_semantics_current))
        object.__setattr__(self, "previous_evidence_current", bool(self.previous_evidence_current))
        object.__setattr__(self, "output_fingerprint_matches", bool(self.output_fingerprint_matches))
        object.__setattr__(self, "checked_by", str(self.checked_by))
        object.__setattr__(self, "checked_at", str(self.checked_at))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "reason": self.reason,
            "previous_evidence_id": self.previous_evidence_id,
            "same_output_proof_id": self.same_output_proof_id,
            "output_fingerprint": self.output_fingerprint,
            "ticket_current": self.ticket_current,
            "model_fingerprint_current": self.model_fingerprint_current,
            "dependency_fingerprints_current": self.dependency_fingerprints_current,
            "flowguard_semantics_current": self.flowguard_semantics_current,
            "previous_evidence_current": self.previous_evidence_current,
            "output_fingerprint_matches": self.output_fingerprint_matches,
            "checked_by": self.checked_by,
            "checked_at": self.checked_at,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ModelRerunEvidence:
    """Current rerun and update-review evidence for an affected model."""

    model_id: str
    status: str = MODEL_RERUN_STATUS_NOT_RUN
    current: bool = False
    evidence_id: str = ""
    command: str = ""
    model_update_reviewed: bool = False
    model_updated: bool = False
    model_update_not_required_reason: str = ""
    test_update_reviewed: bool = False
    tests_updated: bool = False
    test_update_not_required_reason: str = ""
    output_changed: bool = False
    output_change_explanation: str = ""
    checked_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "status", str(self.status))
        object.__setattr__(self, "current", bool(self.current))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "command", str(self.command))
        object.__setattr__(self, "model_update_reviewed", bool(self.model_update_reviewed))
        object.__setattr__(self, "model_updated", bool(self.model_updated))
        object.__setattr__(self, "model_update_not_required_reason", str(self.model_update_not_required_reason))
        object.__setattr__(self, "test_update_reviewed", bool(self.test_update_reviewed))
        object.__setattr__(self, "tests_updated", bool(self.tests_updated))
        object.__setattr__(self, "test_update_not_required_reason", str(self.test_update_not_required_reason))
        object.__setattr__(self, "output_changed", bool(self.output_changed))
        object.__setattr__(self, "output_change_explanation", str(self.output_change_explanation))
        object.__setattr__(self, "checked_at", str(self.checked_at))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "status": self.status,
            "current": self.current,
            "evidence_id": self.evidence_id,
            "command": self.command,
            "model_update_reviewed": self.model_update_reviewed,
            "model_updated": self.model_updated,
            "model_update_not_required_reason": self.model_update_not_required_reason,
            "test_update_reviewed": self.test_update_reviewed,
            "tests_updated": self.tests_updated,
            "test_update_not_required_reason": self.test_update_not_required_reason,
            "output_changed": self.output_changed,
            "output_change_explanation": self.output_change_explanation,
            "checked_at": self.checked_at,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ModelImpactFreshnessPlan:
    """Inventory and evidence package for the model impact freshness gate."""

    plan_id: str
    records: tuple[ModelFreshnessRecord, ...] = ()
    impact: UpgradeImpact = field(default_factory=UpgradeImpact)
    assessments: tuple[ModelImpactAssessment, ...] = ()
    reuse_tickets: tuple[ModelReuseTicket, ...] = ()
    rerun_evidence: tuple[ModelRerunEvidence, ...] = ()
    require_explicit_classification: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "records", tuple(self.records))
        object.__setattr__(self, "assessments", tuple(self.assessments))
        object.__setattr__(self, "reuse_tickets", tuple(self.reuse_tickets))
        object.__setattr__(self, "rerun_evidence", tuple(self.rerun_evidence))
        object.__setattr__(self, "require_explicit_classification", bool(self.require_explicit_classification))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "records": [record.to_dict() for record in self.records],
            "impact": self.impact.to_dict(),
            "assessments": [assessment.to_dict() for assessment in self.assessments],
            "reuse_tickets": [ticket.to_dict() for ticket in self.reuse_tickets],
            "rerun_evidence": [evidence.to_dict() for evidence in self.rerun_evidence],
            "require_explicit_classification": self.require_explicit_classification,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ModelFreshnessFinding:
    """One model freshness gate finding."""

    code: str
    message: str
    severity: str = "blocker"
    model_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "model_id": self.model_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ModelImpactFreshnessReport:
    """Structured result for model impact freshness review."""

    ok: bool
    plan_id: str
    decision: str
    findings: tuple[ModelFreshnessFinding, ...] = ()
    affected_model_ids: tuple[str, ...] = ()
    reused_model_ids: tuple[str, ...] = ()
    rerun_model_ids: tuple[str, ...] = ()
    deprecated_model_ids: tuple[str, ...] = ()
    blocked_model_ids: tuple[str, ...] = ()
    unknown_model_ids: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "affected_model_ids", _as_tuple(self.affected_model_ids))
        object.__setattr__(self, "reused_model_ids", _as_tuple(self.reused_model_ids))
        object.__setattr__(self, "rerun_model_ids", _as_tuple(self.rerun_model_ids))
        object.__setattr__(self, "deprecated_model_ids", _as_tuple(self.deprecated_model_ids))
        object.__setattr__(self, "blocked_model_ids", _as_tuple(self.blocked_model_ids))
        object.__setattr__(self, "unknown_model_ids", _as_tuple(self.unknown_model_ids))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: plan={self.plan_id} decision={self.decision} findings={len(self.findings)}",
            )

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard model impact freshness review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"plan: {self.plan_id}",
            f"decision: {self.decision}",
            f"affected models: {', '.join(self.affected_model_ids) or '(none)'}",
            f"reused models: {', '.join(self.reused_model_ids) or '(none)'}",
            f"rerun models: {', '.join(self.rerun_model_ids) or '(none)'}",
            f"deprecated models: {', '.join(self.deprecated_model_ids) or '(none)'}",
            f"unknown models: {', '.join(self.unknown_model_ids) or '(none)'}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"model: {finding.model_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "plan_id": self.plan_id,
            "decision": self.decision,
            "findings": [finding.to_dict() for finding in self.findings],
            "affected_model_ids": list(self.affected_model_ids),
            "reused_model_ids": list(self.reused_model_ids),
            "rerun_model_ids": list(self.rerun_model_ids),
            "deprecated_model_ids": list(self.deprecated_model_ids),
            "blocked_model_ids": list(self.blocked_model_ids),
            "unknown_model_ids": list(self.unknown_model_ids),
            "summary": self.summary,
        }


def _finding(
    code: str,
    message: str,
    *,
    model_id: str = "",
    severity: str = "blocker",
    metadata: Mapping[str, Any] | None = None,
) -> ModelFreshnessFinding:
    return ModelFreshnessFinding(
        code,
        message,
        severity=severity,
        model_id=model_id,
        metadata=metadata or {},
    )


def _index_by_model_id(
    items: Sequence[Any],
    *,
    item_name: str,
) -> tuple[dict[str, Any], tuple[ModelFreshnessFinding, ...]]:
    indexed: dict[str, Any] = {}
    findings: list[ModelFreshnessFinding] = []
    for item in items:
        model_id = getattr(item, "model_id", "")
        if model_id in indexed:
            findings.append(
                _finding(
                    f"duplicate_{item_name}",
                    f"duplicate {item_name.replace('_', ' ')} for model {model_id!r}",
                    model_id=model_id,
                )
            )
            continue
        indexed[model_id] = item
    return indexed, tuple(findings)


def _direct_impact(record: ModelFreshnessRecord, impact: UpgradeImpact) -> tuple[tuple[str, ...], tuple[str, ...]]:
    artifact_hits = _intersection(record.dependency_artifact_ids, impact.changed_artifact_ids)
    semantic_hits = _intersection(record.flowguard_semantic_ids, impact.changed_flowguard_semantic_ids)
    return artifact_hits, semantic_hits


def _review_reuse_ticket(
    record: ModelFreshnessRecord,
    assessment: ModelImpactAssessment,
    ticket: ModelReuseTicket | None,
    *,
    direct_artifact_hits: tuple[str, ...],
    direct_semantic_hits: tuple[str, ...],
) -> tuple[ModelFreshnessFinding, ...]:
    findings: list[ModelFreshnessFinding] = []
    if ticket is None:
        return (
            _finding(
                "model_reuse_ticket_missing",
                "not-impacted model has no explicit reuse ticket",
                model_id=record.model_id,
            ),
        )

    checks = (
        ("reuse_ticket_not_current", ticket.ticket_current, "reuse ticket is not marked current"),
        (
            "model_fingerprint_not_current",
            ticket.model_fingerprint_current,
            "model fingerprint was not checked as current",
        ),
        (
            "dependency_fingerprint_not_current",
            ticket.dependency_fingerprints_current,
            "dependency fingerprints were not checked as current",
        ),
        (
            "flowguard_semantics_not_current",
            ticket.flowguard_semantics_current,
            "FlowGuard semantics were not checked as current",
        ),
        (
            "previous_evidence_not_current",
            ticket.previous_evidence_current,
            "previous evidence is not current enough for reuse",
        ),
        (
            "output_fingerprint_mismatch",
            ticket.output_fingerprint_matches,
            "output fingerprint does not match the reusable model result",
        ),
    )
    for code, passed, message in checks:
        if not passed:
            findings.append(_finding(code, message, model_id=record.model_id, metadata=ticket.to_dict()))

    if not ticket.reason:
        findings.append(
            _finding(
                "model_reuse_reason_missing",
                "reuse ticket does not explain why the old model evidence still applies",
                model_id=record.model_id,
                metadata=ticket.to_dict(),
            )
        )

    if record.previous_evidence_id and not ticket.previous_evidence_id:
        findings.append(
            _finding(
                "previous_evidence_id_missing",
                "reuse ticket does not name the previous evidence id it is reusing",
                model_id=record.model_id,
                metadata=ticket.to_dict(),
            )
        )
    elif record.previous_evidence_id and ticket.previous_evidence_id != record.previous_evidence_id:
        findings.append(
            _finding(
                "previous_evidence_id_mismatch",
                "reuse ticket points at different previous evidence than the inventory record",
                model_id=record.model_id,
                metadata={
                    "record_previous_evidence_id": record.previous_evidence_id,
                    "ticket_previous_evidence_id": ticket.previous_evidence_id,
                },
            )
        )

    if direct_artifact_hits or direct_semantic_hits:
        if not assessment.rationale:
            findings.append(
                _finding(
                    "direct_impact_reuse_without_rationale",
                    "changed dependency or FlowGuard semantic was reused without a narrower non-impact rationale",
                    model_id=record.model_id,
                    metadata={
                        "changed_artifact_hits": direct_artifact_hits,
                        "changed_semantic_hits": direct_semantic_hits,
                    },
                )
            )
        if not (ticket.same_output_proof_id or ticket.output_fingerprint):
            findings.append(
                _finding(
                    "same_output_proof_missing",
                    "directly touched model needs same-output proof before old evidence can be reused",
                    model_id=record.model_id,
                    metadata=ticket.to_dict(),
                )
            )
    return tuple(findings)


def _review_rerun_evidence(
    record: ModelFreshnessRecord,
    evidence: ModelRerunEvidence | None,
) -> tuple[ModelFreshnessFinding, ...]:
    if evidence is None:
        return (
            _finding(
                "affected_model_rerun_missing",
                "affected model has no current rerun evidence",
                model_id=record.model_id,
            ),
        )

    findings: list[ModelFreshnessFinding] = []
    if evidence.status not in PASSING_MODEL_RERUN_STATUSES:
        findings.append(
            _finding(
                "affected_model_rerun_not_passing",
                f"affected model rerun status is {evidence.status!r}",
                model_id=record.model_id,
                metadata=evidence.to_dict(),
            )
        )
    if not evidence.current:
        findings.append(
            _finding(
                "affected_model_rerun_not_current",
                "affected model rerun evidence is not marked current",
                model_id=record.model_id,
                metadata=evidence.to_dict(),
            )
        )
    if not evidence.evidence_id:
        findings.append(
            _finding(
                "affected_model_evidence_id_missing",
                "affected model rerun evidence does not have an evidence id",
                model_id=record.model_id,
                metadata=evidence.to_dict(),
            )
        )
    if not evidence.model_update_reviewed:
        findings.append(
            _finding(
                "affected_model_update_review_missing",
                "affected model does not record whether the model file required an update",
                model_id=record.model_id,
                metadata=evidence.to_dict(),
            )
        )
    elif not (evidence.model_updated or evidence.model_update_not_required_reason):
        findings.append(
            _finding(
                "affected_model_update_result_missing",
                "model update review has no update flag or no-update rationale",
                model_id=record.model_id,
                metadata=evidence.to_dict(),
            )
        )
    if not evidence.test_update_reviewed:
        findings.append(
            _finding(
                "affected_model_test_update_review_missing",
                "affected model does not record whether model tests required an update",
                model_id=record.model_id,
                metadata=evidence.to_dict(),
            )
        )
    elif not (evidence.tests_updated or evidence.test_update_not_required_reason):
        findings.append(
            _finding(
                "affected_model_test_update_result_missing",
                "test update review has no update flag or no-update rationale",
                model_id=record.model_id,
                metadata=evidence.to_dict(),
            )
        )
    if evidence.output_changed and not evidence.output_change_explanation:
        findings.append(
            _finding(
                "affected_model_output_change_unexplained",
                "rerun output changed without an explanation",
                model_id=record.model_id,
                metadata=evidence.to_dict(),
            )
        )
    return tuple(findings)


def _decision_for(findings: Sequence[ModelFreshnessFinding]) -> tuple[str, bool]:
    blockers = tuple(finding for finding in findings if finding.severity == "blocker")
    if not blockers:
        return MODEL_FRESHNESS_DECISION_CURRENT, True
    codes = {finding.code for finding in blockers}
    if any("classification" in code or "unknown" in code for code in codes):
        return MODEL_FRESHNESS_DECISION_UNKNOWN, False
    if any(code.startswith("affected_model_") for code in codes):
        return MODEL_FRESHNESS_DECISION_AFFECTED_RERUN_REQUIRED, False
    if any("reuse" in code or "fingerprint" in code or "same_output" in code for code in codes):
        return MODEL_FRESHNESS_DECISION_REUSE_INVALID, False
    if any("deprecated" in code or "replacement" in code for code in codes):
        return MODEL_FRESHNESS_DECISION_DEPRECATED_INVALID, False
    return MODEL_FRESHNESS_DECISION_BLOCKED, False


def review_model_impact_freshness(plan: ModelImpactFreshnessPlan) -> ModelImpactFreshnessReport:
    """Review whether existing FlowGuard model evidence is current after an upgrade."""

    findings: list[ModelFreshnessFinding] = []
    affected_model_ids: list[str] = []
    reused_model_ids: list[str] = []
    rerun_model_ids: list[str] = []
    deprecated_model_ids: list[str] = []
    blocked_model_ids: list[str] = []
    unknown_model_ids: list[str] = []

    if not plan.records:
        findings.append(
            _finding(
                "model_inventory_empty",
                "model impact freshness review has no existing model inventory records",
            )
        )

    record_index, duplicate_record_findings = _index_by_model_id(plan.records, item_name="model_record")
    assessment_index, duplicate_assessment_findings = _index_by_model_id(
        plan.assessments,
        item_name="model_assessment",
    )
    reuse_ticket_index, duplicate_reuse_findings = _index_by_model_id(
        plan.reuse_tickets,
        item_name="reuse_ticket",
    )
    rerun_index, duplicate_rerun_findings = _index_by_model_id(
        plan.rerun_evidence,
        item_name="rerun_evidence",
    )
    findings.extend(duplicate_record_findings)
    findings.extend(duplicate_assessment_findings)
    findings.extend(duplicate_reuse_findings)
    findings.extend(duplicate_rerun_findings)

    for model_id, record in record_index.items():
        assessment = assessment_index.get(model_id)
        artifact_hits, semantic_hits = _direct_impact(record, plan.impact)

        if assessment is None:
            unknown_model_ids.append(model_id)
            if plan.require_explicit_classification:
                findings.append(
                    _finding(
                        "model_impact_classification_missing",
                        "model has no impact classification for this upgrade",
                        model_id=model_id,
                        metadata={
                            "changed_artifact_hits": artifact_hits,
                            "changed_semantic_hits": semantic_hits,
                            "record": record.to_dict(),
                        },
                    )
                )
            continue

        if assessment.classification not in MODEL_IMPACT_CLASSIFICATIONS:
            unknown_model_ids.append(model_id)
            findings.append(
                _finding(
                    "model_impact_classification_invalid",
                    f"unknown model impact classification {assessment.classification!r}",
                    model_id=model_id,
                    metadata=assessment.to_dict(),
                )
            )
            continue

        if assessment.classification == MODEL_IMPACT_UNKNOWN:
            unknown_model_ids.append(model_id)
            findings.append(
                _finding(
                    "model_impact_classification_unknown",
                    "model impact classification is still unknown",
                    model_id=model_id,
                    metadata=assessment.to_dict(),
                )
            )
            continue

        if assessment.classification == MODEL_IMPACT_BLOCKED:
            blocked_model_ids.append(model_id)
            findings.append(
                _finding(
                    "model_impact_classification_blocked",
                    assessment.blocked_reason or "model impact classification is blocked",
                    model_id=model_id,
                    metadata=assessment.to_dict(),
                )
            )
            continue

        if assessment.classification == MODEL_IMPACT_DEPRECATED:
            deprecated_model_ids.append(model_id)
            replacement = assessment.replacement_model_id or record.replacement_model_id
            if not replacement:
                findings.append(
                    _finding(
                        "deprecated_model_replacement_missing",
                        "deprecated model does not name a replacement model",
                        model_id=model_id,
                        metadata={"record": record.to_dict(), "assessment": assessment.to_dict()},
                    )
                )
            if not assessment.rationale:
                findings.append(
                    _finding(
                        "deprecated_model_reason_missing",
                        "deprecated model does not explain why it no longer participates",
                        model_id=model_id,
                        metadata=assessment.to_dict(),
                    )
                )
            continue

        if assessment.classification == MODEL_IMPACT_AFFECTED:
            affected_model_ids.append(model_id)
            rerun_model_ids.append(model_id)
            findings.extend(_review_rerun_evidence(record, rerun_index.get(model_id)))
            continue

        if assessment.classification == MODEL_IMPACT_NOT_IMPACTED:
            reused_model_ids.append(model_id)
            findings.extend(
                _review_reuse_ticket(
                    record,
                    assessment,
                    reuse_ticket_index.get(model_id),
                    direct_artifact_hits=artifact_hits,
                    direct_semantic_hits=semantic_hits,
                )
            )

    for assessment_model_id in assessment_index:
        if assessment_model_id not in record_index:
            findings.append(
                _finding(
                    "assessment_without_inventory_record",
                    "impact assessment references a model that is not in the inventory",
                    model_id=assessment_model_id,
                    metadata=assessment_index[assessment_model_id].to_dict(),
                )
            )
    for ticket_model_id in reuse_ticket_index:
        if ticket_model_id not in record_index:
            findings.append(
                _finding(
                    "reuse_ticket_without_inventory_record",
                    "reuse ticket references a model that is not in the inventory",
                    model_id=ticket_model_id,
                    metadata=reuse_ticket_index[ticket_model_id].to_dict(),
                )
            )
    for rerun_model_id in rerun_index:
        if rerun_model_id not in record_index:
            findings.append(
                _finding(
                    "rerun_evidence_without_inventory_record",
                    "rerun evidence references a model that is not in the inventory",
                    model_id=rerun_model_id,
                    metadata=rerun_index[rerun_model_id].to_dict(),
                )
            )

    decision, ok = _decision_for(findings)
    return ModelImpactFreshnessReport(
        ok=ok,
        plan_id=plan.plan_id,
        decision=decision,
        findings=tuple(findings),
        affected_model_ids=tuple(affected_model_ids),
        reused_model_ids=tuple(reused_model_ids),
        rerun_model_ids=tuple(rerun_model_ids),
        deprecated_model_ids=tuple(deprecated_model_ids),
        blocked_model_ids=tuple(blocked_model_ids),
        unknown_model_ids=tuple(unknown_model_ids),
    )


__all__ = [
    "MODEL_FRESHNESS_DECISION_AFFECTED_RERUN_REQUIRED",
    "MODEL_FRESHNESS_DECISION_BLOCKED",
    "MODEL_FRESHNESS_DECISION_CURRENT",
    "MODEL_FRESHNESS_DECISION_DEPRECATED_INVALID",
    "MODEL_FRESHNESS_DECISION_REUSE_INVALID",
    "MODEL_FRESHNESS_DECISION_UNKNOWN",
    "MODEL_IMPACT_AFFECTED",
    "MODEL_IMPACT_BLOCKED",
    "MODEL_IMPACT_CLASSIFICATIONS",
    "MODEL_IMPACT_DEPRECATED",
    "MODEL_IMPACT_NOT_IMPACTED",
    "MODEL_IMPACT_UNKNOWN",
    "MODEL_RERUN_STATUS_ERROR",
    "MODEL_RERUN_STATUS_FAILED",
    "MODEL_RERUN_STATUS_NOT_RUN",
    "MODEL_RERUN_STATUS_PASSED",
    "MODEL_RERUN_STATUS_RUNNING",
    "MODEL_RERUN_STATUS_SKIPPED",
    "MODEL_RERUN_STATUS_STALE",
    "NON_PASSING_MODEL_RERUN_STATUSES",
    "PASSING_MODEL_RERUN_STATUSES",
    "ModelFreshnessFinding",
    "ModelFreshnessRecord",
    "ModelImpactAssessment",
    "ModelImpactFreshnessPlan",
    "ModelImpactFreshnessReport",
    "ModelReuseTicket",
    "ModelRerunEvidence",
    "UpgradeImpact",
    "review_model_impact_freshness",
]
