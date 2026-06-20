# contract-exhaustion-mesh Specification

## Purpose
ContractExhaustionMesh defines the canonical finite bad-case language for
FlowGuard. It turns declared field, state/input, payload, transition,
same-class, parent/child, and no-delta boundaries into stable mutation cases,
oracles, and route handoffs without relying on hand-written fallback examples.
## Requirements
### Requirement: Canonical finite contract dimensions
FlowGuard MUST represent every contract-exhaustion input as a declared
`ContractDimension` before generating required mutation cases.

#### Scenario: Declared field dimension is accepted
- **WHEN** a plan declares a required behavior-bearing field dimension with an
  owner route and allowed values or boundary policy
- **THEN** FlowGuard records the dimension as eligible for mutation-case
  generation

#### Scenario: Undeclared dimension is a model gap
- **WHEN** a caller asks FlowGuard to cover a same-class or boundary risk but
  supplies no declared dimension for that risk
- **THEN** the report records a model gap instead of claiming the risk is
  exhausted

### Requirement: Canonical mutation cases
FlowGuard MUST generate stable `ContractMutationCase` rows for declared finite
boundaries including required-field, empty-value, wrong-type, unknown-enum,
stale-evidence, missing-evidence, path-mismatch, stale-child-evidence,
unconsumed-child-evidence, and repeat-without-delta families when those
families are applicable to the dimensions supplied.

#### Scenario: Required field produces missing-field case
- **WHEN** a required field dimension is included in a contract-exhaustion plan
- **THEN** the generated cases include a stable missing-required-field mutation
  case for that dimension

#### Scenario: Parent-child evidence produces stale-consumption case
- **WHEN** a parent-child evidence dimension declares current child evidence
  consumption
- **THEN** the generated cases include stale or unconsumed child evidence
  mutations

### Requirement: Oracles are required for required cases
FlowGuard MUST require every required generated mutation case to bind an
explicit oracle before full confidence can be reported.

#### Scenario: Missing oracle blocks required case
- **WHEN** a required mutation case has no oracle
- **THEN** the report is blocked or scoped and includes a missing-oracle finding

#### Scenario: Oracle records forbidden downstream path
- **WHEN** a mutation case should stop before a downstream reviewer, parent
  consumer, or side effect
- **THEN** its oracle records the expected status and forbidden downstream step

### Requirement: Feeders do not become canonical generators
FlowGuard MUST accept route-specific seed cases from StateClosure,
ScenarioMatrix, ObligationFamily, ArtifactPayload, TransitionCoverage, and
ModelMesh closure helpers only by projecting them into canonical
`ContractMutationCase` rows.

#### Scenario: State closure seed is projected
- **WHEN** a StateClosure missing-field case is provided as a feeder
- **THEN** FlowGuard creates or references a canonical contract mutation case
  instead of treating the StateClosure case id as canonical coverage

#### Scenario: Family bad-case seed is projected
- **WHEN** an obligation-family seed names a same-class mechanism and sibling
  members
- **THEN** FlowGuard expands the seed into canonical sibling mutation cases

### Requirement: Reports expose proof-route handoffs
FlowGuard MUST report which generated case ids require Model-Test Alignment,
TestMesh, ModelMesh, LayeredBoundaryProof, or RiskEvidenceLedger evidence.

#### Scenario: Payload case requires MTA and TestMesh handoff
- **WHEN** a payload mutation case is large or evidence-sensitive
- **THEN** the report lists the case id as a payload obligation for
  Model-Test Alignment and, when needed, a required child case id for TestMesh

#### Scenario: Risk ledger consumes blocked report
- **WHEN** a contract-exhaustion report is blocked by missing oracles or model
  gaps
- **THEN** downstream risk evidence MUST NOT treat that report as full
  confidence

### Requirement: Composite handoff acceptance is separate from matrix readiness
FlowGuard MUST expose composite handoff acceptance ids separately from the
case/oracle matrix so broad claims cannot treat a single-point matrix pass as
whole model-chain closure.

#### Scenario: Multi-route case creates composite acceptance
- **WHEN** a required generated case must be consumed by more than one route
- **THEN** the report lists an independent composite handoff acceptance id for
  that case and the involved route ids

#### Scenario: Broad single-route matrix is blocked
- **WHEN** a broad release, publish, production, done, or full claim contains
  generated cases but no composite handoff acceptance
- **THEN** FlowGuard blocks the broad claim or requires the claim to be narrowed
  to single-route matrix confidence

### Requirement: No fallback case-generation path
FlowGuard MUST NOT use old hand-written same-class generators, fallback prompt
paths, old aliases, or compatibility-like wrappers as parallel canonical
case-generation routes.

#### Scenario: Old same-class case lacks canonical id
- **WHEN** a same-class closure claim cites only an old hand-written case and
  no canonical contract mutation case id
- **THEN** FlowGuard treats the claim as incomplete for contract-exhaustion
  coverage

#### Scenario: Public facade requires separate proof
- **WHEN** an old case-generation surface is intentionally preserved as a public
  facade
- **THEN** FlowGuard requires ArchitectureReduction or StructureMesh evidence
  instead of treating the facade as a fallback

### Requirement: ContractExhaustionMesh remains canonical after route cleanup
ContractExhaustionMesh SHALL remain the only canonical route for generated
finite bad-case ids after helper-control-plane consolidation.

#### Scenario: Feeder case is projected
- **WHEN** StateClosure, ScenarioMatrix, ObligationFamily, ModelMissReview,
  ArtifactPayload, TransitionCoverage, or ModelMesh closure finds a bad-case
  seed
- **THEN** the seed MUST be projected to `ContractMutationCase` before it can
  support canonical finite-boundary coverage

#### Scenario: Old helper case id is cited
- **WHEN** a claim cites only an old helper-generated case id
- **THEN** ContractExhaustionMesh MUST treat that evidence as seed evidence or
  incomplete coverage, not canonical coverage

### Requirement: Composite handoff acceptance remains separate
ContractExhaustionMesh SHALL keep composite handoff acceptance separate from
matrix readiness.

#### Scenario: Generated case crosses routes
- **WHEN** a generated case must be consumed by Model-Test Alignment, TestMesh,
  ModelMesh, RiskEvidenceLedger, or DevelopmentProcessFlow
- **THEN** the report MUST expose a composite handoff acceptance id that the
  relevant owner routes can close

### Requirement: Model-scoped Cartesian coverage
ContractExhaustionMesh SHALL support model-scoped Cartesian coverage by
allowing a plan to declare local axes, interaction groups, generated
combination cases, coverage receipts, and shard status for a specific model.

#### Scenario: Leaf model generates local combinations
- **WHEN** a leaf model declares finite input, state, field, evidence, or output
  axes in one interaction group
- **THEN** FlowGuard generates stable combination case ids for the local
  Cartesian product of that interaction group
- **AND** the resulting coverage receipt names the model id and generated case
  ids

#### Scenario: Missing model id blocks full hierarchical coverage
- **WHEN** a broad hierarchical claim depends on contract-exhaustion coverage
  but the coverage receipt has no model id
- **THEN** FlowGuard reports the coverage as invalid for all-model Cartesian
  confidence

### Requirement: Coverage receipts preserve shard state
ContractExhaustionMesh SHALL represent large model-scoped Cartesian matrices as
explicit shards without treating unfinished shards as full coverage.

#### Scenario: Unfinished shard remains visible
- **WHEN** a model-scoped coverage receipt has required shards that are not
  current and passing
- **THEN** the receipt reports scoped or blocked coverage instead of full
  coverage

#### Scenario: Full coverage requires every required shard
- **WHEN** every generated case is covered directly or every required shard is
  current and passing
- **THEN** the coverage receipt may report full confidence for that model

### Requirement: Parent interface combinations use child summaries
ContractExhaustionMesh SHALL allow parent interaction groups to combine child
coverage receipt summaries, exposed output classes, exposed error classes, and
parent-local axes instead of expanding every child internal case.

#### Scenario: Parent consumes child summaries
- **WHEN** a parent model declares an interaction group over child receipt
  output classes and parent state
- **THEN** FlowGuard generates parent interface combination cases over those
  summaries
- **AND** the parent receipt records which child receipt ids were consumed

### Requirement: Combination cases project to route obligations
ContractExhaustionMesh SHALL project generated combination case ids to
Model-Test Alignment, TestMesh, ModelMesh, and RiskEvidenceLedger using the
existing route handoff surface.

#### Scenario: Combination case crosses route owners
- **WHEN** a generated combination case requires semantic test binding, large
  test evidence, parent/child consumption, and final risk evidence
- **THEN** FlowGuard exposes route case ids and composite handoff acceptance ids
  for the same combination case id

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
