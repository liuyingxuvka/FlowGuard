## ADDED Requirements

### Requirement: Suite Commitments Map To Owners And Tests
The suite-level alignment matrix SHALL map every registered external behavior commitment to one primary owner model, relevant owner code or prompt contract, negative/positive scenarios, TestMesh shard, and current evidence receipt. Source-to-commitment and commitment-to-source mappings MUST both be complete.

#### Scenario: Commitment has no owner code contract
- **WHEN** a model and ordinary test are green but the commitment has no mapped owner code or prompt contract
- **THEN** alignment fails that commitment rather than accepting the two green endpoints

#### Scenario: Source surface is unregistered
- **WHEN** README, CLI, prompt, route registry, contract, model, installer, or project-adoption behavior makes an external promise absent from the ledger
- **THEN** coverage-gap backfill reports the unmapped source surface

### Requirement: Path Sensitive Commitments Require PPA Evidence
Every behavior commitment marked `path_sensitive=true` SHALL consume a current Primary Path Authority receipt proving one runtime authority, visible primary failure, no automatic alternate success, ContractExhaustionMesh coverage, TestMesh shards, and Risk Evidence Ledger disposition.

#### Scenario: Alternate success path remains
- **WHEN** a path-sensitive commitment has a secondary automatic success route
- **THEN** the alignment row remains failing even if primary-path tests pass

### Requirement: Alignment Closure Requires Current TestMesh Receipts
Model-Test Alignment SHALL NOT treat test names, historical reports, or task completion as current evidence. Every required alignment row MUST reference a current TestMesh receipt whose assertion scope covers that row.

#### Scenario: TestMesh shard is stale
- **WHEN** a mapped owner prompt or code file changes after the TestMesh receipt
- **THEN** the alignment row becomes stale and blocks suite-level closure
