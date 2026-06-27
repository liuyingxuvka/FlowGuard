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
Bind each flowguard run to the declared integration mode, evidence, blockers, residual_risk, and claim_boundary.
## Entrypoint Scope
Covers flowguard-plan-detailing-compiler plus explicitly routed local materials; no unrelated repos, private files, external services, publication, or release claims unless requested and routed.
## Local Material Routing
Use workspace, skill directory, user files, or configured project paths; keep private machine paths local and public instructions portable.
## Entrypoint Acceptance Map
Use SkillGuard as the runtime contract executor attached to the native route/check owner: FlowGuard skill route map plus the real flowguard package/model checks. It enforces contract gates through that native owner before progress or closure; duplicate SkillGuard-owned execution paths are invalid. Declared gates/routes: model preflight, process review, evidence alignment, closure.
## Use When
Use when the request matches flowguard-plan-detailing-compiler and needs this governed workflow, materials, checks, or handoff behavior.
## Do Not Use When
Do not use outside the domain, without required materials, when a more specific skill owns the work, or for tiny direct answers.
## Required Workflow
Select the target-owned native route/check surface, run the SkillGuard contract gates around the native workflow, collect evidence, run checks, fix failures, then report.
## Hard Gates
Do not skip phases, do not replace required evidence with prose, do not treat stale reports as current, do not weaken validation to pass, and do not claim completion when blockers remain.
## Output Requirements
Report evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary; distinguish checked, unchecked, blocked, and uncertain.
## SkillGuard Maintenance
Keep `.skillguard` contracts, checks, evidence, and ledger current; rerun SkillGuard after entrypoint, route, evidence, or closure changes.
<!-- END SKILLGUARD CONTRACT LAYER -->
