## Why

FlowGuard framework upgrades currently rely on human discipline to decide
whether older `.flowguard` models must be updated and rerun. That creates two
bad outcomes:

- a blanket full rerun wastes time when a model and its evidence are truly
  unchanged;
- blind reuse is unsafe when an upgrade touched the model dependency,
  FlowGuard semantics, tests, or evidence interpretation.

The desired rule is selective but mandatory: every existing model in scope must
be classified for the upgrade. Affected models need current update review and
rerun evidence. Unaffected models may reuse prior evidence only with an explicit
reuse ticket that proves the result is still the same.

## What Changes

- Add a public model impact freshness helper that inventories existing
  FlowGuard models, records the upgrade impact surface, classifies each model,
  validates reuse tickets, and validates affected-model rerun evidence.
- Add a FlowGuard model for the gate itself so known-bad routes fail: missing
  classification, old-evidence reuse, and affected models accepted without
  rerun.
- Update framework-upgrade, modeling, DevelopmentProcessFlow, API, and helper
  docs so upgrade confidence uses this gate before completion or release
  claims.
- Add tests, release notes, version update, local editable install sync, shadow
  workspace sync, and local git version sync.

## Capabilities

### New Capabilities

- `model-impact-freshness-gate`: Reviews whether previous FlowGuard model
  evidence can remain current after a FlowGuard upgrade.

### Modified Capabilities

- DevelopmentProcessFlow should consume model-impact freshness evidence before
  claiming a FlowGuard framework upgrade is done or release-ready.
- Framework upgrade checks should require this gate before broad statements
  about all existing FlowGuard models.

## Impact

- Affected package APIs: new dataclasses, constants, report type, and
  `review_model_impact_freshness(...)` exported through `flowguard.__init__`.
- Affected docs: API surface, productized helpers, modeling protocol,
  DevelopmentProcessFlow, and framework upgrade checks.
- Affected tests: API surface tests, focused helper tests, and executable
  `.flowguard/model_impact_freshness_gate` checks.
- Runtime dependencies remain Python standard library only.
