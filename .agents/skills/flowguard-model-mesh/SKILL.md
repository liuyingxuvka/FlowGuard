---
name: flowguard-model-mesh
description: Use for affected topology, partitions, stale child evidence, reattachment, siblings, or mesh closure; count alone is not a trigger.
---

# FlowGuard Model Mesh

## Purpose
Govern ownership, evidence tiers/freshness, partitions/reattach, siblings/closure.

## Entrypoint Scope
A standalone FlowGuard satellite skill; owns hierarchy, not test/code splits.

## Local Material Routing
After admission read `references/model_mesh_protocol.md`; load `references/model_mesh_partition_protocol.md`, `references/model_mesh_reattachment_protocol.md`, or `references/model_mesh_closure_protocol.md` only when triggered.

## Entrypoint Acceptance Map
Accept children; verify partitions/receipts; block incomplete closure.

## Use When
- A relation crosses models, a model is oversized/incomplete, or a changed child/sibling/whole-flow claim needs review.

## Do Not Use When
- Do not trigger on count, split tests/code, promote child-local green, or handle ordinary one-model work; use `flowguard`.

## Required Workflow
1. Inventory hierarchy, owners, partitions, and evidence freshness. Whole-flow claims disposition all models/relations.
2. Consume compact path-quality fingerprints. Reopen only changed children, ancestors, consumers, and siblings; ModelMaturation retains single-model judgment.
3. Review disjointness, Child Reattachment Gate, siblings, receipts, leaves, and closure. Topology may trigger deep review, never a second path comparison.
4. In blueprint scope, connect purpose, producers/consumers, realization refs to independent inventory/binding identities without copying semantics.
5. Consume `flowguard.portable_refinement.v1`; hand gaps/cases/receipts to alignment, test, risk, or portable owners without a second interpreter.

## Hard Gates
- Model-purpose gate: freeze task-specific failure(s) and claim_boundary; bind the candidate to native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose: no mode/fallback; only FlowGuard-declared checks may support completion claims. Require real FlowGuard check engine and AGENTS.md managed record; forbid a fake mini-framework.
- One logical model has one current instance; fingerprints bind model, runner, purpose, and inputs. Compile exact ownership before execution; never rerun-all.
- Multi-model replacement is one revision. Partial activation, stale head, omitted sibling, overlap, incomplete relation, stale receipt, or missing path-quality row blocks parent confidence.
- Ordinary work materializes affected topology; blueprint-wide topology needs explicit scope and never triggers repository discovery.
- Parent projections omit deep candidates/witnesses/costs. `normative_target` cannot replace `observed` until implementation/evidence match.
- ModelMesh proves relationships, not semantics, path quality, inventory, or qualification; counts prove none.

## Output Requirements
- Return evidence, failures, blockers, skipped_checks, residual_risk, claim_boundary, typed_next_actions, Child Reattachment Gate, siblings/gaps/receipts, mesh diagram; edges mean delegates, reattaches, consumes output, realizes, blocks. Blueprint adds depth/gap. Compact reads retain denominators, fingerprints, stale/not-run markers, omitted ids; not a second mesh authority.
