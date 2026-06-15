## Why

FlowGuard's existing ModelMesh can represent parent/child ownership, child
reattachment, closure transitions, transition coverage, and test evidence, but
the default acceptance line is still too easy to satisfy with locally green
children or a partial partition map. That lets agentic handoffs, rejected
packets, missing fields, stale child evidence, and no-delta retry loops stay
outside the required model/test chain.

This change raises the baseline for the existing ModelMesh-centered workflow:
when a parent mesh is used for broad confidence, the model must prove that
children reattach to the parent, handoffs close, retry loops make progress or
block, and the resulting transition cells bind to Model-Test Alignment and
TestMesh evidence.

## What Changes

- Harden `HierarchyPartitionMap` / `review_hierarchical_mesh(...)` so a parent
  mesh cannot claim broad green confidence while child handoffs that emit or
  consume outputs lack closure evidence.
- Extend `MeshClosureTransition` with structured retry/liveness metadata for
  repeated inputs, progress tokens, repair feedback tokens, and blocker tokens.
- Add closure review findings for loop-like handoffs that can repeat the same
  input without progress feedback or a blocking disposition.
- Add a projection helper that turns ModelMesh closure transitions into
  `TransitionCoverageMatrix` cells, so parent/child handoffs automatically
  create Model-Test Alignment obligations and TestMesh leaf-cell ids.
- Require rejection/retry-like closure transitions to carry negative,
  failure-path, and replay test obligations by default.
- Update Model-Test Alignment and TestMesh docs/templates so these generated
  transition cells remain semantic obligations with concrete code/test targets,
  not just a broad child-suite pass.
- Update Model-Miss Review guidance so post-green stuck loops and repeated
  rejected packages backpropagate into the existing ModelMesh closure,
  transition coverage, same-class case, and TestMesh chain.
- Add focused known-bad tests for missing closure, no-delta retry loops,
  missing repair feedback, missing TestMesh cell evidence, stale child
  reattachment, and generated transition obligations without evidence.

## Capabilities

### New Capabilities

- None. This is a hardening of existing FlowGuard model/test routes, not a new
  route or parallel framework.

### Modified Capabilities

- `hierarchical-model-mesh`: Require parent/child mesh green confidence to keep
  handoff closure and child reattachment obligations closed when child outputs
  or reattachment contracts are present.
- `model-mesh-closure-model`: Add structured progress/feedback/blocker gates
  for retry, wait, and rejection-like closure loops.
- `transition-coverage-matrix`: Project ModelMesh closure transitions into
  required transition cells, including retry/rejection required test kinds.
- `model-test-alignment`: Consume ModelMesh-derived transition cells as normal
  model obligations with owner code contracts and current evidence.
- `test-evidence-mesh`: Require child test evidence for all ModelMesh-derived
  required leaf-cell ids before parent validation confidence.
- `post-runtime-model-miss-review`: Treat post-green stuck/retry/rejection
  loops as model misses that must backpropagate into same-class model and
  evidence obligations.

## Impact

- Public API additions in `flowguard.hierarchy`, `flowguard.transition_coverage`,
  and `flowguard.__init__`.
- Focused tests in hierarchical mesh, transition coverage, TestMesh,
  Model-Test Alignment, public template/API, and Model-Miss Review coverage.
- Public docs, route protocols/templates, field inventory, changelog/version,
  project adoption records, editable install, installed skills, shadow
  workspace, and local git state.
