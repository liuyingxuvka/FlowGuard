---
name: flowguard-development-process-flow
description: Use as the FlowGuard development-process simulator front door for plans, multi-skill setup, staged work, install/sync, release/archive/publish, or final claims.
---

# FlowGuard Development Process Flow

Front-door FlowGuard satellite skill for the development-process simulator.
Rough plans, multi-skill workflows, and lifecycle claims enter here first; mode
owners supply evidence.

Return to `model-first-function-flow` when the route is unclear; cite sibling
evidence ids, not internals.

## First Read

- Route id: `development_process_flow`.
- Internal helper: `review_development_process_simulator()`; do not publish
  `development_process_simulator` as a separate direct route.
- Modes: `plan_detailing`, `agent_workflow`, `execution_freshness`.
- Delegates: PlanDetailing for rows, AgentWorkflowRehearsal for skill/tool
  order, this route for freshness.
- Lifecycle helpers: `review_development_process_flow()`,
  `derive_revalidation_plan()`, `review_auto_mesh_splits()`.
- Reference: `references/development_process_flow_protocol.md`.

## Hard Gates

- Verify the real package, keep AGENTS.md managed records current, and do not
  create a fake mini-framework.
- Ordinary rough plans and multi-skill setup enter this simulator before
  delegated mode skills.
- Skipped, stale, failed, progress-only, or release-only evidence is not pass.
- UI, payload schemas, fields, route docs, installed skills, prompts, and
  transitions stale their evidence.
- Replacing older same-class/boundary generation requires ContractExhaustionMesh
  cases/shards/receipts plus refreshed downstream evidence.
- Reused output needs current `TestResultReuseTicket` and `ProofArtifactRef`.
- New/deepened process models need template harvest closure before broad claims.
- Preserve peer changes; later writes can stale earlier evidence.

## Minimum Workflow

1. Classify modes: rough plan -> `plan_detailing`; multi-skill/tool action ->
   `agent_workflow`; implementation/install/sync/release/final claim ->
   `execution_freshness`.
2. For `plan_detailing`, require rows or delegated PlanDetailing evidence.
3. For `agent_workflow`, require fresh inventory, order, and gates.
4. For `execution_freshness`, list stages, artifact versions, validation
   evidence, invalidations, peer writes, and minimum revalidation.
5. If model-boundary coverage changes, include ContractExhaustionMesh and route
   profile/checklist updates before downstream closure.
6. Triage failures before continuing or claiming done.

## Snapshot

Snapshot: modes, versions, order, invalidations, evidence ids, revalidation; edges mean order, invalidation, or required revalidation.
Status: freshness, validation, unsupported claims, next step.

## Non-Goals

- Do not replace ModelMesh, TestMesh, StructureMesh, Model-Test Alignment,
  ContractExhaustionMesh, LongCheck, or Conformance Adoption.
- Do not treat background liveness as completion.

<!-- BEGIN SKILLGUARD CONTRACT LAYER -->
## Purpose
Bind each flowguard run to the declared integration mode, evidence, blockers, residual_risk, and claim_boundary.
## Entrypoint Scope
Covers flowguard-development-process-flow plus explicitly routed local materials; no unrelated repos, private files, external services, publication, or release claims unless requested and routed.
## Local Material Routing
Use workspace, skill directory, user files, or configured project paths; keep private machine paths local and public instructions portable.
## Entrypoint Acceptance Map
Use SkillGuard as the runtime contract executor attached to the native route/check owner: FlowGuard skill route map plus the real flowguard package/model checks. It enforces contract gates through that native owner before progress or closure; duplicate SkillGuard-owned execution paths are invalid. Declared gates/routes: model preflight, process review, evidence alignment, closure.
## Use When
Use when the request matches flowguard-development-process-flow and needs this governed workflow, materials, checks, or handoff behavior.
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
