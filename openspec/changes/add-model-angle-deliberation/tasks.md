## 1. Core Model Angle API

- [x] 1.1 Add `flowguard/model_angle_deliberation.py` with free-form deliberation rows, review report, decisions, confidence levels, and JSON/text formatting.
- [x] 1.2 Export the model-angle helper API through the public facade and route API groups without adding it to core Explorer semantics.
- [x] 1.3 Add a public `model-angle-template` command and template files.

## 2. Route Integrations

- [x] 2.1 Extend ExistingModelPreflight with model-angle review fields and validation.
- [x] 2.2 Extend SummaryReport and MaintenanceScan routing for model-angle gaps.
- [x] 2.3 Extend ClosureContract and RiskEvidenceLedger to consume model-angle evidence.

## 3. Guidance, Docs, And Version Records

- [x] 3.1 Update route-first docs, productized helper docs, and API surface docs.
- [x] 3.2 Update source and installed FlowGuard skills plus AGENTS snippet with compact open-ended model-angle guidance.
- [x] 3.3 Update changelog, package version, project manifest, and adoption notes for the local upgrade.

## 4. Tests And Self-Model

- [x] 4.1 Add focused unit tests for model-angle review, preflight integration, summary/maintenance routing, closure, risk ledger, public API, template output, and skill docs.
- [x] 4.2 Add a FlowGuard self-model for correct and broken model-angle deliberation workflows.
- [x] 4.3 Run focused tests and self-model checks, fixing failures immediately.

## 5. Full Validation And Sync

- [x] 5.1 Run OpenSpec strict validation, project audit, and broad practical regression.
- [x] 5.2 Sync editable/local installed package and verify import path, metadata version, schema, and feature availability.
- [x] 5.3 Sync the shadow workspace/source set without reverting peer-agent work and verify shadow imports/focused tests.
- [x] 5.4 Check local git status, create scoped commit/tag if safe, and record final FlowGuard adoption evidence.
