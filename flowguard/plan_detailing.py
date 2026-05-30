"""Plan-detailing compiler helpers for rough-to-checkable FlowGuard plans.

This module does not generate plans with an LLM and does not execute work.
It reviews structured rows that a human or AI drafted from a rough idea, then
projects those rows into existing FlowGuard routes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .agent_workflow_rehearsal import (
    AgentWorkflowPlan,
    AgentWorkflowStep,
    FINAL_CLAIM_FULL as AGENT_FINAL_CLAIM_FULL,
    FINAL_CLAIM_NONE as AGENT_FINAL_CLAIM_NONE,
    FINAL_CLAIM_SCOPED as AGENT_FINAL_CLAIM_SCOPED,
    SkillInventorySnapshot,
)
from .development_process_flow import (
    DevelopmentProcessPlan,
    FreshnessRule,
    ProcessAction,
    ProcessArtifact,
    ProcessEvidence,
    ValidationRequirement,
)
from .export import to_jsonable
from .plan_intake import (
    PlanIntakeCompletenessPlan,
    PlanIntakeRiskSurface,
    PlanSourceEvidence,
)
from .proof_artifact import ProofArtifactRef
from .step_contracts import STEP_SKIP_ALLOWED_WITH_REASON, STEP_SKIP_FORBIDDEN, WorkflowStepContract


PLAN_DETAIL_STATUS_PASS = "pass"
PLAN_DETAIL_STATUS_NEEDS_REVISION = "needs_revision"
PLAN_DETAIL_STATUS_SCOPED = "scoped"
PLAN_DETAIL_STATUS_BLOCKED = "blocked"

PLAN_DETAIL_STATUSES = (
    PLAN_DETAIL_STATUS_PASS,
    PLAN_DETAIL_STATUS_NEEDS_REVISION,
    PLAN_DETAIL_STATUS_SCOPED,
    PLAN_DETAIL_STATUS_BLOCKED,
)

PLAN_DETAIL_SEVERITY_INFO = "info"
PLAN_DETAIL_SEVERITY_NEEDS_REVISION = "needs_revision"
PLAN_DETAIL_SEVERITY_SCOPED = "scoped"
PLAN_DETAIL_SEVERITY_BLOCKED = "blocked"

PLAN_DETAIL_CLAIM_NONE = "none"
PLAN_DETAIL_CLAIM_SCOPED = "scoped"
PLAN_DETAIL_CLAIM_FULL = "full"
PLAN_DETAIL_CLAIM_BLOCKED = "blocked"

PLAN_DETAIL_CLAIMS = (
    PLAN_DETAIL_CLAIM_NONE,
    PLAN_DETAIL_CLAIM_SCOPED,
    PLAN_DETAIL_CLAIM_FULL,
    PLAN_DETAIL_CLAIM_BLOCKED,
)


def _as_tuple(values: Sequence[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,) if values else ()
    return tuple(str(value) for value in values if str(value))


def _as_mapping(values: Mapping[str, Any] | None) -> dict[str, Any]:
    if values is None:
        return {}
    return {str(key): value for key, value in values.items()}


def _status_from_findings(findings: Sequence["PlanDetailFinding"]) -> str:
    severities = {finding.severity for finding in findings}
    if PLAN_DETAIL_SEVERITY_BLOCKED in severities:
        return PLAN_DETAIL_STATUS_BLOCKED
    if PLAN_DETAIL_SEVERITY_NEEDS_REVISION in severities:
        return PLAN_DETAIL_STATUS_NEEDS_REVISION
    if PLAN_DETAIL_SEVERITY_SCOPED in severities:
        return PLAN_DETAIL_STATUS_SCOPED
    return PLAN_DETAIL_STATUS_PASS


def _claim_scope(value: str) -> str:
    text = str(value or PLAN_DETAIL_CLAIM_SCOPED)
    if text not in PLAN_DETAIL_CLAIMS:
        return PLAN_DETAIL_CLAIM_SCOPED
    return text


def _severity_for_claim(plan: "PlanDetail", *, scoped_ok: bool = False) -> str:
    if plan.final_claim == PLAN_DETAIL_CLAIM_FULL:
        return PLAN_DETAIL_SEVERITY_BLOCKED
    if scoped_ok or plan.exploratory:
        return PLAN_DETAIL_SEVERITY_SCOPED
    return PLAN_DETAIL_SEVERITY_NEEDS_REVISION


@dataclass(frozen=True)
class PlanDetailSource:
    """One source artifact used to create the plan detail."""

    source_id: str
    source_kind: str = "manual"
    current: bool = True
    supports_surface_ids: tuple[str, ...] = ()
    summary: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", str(self.source_id))
        object.__setattr__(self, "source_kind", str(self.source_kind))
        object.__setattr__(self, "supports_surface_ids", _as_tuple(self.supports_surface_ids))
        object.__setattr__(self, "summary", str(self.summary))
        object.__setattr__(self, "metadata", _as_mapping(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_kind": self.source_kind,
            "current": self.current,
            "supports_surface_ids": list(self.supports_surface_ids),
            "summary": self.summary,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class PlanDetailSurface:
    """One risk or scope surface the plan must handle or explicitly scope out."""

    surface_id: str
    surface_kind: str = "user_risk"
    description: str = ""
    in_scope: bool = True
    reviewed: bool = True
    included: bool = True
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
        object.__setattr__(self, "metadata", _as_mapping(self.metadata))

    def has_mapping(self) -> bool:
        return bool(self.source_ids or self.evidence_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface_id": self.surface_id,
            "surface_kind": self.surface_kind,
            "description": self.description,
            "in_scope": self.in_scope,
            "reviewed": self.reviewed,
            "included": self.included,
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
class PlanDetailArtifact:
    """One versioned artifact the plan reads, writes, validates, or invalidates."""

    artifact_id: str
    artifact_type: str = "code"
    current_version: str = "1"
    path: str = ""
    owner: str = ""
    upstream_artifact_ids: tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", str(self.artifact_id))
        object.__setattr__(self, "artifact_type", str(self.artifact_type))
        object.__setattr__(self, "current_version", str(self.current_version))
        object.__setattr__(self, "path", str(self.path))
        object.__setattr__(self, "owner", str(self.owner))
        object.__setattr__(self, "upstream_artifact_ids", _as_tuple(self.upstream_artifact_ids))
        object.__setattr__(self, "description", str(self.description))

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "current_version": self.current_version,
            "path": self.path,
            "owner": self.owner,
            "upstream_artifact_ids": list(self.upstream_artifact_ids),
            "description": self.description,
        }


@dataclass(frozen=True)
class PlanDetailStateSurface:
    """One state field, durable fact, or side-effect surface the model must see."""

    state_id: str
    owner: str = ""
    read_by_step_ids: tuple[str, ...] = ()
    written_by_step_ids: tuple[str, ...] = ()
    must_model: bool = True
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_id", str(self.state_id))
        object.__setattr__(self, "owner", str(self.owner))
        object.__setattr__(self, "read_by_step_ids", _as_tuple(self.read_by_step_ids))
        object.__setattr__(self, "written_by_step_ids", _as_tuple(self.written_by_step_ids))
        object.__setattr__(self, "description", str(self.description))

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "owner": self.owner,
            "read_by_step_ids": list(self.read_by_step_ids),
            "written_by_step_ids": list(self.written_by_step_ids),
            "must_model": self.must_model,
            "description": self.description,
        }


@dataclass(frozen=True)
class PlanDetailSideEffect:
    """One side effect or irreversible action the plan must gate."""

    side_effect_id: str
    step_id: str = ""
    effect_kind: str = "external_action"
    required_evidence_ids: tuple[str, ...] = ()
    reversible: bool = False
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "side_effect_id", str(self.side_effect_id))
        object.__setattr__(self, "step_id", str(self.step_id))
        object.__setattr__(self, "effect_kind", str(self.effect_kind))
        object.__setattr__(self, "required_evidence_ids", _as_tuple(self.required_evidence_ids))
        object.__setattr__(self, "description", str(self.description))

    def to_dict(self) -> dict[str, Any]:
        return {
            "side_effect_id": self.side_effect_id,
            "step_id": self.step_id,
            "effect_kind": self.effect_kind,
            "required_evidence_ids": list(self.required_evidence_ids),
            "reversible": self.reversible,
            "description": self.description,
        }


@dataclass(frozen=True)
class PlanDetailStep:
    """One ordered plan step with receipts, evidence, and rework gates."""

    step_id: str
    action: str = ""
    skill_name: str = ""
    step_type: str = "work"
    order_after: tuple[str, ...] = ()
    requires_receipts: tuple[str, ...] = ()
    produces_receipts: tuple[str, ...] = ()
    invalidates_receipts: tuple[str, ...] = ()
    reads_artifacts: tuple[str, ...] = ()
    writes_artifacts: tuple[str, ...] = ()
    invalidates_artifacts: tuple[str, ...] = ()
    required_evidence_ids: tuple[str, ...] = ()
    produced_evidence_ids: tuple[str, ...] = ()
    continue_evidence_ids: tuple[str, ...] = ()
    validation_required: bool = False
    rework_step_id: str = ""
    claim_labels: tuple[str, ...] = ()
    side_effect_ids: tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "step_id", str(self.step_id))
        object.__setattr__(self, "action", str(self.action))
        object.__setattr__(self, "skill_name", str(self.skill_name))
        object.__setattr__(self, "step_type", str(self.step_type))
        object.__setattr__(self, "order_after", _as_tuple(self.order_after))
        object.__setattr__(self, "requires_receipts", _as_tuple(self.requires_receipts))
        object.__setattr__(self, "produces_receipts", _as_tuple(self.produces_receipts))
        object.__setattr__(self, "invalidates_receipts", _as_tuple(self.invalidates_receipts))
        object.__setattr__(self, "reads_artifacts", _as_tuple(self.reads_artifacts))
        object.__setattr__(self, "writes_artifacts", _as_tuple(self.writes_artifacts))
        object.__setattr__(self, "invalidates_artifacts", _as_tuple(self.invalidates_artifacts))
        object.__setattr__(self, "required_evidence_ids", _as_tuple(self.required_evidence_ids))
        object.__setattr__(self, "produced_evidence_ids", _as_tuple(self.produced_evidence_ids))
        object.__setattr__(self, "continue_evidence_ids", _as_tuple(self.continue_evidence_ids))
        object.__setattr__(self, "rework_step_id", str(self.rework_step_id))
        object.__setattr__(self, "claim_labels", _as_tuple(self.claim_labels))
        object.__setattr__(self, "side_effect_ids", _as_tuple(self.side_effect_ids))
        object.__setattr__(self, "description", str(self.description))

    def completion_receipts(self) -> tuple[str, ...]:
        return self.produces_receipts or (self.step_id,)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action": self.action,
            "skill_name": self.skill_name,
            "step_type": self.step_type,
            "order_after": list(self.order_after),
            "requires_receipts": list(self.requires_receipts),
            "produces_receipts": list(self.produces_receipts),
            "invalidates_receipts": list(self.invalidates_receipts),
            "reads_artifacts": list(self.reads_artifacts),
            "writes_artifacts": list(self.writes_artifacts),
            "invalidates_artifacts": list(self.invalidates_artifacts),
            "required_evidence_ids": list(self.required_evidence_ids),
            "produced_evidence_ids": list(self.produced_evidence_ids),
            "continue_evidence_ids": list(self.continue_evidence_ids),
            "validation_required": self.validation_required,
            "rework_step_id": self.rework_step_id,
            "claim_labels": list(self.claim_labels),
            "side_effect_ids": list(self.side_effect_ids),
            "description": self.description,
        }


@dataclass(frozen=True)
class PlanDetailValidation:
    """One validation obligation and the evidence expected to satisfy it."""

    validation_id: str
    required_artifact_ids: tuple[str, ...] = ()
    required_evidence_kinds: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    command: str = ""
    scope: str = "routine"
    release_required: bool = False
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "validation_id", str(self.validation_id))
        object.__setattr__(self, "required_artifact_ids", _as_tuple(self.required_artifact_ids))
        object.__setattr__(self, "required_evidence_kinds", _as_tuple(self.required_evidence_kinds))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))
        object.__setattr__(self, "command", str(self.command))
        object.__setattr__(self, "scope", str(self.scope))
        object.__setattr__(self, "description", str(self.description))

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "required_artifact_ids": list(self.required_artifact_ids),
            "required_evidence_kinds": list(self.required_evidence_kinds),
            "evidence_ids": list(self.evidence_ids),
            "command": self.command,
            "scope": self.scope,
            "release_required": self.release_required,
            "description": self.description,
        }


@dataclass(frozen=True)
class PlanDetailEvidence:
    """One planned or observed evidence row."""

    evidence_id: str
    evidence_kind: str = "test"
    status: str = "not_run"
    produced_by_step_id: str = ""
    covers_artifacts: tuple[str, ...] = ()
    verifier_artifacts: tuple[str, ...] = ()
    covered_versions: Mapping[str, Any] = field(default_factory=dict)
    validation_ids: tuple[str, ...] = ()
    command: str = ""
    result_path: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "evidence_kind", str(self.evidence_kind))
        object.__setattr__(self, "status", str(self.status))
        object.__setattr__(self, "produced_by_step_id", str(self.produced_by_step_id))
        object.__setattr__(self, "covers_artifacts", _as_tuple(self.covers_artifacts))
        object.__setattr__(self, "verifier_artifacts", _as_tuple(self.verifier_artifacts))
        object.__setattr__(self, "covered_versions", _as_mapping(self.covered_versions))
        object.__setattr__(self, "validation_ids", _as_tuple(self.validation_ids))
        object.__setattr__(self, "command", str(self.command))
        object.__setattr__(self, "result_path", str(self.result_path))
        object.__setattr__(self, "description", str(self.description))

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "evidence_kind": self.evidence_kind,
            "status": self.status,
            "produced_by_step_id": self.produced_by_step_id,
            "covers_artifacts": list(self.covers_artifacts),
            "verifier_artifacts": list(self.verifier_artifacts),
            "covered_versions": dict(self.covered_versions),
            "validation_ids": list(self.validation_ids),
            "command": self.command,
            "result_path": self.result_path,
            "description": self.description,
        }


@dataclass(frozen=True)
class PlanDetailFailureBranch:
    """One expected failure, retry, blocked, or rework branch."""

    branch_id: str
    trigger: str = ""
    step_id: str = ""
    rework_step_id: str = ""
    expected_resolution: str = ""
    evidence_ids: tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "branch_id", str(self.branch_id))
        object.__setattr__(self, "trigger", str(self.trigger))
        object.__setattr__(self, "step_id", str(self.step_id))
        object.__setattr__(self, "rework_step_id", str(self.rework_step_id))
        object.__setattr__(self, "expected_resolution", str(self.expected_resolution))
        object.__setattr__(self, "evidence_ids", _as_tuple(self.evidence_ids))
        object.__setattr__(self, "description", str(self.description))

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "trigger": self.trigger,
            "step_id": self.step_id,
            "rework_step_id": self.rework_step_id,
            "expected_resolution": self.expected_resolution,
            "evidence_ids": list(self.evidence_ids),
            "description": self.description,
        }


@dataclass(frozen=True)
class PlanDetailHumanQuestion:
    """One unresolved decision that prevents unsupported full confidence."""

    question_id: str
    question: str
    blocking: bool = True
    resolved: bool = False
    decision: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "question_id", str(self.question_id))
        object.__setattr__(self, "question", str(self.question))
        object.__setattr__(self, "decision", str(self.decision))

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "question": self.question,
            "blocking": self.blocking,
            "resolved": self.resolved,
            "decision": self.decision,
        }


@dataclass(frozen=True)
class PlanDetailFreshnessRule:
    """One propagation rule from an upstream artifact to stale evidence."""

    rule_id: str
    upstream_artifact_id: str
    invalidates_artifact_ids: tuple[str, ...] = ()
    invalidates_evidence_kinds: tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", str(self.rule_id))
        object.__setattr__(self, "upstream_artifact_id", str(self.upstream_artifact_id))
        object.__setattr__(self, "invalidates_artifact_ids", _as_tuple(self.invalidates_artifact_ids))
        object.__setattr__(self, "invalidates_evidence_kinds", _as_tuple(self.invalidates_evidence_kinds))
        object.__setattr__(self, "description", str(self.description))

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "upstream_artifact_id": self.upstream_artifact_id,
            "invalidates_artifact_ids": list(self.invalidates_artifact_ids),
            "invalidates_evidence_kinds": list(self.invalidates_evidence_kinds),
            "description": self.description,
        }


@dataclass(frozen=True)
class PlanDetail:
    """Structured detail rows for a rough FlowGuard plan."""

    plan_id: str
    task_summary: str = ""
    goal: str = ""
    assumptions: tuple[str, ...] = ()
    sources: tuple[PlanDetailSource, ...] = ()
    surfaces: tuple[PlanDetailSurface, ...] = ()
    artifacts: tuple[PlanDetailArtifact, ...] = ()
    state_surfaces: tuple[PlanDetailStateSurface, ...] = ()
    side_effects: tuple[PlanDetailSideEffect, ...] = ()
    steps: tuple[PlanDetailStep, ...] = ()
    validations: tuple[PlanDetailValidation, ...] = ()
    evidence: tuple[PlanDetailEvidence, ...] = ()
    failure_branches: tuple[PlanDetailFailureBranch, ...] = ()
    human_questions: tuple[PlanDetailHumanQuestion, ...] = ()
    freshness_rules: tuple[PlanDetailFreshnessRule, ...] = ()
    final_claim: str = PLAN_DETAIL_CLAIM_SCOPED
    final_evidence_ids: tuple[str, ...] = ()
    claim_labels: tuple[str, ...] = ("done_claimed",)
    non_trivial: bool = True
    exploratory: bool = False
    allow_scoped_confidence: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "task_summary", str(self.task_summary))
        object.__setattr__(self, "goal", str(self.goal))
        object.__setattr__(self, "assumptions", _as_tuple(self.assumptions))
        object.__setattr__(self, "sources", tuple(self.sources))
        object.__setattr__(self, "surfaces", tuple(self.surfaces))
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(self, "state_surfaces", tuple(self.state_surfaces))
        object.__setattr__(self, "side_effects", tuple(self.side_effects))
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "validations", tuple(self.validations))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "failure_branches", tuple(self.failure_branches))
        object.__setattr__(self, "human_questions", tuple(self.human_questions))
        object.__setattr__(self, "freshness_rules", tuple(self.freshness_rules))
        object.__setattr__(self, "final_claim", _claim_scope(self.final_claim))
        object.__setattr__(self, "final_evidence_ids", _as_tuple(self.final_evidence_ids))
        object.__setattr__(self, "claim_labels", _as_tuple(self.claim_labels))
        object.__setattr__(self, "metadata", _as_mapping(self.metadata))

    def source_ids(self) -> tuple[str, ...]:
        return tuple(source.source_id for source in self.sources)

    def step_ids(self) -> tuple[str, ...]:
        return tuple(step.step_id for step in self.steps)

    def evidence_ids(self) -> tuple[str, ...]:
        produced = tuple(evidence.evidence_id for evidence in self.evidence)
        step_produced = tuple(eid for step in self.steps for eid in step.produced_evidence_ids)
        validation_evidence = tuple(eid for validation in self.validations for eid in validation.evidence_ids)
        return tuple(dict.fromkeys(produced + step_produced + validation_evidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "task_summary": self.task_summary,
            "goal": self.goal,
            "assumptions": list(self.assumptions),
            "sources": [source.to_dict() for source in self.sources],
            "surfaces": [surface.to_dict() for surface in self.surfaces],
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "state_surfaces": [surface.to_dict() for surface in self.state_surfaces],
            "side_effects": [effect.to_dict() for effect in self.side_effects],
            "steps": [step.to_dict() for step in self.steps],
            "validations": [validation.to_dict() for validation in self.validations],
            "evidence": [evidence.to_dict() for evidence in self.evidence],
            "failure_branches": [branch.to_dict() for branch in self.failure_branches],
            "human_questions": [question.to_dict() for question in self.human_questions],
            "freshness_rules": [rule.to_dict() for rule in self.freshness_rules],
            "final_claim": self.final_claim,
            "final_evidence_ids": list(self.final_evidence_ids),
            "claim_labels": list(self.claim_labels),
            "non_trivial": self.non_trivial,
            "exploratory": self.exploratory,
            "allow_scoped_confidence": self.allow_scoped_confidence,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class PlanDetailFinding:
    """One gap found while reviewing plan detail rows."""

    code: str
    message: str
    severity: str = PLAN_DETAIL_SEVERITY_NEEDS_REVISION
    row_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "row_id", str(self.row_id))
        object.__setattr__(self, "metadata", _as_mapping(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "row_id": self.row_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class PlanDetailReviewReport:
    """Review result for a `PlanDetail`."""

    plan_id: str
    status: str
    findings: tuple[PlanDetailFinding, ...] = ()
    summary: str = ""

    @property
    def ok(self) -> bool:
        return self.status == PLAN_DETAIL_STATUS_PASS

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "status", str(self.status))
        object.__setattr__(self, "findings", tuple(self.findings))
        if not self.summary:
            object.__setattr__(
                self,
                "summary",
                f"plan={self.plan_id} status={self.status} findings={len(self.findings)}",
            )

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard plan detailing review ===",
            f"plan_id: {self.plan_id}",
            f"status: {self.status}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_findings]:
            location = f" row={finding.row_id}" if finding.row_id else ""
            lines.append(f"- [{finding.severity}] {finding.code}{location}: {finding.message}")
        remaining = len(self.findings) - max_findings
        if remaining > 0:
            lines.append(f"... {remaining} more finding(s)")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "status": self.status,
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(to_jsonable(self.to_dict()), indent=indent, sort_keys=True)


def _finding(
    code: str,
    message: str,
    *,
    severity: str = PLAN_DETAIL_SEVERITY_NEEDS_REVISION,
    row_id: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> PlanDetailFinding:
    return PlanDetailFinding(code, message, severity=severity, row_id=row_id, metadata=metadata or {})


def review_plan_detail(plan: PlanDetail) -> PlanDetailReviewReport:
    """Review whether a rough plan has enough structured detail to proceed."""

    findings: list[PlanDetailFinding] = []
    step_ids = set(plan.step_ids())
    evidence_ids = set(plan.evidence_ids())
    artifact_ids = {artifact.artifact_id for artifact in plan.artifacts}
    receipt_ids = {receipt for step in plan.steps for receipt in step.completion_receipts()}
    receipt_ids.update(receipt for step in plan.steps for receipt in step.requires_receipts)

    if not plan.task_summary.strip() and not plan.goal.strip():
        findings.append(_finding("missing_goal", "plan detail needs a task summary or goal", severity=PLAN_DETAIL_SEVERITY_BLOCKED))

    if plan.non_trivial and not plan.sources:
        findings.append(_finding("missing_source_evidence", "non-trivial plan detail needs current source evidence"))

    for source in plan.sources:
        if not source.current:
            findings.append(
                _finding(
                    "source_evidence_not_current",
                    "plan source evidence is stale",
                    severity=_severity_for_claim(plan, scoped_ok=True),
                    row_id=source.source_id,
                )
            )

    if plan.non_trivial and not plan.surfaces:
        findings.append(_finding("missing_risk_surfaces", "non-trivial plan detail needs risk or scope surfaces"))

    for surface in plan.surfaces:
        if not surface.in_scope:
            if not (surface.out_of_scope_reason or surface.omission_reason):
                findings.append(
                    _finding(
                        "out_of_scope_surface_missing_reason",
                        "scoped-out surface needs a reason",
                        severity=_severity_for_claim(plan, scoped_ok=True),
                        row_id=surface.surface_id,
                    )
                )
            continue
        if not surface.reviewed:
            findings.append(_finding("surface_not_reviewed", "in-scope surface was not reviewed", row_id=surface.surface_id))
        if not surface.included:
            findings.append(_finding("surface_omitted", "in-scope surface was omitted", row_id=surface.surface_id))
        if surface.included and not surface.has_mapping():
            findings.append(
                _finding(
                    "surface_missing_mapping",
                    "included surface needs source or evidence mapping",
                    row_id=surface.surface_id,
                )
            )

    if plan.non_trivial and not plan.artifacts:
        findings.append(_finding("missing_artifacts", "non-trivial plan detail needs artifacts that can be read, written, or validated"))

    if plan.non_trivial and not plan.state_surfaces and not plan.side_effects:
        findings.append(_finding("missing_state_or_side_effect_surfaces", "plan detail needs modeled state or side-effect surfaces"))

    if not plan.steps:
        findings.append(_finding("missing_steps", "plan detail needs ordered steps", severity=PLAN_DETAIL_SEVERITY_BLOCKED))

    seen_steps: set[str] = set()
    for step in plan.steps:
        if not step.action.strip() and not step.description.strip():
            findings.append(_finding("step_missing_action", "plan step needs an action or description", row_id=step.step_id))
        unknown_prior = sorted(set(step.order_after) - seen_steps)
        if unknown_prior:
            findings.append(
                _finding(
                    "step_out_of_order",
                    "plan step appears before its predecessors",
                    severity=PLAN_DETAIL_SEVERITY_BLOCKED,
                    row_id=step.step_id,
                    metadata={"missing_predecessors": unknown_prior},
                )
            )
        unknown_artifacts = sorted(
            set(step.reads_artifacts + step.writes_artifacts + step.invalidates_artifacts) - artifact_ids
        )
        if unknown_artifacts:
            findings.append(
                _finding(
                    "step_references_unknown_artifact",
                    "plan step references artifacts not declared in the plan detail",
                    severity=PLAN_DETAIL_SEVERITY_BLOCKED,
                    row_id=step.step_id,
                    metadata={"unknown_artifacts": unknown_artifacts},
                )
            )
        if step.validation_required and not step.continue_evidence_ids:
            findings.append(_finding("continue_gate_missing_evidence", "validation step needs continue evidence", row_id=step.step_id))
        if step.validation_required and not step.rework_step_id:
            findings.append(_finding("rework_gate_missing", "validation step needs a rework target", row_id=step.step_id))
        if step.rework_step_id and step.rework_step_id not in step_ids:
            findings.append(
                _finding(
                    "rework_gate_unknown_step",
                    "rework target is not a declared step",
                    severity=PLAN_DETAIL_SEVERITY_BLOCKED,
                    row_id=step.step_id,
                    metadata={"rework_step_id": step.rework_step_id},
                )
            )
        if step.claim_labels and not step.produces_receipts:
            findings.append(_finding("claim_step_missing_receipt", "claim-gated step should produce an explicit receipt", row_id=step.step_id))
        seen_steps.add(step.step_id)

    if plan.non_trivial and not plan.validations:
        findings.append(_finding("missing_validations", "non-trivial plan detail needs validation requirements", severity=_severity_for_claim(plan)))

    for validation in plan.validations:
        if not validation.required_artifact_ids:
            findings.append(_finding("validation_missing_artifacts", "validation needs required artifact ids", row_id=validation.validation_id))
        unknown_validation_artifacts = sorted(set(validation.required_artifact_ids) - artifact_ids)
        if unknown_validation_artifacts:
            findings.append(
                _finding(
                    "validation_references_unknown_artifact",
                    "validation references artifacts not declared in the plan detail",
                    severity=PLAN_DETAIL_SEVERITY_BLOCKED,
                    row_id=validation.validation_id,
                    metadata={"unknown_artifacts": unknown_validation_artifacts},
                )
            )
        if not validation.required_evidence_kinds:
            findings.append(_finding("validation_missing_evidence_kind", "validation needs required evidence kinds", row_id=validation.validation_id))
        if not validation.evidence_ids:
            findings.append(_finding("validation_missing_evidence_id", "validation needs evidence ids", row_id=validation.validation_id))

    for evidence in plan.evidence:
        unknown_evidence_artifacts = sorted(set(evidence.covers_artifacts + evidence.verifier_artifacts) - artifact_ids)
        if unknown_evidence_artifacts:
            findings.append(
                _finding(
                    "evidence_references_unknown_artifact",
                    "evidence references artifacts not declared in the plan detail",
                    severity=PLAN_DETAIL_SEVERITY_BLOCKED,
                    row_id=evidence.evidence_id,
                    metadata={"unknown_artifacts": unknown_evidence_artifacts},
                )
            )

    if plan.non_trivial and not plan.failure_branches:
        findings.append(
            _finding(
                "missing_failure_branches",
                "non-trivial plan detail needs failure, retry, blocked, or rework branches",
                severity=_severity_for_claim(plan),
            )
        )

    for branch in plan.failure_branches:
        if not branch.trigger:
            findings.append(_finding("failure_branch_missing_trigger", "failure branch needs a trigger", row_id=branch.branch_id))
        if branch.step_id and branch.step_id not in step_ids:
            findings.append(_finding("failure_branch_unknown_step", "failure branch references an unknown step", severity=PLAN_DETAIL_SEVERITY_BLOCKED, row_id=branch.branch_id))
        if branch.rework_step_id and branch.rework_step_id not in step_ids:
            findings.append(_finding("failure_branch_unknown_rework_step", "failure branch rework target is unknown", severity=PLAN_DETAIL_SEVERITY_BLOCKED, row_id=branch.branch_id))
        if not branch.rework_step_id and not branch.expected_resolution:
            findings.append(_finding("failure_branch_missing_resolution", "failure branch needs a rework target or expected resolution", row_id=branch.branch_id))

    for question in plan.human_questions:
        if question.blocking and not question.resolved:
            severity = PLAN_DETAIL_SEVERITY_BLOCKED if plan.final_claim == PLAN_DETAIL_CLAIM_FULL else PLAN_DETAIL_SEVERITY_SCOPED
            findings.append(_finding("human_question_unresolved", "blocking human-review question is unresolved", severity=severity, row_id=question.question_id))

    for effect in plan.side_effects:
        if effect.step_id and effect.step_id not in step_ids:
            findings.append(_finding("side_effect_unknown_step", "side effect references an unknown step", severity=PLAN_DETAIL_SEVERITY_BLOCKED, row_id=effect.side_effect_id))
        if not effect.reversible and not effect.required_evidence_ids:
            findings.append(
                _finding(
                    "side_effect_missing_evidence_gate",
                    "irreversible side effect needs required evidence ids",
                    severity=_severity_for_claim(plan),
                    row_id=effect.side_effect_id,
                )
            )
        missing_gate_evidence = sorted(set(effect.required_evidence_ids) - evidence_ids)
        if missing_gate_evidence:
            findings.append(
                _finding(
                    "side_effect_references_unknown_evidence",
                    "side-effect evidence gate references unknown evidence ids",
                    severity=PLAN_DETAIL_SEVERITY_BLOCKED,
                    row_id=effect.side_effect_id,
                    metadata={"unknown_evidence": missing_gate_evidence},
                )
            )

    if plan.final_claim == PLAN_DETAIL_CLAIM_FULL:
        if not plan.final_evidence_ids:
            findings.append(_finding("full_claim_missing_final_evidence", "full claim needs final evidence ids", severity=PLAN_DETAIL_SEVERITY_BLOCKED))
        missing_final_evidence = sorted(set(plan.final_evidence_ids) - evidence_ids)
        if missing_final_evidence:
            findings.append(
                _finding(
                    "full_claim_references_unknown_evidence",
                    "full claim references evidence not declared in the plan detail",
                    severity=PLAN_DETAIL_SEVERITY_BLOCKED,
                    metadata={"unknown_evidence": missing_final_evidence},
                )
            )

    if plan.final_claim == PLAN_DETAIL_CLAIM_FULL and findings:
        findings.append(
            _finding(
                "full_claim_has_detail_gaps",
                "full confidence cannot be claimed while plan-detail gaps remain",
                severity=PLAN_DETAIL_SEVERITY_BLOCKED,
            )
        )

    return PlanDetailReviewReport(plan.plan_id, _status_from_findings(findings), tuple(findings))


def plan_detail_to_plan_intake(plan: PlanDetail) -> PlanIntakeCompletenessPlan:
    """Project plan-detail source and surface rows into PlanIntake."""

    sources = tuple(
        PlanSourceEvidence(
            source.source_id,
            source_kind=source.source_kind,
            current=source.current,
            supports_surface_ids=source.supports_surface_ids,
            summary=source.summary,
            metadata=source.metadata,
        )
        for source in plan.sources
    )
    surfaces = tuple(
        PlanIntakeRiskSurface(
            surface.surface_id,
            surface_kind=surface.surface_kind,
            description=surface.description,
            in_scope=surface.in_scope,
            included=surface.included,
            reviewed=surface.reviewed,
            source_ids=surface.source_ids,
            evidence_ids=surface.evidence_ids,
            out_of_scope_reason=surface.out_of_scope_reason,
            omission_reason=surface.omission_reason,
            recurring=surface.recurring,
            high_risk=surface.high_risk,
            observed_failure_ids=surface.observed_failure_ids,
            same_class_case_ids=surface.same_class_case_ids,
            historical_holdout_ids=surface.historical_holdout_ids,
            scoped_reasons=surface.scoped_reasons,
            metadata=surface.metadata,
        )
        for surface in plan.surfaces
    )
    return PlanIntakeCompletenessPlan(
        plan.plan_id,
        sources=sources,
        surfaces=surfaces,
        source_evidence_current=all(source.current for source in plan.sources),
        recurring_or_high_risk=any(surface.recurring or surface.high_risk for surface in plan.surfaces),
    )


def plan_detail_to_step_contracts(plan: PlanDetail) -> tuple[WorkflowStepContract, ...]:
    """Project plan-detail steps into receipt-gated workflow contracts."""

    contracts: list[WorkflowStepContract] = []
    for step in plan.steps:
        contracts.append(
            WorkflowStepContract(
                step.step_id,
                completion_labels=(step.step_id,) + step.produces_receipts,
                requires_receipts=step.requires_receipts,
                produces_receipts=step.produces_receipts,
                invalidates_receipts=step.invalidates_receipts,
                required_for_claims=step.claim_labels,
                skip_policy=STEP_SKIP_FORBIDDEN if step.validation_required else STEP_SKIP_ALLOWED_WITH_REASON,
                description=step.description or step.action,
                artifact_ids=tuple(dict.fromkeys(step.reads_artifacts + step.writes_artifacts)),
                metadata={"source_plan_id": plan.plan_id},
            )
        )
    return tuple(contracts)


def plan_detail_to_development_process(plan: PlanDetail) -> DevelopmentProcessPlan:
    """Project plan-detail lifecycle rows into DevelopmentProcessFlow."""

    artifacts = tuple(
        ProcessArtifact(
            artifact.artifact_id,
            artifact.artifact_type,
            artifact.current_version,
            path=artifact.path,
            owner=artifact.owner,
            upstream_artifact_ids=artifact.upstream_artifact_ids,
            description=artifact.description,
        )
        for artifact in plan.artifacts
    )
    actions = tuple(
        ProcessAction(
            step.step_id,
            action_type=step.step_type,
            reads_artifacts=step.reads_artifacts,
            writes_artifacts=step.writes_artifacts,
            invalidates_artifacts=step.invalidates_artifacts,
            produced_evidence_ids=step.produced_evidence_ids,
            required_evidence_ids=step.required_evidence_ids,
            order_after=step.order_after,
            description=step.description or step.action,
        )
        for step in plan.steps
    )
    evidence = tuple(
        ProcessEvidence(
            item.evidence_id,
            evidence_kind=item.evidence_kind,
            status=item.status,
            covers_artifacts=tuple(dict.fromkeys(item.covers_artifacts + item.verifier_artifacts)),
            verifier_artifacts=item.verifier_artifacts,
            covered_versions=item.covered_versions,
            validation_requirement_ids=item.validation_ids,
            produced_by_action_id=item.produced_by_step_id,
            command=item.command,
            result_path=item.result_path,
            proof_artifact=ProofArtifactRef(
                item.evidence_id,
                producer_route="plan_detailing_compiler",
                command=item.command,
                result_path=item.result_path,
                result_status=item.status,
                exit_code=0 if item.status == "passed" else None,
                artifact_fingerprints={key: str(value) for key, value in item.covered_versions.items()},
                covered_obligation_ids=item.validation_ids,
            )
            if item.result_path
            else None,
        )
        for item in plan.evidence
    )
    validations = tuple(
        ValidationRequirement(
            validation.validation_id,
            required_artifact_ids=validation.required_artifact_ids,
            required_evidence_kinds=validation.required_evidence_kinds,
            evidence_ids=validation.evidence_ids,
            scope=validation.scope,
            release_required=validation.release_required,
            command=validation.command,
            description=validation.description,
        )
        for validation in plan.validations
    )
    freshness_rules = tuple(
        FreshnessRule(
            rule.rule_id,
            rule.upstream_artifact_id,
            invalidates_artifact_ids=rule.invalidates_artifact_ids,
            invalidates_evidence_kinds=rule.invalidates_evidence_kinds,
            description=rule.description,
        )
        for rule in plan.freshness_rules
    )
    return DevelopmentProcessPlan(
        plan.plan_id,
        artifacts=artifacts,
        actions=actions,
        evidence=evidence,
        validation_requirements=validations,
        freshness_rules=freshness_rules,
        require_proof_artifacts=plan.final_claim == PLAN_DETAIL_CLAIM_FULL,
    )


def plan_detail_to_agent_workflow_plan(plan: PlanDetail, inventory: SkillInventorySnapshot) -> AgentWorkflowPlan:
    """Project plan-detail skill and evidence gates into AgentWorkflowRehearsal."""

    selected_skill_names = tuple(dict.fromkeys(step.skill_name for step in plan.steps if step.skill_name))
    final_claim = {
        PLAN_DETAIL_CLAIM_FULL: AGENT_FINAL_CLAIM_FULL,
        PLAN_DETAIL_CLAIM_NONE: AGENT_FINAL_CLAIM_NONE,
    }.get(plan.final_claim, AGENT_FINAL_CLAIM_SCOPED)
    steps = tuple(
        AgentWorkflowStep(
            step.step_id,
            skill_name=step.skill_name,
            action=step.action,
            step_type=step.step_type,
            order_after=step.order_after,
            required_evidence_ids=step.required_evidence_ids,
            produced_evidence_ids=step.produced_evidence_ids,
            continue_evidence_ids=step.continue_evidence_ids,
            side_effects=step.side_effect_ids,
            validation_required=step.validation_required,
            irreversible=any(effect.step_id == step.step_id and not effect.reversible for effect in plan.side_effects),
            rework_step_id=step.rework_step_id,
            description=step.description,
        )
        for step in plan.steps
    )
    return AgentWorkflowPlan(
        plan.plan_id,
        plan.task_summary or plan.goal,
        inventory,
        selected_skill_names=selected_skill_names,
        steps=steps,
        final_claim=final_claim,
        final_evidence_ids=plan.final_evidence_ids,
        risk_flags=tuple(surface.surface_id for surface in plan.surfaces if surface.in_scope),
        task_trivial=not plan.non_trivial,
    )


__all__ = [
    "PLAN_DETAIL_CLAIM_BLOCKED",
    "PLAN_DETAIL_CLAIM_FULL",
    "PLAN_DETAIL_CLAIM_NONE",
    "PLAN_DETAIL_CLAIM_SCOPED",
    "PLAN_DETAIL_CLAIMS",
    "PLAN_DETAIL_SEVERITY_BLOCKED",
    "PLAN_DETAIL_SEVERITY_INFO",
    "PLAN_DETAIL_SEVERITY_NEEDS_REVISION",
    "PLAN_DETAIL_SEVERITY_SCOPED",
    "PLAN_DETAIL_STATUS_BLOCKED",
    "PLAN_DETAIL_STATUS_NEEDS_REVISION",
    "PLAN_DETAIL_STATUS_PASS",
    "PLAN_DETAIL_STATUS_SCOPED",
    "PLAN_DETAIL_STATUSES",
    "PlanDetail",
    "PlanDetailArtifact",
    "PlanDetailEvidence",
    "PlanDetailFailureBranch",
    "PlanDetailFinding",
    "PlanDetailFreshnessRule",
    "PlanDetailHumanQuestion",
    "PlanDetailReviewReport",
    "PlanDetailSideEffect",
    "PlanDetailSource",
    "PlanDetailStateSurface",
    "PlanDetailStep",
    "PlanDetailSurface",
    "PlanDetailValidation",
    "plan_detail_to_agent_workflow_plan",
    "plan_detail_to_development_process",
    "plan_detail_to_plan_intake",
    "plan_detail_to_step_contracts",
    "review_plan_detail",
]
