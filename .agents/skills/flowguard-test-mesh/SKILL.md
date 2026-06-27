---
name: flowguard-test-mesh
description: Use when tests, checks, validation scripts, or evidence are too large, slow, layered, stale, skipped, release-only, or need parent/child test hierarchy and evidence freshness governance.
---

# FlowGuard Test Mesh

Standalone FlowGuard satellite skill for parent/child test hierarchy and
validation evidence freshness. Use it for large, slow, stale, skipped,
background, layered, release-only checks and child test scripts.

Return to `model-first-function-flow` for ordinary small test evidence.

## First Read

- Route id: `test_mesh_maintenance`.
- Core helpers: `review_test_mesh()`, `TestTargetSplitDerivation`,
  `TestSuiteEvidence`, `transition_coverage_to_required_leaf_cell_ids()`,
  `contract_exhaustion_to_test_mesh_cell_ids()`,
  `contract_exhaustion_to_test_mesh_shard_ids()`.
- Reference: `references/test_mesh_protocol.md`.

## Hard Gates

- Verify the real package, keep AGENTS.md managed records current, and do not
  create a fake mini-framework.
- Background runs are liveness, not pass evidence.
- Reused child-suite results need current `TestResultReuseTicket` and
  `ProofArtifactRef`.
- Parent confidence needs current child evidence and target split derivation.
- Large transition or artifact-payload matrices can feed required child ids;
  every required cell needs a current child owner.
- ContractExhaustionMesh is the canonical source for generated same-class,
  payload, transition, parent/child, and no-delta case ids that need child
  suite ownership. TestMesh reviews freshness and ownership; it does not invent
  replacement bad cases.
- ContractExhaustionMesh Cartesian shards are child evidence targets. A parent
  claim that depends on model-local combinations must list
  `required_coverage_shard_ids`; a child suite must own those shard ids with
  current passing, non-progress-only evidence.
- Model-Test Alignment still owns whether a required cell binds the model
  obligation, owner code contract, and external-contract test evidence.
- New/deepened model-derived test meshes need template harvest closure before
  broad claims.

## Minimum Workflow

1. Identify parent suite/check and partition items.
2. Derive target child suites or child test scripts from model risk.
3. Include transition, payload, same-class, no-delta, contract-exhaustion case
   ids, and contract coverage shard ids when the parent claim depends on them.
4. Attach result status, evidence tier, result path, freshness, and reuse proof.
5. Scope or block parent confidence when child evidence is stale or missing.

## Snapshot

Show a validation mesh diagram with parent gates, child tests, evidence status,
freshness, background status, and scoped gaps.
Status note: parent claim, child status, stale/skipped/background gaps, next rerun/split.

## Non-Goals

- Do not split production code or models.
- Do not treat release-only evidence as routine proof.

<!-- BEGIN SKILLGUARD CONTRACT LAYER -->
## Purpose
Bind this FlowGuard route to one work contract, native checks, evidence, blockers, residual_risk, and claim_boundary.
## Entrypoint Scope
Covers flowguard-test-mesh and routed local materials only; no unrelated repos, private paths, services, publication, or release claims unless separately routed.
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
