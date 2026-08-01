# model-maturation-iterative Specification

## ADDED Requirements

### Requirement: Non-trivial maturation has an independent coverage universe

The maturation owner SHALL require a task purpose, a coverage-universe id,
fingerprint and producer identity independent of the candidate model, and an
exact required-native-probe inventory before accepting a non-trivial plan.

#### Scenario: Empty signals cannot bypass missing coverage
- **GIVEN** a non-trivial plan has no route signals
- **AND** its coverage universe or required probes are missing
- **WHEN** maturation is reviewed
- **THEN** the result is blocked with a concrete missing-coverage action

#### Scenario: Caller cannot shrink its own coverage universe
- **GIVEN** a candidate omits an item from the independently bound current coverage universe
- **WHEN** maturation is reviewed
- **THEN** the result remains blocked even if every caller-supplied signal is marked resolved

### Requirement: Addressable gaps require another iteration

An unresolved in-scope signal classified as `model_edit` or `evidence_acquisition` SHALL produce required actions and `next_iteration_required=true`; a scoped claim SHALL NOT close it.

#### Scenario: Action list without candidate is not terminal
- **GIVEN** an in-scope state, prediction, counterexample, boundary, or evidence gap remains
- **WHEN** the caller only returns prose recommendations
- **THEN** the result remains non-terminal and records the open signal

#### Scenario: Caller resolution boolean is not evidence
- **GIVEN** a required signal is marked resolved but has no current receipt for the exact task, probe, candidate, and coverage universe
- **WHEN** maturation is reviewed
- **THEN** the signal remains open or the input is rejected

### Requirement: Every iteration is fingerprinted and must progress

Each iteration SHALL bind a base model, candidate model, predecessor iteration,
input/resolved/persisted/introduced signals, current native receipts, and a
progress fingerprint. A signal may disappear only with a current resolution
receipt. Progress requires a verified candidate or discriminating-evidence
advance; changing names or deleting gaps is not progress.

#### Scenario: No-progress iteration
- **GIVEN** two consecutive iterations have the same model and open-signal fingerprints
- **WHEN** maturation is reviewed
- **THEN** it returns `progress_stalled` and does not report success

#### Scenario: Oscillating iteration
- **GIVEN** the session returns to an earlier candidate and open-gap fingerprint without new discriminating evidence
- **WHEN** maturation is reviewed
- **THEN** it returns `progress_stalled` and preserves the oscillation evidence

### Requirement: Terminal reasons are explicit

The report SHALL use `model_closed_for_task` only when every required probe has
one current terminal native receipt for the exact candidate and no important
addressable signal remains. `upgrade_required` is non-terminal. External input,
justified exclusion, stall, and iteration-limit outcomes SHALL remain visible
and non-success.

#### Scenario: Exact external blocker
- **GIVEN** a required observation cannot be obtained with current local tools
- **WHEN** the iteration is reviewed
- **THEN** the report names the required input, owner boundary, and affected claim scope as `external_input_required`

#### Scenario: Multi-iteration session reaches the real terminal
- **GIVEN** an earlier iteration requires a model upgrade and a later linked candidate closes every required probe
- **WHEN** the session is reviewed
- **THEN** both iterations are preserved and only the later report is terminal

### Requirement: Self-report is not evidence

The structured maturation contract SHALL contain no understanding-level or self-reported-understanding authority, and such prose SHALL not resolve a signal.

#### Scenario: AI says it understands
- **GIVEN** an answer contains a self-assessment but no changed model or current native receipt
- **WHEN** the closure is reviewed
- **THEN** the signal remains open or blocked

### Requirement: Current schema replaces former success paths

The runtime and CLI SHALL accept one explicit current schema version and SHALL
reject former shallow or legacy payload shapes without an alias, fallback,
dual reader, or scoped-success route.

#### Scenario: Former empty plan is rejected
- **GIVEN** a former payload omits task purpose, coverage binding, required probes, and current receipts
- **WHEN** the runtime or CLI reads it
- **THEN** it fails with a current-schema mismatch and produces no success claim

### Requirement: Model, test, contract, and installation evidence stay aligned

The observed FlowGuard authority and maintained FlowGuard skill contract SHALL
include the maturation runtime, CLI, prompts, required scenarios, tests, and
target-owned terminal closure check before release or installation is claimed
current.

#### Scenario: Version-only authority refresh cannot close the change
- **GIVEN** a model snapshot names the new version but omits the changed runtime, tests, prompts, or target closure check
- **WHEN** release readiness is reviewed
- **THEN** the change remains blocked as evidence-overclaimed
