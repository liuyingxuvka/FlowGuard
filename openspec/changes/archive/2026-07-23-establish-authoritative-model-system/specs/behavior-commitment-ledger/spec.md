## ADDED Requirements

### Requirement: Active commitments bind exact observed model instances
Every in-scope active behavior commitment SHALL resolve to exactly one primary
model instance in the observed-head snapshot. Supporting and child owners SHALL
also use immutable instance references.

#### Scenario: Owner model artifact changes
- **WHEN** a commitment names a logical model id whose artifact or purpose fingerprint no longer matches the observed snapshot member
- **THEN** the commitment is stale and cannot satisfy current behavior coverage

### Requirement: Replaced and retired commitments do not rank as current
Behavior commitment lookup SHALL exclude replaced and retired commitments from
primary current results while preserving them as historical context.

#### Scenario: Retired commitment text matches exactly
- **WHEN** a retired commitment has a stronger lexical match than an active commitment
- **THEN** lookup selects the active same-plane commitment and reports the retired match only as historical context
