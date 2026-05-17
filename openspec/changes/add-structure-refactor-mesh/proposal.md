## Why

Large scripts and broad modules are difficult for AI agents to refactor safely.
FlowGuard already has mesh helpers for model boundaries and test evidence; it
now needs a parallel helper for structure-preserving software decomposition.

## What Changes

- Add StructureMesh as an optional FlowGuard helper for reviewing large-script
  and large-module decomposition plans before or during refactors.
- Add public dataclasses and `review_structure_mesh(...)` for facade retention,
  public entrypoint preservation, partition ownership, state ownership, side
  effect ownership, dependency cycles, configuration drift, and behavior parity
  evidence.
- Add a public `structure-mesh-template` CLI scaffold.
- Update the `model-first-function-flow` Skill with a
  `structure_mesh_maintenance` route and a dedicated reference protocol.
- Add public docs, README/API/changelog entries, OpenSpec artifacts, focused
  tests, and a FlowGuard rollout model.

## Capabilities

### New Capabilities

- `structure-refactor-mesh`: Reviews whether a large script or module can be
  split into smaller owned modules without losing public entrypoints, changing
  behavior contracts, duplicating state or side effects, introducing dangerous
  dependency cycles, or overclaiming release confidence.

### Modified Capabilities

- `model-first-function-flow`: Adds StructureMesh as a first-class route beside
  ModelMesh and TestMesh for structure-preserving software decomposition.

## Impact

- Public API: new StructureMesh helper dataclasses, constants, and review
  function.
- CLI/templates: new `python -m flowguard structure-mesh-template --output .`.
- Skill/docs: update model-first Skill, AGENTS snippet, modeling protocol, API
  surface docs, README, changelog, and a new StructureMesh protocol doc.
- Tests: add focused StructureMesh unit tests plus public-template and Skill
  doc tests.
