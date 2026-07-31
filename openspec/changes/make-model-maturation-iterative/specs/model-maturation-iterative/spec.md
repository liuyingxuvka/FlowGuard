# model-maturation-iterative Specification

## ADDED Requirements

### Requirement: Non-trivial maturation has an independent coverage universe

The maturation owner SHALL require a task purpose, independent coverage-universe fingerprint, and required native probes before declaring a non-trivial model current.

#### Scenario: Empty signals cannot bypass missing coverage
- **GIVEN** a non-trivial plan has no route signals
- **AND** its coverage universe or required probes are missing
- **WHEN** maturation is reviewed
- **THEN** the result is blocked with a concrete missing-coverage action

### Requirement: Addressable gaps require another iteration

An unresolved in-scope signal classified as `model_edit` or `evidence_acquisition` SHALL produce required actions and `next_iteration_required=true`; a scoped claim SHALL NOT close it.

#### Scenario: Action list without candidate is not terminal
- **GIVEN** an in-scope state, prediction, counterexample, boundary, or evidence gap remains
- **WHEN** the caller only returns prose recommendations
- **THEN** the result remains non-terminal and records the open signal

### Requirement: Every iteration is fingerprinted and must progress

Each iteration SHALL bind a base model, candidate model, input signals, resolved/introduced signals, current native receipts, and a progress fingerprint.

#### Scenario: No-progress iteration
- **GIVEN** two consecutive iterations have the same model and open-signal fingerprints
- **WHEN** maturation is reviewed
- **THEN** it returns `progress_stalled` and does not report success

### Requirement: Terminal reasons are explicit

The report SHALL use `model_closed_for_task` only when all required probes are current and no important addressable signals remain. External input, justified exclusion, stall, and iteration-limit outcomes SHALL remain visible and non-success.

#### Scenario: Exact external blocker
- **GIVEN** a required observation cannot be obtained with current local tools
- **WHEN** the iteration is reviewed
- **THEN** the report names the required input, owner boundary, and affected claim scope as `external_input_required`

### Requirement: Self-report is not evidence

The structured maturation contract SHALL contain no understanding-level or self-reported-understanding authority, and such prose SHALL not resolve a signal.

#### Scenario: AI says it understands
- **GIVEN** an answer contains a self-assessment but no changed model or current native receipt
- **WHEN** the closure is reviewed
- **THEN** the signal remains open or blocked
