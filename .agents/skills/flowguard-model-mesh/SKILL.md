---
name: flowguard-model-mesh
description: Use for 3+ models, oversized models, stale child evidence, partitioning, reattachment, affected siblings, or mesh closure risk.
---

# FlowGuard Model Mesh

## Purpose
Govern ownership, freshness, reattachment, and closure without expanding children into the parent.

## Entrypoint Scope
This standalone FlowGuard satellite skill owns model hierarchy, not test or code splits.

## Local Material Routing
Read `references/model_mesh_protocol.md` for inventory, splits, partitions, Child Reattachment Gate, closure, and evidence tiers/freshness.

## Entrypoint Acceptance Map
Accept bounded children; verify partitions/receipts; block overlap, staleness, missing closure, or incomplete leaves.

## Use When
- 3+ models, oversized/incomplete groups, changed child boundaries, stale evidence, affected siblings, or parent whole-flow claims.

## Do Not Use When
- Do not split tests/code, trust child-local green as parent proof, or handle ordinary single-model work; send that to `flowguard`.

## Required Workflow
1. Load the observed snapshot; inventory hierarchy, owners, risks, partitions, evidence, freshness. Keep targets/experiments as candidates.
2. Review disjointness, reattachment, siblings, receipts, leaves, and closure. Portable claims need current fingerprints and a `flowguard.portable_refinement.v1` binding.
3. Preserve scoped/stale gaps; project cases/receipts to Model-Test Alignment, TestMesh, and closure owners.
4. Hand risk, exact children/relations, property owner, and current receipts to PortableSystem; do not run the joint graph here.

## Hard Gates
- One logical model has at most one snapshot instance; every typed relation binds a contained model or current owner artifact.
- A model fingerprint is local: model, runner, purpose, and local/shared inputs only. Snapshot owns global source revision; Git provenance is release traceability and never invalidates unchanged siblings.
- Compile local/shared/snapshot-only ownership before execution. A governed path without one exact owner blocks at zero runners; never rerun-all.
- A multi-model replacement activates as one accepted revision set. Partial child activation, stale base heads, omitted affected siblings, or incomplete relation/coverage diffs block.
- Model-purpose gate: freeze this instance's task-specific failure(s)/boundary and bind candidate plus native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose; no mode/fallback; only FlowGuard-declared checks may support completion claims.
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Parent confidence requires complete partition ownership, legal overlap, current child evidence/receipts, and current parent consumption.
- Portable refinement needs complete reachable mappings (or legal stutter), no stronger assumptions, and no weaker guarantees.
- Progress is liveness only; missing closure feedback/bounds or template-harvest closure blocks broad confidence.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, `typed_next_actions`, mesh diagram, siblings, and receipts; edges mean delegates, reattaches, consumes output, or blocks.


<!--VTP:target adapter/catalog;native validation;stale/ambiguous=block;preview!=proof;harvest:VTP-->
