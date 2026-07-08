## ADDED Requirements

### Requirement: Primary path authority coverage universe
ContractExhaustionMesh SHALL support primary-path authority coverage universes
with finite axes for business intent, primary result, candidate surface,
candidate trigger, candidate behavior, disposition, and evidence state.

#### Scenario: Missing universe blocks no-fallback broad claim
- **WHEN** a primary-path authority plan claims done, release, publish,
  production, archive, or full confidence without a coverage universe
- **THEN** ContractExhaustionMesh SHALL report a missing coverage universe

#### Scenario: Unknown axis item blocks broad claim
- **WHEN** a coverage universe references an unknown primary-path axis value
  without scoped exclusion
- **THEN** ContractExhaustionMesh SHALL report the unknown axis item

### Requirement: Primary path interaction groups produce stable cases
ContractExhaustionMesh SHALL generate stable combination case ids for declared
primary-path interaction groups including core no-fallback, compatibility
disposition, field fallback, facade boundary, and release evidence.

#### Scenario: Core fallback masking case is generated
- **WHEN** the core no-fallback interaction group includes primary failure,
  legacy path, primary-failure trigger, and return-success behavior
- **THEN** the generated case id SHALL be stable and its oracle SHALL reject
  the behavior

#### Scenario: Missing oracle blocks primary path case
- **WHEN** a generated primary-path authority case has no oracle
- **THEN** ContractExhaustionMesh SHALL report a missing-oracle finding
