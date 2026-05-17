## MODIFIED Requirements

### Requirement: Test partition ownership
FlowGuard SHALL allow projects to declare test partition items for behavior,
state, module, command, side effect, invariant, or release boundary coverage,
and SHALL assign each item to a parent test gate, child suite/script,
read-only suite, or shared kernel owner.

TestMesh SHALL be described as a parent/child test hierarchy mesh: a large test
script, suite, or validation flow is the parent boundary, while child suites or
child test scripts own validation regions. A child suite MAY itself become a
parent gate when its internal test structure grows large enough to split again.

#### Scenario: Complete test partition coverage
- **WHEN** every test partition item has a valid parent, child, read-only, or
  shared-kernel owner
- **THEN** TestMesh reports no coverage-gap finding for that parent suite

#### Scenario: Missing test partition owner
- **WHEN** a partition item has no owner
- **THEN** TestMesh reports a coverage-gap finding and does not return a green
  continue decision

#### Scenario: Child suite remains a contract at the parent layer
- **WHEN** a child suite contains many internal cases, fixtures, or state routes
- **THEN** the parent TestMesh consumes the child ownership and evidence
  contract instead of expanding every child case into the parent graph

### Requirement: Test suite evidence remains explicit
FlowGuard SHALL keep test result status, evidence tier, freshness, selected test
count, skipped tests, timeout status, background completion artifacts, and
not-run reasons visible before a child suite can support parent confidence.

#### Scenario: Stale suite evidence
- **WHEN** a child suite result is stale or foreign to the current source
- **THEN** TestMesh reports stale evidence and avoids counting that suite as
  current parent evidence

#### Scenario: Hidden skipped test
- **WHEN** a suite result claims success while skipped tests are not explicitly
  visible
- **THEN** TestMesh reports hidden skipped evidence instead of accepting the
  suite as green
