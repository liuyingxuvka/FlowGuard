---
name: flowguard-plan-detailing-compiler
description: Use when a rough idea, vague request, short plan, or AI-generated workflow needs to become a detailed FlowGuard process plan before modeling, implementation, validation, or done claims.
---

# FlowGuard Plan Detailing Compiler

Standalone FlowGuard satellite skill for turning rough plans into structured
FlowGuard-ready detail rows. Use it before behavior modeling when the task is
non-trivial but the plan lacks explicit scope, state, artifacts, side effects,
receipts, validation, failure branches, rework gates, human-review questions,
or final evidence boundaries.

Return to `model-first-function-flow` when the FlowGuard route itself is
unclear. Use DevelopmentProcessFlow, PlanIntake, WorkflowStepContracts, and
AgentWorkflowRehearsal after plan-detail rows exist.

## First Read

- Route id: `plan_detailing_compiler`.
- Core helpers: `PlanDetail`, `PlanDetailStep`, `PlanDetailValidation`,
  `PlanDetailFailureBranch`, `review_plan_detail()`.
- Projection helpers: `plan_detail_to_plan_intake()`,
  `plan_detail_to_step_contracts()`,
  `plan_detail_to_development_process()`,
  `plan_detail_to_agent_workflow_plan()`.
- Reference: `references/plan_detailing_compiler_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- For real target-project work, keep the AGENTS.md managed block/version record
  current or record why it was not updated.
- Do not create a fake mini-framework.
- Do not treat long prose as structured plan detail.
- Plan-detail pass means the plan may proceed; it is not implementation,
  release, or production proof.
- Full claims require current final evidence ids and no scoped detail gaps.

## Minimum Workflow

1. Capture rough task, goal, assumptions, scope, sources, and risk surfaces.
2. List artifacts, state surfaces, side effects, steps, receipts, validation,
   failure/rework branches, human-review questions, and claim boundary.
3. Run `review_plan_detail()`.
4. Project passing/scoped rows to PlanIntake, WorkflowStepContracts,
   DevelopmentProcessFlow, and AgentWorkflowRehearsal as needed.
5. Keep missing/scoped rows visible before downstream modeling or claims.

## Snapshot

Show goal, state/artifact surfaces, step receipts, validation evidence,
failure/rework branches, human questions, and claim scope.

## Non-Goals

- Do not execute the work plan.
- Do not call LLM APIs from the model.
- Do not replace downstream route evidence or final closure contracts.
