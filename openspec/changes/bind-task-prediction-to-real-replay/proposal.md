## Why

FlowGuard can already explore an abstract model and replay an expected trace
against production code, but production-confidence callers can still record a
passing conformance status without supplying the replay that proves it. The
same gap leaves predictions implicit and model repair dependent on ad hoc file
history instead of a task-local candidate/rollback record.

## What Changes

- **BREAKING**: reject `conformance_status=pass` as production conformance
  evidence unless a current `ConformanceReport` or equivalent replay report is
  supplied.
- Keep production adapters independent from model outcomes; the job-matching
  example will receive only real inputs and derive its own output.
- Make strict runtime-path comparison account for the complete ordered
  observation sequence, including repeated nodes, terminal identity, state
  writes, and side effects.
- Add a small task-local prediction snapshot that freezes the model identity,
  expected trace, falsifier, and observation boundary before replay.
- Add a task-local model revision record that preserves model v1, tracks one
  candidate v2, and supports explicit accept, reject, and rollback decisions
  without modifying FlowGuard's core rules.
- Add focused tests and update the model-first conformance guidance.

## Capabilities

### New Capabilities

- `task-local-prediction-revision`: Freezes a task-specific prediction before
  observation and governs candidate model acceptance, rejection, and rollback.

### Modified Capabilities

- `model-first-function-flow`: Production conformance claims require a current
  replay report rather than a caller-authored passing status.
- `runtime-path-evidence`: Strict path review compares the complete ordered
  observed path, including repeats and terminal/write/side-effect boundaries.

## Impact

- Affected package modules: `flowguard/conformance.py`,
  `flowguard/runner.py`, `flowguard/runtime_path.py`, and one new task-local
  prediction/revision module.
- Affected example: `examples/job_matching/`.
- Affected guidance: the model-first conformance/adoption protocol.
- Existing callers that use status-only conformance as a pass must provide a
  real report or accept a blocked/scoped result.
- No user-level installation, compatibility route, automatic Guard
  self-modification, package release, Git commit, or Git push is included.
