"""Executable scenarios for the plan-detailing compiler.

Risk Purpose Header:
This FlowGuard model reviews the plan-detailing compiler. It guards against
vague plans, happy-path-only plans, missing validation, missing rework gates,
ungated side effects, and overbroad completion claims before implementation.

Run:
python examples/plan_detailing_compiler/run_review.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from flowguard import (
    PLAN_DETAIL_CLAIM_FULL,
    PLAN_DETAIL_CLAIM_SCOPED,
    PlanDetail,
    PlanDetailEvidence,
    PlanDetailFailureBranch,
    PlanDetailHumanQuestion,
    PlanDetailSideEffect,
    PlanDetailSource,
    PlanDetailStateSurface,
    PlanDetailStep,
    PlanDetailSurface,
    PlanDetailValidation,
    ProcessArtifact,
    FunctionResult,
    Scenario,
    ScenarioExpectation,
    Workflow,
    review_plan_detail,
    review_scenarios,
)


@dataclass(frozen=True)
class PlanDetailOutput:
    status: str


class ReviewPlanDetail:
    name = "ReviewPlanDetail"
    reads = ("plan_detail",)
    writes = ("plan_detail_report",)
    input_description = "PlanDetail"
    output_description = "PlanDetailReviewReport"
    accepted_input_type = PlanDetail
    idempotency = "same structured plan produces one detail report"

    def apply(self, input_obj: PlanDetail, state: object) -> Iterable[FunctionResult]:
        report = review_plan_detail(input_obj)
        output = PlanDetailOutput(report.status)
        yield FunctionResult(
            output,
            output,
            label=f"plan_detail_{report.status}",
            reason=report.format_text(max_findings=2),
        )


GOOD_PLAN = PlanDetail(
    "good-plan-detail",
    task_summary="Add plan detailing compiler and prove it with focused checks.",
    goal="Make rough plans structurally checkable before implementation.",
    sources=(PlanDetailSource("source:user-request", "manual", supports_surface_ids=("rough-plan-detail",)),),
    surfaces=(
        PlanDetailSurface(
            "rough-plan-detail",
            description="AI-generated plans must not omit evidence, rework, or failure paths.",
            source_ids=("source:user-request",),
            evidence_ids=("detail-model-pass",),
            high_risk=True,
            observed_failure_ids=("prior-vague-plan-miss",),
            same_class_case_ids=("same-class-ai-plan-gap",),
            historical_holdout_ids=("holdout-plan-detail-regression",),
        ),
    ),
    artifacts=(
        ProcessArtifact("spec.plan-detailing", "requirement", "1"),
        ProcessArtifact("model.plan-detailing", "model", "1"),
        ProcessArtifact("code.plan-detailing", "code", "1"),
        ProcessArtifact("tests.plan-detailing", "test", "1"),
    ),
    state_surfaces=(
        PlanDetailStateSurface(
            "plan_detail_status",
            owner="plan detailing compiler",
            read_by_step_ids=("model", "validate"),
            written_by_step_ids=("implement",),
        ),
    ),
    side_effects=(
        PlanDetailSideEffect(
            "done-claim",
            step_id="claim-done",
            effect_kind="completion_claim",
            required_evidence_ids=("detail-model-pass",),
        ),
    ),
    steps=(
        PlanDetailStep(
            "model",
            "model plan-detailing hazards",
            produces_receipts=("model-current",),
            writes_artifacts=("model.plan-detailing",),
        ),
        PlanDetailStep(
            "implement",
            "implement compiler rows and review",
            order_after=("model",),
            requires_receipts=("model-current",),
            produces_receipts=("code-updated",),
            writes_artifacts=("code.plan-detailing",),
        ),
        PlanDetailStep(
            "validate",
            "run focused plan-detail tests",
            order_after=("implement",),
            requires_receipts=("code-updated",),
            produces_receipts=("detail-model-pass",),
            produced_evidence_ids=("detail-model-pass",),
            continue_evidence_ids=("detail-model-pass",),
            validation_required=True,
            rework_step_id="implement",
        ),
        PlanDetailStep(
            "claim-done",
            "claim completion only after current evidence",
            order_after=("validate",),
            requires_receipts=("detail-model-pass",),
            produces_receipts=("done-receipt",),
            required_evidence_ids=("detail-model-pass",),
            claim_labels=("done_claimed",),
            side_effect_ids=("done-claim",),
        ),
    ),
    validations=(
        PlanDetailValidation(
            "detail-model-current",
            required_artifact_ids=("code.plan-detailing", "tests.plan-detailing"),
            required_evidence_kinds=("model", "unit"),
            evidence_ids=("detail-model-pass",),
            command="python examples/plan_detailing_compiler/run_review.py",
        ),
    ),
    evidence=(
        PlanDetailEvidence(
            "detail-model-pass",
            "model",
            "passed",
            produced_by_step_id="validate",
            covers_artifacts=("code.plan-detailing",),
            verifier_artifacts=("tests.plan-detailing",),
            covered_versions={"code.plan-detailing": "1", "tests.plan-detailing": "1"},
            validation_ids=("detail-model-current",),
            command="python examples/plan_detailing_compiler/run_review.py",
            result_path="tmp/plan-detailing-review.json",
        ),
    ),
    failure_branches=(
        PlanDetailFailureBranch(
            "validation-fails",
            trigger="plan-detailing test or model review fails",
            step_id="validate",
            rework_step_id="implement",
            expected_resolution="repair compiler or model and rerun focused checks",
        ),
    ),
    final_claim=PLAN_DETAIL_CLAIM_FULL,
    final_evidence_ids=("detail-model-pass",),
)

VAGUE_PLAN = PlanDetail(
    "vague-plan",
    task_summary="Make this better.",
    final_claim=PLAN_DETAIL_CLAIM_FULL,
)

HAPPY_PATH_ONLY_PLAN = PlanDetail(
    "happy-path-only",
    task_summary=GOOD_PLAN.task_summary,
    goal=GOOD_PLAN.goal,
    sources=GOOD_PLAN.sources,
    surfaces=GOOD_PLAN.surfaces,
    artifacts=GOOD_PLAN.artifacts,
    state_surfaces=GOOD_PLAN.state_surfaces,
    steps=GOOD_PLAN.steps,
    validations=GOOD_PLAN.validations,
    evidence=GOOD_PLAN.evidence,
    final_claim=PLAN_DETAIL_CLAIM_FULL,
    final_evidence_ids=("detail-model-pass",),
)

MISSING_REWORK_PLAN = PlanDetail(
    "missing-rework",
    task_summary=GOOD_PLAN.task_summary,
    goal=GOOD_PLAN.goal,
    sources=GOOD_PLAN.sources,
    surfaces=GOOD_PLAN.surfaces,
    artifacts=GOOD_PLAN.artifacts,
    state_surfaces=GOOD_PLAN.state_surfaces,
    steps=tuple(
        PlanDetailStep(
            step.step_id,
            step.action,
            order_after=step.order_after,
            requires_receipts=step.requires_receipts,
            produces_receipts=step.produces_receipts,
            writes_artifacts=step.writes_artifacts,
            required_evidence_ids=step.required_evidence_ids,
            produced_evidence_ids=step.produced_evidence_ids,
            continue_evidence_ids=step.continue_evidence_ids,
            validation_required=step.validation_required,
            rework_step_id="" if step.step_id == "validate" else step.rework_step_id,
            claim_labels=step.claim_labels,
            side_effect_ids=step.side_effect_ids,
        )
        for step in GOOD_PLAN.steps
    ),
    validations=GOOD_PLAN.validations,
    evidence=GOOD_PLAN.evidence,
    failure_branches=GOOD_PLAN.failure_branches,
    final_claim=PLAN_DETAIL_CLAIM_FULL,
    final_evidence_ids=("detail-model-pass",),
)

UNGATED_SIDE_EFFECT_PLAN = PlanDetail(
    "ungated-side-effect",
    task_summary=GOOD_PLAN.task_summary,
    goal=GOOD_PLAN.goal,
    sources=GOOD_PLAN.sources,
    surfaces=GOOD_PLAN.surfaces,
    artifacts=GOOD_PLAN.artifacts,
    state_surfaces=GOOD_PLAN.state_surfaces,
    side_effects=(PlanDetailSideEffect("done-claim", step_id="claim-done", effect_kind="completion_claim"),),
    steps=GOOD_PLAN.steps,
    validations=GOOD_PLAN.validations,
    evidence=GOOD_PLAN.evidence,
    failure_branches=GOOD_PLAN.failure_branches,
    final_claim=PLAN_DETAIL_CLAIM_FULL,
    final_evidence_ids=("detail-model-pass",),
)

SCOPED_HUMAN_REVIEW_PLAN = PlanDetail(
    "scoped-human-review",
    task_summary=GOOD_PLAN.task_summary,
    goal=GOOD_PLAN.goal,
    sources=GOOD_PLAN.sources,
    surfaces=GOOD_PLAN.surfaces,
    artifacts=GOOD_PLAN.artifacts,
    state_surfaces=GOOD_PLAN.state_surfaces,
    steps=GOOD_PLAN.steps,
    validations=GOOD_PLAN.validations,
    evidence=GOOD_PLAN.evidence,
    failure_branches=GOOD_PLAN.failure_branches,
    human_questions=(PlanDetailHumanQuestion("product-choice", "Which UX path should win?", blocking=True),),
    final_claim=PLAN_DETAIL_CLAIM_SCOPED,
    final_evidence_ids=("detail-model-pass",),
    exploratory=True,
)


def _expect(summary: str, labels: Sequence[str]) -> ScenarioExpectation:
    return ScenarioExpectation(expected_status="ok", required_trace_labels=tuple(labels), summary=summary)


def scenario(name: str, description: str, plan: PlanDetail, expected_label: str) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        initial_state=None,
        external_input_sequence=(plan,),
        expected=_expect(description, (expected_label,)),
        workflow=Workflow((ReviewPlanDetail(),), name="plan_detailing_compiler"),
        invariants=(),
    )


def plan_detailing_scenarios() -> tuple[Scenario, ...]:
    return (
        scenario("PDC01_good_plan_passes", "detailed plan passes", GOOD_PLAN, "plan_detail_pass"),
        scenario("PDC02_vague_plan_blocks", "vague plan blocks", VAGUE_PLAN, "plan_detail_blocked"),
        scenario("PDC03_happy_path_only_blocks", "happy path only blocks full claim", HAPPY_PATH_ONLY_PLAN, "plan_detail_blocked"),
        scenario("PDC04_missing_rework_blocks", "missing rework blocks full claim", MISSING_REWORK_PLAN, "plan_detail_blocked"),
        scenario("PDC05_ungated_side_effect_blocks", "ungated side effect blocks", UNGATED_SIDE_EFFECT_PLAN, "plan_detail_blocked"),
        scenario("PDC06_human_review_scopes", "unresolved human question scopes exploratory plan", SCOPED_HUMAN_REVIEW_PLAN, "plan_detail_scoped"),
    )


def run_plan_detailing_review():
    return review_scenarios(plan_detailing_scenarios())


from flowguard.skill_contract_model import build_skill_contract_model_export

FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"


def export_contract_model():
    return build_skill_contract_model_export(
        skill_id="flowguard-plan-detailing-compiler",
        route_id="plan_detailing_compiler",
        owner_id="development_process_flow",
        parent_model_id="flowguard.development_process_flow",
        business_intent="Compile a rough non-trivial plan into plane-safe steps, gates, failure branches, and evidence requirements.",
        claim_boundary="This projection structures a plan and its agent-operation targets; it does not execute steps or absorb referenced product behavior.",
    )


__all__ = [
    "GOOD_PLAN",
    "HAPPY_PATH_ONLY_PLAN",
    "MISSING_REWORK_PLAN",
    "SCOPED_HUMAN_REVIEW_PLAN",
    "UNGATED_SIDE_EFFECT_PLAN",
    "VAGUE_PLAN",
    "export_contract_model",
    "plan_detailing_scenarios",
    "run_plan_detailing_review",
]
