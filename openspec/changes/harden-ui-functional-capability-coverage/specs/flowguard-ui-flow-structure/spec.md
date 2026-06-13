## ADDED Requirements

### Requirement: UI Flow Structure includes functional capability coverage in the existing route
FlowGuard UI Flow Structure SHALL account functional capability coverage inside the existing UI route before broad model, human-operability, implementation, or completion claims.

#### Scenario: Capability coverage precedes task and implementation claims
- **WHEN** a UI task claims that user-visible functionality is complete, runnable, release-ready, or human-operable
- **THEN** UI Flow Structure requires a current capability inventory and coverage review that feeds existing feature contracts, task coverage, journeys, controls/events, functional chains, output contracts, and implementation evidence

#### Scenario: Existing UI stages are reused
- **WHEN** capability coverage is required
- **THEN** it augments work mode, observed surface, UI interaction model, human-operability, implementation validation, and closure evidence
- **AND** it does not create a separate parallel UI workflow

#### Scenario: Observed controls alone are insufficient
- **WHEN** observed surface inventory and enabled-control functional chains pass
- **AND** a required capability is absent from the capability inventory or has no existing-flow binding
- **THEN** UI Flow Structure blocks full UI completion confidence
