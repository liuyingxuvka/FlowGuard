---
name: flowguard-test-mesh
description: Use when tests, checks, validation scripts, or evidence are too large, slow, layered, stale, skipped, release-only, or need parent/child test hierarchy and evidence freshness governance.
---

# FlowGuard TestMesh

This is a standalone FlowGuard satellite skill for parent/child validation
evidence. Use it directly when the test/check layer needs structure, freshness
tracking, or routine-versus-release evidence boundaries.

Return to `model-first-function-flow` when the task is ordinary validation or
when route selection is unclear.

## Hard Gates

- Verify the real package before claiming FlowGuard use:
  `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`.
- For real target-project use, ensure the FlowGuard AGENTS.md managed
  block/version record exists, or record why it was not updated.
- Do not create a fake mini-framework or prose-only substitute.
- Long-running checks may run in the background, but progress is not
  completion.
- Parent test confidence consumes child evidence; it does not hide skipped,
  stale, failed, or release-only children.
- Boundary-conformance tests are distinct evidence: they must observe allowed
  inputs, rejected inputs, outputs, state writes, side effects, and error paths
  for the real code surface, not only a happy-path result.
- Leaf boundary-matrix tests are distinct evidence: they must prove every
  finite `Input x State` cell for a leaf model or mark the leaf as split-needed
  or explicitly scoped. Parent test confidence cannot consume missing, stale,
  skipped, progress-only, or release-only leaf matrix evidence as routine pass
  evidence.
- When a parent gate declares required leaf matrix cells, each cell must have a
  current passing child suite/script owner with final artifacts. A broad parent
  command or progress log is not a substitute for named cell evidence.
- A target split is needed before green parent confidence.
- If DevelopmentProcessFlow classifies a validation failure as test too thick,
  slow/layered, stale, skipped, progress-only, or release-only evidence that
  affects parent confidence, TestMesh owns the child validation split and
  evidence-status review.
- If `review_auto_mesh_splits(...)` reports a required test split for slow
  duration, large test counts, broad obligation coverage, background
  progress-only status, or release-only direct evidence, TestMesh owns the
  target validation split and child evidence. Do not treat the original broad
  evidence as full parent confidence.
- If a model-miss repair needs broad same-class validation that cannot be
  represented as a small direct Model-Test Alignment row set, TestMesh owns the
  validation hierarchy and final child evidence ids before full confidence.

## Workflow

1. Inventory test scripts, suites, shards, slow commands, release-only checks,
   and background logs.
2. Derive target parent/child validation structure and ownership.
3. For automatic split or DevelopmentProcessFlow `test_too_thick` handoffs,
   keep the broad command
   as a parent gate or compatibility check until child suites/scripts are
   derived and their evidence status is visible.
4. Mark which child suites are ordinary behavior tests, conformance replay,
   source audit, parent coverage, child disjointness, child reattachment,
   code-boundary conformance, or leaf boundary-matrix tests.
5. For same-class model-miss validation, identify which child suite proves the
   observed regression and which child suite, shard, property test, or seeded
   fuzz run proves the generalized bug family.
6. For leaf matrix-cell suites, record the exact cell ids they prove.
7. Record child evidence status: passed, failed, skipped, stale, progress-only,
   release-only, or not run.
8. Use `review_test_mesh(...)` or the template to review parent confidence.
9. Rerun the minimum affected child checks after code, model, prompt, or
   verifier changes.
10. Feed child evidence ids, status, freshness, and release scope to the Risk
   Evidence Ledger before a broader final confidence claim.
11. For non-trivial TestMesh reviews, default to a user-facing Mermaid
   validation mesh diagram showing parent gates, child suites/scripts, evidence status,
   routine/release boundaries, and stale/skipped/progress-only gaps. Its edges
   mean covers, gates, requires rerun, or stales; they are not product flow.
   Tiny validation checks may stay concise. The diagram explains the test mesh
   and does not replace child evidence or exit artifacts.

## Owned Helpers

- `review_test_mesh(...)`
- `python -m flowguard test-mesh-template --output .`
- `references/test_mesh_protocol.md`

## Non-Goals

- Do not split models; use `flowguard-model-mesh`.
- Do not split code structure; use `flowguard-structure-mesh`.
- Do not replace Model-Test Alignment for direct obligation-to-test coverage.

For detailed route rules, read `references/test_mesh_protocol.md`.
