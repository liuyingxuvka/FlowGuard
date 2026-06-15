## ADDED Requirements

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
