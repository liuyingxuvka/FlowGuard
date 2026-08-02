---
name: flowguard-model-mesh
description: Use for affected cross-model topology, oversized models, stale child evidence, partitioning, reattachment, affected siblings, or mesh closure risk; raw model count alone is not a trigger.
---

# FlowGuard Model Mesh

## Purpose
Govern ownership, freshness, reattachment, and closure without absorbing children.

## Entrypoint Scope
This standalone FlowGuard satellite skill owns model hierarchy, not test or code splits.

## Local Material Routing
After admission, read `references/model_mesh_protocol.md`. When its triggers apply, also read `references/model_mesh_partition_protocol.md`, `references/model_mesh_reattachment_protocol.md`, or `references/model_mesh_closure_protocol.md`; otherwise leave each unloaded.

## Entrypoint Acceptance Map
Accept bounded children; verify partitions/receipts; block overlap, staleness, missing closure, or incomplete leaves.

## Use When
- An affected relation crosses model boundaries; a model is oversized/incomplete; or a changed child, stale evidence, sibling, or whole-flow claim needs review.

## Do Not Use When
- Do not trigger on raw count, split tests/code, promote child-local green, or handle ordinary single-model work; use `flowguard`.

## Required Workflow
1. Load observed authority; inventory affected hierarchy, owners, partitions, evidence, and freshness.
2. Review disjointness, reattachment, siblings, receipts, leaves, and triggered closure.
3. Preserve gaps; hand exact cases/receipts to alignment, test, risk, or portable owners. Do not run a joint graph here.

## Hard Gates
- Model-purpose gate: declare the task-specific failure(s), bind native good/bad-per-failure/oracle/current evidence, and keep the declaration before candidate adoption. Reusable types are not fixed-purpose; there is no mode/fallback, and only FlowGuard-declared checks may support completion claims.
- One logical model has at most one snapshot instance; every typed relation binds a contained model or current owner artifact.
- Fingerprints bind model, runner, purpose, and owned inputs; snapshot owns global revision and Git stays release provenance.
- Compile ownership before execution. A governed path without one exact owner blocks at zero runners; never rerun-all.
- A multi-model replacement activates as one accepted revision set. Partial child activation, stale base heads, omitted affected siblings, or incomplete relation/coverage diffs block.
- Freeze task-specific failures/boundary; bind native good, bad-per-failure, oracle, candidate, and current evidence.
- Require the real FlowGuard check engine and AGENTS.md managed record; forbid fake mini-frameworks.
- Parent confidence requires complete partition ownership, legal overlap, current child evidence/receipts, and current parent consumption.
- Portable refinement needs complete reachable mappings (or legal stutter), no stronger assumptions, and no weaker guarantees.
- Progress is liveness only; missing closure feedback/bounds or template-harvest closure blocks broad confidence.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, `typed_next_actions`, mesh diagram, siblings, and receipts; edges mean delegates, reattaches, consumes output, or blocks.


<!--VTP:target adapter/catalog;native validation;stale|ambiguous=block;preview!=proof;harvest-->
