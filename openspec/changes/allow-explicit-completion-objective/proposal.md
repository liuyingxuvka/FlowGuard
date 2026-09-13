## Why

FlowGuard correctly prevents a single completion objective from regaining its
finite producer budget after an initial attempt and one typed repair. However,
the current public full/readiness routes do not provide a verifiable way to
start a genuinely new objective after that bounded cycle is exhausted. The
result is a correct no-loop block that cannot progress to the next independent
work objective, even when that objective has its own reviewed OpenSpec scope.

## What Changes

- Add an explicit completion-objective input that is derived from a named,
  current OpenSpec change's immutable planning artifacts rather than from a
  caller-supplied hash, timestamp, output directory, or random nonce.
- Bind the completion epoch and finite cycle identity to that derived
  objective fingerprint while preserving the existing one-initial-attempt plus
  one-typed-repair limit for each objective.
- Forward the objective option through the public readiness command and the
  formal full-validation command, and require both commands to freeze the same
  objective identity.
- Reject unknown, unsafe, empty, symlinked, or artifact-incomplete objective
  references before readiness or producer admission.
- Keep the existing repair-scope option separate: a repair link repairs the
  predecessor objective and must never silently create a new objective.
- Add regression coverage proving that same-objective reuse remains zero-
  producer, a third attempt remains blocked, and a distinct reviewed
  objective receives a new finite cycle without changing the old ledger.
- Make completion evidence execution-aware: each full-validation invocation
  uses one bounded run-scoped model-owner receipt store, while historical
  receipts remain retained but are not rescanned as current input.  A current
  reuse pass must validate the suite identity once and then validate each
  selected receipt, so a bounded run cannot become a freshness loop caused by
  quadratic historical I/O.
- Treat work-in-progress evidence as controlled workspace material.  It is
  excluded from distributable/authoritative projections, but it remains
  available until the run reaches a terminal publish/cleanup decision.

## Capabilities

### New Capabilities

- `explicit-completion-objective`: Derive and verify a stable completion
  objective identity from a named OpenSpec change so independent work can
  begin a fresh bounded cycle without weakening same-objective no-retry
  guarantees.

### Modified Capabilities

- `flowguard-self-maintenance-mesh`: Require full/readiness planners to bind
  their finite cycle to the explicit reviewed objective identity when one is
  supplied, while retaining the existing deterministic default for legacy
  callers and the existing repair semantics.

## Impact

- FlowGuard completion epoch planning and persistent cycle identity.
- The canonical `completion-readiness` command and
  `check_flowguard_skill_suite.py --scope full` command surface.
- New read-only objective-artifact fingerprinting under `flowguard/`.
- Completion epoch, readiness, CLI, and integration tests.
- OpenSpec planning artifacts and validation only; no automatic source,
  model-authority, receipt, release, Git, or external-provider writes are
  introduced by objective resolution.
