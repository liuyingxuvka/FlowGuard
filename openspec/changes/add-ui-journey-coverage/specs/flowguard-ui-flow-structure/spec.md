## MODIFIED Requirements

### Requirement: UI interaction model is created before UI structure derivation
The system SHALL provide a UI interaction model surface that represents the UI
as `UI event x UI state -> Set(UI output x UI state)` before deriving a UI
structure blueprint. For complete app-level UI claims, the system SHALL also
review UI journey coverage between the interaction model and structure
derivation.

#### Scenario: UI flow model records initial state and transitions
- **WHEN** a UI flow structure route models an interface
- **THEN** the model includes an initial UI state, state nodes, control events,
  transitions, and terminal or recoverable states before structure derivation

#### Scenario: UI model is not replaced by layout prose
- **WHEN** an agent produces only a list of screens or layout zones without UI
  state transitions
- **THEN** the UI interaction model review reports the missing modeled flow

#### Scenario: Complete app UI requires journey coverage
- **WHEN** an agent claims that an app-level UI has been modeled completely
- **THEN** the route reviews launch-to-terminal journey coverage before deriving
  UI structure or handing the contract to visual design or implementation

### Requirement: Visual design and frontend implementation remain separate
The UI flow structure route SHALL NOT replace visual design, Figma execution,
frontend implementation, browser QA, design implementation review, accessibility
testing, or production conformance. Complete app-level UI claims SHALL remain
bounded to the declared journey coverage and residual blindspots.

#### Scenario: Route hands off after structure contract
- **WHEN** the UI interaction model, app-level journey coverage when required,
  and structure derivation are complete
- **THEN** the resulting UI structure contract can be handed to frontend,
  Figma, or design review workflows without claiming visual completeness

#### Scenario: Journey coverage does not imply production conformance
- **WHEN** UI journey coverage passes for the declared model boundary
- **THEN** the route still reports browser, frontend, accessibility, and
  production conformance as separate downstream validation surfaces
