## Why

AI coding agents can already model workflows with FlowGuard before editing code,
but large implementations can still collapse into oversized scripts when the
model is not translated into an implementation structure. StructureMesh also
reviews large-script decomposition, but it currently checks a supplied split
rather than requiring the target child structure to be derived from a
FlowGuard functional model.

## What Changes

- Add a parallel `code_structure_recommendation` route to the
  `model-first-function-flow` Skill for users or agents who want a recommended
  implementation structure before code is written.
- Add a dedicated Code Structure Recommendation protocol that can build or use
  FlowGuard functional and hierarchical models, then recommend modules,
  orchestration boundaries, state owners, side-effect adapters, facades, and
  validation boundaries.
- Upgrade StructureMesh so existing large-script or large-module splits include
  an internal, mandatory model-derived target split step before ownership,
  facade, dependency, and parity review.
- Add public helper objects for representing model-derived target structure
  recommendations and reviewing whether a StructureMesh plan includes one.
- Update docs, templates, Skill routing text, tests, changelog, and README
  release-facing references.

## Capabilities

### New Capabilities
- `code-structure-recommendation`: Recommends implementation structure from
  requirements, existing functional models, or hierarchical functional models
  without writing production code.

### Modified Capabilities
- `structure-refactor-mesh`: Requires existing large-script or large-module
  decomposition reviews to include a target child structure derived from a
  FlowGuard functional model.
- `model-first-function-flow`: Adds the parallel code structure recommendation
  route while keeping ordinary core modeling lightweight and non-mandatory.

## Impact

- Public API: new code-structure recommendation dataclasses and review helper,
  exported from `flowguard`.
- StructureMesh API: `StructureMeshPlan` gains target structure recommendation
  evidence and reviews it as part of the split.
- CLI/templates: add a code-structure-recommendation template and strengthen the
  StructureMesh template.
- Skill/docs: update route map, modeling guidance, StructureMesh protocol, API
  surface docs, README, and changelog.
- Tests: focused API, template, docs, and model tests; broad test suite before
  release.
