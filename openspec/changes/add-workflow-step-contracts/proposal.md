## Why

FlowGuard can already model a workflow, but several real defects still come from code taking a legal-looking shortcut: a required step is skipped, a later claim is made before its prerequisite evidence exists, or older evidence is reused after a later step made it stale. The model needs a first-class way to say "this step is not just a label, it creates or invalidates a receipt that later steps and claims must respect."

## What Changes

- Add first-class workflow step contracts that define each important step's prerequisites, produced receipts, invalidated receipts, completion labels, required claim labels, skip policy, and optional code/test bindings.
- Compile step contracts into ordinary FlowGuard invariants so Explorer and `run_model_first_checks(...)` can catch skipped steps, wrong order, premature claims, and stale receipts.
- Add a structured review report for concrete traces so examples, tests, and external adopters can explain the exact skipped, early, or stale step.
- Add helper projections from step contracts into DevelopmentProcessFlow validation requirements and Model-Test Alignment obligations.
- Add conformance replay rules that compare expected and observed step-contract metadata when replaying abstract traces against production adapters.
- Update templates, docs, exports, and tests so the new path is discoverable without breaking existing workflows.

## Capabilities

### New Capabilities
- `workflow-step-contracts`: Declare and validate ordered workflow step obligations using receipts, invalidation, skip policy, claim gates, trace review, runner integration, and replay metadata checks.

### Modified Capabilities
- `development-process-flow`: Allow workflow step contracts to generate process validation requirements so staged development claims can reuse the same step/receipt boundary.
- `model-test-alignment`: Allow workflow step contracts to generate model obligations so tests can be checked against required workflow steps.

## Impact

- Affected package modules: `flowguard.plan`, `flowguard.runner`, `flowguard.conformance`, `flowguard.model_test_alignment`, `flowguard.development_process_flow`, `flowguard.templates`, `flowguard.__init__`, and a new `flowguard.step_contracts` helper module.
- Affected docs/templates/tests: README command list, docs for workflow step contracts, public template tests, runner tests, conformance tests, DevelopmentProcessFlow tests, and Model-Test Alignment tests.
- No external dependencies are required. Existing APIs remain compatible; plans without step contracts behave as they do today.
