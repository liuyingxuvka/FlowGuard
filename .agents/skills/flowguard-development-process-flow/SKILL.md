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

Show modes, artifact versions, action order, invalidations, evidence ids,
minimum revalidation, and unsupported claims.
Status note: mode, freshness, invalidated evidence, validation, unsupported claims, next step.

## Non-Goals

- Do not replace ModelMesh, TestMesh, StructureMesh, Model-Test Alignment,
  ContractExhaustionMesh, LongCheck, or Conformance Adoption.
- Do not treat background liveness as completion.


<!-- BEGIN SKILLGUARD CONTRACT LAYER -->
## Purpose

Use this skill for its declared flowguard workflow while binding each run to a route, evidence, checks, and a bounded completion claim.

## Entrypoint Scope

The entrypoint covers the installed flowguard-development-process-flow skill and the local materials explicitly routed by its instructions. It does not expand to unrelated repositories, private files, external services, publication, or release claims unless the user request and skill workflow explicitly include them.

## Local Material Routing

Resolve local materials from the active workspace, this skill directory, user-provided files, or explicitly configured project paths. Treat private machine paths as local-only inputs and keep public-facing instructions portable.

## Entrypoint Acceptance Map

A valid run selects one declared route, follows the phase order, records direct evidence, runs required checks, reports blockers and failures, and closes only inside the claim boundary. Available routes: model preflight, process review, evidence alignment, closure.

## Use When

Use when the user request matches the flowguard-development-process-flow activation boundary and needs this skill's governed workflow, source material, checks, or handoff behavior.

## Do Not Use When

Do not use when the task is outside this skill's domain, when required local materials are unavailable, when another more specific skill owns the request, or when the user asks only for a tiny direct answer.

## Required Workflow

Select the route, inspect local materials, perform the work in phase order, collect direct evidence, run the required checks, fix failures, and only then report progress or completion.

## Output Requirements

When reporting, include evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary. State clearly what was checked, what was not checked, and what remains blocked or uncertain.

## SkillGuard Maintenance

Keep the `.skillguard` control root, work contract, check manifest, check scripts, evidence records, and progress ledger current. Re-run SkillGuard checks after changing this entrypoint, route behavior, evidence rules, or closure wording.

<!-- END SKILLGUARD CONTRACT LAYER -->
