## Why

FieldLifecycleMesh already accounts fields and projects behavior-bearing fields
into model/code/test obligations, but broad confidence can still look like a
field dictionary unless the field row points to the gate, negative test, and
replay evidence that prove the field route. This change adds a minimal evidence
route convention without turning FieldLifecycleMesh into a duplicate test or
runtime-gateway runner.

## What Changes

- Require behavior-bearing field projections to carry lightweight evidence
  route references for broad field-lifecycle claims.
- Reuse existing `FieldProjection.evidence_refs` instead of adding a large new
  field-route schema.
- Teach templates, docs, and skill guidance to use `gate:`, `test:`, and
  `replay:` references for critical fields.
- Keep display-only and metadata fields scoped out by reason, not forced into
  runtime evidence routes.
- **BREAKING**: None. Existing bounded field-lifecycle plans keep working.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `field-lifecycle-mesh`: Broad field-lifecycle confidence requires behavior
  field projections to include minimal gate/test/replay evidence route
  references when those proof kinds are relevant.

## Impact

- Affected code/API: `flowguard/field_lifecycle.py` review logic and exported
  constants only; no large public object is added.
- Affected templates/docs: FieldLifecycleMesh public template, route docs,
  AGENTS snippet, and installed Codex skill guidance.
- Affected tests: focused field lifecycle and public template tests.
- Dependencies: Python standard library only.
