## ADDED Requirements

### Requirement: TestMesh reconciles commitment coverage shards
FlowGuard SHALL let child suites own behavior commitment coverage shards while
the parent TestMesh reconciles all required commitment case ids.

#### Scenario: Child shard covers required case
- **WHEN** a child suite reports current evidence for a required commitment coverage case id
- **THEN** the parent TestMesh MAY count that case as covered

#### Scenario: Progress-only evidence is insufficient
- **WHEN** a child suite reports progress without the required commitment case ids
- **THEN** the parent TestMesh SHALL NOT treat commitment coverage as complete
