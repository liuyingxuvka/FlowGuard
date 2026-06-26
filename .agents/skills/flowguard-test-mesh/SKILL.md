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

Use this skill for its declared flowguard workflow while binding each run to a route, evidence, checks, and a bounded completion claim.

## Entrypoint Scope

The entrypoint covers the installed flowguard-test-mesh skill and the local materials explicitly routed by its instructions. It does not expand to unrelated repositories, private files, external services, publication, or release claims unless the user request and skill workflow explicitly include them.

## Local Material Routing

Resolve local materials from the active workspace, this skill directory, user-provided files, or explicitly configured project paths. Treat private machine paths as local-only inputs and keep public-facing instructions portable.

## Entrypoint Acceptance Map

A valid run selects one declared route, follows the phase order, records direct evidence, runs required checks, reports blockers and failures, and closes only inside the claim boundary. Available routes: model preflight, process review, evidence alignment, closure.

## Use When

Use when the user request matches the flowguard-test-mesh activation boundary and needs this skill's governed workflow, source material, checks, or handoff behavior.

## Do Not Use When

Do not use when the task is outside this skill's domain, when required local materials are unavailable, when another more specific skill owns the request, or when the user asks only for a tiny direct answer.

## Required Workflow

Select the route, inspect local materials, perform the work in phase order, collect direct evidence, run the required checks, fix failures, and only then report progress or completion.

## Output Requirements

When reporting, include evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary. State clearly what was checked, what was not checked, and what remains blocked or uncertain.

## SkillGuard Maintenance

Keep the `.skillguard` control root, work contract, check manifest, check scripts, evidence records, and progress ledger current. Re-run SkillGuard checks after changing this entrypoint, route behavior, evidence rules, or closure wording.

<!-- END SKILLGUARD CONTRACT LAYER -->
