## ADDED Requirements

### Requirement: Managed skills have one current runtime authority
Every managed FlowGuard skill SHALL use exactly one current contract trio, and generated/installed artifacts SHALL preserve that single authority without a migration reader or fallback route.

#### Scenario: Current trio is complete
- **WHEN** a skill has the current source, compiled contract, and exact check manifest and no former runtime residual
- **THEN** it SHALL resolve through that trio as its only runtime authority

#### Scenario: Former runtime surface remains
- **WHEN** a former work contract, underscore check manifest, run record, lifecycle declaration, or compatibility reader remains
- **THEN** runtime-authority, suite, and install validation SHALL block without a fallback route

#### Scenario: Execution depth is claimed
- **WHEN** a maintained skill claims that native checks passed
- **THEN** it SHALL cite current content-addressed owner receipts; contract compilation or former lifecycle evidence SHALL NOT substitute for execution
