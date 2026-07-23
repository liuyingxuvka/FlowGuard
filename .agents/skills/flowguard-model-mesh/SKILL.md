---
name: flowguard-model-mesh
description: Use when a FlowGuard project has three or more local models, an oversized model, stale child evidence, parent/child partitioning, target split derivation, child reattachment, affected siblings, or whole-flow mesh closure risk.
---

# FlowGuard Model Mesh

## Purpose
Govern parent/child ownership, freshness, reattachment, and closure without expanding child graphs into the parent.

## Entrypoint Scope
Route id: `model_mesh_maintenance`; role: `public_owner`; native owner: `model_mesh_maintenance`. This standalone FlowGuard satellite skill owns model hierarchy, not test/code splits.

## Local Material Routing
Read `references/model_mesh_protocol.md` for inventory, target split derivation, partition rules, Child Reattachment Gate, mesh closure, and evidence tiers/freshness.

## Entrypoint Acceptance Map
Accept a parent and bounded children; verify partitions/receipts; block overlap, stale child evidence, missing closure/liveness, or incomplete leaves; hand gaps to typed owners.

## Use When
- Use for 3+ models, oversized/incomplete model groups, changed child boundaries, stale child evidence, coverage receipts, affected siblings, or parent whole-flow claims.

## Do Not Use When
- Do not split tests or code, trust child-local green as parent proof, or use for ordinary single-model work; return that work to `flowguard`.

## Required Workflow
1. Load the observed authority snapshot; inventory its parent/children, typed owner relations, risk boundaries, target split derivation, ownership partitions, evidence tiers, and freshness. Build targets and experiments as separate candidate snapshots.
2. Review disjointness, reattachment, siblings, receipts, leaf boundaries, and closure/liveness. Portable claims require current parent/child fingerprints and an explicit `flowguard.portable_refinement.v1` binding.
3. Preserve scoped/stale gaps and project cases/receipts to Model-Test Alignment, TestMesh, and closure owners.
4. For hierarchical closure risk, hand exact child fingerprints, relations/roots, property owner, and current system/slice receipts to the portable-system owner; do not execute the joint graph here.

## Hard Gates
- One logical model has at most one instance in a snapshot. Every relation endpoint is typed and bound to either a contained model instance or a current native-owner artifact.
- A multi-model replacement activates as one accepted revision set. Partial child activation, stale base heads, omitted affected siblings, or incomplete relation/coverage diffs block.
- Model-purpose gate: before build/change, freeze this instance's task-specific failure(s) and boundary; then bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; only FlowGuard-declared checks may support completion claims.
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Parent confidence requires complete partition ownership, legal overlap, current child evidence/receipts, and current parent consumption.
- Portable refinement requires complete reachable child mappings (or legal stutter), no stronger assumptions, and no weaker guarantees; prose edges are insufficient.
- Background progress is liveness only; missing closure feedback/bounds or template harvest closure blocks broad mesh confidence.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, and `typed_next_actions`, plus a mesh diagram, reattachment, siblings, and receipt status.
- In the mesh diagram, edges mean delegates, reattaches, consumes output, or blocks the parent claim boundary.


<!--VTP:target adapter/catalog;native validation;stale/ambiguous=block;preview!=proof;harvest:VTP-->
