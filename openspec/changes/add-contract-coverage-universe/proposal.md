## Why

ContractExhaustionMesh can generate canonical cases from declared finite
boundaries, but it cannot yet prove that the declared boundary set itself is
complete for a broad coverage claim. Real misses can therefore appear outside
the generated matrix without FlowGuard clearly reporting "the coverage universe
was incomplete".

## What Changes

- Add a generic coverage-universe declaration to ContractExhaustionMesh so a
  model can name the dimensions, axes, interaction groups, payload contracts,
  code boundaries, generated cases, and receipts that are in scope.
- Require broad/full coverage claims to declare and satisfy that universe, or
  to record explicit scoped exclusions.
- Add actionable oracle-feedback checks so rejection/block/reissue cases prove
  that the expected feedback names the missing fields and repair target.
- Add generic synthetic contract-fault profiles from generated cases. These
  describe bad submitter behavior in domain-neutral terms and do not introduce
  a FlowPilot-specific fake-AI surface.
- Add observed-problem backfeed so a real miss must map to generated cases,
  same-class cases, and receipts, or be reported as a model/coverage gap.
- Update public API docs, templates, and tests under the existing
  `contract_exhaustion_mesh` route.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `contract-exhaustion-mesh`: coverage-universe completeness, actionable
  oracle feedback, generic synthetic fault profiles, and observed-problem
  backfeed become first-class route behavior.

## Impact

- Affected code: `flowguard/contract_exhaustion.py`, `flowguard/__init__.py`.
- Affected tests: contract-exhaustion tests and public API/template tests.
- Affected docs/templates: OpenSpec spec delta, API surface docs, check plan,
  productized helper docs, topology, and ContractExhaustionMesh guidance.
