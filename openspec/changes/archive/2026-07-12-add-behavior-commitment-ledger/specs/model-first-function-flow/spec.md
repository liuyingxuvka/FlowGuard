## ADDED Requirements

### Requirement: Model-first work binds models to behavior commitments
FlowGuard SHALL require non-trivial model-first behavior work to identify the
affected behavior commitment before treating a model as sufficient coverage.

#### Scenario: Model proves a commitment
- **WHEN** a model-first plan declares one primary owner model for a behavior commitment
- **THEN** the model SHALL be treated as proof coverage for that commitment rather than as the complete feature inventory

#### Scenario: Model has no commitment boundary
- **WHEN** a model-first plan makes a broad behavior claim without a commitment id
- **THEN** the work SHALL be routed to Behavior Commitment Ledger before broad confidence
