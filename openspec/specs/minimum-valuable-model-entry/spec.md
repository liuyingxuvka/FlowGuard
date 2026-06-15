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

### Requirement: Template reuse review is part of model creation
The minimum valuable model path SHALL perform a template reuse review before model generation, preserve the result in the check plan or adoption evidence, and complete with a harvest closure review after new or materially deepened modeling.

#### Scenario: Template was used
- **WHEN** a matching public or local template is used
- **THEN** the model intent or check plan records the used template id

#### Scenario: Template was not used
- **WHEN** no matching template is used
- **THEN** the model intent or check plan records a no-match reason

#### Scenario: Model closes harvest loop
- **WHEN** an AI creates or materially deepens a minimum valuable model
- **THEN** the check plan or adoption evidence records template harvest closure as written, merged, duplicate-linked, or not-harvestable with an accepted reason

#### Scenario: Missing harvest closure blocks formal confidence
- **WHEN** a new or materially deepened formal model has no harvest closure review
- **THEN** FlowGuard MUST block formal model confidence

### Requirement: Self-owned model runners use the formal entry
FlowGuard's current repository-owned `.flowguard` model runner scripts SHALL
use a formal `FlowGuardCheckPlan`-based entry rather than calling
`Explorer(...)` as the script-level evidence path.

#### Scenario: Correct self-model consumes known-bad proof
- **WHEN** a `.flowguard` runner claims a correct self-model supports
  maintenance confidence
- **THEN** the runner MUST build a check plan with Risk Intent, minimum model
  contract, template reuse/no-match evidence, harvest closure, and current
  known-bad proof rows

#### Scenario: Bad self-model is actually caught
- **WHEN** a `.flowguard` runner declares an expected-bad workflow or explicit
  handled-bad label
- **THEN** the runner MUST prove that the bad case failed, was rejected, or was
  otherwise caught before the correct model consumes the proof

#### Scenario: Internal Explorer remains internal
- **WHEN** the formal runner explores finite states
- **THEN** `Explorer` MAY remain the internal engine behind
  `run_model_first_checks(...)`
- **AND** current `.flowguard` runner scripts MUST NOT call `Explorer(...)`
  directly as their public evidence entry

