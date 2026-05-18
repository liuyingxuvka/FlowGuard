## Why

FlowGuard can currently make a local child model green after a bug fix while
leaving the parent model uncertain about whether the child still fits the
original workflow. A child-local pass must not count as repaired confidence
unless the child can reconnect to the parent model through the same declared
inputs, outputs, state ownership, side effects, and evidence contract.

## What Changes

- Add a child model reattachment gate to ModelMesh so parent boundaries can
  reject child-local repairs whose contracts no longer match parent
  expectations.
- Extend post-runtime model-miss review so a miss repaired in a local child
  model cannot close until the affected parent ModelMesh consumes current child
  evidence.
- Teach the model-first Skill router to combine `model_miss_review` with
  `model_mesh_maintenance` when a repaired child model belongs to a parent mesh.
- Update docs, templates, tests, and release notes to make "child green is not
  parent green" explicit.

## Capabilities

### New Capabilities

- `model-mesh-child-reattachment`: Requires ModelMesh parent boundaries to
  validate child input/output, state, side-effect, contract, and evidence
  reattachment before green parent mesh confidence.
- `model-miss-child-reattachment`: Requires post-runtime model-miss repair of a
  child model to return through the affected parent mesh before the miss can be
  closed.

### Modified Capabilities

- None.

## Impact

- `flowguard.hierarchy` public ModelMesh helper types and review findings.
- ModelMesh, model-miss, and model-first Skill docs under `.agents/skills` and
  installed skill mirrors.
- Public docs, templates, changelog, and focused tests for the new gate.
