## ADDED Requirements

### Requirement: Existing model lookup resolves commitment ownership
FlowGuard SHALL make existing-model preflight identify affected commitment ids,
primary owner models, and sibling commitments before non-trivial planning or
changes in an existing modeled system.

#### Scenario: Existing commitment is reused
- **WHEN** a request touches behavior already registered in a ledger
- **THEN** existing-model preflight SHALL reuse the registered commitment id and primary owner model before proposing new behavior

#### Scenario: Duplicate boundary is suspected
- **WHEN** a request appears to create behavior overlapping a sibling commitment
- **THEN** existing-model preflight SHALL route to Behavior Commitment Ledger review before implementation
