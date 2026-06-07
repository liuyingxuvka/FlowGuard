## Why
FlowGuard full confidence should mean that model obligations, code surfaces,
and tests are locked together by default. The current Model-Test Alignment route
can compare all three, but code contracts can still be omitted from ordinary
green paths. That leaves room for a model and a test to agree while no code
owner is named, or for a test to pass without proving the code surface that
implements the model.

## What Changes
- Make required model obligations require code contract owners by default.
- Require tests that prove model obligations to also bind the code contracts
  that implement those obligations.
- Treat model-only, code-only, test-only, and mismatched links as blockers or
  scoped gaps, never full green confidence.
- Let transition coverage cells name code contracts and runtime nodes so
  interaction/state transitions can lock to code and tests.
- Update FlowGuard skills, docs, and templates so agents derive and show
  model-code-test bindings before claiming full confidence.

## Scope
- Core Model-Test Alignment checks and public API.
- Transition coverage matrix helpers.
- FlowGuard Codex skills and prompt templates that route model, UI, TestMesh,
  and development-process work.
- OpenSpec specs, docs, and regression tests.

## Non-Goals
- No compatibility switch for model-test-only green.
- No remote publish in this change unless requested separately.
- No broad refactor of unrelated FlowGuard routes.
