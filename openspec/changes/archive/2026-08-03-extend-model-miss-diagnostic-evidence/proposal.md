## Why

FlowGuard already owns post-model runtime/test misses, but its current review can identify a miss without consistently returning the smallest explanatory conflict, the exact model/code/observation disagreement, or a non-vacuous repair obligation. That leaves the user with a classification but not a bounded diagnosis.

## What Changes

- Add a model-miss diagnostic projection over the existing review owner; do not create a parallel review workflow.
- Compute bounded deletion-minimal conflict sets and label them explicitly as subset-minimal rather than minimum-cardinality.
- Bind every diagnosis to exact observed evidence, modeled expectation, code/test surface, and failure boundary.
- Require a proposed repair to preserve a named positive behavior and reject vacuous weakening of invariants or acceptance criteria.
- Extend the model-miss prompt, template, executable model, tests, and release evidence.

## Capabilities

### New Capabilities

- `model-miss-diagnostic-evidence`: Defines minimal conflict, disagreement, and repair-preservation evidence for model misses.

## Impact

Affected surfaces: `flowguard/plan_intake.py`, `flowguard/model_miss_diagnostics.py`, model-miss templates and skill references, `.flowguard/model_miss_review`, tests, consumer skill projection, README/release records, and version metadata.
