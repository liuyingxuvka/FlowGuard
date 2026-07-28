## ADDED Requirements

### Requirement: Model-scoped Cartesian coverage
ContractExhaustionMesh SHALL support model-scoped Cartesian coverage by
allowing a plan to declare local axes, interaction groups, generated
combination cases, coverage receipts, and shard status for a specific model.

#### Scenario: Leaf model generates local combinations
- **WHEN** a leaf model declares finite input, state, field, evidence, or output
  axes in one interaction group
- **THEN** FlowGuard generates stable combination case ids for the local
  Cartesian product of that interaction group
- **AND** the resulting coverage receipt names the model id and generated case
  ids

#### Scenario: Missing model id blocks full hierarchical coverage
- **WHEN** a broad hierarchical claim depends on contract-exhaustion coverage
  but the coverage receipt has no model id
- **THEN** FlowGuard reports the coverage as invalid for all-model Cartesian
  confidence

### Requirement: Coverage receipts preserve shard state
ContractExhaustionMesh SHALL represent large model-scoped Cartesian matrices as
explicit shards without treating unfinished shards as full coverage.

#### Scenario: Unfinished shard remains visible
- **WHEN** a model-scoped coverage receipt has required shards that are not
  current and passing
- **THEN** the receipt reports scoped or blocked coverage instead of full
  coverage

#### Scenario: Full coverage requires every required shard
- **WHEN** every generated case is covered directly or every required shard is
  current and passing
- **THEN** the coverage receipt may report full confidence for that model

### Requirement: Parent interface combinations use child summaries
ContractExhaustionMesh SHALL allow parent interaction groups to combine child
coverage receipt summaries, exposed output classes, exposed error classes, and
parent-local axes instead of expanding every child internal case.

#### Scenario: Parent consumes child summaries
- **WHEN** a parent model declares an interaction group over child receipt
  output classes and parent state
- **THEN** FlowGuard generates parent interface combination cases over those
  summaries
- **AND** the parent receipt records which child receipt ids were consumed

### Requirement: Combination cases project to route obligations
ContractExhaustionMesh SHALL project generated combination case ids to
Model-Test Alignment, TestMesh, ModelMesh, and RiskEvidenceLedger using the
existing route handoff surface.

#### Scenario: Combination case crosses route owners
- **WHEN** a generated combination case requires semantic test binding, large
  test evidence, parent/child consumption, and final risk evidence
- **THEN** FlowGuard exposes route case ids and composite handoff acceptance ids
  for the same combination case id
