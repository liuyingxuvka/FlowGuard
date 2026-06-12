# minimum-valuable-model-entry Specification

## Purpose
TBD - created by archiving change raise-minimum-valuable-model-entry. Update Purpose after archive.
## Requirements
### Requirement: Default AI entry uses minimum valuable models
FlowGuard SHALL treat the default AI model-first entry as a minimum valuable
model path rather than a thin happy-path starter.

#### Scenario: Minimum model names the protected error
- **WHEN** an AI creates or materially deepens a default model-first FlowGuard model
- **THEN** the model intent records at least one protected error class or an explicit scoped reason why none applies

#### Scenario: Success-only model is a gap
- **WHEN** a model has no known-bad case and no modeled completion evidence
- **THEN** FlowGuard reports a minimum valuable model confidence gap

### Requirement: Minimum model includes teeth
The minimum valuable model SHALL include the state, side effects, completion
evidence, and known-bad cases required to make the protected error visible.

#### Scenario: Completion requires evidence
- **WHEN** a model claims a workflow can complete
- **THEN** its risk intent or model contract identifies the evidence that proves completion

#### Scenario: Known-bad implementation must fail
- **WHEN** a known-bad case is declared for the model
- **THEN** the model or review must expose the bad case as a failing or rejected path, or keep the claim scoped

### Requirement: Template reuse review is part of model creation
The minimum valuable model path SHALL perform a template reuse review before
model generation and preserve the result in the check plan or adoption evidence.

#### Scenario: Template was used
- **WHEN** a matching public or local template is used
- **THEN** the model intent or check plan records the used template id

#### Scenario: Template was not used
- **WHEN** no matching template is used
- **THEN** the model intent or check plan records a no-match reason
