## Why

ModelMesh and TestMesh already review parent/child partition maps and evidence,
but they can still accept splits that were supplied ad hoc. Large models and
large validation flows need an explicit FlowGuard-derived target split structure
before the mesh reviews ownership and evidence.

## What Changes

- Add target split derivation evidence to ModelMesh so a parent model boundary
  records the FlowGuard model, functional areas, state, side effects, and target
  child model layout used to derive the split.
- Add target split derivation evidence to TestMesh so a parent test gate records
  the FlowGuard validation-structure model and target child suite/script layout
  used to derive the split.
- Update Mesh protocols, public docs, templates, and focused tests so supplied
  partition maps without derivation evidence are not enough.
- Add a FlowGuard rollout model for this mesh-family behavior change.

## Capabilities

### New Capabilities

- `model-mesh-target-split-derivation`: Requires ModelMesh parent/child model
  layouts to carry model-derived target split evidence before mesh confidence.
- `test-mesh-target-split-derivation`: Requires TestMesh parent/child validation
  layouts to carry model-derived target split evidence before parent gate
  confidence.

### Modified Capabilities

- `hierarchical-model-mesh`: ModelMesh review now blocks broad confidence when
  a parent model split lacks target split derivation evidence.
- `test-evidence-mesh`: TestMesh review now blocks broad confidence when a
  parent test split lacks target split derivation evidence.

## Impact

- Public API: new target split derivation dataclasses and plan fields for
  hierarchical model mesh and TestMesh.
- Review behavior: missing or incomplete derivation evidence becomes a blocker
  for ModelMesh/TestMesh parent confidence.
- Documentation/templates: mesh docs and templates teach target split derivation
  before ownership/evidence review.
- Tests: focused unit, template, docs, OpenSpec, and FlowGuard rollout checks.
