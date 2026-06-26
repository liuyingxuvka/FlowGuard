---
name: flowguard-plan-detailing-compiler
description: Use when explicitly requested or delegated by flowguard-development-process-flow's plan_detailing simulator mode to turn rough plans into detailed FlowGuard process rows. Generic rough-plan routing should enter flowguard-development-process-flow first.
---

# FlowGuard Plan Detailing Compiler

Delegated FlowGuard mode skill for structured plan rows. It remains directly
invokable when the user names PlanDetailing or another route delegates
`plan_detailing`; ordinary plan discussion enters
`flowguard-development-process-flow` first.

Return to `model-first-function-flow` when the FlowGuard route itself is unclear.
Return to DevelopmentProcessFlow for generic "make a better plan" requests.

## First Read

- Route id: `plan_detailing_compiler`.
- Simulator mode: `plan_detailing`; front door: `flowguard-development-process-flow`.
- Core helpers: `PlanDetail`, `PlanDetailStep`, `PlanDetailValidation`,
  `PlanDetailFailureBranch`, `review_plan_detail()`.
- Projections: `plan_detail_to_plan_intake()`,
  `plan_detail_to_step_contracts()`,
  `plan_detail_to_development_process()`,
  `plan_detail_to_agent_workflow_plan()`.
- Reference: `references/plan_detailing_compiler_protocol.md`.

## Hard Gates

- Verify the real package, AGENTS.md managed record, and no fake mini-framework.
- Do not present this as the generic first entry for rough-plan discussion.
- Long prose is not structured plan detail.
- Plan-detail pass is not implementation, release, or production proof.
- Full claims require final evidence ids and no scoped detail gaps.
- New/deepened models need template harvest closure.
- UI, import/export, generated artifact, and AI work-package plans need
  task/action coverage, human-operability evidence, payload cases for the real surface,
  execution proof refs, and manual review gates.

## Minimum Workflow

1. Capture goal, assumptions, scope, sources, and risk surfaces.
2. List artifacts, UI tasks/actions, payload/work-package surfaces, state,
   side effects, steps, receipts, validation, failures, questions, and claim boundary.
3. Run `review_plan_detail()`.
4. Project passing/scoped rows to downstream routes as needed.
5. Keep missing/scoped rows visible before downstream claims.

## Snapshot

Show goal, state/artifact surfaces, step receipts, validation evidence,
failure/rework branches, human questions, and claim scope.
Status note: plan goal, missing row, validation/rework gap, question, next step.

## Non-Goals

- Do not execute the work plan.
- Do not call LLM APIs from the model.
- Do not replace downstream route evidence or final closure contracts.


<!-- BEGIN SKILLGUARD CONTRACT LAYER -->
## Purpose

Use this skill for its declared flowguard workflow while binding each run to a route, evidence, checks, and a bounded completion claim.

## Entrypoint Scope

The entrypoint covers the installed flowguard-plan-detailing-compiler skill and the local materials explicitly routed by its instructions. It does not expand to unrelated repositories, private files, external services, publication, or release claims unless the user request and skill workflow explicitly include them.

## Local Material Routing

Resolve local materials from the active workspace, this skill directory, user-provided files, or explicitly configured project paths. Treat private machine paths as local-only inputs and keep public-facing instructions portable.

## Entrypoint Acceptance Map

A valid run selects one declared route, follows the phase order, records direct evidence, runs required checks, reports blockers and failures, and closes only inside the claim boundary. Available routes: model preflight, process review, evidence alignment, closure.

## Use When

Use when the user request matches the flowguard-plan-detailing-compiler activation boundary and needs this skill's governed workflow, source material, checks, or handoff behavior.

## Do Not Use When

Do not use when the task is outside this skill's domain, when required local materials are unavailable, when another more specific skill owns the request, or when the user asks only for a tiny direct answer.

## Required Workflow

Select the route, inspect local materials, perform the work in phase order, collect direct evidence, run the required checks, fix failures, and only then report progress or completion.

## Output Requirements

When reporting, include evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary. State clearly what was checked, what was not checked, and what remains blocked or uncertain.

## SkillGuard Maintenance

Keep the `.skillguard` control root, work contract, check manifest, check scripts, evidence records, and progress ledger current. Re-run SkillGuard checks after changing this entrypoint, route behavior, evidence rules, or closure wording.

<!-- END SKILLGUARD CONTRACT LAYER -->
