---
name: flowguard-development-process-flow
description: Use for any non-trivial staged development or modification task where step ordering, touched artifacts, validation evidence, evidence freshness, peer writes, or minimum revalidation affects whether the agent can safely continue or claim done; also use for release, archive, or publish confidence that depends on current evidence.
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
- Reference: `references/development_process_flow_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- For real target-project work, keep the AGENTS.md managed block/version record
  current or record why it was not updated.
- Do not create a fake mini-framework.
- Skipped, stale, failed, progress-only, or release-only evidence is not pass.
- Model and test reuse tickets can be invalidated by later writes; reused test
  output needs current `TestResultReuseTicket` plus `ProofArtifactRef`.
- Later writes can stale earlier evidence; preserve peer-agent changes.

## Minimum Workflow

1. List stages and touched artifacts.
2. Record which validation evidence covers which artifact version.
3. Identify later actions that stale evidence.
4. Derive the minimum revalidation plan.
5. Triage failures before continuing or claiming done.

## Snapshot

Show artifact versions, action order, invalidations, evidence ids, minimum
revalidation, and unsupported claims.

## Non-Goals

- Do not replace ModelMesh, TestMesh, StructureMesh, Model-Test Alignment,
  LongCheck, or Conformance Adoption.
- Do not treat background liveness as completion.
