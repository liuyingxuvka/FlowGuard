---
name: flowguard-development-process-flow
description: Use for staged development, modification, release, archive, or publish work where step ordering, touched artifacts, validation freshness, peer writes, or minimum revalidation affects safe continuation or confidence.
---

# FlowGuard Development Process Flow

Standalone FlowGuard satellite skill for lifecycle ordering and evidence
freshness. Use it when plan, edit, test, fix, install, shadow sync, archive,
release, or publish confidence depends on current artifact/evidence versions.

Return to `model-first-function-flow` when the basic FlowGuard route is unclear.
DevelopmentProcessFlow references sibling route evidence ids; it does not
inspect or replace sibling route internals.

## First Read

- Route id: `development_process_flow`.
- Core helpers: `review_development_process_flow()`,
  `derive_revalidation_plan()`, `review_auto_mesh_splits()`.
- Revalidation recommendations include route, proof, freshness gap, and blocked claims.
- Reference: `references/development_process_flow_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- For real target-project work, keep the AGENTS.md managed block/version record
  current or record why it was not updated.
- Do not create a fake mini-framework.
- Skipped, stale, failed, progress-only, or release-only evidence is not pass.
- Model/test reuse can be invalidated by later writes; reused output needs current `TestResultReuseTicket` plus `ProofArtifactRef`.
- Model transition changes stale transition coverage matrices, generated MTA
  obligations, and TestMesh required cell evidence unless refreshed.
- Model-code-test binding rows stale when any linked model obligation, owner
  code contract, code source, test evidence, transition cell, or proof artifact
  changes. Rerun Model-Test Alignment before done/release confidence.
- Field lifecycle/projection/replacement rows stale evidence when changed.
- Later writes can stale evidence or reopen maintenance obligations; preserve peer-agent changes.

## Minimum Workflow

1. List stages and touched artifacts.
2. Record which validation evidence covers which artifact version.
3. Identify later actions that stale evidence.
4. Include transition coverage and model-code-test binding regeneration when model/UI transitions, code owners, or tests changed.
5. Include field lifecycle, field projection, replacement disposition, and
   bug-repair closure artifacts when field-bearing work changed them.
6. Derive the minimum revalidation plan.
7. Triage failures before continuing or claiming done.

## Snapshot

Show artifact versions, action order, invalidations, evidence ids, minimum
revalidation, and unsupported claims.
When drawing the snapshot, edges mean order, invalidation, or required revalidation.

## Non-Goals

- Do not replace ModelMesh, TestMesh, StructureMesh, Model-Test Alignment,
  LongCheck, or Conformance Adoption.
- Do not treat background liveness as completion.
