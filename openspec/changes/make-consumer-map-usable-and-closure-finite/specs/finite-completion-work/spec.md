## Purpose

Bound one FlowGuard work item across source edits, validation, repair, and terminal reporting so changing descriptions or output locations cannot create an endless series of full runs.

## ADDED Requirements

### Requirement: Completion work has a stable identity and finite attempts

Every non-trivial completion execution SHALL bind to an explicit stable work identity distinct from mutable content fingerprints, output paths, and epoch identifiers. The work ledger SHALL permit one initial full production and at most one typed repair production for that identity.

#### Scenario: Description changes during one work item
- **WHEN** proposal or task text changes while the same implementation objective continues
- **THEN** the content fingerprint changes but the stable work identity and remaining attempt budget do not reset

#### Scenario: Third full launch is requested
- **WHEN** a caller requests a third production attempt for the same work identity after two attempts are recorded
- **THEN** the request is rejected before creating a child, lease, or producer

### Requirement: Read-only and terminal operations do not consume production budget

Plan, readiness, currentness, reuse-only, report, and terminal-read operations SHALL not launch functional producers or consume the work item's production budget.

#### Scenario: Readiness checks an incomplete work item
- **WHEN** readiness inspects owner evidence and finds a missing receipt
- **THEN** it reports the exact missing owner without launching a replacement producer or consuming an attempt

#### Scenario: Reuse reads an exact terminal receipt
- **WHEN** reuse-only receives an exact same-unit terminal receipt
- **THEN** it returns that receipt with zero new run directories, leases, epochs, and producers

### Requirement: Timeout and cancellation are terminally observable

Any timed-out, cancelled, interrupted, or cleanup-unconfirmed producer SHALL terminate its complete descendant process tree before its evidence is considered. A timeout SHALL not be interpreted as no change or automatically retried.

#### Scenario: Child process outlives its deadline
- **WHEN** a producer exceeds its deadline and descendants remain alive
- **THEN** the result is cleanup-unconfirmed or timeout and cannot be reused or promoted
- **AND** no second producer starts until zero descendants are confirmed

#### Scenario: Timeout cleanup succeeds
- **WHEN** all descendants are confirmed stopped after the grace period
- **THEN** the result records a terminal timeout with cleanup confirmed and the next action is the bounded typed-repair branch, if unused
