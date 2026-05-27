## Why

FlowGuard can currently show that models, code contracts, and tests have some
evidence alignment, but a model can still be too coarse: parent models may not
prove child coverage/disjointness, and leaf code boundaries may only have
representative tests instead of complete finite boundary coverage.

This change makes layered proof an explicit FlowGuard confidence requirement:
parent models consume proven child contracts, child models partition parent
responsibilities without illegal overlap, and leaf models must be small enough
to prove every finite `Input x State -> Set(Output x State)` boundary.

## What Changes

- Add layered model proof APIs that review parent coverage, child
  disjointness, child reattachment, and leaf boundary matrix status in one
  report.
- Extend ModelMesh guidance so parent green confidence requires coverage and
  disjointness proof over child model responsibilities.
- Extend Model-Test Alignment guidance so leaf model confidence requires a
  boundary matrix for finite inputs, states, outputs, state writes, side
  effects, and error paths.
- Extend TestMesh and DevelopmentProcessFlow guidance so stale, skipped,
  progress-only, or release-only child evidence cannot support parent
  confidence or done/release claims.
- Update templates, API exports, docs, tests, and adoption evidence for the
  new layered proof workflow.

## Capabilities

### New Capabilities
- `layered-boundary-proof`: Reviews whether a FlowGuard model tree is closed:
  child models cover the parent, child scopes do not illegally overlap, child
  contracts reattach to the parent, and leaf boundaries have current complete
  matrix evidence.

### Modified Capabilities
None. The existing ModelMesh, Model-Test Alignment, and TestMesh routes will
consume the new layered proof capability, but this repository does not yet have
separate archived OpenSpec capabilities for those routes.

## Impact

- Affected package APIs: new layered proof dataclasses and review helper,
  exported through `flowguard.__init__`.
- Affected docs and skills: ModelMesh, Model-Test Alignment, TestMesh,
  Existing Model Preflight, DevelopmentProcessFlow, Code Structure
  Recommendation, StructureMesh, Architecture Reduction, and Model-Miss Review.
- Affected templates/tests: public template text, API-surface tests, new unit
  tests for the layered proof helper, and release documentation.
