---
name: flowguard-model-miss-review
description: Use when runtime, tests, replay, logs, manual validation, or production evidence fails after FlowGuard modeling passed. Triggers include model miss, false confidence, boundary missing, state too coarse, input branch missing, invariant too weak, evidence overclaimed, or needing a generalized bad case after a real failure.
---

# FlowGuard Model-Miss Review

This is a standalone FlowGuard satellite skill for post-pass failures. Use it
when reality contradicted an earlier FlowGuard pass.

Return to `model-first-function-flow` when there is no prior model/evidence
claim, when the task is ordinary first-pass modeling, or when the failure spans
multiple FlowGuard routes.

## Hard Gates

- Verify the real package before claiming FlowGuard use:
  `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`.
- Do not create a fake mini-framework or prose-only substitute.
- Do not treat a later green runtime check by itself as closure.
- Preserve the observed failure and at least one same-class generalized bad
  case when practical.
- Do not weaken hard invariants merely to make the miss disappear.

## Workflow

1. Capture the prior claim: model, invariant, scenario, replay, test, or manual
   evidence that appeared green.
2. Capture the real failure: exact input, state, log, replay, test, or user
   action.
3. Classify the miss as `boundary_missing`, `state_too_coarse`,
   `input_branch_missing`, `invariant_too_weak`, or `evidence_overclaimed`.
4. Add the observed failure and a generalized same-class bad case to the model
   or replay evidence.
5. Rerun the model and production-facing validation.
6. Close only when the corrected model catches the bad case and the relevant
   runtime/test/replay evidence is current.

## Owned Helpers

- The lightweight model-miss template and protocol references.
- Existing FlowGuard Explorer, invariants, scenario review, replay, and
  conformance helpers as needed for the missed boundary.

## Non-Goals

- Do not use this as a first-pass modeling route.
- Do not use this for large model/test/code splits unless the miss diagnosis
  proves a mesh route is needed.

For detailed route rules, read `references/model_miss_protocol.md`.
