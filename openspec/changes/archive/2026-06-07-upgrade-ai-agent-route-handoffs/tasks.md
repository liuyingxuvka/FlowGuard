## 1. Model And Contract Setup

- [x] 1.1 Add or update a FlowGuard self-model for AI route handoff continuity.
- [x] 1.2 Add focused tests that prove handoff outputs do not create a parallel session runner.

## 2. Summary Report Handoffs

- [x] 2.1 Add structured action fields to `FlowGuardFindingLedgerEntry`.
- [x] 2.2 Map existing summary section categories to owner routes, action kinds, required inputs, proof gap codes, and claim effects.
- [x] 2.3 Update summary report JSON/text tests for structured handoff output.

## 3. Maintenance Obligation And Scan Bridge

- [x] 3.1 Add structured action fields to `MaintenanceObligation`.
- [x] 3.2 Add structured action fields to `MaintenanceAction`.
- [x] 3.3 Add `maintenance_scan_plan_from_summary_report(...)`.
- [x] 3.4 Update maintenance scan tests and template examples.

## 4. DevelopmentProcessFlow Rerun Guidance

- [x] 4.1 Extend `RevalidationRecommendation` with route, proof, freshness-gap, and blocked-claim metadata.
- [x] 4.2 Update DevelopmentProcessFlow recommendation generation and tests.
- [x] 4.3 Update DevelopmentProcessFlow template output.

## 5. Existing Model Preflight Inventory

- [x] 5.1 Add `existing_model_preflight_from_project(...)`.
- [x] 5.2 Add focused tests for found-model and no-model inventory paths.
- [x] 5.3 Update ExistingModelPreflight docs/template guidance.

## 6. Public API, Prompt, And Docs Sync

- [x] 6.1 Export new helpers and keep them out of `CORE_API`.
- [x] 6.2 Update route-first API docs and productized helper docs.
- [x] 6.3 Update compact skill hot paths and AGENTS snippet within prompt budgets.
- [x] 6.4 Update OpenSpec specs, task status, and version/changelog records as needed.

## 7. Verification, Install Sync, And Local State

- [x] 7.1 Run focused unit tests for summary report, maintenance scan, development process flow, existing-model preflight, API surface, and skill docs.
- [x] 7.2 Run FlowGuard self-model checks and OpenSpec strict validation.
- [x] 7.3 Run practical regression and project audit.
- [x] 7.4 Sync editable/local installed version and verify import path, metadata version, and feature availability.
- [x] 7.5 Check source/local git status without reverting peer-agent changes, and record final adoption evidence.
