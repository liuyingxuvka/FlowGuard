## Why

FlowGuard model hierarchies can become stale when a child model changes its
function, state, side-effect, invariant, or risk ownership but the parent model
and sibling models are not rechecked against that new boundary. Recent
model-miss hardening also needs an explicit contract that known bug instances
are holdout evidence, while model precision is judged against the responsible
bug class and its ownership boundary, not a single reproduced case.

## What Changes

- Add boundary-diff propagation for child model boundary changes into parent
  partition maps and affected sibling models.
- Require boundary diffs to identify added, removed, narrowed, widened, or moved
  ownership for function blocks, state fields, side effects, invariants,
  contracts, risk classes, and validation evidence.
- Require parent models to reconcile propagated diffs before their coverage,
  partition, freshness, or release-readiness claims can remain valid.
- Require sibling models to recheck overlap, handoff, shared-read, and duplicate
  ownership risks when a propagated diff intersects their declared boundary.
- Require bug instances to be treated as validation or holdout evidence only;
  model accuracy targets the generalized bug-class responsibility boundary.
- Route slow or large propagated checks through ModelMesh, Budgeted model-group,
  and LongCheck evidence conventions instead of weakening required checks or
  claiming incomplete evidence as passing.
- No breaking changes to existing public runtime APIs are intended.

## Capabilities

### New Capabilities

- `model-boundary-diff-propagation`: Defines how child model boundary changes
  propagate to parent and sibling models, how same-class bug responsibility is
  represented without point-fix overfitting, and how large or slow propagated
  checks are governed through mesh, budgeted, and long-check evidence.

### Modified Capabilities

- None.

## Impact

- Affected code: future optional helpers or reporting structures for model
  boundary diff capture, propagation, reconciliation, and evidence reporting.
- Affected model artifacts: parent model partition maps, child model ownership
  records, sibling overlap reviews, generalized bad-case models, and holdout
  evidence notes.
- Affected validation: scenario review, conformance replay, loop/stuck review,
  progress/fairness checks, contract/refinement checks, ModelMesh review,
  Budgeted model-group shards, and LongCheck logs when checks are large or slow.
- Dependencies: none expected; keep runtime behavior standard-library-only.
