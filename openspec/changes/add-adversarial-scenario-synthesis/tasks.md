## 1. Scenario Matrix Core

- [x] 1.1 Add deterministic challenge pattern synthesis to `ScenarioMatrixBuilder`.
- [x] 1.2 Preserve existing max sequence length, max scenario count, tags, notes, workflow, invariants, and expectation behavior for challenge routes.
- [x] 1.3 Add scenario-matrix tests for challenge route shape, risk notes, tags, limit handling, and default `needs_human_review`.
- [x] 1.4 Add model-derived challenge synthesis from Explorer/CheckReport evidence.

## 2. Helper Pack Integration

- [x] 2.1 Update retry and side-effect packs to include bounded challenge routes.
- [x] 2.2 Update deduplication and cache packs to include bounded challenge routes.
- [x] 2.3 Add or extend tests proving packs reuse the matrix builder and still produce bounded candidate scenarios.
- [x] 2.4 Integrate model-derived challenge synthesis into `run_model_first_checks`.

## 3. Documentation

- [x] 3.1 Update Scenario Sandbox documentation with proactive challenge route guidance.
- [x] 3.2 Update productized helper documentation with the new builder and pack behavior.

## 4. Validation And Sync

- [x] 4.1 Validate the OpenSpec change in strict mode.
- [x] 4.2 Run focused unit tests for scenario matrix and helper packs.
- [x] 4.3 Run practical FlowGuard regression checks and record skipped or background evidence honestly.
- [x] 4.4 Sync editable/local installation and the shadow workspace after validation.
