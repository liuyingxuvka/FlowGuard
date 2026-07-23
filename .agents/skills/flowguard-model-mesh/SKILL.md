---
name: flowguard-model-mesh
description: Use for 3+ models, oversized models, stale child evidence, partitioning, reattachment, affected siblings, or mesh closure risk.
---

# FlowGuard Model Mesh

## Purpose
Govern parent/child ownership, freshness, reattachment, and closure without expanding child graphs into the parent.

## Entrypoint Scope
This standalone FlowGuard satellite skill owns model hierarchy, not test or code splits.

## Local Material Routing
Read `references/model_mesh_protocol.md` for inventory, target split derivation, partition rules, Child Reattachment Gate, mesh closure, and evidence tiers/freshness.

## Entrypoint Acceptance Map
Accept a parent and bounded children; verify partitions/receipts; block overlap, stale evidence, missing closure, or incomplete leaves.

## Use When
- Use for 3+ models, oversized/incomplete model groups, changed child boundaries, stale child evidence, coverage receipts, affected siblings, or parent whole-flow claims.

## Do Not Use When
- Do not split tests or code, trust child-local green as parent proof, or use for ordinary single-model work; return that work to `flowguard`.

## Required Workflow
1. Load the observed snapshot; inventory hierarchy, typed owners, risks, partitions, evidence, and freshness. Keep targets and experiments in separate candidate snapshots.
2. Review disjointness, reattachment, siblings, receipts, leaves, and closure. Portable claims need current fingerprints and a `flowguard.portable_refinement.v1` binding.
3. Preserve scoped/stale gaps and project cases/receipts to Model-Test Alignment, TestMesh, and closure owners.
4. Hand closure risk, exact children/relations, property owner, and current receipts to PortableSystem; do not run the joint graph here.

## Hard Gates
- One logical model has at most one snapshot instance; every typed relation binds a contained model or current owner artifact.
- A multi-model replacement activates as one accepted revision set. Partial child activation, stale base heads, omitted affected siblings, or incomplete relation/coverage diffs block.
- Model-purpose gate: before build/change, freeze this instance's task-specific failure(s) and boundary; then bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; only FlowGuard-declared checks may support completion claims.
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Parent confidence requires complete partition ownership, legal overlap, current child evidence/receipts, and current parent consumption.
- Portable refinement needs complete reachable mappings (or legal stutter), no stronger assumptions, and no weaker guarantees.
- Background progress is liveness only; missing closure feedback/bounds or template harvest closure blocks broad mesh confidence.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, `typed_next_actions`, mesh diagram, siblings, and receipts; edges mean delegates, reattaches, consumes output, or blocks the parent.


<!--VTP:target adapter/catalog;native validation;stale/ambiguous=block;preview!=proof;harvest:VTP-->
