## ADDED Requirements

### Requirement: Invocation-local validation observations are strict non-authoritative reuse
FlowGuard SHALL permit one frozen validation observation to be shared only inside the bounded operation that created it. The observation SHALL preserve the canonical repository-input manifest, receipt inventory, owner contexts, terminal states, obligations, dependencies, toolchain, environment, and independently verified child identities without weakening, relabeling, or omitting any evidence gate.

#### Scenario: Several aggregates consume one verified child
- **WHEN** one independently produced exact-current child receipt is declared by several owner aggregates in the same frozen operation
- **THEN** the child MAY be verified once and referenced by every exact declared aggregate subset
- **AND** every aggregate SHALL retain its distinct owner, subject, obligations, and result identity

#### Scenario: Frozen observation contains a non-terminal child
- **WHEN** a required child is failed, blocked, stale, skipped, timed out, cancelled, not run, ambiguous, or cleanup-unconfirmed
- **THEN** every consuming aggregate SHALL preserve the corresponding non-pass state
- **AND** observation sharing SHALL NOT turn it into terminal success

### Requirement: Observation reuse has one visible freshness boundary
Every bounded operation that uses a frozen validation observation SHALL expose the initial observation identity and final freshness outcome. Current parent, revision, activation, release, or broad-confidence claims SHALL require an exact matching final observation; absence of the final comparison SHALL be `not_run`, not pass.

#### Scenario: Final comparison was skipped
- **WHEN** an operation has produced candidate aggregates but did not perform the required fresh identity comparison
- **THEN** its currentness result SHALL be `not_run`
- **AND** the candidate artifacts SHALL remain non-authoritative

#### Scenario: Final comparison matches
- **WHEN** all governed identities match and every required child was already independently terminal and exact-current
- **THEN** the operation MAY publish its parent or bundle result
- **AND** the final comparison SHALL not manufacture a new child result

#### Scenario: Final observation publishes several new leaves
- **WHEN** one bounded operation has several newly executed terminal children
- **THEN** their owner receipts SHALL consume the one final fresh owner-context projection
- **AND** per-leaf source-current rebuild and per-leaf receipt-store scan counts SHALL be zero
- **AND** exactly one post-publication receipt reconciliation SHALL be required before a parent claim becomes current
