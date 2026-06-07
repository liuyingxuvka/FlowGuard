# Field Prompt Reduction Design

## Principles

1. Preserve quality-critical evidence fields.
   Required ids, status, freshness, boundary shape, skipped/not-run visibility,
   assertion scope, release scope, and scoped gaps remain visible.

2. Collapse repeated prose fields into field groups.
   For example, instead of separate inputs, outputs, state reads, state writes,
   side effects, errors, exactness, and notes on every row, use `boundary`
   with examples of what it must include when relevant.

3. Keep rare deep fields lazy.
   Closure roles, family evidence, leaf matrices, source-audit notes,
   background artifact details, and mesh closure internals should be listed as
   "expand when applicable" fields rather than always-present blanks.

4. Do not change runtime schemas in this pass.
   The risk is prompt burden, not package API compatibility. Runtime field
   removal should be a separate API change with broader tests.

## Target Collapses

### Model-Test Alignment

Collapse the checklist around:

- `obligation`: id, type, required, summary, required evidence kind.
- `boundary`: external inputs/outputs, state, side effects, errors, exactness.
- `evidence`: test/contract ids, status, freshness, assertion scope.
- `risk`: orphan, duplicate, stale, internal-only, source-audit, overclaim.

Move family evidence, closure roles, leaf matrix cells, runtime observations,
and detailed source-audit notes to optional expansion guidance.

### DevelopmentProcessFlow

Collapse artifacts, actions, evidence, requirements, and freshness rules into:

- `changed artifacts`
- `process steps`
- `validation evidence`
- `freshness / invalidation`
- `final claim boundary`

The prompt should ask for grouped summaries instead of a blank for every
subfield.

### TestMesh

Collapse parent, partition, child evidence, and split derivation prompts into:

- `parent gate`
- `ownership map`
- `child evidence`
- `split derivation`
- `release gaps`

Keep hidden skips, stale evidence, background final artifacts, and release-only
scope visible.

### ModelMesh

Collapse the inventory table into:

- `model`
- `risk boundary`
- `artifact paths`
- `interface`
- `ownership`
- `evidence`
- `gaps / split signals`
- optional `reattachment / closure`

### Adoption Log Template

Collapse the template into:

- `Task`
- `Artifacts`
- `Evidence`
- `Gaps / next actions`

## Validation

- OpenSpec strict validation.
- FlowGuard field-prompt reduction model.
- Skill documentation tests for grouped field families and prompt-field caps.
- Existing guidance compression and skill-doc tests.
- Installed skill parity and quick validation.
- Shadow workspace focused validation.
