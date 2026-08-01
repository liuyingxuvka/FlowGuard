## ADDED Requirements

### Requirement: Commitment owner identity reconciles against current model instances
Existing Model Preflight SHALL reconcile a commitment owner against the observed snapshot by exact normalized logical model id, exact normalized repository-relative model path, or exact current model-instance fingerprint. Path suffix matching MAY resolve an absolute and repository-relative form of the same path, but it MUST NOT make two distinct basename or partial-token matches equivalent.

#### Scenario: Ledger stores a path and snapshot exposes a logical id
- **WHEN** a primary commitment owner is stored as the exact current model path and the selected relevant hit exposes the observed logical model id plus that path
- **THEN** preflight recognizes the owner as projected and does not emit `behavior_lookup_owner_model_not_projected`

#### Scenario: Ledger stores a logical id
- **WHEN** the primary commitment owner exactly equals an observed logical model id
- **THEN** preflight recognizes the current owner projection

#### Scenario: Current fingerprint is supplied
- **WHEN** the commitment owner evidence names the exact observed instance fingerprint
- **THEN** preflight reconciles it only to that current instance

#### Scenario: Similar path is not the same owner
- **WHEN** a commitment owner differs by model path, logical id, and current fingerprint despite sharing a basename or token
- **THEN** preflight keeps `behavior_lookup_owner_model_not_projected` blocking

#### Scenario: Owner identity is ambiguous
- **WHEN** one owner identity maps to more than one observed model instance
- **THEN** preflight blocks the owner projection as ambiguous rather than selecting one by order

