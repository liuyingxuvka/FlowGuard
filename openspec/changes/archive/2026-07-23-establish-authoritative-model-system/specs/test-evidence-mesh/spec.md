## ADDED Requirements

### Requirement: Test receipts bind resolved inputs and snapshot subject
TestMesh SHALL retain the exact resolved input paths and hashes, model-instance
fingerprints, snapshot fingerprint, software subject revision, execution owner,
terminal result, skipped rows, and claim boundary for every evidence shard used
by model-system activation.

#### Scenario: Input glob resolves differently after execution
- **WHEN** the current resolved files or hashes differ from the input inventory recorded by a passing shard
- **THEN** TestMesh marks that shard stale even when the original glob expression is unchanged

### Requirement: Full validation has singular execution owners
One frozen source snapshot SHALL have at most one all-model regression execution
owner and at most one full-test execution owner. Consumers SHALL reuse their
terminal receipts and MUST NOT launch equivalent duplicate owners.

#### Scenario: A background owner is still running
- **WHEN** the process is live but no terminal receipt exists
- **THEN** TestMesh reports running rather than passed and downstream release gates remain blocked
