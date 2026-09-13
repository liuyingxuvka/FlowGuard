## ADDED Requirements

### Requirement: Prepared and closed model misses are distinct
Model-miss review SHALL report `prepared`, `blocked`, and `closed_within_scope` separately; only verified finite model, code, test, and interaction evidence may produce `closed_within_scope`.

#### Scenario: Declaration lacks a required case
- **WHEN** a miss has an intent and candidate boundary but a required test or owner receipt is missing
- **THEN** the review remains prepared or blocked and cannot claim closure

#### Scenario: Boolean field is encoded as text
- **WHEN** a canonical relation receives the string `"false"` for an evidence-current field
- **THEN** it rejects the value rather than treating it as boolean true
