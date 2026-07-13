## ADDED Requirements

### Requirement: Runtime evidence preserves fallback masking signals
Runtime path evidence SHALL allow observations and alignment plans to record
primary path id, fallback path id, primary failure id, fallback invocation, and
fallback returned success for path-sensitive claims.

#### Scenario: Runtime fallback masking is reported
- **WHEN** a runtime observation shows the primary path failed, an alternate
  path was invoked because of that failure, and the alternate returned success
- **THEN** the runtime path review SHALL report a silent fallback finding

#### Scenario: No fallback invocation supports evidence
- **WHEN** a path-sensitive runtime observation binds to the expected primary
  path and records that no fallback was invoked
- **THEN** the runtime path review MAY use that observation as no-fallback
  evidence for the declared primary path

### Requirement: Runtime node contracts can name primary authority
Runtime node contracts SHALL be able to declare the primary path id and
expected no-fallback behavior for nodes that support primary-path authority.

#### Scenario: Missing primary path id blocks strict authority proof
- **WHEN** a runtime alignment plan requires primary-path authority evidence
  and a required node contract omits the primary path id
- **THEN** the review SHALL report a missing primary path binding
