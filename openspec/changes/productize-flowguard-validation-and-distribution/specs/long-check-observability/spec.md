## ADDED Requirements

### Requirement: Model Shard Progress Events
Long model-regression execution SHALL emit bounded progress events containing run id, tier, shard, active model, completed/total counts, elapsed time, last terminal, and artifact location. Progress events MUST NOT be treated as completion evidence.

#### Scenario: Background full run is active
- **WHEN** the full tier continues beyond the progress interval
- **THEN** the orchestrator emits progress with completed/total counts while final status remains running

### Requirement: Per Runner And Parent Time Bounds
Each model runner SHALL have a timeout and each shard/full parent SHALL have a declared overall bound or explicit monitor policy. Timeout, cancellation, and interruption MUST create terminal child records and a non-pass parent disposition.

#### Scenario: Parent is cancelled
- **WHEN** the operator cancels an active full regression
- **THEN** active children are terminated safely, completed receipts remain preserved, and the parent reports cancelled rather than pass

### Requirement: Terminal Receipt Completeness
A long validation run SHALL emit a final receipt only after every selected child is terminal. The receipt SHALL list passed, failed, timed-out, cancelled, skipped, and not-run children, plus claim boundary and minimum rerun scope.

#### Scenario: Child process disappears without result
- **WHEN** a selected child exits or is lost without a valid terminal artifact
- **THEN** the parent records an internal/unknown child failure and cannot emit a complete passing receipt
