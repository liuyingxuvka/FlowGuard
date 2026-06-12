"""Agent workflow rehearsal helpers for installed-skill planning.

Agent workflow rehearsal reviews an AI agent's planned use of installed Codex
skills before execution. It does not execute the workflow. It checks whether a
fresh current-machine skill inventory, selected skills, skipped candidate
skills, ordering, continue gates, rework gates, validation guidance, side
effects, and final evidence claims support the plan.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable


REHEARSAL_STATUS_PASS = "pass"
REHEARSAL_STATUS_NEEDS_REVISION = "needs_revision"
REHEARSAL_STATUS_SCOPED = "scoped"
REHEARSAL_STATUS_BLOCKED = "blocked"

REHEARSAL_STATUSES = {
    REHEARSAL_STATUS_PASS,
    REHEARSAL_STATUS_NEEDS_REVISION,
    REHEARSAL_STATUS_SCOPED,
    REHEARSAL_STATUS_BLOCKED,
}

FINDING_SEVERITY_INFO = "info"
FINDING_SEVERITY_NEEDS_REVISION = "needs_revision"
FINDING_SEVERITY_SCOPED = "scoped"
FINDING_SEVERITY_BLOCKED = "blocked"

VALIDATION_GUIDANCE_STRONG = "strong"
VALIDATION_GUIDANCE_WEAK = "weak"
VALIDATION_GUIDANCE_MISSING = "missing"
VALIDATION_GUIDANCE_MANUAL_ONLY = "manual_only"
VALIDATION_GUIDANCE_EXTERNAL_ONLY = "external_only"

VALIDATION_GUIDANCE_STATUSES = {
    VALIDATION_GUIDANCE_STRONG,
    VALIDATION_GUIDANCE_WEAK,
    VALIDATION_GUIDANCE_MISSING,
    VALIDATION_GUIDANCE_MANUAL_ONLY,
    VALIDATION_GUIDANCE_EXTERNAL_ONLY,
}

WEAK_VALIDATION_GUIDANCE_STATUSES = {
    VALIDATION_GUIDANCE_WEAK,
    VALIDATION_GUIDANCE_MISSING,
    VALIDATION_GUIDANCE_MANUAL_ONLY,
    VALIDATION_GUIDANCE_EXTERNAL_ONLY,
}

FINAL_CLAIM_NONE = "none"
FINAL_CLAIM_SCOPED = "scoped"
FINAL_CLAIM_FULL = "full"
FINAL_CLAIM_BLOCKED = "blocked"

FINAL_CLAIMS = {
    FINAL_CLAIM_NONE,
    FINAL_CLAIM_SCOPED,
    FINAL_CLAIM_FULL,
    FINAL_CLAIM_BLOCKED,
}

SIDE_EFFECT_STEP_TYPES = {
    "publish",
    "release",
    "commit",
    "push",
    "delete",
    "email",
    "external_action",
    "install",
    "migration",
}

UI_EVIDENCE_ROLE_INVENTORY = "ui_inventory"
UI_EVIDENCE_ROLE_BASELINE_SEMANTICS = "ui_baseline_semantics"
UI_EVIDENCE_ROLE_IMPLEMENTATION_VALIDATION = "ui_implementation_validation"

UI_AGENT_EVIDENCE_ROLES = (
    UI_EVIDENCE_ROLE_INVENTORY,
    UI_EVIDENCE_ROLE_BASELINE_SEMANTICS,
    UI_EVIDENCE_ROLE_IMPLEMENTATION_VALIDATION,
)


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


def _normalize_validation_guidance_status(value: str) -> str:
    text = str(value or VALIDATION_GUIDANCE_MISSING)
    if text not in VALIDATION_GUIDANCE_STATUSES:
        return VALIDATION_GUIDANCE_MISSING
    return text


@dataclass(frozen=True)
class SkillCapability:
    """One skill visible in the current machine/session inventory."""

    skill_name: str
    description: str = ""
    source: str = ""
    trigger_keywords: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
    validation_guidance_status: str = VALIDATION_GUIDANCE_MISSING
    validation_guidance: str = ""
    candidate_for_task: bool = False
    required_for_task: bool = False
    deep_read: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "skill_name", str(self.skill_name))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "source", str(self.source))
        object.__setattr__(self, "trigger_keywords", _as_tuple(self.trigger_keywords))
        object.__setattr__(self, "capabilities", _as_tuple(self.capabilities))
        object.__setattr__(self, "limitations", _as_tuple(self.limitations))
        object.__setattr__(self, "side_effects", _as_tuple(self.side_effects))
        object.__setattr__(
            self,
            "validation_guidance_status",
            _normalize_validation_guidance_status(self.validation_guidance_status),
        )
        object.__setattr__(self, "validation_guidance", str(self.validation_guidance))

    def has_weak_validation_guidance(self) -> bool:
        return self.validation_guidance_status in WEAK_VALIDATION_GUIDANCE_STATUSES

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "description": self.description,
            "source": self.source,
            "trigger_keywords": list(self.trigger_keywords),
            "capabilities": list(self.capabilities),
            "limitations": list(self.limitations),
            "side_effects": list(self.side_effects),
            "validation_guidance_status": self.validation_guidance_status,
            "validation_guidance": self.validation_guidance,
            "candidate_for_task": self.candidate_for_task,
            "required_for_task": self.required_for_task,
            "deep_read": self.deep_read,
        }


@dataclass(frozen=True)
class SkillInventorySnapshot:
    """Fresh skill inventory for one rehearsal invocation."""

    snapshot_id: str
    skills: tuple[SkillCapability, ...] = ()
    source_paths: tuple[str, ...] = ()
    current: bool = True
    from_cache: bool = False
    generated_for_task: str = ""
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", str(self.snapshot_id))
        object.__setattr__(self, "skills", tuple(self.skills))
        object.__setattr__(self, "source_paths", _as_tuple(self.source_paths))
        object.__setattr__(self, "generated_for_task", str(self.generated_for_task))
        object.__setattr__(self, "notes", _as_tuple(self.notes))

    def is_current_evidence(self) -> bool:
        return self.current and not self.from_cache

    def skill_map(self) -> dict[str, SkillCapability]:
        return {skill.skill_name: skill for skill in self.skills}

    def candidate_skills(self) -> tuple[SkillCapability, ...]:
        return tuple(skill for skill in self.skills if skill.candidate_for_task or skill.required_for_task)

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "skills": [skill.to_dict() for skill in self.skills],
            "source_paths": list(self.source_paths),
            "current": self.current,
            "from_cache": self.from_cache,
            "generated_for_task": self.generated_for_task,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class SkippedSkill:
    """A candidate skill the agent intends not to use."""

    skill_name: str
    reason: str = ""
    consequence: str = ""
    accepted: bool = False
    scope_boundary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "skill_name", str(self.skill_name))
        object.__setattr__(self, "reason", str(self.reason))
        object.__setattr__(self, "consequence", str(self.consequence))
        object.__setattr__(self, "scope_boundary", str(self.scope_boundary))

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "reason": self.reason,
            "consequence": self.consequence,
            "accepted": self.accepted,
            "scope_boundary": self.scope_boundary,
        }


@dataclass(frozen=True)
class AgentWorkflowStep:
    """One planned skill/workflow step in the rehearsal plan."""

    step_id: str
    skill_name: str = ""
    action: str = ""
    step_type: str = "work"
    order_after: tuple[str, ...] = ()
    required_completed_step_ids: tuple[str, ...] = ()
    required_evidence_ids: tuple[str, ...] = ()
    produced_evidence_ids: tuple[str, ...] = ()
    continue_evidence_ids: tuple[str, ...] = ()
    compensating_check_ids: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
    validation_required: bool = False
    irreversible: bool = False
    rework_step_id: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "step_id", str(self.step_id))
        object.__setattr__(self, "skill_name", str(self.skill_name))
        object.__setattr__(self, "action", str(self.action))
        object.__setattr__(self, "step_type", str(self.step_type))
        object.__setattr__(self, "order_after", _as_tuple(self.order_after))
        object.__setattr__(self, "required_completed_step_ids", _as_tuple(self.required_completed_step_ids))
        object.__setattr__(self, "required_evidence_ids", _as_tuple(self.required_evidence_ids))
        object.__setattr__(self, "produced_evidence_ids", _as_tuple(self.produced_evidence_ids))
        object.__setattr__(self, "continue_evidence_ids", _as_tuple(self.continue_evidence_ids))
        object.__setattr__(self, "compensating_check_ids", _as_tuple(self.compensating_check_ids))
        object.__setattr__(self, "side_effects", _as_tuple(self.side_effects))
        object.__setattr__(self, "rework_step_id", str(self.rework_step_id))
        object.__setattr__(self, "description", str(self.description))

    def has_side_effect(self) -> bool:
        return self.irreversible or bool(self.side_effects) or self.step_type in SIDE_EFFECT_STEP_TYPES

    def has_compensating_check(self) -> bool:
        return bool(self.compensating_check_ids or self.continue_evidence_ids or self.produced_evidence_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "skill_name": self.skill_name,
            "action": self.action,
            "step_type": self.step_type,
            "order_after": list(self.order_after),
            "required_completed_step_ids": list(self.required_completed_step_ids),
            "required_evidence_ids": list(self.required_evidence_ids),
            "produced_evidence_ids": list(self.produced_evidence_ids),
            "continue_evidence_ids": list(self.continue_evidence_ids),
            "compensating_check_ids": list(self.compensating_check_ids),
            "side_effects": list(self.side_effects),
            "validation_required": self.validation_required,
            "irreversible": self.irreversible,
            "rework_step_id": self.rework_step_id,
            "description": self.description,
        }


@dataclass(frozen=True)
class AgentWorkflowPlan:
    """The agent's intended cross-skill workflow before execution."""

    plan_id: str
    task_summary: str
    inventory: SkillInventorySnapshot
    selected_skill_names: tuple[str, ...] = ()
    skipped_candidate_skills: tuple[SkippedSkill, ...] = ()
    steps: tuple[AgentWorkflowStep, ...] = ()
    final_claim: str = FINAL_CLAIM_SCOPED
    final_evidence_ids: tuple[str, ...] = ()
    risk_flags: tuple[str, ...] = ()
    ui_evidence_roles: tuple[str, ...] = ()
    task_trivial: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "task_summary", str(self.task_summary))
        object.__setattr__(self, "selected_skill_names", _as_tuple(self.selected_skill_names))
        object.__setattr__(self, "skipped_candidate_skills", tuple(self.skipped_candidate_skills))
        object.__setattr__(self, "steps", tuple(self.steps))
        final_claim = str(self.final_claim or FINAL_CLAIM_SCOPED)
        if final_claim not in FINAL_CLAIMS:
            final_claim = FINAL_CLAIM_SCOPED
        object.__setattr__(self, "final_claim", final_claim)
        object.__setattr__(self, "final_evidence_ids", _as_tuple(self.final_evidence_ids))
        object.__setattr__(self, "risk_flags", _as_tuple(self.risk_flags))
        object.__setattr__(self, "ui_evidence_roles", _as_tuple(self.ui_evidence_roles))

    def selected_skill_set(self) -> set[str]:
        return set(self.selected_skill_names)

    def skipped_skill_map(self) -> dict[str, SkippedSkill]:
        return {skill.skill_name: skill for skill in self.skipped_candidate_skills}

    def steps_for_skill(self, skill_name: str) -> tuple[AgentWorkflowStep, ...]:
        return tuple(step for step in self.steps if step.skill_name == skill_name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "task_summary": self.task_summary,
            "inventory": self.inventory.to_dict(),
            "selected_skill_names": list(self.selected_skill_names),
            "skipped_candidate_skills": [skill.to_dict() for skill in self.skipped_candidate_skills],
            "steps": [step.to_dict() for step in self.steps],
            "final_claim": self.final_claim,
            "final_evidence_ids": list(self.final_evidence_ids),
            "risk_flags": list(self.risk_flags),
            "ui_evidence_roles": list(self.ui_evidence_roles),
            "task_trivial": self.task_trivial,
        }


@dataclass(frozen=True)
class AgentWorkflowRehearsalFinding:
    """One finding from agent workflow rehearsal."""

    code: str
    message: str
    severity: str = FINDING_SEVERITY_NEEDS_REVISION
    skill_name: str = ""
    step_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "skill_name", str(self.skill_name))
        object.__setattr__(self, "step_id", str(self.step_id))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "skill_name": self.skill_name,
            "step_id": self.step_id,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class AgentWorkflowRehearsalReport:
    """Review result for an `AgentWorkflowPlan`."""

    plan_id: str
    status: str
    inventory_snapshot_id: str
    findings: tuple[AgentWorkflowRehearsalFinding, ...] = ()
    selected_skills: tuple[str, ...] = ()
    skipped_skills: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == REHEARSAL_STATUS_PASS

    def format_text(self, max_findings: int = 10) -> str:
        lines = [
            "=== flowguard agent workflow rehearsal ===",
            f"plan_id: {self.plan_id}",
            f"status: {self.status}",
            f"inventory_snapshot_id: {self.inventory_snapshot_id}",
            f"selected_skills: {', '.join(self.selected_skills) if self.selected_skills else '(none)'}",
            f"skipped_skills: {', '.join(self.skipped_skills) if self.skipped_skills else '(none)'}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_findings]:
            location = ""
            if finding.skill_name:
                location += f" skill={finding.skill_name}"
            if finding.step_id:
                location += f" step={finding.step_id}"
            lines.append(f"- [{finding.severity}] {finding.code}{location}: {finding.message}")
        remaining = len(self.findings) - max_findings
        if remaining > 0:
            lines.append(f"... {remaining} more finding(s)")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "status": self.status,
            "inventory_snapshot_id": self.inventory_snapshot_id,
            "findings": [finding.to_dict() for finding in self.findings],
            "selected_skills": list(self.selected_skills),
            "skipped_skills": list(self.skipped_skills),
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(to_jsonable(self.to_dict()), indent=indent, sort_keys=True)


def _has_blocking_finding(findings: Sequence[AgentWorkflowRehearsalFinding]) -> bool:
    return any(finding.severity == FINDING_SEVERITY_BLOCKED for finding in findings)


def _has_revision_finding(findings: Sequence[AgentWorkflowRehearsalFinding]) -> bool:
    return any(finding.severity == FINDING_SEVERITY_NEEDS_REVISION for finding in findings)


def _has_scoped_finding(findings: Sequence[AgentWorkflowRehearsalFinding]) -> bool:
    return any(finding.severity == FINDING_SEVERITY_SCOPED for finding in findings)


def _status_from_findings(findings: Sequence[AgentWorkflowRehearsalFinding]) -> str:
    if _has_blocking_finding(findings):
        return REHEARSAL_STATUS_BLOCKED
    if _has_revision_finding(findings):
        return REHEARSAL_STATUS_NEEDS_REVISION
    if _has_scoped_finding(findings):
        return REHEARSAL_STATUS_SCOPED
    return REHEARSAL_STATUS_PASS


def _is_ui_workflow(plan: AgentWorkflowPlan) -> bool:
    haystack = " ".join(
        (
            plan.task_summary,
            " ".join(plan.risk_flags),
            " ".join(plan.selected_skill_names),
            " ".join(step.skill_name for step in plan.steps),
            " ".join(step.action for step in plan.steps),
        )
    ).lower()
    return any(token in haystack for token in ("ui", "frontend", "button", "visible", "flowguard-ui-flow-structure"))


def review_agent_workflow_rehearsal(plan: AgentWorkflowPlan) -> AgentWorkflowRehearsalReport:
    """Review an agent's intended installed-skill workflow before execution."""

    findings: list[AgentWorkflowRehearsalFinding] = []
    inventory = plan.inventory
    skills = inventory.skill_map()
    selected = plan.selected_skill_set()
    skipped = plan.skipped_skill_map()

    if not inventory.is_current_evidence():
        findings.append(
            AgentWorkflowRehearsalFinding(
                "stale_or_cached_skill_inventory",
                "Every rehearsal invocation must start from a fresh current-machine skill snapshot.",
                FINDING_SEVERITY_BLOCKED,
                metadata={"snapshot_id": inventory.snapshot_id, "from_cache": inventory.from_cache},
            )
        )

    if not inventory.skills:
        findings.append(
            AgentWorkflowRehearsalFinding(
                "empty_skill_inventory",
                "The rehearsal has no current skill inventory to inspect.",
                FINDING_SEVERITY_BLOCKED,
            )
        )

    unknown_selected = sorted(skill_name for skill_name in selected if skill_name not in skills)
    for skill_name in unknown_selected:
        findings.append(
            AgentWorkflowRehearsalFinding(
                "selected_skill_missing_from_inventory",
                "A selected skill is not present in the current snapshot.",
                FINDING_SEVERITY_NEEDS_REVISION,
                skill_name=skill_name,
            )
        )

    if plan.task_trivial and len(selected) > 1:
        findings.append(
            AgentWorkflowRehearsalFinding(
                "trivial_task_overtriggers_skills",
                "A trivial task should not start a multi-skill workflow unless the plan explains a real risk.",
                FINDING_SEVERITY_NEEDS_REVISION,
                metadata={"selected_count": len(selected)},
            )
        )

    if selected and not plan.steps:
        findings.append(
            AgentWorkflowRehearsalFinding(
                "selected_skills_without_steps",
                "Selected skills need ordered workflow steps before execution can be rehearsed.",
                FINDING_SEVERITY_NEEDS_REVISION,
            )
        )

    for skill in inventory.candidate_skills():
        skip = skipped.get(skill.skill_name)
        if skill.skill_name in selected:
            continue
        if skill.required_for_task and (skip is None or not skip.accepted):
            findings.append(
                AgentWorkflowRehearsalFinding(
                    "required_candidate_skill_skipped",
                    "A required candidate skill is missing from the plan without an accepted skip boundary.",
                    FINDING_SEVERITY_BLOCKED,
                    skill_name=skill.skill_name,
                    metadata=skill.to_dict(),
                )
            )
        elif skip is None:
            findings.append(
                AgentWorkflowRehearsalFinding(
                    "candidate_skill_not_dispositioned",
                    "A candidate skill is neither selected nor explicitly skipped with a reason.",
                    FINDING_SEVERITY_NEEDS_REVISION,
                    skill_name=skill.skill_name,
                    metadata=skill.to_dict(),
                )
            )

    for skip in plan.skipped_candidate_skills:
        if not skip.reason:
            findings.append(
                AgentWorkflowRehearsalFinding(
                    "skipped_skill_missing_reason",
                    "Skipped candidate skills require a reason.",
                    FINDING_SEVERITY_BLOCKED,
                    skill_name=skip.skill_name,
                    metadata=skip.to_dict(),
                )
            )
        if skip.accepted and not skip.consequence:
            findings.append(
                AgentWorkflowRehearsalFinding(
                    "skipped_skill_missing_consequence",
                    "Accepted skips must record the consequence or confidence boundary.",
                    FINDING_SEVERITY_NEEDS_REVISION,
                    skill_name=skip.skill_name,
                    metadata=skip.to_dict(),
                )
            )
        if skip.accepted and skills.get(skip.skill_name, SkillCapability(skip.skill_name)).required_for_task:
            findings.append(
                AgentWorkflowRehearsalFinding(
                    "required_skill_skip_scopes_claim",
                    "Skipping a required skill can only support scoped confidence unless later evidence closes the gap.",
                    FINDING_SEVERITY_SCOPED if plan.final_claim != FINAL_CLAIM_FULL else FINDING_SEVERITY_BLOCKED,
                    skill_name=skip.skill_name,
                    metadata=skip.to_dict(),
                )
            )

    completed_steps: set[str] = set()
    produced_evidence: set[str] = set()
    step_ids = {step.step_id for step in plan.steps}
    for step in plan.steps:
        missing_step_dependencies = sorted(
            set(step.order_after + step.required_completed_step_ids) - completed_steps
        )
        if missing_step_dependencies:
            findings.append(
                AgentWorkflowRehearsalFinding(
                    "workflow_step_out_of_order",
                    "A workflow step appears before its required predecessor steps.",
                    FINDING_SEVERITY_BLOCKED,
                    skill_name=step.skill_name,
                    step_id=step.step_id,
                    metadata={"missing_step_dependencies": missing_step_dependencies},
                )
            )

        missing_evidence = sorted(set(step.required_evidence_ids) - produced_evidence)
        if missing_evidence:
            findings.append(
                AgentWorkflowRehearsalFinding(
                    "workflow_step_missing_required_evidence",
                    "A step requires evidence that has not been produced by earlier steps.",
                    FINDING_SEVERITY_BLOCKED,
                    skill_name=step.skill_name,
                    step_id=step.step_id,
                    metadata={"missing_evidence": missing_evidence},
                )
            )

        if step.validation_required and not step.continue_evidence_ids:
            findings.append(
                AgentWorkflowRehearsalFinding(
                    "continue_gate_missing_evidence",
                    "Validation steps need evidence-bound continue gates.",
                    FINDING_SEVERITY_NEEDS_REVISION,
                    skill_name=step.skill_name,
                    step_id=step.step_id,
                )
            )

        if step.validation_required and not step.rework_step_id:
            findings.append(
                AgentWorkflowRehearsalFinding(
                    "rework_gate_missing",
                    "Validation steps need a declared rework target for failed validation.",
                    FINDING_SEVERITY_NEEDS_REVISION,
                    skill_name=step.skill_name,
                    step_id=step.step_id,
                )
            )
        elif step.rework_step_id and step.rework_step_id not in step_ids:
            findings.append(
                AgentWorkflowRehearsalFinding(
                    "rework_gate_unknown_step",
                    "A rework target references a step that is not in the plan.",
                    FINDING_SEVERITY_BLOCKED,
                    skill_name=step.skill_name,
                    step_id=step.step_id,
                    metadata={"rework_step_id": step.rework_step_id},
                )
            )

        if step.has_side_effect() and not step.required_evidence_ids and step.step_type != "work":
            findings.append(
                AgentWorkflowRehearsalFinding(
                    "side_effect_without_prior_evidence_gate",
                    "Side-effect or irreversible steps need a prior evidence gate.",
                    FINDING_SEVERITY_NEEDS_REVISION,
                    skill_name=step.skill_name,
                    step_id=step.step_id,
                    metadata=step.to_dict(),
                )
            )

        completed_steps.add(step.step_id)
        produced_evidence.update(step.produced_evidence_ids)

    for skill_name in sorted(selected):
        skill = skills.get(skill_name)
        if skill is None:
            continue
        if not skill.has_weak_validation_guidance():
            continue
        skill_steps = plan.steps_for_skill(skill_name)
        has_compensation = any(step.has_compensating_check() for step in skill_steps)
        if not has_compensation:
            severity = FINDING_SEVERITY_BLOCKED if plan.final_claim == FINAL_CLAIM_FULL else FINDING_SEVERITY_SCOPED
            findings.append(
                AgentWorkflowRehearsalFinding(
                    "selected_skill_has_weak_validation_guidance",
                    "A selected skill has weak or missing validation guidance and needs a compensating check.",
                    severity,
                    skill_name=skill_name,
                    metadata=skill.to_dict(),
                )
            )

    if plan.final_claim == FINAL_CLAIM_FULL and not plan.final_evidence_ids:
        findings.append(
            AgentWorkflowRehearsalFinding(
                "full_claim_missing_final_evidence",
                "A full completion, release, publish, or production-confidence claim needs final evidence ids.",
                FINDING_SEVERITY_BLOCKED,
            )
        )

    if plan.final_claim == FINAL_CLAIM_FULL and _is_ui_workflow(plan):
        missing_roles = sorted(set(UI_AGENT_EVIDENCE_ROLES) - set(plan.ui_evidence_roles))
        if missing_roles:
            findings.append(
                AgentWorkflowRehearsalFinding(
                    "ui_agent_role_evidence_missing",
                    "Full UI confidence needs separate inventory, baseline-semantics, and implementation-validation evidence roles.",
                    FINDING_SEVERITY_BLOCKED,
                    metadata={
                        "required_roles": list(UI_AGENT_EVIDENCE_ROLES),
                        "provided_roles": list(plan.ui_evidence_roles),
                        "missing_roles": missing_roles,
                    },
                )
            )

    if plan.final_claim == FINAL_CLAIM_FULL and any(
        finding.severity == FINDING_SEVERITY_SCOPED for finding in findings
    ):
        findings.append(
            AgentWorkflowRehearsalFinding(
                "full_claim_has_scoped_gaps",
                "Scoped rehearsal gaps must be closed before claiming full confidence.",
                FINDING_SEVERITY_BLOCKED,
            )
        )

    status = _status_from_findings(findings)
    return AgentWorkflowRehearsalReport(
        plan_id=plan.plan_id,
        status=status,
        inventory_snapshot_id=inventory.snapshot_id,
        findings=tuple(findings),
        selected_skills=tuple(sorted(selected)),
        skipped_skills=tuple(sorted(skipped)),
    )


__all__ = [
    "AgentWorkflowPlan",
    "AgentWorkflowRehearsalFinding",
    "AgentWorkflowRehearsalReport",
    "AgentWorkflowStep",
    "FINAL_CLAIM_BLOCKED",
    "FINAL_CLAIM_FULL",
    "FINAL_CLAIM_NONE",
    "FINAL_CLAIM_SCOPED",
    "FINAL_CLAIMS",
    "FINDING_SEVERITY_BLOCKED",
    "FINDING_SEVERITY_INFO",
    "FINDING_SEVERITY_NEEDS_REVISION",
    "FINDING_SEVERITY_SCOPED",
    "REHEARSAL_STATUS_BLOCKED",
    "REHEARSAL_STATUS_NEEDS_REVISION",
    "REHEARSAL_STATUS_PASS",
    "REHEARSAL_STATUS_SCOPED",
    "REHEARSAL_STATUSES",
    "SIDE_EFFECT_STEP_TYPES",
    "UI_AGENT_EVIDENCE_ROLES",
    "UI_EVIDENCE_ROLE_BASELINE_SEMANTICS",
    "UI_EVIDENCE_ROLE_IMPLEMENTATION_VALIDATION",
    "UI_EVIDENCE_ROLE_INVENTORY",
    "SkillCapability",
    "SkillInventorySnapshot",
    "SkippedSkill",
    "VALIDATION_GUIDANCE_EXTERNAL_ONLY",
    "VALIDATION_GUIDANCE_MANUAL_ONLY",
    "VALIDATION_GUIDANCE_MISSING",
    "VALIDATION_GUIDANCE_STATUSES",
    "VALIDATION_GUIDANCE_STRONG",
    "VALIDATION_GUIDANCE_WEAK",
    "WEAK_VALIDATION_GUIDANCE_STATUSES",
    "review_agent_workflow_rehearsal",
]
