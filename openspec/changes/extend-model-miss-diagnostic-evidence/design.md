## Context

`model_miss_review` remains the single public owner. Diagnostics are a subordinate pure projection from its observed evidence and model/code bindings.

## Goals / Non-Goals

**Goals**

- Explain a miss with a bounded subset-minimal conflict.
- Show exact model, observation, code/test, and failure-boundary disagreement.
- Reject repairs that merely delete the obligation or weaken the invariant.

**Non-Goals**

- No second miss-review terminal owner.
- No claim of minimum-cardinality unless exhaustive proof exists.
- No automatic code edit.

## Decisions

1. Diagnostic inputs are immutable atoms with stable ids and an inconsistency oracle owned by model-miss review.
2. A deterministic deletion pass returns a subset-minimal core; budget exhaustion is explicit.
3. `RepairCandidate` declares preserved positive obligations, changed assumptions/transitions/contracts, and new negative evidence.
4. A repair is non-vacuous only if at least one named positive behavior remains and the original miss trace is rejected for the intended reason.
5. The diagnostic report is attached to the existing review receipt and cannot turn a blocked review green.

## Risks / Trade-offs

- Deletion-minimal cores can vary with stable atom order; the report records order and algorithm version.
- Stronger repair checks may keep more cases blocked, which is preferable to false closure.

## Migration Plan

Add pure diagnostic module and tests, extend current model-miss schema/template/model, update skill guidance and contracts, then release v0.66.0.
