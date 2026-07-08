---
name: flowguard-development-process-flow
description: FlowGuard development-process simulator for plans, staged work, sync, release/archive/publish, and final claims.
---

# FlowGuard Development Process Flow

Front-door FlowGuard satellite skill for the development-process simulator.
Rough plans, multi-skill workflows, lifecycle claims, install/sync, and final confidence enter here first. Return to `model-first-function-flow` if unclear.

## First Read

- Route id: `development_process_flow`.
- Modes: `plan_detailing`, `agent_workflow`, `execution_freshness`.
- Helpers: `review_development_process_flow()`,
  `review_development_process_simulator()`, `derive_revalidation_plan()`,
  `review_auto_mesh_splits()`.
- Reference: `references/development_process_flow_protocol.md`.

## Hard Gates

- Verify FlowGuard check engine and AGENTS.md managed records; no fake mini-framework.
- Rough plans and multi-skill setup enter this simulator before delegated mode skills.
- Skipped, stale, failed, progress-only, or release-only evidence is not pass.
- UI, payload schemas, fields, route docs, installed skills, prompts, and transitions stale evidence.
- Same-class/boundary replacement needs ContractExhaustionMesh cases, shards, receipts, and evidence.
- Broad behavior work needs current ledger coverage: sources, commitments, owner model, evidence, gates.
- Path-sensitive work needs PPA: enumerate runtime/legacy/helper/facade/field/cache/migration/recovery paths, choose one authority, and repair primary failure.
- Broad no-fallback claims need the ledger first, then PPA for path-sensitive rows, Cartesian coverage, TestMesh, and Risk Ledger.
- Reused output needs current `TestResultReuseTicket` and `ProofArtifactRef`.
- New/deepened process models need template harvest closure before broad claims.
- Preserve peer changes; later writes can stale earlier evidence.

## Minimum Workflow

1. Classify mode: rough plan -> `plan_detailing`; skill/tool order ->
   `agent_workflow`; implementation/install/sync/release/final claim ->
   `execution_freshness`.
2. Require rows for `plan_detailing`, inventory/order/gates for `agent_workflow`,
   and artifact versions, validation, invalidations, peer writes, and minimum revalidation for `execution_freshness`.
3. If behavior coverage changes, include Behavior Commitment Ledger before model-specific closure.
4. If model-boundary coverage changes, include ContractExhaustionMesh and route
   profile/checklist updates before downstream closure.
5. Triage failures before continuing or claiming done.

## Snapshot

Show modes, artifact versions, action order, invalidations, evidence ids,
minimum revalidation, and unsupported claims.

Status note: mode, freshness, invalidated evidence, validation, unsupported claims, next step.

## Non-Goals

- Do not replace ModelMesh, TestMesh, StructureMesh, Model-Test Alignment, ContractExhaustionMesh, LongCheck, or Conformance Adoption.
- Do not treat background liveness as completion.
