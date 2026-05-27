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
- If the prior green result failed because the plan omitted a surface, an
  adapter lost raw evidence status, evidence went stale, or a narrow report was
  overpromoted, run `review_false_negative_backpropagation(...)` and feed the
  result to the typed claim chain before broad closure.
- If the same-class miss recurs, or if a high-risk first miss would make a local
  point fix overclaim full confidence, promote it to a recurring defect-family
  gate before closure. This is FlowGuard evidence inside the existing
  Model-Miss/Risk Evidence Ledger chain, not a new downstream-app-owned skill
  or product-specific closure route.
- If a repair creates or prefers a new route while the old route can still
  execute, closure requires a legacy path disposition: deleted, blocked,
  delegated to a repaired contract, same-contract repaired, or explicitly out
  of scope with a reason. `unknown` remains blocked.
- For full closure, defect-family, alignment, ledger, layered-boundary, and
  lifecycle evidence must be proof-artifact-bound. A row that merely declares
  `passed/current` is not closure evidence without a current proof artifact
  carrying a result path, fingerprint, obligation coverage, and external
  contract scope where relevant.
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
- Before broad closure, feed the miss classification, alignment, mesh,
  code-boundary, and freshness rows to `review_model_maturation_loop(...)`; if
  it reports an open model-upgrade action, upgrade the model or scope the claim.

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
7. If the same-class miss is recurring or high risk, create or update a
   defect-family gate with a model obligation, authority boundary, observed
   failure, same-class generalized case, historical holdout, and current proof
   evidence.
8. If an old route remains present, record its legacy path disposition and
   attach proof for delegated or same-contract repaired outcomes.
9. If the failure shows real code accepted an unexpected input or emitted an
   undeclared output, state write, side effect, or error path, add
   code-boundary observations through Model-Test Alignment.
10. Rerun the model, same-class tests, and production-facing validation.
11. If a repaired child model is part of a parent mesh, rerun the affected
   parent ModelMesh reattachment gate.
12. If the miss exposes a missing or overflowing leaf boundary cell, update the
    leaf boundary matrix and rerun layered proof before parent confidence.
13. Run `review_model_maturation_loop(...)` before closure and resolve or scope
    any model-upgrade action it reports.
14. Close only when the corrected model catches the bad case and the relevant
    runtime/test/replay evidence is current, including same-class test evidence
    for in-scope repairs and current defect-family gate evidence when required.
15. Update the Risk Evidence Ledger row that the old green claim overcovered:
    record the prior evidence as overclaimed or stale, then attach the new
    same-class bad-case evidence and defect-family gate status before restoring
    full confidence.
16. When the miss exposes plan-intake, adapter-conformance, stale-evidence, or
    claim-scope causes, record the false-negative backpropagation case and make
    the final claim consume that case through `review_flowguard_claim_chain(...)`.
17. For non-trivial misses, default to a user-facing Mermaid miss-repair diagram
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
