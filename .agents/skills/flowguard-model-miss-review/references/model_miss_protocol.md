# Bug Repair And Post-Runtime Model-Miss Protocol

Use this protocol when runtime, tests, replay, logs, manual validation,
production evidence, or UI operation exposes a missed behavior after a
FlowGuard claim. A later green command is useful evidence, but it cannot by
itself close the missed class.

If a post-green parent/child route repeatedly returns the same packet,
rejection, missing-field shape, or no-body shape, model the retry/rejection
liveness gap, require repair feedback or an explicit blocker, and project the
affected closure transitions to Model-Test Alignment/TestMesh.

The current repair path is deliberately singular:

```text
observed failure
-> exact behavior commitment + primary owner + blueprint gap
-> finite canonical relations and ContractExhaustion cases
-> task-bound ModelMaturation contribution
-> owner code/test binding and affected topology/parent replay
-> freshness, risk, and claim-boundary decision
```

Existing Model Preflight owns the initial lookup. It must identify one affected
behavior plane, reuse the commitment and primary owner that already promise the
behavior, and preserve other planes only as typed context. When no current
commitment covers the promise, record `coverage_gap_backfill` and one explicit
`affected_blueprint_gap_id`; do not create an overlapping owner.

For an existing modeled target, current design comes only from the accepted
revision's complete `CurrentEffectiveIntentView` and the exact binding for the
affected model owner. The observed bug may prove that this contribution or its
boundary must change, but a latest revision delta, ancestry scan, root intent,
text match, or implementation path cannot be treated as the repaired current
design. The repair contributes a new delta and explicit transition; the next
accepted complete view remains the only current authority.

Symptom wording is not an ownership rule. Similar text in product runtime,
agent operation, and development process remains separately owned unless
current BCL/DNA/topology evidence declares an exact typed relation.

## Required Steps

1. Reopen the model-first work rather than treating the prior pass, bug report,
   or failing test as a local patch target.
2. Preserve the observed evidence and record the previous claim, if any. Name
   the affected behavior plane, commitment id, primary owner model, stable
   evidence-bound error signature, and typed related commitment ids.
3. Classify the miss as `boundary_missing`, `code_boundary_mismatch`,
   `state_too_coarse`, `input_branch_missing`, `invariant_too_weak`, or
   `evidence_overclaimed`. Record a plain-language detail without inventing a
   new formal type for every incident.
4. Backpropagate the supported root cause into the prior plan/model/test gap:
   previous claim, observed failure, supported cause, `would_have_failed_if`,
   new model or evidence item, and required closure evidence. If no previous
   claim existed, say so explicitly.
5. Bind the repair to one exact `affected_blueprint_gap_id`. The gap must point
   to the missing or incorrect current behavior boundary, not merely to the
   file where the symptom appeared.
6. When bounded diagnosis is useful, derive one deterministic
   deletion-minimal conflict and one deletion-minimal positive witness from the
   existing false-negative owner record. Give every retained evidence item a
   necessity witness. This read-only projection preserves the owner's decision
   and cannot close or reopen the review.
7. Represent an in-scope observed issue in executable evidence: a scenario,
   invariant, replay adapter, representative trace, leaf boundary cell, or
   model-boundary update. Otherwise record the exact out-of-scope reason.
8. Declare only the finite affected relations already licensed by current
   DNA, BCL, or affected-topology identities. Each relation needs a stable id,
   type, two typed endpoints, and source identities. Pass one
   `CanonicalRelationHandoff` containing the affected model, code-obligation,
   test-obligation, and blueprint-gap ids. The carrier does not discover new
   scope or prove that two surfaces are equivalent.
9. Route the finite field, state/input, payload, transition, parent/child, or
   same-class boundary through ContractExhaustionMesh. Materialize stable case
   ids, generated combination ids or coverage receipt ids, and actionable
   oracles. An unmaterialized required relation remains a visible gap.
10. If behavior-bearing fields, schema keys, config or prompt fields, payload
    columns, or persisted attributes are involved, update FieldLifecycleMesh
    with root-cause, same-class, and old-field identities. Unknown projection
    or disposition blocks broad closure.
11. Add current test evidence for the observed regression and for every
    required generated case. A concrete counterexample or known-bad proof also
    needs a stable target id and matching `counterexample_regression` or
    `known_bad_replay` evidence.
12. Bind the repaired obligation to the owner code contract that implements
    the public behavior. Helper-only, adapter-only, or internal-path evidence
    cannot close a public miss. Run Model-Test Alignment over the model
    obligation, code contract, closure targets, field projections, and tests.
    Use TestMesh only when this finite validation is large, slow, layered,
    stale-prone, background, or release-only.
13. Emit a task-bound `ModelMaturationCoverageContribution` containing the
    exact owner, source, coverage ids, probe ids, blueprint gap, and current
    native receipt. Run the maturation loop with the miss, alignment,
    code-boundary, mesh, and freshness signals. A gap disappears only through
    a current resolution receipt binding the same task, candidate, coverage
    fingerprint, and predecessor identity.
14. Rerun every affected topology edge. If a child boundary changed, the
    parent must consume the new child evidence and recheck inputs, outputs,
    state ownership, side effects, outgoing guarantees, joins, and affected
    siblings. Child-local green cannot close a parent claim.
15. Give reachable old, fallback, alternate, replaced, or deprecated paths and
    fields a direct disposition: deleted, blocked, migrated, delegated to the
    repaired owner, same-contract repaired, or explicitly scoped with a
    reason. `unknown` blocks closure.
16. Run the relevant model checks again and confirm that both the observed
    weakness and required ContractExhaustion cases are now visible. Validate
    with the strongest practical production-facing evidence.
17. Run DevelopmentProcessFlow over the changed plan, model, code, tests, and
    documents so later edits, peer writes, adapters, or generated artifacts do
    not silently stale the result.
18. Project independently verified ModelMaturation evidence into the Risk
    Evidence Ledger. The risk row consumes the exact maturation evidence id;
    it does not accept a declared pass or raw mapping as proof.

## UI Misses

For UI failures, run `review_ui_model_misses(...)` and preserve the prior
claim, why it looked green, the user-observed failure, affected and same-class
capabilities/controls/fields, task-flow and human-operability gaps, root-cause
backpropagation, code owner, and real click or implementation evidence.
Missing promised capabilities belong in `missing_promised_capability_ids` and
are classified as `boundary_missing` or `evidence_overclaimed`. A label or
planned control is not proof that the real surface works.

## What Not To Add By Default

Do not add a hazard registry, upgrade reviewer, default ModelMesh, or full
coverage matrix for an ordinary local miss. Activate a specialist only when
the exact gap requires it. This does not waive parent reattachment when an
existing parent depends on the changed child.

Do not create a second discovery, relation-scoring, or bug-family authority.
The current commitment and blueprint select scope, the internal canonical
relation carrier transports exact edges, ContractExhaustionMesh materializes
finite cases, and ModelMaturation owns iterative depth.

## Completion Standard

An in-scope miss is closed only when:

- the observed failure, prior claim, supported root cause, commitment, primary
  owner, and blueprint gap are recorded;
- the repaired model exposes the observed issue and finite generated cases;
- all required canonical relations are materialized or explicitly scoped;
- the owner code contract and external tests bind the same obligations and
  closure targets;
- relevant fields and old paths have closing dispositions;
- affected topology and parent evidence have been replayed;
- ModelMaturation has no open in-scope action for the claim, or the claim is
  explicitly narrowed;
- process freshness and the Risk Evidence Ledger consume current verified
  evidence.

A point patch, one exact regression test, a later green runtime command, or a
raw relation id cannot satisfy this standard on its own.

Record the miss type, commitment/owner/blueprint-gap ids, root-cause
backpropagation, canonical relation ids, ContractExhaustion case and receipt
ids, owner code/test bindings, field and legacy dispositions, ModelMaturation
evidence id, topology/parent replay, freshness, skipped checks, residual risk,
and final claim boundary in adoption evidence.
