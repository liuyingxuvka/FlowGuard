## 1. FlowGuard Model And Contract

- [x] 1.1 Add a FlowGuard self-model for the existing maintenance-obligation chain.
- [x] 1.2 Add tests proving anchored obligations route through existing owner routes and unanchored observations do not become blockers.

## 2. Core Obligation Memory

- [x] 2.1 Add public helper data types for maintenance obligations and obligation reports.
- [x] 2.2 Add conversion helpers from summary findings, maintenance actions, and maturation findings to obligations.
- [x] 2.3 Export obligation helper APIs through the reporting/helper surface and route registry without adding them to core.

## 3. Existing Flow Upgrades

- [x] 3.1 Extend `FlowGuardSummaryReport` and model-first checks to expose obligation memory metadata.
- [x] 3.2 Extend `MaintenanceScanPlan` and `review_maintenance_scan(...)` to consume prior obligations and reopen touched anchors.
- [x] 3.3 Extend `ModelMaturationReport` to expose unresolved required signals as obligations.
- [x] 3.4 Extend `RiskEvidenceLedgerPlan` and `review_risk_evidence_ledger(...)` to block or scope broad claims with relevant open obligations.

## 4. Guidance, Templates, And Docs

- [x] 4.1 Update compact FlowGuard kernel, AGENTS snippet, and satellite guidance to inherit open obligations through existing routes.
- [x] 4.2 Update docs for check plans, maintenance scan, model maturation, risk evidence ledger, API surface, README, and adoption guidance.
- [x] 4.3 Update templates or examples so projects can persist and pass obligations without treating them as validation.

## 5. Verification And Sync

- [x] 5.1 Run OpenSpec validation for the change and all specs.
- [x] 5.2 Run focused unit tests for obligation memory, summary report, maintenance scan, maturation, risk ledger, API surface, public templates, and skill docs.
- [x] 5.3 Run FlowGuard self-model checks and practical model regressions, using background execution for long suites and collecting exit artifacts.
- [x] 5.4 Run full practical Python regression.
- [x] 5.5 Sync package version, editable install, project adoption record, installed local skills, and local repository/git copy when a git root is available.
- [x] 5.6 Record FlowGuard adoption evidence and residual sync gaps without reverting peer-agent changes.
