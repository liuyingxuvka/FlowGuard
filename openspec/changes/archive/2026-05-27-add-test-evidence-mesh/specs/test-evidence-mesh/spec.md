## ADDED Requirements

### Requirement: Test partition ownership
FlowGuard SHALL allow projects to declare test partition items for behavior,
state, module, command, side effect, invariant, or release boundary coverage,
and SHALL assign each item to a parent, child suite, read-only suite, or shared
kernel owner.

#### Scenario: Complete test partition coverage
- **WHEN** every test partition item has a valid owner
- **THEN** TestMesh reports no coverage-gap finding for that parent suite

#### Scenario: Missing test partition owner
- **WHEN** a partition item has no owner
- **THEN** TestMesh reports a coverage-gap finding and does not return a green
  continue decision

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

### Requirement: Background completion is not progress
FlowGuard SHALL distinguish background progress output from completion evidence.

#### Scenario: Background progress without exit artifact
- **WHEN** a background test run has progress output but no exit/result artifact
- **THEN** TestMesh reports the background run as incomplete rather than passed

### Requirement: Duplicate ownership is blocked
FlowGuard SHALL reject test hierarchies where sibling suites both own the same
state write, side effect, or core validation partition unless the ownership is
read-only or explicitly shared-kernel.

#### Scenario: Duplicate state owner
- **WHEN** two child suites both own the same state or side-effect partition
- **THEN** TestMesh reports an ownership conflict and blocks green continuation

### Requirement: Routine and release gates are distinct
FlowGuard SHALL distinguish routine validation confidence from release
confidence so expensive release-only suites can be visible without blocking fast
routine checks.

#### Scenario: Routine scope with pending release-only suite
- **WHEN** routine validation is requested and a release-only suite is pending
- **THEN** TestMesh may return routine green while reporting the release
  obligation as deferred

#### Scenario: Release scope with missing release suite
- **WHEN** release validation is requested and a release-required suite is not
  current
- **THEN** TestMesh blocks release green confidence
