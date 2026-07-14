## ADDED Requirements

### Requirement: Plane-aware BCL APIs stay in existing route groups
The public API registry SHALL export behavior-plane constants, actor-kind constants, relation/lookup-binding types, canonical ledger load/write helpers, lookup query/hit/report types, and query functions through existing behavior-commitment or existing-preflight API groups.

#### Scenario: New public type lacks route ownership
- **WHEN** a plane-aware public export is added without membership in an existing API group
- **THEN** API registry review SHALL report an unowned public export

### Requirement: Query command adds no route id
The read-only `behavior-commitment-query` CLI SHALL be owned by the existing BCL/preflight API surface and SHALL NOT create a new public route or self-maintenance profile.

#### Scenario: Route inventory remains stable
- **WHEN** the query command is registered
- **THEN** the public route id inventory SHALL remain unchanged
- **AND** self-maintenance SHALL continue to use the existing BCL and preflight owners

### Requirement: Serialization and CLI JSON are stable
Public plane/relation/lookup reports SHALL serialize deterministically and expose canonical machine values independent of localized display wording.

#### Scenario: Same ledger and query repeat
- **WHEN** the same canonical ledger and query are executed twice
- **THEN** ordered hit ids, scores, reasons, relation roles, and ledger fingerprint SHALL be stable

