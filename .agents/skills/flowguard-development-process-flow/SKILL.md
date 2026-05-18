---
name: flowguard-development-process-flow
description: Use when development lifecycle ordering, artifact overwrite, peer writes, validation freshness, minimum revalidation, V-style development/verification pairing, release readiness, archive readiness, or publish confidence depends on whether later work invalidated earlier evidence.
---

# FlowGuard Development Process Flow

This is a standalone FlowGuard satellite skill for lifecycle and validation
freshness questions. Use it directly when the risk is "does the process order
still support the done/release/archive/publish claim?"

Return to `model-first-function-flow` when the basic FlowGuard route is
unclear or when the task needs broader modeling before lifecycle evidence can
be judged.

## Hard Gates

- Verify the real package before claiming FlowGuard use:
  `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`.
- Do not create a fake mini-framework or prose-only substitute.
- Model process blocks as `Input x State -> Set(Output x State)` when the
  lifecycle risk needs executable checking.
- Skipped, stale, progress-only, or not-run validation is not a pass.
- Preserve user and peer-agent changes; later writes can stale earlier
  evidence.

## Workflow

1. List lifecycle artifacts: requirements, models, code, tests, prompts,
   docs, install surfaces, tags, release records, and generated assets.
2. Record which validations cover which artifact versions.
3. Identify later actions that can overwrite, stale, or narrow earlier
   evidence.
4. Use `review_development_process_flow(...)` or the template to derive the
   minimum revalidation plan.
5. Treat sibling route evidence ids as inputs only; do not inspect or
   supervise sibling route internals.
6. Before done/release/archive/publish, verify the final evidence is current
   for the final artifact set.

## Owned Helpers

- `review_development_process_flow(...)`
- `derive_revalidation_plan(...)`
- `python -m flowguard development-process-flow-template --output .`

## Non-Goals

- Do not replace ModelMesh, TestMesh, StructureMesh, Model-Test Alignment,
  LongCheck, or Conformance Adoption.
- Do not mark background progress as completion.
- Do not convert helper APIs or templates into Codex skills.

For detailed route rules, read
`references/development_process_flow_protocol.md`.
