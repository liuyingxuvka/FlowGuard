"""Automatic ModelMesh/TestMesh split diagnostics.

This helper turns oversized, slow, broad, progress-only, or incomplete direct
model/test evidence into a structured ModelMesh/TestMesh split requirement. It
does not run child models or tests; it recommends the existing mesh routes and
keeps broad direct evidence from becoming full parent confidence by itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable
from .hierarchy import DEFAULT_LARGE_MODEL_STATE_THRESHOLD, ModelTargetSplitDerivation
from .testmesh import TestTargetSplitDerivation


AUTO_SPLIT_TARGET_MODEL = "model"
AUTO_SPLIT_TARGET_TEST = "test"
AUTO_SPLIT_ROUTE_MODEL_MESH = "model_mesh"
AUTO_SPLIT_ROUTE_TEST_MESH = "test_mesh"

AUTO_SPLIT_CONFIDENCE_FULL = "full"
AUTO_SPLIT_CONFIDENCE_SCOPED = "scoped"
AUTO_SPLIT_CONFIDENCE_BLOCKED = "blocked"

AUTO_SPLIT_DECISION_NOT_REQUIRED = "auto_split_not_required"
AUTO_SPLIT_DECISION_FULL = "auto_split_full_confidence"
AUTO_SPLIT_DECISION_SCOPED = "auto_split_scoped_confidence"
AUTO_SPLIT_DECISION_MODEL_REQUIRED = "model_mesh_split_required"
AUTO_SPLIT_DECISION_TEST_REQUIRED = "test_mesh_split_required"
AUTO_SPLIT_DECISION_TARGET_REQUIRED = "target_split_derivation_required"


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


@dataclass(frozen=True)
class AutoSplitPolicy:
    """Thresholds used to decide when direct evidence must become mesh evidence."""

    model_state_threshold: int = DEFAULT_LARGE_MODEL_STATE_THRESHOLD
    test_duration_seconds_threshold: float = 300.0
    test_count_threshold: int = 500
    selected_test_threshold: int = 250
    broad_obligation_threshold: int = 4

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_state_threshold", int(self.model_state_threshold))
        object.__setattr__(self, "test_duration_seconds_threshold", float(self.test_duration_seconds_threshold))
        object.__setattr__(self, "test_count_threshold", int(self.test_count_threshold))
        object.__setattr__(self, "selected_test_threshold", int(self.selected_test_threshold))
        object.__setattr__(self, "broad_obligation_threshold", int(self.broad_obligation_threshold))

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_state_threshold": self.model_state_threshold,
            "test_duration_seconds_threshold": self.test_duration_seconds_threshold,
            "test_count_threshold": self.test_count_threshold,
            "selected_test_threshold": self.selected_test_threshold,
            "broad_obligation_threshold": self.broad_obligation_threshold,
        }


@dataclass(frozen=True)
class AutoSplitCandidate:
    """One direct model or validation evidence object being reviewed for split needs."""

    candidate_id: str
    target_kind: str
    parent_id: str = ""
    evidence_id: str = ""
    source_model_id: str = ""
    source_model_path: str = ""
    estimated_state_count: int | None = None
    observed_state_count: int | None = None
    processed_state_count: int | None = None
    pending_state_count: int = 0
    duration_seconds: float | None = None
    test_count: int = 0
    selected_count: int = 0
    covered_obligation_count: int = 0
    separable_areas: bool = False
    background: bool = False
    progress_only: bool = False
    release_only: bool = False
    suggested_child_ids: tuple[str, ...] = ()
    covered_partition_item_ids: tuple[str, ...] = ()
    state_owner_fields: tuple[str, ...] = ()
    side_effect_owner_fields: tuple[str, ...] = ()
    split_gate_id: str = ""
    split_review_current: bool = False
    split_confidence: str = AUTO_SPLIT_CONFIDENCE_BLOCKED
    scoped_reasons: tuple[str, ...] = ()
    rationale: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", str(self.candidate_id))
        object.__setattr__(self, "target_kind", str(self.target_kind))
        object.__setattr__(self, "parent_id", str(self.parent_id))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "source_model_id", str(self.source_model_id))
        object.__setattr__(self, "source_model_path", str(self.source_model_path))
        object.__setattr__(self, "pending_state_count", int(self.pending_state_count))
        object.__setattr__(self, "test_count", int(self.test_count))
        object.__setattr__(self, "selected_count", int(self.selected_count))
        object.__setattr__(self, "covered_obligation_count", int(self.covered_obligation_count))
        object.__setattr__(self, "suggested_child_ids", _as_tuple(self.suggested_child_ids))
        object.__setattr__(self, "covered_partition_item_ids", _as_tuple(self.covered_partition_item_ids))
        object.__setattr__(self, "state_owner_fields", _as_tuple(self.state_owner_fields))
        object.__setattr__(self, "side_effect_owner_fields", _as_tuple(self.side_effect_owner_fields))
        object.__setattr__(self, "split_gate_id", str(self.split_gate_id))
        object.__setattr__(self, "split_confidence", str(self.split_confidence))
        object.__setattr__(self, "scoped_reasons", _as_tuple(self.scoped_reasons))
        object.__setattr__(self, "rationale", str(self.rationale))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def largest_state_count(self) -> int:
        counts = [
            count
            for count in (self.estimated_state_count, self.observed_state_count, self.processed_state_count)
            if count is not None
        ]
        return max(counts) if counts else 0

    def target_route(self) -> str:
        return AUTO_SPLIT_ROUTE_MODEL_MESH if self.target_kind == AUTO_SPLIT_TARGET_MODEL else AUTO_SPLIT_ROUTE_TEST_MESH

    def split_reasons(self, policy: AutoSplitPolicy) -> tuple[str, ...]:
        reasons: list[str] = []
        if self.target_kind == AUTO_SPLIT_TARGET_MODEL:
            if self.largest_state_count() > policy.model_state_threshold:
                reasons.append("model_state_threshold_exceeded")
            if self.pending_state_count > 0:
                reasons.append("budgeted_model_pending_states")
            if self.separable_areas:
                reasons.append("separable_model_areas")
        elif self.target_kind == AUTO_SPLIT_TARGET_TEST:
            if self.duration_seconds is not None and self.duration_seconds > policy.test_duration_seconds_threshold:
                reasons.append("test_duration_threshold_exceeded")
            if self.test_count > policy.test_count_threshold:
                reasons.append("test_count_threshold_exceeded")
            if self.selected_count > policy.selected_test_threshold:
                reasons.append("selected_test_threshold_exceeded")
            if self.release_only:
                reasons.append("release_only_direct_validation")
        if self.covered_obligation_count > policy.broad_obligation_threshold:
            reasons.append("broad_parent_evidence")
        if self.background and self.progress_only:
            reasons.append("background_progress_only")
        return tuple(reasons)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "target_kind": self.target_kind,
            "parent_id": self.parent_id,
            "evidence_id": self.evidence_id,
            "source_model_id": self.source_model_id,
            "source_model_path": self.source_model_path,
            "estimated_state_count": self.estimated_state_count,
            "observed_state_count": self.observed_state_count,
            "processed_state_count": self.processed_state_count,
            "pending_state_count": self.pending_state_count,
            "duration_seconds": self.duration_seconds,
            "test_count": self.test_count,
            "selected_count": self.selected_count,
            "covered_obligation_count": self.covered_obligation_count,
            "separable_areas": self.separable_areas,
            "background": self.background,
            "progress_only": self.progress_only,
            "release_only": self.release_only,
            "suggested_child_ids": list(self.suggested_child_ids),
            "covered_partition_item_ids": list(self.covered_partition_item_ids),
            "state_owner_fields": list(self.state_owner_fields),
            "side_effect_owner_fields": list(self.side_effect_owner_fields),
            "split_gate_id": self.split_gate_id,
            "split_review_current": self.split_review_current,
            "split_confidence": self.split_confidence,
            "scoped_reasons": list(self.scoped_reasons),
            "rationale": self.rationale,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class AutoSplitPlan:
    """Review plan for automatic ModelMesh/TestMesh split requirements."""

    plan_id: str
    candidates: tuple[AutoSplitCandidate, ...] = ()
    policy: AutoSplitPolicy = field(default_factory=AutoSplitPolicy)
    allow_scoped_confidence: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "candidates", tuple(self.candidates))

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "policy": self.policy.to_dict(),
            "allow_scoped_confidence": self.allow_scoped_confidence,
        }


@dataclass(frozen=True)
class AutoSplitFinding:
    """One automatic split diagnostic finding."""

    code: str
    message: str
    severity: str = "blocker"
    candidate_id: str = ""
    target_route: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "candidate_id", str(self.candidate_id))
        object.__setattr__(self, "target_route", str(self.target_route))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "candidate_id": self.candidate_id,
            "target_route": self.target_route,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class AutoSplitReport:
    """Structured auto split review result."""

    ok: bool
    plan_id: str
    decision: str
    findings: tuple[AutoSplitFinding, ...] = ()
    required_model_candidate_ids: tuple[str, ...] = ()
    required_test_candidate_ids: tuple[str, ...] = ()
    model_target_split_derivations: tuple[ModelTargetSplitDerivation, ...] = ()
    test_target_split_derivations: tuple[TestTargetSplitDerivation, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "required_model_candidate_ids", _as_tuple(self.required_model_candidate_ids))
        object.__setattr__(self, "required_test_candidate_ids", _as_tuple(self.required_test_candidate_ids))
        object.__setattr__(self, "model_target_split_derivations", tuple(self.model_target_split_derivations))
        object.__setattr__(self, "test_target_split_derivations", tuple(self.test_target_split_derivations))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: plan={self.plan_id} decision={self.decision} findings={len(self.findings)}",
            )

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard auto model/test split review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"plan: {self.plan_id}",
            f"decision: {self.decision}",
            f"model split candidates: {', '.join(self.required_model_candidate_ids) or '(none)'}",
            f"test split candidates: {', '.join(self.required_test_candidate_ids) or '(none)'}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"candidate: {finding.candidate_id or '(none)'}",
                    f"route: {finding.target_route or '(none)'}",
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
            "required_model_candidate_ids": list(self.required_model_candidate_ids),
            "required_test_candidate_ids": list(self.required_test_candidate_ids),
            "model_target_split_derivations": [
                derivation.to_dict() for derivation in self.model_target_split_derivations
            ],
            "test_target_split_derivations": [
                derivation.to_dict() for derivation in self.test_target_split_derivations
            ],
            "summary": self.summary,
        }


def _finding(
    code: str,
    message: str,
    *,
    candidate: AutoSplitCandidate,
    severity: str = "blocker",
    metadata: Mapping[str, Any] | None = None,
) -> AutoSplitFinding:
    return AutoSplitFinding(
        code,
        message,
        severity=severity,
        candidate_id=candidate.candidate_id,
        target_route=candidate.target_route(),
        metadata=metadata or {},
    )


def _decision_for(
    findings: Sequence[AutoSplitFinding],
    required_model_ids: Sequence[str],
    required_test_ids: Sequence[str],
) -> tuple[str, bool]:
    blockers = tuple(finding for finding in findings if finding.severity == "blocker")
    if not blockers:
        if findings:
            return AUTO_SPLIT_DECISION_SCOPED, True
        if required_model_ids or required_test_ids:
            return AUTO_SPLIT_DECISION_FULL, True
        return AUTO_SPLIT_DECISION_NOT_REQUIRED, True
    codes = {finding.code for finding in blockers}
    if "missing_auto_split_target_derivation" in codes:
        return AUTO_SPLIT_DECISION_TARGET_REQUIRED, False
    if any(code.startswith("auto_model_") for code in codes):
        return AUTO_SPLIT_DECISION_MODEL_REQUIRED, False
    if any(code.startswith("auto_test_") for code in codes):
        return AUTO_SPLIT_DECISION_TEST_REQUIRED, False
    return blockers[0].code, False


def _model_derivation(candidate: AutoSplitCandidate) -> ModelTargetSplitDerivation:
    return ModelTargetSplitDerivation(
        candidate.source_model_id or candidate.parent_id or candidate.candidate_id,
        target_child_model_ids=candidate.suggested_child_ids,
        covered_partition_item_ids=candidate.covered_partition_item_ids,
        state_owner_fields=candidate.state_owner_fields,
        side_effect_owner_fields=candidate.side_effect_owner_fields,
        source_model_path=candidate.source_model_path,
        rationale=candidate.rationale or "automatic split diagnostic exceeded direct model evidence bounds",
    )


def _test_derivation(candidate: AutoSplitCandidate) -> TestTargetSplitDerivation:
    return TestTargetSplitDerivation(
        candidate.source_model_id or candidate.parent_id or candidate.candidate_id,
        target_suite_ids=candidate.suggested_child_ids,
        covered_partition_item_ids=candidate.covered_partition_item_ids,
        state_owner_fields=candidate.state_owner_fields,
        side_effect_owner_fields=candidate.side_effect_owner_fields,
        source_model_path=candidate.source_model_path,
        rationale=candidate.rationale or "automatic split diagnostic exceeded direct validation evidence bounds",
    )


def review_auto_mesh_splits(plan: AutoSplitPlan) -> AutoSplitReport:
    """Review whether direct model/test evidence must route through mesh splits."""

    findings: list[AutoSplitFinding] = []
    required_model_ids: list[str] = []
    required_test_ids: list[str] = []
    model_derivations: list[ModelTargetSplitDerivation] = []
    test_derivations: list[TestTargetSplitDerivation] = []

    seen: set[str] = set()
    for candidate in plan.candidates:
        if candidate.candidate_id in seen:
            findings.append(
                AutoSplitFinding(
                    "duplicate_auto_split_candidate_id",
                    f"auto split candidate id {candidate.candidate_id!r} appears more than once",
                    candidate_id=candidate.candidate_id,
                )
            )
        seen.add(candidate.candidate_id)

        reasons = candidate.split_reasons(plan.policy)
        if not reasons:
            continue

        if candidate.target_kind == AUTO_SPLIT_TARGET_MODEL:
            required_model_ids.append(candidate.candidate_id)
            prefix = "auto_model"
        elif candidate.target_kind == AUTO_SPLIT_TARGET_TEST:
            required_test_ids.append(candidate.candidate_id)
            prefix = "auto_test"
        else:
            findings.append(
                AutoSplitFinding(
                    "unknown_auto_split_target_kind",
                    f"unknown auto split target kind {candidate.target_kind!r}",
                    candidate_id=candidate.candidate_id,
                    metadata=candidate.to_dict(),
                )
            )
            continue

        if candidate.suggested_child_ids and candidate.covered_partition_item_ids:
            if candidate.target_kind == AUTO_SPLIT_TARGET_MODEL:
                model_derivations.append(_model_derivation(candidate))
            else:
                test_derivations.append(_test_derivation(candidate))
        else:
            findings.append(
                _finding(
                    "missing_auto_split_target_derivation",
                    "required split has no suggested child ids or covered partition items",
                    candidate=candidate,
                    metadata={"split_reasons": reasons, "candidate": candidate.to_dict()},
                )
            )

        if not candidate.split_review_current:
            findings.append(
                _finding(
                    f"{prefix}_split_not_current",
                    "required mesh split review is missing or stale",
                    candidate=candidate,
                    metadata={"split_reasons": reasons, "candidate": candidate.to_dict()},
                )
            )
        elif candidate.split_confidence == AUTO_SPLIT_CONFIDENCE_BLOCKED:
            findings.append(
                _finding(
                    f"{prefix}_split_blocked",
                    "required mesh split review is blocked",
                    candidate=candidate,
                    metadata={"split_reasons": reasons, "candidate": candidate.to_dict()},
                )
            )
        elif candidate.split_confidence == AUTO_SPLIT_CONFIDENCE_SCOPED or candidate.scoped_reasons:
            severity = "warning" if plan.allow_scoped_confidence else "blocker"
            findings.append(
                _finding(
                    f"{prefix}_split_scoped_confidence",
                    "required mesh split review is explicitly scoped",
                    candidate=candidate,
                    severity=severity,
                    metadata={
                        "split_reasons": reasons,
                        "scoped_reasons": candidate.scoped_reasons,
                        "candidate": candidate.to_dict(),
                    },
                )
            )

    decision, ok = _decision_for(findings, required_model_ids, required_test_ids)
    return AutoSplitReport(
        ok=ok,
        plan_id=plan.plan_id,
        decision=decision,
        findings=tuple(findings),
        required_model_candidate_ids=tuple(required_model_ids),
        required_test_candidate_ids=tuple(required_test_ids),
        model_target_split_derivations=tuple(model_derivations),
        test_target_split_derivations=tuple(test_derivations),
    )


__all__ = [
    "AUTO_SPLIT_CONFIDENCE_BLOCKED",
    "AUTO_SPLIT_CONFIDENCE_FULL",
    "AUTO_SPLIT_CONFIDENCE_SCOPED",
    "AUTO_SPLIT_DECISION_FULL",
    "AUTO_SPLIT_DECISION_MODEL_REQUIRED",
    "AUTO_SPLIT_DECISION_NOT_REQUIRED",
    "AUTO_SPLIT_DECISION_SCOPED",
    "AUTO_SPLIT_DECISION_TARGET_REQUIRED",
    "AUTO_SPLIT_DECISION_TEST_REQUIRED",
    "AUTO_SPLIT_ROUTE_MODEL_MESH",
    "AUTO_SPLIT_ROUTE_TEST_MESH",
    "AUTO_SPLIT_TARGET_MODEL",
    "AUTO_SPLIT_TARGET_TEST",
    "AutoSplitCandidate",
    "AutoSplitFinding",
    "AutoSplitPlan",
    "AutoSplitPolicy",
    "AutoSplitReport",
    "review_auto_mesh_splits",
]
