## ADDED Requirements

### Requirement: Portable Temporal Topology Evidence
When a topology review makes a portable liveness or fairness claim, the system SHALL consume current executable temporal obligations and checker findings for the same portable model identity.

#### Scenario: Current temporal receipt supports topology claim
- **WHEN** the topology and portable checker consume the same graph identity and all required temporal obligations pass
- **THEN** the portable liveness or fairness claim may pass within the declared bound

#### Scenario: Metadata-only fairness is rejected
- **WHEN** fairness is described in route metadata without a current executable obligation and receipt
- **THEN** the portable fairness claim remains unverified

