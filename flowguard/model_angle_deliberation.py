"""Open-ended FlowGuard model-angle deliberation helpers.

This route records whether the current model boundary is enough before an
agent relies on it. Existing FlowGuard routes remain the owners of the actual
work; this helper preserves the reasoning that decides whether to reuse,
extend, split, create, scope, or block model coverage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ._normalization import string_tuple as _as_tuple

from .export import to_jsonable
from .proof_artifact import ProofArtifactRef, coerce_proof_artifact_ref
from .model_maturation import (
    MODEL_MATURATION_RESOLUTION_MODEL_EDIT,
    MODEL_MATURATION_SIGNAL_MISSING_MODEL_OBLIGATION,
    ModelMaturationCoverageContribution,
    ModelMaturationSignal,
)


MODEL_ANGLE_ACTION_REUSE_EXISTING = "reuse_existing"
MODEL_ANGLE_ACTION_EXTEND_EXISTING = "extend_existing"
MODEL_ANGLE_ACTION_CREATE_NEW_MODEL = "create_new_model"
MODEL_ANGLE_ACTION_ADD_CHILD_MODEL = "add_child_model"
MODEL_ANGLE_ACTION_SCOPE_OUT = "scope_out_with_reason"
MODEL_ANGLE_ACTION_DEFER = "defer_with_reason"
MODEL_ANGLE_ACTION_NEEDS_HUMAN_REVIEW = "needs_human_review"

MODEL_ANGLE_ACTIONS = {
    MODEL_ANGLE_ACTION_REUSE_EXISTING,
    MODEL_ANGLE_ACTION_EXTEND_EXISTING,
    MODEL_ANGLE_ACTION_CREATE_NEW_MODEL,
    MODEL_ANGLE_ACTION_ADD_CHILD_MODEL,
    MODEL_ANGLE_ACTION_SCOPE_OUT,
    MODEL_ANGLE_ACTION_DEFER,
    MODEL_ANGLE_ACTION_NEEDS_HUMAN_REVIEW,
}

MODEL_ANGLE_DECISION_READY = "model_angle_ready"
MODEL_ANGLE_DECISION_SCOPED = "model_angle_scoped_confidence"
MODEL_ANGLE_DECISION_BLOCKED = "model_angle_blocked"

MODEL_ANGLE_CONFIDENCE_FULL = "full"
MODEL_ANGLE_CONFIDENCE_SCOPED = "scoped"
MODEL_ANGLE_CONFIDENCE_BLOCKED = "blocked"

MODEL_ANGLE_FINDING_INFO = "info"
MODEL_ANGLE_FINDING_GAP = "gap"
MODEL_ANGLE_FINDING_BLOCKER = "blocker"
MODEL_ANGLE_FINDING_SEVERITIES = {
    MODEL_ANGLE_FINDING_INFO,
    MODEL_ANGLE_FINDING_GAP,
    MODEL_ANGLE_FINDING_BLOCKER,
}

MODEL_ANGLE_ROUTE_MODEL_MATURATION = "model_maturation_loop"
MODEL_ANGLE_ROUTE_MODEL_MESH = "model_mesh_maintenance"
MODEL_ANGLE_ROUTE_AGENT_WORKFLOW_REHEARSAL = "agent_workflow_rehearsal"

_BROAD_ACTIONS = {
    MODEL_ANGLE_ACTION_EXTEND_EXISTING,
    MODEL_ANGLE_ACTION_CREATE_NEW_MODEL,
    MODEL_ANGLE_ACTION_ADD_CHILD_MODEL,
    MODEL_ANGLE_ACTION_NEEDS_HUMAN_REVIEW,
}


def _coerce_deliberation(value: Any) -> "ModelAngleDeliberation":
    if isinstance(value, ModelAngleDeliberation):
        return value
    if isinstance(value, Mapping):
        return ModelAngleDeliberation(**value)
    raise TypeError(f"cannot coerce {type(value).__name__} to ModelAngleDeliberation")


@dataclass(frozen=True)
class ModelAngleDeliberation:
    """One free-form candidate model angle considered by an agent."""

    angle_id: str
    angle_name: str
    trigger_observation: str = ""
    current_model_sees: str = ""
    current_model_misses: str = ""
    failure_if_ignored: str = ""
    candidate_action: str = MODEL_ANGLE_ACTION_REUSE_EXISTING
    existing_model_ids: tuple[str, ...] = ()
    proposed_model_boundary: str = ""
    owner_route_hint: str = ""
    required_before_broad_claim: bool = True
    scoped_out_reason: str = ""
    evidence_needed: tuple[str, ...] = ()
    open_questions: tuple[str, ...] = ()
    resolved: bool = False
    owner_evidence: ProofArtifactRef | Mapping[str, Any] | None = None
    subject_fingerprints: Mapping[str, str] = field(default_factory=dict)
    current: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "angle_id", str(self.angle_id))
        object.__setattr__(self, "angle_name", str(self.angle_name))
        object.__setattr__(self, "trigger_observation", str(self.trigger_observation))
        object.__setattr__(self, "current_model_sees", str(self.current_model_sees))
        object.__setattr__(self, "current_model_misses", str(self.current_model_misses))
        object.__setattr__(self, "failure_if_ignored", str(self.failure_if_ignored))
        object.__setattr__(self, "candidate_action", str(self.candidate_action))
        object.__setattr__(self, "existing_model_ids", _as_tuple(self.existing_model_ids))
        object.__setattr__(self, "proposed_model_boundary", str(self.proposed_model_boundary))
        object.__setattr__(self, "owner_route_hint", str(self.owner_route_hint))
        object.__setattr__(self, "required_before_broad_claim", bool(self.required_before_broad_claim))
        object.__setattr__(self, "scoped_out_reason", str(self.scoped_out_reason))
        object.__setattr__(self, "evidence_needed", _as_tuple(self.evidence_needed))
        object.__setattr__(self, "open_questions", _as_tuple(self.open_questions))
        object.__setattr__(self, "resolved", bool(self.resolved))
        object.__setattr__(self, "owner_evidence", coerce_proof_artifact_ref(self.owner_evidence))
        object.__setattr__(
            self,
            "subject_fingerprints",
            {str(key): str(value) for key, value in self.subject_fingerprints.items()},
        )
        object.__setattr__(self, "current", bool(self.current))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def owner_route(self) -> str:
        if self.owner_route_hint:
            return self.owner_route_hint
        if self.candidate_action == MODEL_ANGLE_ACTION_ADD_CHILD_MODEL:
            return MODEL_ANGLE_ROUTE_MODEL_MESH
        if self.candidate_action == MODEL_ANGLE_ACTION_NEEDS_HUMAN_REVIEW:
            return MODEL_ANGLE_ROUTE_AGENT_WORKFLOW_REHEARSAL
        return MODEL_ANGLE_ROUTE_MODEL_MATURATION

    def needs_resolution_before_broad_claim(self) -> bool:
        return (
            self.required_before_broad_claim
            and self.current
            and not self.resolution_is_authoritative()
            and self.candidate_action in _BROAD_ACTIONS
        )

    def owner_evidence_gap_codes(self) -> tuple[str, ...]:
        if not self.resolved:
            return ("model_angle_not_resolved",)
        proof = self.owner_evidence
        if proof is None:
            return ("missing_model_angle_owner_evidence",)
        gaps: list[str] = []
        if proof.producer_route != self.owner_route():
            gaps.append("model_angle_owner_mismatch")
        if not proof.has_current_pass():
            gaps.append("model_angle_owner_evidence_not_current_pass")
        if not proof.covers_all((self.angle_id,)):
            gaps.append("model_angle_owner_evidence_missing_angle")
        if not self.subject_fingerprints:
            gaps.append("model_angle_subject_fingerprints_missing")
        elif any(
            proof.artifact_fingerprints.get(key) != value
            for key, value in self.subject_fingerprints.items()
        ):
            gaps.append("model_angle_subject_fingerprint_mismatch")
        return tuple(gaps)

    def resolution_is_authoritative(self) -> bool:
        return not self.owner_evidence_gap_codes()

    def is_scoped_action(self) -> bool:
        return self.candidate_action in {
            MODEL_ANGLE_ACTION_SCOPE_OUT,
            MODEL_ANGLE_ACTION_DEFER,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "angle_id": self.angle_id,
            "angle_name": self.angle_name,
            "trigger_observation": self.trigger_observation,
            "current_model_sees": self.current_model_sees,
            "current_model_misses": self.current_model_misses,
            "failure_if_ignored": self.failure_if_ignored,
            "candidate_action": self.candidate_action,
            "existing_model_ids": list(self.existing_model_ids),
            "proposed_model_boundary": self.proposed_model_boundary,
            "owner_route_hint": self.owner_route_hint,
            "required_before_broad_claim": self.required_before_broad_claim,
            "scoped_out_reason": self.scoped_out_reason,
            "evidence_needed": list(self.evidence_needed),
            "open_questions": list(self.open_questions),
            "resolved": self.resolved,
            "owner_evidence": self.owner_evidence.to_dict() if self.owner_evidence else None,
            "subject_fingerprints": dict(self.subject_fingerprints),
            "current": self.current,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ModelAngleFinding:
    """One model-angle review finding."""

    code: str
    message: str
    severity: str = MODEL_ANGLE_FINDING_BLOCKER
    angle_id: str = ""
    owner_route: str = ""
    candidate_action: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        severity = str(self.severity or MODEL_ANGLE_FINDING_BLOCKER)
        if severity not in MODEL_ANGLE_FINDING_SEVERITIES:
            raise ValueError("severity must be info, gap, or blocker")
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "angle_id", str(self.angle_id))
        object.__setattr__(self, "owner_route", str(self.owner_route))
        object.__setattr__(self, "candidate_action", str(self.candidate_action))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def blocks_full_confidence(self) -> bool:
        return self.severity == MODEL_ANGLE_FINDING_BLOCKER

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "angle_id": self.angle_id,
            "owner_route": self.owner_route,
            "candidate_action": self.candidate_action,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ModelAngleReviewReport:
    """Structured outcome for open-ended model-angle review."""

    ok: bool
    review_id: str
    decision: str
    confidence: str
    deliberations: tuple[ModelAngleDeliberation, ...] = ()
    findings: tuple[ModelAngleFinding, ...] = ()
    unresolved_angle_ids: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "review_id", str(self.review_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "deliberations", tuple(_coerce_deliberation(item) for item in self.deliberations))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "unresolved_angle_ids", _as_tuple(self.unresolved_angle_ids))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: review={self.review_id} decision={self.decision} "
                f"angles={len(self.deliberations)} findings={len(self.findings)}",
            )

    def supports_full_confidence(self) -> bool:
        return self.ok and self.confidence == MODEL_ANGLE_CONFIDENCE_FULL and not self.unresolved_angle_ids

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == MODEL_ANGLE_FINDING_BLOCKER)

    def gap_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == MODEL_ANGLE_FINDING_GAP)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "model_angle_review_report",
            "ok": self.ok,
            "review_id": self.review_id,
            "decision": self.decision,
            "confidence": self.confidence,
            "deliberations": [item.to_dict() for item in self.deliberations],
            "findings": [finding.to_dict() for finding in self.findings],
            "unresolved_angle_ids": list(self.unresolved_angle_ids),
            "summary": self.summary,
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard model angle deliberation ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"review: {self.review_id}",
            f"decision: {self.decision}",
            f"confidence: {self.confidence}",
            f"angles: {len(self.deliberations)}",
            f"findings: {len(self.findings)}",
        ]
        if self.unresolved_angle_ids:
            lines.append("unresolved_angle_ids: " + ", ".join(self.unresolved_angle_ids))
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"angle: {finding.angle_id or '(none)'}",
                    f"owner_route: {finding.owner_route or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)


def review_model_angle_deliberations(
    review_id: str,
    deliberations: Sequence[ModelAngleDeliberation | Mapping[str, Any]],
    *,
    require_review: bool = True,
    broad_claim: bool = False,
    allow_scoped_confidence: bool = True,
) -> ModelAngleReviewReport:
    """Review free-form model-angle deliberations before route confidence."""

    normalized = tuple(_coerce_deliberation(item) for item in deliberations)
    findings: list[ModelAngleFinding] = []
    unresolved: list[str] = []

    if require_review and not normalized:
        severity = MODEL_ANGLE_FINDING_BLOCKER if broad_claim else MODEL_ANGLE_FINDING_GAP
        findings.append(
            ModelAngleFinding(
                "missing_model_angle_review",
                "model-angle deliberation is required but no candidate angle rows were supplied",
                severity=severity,
                owner_route=MODEL_ANGLE_ROUTE_MODEL_MATURATION,
            )
        )

    seen_angle_ids: set[str] = set()
    for item in normalized:
        metadata = item.to_dict()
        owner_route = item.owner_route()
        if not item.angle_id:
            findings.append(
                ModelAngleFinding(
                    "missing_angle_id",
                    "model-angle row has no stable id",
                    owner_route=owner_route,
                    candidate_action=item.candidate_action,
                    metadata=metadata,
                )
            )
        elif item.angle_id in seen_angle_ids:
            findings.append(
                ModelAngleFinding(
                    "duplicate_angle_id",
                    f"model-angle id {item.angle_id!r} is duplicated",
                    angle_id=item.angle_id,
                    owner_route=owner_route,
                    candidate_action=item.candidate_action,
                    metadata=metadata,
                )
            )
        else:
            seen_angle_ids.add(item.angle_id)

        if not item.current:
            findings.append(
                ModelAngleFinding(
                    "stale_model_angle_review",
                    "model-angle deliberation is stale and must be rerun before broad confidence",
                    angle_id=item.angle_id,
                    owner_route=owner_route,
                    candidate_action=item.candidate_action,
                    metadata=metadata,
                )
            )
        if not item.angle_name:
            findings.append(
                ModelAngleFinding(
                    "missing_angle_name",
                    "model-angle row must name the angle in plain language",
                    angle_id=item.angle_id,
                    owner_route=owner_route,
                    candidate_action=item.candidate_action,
                    metadata=metadata,
                )
            )
        if item.candidate_action not in MODEL_ANGLE_ACTIONS:
            findings.append(
                ModelAngleFinding(
                    "invalid_model_angle_action",
                    f"candidate action {item.candidate_action!r} is not recognized",
                    angle_id=item.angle_id,
                    owner_route=owner_route,
                    candidate_action=item.candidate_action,
                    metadata=metadata,
                )
            )

        for field_name, label in (
            ("current_model_sees", "what the current model covers"),
            ("current_model_misses", "what the current model may miss"),
            ("failure_if_ignored", "what can fail if this angle is ignored"),
        ):
            if not getattr(item, field_name):
                findings.append(
                    ModelAngleFinding(
                        f"missing_{field_name}",
                        f"model-angle row must record {label}",
                        severity=MODEL_ANGLE_FINDING_GAP,
                        angle_id=item.angle_id,
                        owner_route=owner_route,
                        candidate_action=item.candidate_action,
                        metadata=metadata,
                    )
                )

        if item.candidate_action in {
            MODEL_ANGLE_ACTION_EXTEND_EXISTING,
            MODEL_ANGLE_ACTION_ADD_CHILD_MODEL,
        } and not item.existing_model_ids:
            findings.append(
                ModelAngleFinding(
                    "missing_existing_model_owner",
                    "extension or child-model decisions must name the existing owner model ids",
                    angle_id=item.angle_id,
                    owner_route=owner_route,
                    candidate_action=item.candidate_action,
                    metadata=metadata,
                )
            )
        if item.candidate_action in {
            MODEL_ANGLE_ACTION_EXTEND_EXISTING,
            MODEL_ANGLE_ACTION_CREATE_NEW_MODEL,
            MODEL_ANGLE_ACTION_ADD_CHILD_MODEL,
        } and not item.proposed_model_boundary:
            findings.append(
                ModelAngleFinding(
                    "missing_proposed_model_boundary",
                    "model-angle row must describe the proposed model boundary",
                    angle_id=item.angle_id,
                    owner_route=owner_route,
                    candidate_action=item.candidate_action,
                    metadata=metadata,
                )
            )
        if item.is_scoped_action() and not item.scoped_out_reason:
            findings.append(
                ModelAngleFinding(
                    "missing_scope_reason",
                    "scoped or deferred model-angle decisions must explain why that is safe",
                    angle_id=item.angle_id,
                    owner_route=owner_route,
                    candidate_action=item.candidate_action,
                    metadata=metadata,
                )
            )
        if item.candidate_action == MODEL_ANGLE_ACTION_NEEDS_HUMAN_REVIEW and not item.open_questions:
            findings.append(
                ModelAngleFinding(
                    "missing_human_review_question",
                    "human-review model-angle decisions must name the unresolved question",
                    angle_id=item.angle_id,
                    owner_route=owner_route,
                    candidate_action=item.candidate_action,
                    metadata=metadata,
                )
            )
        if item.needs_resolution_before_broad_claim():
            unresolved.append(item.angle_id)
            severity = MODEL_ANGLE_FINDING_BLOCKER if broad_claim else MODEL_ANGLE_FINDING_GAP
            for gap_code in item.owner_evidence_gap_codes():
                findings.append(
                    ModelAngleFinding(
                        gap_code,
                        "required model-angle resolution lacks exact current proof from its owner route and subject",
                        severity=severity,
                        angle_id=item.angle_id,
                        owner_route=owner_route,
                        candidate_action=item.candidate_action,
                        metadata=metadata,
                    )
                )
            findings.append(
                ModelAngleFinding(
                    "unresolved_required_model_angle",
                    "required model-angle decision is not resolved by owner-route evidence",
                    severity=severity,
                    angle_id=item.angle_id,
                    owner_route=owner_route,
                    candidate_action=item.candidate_action,
                    metadata=metadata,
                )
            )

    blockers = tuple(finding for finding in findings if finding.severity == MODEL_ANGLE_FINDING_BLOCKER)
    gaps = tuple(finding for finding in findings if finding.severity == MODEL_ANGLE_FINDING_GAP)
    if blockers:
        decision = MODEL_ANGLE_DECISION_BLOCKED
        confidence = MODEL_ANGLE_CONFIDENCE_BLOCKED
        ok = False
    elif gaps:
        decision = MODEL_ANGLE_DECISION_SCOPED
        confidence = MODEL_ANGLE_CONFIDENCE_SCOPED
        ok = bool(allow_scoped_confidence)
    else:
        decision = MODEL_ANGLE_DECISION_READY
        confidence = MODEL_ANGLE_CONFIDENCE_FULL
        ok = True

    return ModelAngleReviewReport(
        ok=ok,
        review_id=str(review_id),
        decision=decision,
        confidence=confidence,
        deliberations=normalized,
        findings=tuple(findings),
        unresolved_angle_ids=tuple(value for value in unresolved if value),
    )


def model_angle_report_to_maturation_contribution(
    report: ModelAngleReviewReport,
    *,
    task_id: str,
    report_evidence: ProofArtifactRef | Mapping[str, Any] | None,
    subject_fingerprints: Mapping[str, str],
) -> ModelMaturationCoverageContribution:
    """Project angle coverage and open owner-proof gaps without claiming sufficiency."""

    coverage_ids = tuple(item.angle_id for item in report.deliberations if item.angle_id)
    signals = tuple(
        ModelMaturationSignal(
            signal_id=f"model-angle:{item.angle_id}",
            signal_type=MODEL_MATURATION_SIGNAL_MISSING_MODEL_OBLIGATION,
            source_route="model_angle_deliberation",
            model_id=next(iter(item.existing_model_ids), ""),
            coverage_id=item.angle_id,
            probe_id=f"probe:model-angle:{item.angle_id}",
            resolution_class=MODEL_MATURATION_RESOLUTION_MODEL_EDIT,
            prediction=f"owner route {item.owner_route()} resolves angle {item.angle_id}",
            falsifier=f"angle {item.angle_id} lacks exact current owner proof",
            description=item.failure_if_ignored,
            resolved=item.resolution_is_authoritative(),
            current=item.current,
            metadata={"owner_route": item.owner_route(), "candidate_action": item.candidate_action},
        )
        for item in report.deliberations
        if item.angle_id
    )
    return ModelMaturationCoverageContribution(
        contribution_id=f"model-angle:{report.review_id}",
        owner_route="model_angle_deliberation",
        task_id=task_id,
        coverage_source_refs=(f"model-angle-review:{report.review_id}",),
        coverage_ids=coverage_ids,
        required_probe_ids=tuple(f"probe:model-angle:{value}" for value in coverage_ids),
        signals=signals,
        evidence_ref=report_evidence,
        subject_fingerprints=subject_fingerprints,
        status="pass",
        current=all(item.current for item in report.deliberations),
    )


__all__ = [
    "MODEL_ANGLE_ACTION_ADD_CHILD_MODEL",
    "MODEL_ANGLE_ACTION_CREATE_NEW_MODEL",
    "MODEL_ANGLE_ACTION_DEFER",
    "MODEL_ANGLE_ACTION_EXTEND_EXISTING",
    "MODEL_ANGLE_ACTION_NEEDS_HUMAN_REVIEW",
    "MODEL_ANGLE_ACTION_REUSE_EXISTING",
    "MODEL_ANGLE_ACTION_SCOPE_OUT",
    "MODEL_ANGLE_ACTIONS",
    "MODEL_ANGLE_CONFIDENCE_BLOCKED",
    "MODEL_ANGLE_CONFIDENCE_FULL",
    "MODEL_ANGLE_CONFIDENCE_SCOPED",
    "MODEL_ANGLE_DECISION_BLOCKED",
    "MODEL_ANGLE_DECISION_READY",
    "MODEL_ANGLE_DECISION_SCOPED",
    "MODEL_ANGLE_FINDING_BLOCKER",
    "MODEL_ANGLE_FINDING_GAP",
    "MODEL_ANGLE_FINDING_INFO",
    "MODEL_ANGLE_FINDING_SEVERITIES",
    "MODEL_ANGLE_ROUTE_AGENT_WORKFLOW_REHEARSAL",
    "MODEL_ANGLE_ROUTE_MODEL_MATURATION",
    "MODEL_ANGLE_ROUTE_MODEL_MESH",
    "ModelAngleDeliberation",
    "ModelAngleFinding",
    "ModelAngleReviewReport",
    "model_angle_report_to_maturation_contribution",
    "review_model_angle_deliberations",
]
