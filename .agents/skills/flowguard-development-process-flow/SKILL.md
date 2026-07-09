---
name: flowguard-development-process-flow
description: FlowGuard development-process simulator for plans, staged work, sync, release/archive/publish, and final claims.
---

# FlowGuard Development Process Flow

Front-door FlowGuard satellite skill for the development-process simulator. Rough plans, multi-skill workflows, lifecycle claims, install/sync, and final confidence enter here. Return to `model-first-function-flow` if unclear.

## First Read

- Route id: `development_process_flow`.
- Modes: `plan_detailing`, `agent_workflow`, `execution_freshness`.
- Helpers: `review_development_process_flow()`, `review_development_process_simulator()`, `derive_revalidation_plan()`, `review_auto_mesh_splits()`.
- Reference: `references/development_process_flow_protocol.md`.

## Hard Gates

- Verify FlowGuard check engine and AGENTS.md managed records; no fake mini-framework.
- Rough plans and multi-skill setup enter before delegated mode skills.
- Skipped, stale, failed, progress-only, or release-only evidence is not pass.
- UI, payload schemas, fields, route docs, installed skills, prompts, and transitions stale evidence.
- Same-class/boundary replacement needs ContractExhaustionMesh cases, shards, receipts, evidence.
- Broad behavior work needs current ledger coverage: sources, commitments, owner model, evidence, gates.
- Behavior/API/CLI/skill/template/process changes classify BCL mode first: bootstrap/add/change/remove/backfill/model-miss.
- Changed docs, prompts, API/CLI surfaces, templates, or skills stale BCL source surfaces until refreshed.
- Path-sensitive work needs PPA: enumerate paths, choose one authority, repair primary failure.
- Broad no-alternate-success claims need ledger, PPA, Cartesian coverage, TestMesh, and Risk Ledger.
- Reused output needs current `TestResultReuseTicket` and `ProofArtifactRef`.
- New/deepened process models need template harvest closure.
- Preserve peer changes; later writes can stale earlier evidence.

## Minimum Workflow

1. Classify mode: rough plan -> `plan_detailing`; skill/tool order -> `agent_workflow`; implementation/install/sync/release/final claim -> `execution_freshness`.
2. Record artifact versions, action order, invalidations, peer writes, validation, and minimum revalidation.
3. If behavior coverage changes, select BCL mode and include Behavior Commitment Ledger before model-specific closure.
4. If model-boundary coverage changes, include ContractExhaustionMesh and route profile/checklist updates.
5. If runtime/test/replay/manual evidence fails after green, route Model Miss Review, then backfeed commitment, owner model, DCAR, TestMesh.
6. Triage failures before continuing or claiming done.

## Snapshot

Show modes, artifact versions, action order, invalidations, evidence ids, minimum revalidation, unsupported claims.

## Non-Goals

- Do not replace ModelMesh, TestMesh, StructureMesh, MTA, ContractExhaustionMesh, LongCheck, or Conformance Adoption.
- Do not treat background liveness as completion.
