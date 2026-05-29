## Why

FlowGuard can already review individual model boundaries, parent/child meshes,
architecture-reduction candidates, and model/test alignment, but it does not
proactively compare models to identify related workflows before new boundaries
or duplicate code are introduced. Projects with several modeled features need a
reviewable way to detect same-workflow reuse, family variants, symmetric flows,
shared kernels, duplicate ownership, adapter-only differences, and false
friends.

## What Changes

- Add a Model Similarity Consolidation capability that represents model
  signatures, typed model-to-model relations, consolidation candidates, route
  handoffs, and evidence gaps.
- Add a review helper that classifies relations as same workflow, family
  variant, symmetric flow, shared-kernel candidate, duplicate boundary,
  overlapping ownership, parent/child candidate, sibling overlap, adapter-only
  difference, evidence duplicate, false friend, unrelated, or manual review.
- Add target-action and downstream-route recommendations so similarity findings
  can feed Existing Model Preflight, ModelMesh, Architecture Reduction, Code
  Structure Recommendation, StructureMesh, Model-Test Alignment, and manual
  review without rewriting production code automatically.
- Add public API exports, CLI/template support, docs, OpenSpec specs, examples,
  tests, and FlowGuard adoption records for the new route.
- Update Existing Model Preflight so new or changed boundaries can carry
  current model-similarity evidence before deciding whether to reuse, extend,
  add a child model, create a family variant, extract a shared kernel, route to
  Architecture Reduction, or keep boundaries separate.
- No breaking changes.

## Capabilities

### New Capabilities

- `model-similarity-consolidation`: model signature extraction inputs, typed
  relation review, consolidation recommendations, evidence gaps, and downstream
  FlowGuard route handoffs.

### Modified Capabilities

- `existing-model-preflight`: full preflight can consume current
  model-similarity evidence and must keep unresolved similarity-required
  relation gaps visible before creating or extending model boundaries.
- `architecture-reduction`: reduction reviews can consume duplicate-boundary,
  adapter-only, and shared-kernel similarity relations as candidate provenance.
- `code-structure-recommendation`: structure recommendations can consume
  shared-kernel and family-variant similarity relations when deriving target
  modules, facades, adapters, and validation boundaries.
- `model-test-alignment`: alignment can consume evidence-duplicate or
  family-variant similarity relations to require sibling model obligations or
  family parity evidence when a broad same-class claim is made.

## Impact

- New package module: `flowguard/model_similarity.py`.
- Public API exports through `flowguard/__init__.py` and `docs/api_surface.md`.
- CLI/template registration through `flowguard/__main__.py` and
  `flowguard/templates.py`.
- Existing review helpers receive optional similarity handoff fields where
  needed for route integration.
- New tests for model similarity review, template/CLI export, API surface, and
  preflight integration.
- New `.flowguard/model_similarity_consolidation` executable model and adoption
  log entries.
