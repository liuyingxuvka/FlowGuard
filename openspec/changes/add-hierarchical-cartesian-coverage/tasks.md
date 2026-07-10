## 1. ContractExhaustion Core

- [x] 1.1 Add model-scoped axis, interaction-group, combination-case, shard, and coverage-receipt data classes.
- [x] 1.2 Add deterministic local Cartesian generation for interaction groups and parent interface summaries.
- [x] 1.3 Add coverage receipt review logic for missing model ids, unbounded axes, missing oracles, unfinished shards, and invalid child receipt consumption.
- [x] 1.4 Add projection helpers from combination reports to MTA obligations, TestMesh case ids, RiskLedger gate ids, and composite handoff ids.

## 2. Model, Test, And Risk Integration

- [x] 2.1 Add ModelMesh review support for required model coverage receipts, stale receipts, duplicate receipts, and child receipts not consumed by parent receipts.
- [x] 2.2 Add Model-Test Alignment support for generated combination case obligations and tests that must cite combination case ids.
- [x] 2.3 Add TestMesh support for required combination case ids and coverage shard ids as child evidence targets.
- [x] 2.4 Add RiskEvidenceLedger gates for all-model Cartesian coverage, missing receipts, unclosed shards, and unconsumed child coverage.

## 3. Bug Family And Model Miss Backpropagation

- [x] 3.1 Extend family bad-case and defect-family gate records with model ids, root-cause dimensions, interaction group ids, combination case ids, and coverage receipt ids.
- [x] 3.2 Update model-miss guidance/templates so combination bugs must promote interaction groups before closure.

## 4. Docs, Skills, And API Surface

- [x] 4.1 Export new public API symbols under the existing `contract_exhaustion_mesh` route.
- [x] 4.2 Update ContractExhaustionMesh, ModelMesh, Model-Test Alignment, TestMesh, ModelMissReview, RiskEvidenceLedger, and DevelopmentProcessFlow skill guidance.
- [x] 4.3 Update API docs, productized helper docs, modeling protocol, check plan, and topology docs for all-model Cartesian coverage.
- [x] 4.4 Update OpenSpec managed specs with the new requirements when archiving is ready.

## 5. Validation And Sync

- [x] 5.1 Add focused tests for local model Cartesian generation, receipt review, parent/child consumption, TestMesh shard evidence, MTA binding, RiskLedger gates, and bug-family backpropagation fields.
- [x] 5.2 Run focused tests for affected modules and repair failures.
- [x] 5.3 Run OpenSpec strict validation, FlowGuard project audit, and full pytest.
- [x] 5.4 Sync source repo, shadow workspace, installed skill copies, and local package install; verify imports and versions.
- [x] 5.5 Commit scoped changes, push to GitHub, and confirm Git state.
