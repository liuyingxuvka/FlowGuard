# flowguard-closure-contract Specification

## Purpose
TBD - created by archiving change require-flowguard-closure-contract. Update Purpose after archive.
## Requirements
### Requirement: Complete FlowGuard Use Requires Closure Contract

FlowGuard SHALL define complete use as a mandatory closure contract rather than
an optional mode.

#### Scenario: Full-confidence claim has closure evidence

- **GIVEN** a task claims done, release, publish, or production confidence after
  FlowGuard use
- **AND** the claim crosses model, code, test, process, UI, mesh, adapter, or
  evidence boundaries
- **WHEN** FlowGuard guidance reviews the claim
- **THEN** the claim requires current closure evidence for plan/risk intake,
  model ownership or model creation, model-test/code alignment when code or
  tests are in scope, same-class model-miss evidence when a miss was repaired,
  mesh or boundary proof when parent/child evidence is in scope, evidence
  freshness, Risk Evidence Ledger, and typed claim-chain review

#### Scenario: Partial evidence cannot be called complete FlowGuard use

- **GIVEN** a model or test run passed
- **AND** a required closure gate is missing, stale, skipped, progress-only, or
  explicitly scoped out
- **WHEN** the result is reported
- **THEN** the report marks the work as partial/scoped FlowGuard evidence
  instead of saying FlowGuard completion or full confidence

### Requirement: Thin Entry Path Does Not Replace Closure

The lightweight model-first path SHALL remain an entry path and SHALL NOT be
described as sufficient for broad completion claims by itself.

#### Scenario: Small local risk stays small

- **GIVEN** a small task only claims a bounded model-level decision
- **WHEN** the thin path runs one fit-for-risk model and evidence remains
  inside that local claim
- **THEN** the report may stay bounded without invoking unrelated framework
  suites

#### Scenario: Broad claim escalates

- **GIVEN** a task starts with the thin path
- **AND** the final statement would claim real code, tests, release readiness,
  parent/child model confidence, or production confidence
- **WHEN** the claim is made
- **THEN** the required closure routes must be consumed before full confidence
  is allowed

### Requirement: Model Misses Upgrade The Closure Contract

FlowGuard SHALL treat every post-green bug as evidence that the previous
closure contract was too narrow until the miss is backpropagated.

#### Scenario: Bug escapes after green evidence

- **GIVEN** runtime, test, replay, log, or manual evidence fails after an
  earlier FlowGuard pass
- **WHEN** FlowGuard reviews the failure
- **THEN** Model-Miss Review records the observed failure and at least one
  same-class generalized bad case when practical, Model-Test Alignment binds
  current observed-regression and same-class test evidence, and the final Risk
  Evidence Ledger/claim-chain boundary marks prior evidence stale or
  overclaimed until the repaired obligation is current

### Requirement: Installed And Source Surfaces Stay Synchronized

FlowGuard SHALL treat public skill-guidance changes as incomplete until source,
installed, editable-install, shadow workspace, and version surfaces are
synchronized or explicitly reported as scoped.

#### Scenario: Skill contract changes

- **GIVEN** a change modifies FlowGuard skill guidance or public documentation
- **WHEN** the change is completed locally
- **THEN** source files, installed Codex skill copies, editable package import,
  shadow workspace import, and visible version metadata are checked for
  alignment before the final completion claim
