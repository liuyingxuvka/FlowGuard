## ADDED Requirements

### Requirement: Runtime observations bind business path identity
Runtime path evidence SHALL allow node contracts and observations to bind to an
expected business path id, business intent, and expected terminal when real-code
evidence is used to support a path-sensitive claim.

#### Scenario: Runtime observation proves expected business path
- **WHEN** a runtime observation contains the expected node id and business path identity
- **THEN** the runtime path review records the observation as aligned with that business path

#### Scenario: Runtime observation follows wrong business path
- **WHEN** a runtime observation matches the node id but reports a different business path id, intent, or terminal
- **THEN** the runtime path review reports a mismatch instead of treating the claim as proven

### Requirement: Path-sensitive runtime gaps remain explicit
Runtime path evidence SHALL preserve path-sensitive missing or stale evidence as
review findings rather than silently downgrading the claim.

#### Scenario: Missing business path binding blocks broad claim
- **WHEN** a runtime contract declares a required business path id and the observation omits it
- **THEN** the review reports missing business path binding for that node or path
