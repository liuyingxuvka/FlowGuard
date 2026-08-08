## ADDED Requirements

### Requirement: Model-revision evidence shares one bounded child closure
One model-revision evidence operation SHALL freeze the affected model set, mapped validation owners, exact-current child receipts, repository input manifest, and receipt inventory into one immutable invocation-local observation. All owner aggregates in that revision SHALL be derived from the same verified child closure, and the operation SHALL NOT reconstruct the complete closure independently for every owner aggregate.

#### Scenario: Six affected owners share current model children
- **WHEN** one revision requires six owner aggregates over overlapping exact-current model child receipts
- **THEN** every aggregate SHALL cite the same frozen observation identity and its own exact child subset
- **AND** each child SHALL be natively verified once for that frozen operation rather than once per consuming aggregate

#### Scenario: Two owners require different child subsets
- **WHEN** owner A and owner B consume different declared subsets of the frozen child closure
- **THEN** each aggregate SHALL preserve its own obligations, subject, and child identities
- **AND** sharing the observation SHALL NOT merge owners, copy one aggregate result to another, or widen either subset

### Requirement: Revision evidence receives one final fail-closed freshness check
Before a revision-evidence bundle can support candidate construction or observed-head activation, the system SHALL make one fresh observation of every frozen source, model, owner, receipt, dependency, toolchain, and environment identity. Matching identities authorize reuse of the already verified frozen closure; any difference SHALL block the bundle without patching individual aggregates in place.

#### Scenario: Source remains stable through bundle production
- **WHEN** the final observation exactly matches the frozen observation
- **THEN** the verified bundle MAY support candidate construction without repeating complete owner-closure collection or child semantic verification

#### Scenario: One governed source changes during bundle production
- **WHEN** any affected source identity differs at the final observation
- **THEN** the entire revision-evidence bundle SHALL be stale for activation
- **AND** unchanged sibling aggregates MAY remain historical evidence but SHALL NOT make the mixed bundle current

### Requirement: Frozen observation reuse cannot create model authority
An invocation-local observation SHALL be a transient verification input only. It SHALL NOT be persisted as a current model head, receipt alias, compatibility record, alternate owner store, or reusable cross-invocation success result.

#### Scenario: A later revision starts with the same repository content
- **WHEN** a second revision operation begins after the first operation has ended
- **THEN** the second operation SHALL create its own fresh frozen observation
- **AND** equality with the prior observation MAY explain reuse but SHALL NOT replace current receipt and owner verification
