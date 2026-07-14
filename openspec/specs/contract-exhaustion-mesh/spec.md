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

### Requirement: Primary path authority coverage universe
ContractExhaustionMesh SHALL support primary-path authority coverage universes
with finite axes for business intent, primary result, candidate surface,
candidate trigger, candidate behavior, disposition, and evidence state.

#### Scenario: Missing universe blocks no-fallback broad claim
- **WHEN** a primary-path authority plan claims done, release, publish,
  production, archive, or full confidence without a coverage universe
- **THEN** ContractExhaustionMesh SHALL report a missing coverage universe

#### Scenario: Unknown axis item blocks broad claim
- **WHEN** a coverage universe references an unknown primary-path axis value
  without scoped exclusion
- **THEN** ContractExhaustionMesh SHALL report the unknown axis item

### Requirement: Primary path interaction groups produce stable cases
ContractExhaustionMesh SHALL generate stable combination case ids for declared
primary-path interaction groups including core no-fallback, compatibility
disposition, field fallback, facade boundary, and release evidence.

#### Scenario: Core fallback masking case is generated
- **WHEN** the core no-fallback interaction group includes primary failure,
  legacy path, primary-failure trigger, and return-success behavior
- **THEN** the generated case id SHALL be stable and its oracle SHALL reject
  the behavior

#### Scenario: Missing oracle blocks primary path case
- **WHEN** a generated primary-path authority case has no oracle
- **THEN** ContractExhaustionMesh SHALL report a missing-oracle finding

### Requirement: ContractExhaustionMesh consumes commitment coverage axes
FlowGuard SHALL let ContractExhaustionMesh generate finite commitment coverage
cases for source mapping, owner uniqueness, evidence freshness, dependency
closure, scoped-out disposition, path sensitivity, PPA result, and release gate
state.

#### Scenario: Cartesian universe is generated
- **WHEN** a behavior commitment coverage universe is requested
- **THEN** ContractExhaustionMesh SHALL expose axes, interaction groups, case ids, and oracle ids for the commitment boundary

#### Scenario: Change-mode and model-miss DCAR axes are generated
- **WHEN** a behavior commitment coverage plan is generated
- **THEN** ContractExhaustionMesh SHALL include change mode, source freshness, replacement state, model sync, TestMesh state, and model-miss origin axes
- **AND** it SHALL include interaction groups for change/source freshness, replacement/model sync, and model-miss backfeed

#### Scenario: Missing oracle blocks coverage
- **WHEN** a generated commitment case has no oracle
- **THEN** ContractExhaustionMesh SHALL report the case as not covered

### Requirement: ContractExhaustionMesh generates stable behavior-authority identity faults
FlowGuard SHALL generate canonical mutation cases for missing, unknown, stale, and mismatched `business_intent_id`, `behavior_commitment_id`, and selected `primary_path_id` whenever a finite behavior or path-sensitive boundary includes those identities.

#### Scenario: Stable authority identity is missing
- **WHEN** a required path-sensitive contract omits the stable intent, commitment, or selected primary-path identity
- **THEN** ContractExhaustionMesh SHALL generate a stable missing-authority-identity case
- **AND** its oracle SHALL block downstream broad confidence

#### Scenario: Same intent uses the wrong selected path
- **WHEN** a mutation keeps the expected `business_intent_id` but substitutes another primary-path id
- **THEN** ContractExhaustionMesh SHALL generate a same-intent path-drift case
- **AND** its oracle SHALL reject the alternate path as authority evidence

#### Scenario: Parallel success masks primary failure
- **WHEN** a candidate surface is invoked after selected-primary-path failure and returns business success
- **THEN** ContractExhaustionMesh SHALL generate a parallel-success or fallback-masking case
- **AND** its oracle SHALL require visible primary failure and forbid the alternate success terminal

#### Scenario: Current path proof becomes stale
- **WHEN** the intent, commitment, selected path, owner contract, or candidate inventory changes after runtime or test evidence passed
- **THEN** ContractExhaustionMesh SHALL generate or require a stale-authority-proof case
- **AND** stale evidence SHALL NOT satisfy the refreshed coverage universe

### Requirement: Expected family members and reduction candidates are finite completeness dimensions
FlowGuard SHALL accept expected obligation-family member ids and expected Architecture Reduction candidate ids as declared finite coverage dimensions, and SHALL generate omission cases for required expected items not materialized by their owning route.

#### Scenario: Expected family member is omitted
- **WHEN** an obligation-family coverage dimension contains an expected required member absent from the materialized family and without scoped exclusion
- **THEN** ContractExhaustionMesh SHALL generate a stable omitted-family-member case
- **AND** its oracle SHALL require the family owner to materialize or disposition that member

#### Scenario: Expected reduction candidate is omitted
- **WHEN** a same-intent candidate dimension contains an expected surface absent from Architecture Reduction candidates and without scoped disposition
- **THEN** ContractExhaustionMesh SHALL generate a stable omitted-reduction-candidate case
- **AND** its oracle SHALL block complete candidate-inventory confidence

#### Scenario: Completeness boundary has no expected inventory
- **WHEN** a broad family or reduction completeness claim supplies only materialized rows and declares no independent expected-member or expected-candidate inventory
- **THEN** ContractExhaustionMesh SHALL report a model or coverage-universe gap
- **AND** it SHALL NOT infer completeness from the smaller observed set

### Requirement: Similarity handoffs produce materialized canonical cases and obligations
FlowGuard SHALL require in-scope model-similarity relation, test-obligation, and code-obligation ids to materialize as canonical mutation or combination cases and typed downstream obligations before they support finite-boundary confidence.

#### Scenario: Similarity relation materializes a canonical case
- **WHEN** a similarity relation identifies same-workflow, duplicate-boundary, adapter-only, or same-intent risk
- **THEN** ContractExhaustionMesh SHALL generate or reference canonical cases for the materialized affected members or candidates
- **AND** the report SHALL expose the originating similarity ids and downstream obligation ids

#### Scenario: Similarity id has no canonical case
- **WHEN** a coverage claim cites an in-scope similarity relation, test-obligation, or code-obligation id but no canonical case or explicit scoped disposition consumes it
- **THEN** ContractExhaustionMesh SHALL report an unmaterialized-similarity-id gap
- **AND** the opaque id SHALL NOT count as exhausted coverage

#### Scenario: Similarity inventory changes after case generation
- **WHEN** the impacted model, surface, member, or candidate inventory changes after similarity-derived cases were generated
- **THEN** the corresponding cases and receipts SHALL be stale
- **AND** current coverage SHALL require regenerated materialized cases

### Requirement: ContractExhaustionMesh covers facade delegation and invalid UI exceptions
FlowGuard SHALL generate canonical cases for retained facade delegation and UI consistency exceptions when those boundaries could conceal a second business path or authorize a forbidden behavior difference.

#### Scenario: Facade delegates to the selected primary path
- **WHEN** a facade candidate is classified as retained delegation
- **THEN** ContractExhaustionMesh SHALL require a case proving that the facade reaches the selected primary path and does not own an independent business terminal

#### Scenario: Facade returns independent success
- **WHEN** a retained facade mutation returns business success or performs the primary side effect without delegating to the selected path
- **THEN** ContractExhaustionMesh SHALL generate a rejecting facade-parallel-success case
- **AND** its oracle SHALL forbid retained-facade readiness

#### Scenario: UI exception changes behavior authority
- **WHEN** a UI consistency exception attempts to waive `business_intent_id`, `behavior_commitment_id`, `primary_path_id`, external result, or user intent
- **THEN** ContractExhaustionMesh SHALL generate an invalid-UI-exception case
- **AND** its oracle SHALL reject the exception before UI or alignment confidence

#### Scenario: UI exception changes presentation only
- **WHEN** a current UI exception changes only an allowed presentation field and preserves the stable behavior authority and external result
- **THEN** ContractExhaustionMesh MAY classify the behavior-authority portion as preserved
- **AND** the UI owner SHALL remain responsible for the presentation-specific evidence

### Requirement: Behavior-plane boundary projects finite coverage axes
Behavior Commitment Ledger SHALL declare finite ContractExhaustion dimensions for behavior plane, actor kind, relation type, source/target plane pair, lookup state, owner state, and former-shape rejection state.

#### Scenario: Plane relation matrix is exhausted
- **WHEN** the plane-aware BCL coverage plan is generated
- **THEN** canonical cases SHALL include allowed and rejected same-plane/cross-plane relation combinations with stable ids and oracles

#### Scenario: Actor and plane mismatch is generated
- **WHEN** finite actor-kind and plane values are declared
- **THEN** the matrix SHALL include representative invalid or review-required actor/plane combinations without claiming all semantic mistakes are enumerable

### Requirement: Lookup known-bad families have canonical cases
ContractExhaustionMesh SHALL generate canonical cases for wrong-plane primary hit, related-hit promotion, missing/stale ledger, ambiguous plane, unknown owner model, and missing match explanation.

#### Scenario: Same word appears in three planes
- **WHEN** the seed boundary contains one shared term across product, agent, and development commitments
- **THEN** generated cases SHALL require the selected plane to remain primary and other planes to remain separated or typed-related

### Requirement: Former-shape known-bad families have canonical cases
ContractExhaustionMesh SHALL generate cases for former dependency input, former embedded Python inventory, former JSON shape, dual active authority, and unclassified runtime row.

#### Scenario: Former shape is auto-translated
- **WHEN** a current loader silently translates a former field or artifact
- **THEN** the canonical oracle SHALL reject the case and identify the unexpected compatibility path

### Requirement: Plane cases project to downstream evidence owners
Plane/relation/lookup/former-shape case, shard, receipt, and composite acceptance ids SHALL be consumable by Model-Test Alignment, TestMesh, DevelopmentProcessFlow, and Risk Evidence Ledger.

#### Scenario: Matrix is generated but unconsumed
- **WHEN** canonical cases exist without current downstream owner evidence
- **THEN** ContractExhaustionMesh SHALL report matrix readiness only and SHALL NOT support whole-chain confidence
