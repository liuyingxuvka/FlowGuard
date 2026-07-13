"""Executable scenarios for agent workflow rehearsal.

Risk Purpose Header:
This FlowGuard model reviews the new `flowguard-agent-workflow-rehearsal`
satellite. It guards against stale skill inventories, skipped required skills,
wrong ordering, weak skill validation guidance, missing rework gates,
overbroad final claims, and over-triggering small tasks before the agent starts
real work.

Run:
python examples/flowguard_agent_workflow_rehearsal/run_review.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from flowguard import (
    AgentWorkflowPlan,
    AgentWorkflowStep,
    FINAL_CLAIM_FULL,
    FINAL_CLAIM_SCOPED,
    FunctionResult,
    Scenario,
    ScenarioExpectation,
    SkillCapability,
    SkillInventorySnapshot,
    SkippedSkill,
    VALIDATION_GUIDANCE_MISSING,
    VALIDATION_GUIDANCE_STRONG,
    VALIDATION_GUIDANCE_WEAK,
    Workflow,
    review_agent_workflow_rehearsal,
    review_scenarios,
)


@dataclass(frozen=True)
class RehearsalOutput:
    status: str


class ReviewAgentWorkflowPlan:
    name = "ReviewAgentWorkflowPlan"
    reads = ("agent_workflow_plan",)
    writes = ("agent_workflow_rehearsal_report",)
    input_description = "AgentWorkflowPlan"
    output_description = "AgentWorkflowRehearsalReport"
    accepted_input_type = AgentWorkflowPlan
    idempotency = "same plan and inventory produce one rehearsal report"

    def apply(self, input_obj: AgentWorkflowPlan, state: object) -> Iterable[FunctionResult]:
        report = review_agent_workflow_rehearsal(input_obj)
        output = RehearsalOutput(report.status)
        yield FunctionResult(
            output,
            output,
            label=f"rehearsal_{report.status}",
            reason=report.format_text(max_findings=2),
        )


def _inventory(*skills: SkillCapability, snapshot_id: str = "fresh") -> SkillInventorySnapshot:
    return SkillInventorySnapshot(
        snapshot_id=snapshot_id,
        skills=tuple(skills),
        source_paths=("current-session-skills",),
        current=True,
        from_cache=False,
    )


def _required_skill(name: str, validation: str = VALIDATION_GUIDANCE_STRONG) -> SkillCapability:
    return SkillCapability(
        name,
        description=f"{name} skill",
        source="installed",
        candidate_for_task=True,
        required_for_task=True,
        validation_guidance_status=validation,
    )


def _candidate_skill(name: str, validation: str = VALIDATION_GUIDANCE_STRONG) -> SkillCapability:
    return SkillCapability(
        name,
        description=f"{name} skill",
        source="installed",
        candidate_for_task=True,
        validation_guidance_status=validation,
    )


GOOD_PLAN = AgentWorkflowPlan(
    "good-release-plan",
    "Complex release with current skill rehearsal.",
    _inventory(
        _required_skill("predictive-kb-preflight"),
        _required_skill("flowguard-development-process-flow"),
        _required_skill("publish-github-release"),
    ),
    selected_skill_names=(
        "predictive-kb-preflight",
        "flowguard-development-process-flow",
        "publish-github-release",
    ),
    steps=(
        AgentWorkflowStep(
            "kb",
            "predictive-kb-preflight",
            "retrieve release lessons",
            validation_required=True,
            produced_evidence_ids=("kb-hits",),
            continue_evidence_ids=("kb-hits",),
            rework_step_id="kb",
        ),
        AgentWorkflowStep(
            "process",
            "flowguard-development-process-flow",
            "derive revalidation plan",
            order_after=("kb",),
            required_evidence_ids=("kb-hits",),
            validation_required=True,
            produced_evidence_ids=("process-evidence",),
            continue_evidence_ids=("process-evidence",),
            rework_step_id="process",
        ),
        AgentWorkflowStep(
            "release",
            "publish-github-release",
            "publish after evidence",
            step_type="publish",
            order_after=("process",),
            required_evidence_ids=("process-evidence",),
            produced_evidence_ids=("release-evidence",),
            side_effects=("github_release",),
            irreversible=True,
        ),
    ),
    final_claim=FINAL_CLAIM_FULL,
    final_evidence_ids=("release-evidence",),
    risk_flags=("release", "external_action"),
)

STALE_SNAPSHOT_PLAN = AgentWorkflowPlan(
    "stale-snapshot-plan",
    "Plan tries to reuse a cached skill list.",
    SkillInventorySnapshot(
        "cached",
        skills=(_required_skill("publish-github-release"),),
        source_paths=("cache",),
        current=False,
        from_cache=True,
    ),
    selected_skill_names=("publish-github-release",),
    steps=(AgentWorkflowStep("release", "publish-github-release", "release"),),
    final_claim=FINAL_CLAIM_SCOPED,
)

MISSING_REQUIRED_SKILL_PLAN = AgentWorkflowPlan(
    "missing-required-skill",
    "Complex UI task skips the required UI validation skill.",
    _inventory(_required_skill("frontend-design"), _candidate_skill("browser")),
    selected_skill_names=("browser",),
    skipped_candidate_skills=(SkippedSkill("frontend-design", "will inspect code only", accepted=False),),
    steps=(
        AgentWorkflowStep(
            "browser",
            "browser",
            "quick browser smoke",
            validation_required=True,
            produced_evidence_ids=("browser-smoke",),
            continue_evidence_ids=("browser-smoke",),
            rework_step_id="browser",
        ),
    ),
    final_claim=FINAL_CLAIM_SCOPED,
)

WEAK_VALIDATION_PLAN = AgentWorkflowPlan(
    "weak-validation-plan",
    "Uses a skill with weak validation and keeps the claim scoped.",
    _inventory(_required_skill("custom-doc-skill", VALIDATION_GUIDANCE_WEAK)),
    selected_skill_names=("custom-doc-skill",),
    steps=(AgentWorkflowStep("doc", "custom-doc-skill", "generate document"),),
    final_claim=FINAL_CLAIM_SCOPED,
)

MISSING_REWORK_PLAN = AgentWorkflowPlan(
    "missing-rework-plan",
    "Validation step has no rework target.",
    _inventory(_required_skill("flowguard-development-process-flow")),
    selected_skill_names=("flowguard-development-process-flow",),
    steps=(
        AgentWorkflowStep(
            "process",
            "flowguard-development-process-flow",
            "validate process",
            validation_required=True,
            produced_evidence_ids=("process-evidence",),
            continue_evidence_ids=("process-evidence",),
        ),
    ),
    final_claim=FINAL_CLAIM_SCOPED,
)

WRONG_ORDER_PLAN = AgentWorkflowPlan(
    "wrong-order-plan",
    "Publishing happens before validation evidence exists.",
    _inventory(_required_skill("flowguard-development-process-flow"), _required_skill("publish-github-release")),
    selected_skill_names=("flowguard-development-process-flow", "publish-github-release"),
    steps=(
        AgentWorkflowStep(
            "release",
            "publish-github-release",
            "publish too early",
            step_type="publish",
            required_evidence_ids=("process-evidence",),
            side_effects=("github_release",),
            irreversible=True,
        ),
        AgentWorkflowStep(
            "process",
            "flowguard-development-process-flow",
            "validate after publish",
            validation_required=True,
            produced_evidence_ids=("process-evidence",),
            continue_evidence_ids=("process-evidence",),
            rework_step_id="process",
        ),
    ),
    final_claim=FINAL_CLAIM_FULL,
    final_evidence_ids=("process-evidence",),
)

OVERBROAD_CLAIM_PLAN = AgentWorkflowPlan(
    "overbroad-claim-plan",
    "Full claim has no final evidence.",
    _inventory(_required_skill("publish-github-release")),
    selected_skill_names=("publish-github-release",),
    steps=(AgentWorkflowStep("release", "publish-github-release", "release", produced_evidence_ids=("release",)),),
    final_claim=FINAL_CLAIM_FULL,
)

OVERTRIGGER_PLAN = AgentWorkflowPlan(
    "overtrigger-plan",
    "Tiny read-only task selects many skills.",
    _inventory(
        _candidate_skill("predictive-kb-preflight"),
        _candidate_skill("flowguard-development-process-flow"),
        _candidate_skill("logicguard", VALIDATION_GUIDANCE_MISSING),
    ),
    selected_skill_names=("predictive-kb-preflight", "flowguard-development-process-flow", "logicguard"),
    skipped_candidate_skills=(),
    steps=(
        AgentWorkflowStep("kb", "predictive-kb-preflight", "search"),
        AgentWorkflowStep("logic", "logicguard", "model"),
    ),
    final_claim=FINAL_CLAIM_SCOPED,
    task_trivial=True,
)


def _expect_ok(summary: str, labels: Sequence[str]) -> ScenarioExpectation:
    return ScenarioExpectation(expected_status="ok", required_trace_labels=tuple(labels), summary=summary)


def scenario(name: str, description: str, plan: AgentWorkflowPlan, expected_label: str) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        initial_state=None,
        external_input_sequence=(plan,),
        expected=_expect_ok(description, (expected_label,)),
        workflow=Workflow((ReviewAgentWorkflowPlan(),), name="flowguard_agent_workflow_rehearsal"),
        invariants=(),
    )


def agent_workflow_rehearsal_scenarios() -> tuple[Scenario, ...]:
    return (
        scenario("AWS01_good_plan_passes", "good plan passes", GOOD_PLAN, "rehearsal_pass"),
        scenario(
            "AWS02_stale_snapshot_blocks",
            "stale cached snapshot is blocked",
            STALE_SNAPSHOT_PLAN,
            "rehearsal_blocked",
        ),
        scenario(
            "AWS03_missing_required_skill_blocks",
            "missing required skill is blocked",
            MISSING_REQUIRED_SKILL_PLAN,
            "rehearsal_blocked",
        ),
        scenario(
            "AWS04_weak_validation_scopes",
            "weak skill validation scopes confidence",
            WEAK_VALIDATION_PLAN,
            "rehearsal_scoped",
        ),
        scenario(
            "AWS05_missing_rework_needs_revision",
            "missing rework gate needs revision",
            MISSING_REWORK_PLAN,
            "rehearsal_needs_revision",
        ),
        scenario("AWS06_wrong_order_blocks", "wrong ordering is blocked", WRONG_ORDER_PLAN, "rehearsal_blocked"),
        scenario(
            "AWS07_overbroad_claim_blocks",
            "full claim without final evidence is blocked",
            OVERBROAD_CLAIM_PLAN,
            "rehearsal_blocked",
        ),
        scenario(
            "AWS08_trivial_task_overtrigger_revises",
            "trivial task over-trigger needs revision",
            OVERTRIGGER_PLAN,
            "rehearsal_needs_revision",
        ),
    )


def run_agent_workflow_rehearsal_review():
    return review_scenarios(agent_workflow_rehearsal_scenarios())


from flowguard.skill_contract_model import build_skill_contract_model_export

FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"


def export_contract_model():
    return build_skill_contract_model_export(
        skill_id="flowguard-agent-workflow-rehearsal",
        route_id="agent_workflow_rehearsal",
        owner_id="development_process_flow",
        parent_model_id="flowguard.development_process_flow",
        business_intent="Rehearse a selected AI-operation workflow while keeping referenced product commitments as typed target context.",
        claim_boundary="This projection rehearses agent-operation order and gates only; it neither owns product runtime behavior nor guarantees future AI choices.",
    )


__all__ = [
    "agent_workflow_rehearsal_scenarios",
    "export_contract_model",
    "run_agent_workflow_rehearsal_review",
]
