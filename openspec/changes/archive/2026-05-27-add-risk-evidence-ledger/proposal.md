## Why

FlowGuard adoption records often show model checks and tests passing while later
work discovers that the real confidence boundary was narrower than the final
claim. The missing contract is a plain, explicit ledger that connects each
modeled risk to its model owner, code contract, test or replay evidence,
freshness state, and remaining gap before a run can claim full confidence.

## What Changes

- Add a risk evidence ledger to FlowGuard adoption and model-first completion
  guidance.
- Add public helper data structures and review logic for model risk, code
  surface, test/replay evidence, freshness, and disposition rows.
- Add generated template coverage so future projects get the ledger without
  hand-authoring it from scratch.
- Update Model-Test Alignment, Model-Miss Review, TestMesh, ModelMesh,
  DevelopmentProcessFlow, Existing Model Preflight, and the Skill Kernel so
  each route knows which part of the ledger it owns.
- Update documentation, README/API surface, adoption logs, and release notes.
- Keep schema version `1.0` and Python standard-library-only runtime.

## Capabilities

### New Capabilities
- `risk-evidence-ledger`: Defines the risk-to-model-to-code-to-test evidence
  ledger, confidence decisions, stale/skipped/out-of-scope handling, and route
  ownership handoffs.

### Modified Capabilities
- None.

## Impact

- Affected package code: `flowguard`, public exports, CLI templates, and tests.
- Affected guidance: installed/repository FlowGuard skills, adoption protocol,
  model-test alignment, model-miss review, TestMesh, ModelMesh, and
  DevelopmentProcessFlow references.
- Affected release surfaces: `README.md`, `CHANGELOG.md`, `docs/`, local
  editable install, shadow workspace sync, git tag, and GitHub Release.
