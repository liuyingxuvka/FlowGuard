# flowguard-ui-flow-structure Specification

## Purpose
TBD - created by archiving change add-ui-flow-structure. Update Purpose after archive.
## Requirements
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

### Requirement: UI controls and events are mapped to model behavior
The system SHALL map controls, events, and button effects to UI state
transitions and FlowGuard FunctionBlocks or equivalent modeled UI actions.

#### Scenario: Control has modeled effect
- **WHEN** a button, menu item, or input action is included in the UI model
- **THEN** the model identifies the event, owning control, source state,
  resulting state, visible output, and modeled action or FunctionBlock

#### Scenario: Unmapped control is rejected
- **WHEN** a visible control has no modeled event or transition
- **THEN** the UI interaction model review reports the control as unmodeled

### Requirement: UI information and control redundancy is reviewed
The system SHALL represent semantic information displays and control function
keys so redundant UI content or overlapping same-level controls can be checked
instead of accepted as arbitrary layout.

#### Scenario: Duplicate same-state information requires rationale
- **WHEN** one UI state shows two display elements with the same semantic
  information key
- **THEN** the UI interaction model review reports duplicate information unless
  the repetition has an explicit redundancy rationale or duplicate group

#### Scenario: Duplicate same-level control function requires rationale
- **WHEN** one UI state exposes multiple controls at the same hierarchy level
  for the same modeled function
- **THEN** the UI interaction model review reports overlapping controls unless
  the repetition has an explicit redundancy rationale or duplicate group

#### Scenario: Region repeats information without reason
- **WHEN** a structure derivation places multiple displays with the same
  semantic information key in one region
- **THEN** the structure review reports duplicate regional information unless
  the repetition is explicitly justified

### Requirement: State availability is explicit
The system SHALL represent which controls are visible, enabled, disabled, or
hidden, and which semantic information displays are visible, in each relevant
UI state.

#### Scenario: Stage-dependent action is represented
- **WHEN** an action is available only after another flow phase completes
- **THEN** the state availability matrix records the dependency and the states
  where the action is enabled or unavailable

#### Scenario: Terminal state does not expose forward-only action
- **WHEN** a UI state is terminal
- **THEN** the review reports a finding if a forward-only action remains
  enabled without an explicit restart, export, close, or recovery purpose

### Requirement: Failure and recovery paths are modeled
The system SHALL identify failure states and provide modeled recovery,
rollback, retry, cancel, or diagnostic actions when recovery is possible.

#### Scenario: Failure state has recovery action
- **WHEN** a transition can enter a recoverable failure state
- **THEN** the UI model includes at least one recovery action or explains why
  the state is terminal

#### Scenario: Missing recovery is rejected
- **WHEN** a recoverable failure state has no recovery, diagnostic, or terminal
  explanation
- **THEN** the UI interaction model review reports missing failure recovery

### Requirement: UI structure is derived from the UI interaction model
The system SHALL derive UI parent/child nodes, persistent controls, contextual
controls, navigation, regions, panels, and control tiers from the reviewed UI
interaction model.

#### Scenario: Parent and child nodes are derived
- **WHEN** the UI flow contains state groups or dependency chains
- **THEN** the structure derivation identifies parent nodes, child nodes,
  covered states, covered controls, and rationale

#### Scenario: Global control remains stable
- **WHEN** a control is marked persistent or global in the model
- **THEN** the structure derivation places it in a stable global region rather
  than a phase-only child area

#### Scenario: Contextual control is scoped to its phase
- **WHEN** a control depends on a particular state or parent flow
- **THEN** the structure derivation assigns it to the matching contextual
  region, panel, or child node

### Requirement: UI hierarchy recommendations are explicit
The system SHALL convert modeled parent/child UI topology into explicit
hierarchy and placement recommendations such as first-level persistent menus,
second-level contextual regions, third-level local controls, modal or drawer
overlays, stable toolbar positions, and layout areas that must not drift across
states.

#### Scenario: Menu levels are derived from function topology
- **WHEN** a modeled function is global, parent-level, child-level, or local to
  a sub-state
- **THEN** the structure derivation recommends the matching menu or control
  level and records the reason

#### Scenario: Layout positions remain stable across states
- **WHEN** a control or region is persistent across multiple UI states
- **THEN** the structure derivation marks its placement as stable so later
  visual design does not move it arbitrarily between screens

#### Scenario: Overlay hierarchy is derived from blocking flow
- **WHEN** a modeled action temporarily blocks or scopes the parent flow
- **THEN** the structure derivation identifies whether the interaction belongs
  in a modal, drawer, inspector, popover, or inline child region

### Requirement: UI flow structure is a standalone Codex satellite skill
The repository SHALL provide a directly invokable
`flowguard-ui-flow-structure` Codex skill while preserving
`model-first-function-flow` as the kernel for applicability, hard gates, and
ambiguous routing.

#### Scenario: Direct UI model request invokes satellite
- **WHEN** a user asks Codex to model UI button flows, UI state transitions, or
  model-derived UI structure from a workflow
- **THEN** Codex can invoke `flowguard-ui-flow-structure` directly

#### Scenario: Ambiguous UI work returns to kernel
- **WHEN** a UI request is visual-only, trivial, or unclear about behavior and
  state impact
- **THEN** the satellite routes the task back to `model-first-function-flow` or
  skips with a reason according to the kernel guidance

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
