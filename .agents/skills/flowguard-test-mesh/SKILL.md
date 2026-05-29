---
name: flowguard-test-mesh
description: Use when tests, checks, validation scripts, or evidence are too large, slow, layered, stale, skipped, release-only, or need parent/child test hierarchy and evidence freshness governance.
---

# FlowGuard Test Mesh

Standalone FlowGuard satellite skill for parent/child test hierarchy and
validation evidence freshness. Use it for large, slow, stale, skipped,
background, layered, or release-only tests and child test scripts.

Return to `model-first-function-flow` for ordinary small test evidence.

## First Read

- Route id: `test_mesh_maintenance`.
- Core helpers: `review_test_mesh()`, `TestTargetSplitDerivation`,
  `TestSuiteEvidence`.
- Reference: `references/test_mesh_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- For real target-project work, keep the AGENTS.md managed block/version record
  current or record why it was not updated.
- Do not create a fake mini-framework.
- In-progress background runs are liveness, not pass evidence.
- Parent confidence needs current child evidence and target split derivation.

## Minimum Workflow

1. Identify parent suite/check and partition items.
2. Derive target child suites or child test scripts from the model risk.
3. Attach result status, evidence tier, result path, and freshness.
4. Scope or block parent confidence when child evidence is stale or missing.

## Snapshot

Show a validation mesh diagram with parent gates, child tests, evidence status,
freshness, background status, and scoped gaps.

## Non-Goals

- Do not split production code or models.
- Do not treat release-only evidence as routine proof.
