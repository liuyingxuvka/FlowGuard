## ADDED Requirements

### Requirement: TestMesh owns primary path coverage shards
TestMesh SHALL allow parent validation gates to require child suite ownership
for primary-path authority coverage shard ids.

#### Scenario: Child suite owns authority shard
- **WHEN** a child suite records current passing evidence for required
  primary-path authority shard ids
- **THEN** the parent TestMesh gate MAY consume that child evidence

#### Scenario: Unowned shard blocks parent confidence
- **WHEN** a parent gate requires a primary-path authority shard id and no
  child suite owns it with current passing evidence
- **THEN** TestMesh SHALL report the required cell as missing

### Requirement: Broad green test command is insufficient
TestMesh SHALL NOT treat a broad green regression command as primary-path
Cartesian proof unless child shard ownership and current evidence are visible.

#### Scenario: Parent gate lacks child shard evidence
- **WHEN** a parent test command passes but required primary-path shard ids are
  not mapped to child evidence
- **THEN** TestMesh SHALL keep the parent confidence blocked or scoped
