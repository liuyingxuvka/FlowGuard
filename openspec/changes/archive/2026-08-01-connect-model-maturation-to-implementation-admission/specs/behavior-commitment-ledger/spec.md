## ADDED Requirements

### Requirement: Triggered commitment coverage contributes to maturation
Behavior Commitment Ledger SHALL project the in-scope external-promise source inventory, current primary owners, and open coverage or path-authority gaps into task-local maturation when behavior commitment review is triggered.

#### Scenario: Target-domain role remains target-owned
- **WHEN** a commitment references a target application's administrator, approver, member, or other domain role
- **THEN** FlowGuard MUST treat that role identity as target-owned behavior context and MUST NOT add it to a global FlowGuard role taxonomy

#### Scenario: Commitment is omitted from candidate coverage
- **WHEN** an independently inventoried in-scope external promise is not represented by the candidate model
- **THEN** maturation MUST retain the promise as an uncovered item
