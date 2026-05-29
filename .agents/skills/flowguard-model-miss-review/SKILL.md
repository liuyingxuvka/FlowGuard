---
name: flowguard-model-miss-review
description: Use when runtime, tests, replay, logs, manual validation, or production evidence fails after FlowGuard modeling passed. Triggers include model miss, false confidence, boundary missing, state too coarse, input branch missing, invariant too weak, evidence overclaimed, or needing a generalized bad case after a real failure.
---

# FlowGuard Model Miss Review

Standalone FlowGuard satellite skill for failures that appear after FlowGuard
looked green. Use it for boundary missing, code-boundary mismatch, state too
coarse, input branch missing, invariant too weak, or evidence overclaimed.

Return to `model-first-function-flow` when there is no post-green failure yet.

## First Read

- Route id: `model_miss_review`.
- Core concepts: observed failure, same-class generalized bad case,
  `boundary_missing`, recurring defect-family gate,
  `review_model_maturation_loop()`.
- Reference: `references/model_miss_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- For real target-project work, keep the AGENTS.md managed block/version record
  current or record why it was not updated.
- Do not create a fake mini-framework.
- The observed bug instance and bug-class responsibility are separate.
- A later green runtime check does not close a miss without same-class evidence.

## Minimum Workflow

1. Classify the miss and preserve observed evidence.
2. Add or name one same-class generalized bad case when practical.
3. Update the model before broad closure if the boundary was missing.
4. Add observed-regression and same-class test evidence.
5. Rerun alignment, mesh/reattachment, maturation, and risk ledger gates as
   relevant.

## Snapshot

Show a miss-repair diagram with observed failure, missing boundary, generalized
bad case, model change, tests, reattachment needs, and residual gaps.

## Non-Goals

- Do not close the class by patching only the observed instance.
- Do not treat production prose or progress logs as closure evidence.
