## 1. OpenSpec And FlowGuard Model

- [x] 1.1 Validate the OpenSpec change and read apply instructions.
- [x] 1.2 Add an executable FlowGuard self-model for route-first surface,
  compatibility-field cleanup, handoff evidence, validation, install, shadow,
  and git gates.

## 2. Model Similarity Surface

- [x] 2.1 Add `SimilarityHandoff` and report conversion in the existing model
  similarity route.
- [x] 2.2 Add lightweight signature and plan helpers for minimal and
  maintenance-oriented reviews.
- [x] 2.3 Preserve full dataclass construction for advanced cases.

## 3. Downstream Handoff Cleanup

- [x] 3.1 Replace repeated similarity scalar fields in Existing Model Preflight
  with `similarity_handoff`.
- [x] 3.2 Replace repeated similarity scalar fields in Code Structure
  Recommendation with `similarity_handoff`.
- [x] 3.3 Replace repeated similarity scalar fields in Model-Test Alignment
  with `similarity_handoff`.
- [x] 3.4 Replace repeated similarity scalar fields in Architecture Reduction
  with `similarity_handoff`.

## 4. Docs, Templates, And API Registry

- [x] 4.1 Export the new helpers through the route API and public facade.
- [x] 4.2 Update route-first API docs and model-similarity docs with basic and
  full paths.
- [x] 4.3 Update templates, README, and changelog to teach the clean handoff
  path and mark the compatibility cleanup.

## 5. Tests

- [x] 5.1 Add focused tests for lightweight constructors and `SimilarityHandoff`.
- [x] 5.2 Update downstream integration tests to use `similarity_handoff`
  instead of old repeated scalar fields.
- [x] 5.3 Add API/doc/template tests that enforce route-first/basic-full
  guidance.

## 6. Validation And Sync

- [x] 6.1 Run OpenSpec validation, FlowGuard self-model, focused tests, project
  audit, and full regression.
- [x] 6.2 Refresh editable install and verify import path, version, schema, and
  new API availability.
- [x] 6.3 Sync the updated checkout to
  the local local shadow workspace and verify shadow imports,
  OpenSpec, project audit, self-model, and focused tests.
- [x] 6.4 Record FlowGuard adoption evidence and KB postflight.
- [x] 6.5 Commit local git and tag the local version.
