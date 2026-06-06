## Why

FlowGuard currently has useful pieces for route handoff, state closure,
transition coverage, code contracts, legacy-path disposition, and bug repair,
but replacement work can still leave old paths, old fields, prompt fallbacks,
or shallow tests alive across different layers. Field-heavy systems also need
a complete field accounting layer so AI agents do not silently omit fields that
drive behavior, migration, replay, or cleanup.

## What Changes

- Add a first-class `field-lifecycle-mesh` capability that records every
  discovered field at leaf level, classifies its role, lifecycle, ownership,
  behavior impact, replacement relation, disposition, and required evidence.
- Make replacement semantics explicit: unless compatibility is declared, new
  feature work and feature migration default to old-path and old-field
  disposition before done confidence.
- Project behavior-bearing fields from the field lifecycle mesh into existing
  model obligations, transition coverage cells, code contracts, and test
  evidence requirements.
- Extend bug repair closure so observed failures, same-class generalized cases,
  root cause, field lifecycle gaps, owner code contracts, tests, old-path
  disposition, and old-field disposition close as one loop.
- Extend process freshness and closure gates so field lifecycle edits, field
  projections, replacement decisions, prompt guidance changes, and code/test
  binding edits invalidate earlier evidence.
- Update AI-facing route guidance and templates so agents use structured
  field/replacement evidence instead of preserving fallback or compatibility
  paths by default.
- No dependency changes are expected.

## Capabilities

### New Capabilities

- `field-lifecycle-mesh`: Represents complete field inventory, field
  parent/child coverage, field-role classification, behavior projections,
  old/new field relationships, field disposition, and evidence obligations.

### Modified Capabilities

- `flowguard-global-routing`: Default replacement work requires old-path and
  old-field disposition unless explicit compatibility is declared.
- `existing-model-preflight`: Existing model grounding includes field lifecycle
  ownership, hidden field gaps, and reuse/extend/add-child decisions for field
  models.
- `model-first-function-flow`: Model-first checks surface field lifecycle mesh
  needs and require behavior-bearing field projection or scoped-out reasons.
- `code-structure-recommendation`: Target code structure consumes field owner,
  reader, writer, public-entrypoint, and validation-boundary maps.
- `model-test-alignment`: Alignment consumes field projections and requires
  model obligations, code contracts, and tests to bind the same behavior-bearing
  fields.
- `post-runtime-model-miss-review`: Bug repair review treats missing field
  modeling and old-field disposition as possible root-cause and closure gaps.
- `development-process-flow`: Lifecycle freshness tracks field mesh,
  projection, replacement, model-code-test binding, and bug repair evidence.
- `architecture-reduction`: Reduction can classify old fields and field-like
  compatibility surfaces before contraction.
- `legacy-path-disposition`: Replacement closure includes old-field
  disposition alongside old path disposition.
- `flowguard-closure-contract`: Full confidence consumes field lifecycle mesh,
  replacement disposition, model-code-test binding, bug repair, and freshness
  evidence.
- `flowguard-ai-entry-simplification`: Compact AI guidance points agents to the
  field/replacement handoff without creating a parallel all-in-one runner.

## Impact

- Affected code/API: new field lifecycle module and exports, Model-Test
  Alignment data consumption, Model-Miss/closure data rows, DevelopmentProcess
  freshness rules, Architecture Reduction classification, maintenance scan
  handoffs, and route API grouping.
- Affected models: new FlowGuard self-model for default replacement and field
  lifecycle closure, plus focused updates to related route models where needed.
- Affected prompts/docs/templates: `.agents/skills/*/SKILL.md`, route reference
  docs, `docs/*`, `flowguard/template_text/*`, `docs/agents_snippet.md`, and
  public template tests.
- Affected validation/sync: OpenSpec strict validation, FlowGuard model checks,
  focused tests, full regression when practical, editable install sync,
  installed Codex skill sync, shadow workspace sync, local git sync, and
  adoption log updates.
