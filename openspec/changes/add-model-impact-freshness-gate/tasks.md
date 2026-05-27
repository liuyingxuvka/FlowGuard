## 1. OpenSpec And Model

- [x] 1.1 Record proposal, design, spec, and tasks for model-impact freshness.
- [x] 1.2 Verify the real `flowguard` package is importable before production edits.
- [x] 1.3 Inspect existing route ownership and public API export constraints.
- [x] 1.4 Add an executable FlowGuard model rejecting blind full-reuse, missing classification, and affected-without-rerun routes.

## 2. Core API

- [x] 2.1 Add model inventory, upgrade impact, impact assessment, reuse ticket, rerun evidence, plan, report, and finding dataclasses.
- [x] 2.2 Add `review_model_impact_freshness(...)` for selective affected/rerun versus unchanged/reuse decisions.
- [x] 2.3 Export the helper API through `flowguard.__init__`, `__all__`, and API surface groups.

## 3. Docs And Versioning

- [x] 3.1 Update framework-upgrade, DevelopmentProcessFlow, modeling protocol, product helper, and API surface docs.
- [x] 3.2 Update package changelog and version.

## 4. Validation

- [x] 4.1 Add focused tests for green paths and known-bad omissions.
- [x] 4.2 Run OpenSpec validation for this change.
- [x] 4.3 Run focused package tests and the executable FlowGuard model checks.
- [x] 4.4 Run broader/background regression checks and inspect final artifacts.

## 5. Sync

- [x] 5.1 Sync the local editable installation.
- [x] 5.2 Verify installed import path/version and schema version.
- [x] 5.3 Sync the shadow workspace without reverting parallel work.
- [ ] 5.4 Commit/tag local git version if validation passes.
- [ ] 5.5 Run KB postflight and record reusable lessons if any.
