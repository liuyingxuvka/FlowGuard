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

## Workflow

1. Inventory test scripts, suites, shards, slow commands, release-only checks,
   and background logs.
2. Derive target parent/child validation structure and ownership.
3. Record child evidence status: passed, failed, skipped, stale, progress-only,
   release-only, or not run.
4. Use `review_test_mesh(...)` or the template to review parent confidence.
5. Rerun the minimum affected child checks after code, model, prompt, or
   verifier changes.

## Owned Helpers

- `review_test_mesh(...)`
- `python -m flowguard test-mesh-template --output .`
- `references/test_mesh_protocol.md`

## Non-Goals

- Do not split models; use `flowguard-model-mesh`.
- Do not split code structure; use `flowguard-structure-mesh`.
- Do not replace Model-Test Alignment for direct obligation-to-test coverage.

For detailed route rules, read `references/test_mesh_protocol.md`.
