# minimum-valuable-model-entry Specification

## Purpose
Define FlowGuard's default AI model-first entry as a minimum valuable formal
model with protected error classes, state, side effects, completion evidence,
template reuse or no-match rationale, and executable known-bad proof.
## Requirements
### Requirement: Default AI entry uses minimum valuable models
FlowGuard SHALL treat the default AI model-first entry as a single formal minimum valuable model path rather than a thin happy-path starter or direct `Explorer(...)` route.

#### Scenario: Minimum model names the protected error
- **WHEN** an AI creates or materially deepens a default model-first FlowGuard model
- **THEN** the model intent records at least one protected error class

#### Scenario: Success-only model is blocked
- **WHEN** a model has no known-bad case, no modeled completion evidence, or no known-bad proof
- **THEN** FlowGuard blocks formal model confidence

#### Scenario: Direct Explorer is not a formal entry
- **WHEN** a caller uses direct `Explorer(...)` without the formal minimum valuable model path
- **THEN** FlowGuard MUST NOT treat that run as satisfying the default AI entry

### Requirement: Minimum model includes teeth
The minimum valuable model SHALL include the state, side effects, completion evidence, known-bad cases, and executable known-bad proof required to make the protected error visible.

#### Scenario: Completion requires evidence
- **WHEN** a model claims a workflow can complete
- **THEN** its risk intent or model contract identifies the evidence that proves completion

#### Scenario: Known-bad implementation must fail
- **WHEN** a known-bad case is declared for the model
- **THEN** the model or review MUST expose the bad case as a failing or rejected path with current structured proof

#### Scenario: Name-only known-bad case is insufficient
- **WHEN** a known-bad case is listed but no executable proof shows it is caught
- **THEN** FlowGuard MUST block formal model confidence

### Requirement: Minimum formal entry is complete without template search
The minimum valuable model entry SHALL require protected errors, explicit state and effects, completion evidence, executable known-bad proof, and current model/code/test bindings. It SHALL NOT require template search, no-match rationale, or harvest closure unless a separate template-reuse/publication trigger applies.

#### Scenario: Ordinary minimum model is complete
- **WHEN** the model satisfies its DNA contract and executable known-bad proof without a template-reuse trigger
- **THEN** FlowGuard may grant the model's bounded formal confidence without template search or harvest evidence

#### Scenario: FlowGuard's own minimum-entry model still requires template work
- **WHEN** the current `minimum_valuable_model_entry` self model rejects an otherwise complete ordinary model because template search, no-match, or harvest was not run
- **THEN** self-authority qualification MUST fail because the executable DNA contradicts the current minimum-entry contract
- **AND** the self model SHALL be repaired directly rather than hidden behind a prompt-only exception

### Requirement: Self-owned model runners use canonical formal evidence
FlowGuard-owned model runners SHALL use the formal check-plan entry with risk intent, the minimum model contract, current known-bad proof, and the exact route-specific evidence required by the model.

#### Scenario: Correct self-model consumes known-bad proof
- **WHEN** a self-owned runner claims maintenance confidence
- **THEN** it MUST prove the declared bad cases are rejected and consume current route-specific evidence
- **AND** template evidence is required only when the runner declares a separate template-reuse/publication obligation

#### Scenario: Internal finite explorer is used
- **WHEN** the formal runner explores finite states
- **THEN** the finite explorer may remain an internal engine and MUST NOT become an alternate public evidence entry
