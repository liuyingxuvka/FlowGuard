---
name: flowguard-test-mesh
description: Use when tests, checks, transition cells, payload cases, or evidence are large, slow, layered, stale, skipped, backgrounded, release-only, or require parent/child suite ownership and freshness proof.
---

# FlowGuard Test Mesh

## Purpose
Govern parent/child test hierarchy, explicit validation partitions, result artifacts, and evidence freshness without inlining every child test.

## Entrypoint Scope
Route id: `test_mesh_maintenance`; role: `public_owner`; native owner: `test_mesh_maintenance`. This standalone FlowGuard satellite skill owns validation hierarchy, not semantic obligations or test execution.

## Local Material Routing
Read `references/test_mesh_protocol.md` for target split derivation, ownership/evidence rows, reuse proof, transition/payload matrices, and routine/release scope.

## Entrypoint Acceptance Map
Accept a parent gate and model-derived child split; review child ownership/status/freshness; block hidden skip/timeout/progress/release gaps or unowned cells; hand semantic bindings and lifecycle/risk decisions to typed owners.

## Use When
- Use for large/slow/background validation, child test scripts, stale/reused evidence, release-only gates, or transition/artifact-payload matrices.

## Do Not Use When
- Do not split production code/models, decide semantic obligations, run tests directly, or treat release-only/background progress as routine proof; return small ordinary tests to `model-first-function-flow`.

## Required Workflow
1. Define the parent gate and derive target child suites/scripts from a FlowGuard validation-structure model.
2. Map partitions/cells/shards to owners and attach status, freshness, proof artifacts, reuse tickets, skips, timeouts, and result paths.
3. Review routine/release scope and return current child evidence plus Model-Test Alignment, process, and risk handoffs.

## Hard Gates
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Background progress is liveness only; reuse requires current `TestResultReuseTicket` and `ProofArtifactRef`.
- Every required cell/shard needs a registered current passing owner; missing target derivation, hidden skips, or template harvest closure blocks broad parent confidence.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, and `typed_next_actions`, plus a validation mesh diagram and child freshness.

## SkillGuard Maintenance
- Edit `.skillguard/contract-source.json`, then regenerate derived contracts; SkillGuard validates test-mesh governance and cannot turn liveness into native pass evidence.
