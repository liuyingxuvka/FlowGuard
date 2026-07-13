## ADDED Requirements

### Requirement: UI-visible capabilities map to behavior commitments
FlowGuard SHALL require UI-visible capabilities, controls, journeys, and
screen-level promises to map to Behavior Commitment Ledger rows when UI work
claims behavioral coverage.

#### Scenario: UI capability maps to commitment
- **WHEN** a UI flow exposes a user-visible capability
- **THEN** UI Flow Structure SHALL record the behavior commitment id that owns the capability

#### Scenario: Duplicate UI ownership blocks
- **WHEN** two UI regions claim independent ownership of the same behavior commitment
- **THEN** UI Flow Structure SHALL route to Behavior Commitment Ledger before broad confidence
