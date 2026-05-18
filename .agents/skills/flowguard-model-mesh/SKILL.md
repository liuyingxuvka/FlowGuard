---
name: flowguard-model-mesh
description: Use when a FlowGuard project has three or more local models, an oversized model, stale child model evidence, parent/child model partitioning, target model split derivation, or hierarchical model-mesh governance needs.
---

# FlowGuard ModelMesh

This is a standalone FlowGuard satellite skill for parent/child model
partitioning. Use it directly when the model layer itself is too large,
numerous, stale, or hard to validate as one flat model.

Return to `model-first-function-flow` when the task is ordinary core modeling
or when it is unclear whether a mesh is needed.

## Hard Gates

- Verify the real package before claiming FlowGuard use:
  `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`.
- Do not create a fake mini-framework or prose-only substitute.
- Parent models consume child contracts and evidence; they do not inline every
  child route.
- Parent green confidence requires a FlowGuard-derived target split, not only
  a supplied partition map.
- Stale child evidence is not a pass.

## Workflow

1. Inventory local FlowGuard models, child scopes, ownership fields, and
   evidence freshness.
2. Derive the target split from model structure: source model, child models,
   covered partition items, ownership, and rationale.
3. Review parent and child responsibilities, shared state, cross-child edges,
   and required hazards.
4. Run child checks first, then parent review through hierarchical mesh
   helpers.
5. Record which child evidence ids the parent consumed and which are stale,
   skipped, or release-only.

## Owned Helpers

- `review_hierarchical_mesh(...)`
- hierarchical model-mesh examples and docs.
- `references/model_mesh_protocol.md`

## Non-Goals

- Do not split tests; use `flowguard-test-mesh`.
- Do not split implementation modules; use `flowguard-structure-mesh`.
- Do not use Model-Test Alignment as a model mesh substitute.

For detailed route rules, read `references/model_mesh_protocol.md`.
