## 1. ContractExhaustion Core

- [x] 1.1 Add coverage-universe, universe-exclusion, contract-fault-profile, and observed-problem backfeed data classes.
- [x] 1.2 Extend `ContractExhaustionPlan` and `ContractExhaustionReport` to carry universe and backfeed review data.
- [x] 1.3 Add review checks for missing universe declarations, missing required ids, invalid exclusions, and missing actionable oracle feedback.
- [x] 1.4 Add generic synthetic contract-fault profile generation from generated cases and oracles.
- [x] 1.5 Add observed-problem backfeed review against generated cases, combination cases, same-class ids, and coverage receipts.

## 2. Public API, Docs, And Templates

- [x] 2.1 Export new public symbols under the existing `contract_exhaustion_mesh` API and modeling helper inventory.
- [x] 2.2 Update API surface, check plan, productized helper, topology, and ContractExhaustionMesh guidance docs.
- [x] 2.3 Keep language generic: contract submitter, payload, worker, runtime, package, or boundary; no FlowPilot-only fake-AI API.

## 3. Tests And Validation

- [x] 3.1 Add focused tests for broad claims requiring coverage universe and universe-required ids.
- [x] 3.2 Add focused tests for actionable oracle feedback, generic synthetic fault profiles, and observed-problem backfeed.
- [x] 3.3 Update API/template tests for the new exported symbols and docs.
- [x] 3.4 Run OpenSpec validation, targeted pytest, project audit, and package import/version checks.

## 4. Sync And Closure

- [x] 4.1 Bump the local package version and changelog for the new generic capability.
- [x] 4.2 Sync the editable local install and verify imports from outside the repo.
- [x] 4.3 Commit scoped local changes without pushing to GitHub.
- [x] 4.4 Record KB postflight if this work produced a reusable lesson.
