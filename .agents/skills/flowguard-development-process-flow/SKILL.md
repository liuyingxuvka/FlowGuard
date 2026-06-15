---
name: flowguard-development-process-flow
description: Use as the FlowGuard development-process simulator front door for non-trivial plan discussion, multi-skill workflow setup, staged development, install/sync, release, archive, publish, or final process claims. Record plan_detailing, agent_workflow, and execution_freshness modes before delegating.
---

# FlowGuard Development Process Flow

Front-door FlowGuard satellite skill for the development-process simulator.
Rough plans, multi-skill/tool workflows, and plan/edit/test/install/sync/release
confidence enter here first; internal mode owners supply detailed evidence.

Return to `model-first-function-flow` when the route is unclear; cite sibling evidence ids, not internals.

## First Read

- Route id: `development_process_flow`; simulator route id: `development_process_simulator`.
- Helper: `review_development_process_simulator()`.
- Modes: `plan_detailing`, `agent_workflow`, `execution_freshness`.
- Delegates: `flowguard-plan-detailing-compiler` for plan rows,
  `flowguard-agent-workflow-rehearsal` for skill/tool order, this skill for
  evidence freshness.
- Lifecycle helpers: `review_development_process_flow()`,
  `derive_revalidation_plan()`, `review_auto_mesh_splits()`.
- Reference: `references/development_process_flow_protocol.md`.

## Hard Gates

- Verify the real package and AGENTS.md managed records; do not create a fake mini-framework.
- Do not route ordinary rough plans or multi-skill setup directly to delegated
  mode skills; enter this simulator and record selected mode(s).
- Skipped, stale, failed, progress-only, or release-only evidence is not pass.
- UI, payload schemas, field, route docs, installed-skill, prompt, transition,
  and human-operability changes stale their evidence.
- Reused output needs current `TestResultReuseTicket` and `ProofArtifactRef`.
- New/deepened process models need template harvest closure before broad claims.
- Preserve peer changes; later writes can stale earlier evidence.

## Minimum Workflow

1. Classify modes: rough plan -> `plan_detailing`; multi-skill/tool/external
   action -> `agent_workflow`; implementation/install/sync/release/final claim
   -> `execution_freshness`.
2. For `plan_detailing`, require rows or a delegated PlanDetailing pass.
3. For `agent_workflow`, require fresh inventory/order/gates or a delegated
   AgentWorkflowRehearsal pass.
4. For `execution_freshness`, list stages, artifacts, validation evidence,
   invalidations, peer writes, and minimum revalidation.
5. Triage failures before continuing or claiming done.

## Snapshot

Show modes, artifact versions, action order, invalidations, evidence ids,
minimum revalidation, and unsupported claims.

## Non-Goals

- Do not replace ModelMesh, TestMesh, StructureMesh, Model-Test Alignment,
  LongCheck, or Conformance Adoption.
- Do not treat background liveness as completion.
