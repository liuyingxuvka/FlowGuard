## Why

FlowGuard's field-bearing routes have accumulated too many input fields for
agents to read and fill reliably. The problem is no longer missing evidence
shape; it is that several dataclasses expose report-only, derived, historical,
or low-frequency gate fields as if they were normal model inputs.

## What Changes

- **BREAKING**: Remove the horizontal gate fields from `RiskEvidenceRow` and
  replace them with one typed `RiskEvidenceGate` list.
- **BREAKING**: Remove auto-split and large-run metric fields from
  `ProcessEvidence`; auto-split evidence must use the existing AutoSplit route
  rather than piggybacking on process evidence rows.
- **BREAKING**: Simplify Plan Intake mapping fields by keeping one evidence-id
  shape and removing duplicate or strict-adapter fields from normal mapping
  rows.
- **BREAKING**: Merge duplicated same-shape helper classes where they model the
  same concept.
- Update templates, docs, tests, and exported API lists so agents see the thin
  model first.
- Do not keep old field aliases, compatibility fallbacks, or migration shims in
  normal route logic.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `risk-evidence-ledger`: Risk rows use a compact gate list instead of
  route-specific gate columns.
- `development-process-flow`: Process evidence no longer carries auto-split
  metrics; auto-split evidence is handled by AutoSplit/TestMesh routes.
- `plan-intake-claims`: Plan intake mappings and source evidence use one
  canonical evidence-id shape.
- `flowguard-evidence-field-structure`: Field-bearing route schemas remove
  duplicate, report-only, historical, and derived input fields.
- `flowguard-api-registry`: Public exports and first-read API guidance reflect
  the thin breaking schema.

## Impact

- Affected code/API: `flowguard/risk_evidence_ledger.py`,
  `flowguard/development_process_flow.py`, `flowguard/plan_intake.py`,
  duplicated helper classes, and top-level exports.
- Affected templates/docs: public route templates, field inventory/API docs,
  route documentation, and OpenSpec specs.
- Affected tests: focused route tests, public template tests, API-surface
  tests, and model regression checks.
- Dependencies: Python standard library only.
