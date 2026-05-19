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
- Whole-flow parent confidence requires a green mesh closure model over root
  entries, child outputs, consumers, joins, terminals, and out-of-scope
  dispositions; partition coverage alone is not entry-to-exit closure.
- A repaired child model is not parent-green until the parent consumes its
  current evidence id and its input/output/state/side-effect contract still
  reattaches to the parent flow.
- Model-Miss Review owns the current bug instance and same-class bug
  responsibility; ModelMesh owns child-boundary propagation and affected
  sibling review.
- Background progress is liveness only, not pass evidence.
- Stale child evidence is not a pass.

## Workflow

1. Inventory local FlowGuard models, child scopes, ownership fields, and
   evidence freshness.
2. Derive the target split from model structure: source model, child models,
   covered partition items, ownership, and rationale.
3. Review parent and child responsibilities, shared state, cross-child edges,
   and required hazards.
4. For repaired child models, record the parent reattachment contract: expected
   inputs, outputs, state ownership, side-effect ownership, outgoing guarantees,
   and consumed child evidence id.
5. When whole-flow parent confidence is claimed, build or update the mesh
   closure model and make unconsumed child outputs, incomplete joins, terminal
   leaks, out-of-scope gaps, and loop-progress gaps fail.
6. If a child boundary changed, propagate the stale-boundary review upward and
   review affected siblings that share or depend on the same parent partition
   items, state writes, side effects, invariants, or contracts.
7. Confirm background long-running checks have final artifacts and exit status
   before consuming them as evidence.
8. Run child checks first, then parent review through hierarchical mesh
   helpers.
9. Record which child evidence ids the parent consumed and which are stale,
   skipped, or release-only.

## Owned Helpers

- `review_hierarchical_mesh(...)`
- `review_mesh_closure_model(...)`
- hierarchical model-mesh examples and docs.
- `references/model_mesh_protocol.md`

## Non-Goals

- Do not split tests; use `flowguard-test-mesh`.
- Do not split implementation modules; use `flowguard-structure-mesh`.
- Do not use Model-Test Alignment as a model mesh substitute.

For detailed route rules, read `references/model_mesh_protocol.md`.
