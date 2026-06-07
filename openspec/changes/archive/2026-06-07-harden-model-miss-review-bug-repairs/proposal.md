## Why

Ordinary bug-fix requests can still lead agents to patch the visible failure
and stop before the existing FlowGuard model-miss, model-code-test, freshness,
compatibility, and final-closure evidence chain is complete. The existing
routes already own those responsibilities, but the Model-Miss Review entry and
handoffs are too narrowly framed around "after FlowGuard passed" failures.

## What Changes

- Broaden the existing Model-Miss Review route so non-trivial bug repairs enter
  the same model-miss discipline when a real failure suggests a missed failure
  class.
- Add explicit root-cause backpropagation guidance to Model-Miss Review by
  reusing existing Plan Intake false-negative fields rather than adding a new
  root-cause route.
- Make Model-Miss Review hand off bug repairs to existing Model-Test Alignment
  for model obligation, owner code contract, and observed/same-class test
  binding before broad closure.
- Make old paths, fallbacks, aliases, and compatibility adapters visible in
  bug repair closure through existing Architecture Reduction classification and
  LegacyPathDisposition evidence.
- Update templates, skill docs, OpenSpec specs, and focused tests so the bug
  repair path is protected without introducing a new standalone bug-fix skill
  or workflow.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `post-runtime-model-miss-review`: broaden Model-Miss Review to cover
  non-trivial bug repairs where a model, test, or confidence claim may have
  missed a failure class.
- `model-miss-test-evidence-closure`: require bug repair closure to preserve
  observed-regression and same-class evidence and bind that evidence to the
  repaired model obligation and owner code contract.
- `model-first-function-flow`: route ordinary bug repairs through existing
  model ownership preflight and Model-Miss Review instead of treating them as
  direct implementation-only work.
- `development-process-flow`: keep bug repair evidence fresh when model,
  code-contract, test, compatibility, or legacy-path evidence changes during
  repair.
- `flowguard-closure-contract`: require final bug repair confidence to consume
  current model-miss, model-code-test, freshness, compatibility/legacy, and
  risk-ledger evidence.

## Impact

- Affected skills: `flowguard-model-miss-review`,
  `model-first-function-flow`, and related installed Codex skill copies.
- Affected docs/templates: Model-Miss Review protocol and template notes,
  Model-Test Alignment docs, DevelopmentProcessFlow docs, Closure Contract
  docs, Risk Evidence Ledger docs, and AGENTS snippet guidance.
- Affected tests: skill-doc assertions, public template assertions,
  Model-Test Alignment bug-repair closure tests, Plan Intake false-negative
  tests, Risk Evidence Ledger/closure tests, and targeted OpenSpec validation.
- No new runtime dependency and no new standalone FlowGuard route.
