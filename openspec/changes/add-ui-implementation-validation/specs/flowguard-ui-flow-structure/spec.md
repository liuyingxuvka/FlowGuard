## MODIFIED Requirements

### Requirement: UI interaction model is created before UI structure derivation
The system SHALL provide a UI interaction model surface that represents the UI
as `UI event x UI state -> Set(UI output x UI state)` before deriving a UI
structure blueprint. For complete app-level UI claims, the system SHALL also
review UI journey coverage between the interaction model and structure
derivation. For implemented or runnable UI completion claims, the system SHALL
review implementation validation after the model, journey coverage, structure,
and text hierarchy evidence exists.

#### Scenario: UI flow model records initial state and transitions
- **WHEN** a UI flow structure route models an interface
- **THEN** the model includes an initial UI state, state nodes, control events,
  transitions, and terminal or recoverable states before structure derivation

#### Scenario: Complete app UI requires journey coverage
- **WHEN** an agent claims that an app-level UI has been modeled completely
- **THEN** the route reviews launch-to-terminal journey coverage before deriving
  UI structure or handing the contract to visual design or implementation

#### Scenario: Implemented UI requires real execution evidence
- **WHEN** an agent claims that the running UI has been implemented completely
- **THEN** the route reviews implementation validation evidence that aligns the
  feature contracts, UI journey coverage, and browser/manual click-through
  records before accepting the completion claim

### Requirement: Visual design and frontend implementation remain separate
The UI flow structure route SHALL NOT replace visual design, Figma execution,
frontend implementation, browser QA, design implementation review, accessibility
testing, or production conformance. Complete app-level UI model claims SHALL
remain bounded to declared journey coverage and residual blindspots. Complete
implemented UI claims SHALL additionally remain bounded to declared
implementation validation evidence and residual implementation blindspots.

#### Scenario: Route hands off after structure contract
- **WHEN** the UI interaction model, app-level journey coverage when required,
  and structure derivation are complete
- **THEN** the resulting UI structure contract can be handed to frontend,
  Figma, or design review workflows without claiming visual or implementation
  completeness

#### Scenario: Journey coverage does not imply production conformance
- **WHEN** UI journey coverage passes for the declared model boundary
- **THEN** the route still reports browser, frontend, accessibility, and
  production conformance as separate downstream validation surfaces

#### Scenario: Implementation validation consumes downstream evidence
- **WHEN** browser automation, desktop automation, or human click-through
  evidence is available for the implemented UI
- **THEN** the route records that evidence in implementation validation instead
  of treating downstream QA prose as proof of model completeness
