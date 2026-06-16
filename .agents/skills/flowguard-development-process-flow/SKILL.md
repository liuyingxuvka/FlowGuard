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

## Non-Goals

- Do not replace ModelMesh, TestMesh, StructureMesh, Model-Test Alignment,
  ContractExhaustionMesh, LongCheck, or Conformance Adoption.
- Do not treat background liveness as completion.
