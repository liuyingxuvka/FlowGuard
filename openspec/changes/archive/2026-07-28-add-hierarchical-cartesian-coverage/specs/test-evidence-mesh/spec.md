## ADDED Requirements

### Requirement: TestMesh owns combination case shards
TestMesh SHALL treat generated ContractExhaustionMesh combination case ids and
coverage shard ids as required child-suite or leaf-cell evidence targets when
validation is large, slow, split, or parent-owned.

#### Scenario: Child suite owns combination cases
- **WHEN** a TestMesh parent gate declares required combination case ids
- **THEN** each required case id is owned by a registered child suite or shard
  with current passing evidence

#### Scenario: Missing shard evidence blocks parent validation
- **WHEN** a required coverage shard has no current passing result artifact
- **THEN** TestMesh reports missing shard evidence
- **AND** parent validation confidence remains blocked or scoped

### Requirement: Progress-only shard evidence is not completion
TestMesh SHALL keep background or progress-only shard evidence separate from
completion evidence for generated combination cases.

#### Scenario: Shard has progress but no exit artifact
- **WHEN** a shard run reports progress for generated combination cases
- **AND** no final exit or result artifact exists
- **THEN** TestMesh does not count that shard as passing evidence
