## Why

FlowGuard already routes structural, evidence, and model-fidelity gaps to
existing specialist routes, but those open obligations are mostly local to the
current report. Agents can later touch the same model, code path, test surface,
or public entrypoint without automatically reloading the unresolved obligation.

This change upgrades the existing finding-ledger, maintenance-scan,
model-maturation, and risk-ledger chain so normal FlowGuard use preserves
anchored maintenance obligations and re-triggers them on future relevant work,
without introducing a standalone technical-debt scanner or parallel workflow.

## What Changes

- Extend the unified finding ledger with machine-readable obligation records
  for anchored non-pass findings, skipped routes, stale evidence, structure
  pressure, and scoped future-use hazards.
- Extend maintenance scan inputs so prior open obligations can be supplied
  alongside current changed artifacts, evidence rows, signals, and skipped
  routes.
- Make maintenance scan route reopened obligations back to existing FlowGuard
  owner routes when the current work touches their anchored model/code/test or
  public surface.
- Let model maturation preserve unresolved required model-upgrade signals as
  open obligations instead of letting them disappear after a scoped report.
- Let Risk Evidence Ledger consume relevant open obligations before full done,
  release, publish, archive, or production-confidence claims.
- Update compact agent guidance and templates to say that open obligations are
  inherited through the existing maintenance chain, not handled by a new
  technical-debt route.

## Capabilities

### New Capabilities
- `maintenance-obligation-memory`: Records and reuses anchored open
  maintenance obligations produced by existing FlowGuard reports.

### Modified Capabilities
- `flowguard-global-routing`: Clarifies that normal FlowGuard use inherits open
  obligations through existing routes instead of invoking a separate technical
  debt scanner.
- `model-first-function-flow`: Requires model-first summary gaps that are
  anchored to model/code/test/entrypoint surfaces to be exposed as open
  obligations for maintenance scan consumption.
- `model-maturation-loop`: Preserves unresolved required maturation signals as
  open obligations until resolved or explicitly scoped.
- `risk-evidence-ledger`: Blocks or scopes broad confidence when relevant open
  obligations remain unresolved.

## Impact

- Public helper/reporting API additions for obligation records.
- `FlowGuardSummaryReport`, `review_maintenance_scan(...)`,
  `review_model_maturation_loop(...)`, and `review_risk_evidence_ledger(...)`.
- Maintenance scan templates, API docs, check-plan docs, risk-ledger docs,
  modeling protocol, AGENTS snippet, and satellite skill guidance.
- Focused tests, self-model checks, OpenSpec validation, package version sync,
  editable install, and local repository synchronization.
