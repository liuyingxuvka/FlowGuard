# flowguard-portable-checker Specification

## Purpose
Provide a code-independent reference checker that validates portable models, explores bounded nondeterminism, and emits canonical pass, fail, blocked, or invalid evidence.
## Requirements
### Requirement: Code-Independent Reference Execution
The system SHALL execute a valid portable model without importing project model code and SHALL explore every nondeterministic branch for the explicit input sequence within declared bounds.

#### Scenario: Explicit sequence produces typed traces
- **WHEN** a valid model and finite input sequence are checked
- **THEN** the report contains typed state, input, output, and transition steps for every reachable branch

#### Scenario: Exploration bound is exhausted
- **WHEN** configured state or trace bounds prevent complete exploration
- **THEN** the result is blocked and reports truncation rather than passing

### Requirement: Safety And Temporal Verification
The system SHALL check forbidden-state invariants, universal eventuality, bounded eventuality, terminal progress, and weak-fairness declarations over the finite reachable graph.

#### Scenario: Closed non-target cycle is a counterexample
- **WHEN** a reachable trigger can remain forever in a closed SCC that contains no eventuality target
- **THEN** the checker fails with a cycle trace and the unsatisfied obligation id

#### Scenario: Bounded target is late
- **WHEN** a target is reachable but one target-avoiding path exceeds the declared maximum steps
- **THEN** bounded eventuality fails with the over-bound path

### Requirement: Canonical Checker Reports
The system SHALL emit one canonical report model for Python and CLI use with status, model identity, findings, counterexamples, checked obligations, blockers, skipped checks, residual risk, and claim boundary.

#### Scenario: Human and JSON projections agree
- **WHEN** the same check is rendered as concise text and JSON
- **THEN** both projections retain the same status, finding ids, and model identity

### Requirement: Narrow Portable CLI
The system SHALL expose validate, check, and refinement commands that consume explicit artifact paths and return nonzero for fail, blocked, or invalid outcomes.

#### Scenario: Invalid file fails the command
- **WHEN** `portable-model-validate` receives a structurally invalid artifact
- **THEN** it emits a canonical invalid report and exits nonzero
