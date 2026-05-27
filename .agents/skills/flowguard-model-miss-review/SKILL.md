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
- Do not close an in-scope miss with only an observed-bug regression test. The
  repaired model obligation needs current same-class test evidence verified by
  Model-Test Alignment, or the confidence claim stays scoped.
- Do not weaken hard invariants merely to make the miss disappear.
- If the repair changes a local child model that belongs to a parent ModelMesh,
  do not close the miss until the parent reattachment gate consumes current
  child evidence and confirms the child still fits the parent flow.
- For layered proof failures, map the bug to the broken table: parent coverage
  gap, illegal child overlap, stale child reattachment, missing leaf
  boundary-matrix cell, or real-code boundary overflow. Do not close the miss
  by only adding a happy-path test.
- If the miss appears as duplicate primary `edge_path` proof under one
  obligation, do not close it by relabeling one proof as auxiliary. Split the
  obligation or reattach the proof to a leaf matrix cell, then rerun alignment.

## Workflow

1. Capture the prior claim: model, invariant, scenario, replay, test, or manual
   evidence that appeared green.
2. Capture the real failure: exact input, state, log, replay, test, or user
   action.
3. Classify the miss as `boundary_missing`, `code_boundary_mismatch`,
   `state_too_coarse`, `input_branch_missing`, `invariant_too_weak`, or
   `evidence_overclaimed`.
4. Add the observed failure and a generalized same-class bad case to the model
   or replay evidence.
5. Add or identify test evidence for both the observed regression and the
   same-class generalized bad case. Use Model-Test Alignment to prove those
   rows cover the repaired model obligation before full closure.
6. If the same-class test space is large, slow, layered, background, or
   release-only, route the validation hierarchy to TestMesh and report scoped
   confidence until current TestMesh evidence exists.
7. If the failure shows real code accepted an unexpected input or emitted an
   undeclared output, state write, side effect, or error path, add
   code-boundary observations through Model-Test Alignment.
8. Rerun the model, same-class tests, and production-facing validation.
9. If a repaired child model is part of a parent mesh, rerun the affected
   parent ModelMesh reattachment gate.
10. If the miss exposes a missing or overflowing leaf boundary cell, update the
   leaf boundary matrix and rerun layered proof before parent confidence.
11. Close only when the corrected model catches the bad case and the relevant
   runtime/test/replay evidence is current, including same-class test evidence
   for in-scope repairs.
12. Update the Risk Evidence Ledger row that the old green claim overcovered:
   record the prior evidence as overclaimed or stale, then attach the new
   same-class bad-case evidence before restoring full confidence.
13. For non-trivial misses, default to a user-facing Mermaid miss-repair diagram
   showing the prior green claim, observed failure, miss classification, model
   repair, same-class generalized bad case, observed-regression test,
   same-class test evidence, alignment rerun, and remaining validation
   boundary. Its edges mean missed, repaired, generalized, tested, aligned,
   validated, or still out of scope; they are not a normal success workflow.
   The diagram explains the repair path and does not close the miss.

## Owned Helpers

- The lightweight model-miss template and protocol references.
- Existing FlowGuard Explorer, invariants, scenario review, replay, and
  conformance helpers as needed for the missed boundary.

## Non-Goals

- Do not use this as a first-pass modeling route.
- Do not use this for large model/test/code splits unless the miss diagnosis
  proves a mesh route is needed.

For detailed route rules, read `references/model_miss_protocol.md`.
