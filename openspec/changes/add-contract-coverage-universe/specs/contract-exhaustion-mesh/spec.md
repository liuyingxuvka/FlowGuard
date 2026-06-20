## ADDED Requirements

### Requirement: Coverage universe completeness
ContractExhaustionMesh SHALL allow a plan to declare the complete coverage
universe for a scoped or broad claim, including required dimensions, axes,
interaction groups, payload contracts, code boundaries, generated case ids,
coverage receipts, and explicit scoped exclusions.

#### Scenario: Broad claim missing coverage universe
- **WHEN** a contract-exhaustion plan claims done, release, publish,
  production, or full confidence without a coverage universe
- **THEN** FlowGuard reports a blocked finding instead of treating the generated
  matrix as complete coverage

#### Scenario: Declared universe item is missing from generated coverage
- **WHEN** a coverage universe names a required dimension, axis, interaction
  group, case id, payload contract, boundary, or receipt that is not present in
  the plan or generated report
- **THEN** FlowGuard reports the missing item with its kind and id

#### Scenario: Scoped exclusion closes an intentional gap
- **WHEN** a universe item is intentionally excluded with a reason and owner
  route
- **THEN** FlowGuard keeps the exclusion visible without blocking that specific
  missing item

### Requirement: Actionable oracle feedback
ContractExhaustionMesh SHALL require reject, block, reissue, retry, or repair
cases to declare expected feedback fields and repair fields when actionable
feedback is required by the plan or broad claim.

#### Scenario: Reject case lacks repair fields
- **WHEN** a required bad case expects rejection, blocking, reissue, retry, or
  repair but its oracle does not name repair fields
- **THEN** FlowGuard reports an actionable-oracle finding for that case

#### Scenario: Reject case includes actionable feedback
- **WHEN** a required bad case has an oracle with expected message fields and
  repair fields
- **THEN** FlowGuard can treat the case as mechanically actionable for the
  contract-exhaustion report

### Requirement: Generic synthetic contract fault profiles
ContractExhaustionMesh SHALL expose generic synthetic contract-fault profiles
from generated cases so downstream consumers can rehearse bad submissions
without adding a domain-specific fake actor to FlowGuard.

#### Scenario: Synthetic fault profile is generated from a case
- **WHEN** a generated mutation or combination case has an expected oracle
  reaction
- **THEN** FlowGuard can emit a `ContractFaultProfile` naming the contract
  path, mutation type, expected status, message fields, repair fields, and
  retry class

#### Scenario: Synthetic fault profile is not live evidence
- **WHEN** a synthetic fault profile is exported
- **THEN** it is marked synthetic-only and not allowed to satisfy live
  completion evidence by itself

### Requirement: Observed problem backfeed
ContractExhaustionMesh SHALL accept observed-problem backfeed rows and report
whether each real miss maps to generated cases, same-class cases, and coverage
receipts.

#### Scenario: Observed miss maps to generated coverage
- **WHEN** an observed problem names generated mutation or combination cases
  plus same-class coverage and receipt ids
- **THEN** FlowGuard records the problem as mapped to the current coverage
  matrix

#### Scenario: Observed miss is outside the coverage universe
- **WHEN** an observed problem cannot be matched to a generated case,
  same-class case, or required receipt
- **THEN** FlowGuard reports it as a coverage or model gap rather than
  treating the existing matrix as complete
