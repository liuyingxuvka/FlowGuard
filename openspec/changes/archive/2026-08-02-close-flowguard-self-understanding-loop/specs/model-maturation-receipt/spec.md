## ADDED Requirements

### Requirement: Understanding status is a read-only receipt projection
The system SHALL provide a status projection over explicitly supplied task, model, demand, resolution, maturation, and receipt identities. Reading status SHALL NOT execute an owner, publish or renew a receipt, change current authority, or convert missing evidence into success.

#### Scenario: No maturation receipt is supplied
- **WHEN** status is requested for a task with no matching verified maturation receipt
- **THEN** understanding sufficiency is reported as not-run or unresolved and no receipt is created

#### Scenario: Receipt identity is stale
- **WHEN** the supplied receipt does not match the current task, model, demand, or resolution identity
- **THEN** status reports stale with the mismatched identity fields
