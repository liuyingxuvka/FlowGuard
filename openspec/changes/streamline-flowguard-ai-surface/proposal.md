## Why

FlowGuard 0.36.0 already has the right model-similarity maintenance capability,
but the AI-facing path still asks agents to see too many fields, repeated
handoff ids, and the large flat helper inventory too early. This change keeps
the existing capability and makes it easier to use correctly by making the
normal path route-first, profile-based, and handoff-based.

## What Changes

- Add lightweight model-similarity construction helpers for the ordinary
  maintenance path so agents can describe a model family without filling every
  full-schema field.
- Add one `SimilarityHandoff` bundle for downstream routes so relation,
  maintenance-group, change-impact, test-obligation, code-obligation, impacted
  model, and false-friend evidence travels together.
- **BREAKING**: remove repeated downstream similarity id fields where the new
  handoff carries the same information more clearly.
- Keep full schema dataclasses available for advanced evidence and deep route
  work, but move docs/templates toward a basic path first and a full-schema
  path second.
- Keep the existing Model Similarity Consolidation route as the owner of A/B/C
  maintenance similarity; do not add a parallel new capability.
- Refresh OpenSpec, FlowGuard self-model evidence, tests, version records,
  editable install, shadow workspace, and local git state.

## Capabilities

### New Capabilities

### Modified Capabilities

- `flowguard-ai-entry-simplification`: the thin AI entry path now requires
  route-first grouped discovery, profile helpers, and a basic/full split before
  the flat helper inventory.
- `flowguard-structure-simplification`: public structure simplification now
  permits removing stale compatibility fields when a clearer replacement keeps
  behavior and validation evidence intact.
- `code-structure-recommendation`: model-similarity maintenance provenance is
  consumed through a handoff object rather than repeated scalar id fields.

## Impact

- Affected public API: model-similarity helpers, downstream FlowGuard route
  dataclasses, route API registries, and `__all__`.
- Affected docs/templates: API surface docs, model-similarity docs, README,
  changelog, and route template text.
- Affected tests: model similarity, downstream integrations, public API
  surface, public templates, OpenSpec, FlowGuard self-model, install/shadow
  verification, and regression checks.
- No dependency changes and no remote publishing unless separately requested.
