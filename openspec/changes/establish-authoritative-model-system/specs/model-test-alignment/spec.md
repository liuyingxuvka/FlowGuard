## ADDED Requirements

### Requirement: Alignment evidence binds a model-system snapshot
Model-Test Alignment SHALL compare obligations, code contracts, scenarios,
invariants, hazards, source audits, and evidence against the exact model
instance and model-system snapshot identities they validate.

#### Scenario: Test is green against an older input inventory
- **WHEN** a test result passes but its resolved source inventory differs from the candidate or observed snapshot
- **THEN** alignment reports stale evidence and does not close the obligation

### Requirement: Alignment reports revision-set closure
For a model revision set, Model-Test Alignment SHALL report every required
member, relation, commitment, field, side effect, contract, test, and evidence
row as passed, blocked, failed, stale, skipped, or not run.

#### Scenario: One related contract is not run
- **WHEN** all changed models pass but one required affected code contract is not run
- **THEN** the aggregate revision-set result remains blocked
