---
name: flowguard-model-miss-review
description: Use for non-trivial bug repairs or when runtime, tests, replay, logs, manual validation, or production evidence fails after FlowGuard modeling passed. Triggers include model miss, false confidence, boundary missing, state too coarse, input branch missing, invariant too weak, evidence overclaimed, root-cause backpropagation, or needing a generalized bad case after a real failure.
---

# FlowGuard Model Miss Review

Standalone FlowGuard satellite skill for bug repairs where a real failure shows
the model, code contract, tests, or final claim may be too narrow. Use it for
boundary missing, code-boundary mismatch, state too coarse, input branch
missing, invariant too weak, root-cause backpropagation, or evidence
overclaimed.

Return to `model-first-function-flow` only when there is no concrete failure
evidence yet or the work is ordinary behavior modeling rather than bug repair.

## First Read

- Route id: `model_miss_review`.
- Core concepts: observed failure, same-class generalized bad case,
  root-cause backpropagation, owner code contract, `boundary_missing`,
  recurring defect-family gate, legacy path disposition,
  `review_model_maturation_loop()`.
- Reference: `references/model_miss_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- For real target-project work, keep the AGENTS.md managed block/version record
  current or record why it was not updated.
- Do not create a fake mini-framework.
- The observed bug instance and bug-class responsibility are separate.
- Root cause, model obligation, owner code contract, observed test, and
  same-class test must bind to the same repaired behavior before broad closure.
- Old, fallback, compatibility, or alternate paths need a disposition instead
  of being left reachable by accident.
- A later green runtime check does not close a miss without same-class evidence.

## Minimum Workflow

1. Run existing-model preflight when the bug is inside a modeled system.
2. Classify the miss, preserve observed evidence, and backpropagate root cause
   into the plan/model/test gap that would have caught it.
3. Add or name one same-class generalized bad case when practical.
4. Update the model and bind the owner code contract before broad closure.
5. Add observed-regression and same-class test evidence, then rerun alignment,
   legacy/fallback disposition, mesh/reattachment, maturation, process
   freshness, and risk ledger gates as relevant.

## Snapshot

Show a miss-repair diagram with observed failure, missing boundary, generalized
bad case, root cause, code owner, tests, legacy path disposition, reattachment
needs, and residual gaps.

## Non-Goals

- Do not close the class by patching only the observed instance.
- Do not treat production prose or progress logs as closure evidence.
