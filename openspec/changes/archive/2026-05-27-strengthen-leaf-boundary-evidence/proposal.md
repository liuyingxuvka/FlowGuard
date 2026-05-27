## Why

FlowGuard v0.21.0 added layered boundary proof, but model-test alignment can
still report duplicate same-kind evidence without directly forcing the next
model split decision. That leaves a weak escape hatch: an agent can downgrade
one `edge_path` proof to supporting evidence and make the report green while
the model obligation remains too coarse.

This change strengthens the handoff between Model-Test Alignment, ModelMesh,
TestMesh, and Existing Model Preflight so duplicate primary boundary evidence
means "split or attach to a leaf matrix", not "rename one proof".

## What Changes

- Add explicit test evidence roles so primary boundary evidence, supporting
  contract evidence, integration smoke evidence, and leaf matrix-cell evidence
  are not confused.
- Make multiple current primary `edge_path` proofs for one model obligation a
  child-model split blocker unless they are reattached to separate leaf matrix
  cells.
- Strengthen leaf boundary matrices with declared input/state axes, Cartesian
  completeness checks, unexpected-cell checks, and missing-observed-behavior
  checks.
- Extend TestMesh so parent validation gates can require current leaf
  matrix-cell test evidence.
- Extend Existing Model Preflight so parent/child models cannot be treated as
  understood when their layered proof status is unknown.
- Update docs, skills, tests, templates, versioning, and release evidence.

## Capabilities

### Modified Capabilities
- `model-test-alignment`: distinguishes evidence roles and routes duplicate
  primary boundary evidence to model splitting.
- `layered-boundary-proof`: requires complete finite Cartesian leaf boundary
  matrices and checks both overflow and underflow.
- `test-evidence-mesh`: keeps leaf matrix-cell validation evidence visible
  under parent test gates.
- `existing-model-preflight`: records whether parent/child/leaf proof status is
  known before downstream confidence claims.

## Impact

- Affected package APIs: `TestEvidence`, `LeafBoundaryMatrix`,
  `TestMeshPlan`, `TestSuiteEvidence`, and `ModelContextHit` gain optional
  fields while preserving existing defaults.
- Affected docs/skills: Model-Test Alignment, ModelMesh, TestMesh, Existing
  Model Preflight, Model-Miss Review, and the kernel guidance.
- Affected tests: focused model-test alignment, layered proof, TestMesh,
  Existing Model Preflight, API surface, skill docs, and public templates.
