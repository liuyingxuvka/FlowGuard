# FlowGuard Model-Miss Review Notes

Use this scaffold when real runtime, test, replay, log, manual, production, or
UI evidence exposes a missed behavior after a FlowGuard claim. Start from
`python -m flowguard template model-miss-review` (or `model-miss-review-full`).

## One Repair Chain

```text
observed failure
-> affected commitment + primary owner model
-> finite affected relations
-> ContractExhaustion cases and oracles
-> owner code/test binding + topology/parent replay
-> rerun what `python -m flowguard change` lists, then a bounded claim
```

The model miss is not a request to inspect every superficially similar feature.
Existing Model Preflight first resolves the failed promise inside one behavior
plane. Reuse its commitment and owner model when present; create one explicit
coverage gap only when no same-plane promise covers the failure. Other planes
remain typed context and do not become duplicate owners.

## Review Questions

- What concrete evidence failed, and what earlier claim did it contradict?
- Which `affected_commitment_id` and `primary_owner_model_id` own the repair?
- What supported root cause and `would_have_failed_if` condition
  (`FalseNegativeCase`) explain why the earlier model or evidence went green?
- Is the miss `boundary_missing`, `code_boundary_mismatch`,
  `state_too_coarse`, `input_branch_missing`, or `evidence_overclaimed`, or was
  the invariant simply too weak?
- Which scenario, invariant, replay, trace, leaf cell, or boundary update makes
  the observed issue executable?
- Which exact behavior-commitment and topology relations define the finite
  affected scope? Which model or source file does each relation come from?
- Which ContractExhaustion case ids, combination ids, and actionable oracles
  materialize that scope?
- If a concrete counterexample or known-bad proof exists, which stable target
  id (`ClosureEvidenceTarget`) binds it to the external regression test?
- Which owner `CodeContract` implements the repaired behavior, and which
  observed plus generated-case tests prove that same external boundary?
- Did the repair change a field, old path, child boundary, topology edge,
  parent input/output, state owner, side-effect owner, join, or sibling
  obligation? Where is its disposition or replay evidence?
- Which later edits would stale the result (`python -m flowguard map check`
  shows drift), and what exact claim remains if any evidence is missing,
  scoped, skipped, or not run?

For UI misses, also record why the old row looked green, the user-observed
failure, missing promised capabilities, affected and same-class controls and
fields, task-flow and human-operability gaps, code owner, and real click or
implementation evidence (`UIModelMissRecord`, `review_ui_model_misses(...)`).
A label, API route, or planned control is not proof of a working visible
capability.

When the cause is unclear, `diagnose_false_negative_backpropagation(...)` can
reduce a `FalseNegativeBackpropagationReport` to a deletion-minimal conflict
plus a positive witness. It is read-only diagnosis and does not change the
owner decision.

## Closure Rule

A later green command, point patch, one observed regression, helper-only test,
or relation id with no case behind it cannot close an in-scope miss. Broad
closure requires the commitment and owner model, executable observed and
generated cases, owner code/test binding, relevant field and old-path
dispositions, affected topology/parent replay, and a fresh run of the models
and tests that `python -m flowguard change` lists. Otherwise report the exact
scoped boundary and the next action.
