"""Template text for FlowGuard plan-detailing compiler route."""

from __future__ import annotations

PLAN_DETAILING_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Compile a rough feature/change idea into structured plan-detail rows before
behavior modeling, implementation, validation, or done claims.

Guards against:
- happy-path-only plans being treated as complete;
- missing state, artifact, side-effect, validation, rework, or evidence detail;
- irreversible side effects without evidence gates;
- full completion claims without current final evidence.

Use before editing:
any non-trivial work that starts from a vague idea, short plan, or AI-generated
workflow outline.

Run:
python .flowguard/plan_detailing/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    PLAN_DETAIL_CLAIM_FULL,
    PlanDetail,
    PlanDetailEvidence,
    PlanDetailFailureBranch,
    PlanDetailFreshnessRule,
    PlanDetailSideEffect,
    PlanDetailSource,
    PlanDetailStateSurface,
    PlanDetailStep,
    PlanDetailSurface,
    PlanDetailValidation,
    ProcessArtifact,
    plan_detail_to_development_process,
    plan_detail_to_plan_intake,
    plan_detail_to_step_contracts,
    review_development_process_flow,
    review_plan_detail,
    review_plan_intake_completeness,
)


def detailed_plan() -> PlanDetail:
    return PlanDetail(
        "checkout-plan-detail",
        task_summary="Change checkout validation and prove the new workflow.",
        goal="Update checkout validation without stale tests or premature done claims.",
        sources=(PlanDetailSource("source:request", "manual", supports_surface_ids=("duplicate-submit",)),),
        surfaces=(
            PlanDetailSurface(
                "duplicate-submit",
                description="Repeated checkout submit must not create duplicate durable side effects.",
                source_ids=("source:request",),
                evidence_ids=("unit-pass",),
                high_risk=True,
                observed_failure_ids=("prior-duplicate-submit",),
                same_class_case_ids=("same-class-repeat-submit",),
                historical_holdout_ids=("holdout-checkout-submit",),
            ),
        ),
        artifacts=(
            ProcessArtifact("requirements.checkout", "requirement", "1"),
            ProcessArtifact("code.checkout", "code", "2", upstream_artifact_ids=("requirements.checkout",)),
            ProcessArtifact("tests.checkout", "test", "1"),
        ),
        state_surfaces=(
            PlanDetailStateSurface(
                "checkout_request_status",
                owner="checkout validation",
                read_by_step_ids=("model", "test"),
                written_by_step_ids=("edit-code",),
            ),
        ),
        side_effects=(
            PlanDetailSideEffect(
                "claim-done-side-effect",
                step_id="claim-done",
                effect_kind="done_claim",
                required_evidence_ids=("unit-pass",),
            ),
        ),
        steps=(
            PlanDetailStep(
                "model",
                "write or update FlowGuard model",
                produces_receipts=("model-current",),
                writes_artifacts=("requirements.checkout",),
            ),
            PlanDetailStep(
                "edit-code",
                "implement checkout validation",
                order_after=("model",),
                requires_receipts=("model-current",),
                produces_receipts=("code-updated",),
                writes_artifacts=("code.checkout",),
            ),
            PlanDetailStep(
                "test",
                "run checkout regression",
                order_after=("edit-code",),
                requires_receipts=("code-updated",),
                produces_receipts=("unit-pass",),
                produced_evidence_ids=("unit-pass",),
                continue_evidence_ids=("unit-pass",),
                validation_required=True,
                rework_step_id="edit-code",
            ),
            PlanDetailStep(
                "claim-done",
                "claim done after current evidence",
                order_after=("test",),
                requires_receipts=("unit-pass",),
                produces_receipts=("done-receipt",),
                required_evidence_ids=("unit-pass",),
                claim_labels=("done_claimed",),
                side_effect_ids=("claim-done-side-effect",),
            ),
        ),
        validations=(
            PlanDetailValidation(
                "unit-current",
                required_artifact_ids=("code.checkout", "tests.checkout"),
                required_evidence_kinds=("unit",),
                evidence_ids=("unit-pass",),
                command="python -m unittest tests.test_checkout",
            ),
        ),
        evidence=(
            PlanDetailEvidence(
                "unit-pass",
                "unit",
                "passed",
                produced_by_step_id="test",
                covers_artifacts=("code.checkout",),
                verifier_artifacts=("tests.checkout",),
                covered_versions={"code.checkout": "2", "tests.checkout": "1"},
                validation_ids=("unit-current",),
                command="python -m unittest tests.test_checkout",
                result_path="tmp/unit-pass.json",
            ),
        ),
        failure_branches=(
            PlanDetailFailureBranch(
                "unit-fails",
                trigger="unit validation fails",
                step_id="test",
                rework_step_id="edit-code",
                expected_resolution="fix implementation and rerun validation",
            ),
        ),
        freshness_rules=(
            PlanDetailFreshnessRule(
                "requirement-invalidates-code",
                "requirements.checkout",
                invalidates_artifact_ids=("code.checkout",),
            ),
        ),
        final_claim=PLAN_DETAIL_CLAIM_FULL,
        final_evidence_ids=("unit-pass",),
    )


def missing_failure_branch_plan() -> PlanDetail:
    base = detailed_plan()
    return PlanDetail(
        "missing-failure-branch",
        task_summary=base.task_summary,
        goal=base.goal,
        sources=base.sources,
        surfaces=base.surfaces,
        artifacts=base.artifacts,
        state_surfaces=base.state_surfaces,
        side_effects=base.side_effects,
        steps=base.steps,
        validations=base.validations,
        evidence=base.evidence,
        final_claim=PLAN_DETAIL_CLAIM_FULL,
        final_evidence_ids=("unit-pass",),
    )


def missing_rework_plan() -> PlanDetail:
    base = detailed_plan()
    steps = tuple(
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
            rework_step_id="" if step.step_id == "test" else step.rework_step_id,
            claim_labels=step.claim_labels,
            side_effect_ids=step.side_effect_ids,
        )
        for step in base.steps
    )
    return PlanDetail(
        "missing-rework",
        task_summary=base.task_summary,
        goal=base.goal,
        sources=base.sources,
        surfaces=base.surfaces,
        artifacts=base.artifacts,
        state_surfaces=base.state_surfaces,
        side_effects=base.side_effects,
        steps=steps,
        validations=base.validations,
        evidence=base.evidence,
        failure_branches=base.failure_branches,
        final_claim=PLAN_DETAIL_CLAIM_FULL,
        final_evidence_ids=("unit-pass",),
    )


def missing_validation_plan() -> PlanDetail:
    base = detailed_plan()
    return PlanDetail(
        "missing-validation",
        task_summary=base.task_summary,
        goal=base.goal,
        sources=base.sources,
        surfaces=base.surfaces,
        artifacts=base.artifacts,
        state_surfaces=base.state_surfaces,
        steps=base.steps,
        failure_branches=base.failure_branches,
        final_claim=PLAN_DETAIL_CLAIM_FULL,
    )


def run_checks():
    good = detailed_plan()
    missing_failure = missing_failure_branch_plan()
    missing_rework = missing_rework_plan()
    missing_validation = missing_validation_plan()
    detail_reports = (
        review_plan_detail(good),
        review_plan_detail(missing_failure),
        review_plan_detail(missing_rework),
        review_plan_detail(missing_validation),
    )
    intake = review_plan_intake_completeness(plan_detail_to_plan_intake(good))
    process = review_development_process_flow(plan_detail_to_development_process(good))
    contracts = plan_detail_to_step_contracts(good)
    return detail_reports, intake, process, contracts
'''

PLAN_DETAILING_RUN_CHECKS_TEMPLATE = '''"""Run the plan-detailing template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    detail_reports, intake, process, contracts = run_checks()
    print("=== flowguard plan-detailing template ===")
    for report in detail_reports:
        print(report.format_text(max_findings=4))
        print()
    print(intake.format_text(max_findings=4))
    print()
    print(process.format_text(max_findings=4))
    print(f"contracts: {len(contracts)}")
    good_ok = detail_reports[0].ok and intake.ok and process.ok and contracts
    broken_blocked = all(not report.ok for report in detail_reports[1:])
    return 0 if good_ok and broken_blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

PLAN_DETAILING_NOTES_TEMPLATE = """# FlowGuard Plan Detailing Notes

Use this scaffold when the work starts as a rough idea or short AI-generated
plan. The detail rows are the bridge between prose and FlowGuard checks.

## What To Fill In

- goal and scope;
- current source evidence;
- risk surfaces and out-of-scope reasons;
- artifacts that may be read, written, validated, or invalidated;
- state and side-effect surfaces that the behavior model must see;
- ordered steps with receipts and evidence gates;
- validation requirements and expected evidence ids;
- failure/retry/rework branches;
- human-review questions;
- final claim boundary.

Passing this plan-detail review means the plan is structured enough to proceed.
It does not prove the implementation is complete; downstream FlowGuard routes,
tests, replay, and evidence ledgers still own their proof.
"""

__all__ = [
    "PLAN_DETAILING_MODEL_TEMPLATE",
    "PLAN_DETAILING_RUN_CHECKS_TEMPLATE",
    "PLAN_DETAILING_NOTES_TEMPLATE",
]
