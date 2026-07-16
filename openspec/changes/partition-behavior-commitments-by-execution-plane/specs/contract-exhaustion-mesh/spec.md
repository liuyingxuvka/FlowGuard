## ADDED Requirements

### Requirement: Behavior-plane boundary projects finite coverage axes
Behavior Commitment Ledger SHALL declare finite ContractExhaustion dimensions for behavior plane, actor kind, relation type, source/target plane pair, lookup state, owner state, and migration state.

#### Scenario: Plane relation matrix is exhausted
- **WHEN** the plane-aware BCL coverage plan is generated
- **THEN** canonical cases SHALL include allowed and rejected same-plane/cross-plane relation combinations with stable ids and oracles

#### Scenario: Actor and plane mismatch is generated
- **WHEN** finite actor-kind and plane values are declared
- **THEN** the matrix SHALL include representative invalid or review-required actor/plane combinations without claiming all semantic mistakes are enumerable

### Requirement: Lookup known-bad families have canonical cases
ContractExhaustionMesh SHALL generate canonical cases for wrong-plane primary hit, related-hit promotion, missing/stale ledger, ambiguous plane, unknown owner model, and missing match explanation.

#### Scenario: Same word appears in three planes
- **WHEN** the seed boundary contains one shared term across product, agent, and development commitments
- **THEN** generated cases SHALL require the selected plane to remain primary and other planes to remain separated or typed-related

### Requirement: Migration known-bad families have canonical cases
ContractExhaustionMesh SHALL generate cases for deterministic same-plane migration, ambiguous cross-plane dependency, unknown custom Python, dry-run mutation, dual active authority, and unclassified runtime row.

#### Scenario: Dry-run writes target
- **WHEN** a migration implementation modifies source or target during dry-run
- **THEN** the canonical oracle SHALL reject the case and provide the mutated-path evidence needed for repair

### Requirement: Plane cases project to downstream evidence owners
Plane/relation/lookup/migration case, shard, receipt, and composite acceptance ids SHALL be consumable by Model-Test Alignment, TestMesh, DevelopmentProcessFlow, and Risk Evidence Ledger.

#### Scenario: Matrix is generated but unconsumed
- **WHEN** canonical cases exist without current downstream owner evidence
- **THEN** ContractExhaustionMesh SHALL report matrix readiness only and SHALL NOT support whole-chain confidence
