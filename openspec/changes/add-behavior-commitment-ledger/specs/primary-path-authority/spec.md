## ADDED Requirements

### Requirement: PPA acts as downstream authority for path-sensitive commitments
FlowGuard SHALL let Behavior Commitment Ledger hand path-sensitive commitments
to Primary Path Authority and consume the resulting report, decision, receipt,
and risk gate ids.

#### Scenario: Ledger creates PPA binding
- **WHEN** a behavior commitment is marked path-sensitive
- **THEN** the ledger SHALL require a PPA binding instead of treating fallback-path review as a separate ledger-only concern

#### Scenario: PPA report maps back to commitment
- **WHEN** a PPA report is attached to a behavior commitment
- **THEN** the ledger SHALL preserve the commitment id and expose the PPA decision in the commitment coverage report
