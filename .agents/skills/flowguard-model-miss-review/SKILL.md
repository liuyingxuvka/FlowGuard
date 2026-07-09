---
name: flowguard-model-miss-review
description: Use when runtime, tests, replay, logs, or manual validation fails after FlowGuard passed.
---

# FlowGuard Model Miss Review

Standalone FlowGuard satellite skill for repairs where real failure shows the model, code contract, tests, or final claim is too narrow. Return to `model-first-function-flow` only when no concrete failure evidence exists.

## First Read

- Route id: `model_miss_review`.
- Entry: `ROUTE_STARTER_API["model_miss_review"]`, `model-miss-template`, or full variant.
- Concepts: observed failure, contract-exhaustion same-class case, `boundary_missing`, root-cause backpropagation, owner code contract, disposition, coverage receipt, defect-family gate.
- Reference: `references/model_miss_protocol.md`.

## Hard Gates

- Verify FlowGuard check engine and AGENTS.md managed records; no fake mini-framework.
- A user-observed UI failure after green is a model miss.
- Preserve prior claim, failure, same-class surface, tests, backpropagation, and code owner.
- Model miss is BCL backfeed, not a new-feature factory: map to existing commitment/owner first; backfill only if behavior was unregistered.
- Observed instance and bug-class responsibility are separate.
- Same-class generation is seed evidence; route through ContractExhaustionMesh.
- Root cause, model obligation, owner code contract, observed test, and same-class test bind to the same repaired behavior.
- Counterexample/known-bad misses need target-aware owner-code replay evidence.
- Old or alternate paths and field misses need disposition/projection.
- A later green runtime check does not close a miss without current class evidence.
- Deepened miss models need template harvest closure.

## Minimum Workflow

1. Run existing-model preflight when inside a modeled system.
2. Identify affected commitment id; if none exists for external behavior, route to BCL coverage-gap backfill.
3. Classify the miss and backpropagate root cause into model/test gap.
4. For UI misses, run `review_ui_model_misses()` before fixing one control.
5. Add one family seed or interaction group, then use ContractExhaustionMesh.
6. Update model or FieldLifecycleMesh and bind the owner code contract.
7. Add observed-regression and contract-exhaustion evidence, then rerun alignment, disposition, mesh, maturation, freshness, risk gates.

## Snapshot

Show a miss-repair diagram with failure, boundary_missing, contract-exhaustion case ids, root cause, field gap, code owner, tests, old-path disposition, gaps.

## Non-Goals

- Do not close the class by patching only the observed instance.
- Do not treat production prose or progress logs as closure evidence.
