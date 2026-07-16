## ADDED Requirements

### Requirement: DevelopmentProcessFlow consumes spec work packages
DevelopmentProcessFlow SHALL treat provider work packages, reconciliation reports, session snapshots, and receipt fan-out as development-process artifacts without absorbing provider or product behavior authority.

#### Scenario: Work package enters the lifecycle
- **WHEN** a provider work package is selected for implementation or verification
- **THEN** DevelopmentProcessFlow SHALL order provider read, task/obligation reconciliation, begin snapshot, execute-or-reuse checks, post snapshot, native provider verification, synchronization, and archive readiness

#### Scenario: Peer write occurs during the session
- **WHEN** a peer or unknown writer changes a covered canonical input after begin
- **THEN** DevelopmentProcessFlow SHALL preserve the write, stale affected receipts, and derive minimum revalidation rather than roll back the peer

### Requirement: Process closure requires post-snapshot evidence
DevelopmentProcessFlow SHALL reject done, archive, release, or publish confidence based only on provider checkboxes, a pre-run snapshot, or background liveness.

#### Scenario: Session lacks terminal post evidence
- **WHEN** the process has no matching immutable post snapshot and terminal child receipts
- **THEN** the process SHALL remain incomplete even if every provider task is checked
