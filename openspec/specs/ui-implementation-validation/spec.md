# ui-implementation-validation Specification

## Purpose
This capability defines FlowGuard's Ui Implementation Validation behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: UI implementation validation is explicit
The system SHALL provide a UI implementation validation surface that
distinguishes model-complete UI design from running UI completion evidence.

#### Scenario: Implemented UI claim names evidence boundary
- **WHEN** a route claims a UI is implemented, runnable, or complete in the
  running interface
- **THEN** the validation records the source feature model, source UI
  interaction model, source journey coverage, implementation target, evidence
  freshness reference, validation boundaries, and rationale

#### Scenario: Design-only UI can stop before implementation evidence
- **WHEN** a route only claims model, structure, text hierarchy, or design
  contract completion
- **THEN** implementation click-through validation is not required as long as no
  running UI completion claim is made

### Requirement: Functional features align with UI journeys
The system SHALL verify that every user-visible feature contract is represented
by a UI journey, entry point, terminal action, or scoped implementation
blindspot.

#### Scenario: User-visible feature has UI journey coverage
- **WHEN** a feature contract declares `new_project` as user-visible UI
  functionality
- **THEN** the validation finds a matching journey, entry point, terminal action,
  or implementation blindspot for `new_project`

#### Scenario: Functional feature with no UI path is rejected
- **WHEN** a user-visible feature contract has no matching UI journey, event,
  entry point, terminal allowance, or blindspot
- **THEN** the implementation validation reports the feature as not exposed by
  the UI model

### Requirement: UI controls and events have functional ownership
The system SHALL verify that reachable actionable UI controls and modeled UI
events are either owned by a functional feature contract, classified as pure UI
behavior, or scoped to an implementation blindspot.

#### Scenario: UI-only close action is allowed
- **WHEN** a close, cancel, back, expand, collapse, or exit control is modeled
  as pure UI behavior
- **THEN** the implementation validation does not require a product feature
  contract for that control

#### Scenario: Actionable button without feature ownership is rejected
- **WHEN** a reachable actionable control is covered by UI journey coverage but
  has no feature contract, pure UI classification, or implementation blindspot
- **THEN** the implementation validation reports the control as functionally
  unowned

### Requirement: Real UI journey runs cover modeled feature paths
The system SHALL require browser, desktop automation, or manual click-through
evidence for every modeled feature journey when implemented UI completion is
claimed.

#### Scenario: Journey run verifies modeled steps
- **WHEN** a journey run validates the load-existing-project path
- **THEN** each step references modeled controls, events, source states, target
  states, a validation method, a passed result, and an evidence reference

#### Scenario: Missing run for feature journey is rejected
- **WHEN** a feature journey is declared in UI journey coverage
- **AND** no passed implementation run or scoped blindspot covers that feature
- **THEN** the implementation validation reports missing click-through evidence

#### Scenario: Success-only evidence does not cover failure recovery
- **WHEN** a modeled feature journey names failure, recovery, cancel, or exit
  events
- **AND** implementation evidence omits those modeled handling events
- **THEN** the implementation validation reports missing branch evidence

### Requirement: Evidence freshness is enforced
The system SHALL reject implementation evidence that does not identify the UI
model or implementation revision it validates.

#### Scenario: Current model revision is recorded
- **WHEN** validation evidence is recorded after the UI model and journey
  coverage are reviewed
- **THEN** the validation includes a model revision or fingerprint that can be
  compared with the current source model

#### Scenario: Missing or stale evidence revision is rejected
- **WHEN** implementation validation lacks a freshness reference or references a
  different source model revision than the supplied current revision
- **THEN** the validation reports stale or ungrounded evidence

### Requirement: Implementation blindspots are bounded
The system SHALL allow intentionally unverified UI implementation branches only
when they are recorded as blindspots with scope, reason, owner, validation
boundary, and rationale.

#### Scenario: Hard-to-automate branch is deferred with owner
- **WHEN** a desktop file picker branch cannot be automated in the current run
- **THEN** the implementation blindspot names the feature, controls or events,
  reason, owner, validation boundary, and follow-up rationale

#### Scenario: Unscoped implementation blindspot is rejected
- **WHEN** an implementation blindspot has no feature, control, event, reason,
  owner, validation boundary, or rationale
- **THEN** the implementation validation reports the blindspot as incomplete
