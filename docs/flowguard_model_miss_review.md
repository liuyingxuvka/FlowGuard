# FlowGuard Model-Miss Review Notes

Use this scaffold when real runtime, test, replay, log, manual, production, or
UI evidence exposes a missed behavior after a FlowGuard claim.

## One Current Repair Chain

```text
observed failure
-> affected commitment + primary owner + blueprint gap
-> finite canonical relations
-> ContractExhaustion cases and oracles
-> ModelMaturation contribution
-> owner code/test binding + topology/parent replay
-> freshness, risk evidence, and bounded closure
```

The model miss is not a request to inspect every superficially similar feature.
Existing Model Preflight first resolves the failed promise inside one behavior
plane. Reuse its commitment and owner when present; create one explicit
coverage gap only when no same-plane promise covers the failure. Other planes
remain typed context and do not become duplicate owners.

## Review Questions

- What concrete evidence failed, and what earlier claim did it contradict?
- Which `affected_commitment_id`, `owner_model_id`, and
  `affected_blueprint_gap_id` own the repair?
- What supported root cause and `would_have_failed_if` condition explain why
  the earlier model or evidence went green?
- Is the miss `boundary_missing`, `code_boundary_mismatch`,
  `state_too_coarse`, `input_branch_missing`, `invariant_too_weak`, or
  `evidence_overclaimed`?
- Which scenario, invariant, replay, trace, leaf cell, or boundary update makes
  the observed issue executable?
- Which exact current DNA/BCL/topology relations define the finite affected
  scope? What source identities prove each relation?
- Which ContractExhaustion case ids, combination ids, coverage receipt ids,
  and actionable oracles materialize that scope?
- If a concrete counterexample or known-bad proof exists, which stable target
  id binds it to the external regression test?
- Which owner `CodeContract` implements the repaired behavior, and which
  observed plus generated-case tests prove that same external boundary?
- Which task-bound ModelMaturation contribution carries the blueprint gap,
  coverage/probe ids, candidate fingerprint, and current native receipt?
- Did the repair change a field, old path, child boundary, topology edge,
  parent input/output, state owner, side-effect owner, join, or sibling
  obligation? Where is its disposition or replay evidence?
- Which later edits would stale the result, and what exact claim remains if any
  evidence is missing, scoped, skipped, or not run?

For UI misses, also record why the old row looked green, the user-observed
failure, missing promised capabilities, affected and same-class controls and
fields, task-flow and human-operability gaps, code owner, and real click or
implementation evidence. A label, API route, or planned control is not proof
of a working visible capability.

## Closure Rule

A later green command, point patch, one observed regression, helper-only test,
or unmaterialized relation id cannot close an in-scope miss. Broad closure
requires current commitment/blueprint ownership, executable observed and
generated cases, owner code/test binding, relevant field and old-path
dispositions, affected topology/parent replay, closed task-bound
ModelMaturation evidence, process freshness, and Risk Evidence Ledger
consumption. Otherwise report the exact scoped boundary and next owner action.
