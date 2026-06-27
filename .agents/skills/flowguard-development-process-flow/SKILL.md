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
Bind this FlowGuard route to one work contract, native checks, evidence, blockers, residual_risk, and claim_boundary.
## Entrypoint Scope
Covers flowguard-development-process-flow and routed local materials only; no unrelated repos, private paths, services, publication, or release claims unless separately routed.
## Local Material Routing
Use FlowGuard's native router, package/model checks, `.skillguard/work-contract.json`, check_manifest, and run records; keep public text portable.
## Entrypoint Acceptance Map
Mode is native-integrated/hybrid as declared; SkillGuard executes gates around the native owner and must not add a second execution route.
## Use When
Use when this skill is selected and the task needs governed route, evidence, check, handoff, or closure behavior.
## Do Not Use When
Do not use outside the skill domain, without required materials, when a more specific skill owns the work, or for tiny direct answers.
## Required Workflow
Select the FlowGuard-owned route, open/compile the contract, start/update run record, run native model/check gates, refresh evidence, fix blockers, then close from current checks.
## Hard Gates
Block skipped phases, stale/prose-only evidence, hollow contracts, quality downgrades, native-route conflicts, and completion claims with blockers.
## Output Requirements
Report target, route, evidence, failures, blockers, skipped_checks, residual_risk, and claim_boundary; separate checked facts from judgment.
## SkillGuard Maintenance
Refresh contracts, checks, evidence, and installed copies after entrypoint, route, evidence, or closure changes.
<!-- END SKILLGUARD CONTRACT LAYER -->
