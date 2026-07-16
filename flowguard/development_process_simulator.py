"""Single front-door development-process simulator routing helpers.

The simulator classifies development-process work before detailed route
reviews. It does not replace PlanDetailing, AgentWorkflowRehearsal, or
DevelopmentProcessFlow evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .export import to_jsonable


DEVELOPMENT_PROCESS_SIMULATOR_ROUTE = "development_process_simulator"
DEVELOPMENT_PROCESS_FRONT_DOOR_SKILL = "flowguard-development-process-flow"

SIMULATOR_MODE_PLAN_DETAILING = "plan_detailing"
SIMULATOR_MODE_STRATEGY_SELECTION = "strategy_selection"
SIMULATOR_MODE_AGENT_WORKFLOW = "agent_workflow"
SIMULATOR_MODE_EXECUTION_FRESHNESS = "execution_freshness"
SIMULATOR_MODES = (
    SIMULATOR_MODE_PLAN_DETAILING,
    SIMULATOR_MODE_STRATEGY_SELECTION,
    SIMULATOR_MODE_AGENT_WORKFLOW,
    SIMULATOR_MODE_EXECUTION_FRESHNESS,
)

SIMULATOR_MODE_TO_REVIEW = {
    SIMULATOR_MODE_PLAN_DETAILING: "review_plan_detail",
    SIMULATOR_MODE_STRATEGY_SELECTION: "review_process_optimization",
    SIMULATOR_MODE_AGENT_WORKFLOW: "review_agent_workflow_rehearsal",
    SIMULATOR_MODE_EXECUTION_FRESHNESS: "review_development_process_flow",
}

SIMULATOR_MODE_TO_DELEGATED_SKILL = {
    SIMULATOR_MODE_PLAN_DETAILING: "flowguard-plan-detailing-compiler",
    SIMULATOR_MODE_STRATEGY_SELECTION: DEVELOPMENT_PROCESS_FRONT_DOOR_SKILL,
    SIMULATOR_MODE_AGENT_WORKFLOW: "flowguard-agent-workflow-rehearsal",
    SIMULATOR_MODE_EXECUTION_FRESHNESS: DEVELOPMENT_PROCESS_FRONT_DOOR_SKILL,
}

SIMULATOR_STATUS_PASS = "pass"
SIMULATOR_STATUS_SCOPED = "scoped"
SIMULATOR_STATUS_NEEDS_REVISION = "needs_revision"
SIMULATOR_STATUS_BLOCKED = "blocked"
SIMULATOR_STATUS_SKIPPED = "skipped_with_reason"
SIMULATOR_STATUSES = (
    SIMULATOR_STATUS_PASS,
    SIMULATOR_STATUS_SCOPED,
    SIMULATOR_STATUS_NEEDS_REVISION,
    SIMULATOR_STATUS_BLOCKED,
    SIMULATOR_STATUS_SKIPPED,
)

SIMULATOR_FINDING_INFO = "info"
SIMULATOR_FINDING_SCOPED = "scoped"
SIMULATOR_FINDING_NEEDS_REVISION = "needs_revision"
SIMULATOR_FINDING_BLOCKED = "blocked"

_PROCESS_OPTIMIZATION_REASONS = {
    "explicit_request",
    "multiple_equivalent_routes",
    "material_rework_risk",
    "diagnostic_boundary_choice",
}


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


@dataclass(frozen=True)
class DevelopmentProcessSimulationRequest:
    """A front-door routing request for development-process simulation."""

    request_id: str
    task_summary: str = ""
    rough_plan: bool = False
    plan_discussion: bool = False
    plan_detail_requested: bool = False
    multiple_skills_or_tools: bool = False
    process_optimization_reasons: tuple[str, ...] = ()
    external_side_effects: bool = False
    staged_validation: bool = False
    implementation_work: bool = False
    validation_freshness_risk: bool = False
    install_sync: bool = False
    shadow_workspace_sync: bool = False
    local_git_sync: bool = False
    release_archive_or_publish: bool = False
    final_claim_requested: bool = False
    task_trivial: bool = False
    explicit_plan_detailing_skill: bool = False
    explicit_agent_workflow_skill: bool = False
    explicit_development_process_skill: bool = False
    plan_detail_evidence_ids: tuple[str, ...] = ()
    process_optimization_evidence_ids: tuple[str, ...] = ()
    agent_workflow_evidence_ids: tuple[str, ...] = ()
    execution_freshness_evidence_ids: tuple[str, ...] = ()
    accepted_scope: str = ""
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", str(self.request_id))
        object.__setattr__(self, "task_summary", str(self.task_summary))
        object.__setattr__(
            self,
            "process_optimization_reasons",
            _as_tuple(self.process_optimization_reasons),
        )
        object.__setattr__(self, "plan_detail_evidence_ids", _as_tuple(self.plan_detail_evidence_ids))
        object.__setattr__(
            self,
            "process_optimization_evidence_ids",
            _as_tuple(self.process_optimization_evidence_ids),
        )
        object.__setattr__(
            self,
            "agent_workflow_evidence_ids",
            _as_tuple(self.agent_workflow_evidence_ids),
        )
        object.__setattr__(
            self,
            "execution_freshness_evidence_ids",
            _as_tuple(self.execution_freshness_evidence_ids),
        )
        object.__setattr__(self, "accepted_scope", str(self.accepted_scope))
        object.__setattr__(
            self,
            "metadata",
            {} if self.metadata is None else dict(self.metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "task_summary": self.task_summary,
            "rough_plan": self.rough_plan,
            "plan_discussion": self.plan_discussion,
            "plan_detail_requested": self.plan_detail_requested,
            "multiple_skills_or_tools": self.multiple_skills_or_tools,
            "process_optimization_reasons": list(self.process_optimization_reasons),
            "external_side_effects": self.external_side_effects,
            "staged_validation": self.staged_validation,
            "implementation_work": self.implementation_work,
            "validation_freshness_risk": self.validation_freshness_risk,
            "install_sync": self.install_sync,
            "shadow_workspace_sync": self.shadow_workspace_sync,
            "local_git_sync": self.local_git_sync,
            "release_archive_or_publish": self.release_archive_or_publish,
            "final_claim_requested": self.final_claim_requested,
            "task_trivial": self.task_trivial,
            "explicit_plan_detailing_skill": self.explicit_plan_detailing_skill,
            "explicit_agent_workflow_skill": self.explicit_agent_workflow_skill,
            "explicit_development_process_skill": self.explicit_development_process_skill,
            "plan_detail_evidence_ids": list(self.plan_detail_evidence_ids),
            "process_optimization_evidence_ids": list(self.process_optimization_evidence_ids),
            "agent_workflow_evidence_ids": list(self.agent_workflow_evidence_ids),
            "execution_freshness_evidence_ids": list(self.execution_freshness_evidence_ids),
            "accepted_scope": self.accepted_scope,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class DevelopmentProcessModeDecision:
    """One selected internal simulator mode and its downstream evidence owner."""

    mode: str
    delegated_skill: str
    required_review: str
    reason: str
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", str(self.mode))
        object.__setattr__(self, "delegated_skill", str(self.delegated_skill))
        object.__setattr__(self, "required_review", str(self.required_review))
        object.__setattr__(self, "reason", str(self.reason))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "delegated_skill": self.delegated_skill,
            "required_review": self.required_review,
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
        }


@dataclass(frozen=True)
class DevelopmentProcessSimulatorFinding:
    """A simulator route finding that constrains the claim boundary."""

    code: str
    message: str
    severity: str = SIMULATOR_FINDING_INFO
    mode: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "mode", str(self.mode))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "mode": self.mode,
        }


@dataclass(frozen=True)
class DevelopmentProcessSimulatorReport:
    """Front-door simulator result."""

    request_id: str
    front_door_skill: str
    selected_modes: tuple[str, ...]
    mode_decisions: tuple[DevelopmentProcessModeDecision, ...]
    required_reviews: tuple[str, ...]
    claim_boundary: str
    status: str
    findings: tuple[DevelopmentProcessSimulatorFinding, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status in {SIMULATOR_STATUS_PASS, SIMULATOR_STATUS_SKIPPED}

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "front_door_skill": self.front_door_skill,
            "selected_modes": list(self.selected_modes),
            "mode_decisions": [decision.to_dict() for decision in self.mode_decisions],
            "required_reviews": list(self.required_reviews),
            "claim_boundary": self.claim_boundary,
            "status": self.status,
            "ok": self.ok,
            "findings": [finding.to_dict() for finding in self.findings],
        }

    def format_text(self) -> str:
        lines = [
            "FlowGuard development process simulator",
            f"request: {self.request_id}",
            f"front door: {self.front_door_skill}",
            f"status: {self.status}",
            f"modes: {', '.join(self.selected_modes) if self.selected_modes else '(none)'}",
            f"claim boundary: {self.claim_boundary}",
        ]
        if self.mode_decisions:
            lines.append("mode decisions:")
            for decision in self.mode_decisions:
                evidence = ", ".join(decision.evidence_ids) if decision.evidence_ids else "evidence required"
                lines.append(
                    f"- {decision.mode}: {decision.required_review} via {decision.delegated_skill} ({evidence})"
                )
        if self.findings:
            lines.append("findings:")
            for finding in self.findings:
                mode = f" [{finding.mode}]" if finding.mode else ""
                lines.append(f"- {finding.severity}: {finding.code}{mode} - {finding.message}")
        return "\n".join(lines)


def _select_modes(request: DevelopmentProcessSimulationRequest) -> list[DevelopmentProcessModeDecision]:
    decisions: list[DevelopmentProcessModeDecision] = []

    if request.rough_plan or request.plan_discussion or request.plan_detail_requested:
        decisions.append(
            DevelopmentProcessModeDecision(
                SIMULATOR_MODE_PLAN_DETAILING,
                SIMULATOR_MODE_TO_DELEGATED_SKILL[SIMULATOR_MODE_PLAN_DETAILING],
                SIMULATOR_MODE_TO_REVIEW[SIMULATOR_MODE_PLAN_DETAILING],
                "rough or under-specified plan needs structured detail rows",
                request.plan_detail_evidence_ids,
            )
        )

    if request.process_optimization_reasons:
        decisions.append(
            DevelopmentProcessModeDecision(
                SIMULATOR_MODE_STRATEGY_SELECTION,
                SIMULATOR_MODE_TO_DELEGATED_SKILL[SIMULATOR_MODE_STRATEGY_SELECTION],
                SIMULATOR_MODE_TO_REVIEW[SIMULATOR_MODE_STRATEGY_SELECTION],
                "several outcome-equivalent process sequences or material repeated-work/information tradeoffs need comparison",
                request.process_optimization_evidence_ids,
            )
        )

    if request.multiple_skills_or_tools or request.external_side_effects:
        decisions.append(
            DevelopmentProcessModeDecision(
                SIMULATOR_MODE_AGENT_WORKFLOW,
                SIMULATOR_MODE_TO_DELEGATED_SKILL[SIMULATOR_MODE_AGENT_WORKFLOW],
                SIMULATOR_MODE_TO_REVIEW[SIMULATOR_MODE_AGENT_WORKFLOW],
                "skill/tool/plugin order, skipped candidates, side effects, or gates affect the outcome",
                request.agent_workflow_evidence_ids,
            )
        )

    if (
        request.staged_validation
        or request.implementation_work
        or request.validation_freshness_risk
        or request.install_sync
        or request.shadow_workspace_sync
        or request.local_git_sync
        or request.release_archive_or_publish
        or request.final_claim_requested
        or request.explicit_development_process_skill
    ):
        decisions.append(
            DevelopmentProcessModeDecision(
                SIMULATOR_MODE_EXECUTION_FRESHNESS,
                SIMULATOR_MODE_TO_DELEGATED_SKILL[SIMULATOR_MODE_EXECUTION_FRESHNESS],
                SIMULATOR_MODE_TO_REVIEW[SIMULATOR_MODE_EXECUTION_FRESHNESS],
                "artifact versions, validation freshness, sync, or final claim confidence matters",
                request.execution_freshness_evidence_ids,
            )
        )

    return decisions


def _status_from_findings(
    request: DevelopmentProcessSimulationRequest,
    findings: Sequence[DevelopmentProcessSimulatorFinding],
    decisions: Sequence[DevelopmentProcessModeDecision],
) -> str:
    if request.task_trivial and not decisions:
        return SIMULATOR_STATUS_SKIPPED
    severities = {finding.severity for finding in findings}
    if SIMULATOR_FINDING_BLOCKED in severities:
        return SIMULATOR_STATUS_BLOCKED
    if SIMULATOR_FINDING_NEEDS_REVISION in severities:
        return SIMULATOR_STATUS_NEEDS_REVISION
    if SIMULATOR_FINDING_SCOPED in severities:
        return SIMULATOR_STATUS_SCOPED
    return SIMULATOR_STATUS_PASS


def review_development_process_simulator(
    request: DevelopmentProcessSimulationRequest,
) -> DevelopmentProcessSimulatorReport:
    """Classify a development-process request into simulator modes."""

    decisions = tuple(_select_modes(request))
    selected_modes = tuple(decision.mode for decision in decisions)
    required_reviews = _dedupe(tuple(decision.required_review for decision in decisions))
    findings: list[DevelopmentProcessSimulatorFinding] = []

    invalid_optimization_reasons = sorted(
        set(request.process_optimization_reasons) - _PROCESS_OPTIMIZATION_REASONS
    )
    if invalid_optimization_reasons or len(set(request.process_optimization_reasons)) != len(
        request.process_optimization_reasons
    ):
        findings.append(
            DevelopmentProcessSimulatorFinding(
                "process_optimization_reason_invalid",
                "process optimization reasons must be unique stable reason ids",
                SIMULATOR_FINDING_BLOCKED,
                SIMULATOR_MODE_STRATEGY_SELECTION,
            )
        )

    if not decisions and not request.task_trivial:
        findings.append(
            DevelopmentProcessSimulatorFinding(
                "no_development_process_mode_selected",
                "non-trivial development-process request did not select a simulator mode",
                SIMULATOR_FINDING_NEEDS_REVISION,
            )
        )

    if request.explicit_plan_detailing_skill and SIMULATOR_MODE_PLAN_DETAILING not in selected_modes:
        findings.append(
            DevelopmentProcessSimulatorFinding(
                "explicit_plan_detailing_without_mode",
                "explicit PlanDetailing use must still record the plan_detailing mode boundary",
                SIMULATOR_FINDING_NEEDS_REVISION,
                SIMULATOR_MODE_PLAN_DETAILING,
            )
        )

    if request.explicit_agent_workflow_skill and SIMULATOR_MODE_AGENT_WORKFLOW not in selected_modes:
        findings.append(
            DevelopmentProcessSimulatorFinding(
                "explicit_agent_workflow_without_mode",
                "explicit AgentWorkflowRehearsal use must still record the agent_workflow mode boundary",
                SIMULATOR_FINDING_NEEDS_REVISION,
                SIMULATOR_MODE_AGENT_WORKFLOW,
            )
        )

    if request.final_claim_requested:
        for decision in decisions:
            if decision.mode == SIMULATOR_MODE_EXECUTION_FRESHNESS:
                continue
            if not decision.evidence_ids:
                findings.append(
                    DevelopmentProcessSimulatorFinding(
                        "final_claim_missing_mode_evidence",
                        "final claims need current downstream evidence for each selected mode",
                        SIMULATOR_FINDING_SCOPED,
                        decision.mode,
                    )
                )
        if SIMULATOR_MODE_EXECUTION_FRESHNESS not in selected_modes:
            findings.append(
                DevelopmentProcessSimulatorFinding(
                    "final_claim_missing_execution_freshness",
                    "final done/release/archive/publish confidence requires execution_freshness mode",
                    SIMULATOR_FINDING_BLOCKED,
                    SIMULATOR_MODE_EXECUTION_FRESHNESS,
                )
            )
        elif not request.execution_freshness_evidence_ids:
            findings.append(
                DevelopmentProcessSimulatorFinding(
                    "final_claim_missing_execution_evidence",
                    "final claims need current DevelopmentProcessFlow freshness evidence",
                    SIMULATOR_FINDING_SCOPED,
                    SIMULATOR_MODE_EXECUTION_FRESHNESS,
                )
            )

    if request.task_trivial and decisions:
        findings.append(
            DevelopmentProcessSimulatorFinding(
                "trivial_task_overtriggered_development_simulator",
                "trivial work should skip the development simulator with a reason",
                SIMULATOR_FINDING_SCOPED,
            )
        )

    status = _status_from_findings(request, findings, decisions)
    if status == SIMULATOR_STATUS_SKIPPED:
        claim_boundary = "skipped_with_reason"
    elif findings:
        claim_boundary = "scoped_or_blocked_until_selected_mode_evidence_is_current"
    else:
        claim_boundary = "mode_selection_ready_downstream_reviews_required"

    return DevelopmentProcessSimulatorReport(
        request_id=request.request_id,
        front_door_skill=DEVELOPMENT_PROCESS_FRONT_DOOR_SKILL,
        selected_modes=selected_modes,
        mode_decisions=decisions,
        required_reviews=required_reviews,
        claim_boundary=claim_boundary,
        status=status,
        findings=tuple(findings),
    )


__all__ = [
    "DEVELOPMENT_PROCESS_FRONT_DOOR_SKILL",
    "DEVELOPMENT_PROCESS_SIMULATOR_ROUTE",
    "DevelopmentProcessModeDecision",
    "DevelopmentProcessSimulationRequest",
    "DevelopmentProcessSimulatorFinding",
    "DevelopmentProcessSimulatorReport",
    "SIMULATOR_FINDING_BLOCKED",
    "SIMULATOR_FINDING_INFO",
    "SIMULATOR_FINDING_NEEDS_REVISION",
    "SIMULATOR_FINDING_SCOPED",
    "SIMULATOR_MODE_AGENT_WORKFLOW",
    "SIMULATOR_MODE_EXECUTION_FRESHNESS",
    "SIMULATOR_MODE_PLAN_DETAILING",
    "SIMULATOR_MODE_STRATEGY_SELECTION",
    "SIMULATOR_MODES",
    "SIMULATOR_MODE_TO_DELEGATED_SKILL",
    "SIMULATOR_MODE_TO_REVIEW",
    "SIMULATOR_STATUS_BLOCKED",
    "SIMULATOR_STATUS_NEEDS_REVISION",
    "SIMULATOR_STATUS_PASS",
    "SIMULATOR_STATUS_SCOPED",
    "SIMULATOR_STATUS_SKIPPED",
    "SIMULATOR_STATUSES",
    "review_development_process_simulator",
]
