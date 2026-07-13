## ADDED Requirements

### Requirement: Model miss review backfeeds behavior registration without creating duplicate features
FlowGuard SHALL use model-miss evidence to check whether the failed external
behavior was already registered before changing the Behavior Commitment Ledger.

#### Scenario: Existing commitment owns the missed behavior
- **WHEN** runtime, test, replay, log, or manual validation evidence fails after a green FlowGuard claim
- **AND** an existing commitment covers the observed external behavior
- **THEN** Model Miss Review SHALL repair the owner model, code contract, tests, same-class/DCAR coverage, and evidence under the existing commitment
- **AND** it SHALL NOT require a new behavior commitment for the point failure

#### Scenario: Miss exposes unregistered external behavior
- **WHEN** model-miss evidence exposes external behavior that no commitment covers
- **THEN** Model Miss Review SHALL route to Behavior Commitment Ledger coverage-gap backfill
