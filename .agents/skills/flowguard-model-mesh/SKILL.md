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
- Parent confidence also requires layered boundary proof when child contracts
  are being consumed: child models must cover the parent responsibilities, avoid
  illegal overlap, reattach with current evidence ids, and delegate finite leaf
  code surfaces to boundary-matrix evidence.
- Layered proof used for parent confidence should run with
  `require_proof_artifacts=True`: child contracts and leaf boundary cells need
  proof artifacts with result paths, fingerprints, current route evidence, and
  obligation coverage, not only declared `passed/current` rows.
- If Model-Test Alignment finds multiple primary `edge_path` proofs for one
  parent obligation, treat that as a model split signal. Do not accept a label
  downgrade as parent confidence unless the evidence reappears under child
  obligations or leaf matrix cells.
- A repaired child model is not parent-green until the parent consumes its
  current evidence id and its input/output/state/side-effect contract still
  reattaches to the parent flow.
- If a child model owns a real code surface with finite inputs or outputs,
  parent confidence must consume current code-boundary conformance evidence or
  explicitly mark that runtime boundary as out of scope.
- If DevelopmentProcessFlow classifies a validation failure as model too thick
  or oversized model evidence, ModelMesh owns the split and parent
  reattachment. Do not keep pushing the thick model as direct parent evidence.
- If `review_auto_mesh_splits(...)` reports a required model split for
  oversized state count, pending budgeted states, separable areas, broad
  parent evidence, or background progress-only status, ModelMesh owns the
  target split and child evidence. Do not treat the original direct evidence as
  full parent confidence.
- Model-Miss Review owns the current bug instance and same-class bug
  responsibility; ModelMesh owns child-boundary propagation and affected
  sibling review.
- Child boundary changes, parent reattachment gaps, duplicate edge paths, and
  oversized direct evidence should also become `review_model_maturation_loop(...)`
  signals before broad parent confidence is claimed.
- Background progress is liveness only, not pass evidence.
- Stale child evidence is not a pass.
- If sibling models or child boundaries appear to express the same
  implementation responsibility and the desired result is a smaller code
  architecture, route to `flowguard-architecture-reduction` before expanding
  the mesh.

## Workflow

1. Inventory local FlowGuard models, child scopes, ownership fields, and
   evidence freshness.
2. Derive the target split from model structure: source model, child models,
   covered partition items, ownership, and rationale.
3. For automatic split or DevelopmentProcessFlow `model_too_thick` handoffs,
   classify the thick
   source model as compatibility evidence unless it is still small enough for
   direct parent consumption, then derive focused child models before parent
   confidence.
4. Review parent and child responsibilities, shared state, cross-child edges,
   and required hazards.
5. For repaired child models, record the parent reattachment contract: expected
   inputs, outputs, state ownership, side-effect ownership, outgoing guarantees,
   and consumed child evidence id.
6. When parent confidence depends on child contracts, run or prepare
   `review_layered_boundary_proof(...)` with parent coverage, child
   disjointness, reattachment, and leaf boundary matrix rows.
7. When whole-flow parent confidence is claimed, build or update the mesh
   closure model and make unconsumed child outputs, incomplete joins, terminal
   leaks, out-of-scope gaps, and loop-progress gaps fail.
8. If a child boundary changed, propagate the stale-boundary review upward and
    review affected siblings that share or depend on the same parent partition
    items, state writes, side effects, invariants, or contracts.
9. If the changed child boundary maps to real code, require Model-Test
    Alignment code-boundary observations before treating the child handoff as
    runtime-safe.
10. Feed boundary-change, reattachment, oversized-model, and duplicate-edge-path
    findings to `review_model_maturation_loop(...)`.
11. When sibling overlap suggests redundant implementation structure, hand the
    ownership and contract snapshot to Architecture Reduction before creating
    more child models.
12. Confirm background long-running checks have final artifacts and exit status
    before consuming them as evidence.
13. Run child checks first, then parent review through hierarchical mesh
    helpers.
14. Record which child evidence ids the parent consumed and which are stale,
    skipped, or release-only.
15. Feed consumed child evidence ids and stale/skipped/release-only gaps to the
    Risk Evidence Ledger before a broad final confidence claim.
16. For non-trivial meshes, default to a user-facing Mermaid mesh diagram
    showing root entries, child model boundaries, handoffs, evidence tiers/freshness,
    blockers, and what the mesh does or does not prove. Its
    edges mean delegates, reattaches, consumes output, affects sibling, or
    invalidates evidence; they are not a linear workflow. Tiny reviews may stay
    concise. Do not inline every child model's internals, and do not treat the
    diagram as validation evidence.

## Owned Helpers

- `review_hierarchical_mesh(...)`
- `review_mesh_closure_model(...)`
- hierarchical model-mesh examples and docs.
- `references/model_mesh_protocol.md`

## Non-Goals

- Do not split tests; use `flowguard-test-mesh`.
- Do not split implementation modules; use `flowguard-structure-mesh`.
- Do not decide whether overlapping model boundaries imply code contraction;
  use `flowguard-architecture-reduction` for that bridge.
- Do not use Model-Test Alignment as a model mesh substitute.

For detailed route rules, read `references/model_mesh_protocol.md`.
