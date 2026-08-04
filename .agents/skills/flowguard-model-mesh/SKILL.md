---
name: flowguard-model-mesh
description: Use for affected topology, oversized models, stale child evidence, partitioning, reattachment, siblings, or mesh closure; count alone is not a trigger.
---

# FlowGuard Model Mesh

## Purpose
Govern model ownership, evidence tiers/freshness, partitioning, reattachment, siblings, and closure.

## Entrypoint Scope
This standalone FlowGuard satellite skill owns model hierarchy, not test/code splits.

## Local Material Routing
After admission, read `references/model_mesh_protocol.md`; load `references/model_mesh_partition_protocol.md`, `references/model_mesh_reattachment_protocol.md`, or `references/model_mesh_closure_protocol.md` only when triggered.

## Entrypoint Acceptance Map
Accept children; verify partitions/receipts; block overlap, stale or incomplete closure.

## Use When
- A relation crosses model boundaries, a model is oversized/incomplete, or a changed child/sibling/whole-flow claim needs review.

## Do Not Use When
- Do not trigger on raw count, split tests/code, promote child-local green, or handle ordinary single-model work; use `flowguard`.

## Required Workflow
1. Load observed authority; inventory hierarchy, owners, partitions, and evidence tiers/freshness. Whole-flow claims disposition every model and require consumer relations.
2. Review disjointness, Child Reattachment Gate, siblings, receipts, leaves, and triggered closure.
3. For explicit blueprint scope, connect purpose, producer/consumer, and realization references to independent inventory/binding identities without copying source semantics.
4. Consume explicit `flowguard.portable_refinement.v1` for portable refinement; preserve gaps and hand exact cases/receipts to alignment, test, risk, or portable owners without running a joint graph here.

## Hard Gates
- Model-purpose gate: freeze task-specific failure(s); bind native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose: no mode/fallback; only FlowGuard-declared checks may support completion claims. Require the real FlowGuard check engine and AGENTS.md managed record; forbid a fake mini-framework.
- One logical model has one current snapshot instance; fingerprints bind model, runner, purpose, and inputs. Compile exact ownership before execution; never rerun-all.
- Multi-model replacement is one revision set. Partial activation, stale heads, omitted siblings, illegal overlap, incomplete relations, or stale child receipts block parent confidence.
- Ordinary work materializes affected topology only. Blueprint-wide topology requires explicit scope and never triggers repository discovery.
- ModelMesh proves relationships, not source semantics, inventory, or static qualification. Counts alone prove none of them.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, `typed_next_actions`, Child Reattachment Gate, siblings, receipts, and a mesh diagram; edges mean delegates, reattaches, consumes output, realizes, or blocks. Blueprint output adds depth/first gap, fingerprints, and missing relations.


<!--VTP:target adapter/catalog;native validation;stale|ambiguous=block;preview!=proof;harvest-->
