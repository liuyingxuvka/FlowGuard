---
name: flowguard-test-mesh
description: Use when tests/checks/evidence are large, slow, layered, stale, skipped, release-only, or need parent/child freshness.
---

# FlowGuard Test Mesh

Standalone FlowGuard satellite skill for parent/child test hierarchy and evidence freshness. Use it for large, slow, stale, skipped, background, layered, release-only checks and child test scripts. Return to `model-first-function-flow` for small tests.

## First Read

- Route id: `test_mesh_maintenance`.
- Core helpers: `review_test_mesh()`, `TestTargetSplitDerivation`, `TestSuiteEvidence`, transition/case/shard projection helpers.
- Reference: `references/test_mesh_protocol.md`.

## Hard Gates

- Verify FlowGuard check engine and AGENTS.md managed records; no fake mini-framework.
- Background runs are liveness, not pass evidence.
- Reused child-suite results need current `TestResultReuseTicket` and `ProofArtifactRef`.
- Parent confidence needs current child evidence and target split derivation.
- Large transition or artifact-payload matrices can feed required child ids; each cell needs a current child owner.
- ContractExhaustionMesh is the canonical source for same-class, payload, transition, parent/child, no-delta case ids, and shards. TestMesh reviews freshness/ownership.
- Parent claims using model-local combinations list `required_coverage_shard_ids`; child suites own those shards with current passing, non-progress-only evidence.
- Model-Test Alignment owns cell binding to model obligation, owner code contract, and external-contract test evidence.
- New/deepened model-derived test meshes need template harvest closure before broad claims.
- PPA matrices are TestMesh shard inputs for no-fallback confidence; primary-failure, compatibility, field, facade, runtime, and release shards need owners.
- Behavior Commitment Ledger matrices feed TestMesh shards for missing, extra, overlap, dependency, evidence, and PPA-handoff cases.

## Minimum Workflow

1. Identify parent suite/check and partition items.
2. Derive target child suites or child test scripts from model risk.
3. Include transition, payload, same-class, no-delta, contract-exhaustion case ids, and shard ids when parent confidence depends on them.
4. Attach result status, evidence tier, result path, freshness, and reuse proof.
5. Scope or block parent confidence when child evidence is stale or missing.
6. For Behavior Commitment Ledger, child evidence covers required commitment shard ids before parent confidence.
7. For PPA, child evidence proves no automatic alternate success and keeps skipped/stale/progress-only/release-only shards visible.

## Snapshot

Show a validation mesh diagram with parent gates, child tests, evidence, freshness, background status, and gaps.
Status note: parent claim, child status, stale/skipped/background gaps, next rerun/split.

## Non-Goals

- Do not split production code or models.
- Do not treat release-only evidence as routine proof.
