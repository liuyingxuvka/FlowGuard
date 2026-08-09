## ADDED Requirements

### Requirement: Readiness distinguishes static closure from portable materialization
Blueprint readiness SHALL expose static closure, portable materialization, and execution evidence as separate ordered claims with separate fingerprints and claim boundaries.

#### Scenario: Static closure passes while execution is not run
- **WHEN** every static layer is current but one or more leaf execution owners are `not_run`
- **THEN** static readiness MAY be `ready`
- **AND** execution readiness SHALL remain visibly `not_run` or incomplete

#### Scenario: Portable materialization is absent
- **WHEN** static readiness is `ready` but no current manifest and shard bundle is available
- **THEN** portable readiness SHALL not be reported as ready
- **AND** the result SHALL name the missing materialization identity

### Requirement: Compact readiness is a projection, not a smaller denominator
Compact and candidate-detail readiness projections SHALL preserve the same complete observed denominator, fingerprints, unresolved ids, skipped/not-run statuses, and claim boundary as the full result.

#### Scenario: Caller requests a compact result
- **WHEN** the caller requests summary output
- **THEN** the system SHALL return summary identities and candidate indexes without duplicating full evidence payloads
- **AND** the caller SHALL be able to expand any listed candidate by exact id

#### Scenario: Compact output omits a gap
- **WHEN** a compact projection would hide an unresolved, skipped, stale, or `not_run` member
- **THEN** the projection SHALL remain non-ready or fail integrity validation rather than silently omitting the member
