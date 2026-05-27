# budgeted-model-groups Specification

## Purpose
TBD - created by archiving change add-budgeted-model-groups. Update Purpose after archive.
## Requirements
### Requirement: Sharded Model Group Execution
FlowGuard SHALL provide a graph-style model-group runner that processes a large
reachable model in bounded shards instead of requiring the entire model to be
held or completed in one run.

#### Scenario: Model exceeds one shard budget
- **WHEN** a reachable graph has more states than the configured shard budget
- **THEN** the runner processes at most that shard budget before ending the
  shard and leaves remaining states pending in the model-group ledger

#### Scenario: Model fits one shard budget
- **WHEN** a reachable graph is exhausted before the configured shard budget is
  reached
- **THEN** the runner reports the model group as complete

### Requirement: Durable Ledger And Resume
FlowGuard SHALL persist enough model-group ledger state to avoid reprocessing
already processed states when the same model fingerprint is run again.

#### Scenario: Previous shard completed
- **WHEN** a caller runs the same model fingerprint after an earlier shard
  stopped with pending states
- **THEN** the runner continues from pending states recorded in the ledger rather
  than starting from the initial state again

#### Scenario: Model fingerprint changes
- **WHEN** the model fingerprint changes
- **THEN** the runner uses a separate ledger and does not reuse stale prior
  results

### Requirement: Whole Group Reporting
FlowGuard SHALL distinguish shard-local progress from whole model-group
completion in its structured report and text output.

#### Scenario: Shard finishes with pending work
- **WHEN** the current shard reaches 100% of its own budget but pending states
  remain
- **THEN** the report marks the model group incomplete and not OK

#### Scenario: All shards finish
- **WHEN** no pending states remain and no invariant or reachability failure was
  found
- **THEN** the report marks the model group complete and OK

### Requirement: Global Reachability And Invariant Results
FlowGuard SHALL evaluate invariants during shard processing and evaluate
required labels across the whole model group, not independently per shard.

#### Scenario: Required label appears in a later shard
- **WHEN** a required label is first discovered after the first shard
- **THEN** the final complete report treats that label as reached

#### Scenario: Invariant failure appears in a later shard
- **WHEN** an invariant fails in any shard
- **THEN** the whole model-group report marks the run as failed

### Requirement: Progress Output Compatibility
FlowGuard SHALL keep existing `Explorer` progress behavior compatible while the
new model-group runner emits shard-local ten-step progress and model-group
summary lines.

#### Scenario: Existing Explorer caller
- **WHEN** existing code uses `Explorer.explore()`
- **THEN** its progress behavior and report format remain compatible

#### Scenario: Budgeted model-group caller
- **WHEN** a caller uses the new budgeted model-group runner
- **THEN** progress output identifies both the current shard and the total
  processed/pending model-group state
