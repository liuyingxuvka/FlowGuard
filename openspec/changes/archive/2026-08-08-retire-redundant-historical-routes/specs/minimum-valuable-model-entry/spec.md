## ADDED Requirements

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

## REMOVED Requirements

### Requirement: Template reuse review is part of model creation
**Reason**: Template work is optional reuse governance, not a universal minimum-DNA condition.
**Migration**: Use the conditional template-library route only when triggered.

### Requirement: Self-owned model runners use the formal entry
**Reason**: Replaced by the canonical formal-evidence requirement that removes unconditional template gates while preserving executable proof.
**Migration**: Keep the formal check plan and known-bad proof; drop untriggered template search and harvest fields.
