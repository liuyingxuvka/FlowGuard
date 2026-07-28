## MODIFIED Requirements

### Requirement: Interrupted Owner Evidence Is Not Reusable
Timeout, cancellation, interruption, or launcher failure SHALL trigger
platform-appropriate containment, termination, and enumeration of the complete
descendant process tree. Until zero live descendants are confirmed, cleanup
SHALL be `cleanup-unconfirmed`, no authoritative owner receipt may be
published, owner and resource leases MUST remain blocking, and no later owner
in the frozen parent or automatic retry may start. After cleanup is confirmed,
FlowGuard MAY persist terminal non-pass diagnostic evidence for the original
episode; any retry MUST use one new immutable execution identity.

#### Scenario: Launcher times out with live descendants
- **WHEN** the launcher stops but any descendant process remains
- **THEN** cleanup status is `cleanup-unconfirmed`
- **AND** no receipt is published or reusable, no residual lease is released,
  and no later owner or automatic retry starts

#### Scenario: Cleanup reaches zero descendants
- **WHEN** cancellation or interruption is followed by confirmed zero live
  descendants
- **THEN** the original episode MAY settle as terminal non-pass evidence and
  its leases MAY be released
- **AND** a retry MUST use a new execution identity

## ADDED Requirements

### Requirement: Process-tree terminality replaces PID and log authority
A long-check owner SHALL be terminal only when its contained descendant process
tree has settled, its registered result artifacts are closed, and its exit
status is final. Launcher exit, a missing top-level PID, quiet logs, growing
logs, heartbeat expiry, or progress completion MUST NOT establish process-tree
terminality.

#### Scenario: Direct child exits while grandchild continues
- **WHEN** the launcher and direct child are absent but a contained grandchild
  remains live
- **THEN** the owner MUST remain running or cleanup-unconfirmed and cannot
  publish terminal evidence

#### Scenario: Logs stop before process settlement
- **WHEN** no new log output appears but the descendant tree has not reached
  confirmed zero
- **THEN** FlowGuard MUST report liveness uncertainty rather than failure,
  success, or safe cleanup

### Requirement: Long-check receipts bind settlement evidence
A terminal long-check receipt SHALL bind the execution identity, containment
identity, descendant-settlement result, terminal exit status, exact result
artifacts and fingerprints, and owner/resource lease settlement. A receipt
that lacks confirmed process-tree settlement MUST NOT be current or reusable.

#### Scenario: Result artifact exists before descendants exit
- **WHEN** a nominally passing result file exists while a descendant remains
  live
- **THEN** no terminal-success receipt may be published

#### Scenario: Terminal receipt has complete settlement
- **WHEN** every descendant is confirmed terminated, result artifacts are
  finalized, exit status is terminal, and leases are settled
- **THEN** the owner MAY publish an immutable receipt for independent parent
  verification
