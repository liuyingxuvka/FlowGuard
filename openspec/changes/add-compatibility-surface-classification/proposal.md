## Why

FlowGuard Architecture Reduction can already identify merge, collapse, remove,
and keep-facade candidates, but it does not explicitly classify whether a
candidate is current behavior or an old compatibility surface. That gap makes
legacy aliases, migration branches, pass-through adapters, and historical
facades look like ordinary code contraction work even when they require a
different safety decision.

## What Changes

- Add compatibility-surface classification to Architecture Reduction before
  contraction candidates are reported as ready.
- Classify each relevant old or alternate surface as current contract,
  boundary adapter, negative legacy test, archive-only evidence, prune
  candidate, or evidence-needed.
- Block or downgrade unsafe contraction when a candidate touches current
  contracts, public entrypoints, negative legacy tests, or surfaces with
  missing evidence.
- Keep `LegacyPathDisposition` as the post-repair closure mechanism for old
  paths, while Architecture Reduction owns pre-reduction classification.
- Update API exports, documentation, and tests for the new helper type and
  review findings.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `architecture-reduction`: Architecture Reduction classifies compatibility
  surfaces before treating old aliases, adapters, branches, facades, migration
  paths, or retired tests as safe contraction candidates.
- `legacy-path-disposition`: Clarifies that legacy path disposition remains
  post-repair closure evidence and can consume Architecture Reduction's
  compatibility classification when old paths remain reachable.

## Impact

- Affected code: `flowguard/architecture_reduction.py`,
  `flowguard/__init__.py`, and tests for architecture reduction and API
  surface exports.
- Affected docs/specs: Architecture Reduction spec, Legacy Path Disposition
  spec, API surface documentation, and a short compatibility-surface guide.
- No breaking change to existing constructor call sites is intended; new plan
  fields default to empty tuples.
