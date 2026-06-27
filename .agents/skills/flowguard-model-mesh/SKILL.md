---
name: flowguard-model-mesh
description: Use when a FlowGuard project has three or more local models, an oversized model, stale child model evidence, parent/child model partitioning, target model split derivation, or hierarchical model-mesh governance needs.
---

# FlowGuard Model Mesh

Standalone FlowGuard satellite skill for parent/child model governance when
evidence is oversized, stale, split across local models, or needs child
reattachment and affected sibling review. Return to `model-first-function-flow`
for ordinary single-model work; use TestMesh for tests and StructureMesh for code.

## First Read

- Route id: `model_mesh_maintenance`.
- Core helpers: `review_hierarchical_mesh()`,
  `review_mesh_closure_model()`, `model_mesh_closure_to_contract_cases()`,
  Child Reattachment Gate.
- Report evidence tiers/freshness before broad parent confidence.
- Reference: `references/model_mesh_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- Keep the AGENTS.md managed block/version record current or record why not.
- Do not create a fake mini-framework.
- Parent confidence needs parent coverage, legal child disjointness, current
  child reattachment, and leaf boundary-matrix evidence.
- Background or stale child evidence is scoped, not pass.
- Old parent/child artifacts must be upgraded, replaced, or blocked.
- Parent/child stale evidence, unconsumed child output, and retry/no-delta
  loop hazards should be projected to ContractExhaustionMesh. Child-local green
  is not parent proof until those generated case ids are consumed by MTA,
  TestMesh, and risk evidence where relevant.
- Child-local Cartesian coverage is not parent coverage. Parent ModelMesh must
  consume child `ModelContractCoverageReceipt` ids before broad confidence.
- New/deepened child or parent models need template harvest closure before broad claims.

## Minimum Workflow

1. Identify parent model, child models, partition items, and target split.
2. Classify old-shape parent/child evidence as upgraded, replaced, or blocked.
3. Review required hazards and child ownership boundaries.
4. Check parent coverage, child disjointness, and child reattachment.
5. Review affected siblings when a child boundary changed.
6. Project closure hazards to ContractExhaustionMesh and keep whole-flow
   closure separate from local child green.
7. Require current child and parent coverage receipts; stale, missing,
   duplicate, incomplete, or unconsumed receipts block parent confidence.

## Snapshot

Show a mesh diagram with parent, children, partition items, case ids,
evidence tiers/freshness, reattachment, and claim boundary. Snapshot edges mean delegates, reattaches, consumes output, or blocks parent confidence.
Status note: parent, children, stale/missing evidence, reattachment, next mesh check.

## Non-Goals

- Do not split tests; use TestMesh.
- Do not split code; use StructureMesh.
- Do not claim parent confidence from child-local green alone.

<!-- BEGIN SKILLGUARD CONTRACT LAYER -->
## Purpose
Bind this FlowGuard route to one work contract, native checks, evidence, blockers, residual_risk, and claim_boundary.
## Entrypoint Scope
Covers flowguard-model-mesh and routed local materials only; no unrelated repos, private paths, services, publication, or release claims unless separately routed.
## Local Material Routing
Use FlowGuard's native router, package/model checks, `.skillguard/work-contract.json`, check_manifest, and run records; keep public text portable.
## Entrypoint Acceptance Map
Mode is native-integrated/hybrid as declared; SkillGuard executes gates around the native owner and must not add a second execution route.
## Use When
Use when this skill is selected and the task needs governed route, evidence, check, handoff, or closure behavior.
## Do Not Use When
Do not use outside the skill domain, without required materials, when a more specific skill owns the work, or for tiny direct answers.
## Required Workflow
Select the FlowGuard-owned route, open/compile the contract, start/update run record, run native model/check gates, refresh evidence, fix blockers, then close from current checks.
## Hard Gates
Block skipped phases, stale/prose-only evidence, hollow contracts, quality downgrades, native-route conflicts, and completion claims with blockers.
## Output Requirements
Report target, route, evidence, failures, blockers, skipped_checks, residual_risk, and claim_boundary; separate checked facts from judgment.
## SkillGuard Maintenance
Refresh contracts, checks, evidence, and installed copies after entrypoint, route, evidence, or closure changes.
<!-- END SKILLGUARD CONTRACT LAYER -->
