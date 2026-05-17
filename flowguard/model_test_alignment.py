"""Model obligation to test evidence alignment helpers.

Model-Test Alignment reviews whether explicit FlowGuard model obligations and
ordinary test evidence describe the same behavioral surface. It intentionally
does not read TestMesh, StructureMesh, or ModelMesh reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable


TEST_STATUS_PASSED = "passed"
TEST_STATUS_FAILED = "failed"
TEST_STATUS_TIMEOUT = "timeout"
TEST_STATUS_SKIPPED = "skipped"
TEST_STATUS_NOT_RUN = "not_run"
TEST_STATUS_RUNNING = "running"
TEST_STATUS_ERROR = "error"

PASSING_STATUSES = {TEST_STATUS_PASSED}
NON_PASSING_STATUSES = {
    TEST_STATUS_FAILED,
    TEST_STATUS_TIMEOUT,
    TEST_STATUS_SKIPPED,
    TEST_STATUS_NOT_RUN,
    TEST_STATUS_RUNNING,
    TEST_STATUS_ERROR,
}

TEST_KIND_HAPPY_PATH = "happy_path"
TEST_KIND_FAILURE_PATH = "failure_path"
TEST_KIND_EDGE_PATH = "edge_path"
TEST_KIND_NEGATIVE_PATH = "negative_path"
TEST_KIND_REPLAY = "replay"


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


@dataclass(frozen=True)
class ModelObligation:
    """One scenario, invariant, hazard, transition, or contract the model owns."""

    obligation_id: str
    obligation_type: str = "scenario"
    description: str = ""
    required: bool = True
    required_test_kinds: tuple[str, ...] = ()
    risk_level: str = "normal"
    allow_shared_evidence: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "obligation_id", str(self.obligation_id))
        object.__setattr__(self, "obligation_type", str(self.obligation_type))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "required_test_kinds", _as_tuple(self.required_test_kinds))
        object.__setattr__(self, "risk_level", str(self.risk_level))

    def to_dict(self) -> dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "obligation_type": self.obligation_type,
            "description": self.description,
            "required": self.required,
            "required_test_kinds": list(self.required_test_kinds),
            "risk_level": self.risk_level,
            "allow_shared_evidence": self.allow_shared_evidence,
        }


@dataclass(frozen=True)
class TestEvidence:
    """Plain evidence from one test, command, replay, or manual validation."""

    evidence_id: str
    test_name: str = ""
    path: str = ""
    command: str = ""
    result_status: str = TEST_STATUS_NOT_RUN
    evidence_current: bool = True
    test_kind: str = TEST_KIND_HAPPY_PATH
    covered_obligations: tuple[str, ...] = ()
    stale_reasons: tuple[str, ...] = ()
    overclaims_model_confidence: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "test_name", str(self.test_name))
        object.__setattr__(self, "path", str(self.path))
        object.__setattr__(self, "command", str(self.command))
        object.__setattr__(self, "result_status", str(self.result_status))
        object.__setattr__(self, "test_kind", str(self.test_kind))
        object.__setattr__(self, "covered_obligations", _as_tuple(self.covered_obligations))
        object.__setattr__(self, "stale_reasons", _as_tuple(self.stale_reasons))

    def has_current_pass(self) -> bool:
        return self.result_status in PASSING_STATUSES and self.evidence_current

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "test_name": self.test_name,
            "path": self.path,
            "command": self.command,
            "result_status": self.result_status,
            "evidence_current": self.evidence_current,
            "test_kind": self.test_kind,
            "covered_obligations": list(self.covered_obligations),
            "stale_reasons": list(self.stale_reasons),
            "overclaims_model_confidence": self.overclaims_model_confidence,
        }


@dataclass(frozen=True)
class ModelTestAlignmentPlan:
    """A direct model-obligation and test-evidence alignment review plan."""

    model_id: str
    obligations: tuple[ModelObligation, ...] = ()
    test_evidence: tuple[TestEvidence, ...] = ()
    allow_orphan_tests: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "obligations", tuple(self.obligations))
        object.__setattr__(self, "test_evidence", tuple(self.test_evidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "obligations": [obligation.to_dict() for obligation in self.obligations],
            "test_evidence": [evidence.to_dict() for evidence in self.test_evidence],
            "allow_orphan_tests": self.allow_orphan_tests,
        }


@dataclass(frozen=True)
class ModelTestAlignmentFinding:
    """One model-test alignment gap, overlap, stale evidence, or overclaim."""

    code: str
    message: str
    severity: str = "blocker"
    obligation_id: str = ""
    evidence_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "obligation_id", str(self.obligation_id))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "obligation_id": self.obligation_id,
            "evidence_id": self.evidence_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ModelTestAlignmentReport:
    """Structured outcome of a model-test alignment review."""

    ok: bool
    model_id: str
    decision: str
    findings: tuple[ModelTestAlignmentFinding, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "findings", tuple(self.findings))
        if not self.summary:
            status = "OK" if self.ok else "BLOCKED"
            object.__setattr__(
                self,
                "summary",
                f"{status}: model={self.model_id} decision={self.decision} findings={len(self.findings)}",
            )

    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard model-test alignment review ===",
            f"status: {'OK' if self.ok else 'BLOCKED'}",
            f"model: {self.model_id}",
            f"decision: {self.decision}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.code}",
                    f"severity: {finding.severity}",
                    f"obligation: {finding.obligation_id or '(none)'}",
                    f"evidence: {finding.evidence_id or '(none)'}",
                    f"message: {finding.message}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "model_id": self.model_id,
            "decision": self.decision,
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
        }


def _blocker_findings(
    findings: Sequence[ModelTestAlignmentFinding],
) -> tuple[ModelTestAlignmentFinding, ...]:
    return tuple(finding for finding in findings if finding.severity == "blocker")


def _decision_for_findings(findings: Sequence[ModelTestAlignmentFinding]) -> str:
    blockers = _blocker_findings(findings)
    if not blockers:
        return "model_test_alignment_green"
    priority = [
        ("duplicate_model_obligation", "invalid_alignment_plan"),
        ("missing_test_evidence", "missing_test_evidence"),
        ("missing_required_test_kind", "missing_required_test_kind"),
        ("duplicate_test_evidence_owner", "duplicate_test_evidence_owner"),
        ("orphan_test_evidence", "orphan_test_evidence"),
        ("unknown_obligation_reference", "orphan_test_evidence"),
        ("test_evidence_not_passing", "test_evidence_not_passing"),
        ("stale_test_evidence", "stale_test_evidence"),
        ("test_overclaims_model_confidence", "test_overclaims_model_confidence"),
    ]
    codes = {finding.code for finding in blockers}
    for code, decision in priority:
        if code in codes:
            return decision
    return "model_test_alignment_blocked"


def _obligation_index(plan: ModelTestAlignmentPlan) -> tuple[dict[str, ModelObligation], list[ModelTestAlignmentFinding]]:
    obligations_by_id: dict[str, ModelObligation] = {}
    findings: list[ModelTestAlignmentFinding] = []
    for obligation in plan.obligations:
        if obligation.obligation_id in obligations_by_id:
            findings.append(
                ModelTestAlignmentFinding(
                    "duplicate_model_obligation",
                    f"model obligation {obligation.obligation_id} is declared more than once",
                    obligation_id=obligation.obligation_id,
                    metadata=obligation.to_dict(),
                )
            )
            continue
        obligations_by_id[obligation.obligation_id] = obligation
    return obligations_by_id, findings


def _evidence_findings(
    plan: ModelTestAlignmentPlan,
    obligations_by_id: Mapping[str, ModelObligation],
) -> list[ModelTestAlignmentFinding]:
    findings: list[ModelTestAlignmentFinding] = []
    for evidence in plan.test_evidence:
        if not evidence.covered_obligations:
            severity = "warning" if plan.allow_orphan_tests else "blocker"
            findings.append(
                ModelTestAlignmentFinding(
                    "orphan_test_evidence",
                    f"test evidence {evidence.evidence_id} is not bound to any model obligation",
                    severity=severity,
                    evidence_id=evidence.evidence_id,
                    metadata=evidence.to_dict(),
                )
            )
        for obligation_id in evidence.covered_obligations:
            if obligation_id not in obligations_by_id:
                severity = "warning" if plan.allow_orphan_tests else "blocker"
                findings.append(
                    ModelTestAlignmentFinding(
                        "unknown_obligation_reference",
                        f"test evidence {evidence.evidence_id} references unknown model obligation {obligation_id}",
                        severity=severity,
                        obligation_id=obligation_id,
                        evidence_id=evidence.evidence_id,
                        metadata=evidence.to_dict(),
                    )
                )
        if evidence.result_status in NON_PASSING_STATUSES:
            findings.append(
                ModelTestAlignmentFinding(
                    "test_evidence_not_passing",
                    f"test evidence {evidence.evidence_id} status is {evidence.result_status}",
                    evidence_id=evidence.evidence_id,
                    metadata=evidence.to_dict(),
                )
            )
        if evidence.result_status not in PASSING_STATUSES | NON_PASSING_STATUSES:
            findings.append(
                ModelTestAlignmentFinding(
                    "test_evidence_not_passing",
                    f"test evidence {evidence.evidence_id} has unknown status {evidence.result_status}",
                    evidence_id=evidence.evidence_id,
                    metadata=evidence.to_dict(),
                )
            )
        if not evidence.evidence_current:
            findings.append(
                ModelTestAlignmentFinding(
                    "stale_test_evidence",
                    f"test evidence {evidence.evidence_id} is stale",
                    evidence_id=evidence.evidence_id,
                    metadata=evidence.to_dict(),
                )
            )
        if evidence.overclaims_model_confidence:
            findings.append(
                ModelTestAlignmentFinding(
                    "test_overclaims_model_confidence",
                    f"test evidence {evidence.evidence_id} claims more model confidence than its obligation bindings prove",
                    evidence_id=evidence.evidence_id,
                    metadata=evidence.to_dict(),
                )
            )
    return findings


def _passing_evidence_by_obligation(
    plan: ModelTestAlignmentPlan,
    obligations_by_id: Mapping[str, ModelObligation],
) -> dict[str, list[TestEvidence]]:
    result: dict[str, list[TestEvidence]] = {obligation_id: [] for obligation_id in obligations_by_id}
    for evidence in plan.test_evidence:
        if not evidence.has_current_pass():
            continue
        for obligation_id in evidence.covered_obligations:
            if obligation_id in result:
                result[obligation_id].append(evidence)
    return result


def _coverage_findings(
    obligations_by_id: Mapping[str, ModelObligation],
    passing_by_obligation: Mapping[str, Sequence[TestEvidence]],
) -> list[ModelTestAlignmentFinding]:
    findings: list[ModelTestAlignmentFinding] = []
    for obligation_id, obligation in obligations_by_id.items():
        passing = tuple(passing_by_obligation.get(obligation_id, ()))
        if obligation.required and not passing:
            findings.append(
                ModelTestAlignmentFinding(
                    "missing_test_evidence",
                    f"model obligation {obligation_id} has no current passing test evidence",
                    obligation_id=obligation_id,
                    metadata=obligation.to_dict(),
                )
            )
            continue

        kinds_present = {evidence.test_kind for evidence in passing}
        for required_kind in obligation.required_test_kinds:
            if required_kind not in kinds_present:
                findings.append(
                    ModelTestAlignmentFinding(
                        "missing_required_test_kind",
                        f"model obligation {obligation_id} lacks current passing {required_kind} test evidence",
                        obligation_id=obligation_id,
                        metadata={
                            "obligation": obligation.to_dict(),
                            "kinds_present": sorted(kinds_present),
                            "required_kind": required_kind,
                        },
                    )
                )

        if not obligation.allow_shared_evidence:
            evidence_by_kind: dict[str, list[TestEvidence]] = {}
            for evidence in passing:
                evidence_by_kind.setdefault(evidence.test_kind, []).append(evidence)
            for test_kind, same_kind in sorted(evidence_by_kind.items()):
                if len(same_kind) > 1:
                    findings.append(
                        ModelTestAlignmentFinding(
                            "duplicate_test_evidence_owner",
                            f"model obligation {obligation_id} has multiple current passing {test_kind} evidence owners",
                            obligation_id=obligation_id,
                            metadata={
                                "test_kind": test_kind,
                                "evidence_ids": [evidence.evidence_id for evidence in same_kind],
                            },
                        )
                    )
    return findings


def review_model_test_alignment(plan: ModelTestAlignmentPlan) -> ModelTestAlignmentReport:
    """Review explicit model obligations against plain test evidence."""

    obligations_by_id, findings = _obligation_index(plan)
    findings.extend(_evidence_findings(plan, obligations_by_id))
    passing_by_obligation = _passing_evidence_by_obligation(plan, obligations_by_id)
    findings.extend(_coverage_findings(obligations_by_id, passing_by_obligation))
    blockers = _blocker_findings(findings)
    return ModelTestAlignmentReport(
        ok=not blockers,
        model_id=plan.model_id,
        decision=_decision_for_findings(findings),
        findings=tuple(findings),
    )


__all__ = [
    "ModelObligation",
    "ModelTestAlignmentFinding",
    "ModelTestAlignmentPlan",
    "ModelTestAlignmentReport",
    "TestEvidence",
    "TEST_KIND_EDGE_PATH",
    "TEST_KIND_FAILURE_PATH",
    "TEST_KIND_HAPPY_PATH",
    "TEST_KIND_NEGATIVE_PATH",
    "TEST_KIND_REPLAY",
    "TEST_STATUS_ERROR",
    "TEST_STATUS_FAILED",
    "TEST_STATUS_NOT_RUN",
    "TEST_STATUS_PASSED",
    "TEST_STATUS_RUNNING",
    "TEST_STATUS_SKIPPED",
    "TEST_STATUS_TIMEOUT",
    "review_model_test_alignment",
]
