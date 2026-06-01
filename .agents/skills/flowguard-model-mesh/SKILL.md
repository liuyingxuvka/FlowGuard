---
name: flowguard-model-mesh
description: Use when a FlowGuard project has three or more local models, an oversized model, stale child model evidence, parent/child model partitioning, target model split derivation, or hierarchical model-mesh governance needs.
---

# FlowGuard Model Mesh

Standalone FlowGuard satellite skill for parent/child model governance. Use it
when model evidence is oversized, stale, split across three or more local
models, or needs child reattachment and affected sibling review.

Return to `model-first-function-flow` for ordinary single-model work. Use
TestMesh for test hierarchy and StructureMesh for code hierarchy.

## First Read

- Route id: `model_mesh_maintenance`.
- Core helpers: `review_hierarchical_mesh()`,
  `review_mesh_closure_model()`, Child Reattachment Gate.
- Report evidence tiers/freshness before broad parent confidence.
- Reference: `references/model_mesh_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- For real target-project work, keep the AGENTS.md managed block/version record
  current or record why it was not updated.
- Do not create a fake mini-framework.
- Parent confidence needs parent coverage, legal child disjointness, current
  child reattachment, and leaf boundary-matrix evidence.
- Background or stale child evidence is scoped, not pass.
- Older child or parent model artifacts must be upgraded to the current
  FlowGuard shape, replaced, or explicitly blocked before they count as current
  mesh evidence.

## Minimum Workflow

1. Identify parent model, child models, partition items, and target split.
2. Classify old-shape parent/child evidence as upgraded, replaced, or blocked.
3. Review required hazards and child ownership boundaries.
4. Check parent coverage, child disjointness, and child reattachment.
5. Review affected siblings when a child boundary changed.
6. Keep whole-flow closure separate from local child green.

## Snapshot

Show a mesh diagram with parent, children, partition items, evidence
tiers/freshness, reattachment status, and what the mesh does or does not prove.
When drawing the snapshot, edges mean delegates, reattaches, consumes output, inherits obligations, or scopes confidence.

## Non-Goals

- Do not split tests; use TestMesh.
- Do not split code; use StructureMesh.
- Do not claim parent confidence from child-local green alone.
