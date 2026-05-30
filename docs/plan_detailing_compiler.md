# Plan Detailing Compiler

Plan Detailing Compiler is the first FlowGuard route for rough ideas, short
plans, or AI-generated outlines. Its job is to make missing details visible
before behavior modeling, staged development, validation, or done claims begin.

It does not call an LLM and it does not execute the plan. A human or AI writes
structured `PlanDetail` rows; FlowGuard reviews whether those rows are detailed
enough to proceed.

## Required Rows

- `PlanDetailSource`: current source evidence for the plan.
- `PlanDetailSurface`: in-scope, scoped-out, recurring, or high-risk surfaces.
- `PlanDetailArtifact`: requirements, models, code, tests, docs, reports, or
  release artifacts the plan reads, writes, or validates.
- `PlanDetailStateSurface`: durable state or facts the model must see.
- `PlanDetailSideEffect`: irreversible or external effects that need evidence
  gates.
- `PlanDetailStep`: ordered work with receipts, evidence gates, and rework.
- `PlanDetailValidation`: validation obligations and expected evidence.
- `PlanDetailEvidence`: planned or current evidence rows.
- `PlanDetailFailureBranch`: failure, retry, blocked, or rework paths.
- `PlanDetailHumanQuestion`: unresolved choices that block or scope claims.
- `PlanDetailFreshnessRule`: upstream changes that stale artifacts or evidence.

## Review And Projection

Run `review_plan_detail(plan)`. The report returns `pass`, `needs_revision`,
`scoped`, or `blocked`. Full confidence is blocked whenever any detail gap
remains.

After review, project the same rows to downstream routes as needed:

- `plan_detail_to_plan_intake(...)`
- `plan_detail_to_step_contracts(...)`
- `plan_detail_to_development_process(...)`
- `plan_detail_to_agent_workflow_plan(...)`

A plan-detail pass means the plan is detailed enough for those route checks. It
does not prove implementation, replay, tests, release, or completion.

## Template

```powershell
python -m flowguard plan-detailing-template --output .
```

The template writes:

- `.flowguard/plan_detailing/model.py`
- `.flowguard/plan_detailing/run_checks.py`
- `docs/flowguard_plan_detailing.md`

The generated model includes one complete plan and broken variants for missing
failure branches, missing rework gates, and missing validation.
