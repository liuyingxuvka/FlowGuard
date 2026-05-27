## 1. Model And API

- [x] 1.1 Add a FlowGuard rollout model for risk evidence ledger confidence gaps.
- [x] 1.2 Implement public risk evidence ledger data classes, review findings,
  reports, and decision logic.
- [x] 1.3 Export the new public APIs and add CLI/template generation support.

## 2. Route Guidance And Docs

- [x] 2.1 Update the model-first skill kernel and adoption protocol so completion
  claims require a risk evidence ledger boundary.
- [x] 2.2 Update Model-Test Alignment, DevelopmentProcessFlow, Model-Miss Review,
  TestMesh, ModelMesh, Existing Model Preflight, StructureMesh, and Code
  Structure Recommendation guidance with their ledger responsibilities.
- [x] 2.3 Update README, API surface docs, modeling/adoption docs, and changelog.

## 3. Tests And Validation

- [x] 3.1 Add focused unit tests for full, partial, stale, skipped,
  internal-path-only, out-of-scope, and route-handoff ledger decisions.
- [x] 3.2 Add public template and skill documentation tests for the new guidance.
- [x] 3.3 Run OpenSpec validation, the new rollout model, focused tests, full
  regression, and benchmark/evidence checks.

## 4. Release And Sync

- [x] 4.1 Bump the package to the next patch version and verify README,
  changelog, package metadata, and schema/version wording.
- [x] 4.2 Sync editable install, installed Codex skills, and the
  `FlowGuard_20260427` shadow workspace.
- [x] 4.3 Commit the scoped changes, tag the release, push to GitHub, create the
  GitHub Release, and verify branch protection plus version/tag/release
  alignment.
- [x] 4.4 Record FlowGuard adoption evidence and KB postflight observations.
