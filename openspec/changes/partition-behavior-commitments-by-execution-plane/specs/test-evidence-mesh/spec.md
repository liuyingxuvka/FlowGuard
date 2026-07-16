## ADDED Requirements

### Requirement: Plane-upgrade validation has explicit child partitions
The parent validation gate SHALL track focused schema/lookup tests, migration tests, model regressions, skill/install parity, OpenSpec verification, and the full test suite as explicit child evidence partitions.

#### Scenario: Focused tests pass while full suite runs
- **WHEN** focused plane tests pass and a full suite is still running in the background
- **THEN** routine implementation MAY continue using the focused evidence
- **AND** full completion SHALL remain pending until final full-suite artifacts and exit status exist

### Requirement: Background model regressions expose liveness and final receipts separately
Background model-regression output SHALL be liveness-only until the registered runner writes final result/receipt artifacts with current source fingerprints and exit status.

#### Scenario: Background log is growing
- **WHEN** a regression process emits progress but has no final receipt
- **THEN** TestMesh SHALL report the child as running, not passed

#### Scenario: Peer write occurs during regression
- **WHEN** a watched source/model/test/prompt file changes after a background run starts
- **THEN** the affected result SHALL be stale and rerun or explicitly scoped before parent confidence

### Requirement: Installation parity is a distinct validation child
Canonical skill source, compiled contracts, shadow installation, and formal installed layout SHALL have explicit parity evidence separate from skill source tests.

#### Scenario: Source skill passes but installed hash differs
- **WHEN** source checks pass and installed content differs from canonical content
- **THEN** the installation child SHALL fail or block parent completion

### Requirement: Parent completion consumes every required child
The parent plane-upgrade validation gate SHALL consume current passing evidence for every required child partition and SHALL preserve failures, timeouts, skips, not-run states, and stale results.

#### Scenario: One affected model regression fails
- **WHEN** the full parent test command is green but an affected registered model child has a current failure
- **THEN** the parent SHALL remain blocked until the owning failure is repaired and rerun
