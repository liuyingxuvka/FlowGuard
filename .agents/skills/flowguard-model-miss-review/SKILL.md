---
name: flowguard-model-miss-review
description: Use for non-trivial bug repairs or when runtime, tests, replay, logs, manual validation, or production evidence fails after FlowGuard modeling passed. Triggers include model miss, false confidence, boundary missing, state too coarse, input branch missing, invariant too weak, evidence overclaimed, root-cause backpropagation, or needing a generalized bad case after a real failure.
---

# FlowGuard Model Miss Review

Standalone FlowGuard satellite skill for bug repairs where a real failure shows
the model, code contract, tests, or final claim is too narrow. Return to
`model-first-function-flow` only when there is no concrete failure evidence.

## First Read

- Route id: `model_miss_review`.
- Entry: `ROUTE_STARTER_API["model_miss_review"]`, `model-miss-template`, or `model-miss-full-template`.
- Core concepts: observed failure, same-class bad case, `boundary_missing`, root-cause backpropagation, owner code contract, old-path/field disposition, defect-family gate, maturation.
- Reference: `references/model_miss_protocol.md`.

## Hard Gates

- Verify the real package, keep AGENTS.md managed records current, and do not create a fake mini-framework.
- A user-observed UI failure after a green claim is a model miss, not a local button-only cleanup.
- UI misses preserve previous claim/reason, real failure, affected controls/fields, same-class controls/fields, tests/evidence, backpropagation, and code owner.
- The observed bug instance and bug-class responsibility are separate.
- Root cause, model obligation, owner code contract, observed test, and same-class test must bind to the same repaired behavior before broad closure.
- Old, fallback, compatibility, alternate paths, and field misses need disposition/projection instead of accidental reachability.
- A later green runtime check does not close a miss without same-class evidence.
- Search public/local risk templates before deepening the model; harvest useful generalized miss patterns afterward.

## Minimum Workflow

1. Run existing-model preflight when the bug is inside a modeled system.
2. Classify the miss, preserve observed evidence, and backpropagate root cause into the plan/model/test gap.
3. For UI misses, run `review_ui_model_misses()` and scan same-class controls or fields before fixing only the observed control.
4. Add or name one same-class generalized bad case when practical.
5. Update the model or FieldLifecycleMesh and bind the owner code contract.
6. Add observed-regression and same-class evidence, then rerun alignment, disposition, mesh/reattachment, maturation, process freshness, and risk ledger gates as relevant.

## Snapshot

Show a miss-repair diagram with failure, boundary_missing, same-class case,
root cause, field gap, code owner, tests, old-path disposition, and gaps.

## Non-Goals

- Do not close the class by patching only the observed instance.
- Do not treat production prose or progress logs as closure evidence.
