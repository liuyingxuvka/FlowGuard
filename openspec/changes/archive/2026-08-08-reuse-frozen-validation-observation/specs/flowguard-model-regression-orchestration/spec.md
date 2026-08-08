## ADDED Requirements

### Requirement: Full model composition shares one frozen validation observation
A bounded full-model planning, execution, or parent-composition operation SHALL resolve the complete repository input manifest, receipt inventory, owner contexts, and exact-current child receipt set once for its initial frozen observation. Every sibling child decision and parent row in that operation SHALL consume those same exact identities rather than rebuilding the complete observation per child, per row, or per aggregate.

#### Scenario: Fifty-one model children compose one parent
- **WHEN** one full-model operation plans or composes all required model children from unchanged repository and receipt-store inputs
- **THEN** instrumentation SHALL show one complete initial validation observation shared by every child decision
- **AND** the parent SHALL name the exact observation identity it consumed

#### Scenario: One child identity changes during composition
- **WHEN** the final freshness observation differs from the frozen observation for any consumed model input, owner context, receipt, or required child identity
- **THEN** parent publication SHALL be blocked as stale
- **AND** the operation SHALL NOT silently rebuild selected rows against the newer state or fall back to a full rerun

### Requirement: Final parent freshness comparison does not repeat semantic execution
Before publishing a current full-model parent, the orchestrator SHALL perform one fresh repository-and-receipt identity observation and compare it with the frozen observation. When the identities match, the comparison SHALL NOT rerun already terminal child producers or repeat their native semantic verifiers; when an identity differs, the parent SHALL fail closed and require a separately planned affected operation.

#### Scenario: Frozen inputs remain unchanged
- **WHEN** every final manifest, receipt inventory, owner, and child identity matches the frozen observation
- **THEN** the parent MAY become current without a second complete child-verification pass
- **AND** executed and reused child counts SHALL remain unchanged

#### Scenario: Receipt store changes after child verification
- **WHEN** a receipt is added, removed, replaced, or becomes ambiguous before parent publication
- **THEN** the final comparison SHALL reject the parent
- **AND** no earlier in-memory success or persistent cache SHALL override the drift

#### Scenario: Several executed leaves require publication
- **WHEN** several selected native model runners terminate against one frozen operation
- **THEN** the orchestrator SHALL make one final complete repository observation before publishing their validation-owner receipts
- **AND** every executed leaf SHALL use its owner context from that final observation instead of rebuilding current source identity per leaf
- **AND** one post-publication receipt reconciliation SHALL verify the exact newly supplied receipt identities without a third complete repository observation

### Requirement: Full-model timing reports separate useful work and observation overhead
The canonical full-model result SHALL report producer execution time, exact-current reuse count, initial observation time, final freshness-comparison time, and parent-composition time as distinct bounded measurements. Timing fields are diagnostic only and SHALL NOT become evidence authority.

#### Scenario: All child receipts are reused
- **WHEN** a full-model request starts zero child producers
- **THEN** the result SHALL distinguish zero producer execution from the time spent observing and composing current evidence
- **AND** it SHALL NOT report observation time as model execution time
