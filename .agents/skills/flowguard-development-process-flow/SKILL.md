---
name: flowguard-development-process-flow
description: Use for staged development, modification, release, archive, or publish work where ordering, artifact versions, validation freshness, peer writes, writing-quality evidence, or minimum revalidation affects confidence.
---

# FlowGuard Development Process Flow

Standalone FlowGuard satellite skill for lifecycle order and evidence freshness.
Use when plan/edit/test/fix/install/release confidence depends on current artifact/evidence versions.
Return to `model-first-function-flow` when the basic route is unclear.

## First Read

- Route id: `development_process_flow`.
- Helpers: `review_development_process_flow()`, `derive_revalidation_plan()`, `review_auto_mesh_splits()`.
- Reference: `references/development_process_flow_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- Keep the AGENTS.md managed block/version record current, or record why not.
- Do not create a fake mini-framework.
- Skipped, stale, failed, progress-only, or release-only evidence is not pass.
- Later writes can stale model/test reuse; reused output needs current `TestResultReuseTicket` plus `ProofArtifactRef`.
- Model transition changes stale transition matrices, generated MTA obligations,
  and TestMesh required cells unless refreshed.
- UI action maps, payload schemas, fake file/work-package packs, and validation
  prompts stale their evidence when changed.
- Model-code-test binding rows stale when linked obligations, owners, code, tests, transition cells, or proof artifacts change.
- Field lifecycle/projection/replacement rows stale evidence when changed.
- Route graph/profile/docs/installed-skill rows stale AI-entry evidence when changed.
- Source-backed writing gates stale when literature progression, method depth, figure/table treatment, citation/footnote support, final prose, source registry, or revision report changes.
- Later writes can stale evidence or reopen obligations; preserve peer-agent changes.

## Minimum Workflow

1. List stages and touched artifacts.
2. Record which validation evidence covers which artifact version.
3. Identify later actions that stale evidence.
4. Regenerate transition coverage and model-code-test bindings when transitions, owners, or tests changed.
5. Include field lifecycle, payload, UI action, replacement, bug-closure, and writing quality-gate artifacts when those surfaces changed.
6. Derive the minimum revalidation plan.
7. Triage failures before continuing or claiming done.

## Snapshot

Show artifact versions, action order, invalidations, evidence ids, minimum revalidation, and unsupported claims; edges mean order, invalidation, or required revalidation.

## Non-Goals

- Do not replace ModelMesh, TestMesh, StructureMesh, Model-Test Alignment, LongCheck, or Conformance Adoption.
- Do not treat background liveness as completion.
