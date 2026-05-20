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
- Do not create a fake mini-framework or prose-only substitute.
- Long-running checks may run in the background, but progress is not
  completion.
- Parent test confidence consumes child evidence; it does not hide skipped,
  stale, failed, or release-only children.
- A target split is needed before green parent confidence.
- If DevelopmentProcessFlow classifies a validation failure as test too thick,
  slow/layered, stale, skipped, progress-only, or release-only evidence that
  affects parent confidence, TestMesh owns the child validation split and
  evidence-status review.

## Workflow

1. Inventory test scripts, suites, shards, slow commands, release-only checks,
   and background logs.
2. Derive target parent/child validation structure and ownership.
3. For DevelopmentProcessFlow `test_too_thick` handoffs, keep the broad command
   as a parent gate or compatibility check until child suites/scripts are
   derived and their evidence status is visible.
4. Record child evidence status: passed, failed, skipped, stale, progress-only,
   release-only, or not run.
5. Use `review_test_mesh(...)` or the template to review parent confidence.
6. Rerun the minimum affected child checks after code, model, prompt, or
   verifier changes.
7. For non-trivial TestMesh reviews, default to a user-facing Mermaid
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
