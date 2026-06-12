---
name: flowguard-development-process-flow
description: Use for staged development, modification, release, archive, or publish work where step ordering, artifact versions, validation freshness, peer writes, or minimum revalidation affects confidence.
---

# FlowGuard Development Process Flow

Standalone FlowGuard satellite skill for lifecycle order and evidence freshness
when plan, edit, test, fix, install, shadow sync, archive, release, or publish
confidence depends on current artifact/evidence versions.

Return to `model-first-function-flow` when the FlowGuard route is unclear; cite sibling evidence ids, not internals.

## First Read

- Route id: `development_process_flow`.
- Core helpers: `review_development_process_flow()`, `derive_revalidation_plan()`, `review_auto_mesh_splits()`.
- Revalidation output includes route, proof, freshness gap, blocked claim.
- Reference: `references/development_process_flow_protocol.md`.

## Hard Gates

- Verify the real package, keep AGENTS.md managed records current, and do not create a fake mini-framework.
- Skipped, stale, failed, progress-only, or release-only evidence is not pass.
- UI tasks need explicit completion evidence type; background or planned UI evidence does not satisfy `[x]`, done, release, or archive.
- Later writes can stale model/test reuse; reused output needs current `TestResultReuseTicket` plus `ProofArtifactRef`.
- Model transition changes stale transition matrices, generated MTA obligations, and TestMesh required cells unless refreshed.
- UI chains, human-operability, MATLAB callbacks, done reviews, payload schemas/surfaces/cases, and prompts stale evidence when changed.
- Model-code-test rows stale when linked obligations, owners, tests, transition cells, or proof artifacts change.
- Field lifecycle/projection/replacement rows stale evidence when changed.
- Route graph/profile/docs/installed-skill rows stale AI-entry evidence when changed.
- New/deepened process models need template harvest closure before broad claims.
- Later writes can stale evidence or reopen obligations; preserve peer changes.

## Minimum Workflow

1. List stages and touched artifacts.
2. Record which validation evidence covers which artifact version.
3. Identify later actions that stale evidence.
4. Regenerate transition coverage and model-code-test bindings when transitions,
   owners, or tests changed.
5. Include field lifecycle, payload, UI inventory/functional-chain/human-operability/MATLAB/done-claim, replacement, and bug-closure artifacts when changed.
6. Derive the minimum revalidation plan.
7. Triage failures before continuing or claiming done.

## Snapshot

Show artifact versions, action order, invalidations, evidence ids, minimum
revalidation, and unsupported claims. Edges mean order, invalidation, or
required revalidation.

## Non-Goals

- Do not replace ModelMesh, TestMesh, StructureMesh, Model-Test Alignment,
  LongCheck, or Conformance Adoption.
- Do not treat background liveness as completion.
