# ui-journey-coverage Specification

## Purpose
This capability defines FlowGuard's Ui Journey Coverage behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: App-level UI journey coverage is explicit
The system SHALL provide a UI journey coverage surface that distinguishes
component-local UI interaction coherence from complete app-level UI coverage.

#### Scenario: Complete app UI names launch and feature inventory
- **WHEN** a UI route claims complete app-level UI modeling
- **THEN** the coverage records the launch state, entry points, declared feature
  journeys, required terminal states, validation boundaries, and rationale

#### Scenario: Local UI model remains allowed
- **WHEN** a UI model is explicitly scoped to a local component or single
  workflow slice
- **THEN** the existing interaction, structure, and text reviews can run without
  app-level journey coverage as long as no complete-app claim is made

### Requirement: Entry points are modeled from launch
The system SHALL verify that every declared app entry point references modeled
UI controls, events, and launch-available source states.

#### Scenario: New project entry is covered
- **WHEN** a journey coverage declares `new_project` as an entry point
- **THEN** the entry references a registered control, registered event, and a
  source state reachable from the launch state

#### Scenario: Missing load existing project entry is rejected
- **WHEN** a required feature journey depends on loading an existing project but
  no load entry point is declared
- **THEN** the journey coverage review reports the missing entry-point coverage

### Requirement: Feature journeys have launch-to-terminal paths
The system SHALL verify that each declared feature journey has a modeled path
from launch through required states and events to success, cancel, recovery, or
terminal outcomes.

#### Scenario: Feature has success terminal
- **WHEN** a feature journey is declared
- **THEN** the journey names at least one success terminal state that is
  registered and reachable from launch

#### Scenario: Unreachable state is rejected
- **WHEN** a feature journey names a required state that cannot be reached from
  the launch state
- **THEN** the journey coverage review reports the unreachable path state

#### Scenario: Unknown event is rejected
- **WHEN** a feature journey names an event that is not in the source
  interaction model
- **THEN** the journey coverage review reports the unknown path event

### Requirement: Reachable visible controls and events are accounted for
The system SHALL verify that complete app-level UI coverage accounts for every
reachable visible or enabled actionable control and every reachable modeled
event, either inside a feature journey, entry point, terminal allowance, or
scoped residual blindspot.

#### Scenario: Enabled button with no event is rejected
- **WHEN** a reachable UI state exposes an actionable enabled control
- **AND** that control has no modeled event for that state
- **AND** the control is not scoped to a residual blindspot
- **THEN** the journey coverage review reports the silent-button branch

#### Scenario: Reachable event outside all journeys is rejected
- **WHEN** a reachable modeled UI transition exists
- **AND** its event is not part of an entry point, feature journey, terminal
  allowance, or residual blindspot
- **THEN** the journey coverage review reports the uncovered event branch

#### Scenario: Residual blindspot names its branch scope
- **WHEN** a visible branch is intentionally outside the current journey
  coverage boundary
- **THEN** the blindspot names the feature, control, or event scope that is
  deferred, plus its owner and downstream validation boundary

### Requirement: Failure, cancel, recovery, and exit paths are accounted for
The system SHALL require recoverable failures and app exits in declared
journeys to have modeled recovery, cancel, close, retry, or terminal handling.

#### Scenario: Recoverable load failure has recovery
- **WHEN** a load-existing-project journey can enter a recoverable failure state
- **THEN** the journey names recovery, cancel, or terminal handling for that
  failure state

#### Scenario: Failure without recovery decision is rejected
- **WHEN** a feature journey names a failure state but provides no recovery,
  cancel, exit, or terminal decision
- **THEN** the journey coverage review reports missing failure handling

### Requirement: Terminal states are not silently forward-moving
The system SHALL reject terminal states that expose outgoing forward-only
transitions unless the transition is explicitly classified as restart, export,
close, recovery, cancel, or exit behavior.

#### Scenario: Export from result terminal is allowed
- **WHEN** a result-ready terminal state has an outgoing export transition
- **THEN** journey coverage can allow the transition by recording the terminal
  action purpose

#### Scenario: Forward run from terminal is rejected
- **WHEN** a terminal state has an outgoing run or progression transition with
  no allowed terminal action purpose
- **THEN** the journey coverage review reports the terminal forward-action
  hazard

### Requirement: Residual UI blindspots are visible
The system SHALL allow intentionally out-of-scope UI branches only when they
are recorded as residual blindspots with rationale and validation boundaries.

#### Scenario: Out-of-scope branch has validation boundary
- **WHEN** a UI branch is intentionally outside the journey coverage boundary
- **THEN** the blindspot records the feature, reason, owner or downstream check,
  and validation boundary

#### Scenario: Blindspot without validation is rejected
- **WHEN** a residual blindspot has no validation boundary or rationale
- **THEN** the journey coverage review reports the blindspot as incomplete
