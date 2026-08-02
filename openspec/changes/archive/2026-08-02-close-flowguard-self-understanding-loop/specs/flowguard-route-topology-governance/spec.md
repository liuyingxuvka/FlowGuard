## ADDED Requirements

### Requirement: One canonical declaration owns every public route identity
The system SHALL project public route admission, coverage ownership, skill identity, documentation identity, and contract identity from one canonical declaration. Missing, conflicting, or retired identities SHALL fail visibly and SHALL NOT be repaired through aliases or fallback mappings.

#### Scenario: Coverage and admission use different owner identities
- **WHEN** generated coverage ownership differs from generated admission ownership for one public route
- **THEN** topology validation fails and names both conflicting projections

#### Scenario: Retired route identity is supplied
- **WHEN** a caller supplies a retired route identifier
- **THEN** the system rejects it without translating it to the current identifier
