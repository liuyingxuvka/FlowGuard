## Why

FlowGuard has first-class routes for product behavior, model/test alignment,
model meshes, test meshes, and structure meshes, but it does not yet model the
development lifecycle itself as an executable stateful process. Agents can
therefore overclaim completion when a later design, model, code, test, or peer
workspace change makes earlier validation evidence stale.

## What Changes

- Add `development_process_flow` as a sibling model-first route for development
  lifecycle ordering, artifact version changes, evidence freshness, and minimum
  revalidation decisions.
- Add public helper APIs for process artifacts, lifecycle actions, action
  effects, evidence records, validation requirements, freshness rules, reports,
  and revalidation recommendations.
- Add a `development-process-flow-template` starter that demonstrates a V-style
  lifecycle with broken variants for stale evidence, verifier changes, release
  overclaims, and background progress-only evidence.
- Update the model-first Skill, reference protocols, public docs, README, API
  surface, productized helper docs, and changelog.
- Keep the new route parallel to ModelMesh, TestMesh, StructureMesh, and
  Model-Test Alignment. It may reference sibling route evidence ids, but it
  must not inspect or replace sibling route internals.

## Capabilities

### New Capabilities

- `development-process-flow`: Reviews development lifecycle workflows for
  artifact overwrite, ordering gaps, stale validation evidence, missing
  revalidation, verifier changes, peer-agent writes, routine/release scope
  boundaries, and unsupported done/release/archive claims.

### Modified Capabilities

- `model-first-function-flow`: Adds `development_process_flow` as a first-class
  sibling route for development lifecycle confidence.

## Impact

- Public API: new development-process-flow dataclasses, constants, review
  function, and minimum revalidation helper.
- CLI/templates: new
  `python -m flowguard development-process-flow-template --output .`.
- Skill/docs: update the FlowGuard Skill Kernel route map, reference protocol
  ownership map, modeling protocol trigger checks, agents snippet, public API
  docs, productized helpers, README, and changelog.
- Tests: add focused process-flow unit tests, public-template tests, API
  surface tests, and Skill/doc routing tests.
- Dependencies: none; keep runtime helpers standard-library-only.
