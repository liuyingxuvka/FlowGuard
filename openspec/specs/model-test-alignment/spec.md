# model-test-alignment Specification

## Purpose
TBD - created by archiving change add-model-test-alignment. Update Purpose after archive.
## Requirements
### Requirement: Review model obligations against test evidence
FlowGuard SHALL provide a standalone model-test alignment helper that accepts explicit model obligations and plain test evidence, then reports whether every required model obligation has current acceptable test evidence.

#### Scenario: Complete alignment passes
- **WHEN** each required model obligation is referenced by at least one current passing test evidence item with an allowed test kind
- **THEN** the alignment report SHALL be OK and SHALL return `model_test_alignment_green` as the decision

#### Scenario: Missing test evidence blocks green
- **WHEN** a required model obligation has no current passing test evidence
- **THEN** the alignment report SHALL not be OK and SHALL include a `missing_test_evidence` finding for that obligation

### Requirement: Keep orphan and duplicate test claims visible
FlowGuard SHALL report tests that do not map to known model obligations and SHALL report duplicate ownership when multiple tests claim the same obligation unless sharing is explicitly allowed.

#### Scenario: Orphan test is reported
- **WHEN** a test evidence item does not reference any known model obligation
- **THEN** the alignment report SHALL include an `orphan_test_evidence` finding for that test

#### Scenario: Duplicate test ownership is reported
- **WHEN** more than one test evidence item claims the same obligation and the obligation does not allow shared evidence
- **THEN** the alignment report SHALL include a `duplicate_test_evidence_owner` finding

### Requirement: Preserve evidence freshness and result status
FlowGuard SHALL treat stale, skipped, failed, timeout, not-run, running, and error test evidence as visible gaps rather than passing coverage.

#### Scenario: Stale passing test is not current coverage
- **WHEN** a test evidence item passed but is marked not current
- **THEN** the alignment report SHALL include `stale_test_evidence` and SHALL not use it as current passing coverage

#### Scenario: Skipped test is not passing coverage
- **WHEN** a test evidence item is skipped, failed, timeout, not-run, running, or error
- **THEN** the alignment report SHALL include a non-passing evidence finding and SHALL not use it as current passing coverage

### Requirement: Flag missing risky path coverage
FlowGuard SHALL detect when a model obligation declares required test kinds and the bound test evidence only covers a subset, such as a happy path without a required failure, edge, replay, or negative path.

#### Scenario: Happy-path-only evidence is insufficient
- **WHEN** an obligation requires both `happy_path` and `failure_path` evidence but only `happy_path` evidence is current and passing
- **THEN** the alignment report SHALL include a `missing_required_test_kind` finding

### Requirement: Skill Kernel routes to model-test alignment independently
The model-first FlowGuard Skill Kernel SHALL expose `model_test_alignment` as a route that is independent of TestMesh, StructureMesh, and ModelMesh.

#### Scenario: Alignment route does not require mesh routes
- **WHEN** a project has a FlowGuard model and ordinary tests but no TestMesh, StructureMesh, or ModelMesh artifacts
- **THEN** the Skill Kernel documentation SHALL still allow `model_test_alignment` to be used

### Requirement: Model-Test Alignment covers optional code external contracts
The `model_test_alignment` route SHALL compare FlowGuard model obligations,
optional code external contracts, and ordinary test evidence when code
contracts are in scope.

#### Scenario: Model-to-test alignment remains valid without code contracts
- **WHEN** a FlowGuard model has explicit obligations and no externally visible
  code contract is in scope for the current review
- **THEN** Model-Test Alignment compares `ModelObligation` rows directly with
  `TestEvidence` rows
- **AND** it does not require agents to invent code contract rows, split code,
  or invoke StructureMesh

#### Scenario: Code contracts are included when the external code surface is in scope
- **WHEN** the reviewed behavior depends on a public function, API, CLI,
  facade, adapter, persisted output, or other externally visible code surface
- **THEN** Model-Test Alignment includes optional `CodeContract` rows between
  `ModelObligation` rows and `TestEvidence` rows
- **AND** each owner code contract is bound to the model obligations it
  implements

#### Scenario: Code contracts can be required before rows exist
- **WHEN** the review declares that code external contracts are in scope but no
  code contract rows have been listed yet
- **THEN** the plan can require code contracts explicitly
- **AND** missing owner contracts block coverage instead of silently falling
  back to model-to-test-only confidence

### Requirement: Code contract rows expose externally visible behavior
When `CodeContract` rows are present, the review SHALL record enough behavior
surface to compare them with model obligations.

#### Scenario: Code contract fields are recorded
- **WHEN** an agent lists a code external contract
- **THEN** the row includes id, path, symbol, surface type, role, implemented
  model obligation ids, external inputs, external outputs, state reads, state
  writes, side effects, error paths, and required status

#### Scenario: Missing code contract owner blocks coverage
- **WHEN** a required model obligation has code contracts in scope but no owner
  contract implements that obligation
- **THEN** the review reports `missing_code_contract`
- **AND** the coverage claim remains blocked

#### Scenario: Code contract behavior mismatch stays visible
- **WHEN** a code contract owner is missing behavior required by the model
  obligation
- **THEN** the review reports `code_contract_missing_behavior`
- **AND** when the obligation requires an exact external contract and the code
  contract exposes extra behavior, the review reports
  `code_contract_extra_behavior`

#### Scenario: Duplicate code contract owners stay visible
- **WHEN** more than one owner code contract claims the same model obligation
  without explicit shared implementation intent
- **THEN** the review reports `duplicate_code_contract_owner`

### Requirement: Test evidence binds to code contracts when contracts are in scope

When code external contracts are included, ordinary test evidence SHALL bind to
both the relevant model obligations and the relevant code contract ids.

#### Scenario: Duplicate primary edge proof requires a child split
- **WHEN** more than one current passing primary `edge_path` evidence row
  claims the same model obligation
- **THEN** Model-Test Alignment MUST report
  `obligation_too_coarse_for_primary_evidence`
- **AND** the decision MUST be `child_model_split_required`
- **AND** the report MUST NOT treat downgrading one proof to supporting evidence
  as coverage unless that evidence is attached to a child obligation, code
  contract, or leaf matrix cell

#### Scenario: Leaf matrix-cell evidence is not a duplicate primary proof
- **WHEN** multiple current passing test rows claim the same model obligation
  and kind but are marked as leaf matrix-cell evidence with distinct target
  cell ids
- **THEN** Model-Test Alignment MUST NOT report duplicate primary ownership for
  those rows

#### Scenario: Supporting evidence has no target
- **WHEN** a supporting or leaf matrix-cell evidence row does not identify the
  child obligation, code contract, or leaf cell it supports
- **THEN** Model-Test Alignment MUST block the coverage claim with a missing
  target finding

### Requirement: Model-Test Alignment remains independent from mesh routes
The route SHALL remain a direct alignment review and SHALL NOT become TestMesh,
StructureMesh, or ModelMesh.

#### Scenario: Large validation is routed separately
- **WHEN** the problem is large, slow, layered, stale-prone, or release-only
  validation evidence
- **THEN** the agent uses TestMesh instead of expanding Model-Test Alignment
  into a test hierarchy

#### Scenario: Code partition work is routed separately
- **WHEN** the problem is splitting code, APIs, modules, scripts, facades, or
  ownership boundaries
- **THEN** the agent uses StructureMesh instead of treating code contract rows
  as a refactor plan

#### Scenario: Model partition work is routed separately
- **WHEN** the problem is parent/child model evidence, multiple local models,
  or oversized model partitioning
- **THEN** the agent uses ModelMesh instead of reading mesh reports from
  Model-Test Alignment

### Requirement: Code boundary conformance review
The system SHALL provide a Model-Test Alignment helper that compares declared
model-backed code boundaries with real-code observations.

#### Scenario: Accepted inputs stay within the declared output boundary
- **WHEN** a `CodeBoundaryContract` declares allowed input cases, allowed
  outputs, allowed state writes, allowed side effects, and allowed error paths
- **AND** current `CodeBoundaryObservation` rows show real code accepting those
  input cases
- **THEN** the review verifies that every observed output, state write, side
  effect, and error path is declared by the boundary before allowing green
  boundary confidence

#### Scenario: Forbidden input is accepted
- **WHEN** a boundary declares an input case as rejected or forbidden
- **AND** a real-code observation shows that input case was accepted
- **THEN** the review reports a blocker instead of treating the code surface as
  conformant

#### Scenario: Missing input-gate evidence
- **WHEN** a boundary requires input-gate evidence for rejected input cases
- **AND** no current observation proves that a rejected input case is rejected
- **THEN** the review reports missing boundary evidence

#### Scenario: Extra runtime behavior is observed
- **WHEN** an exact boundary observation records an output, state write, side
  effect, or error path not declared by the boundary
- **THEN** the review reports an extra-behavior blocker

### Requirement: Boundary conformance feeds Model-Test Alignment
The system SHALL let `ModelTestAlignmentPlan` include code boundary contracts
and observations so boundary failures block model/test/code alignment claims.

#### Scenario: Alignment blocks on boundary failure
- **WHEN** a Model-Test Alignment plan includes boundary contracts and runtime
  observations
- **AND** the boundary review reports forbidden input acceptance, missing
  boundary evidence, extra output, extra error path, extra state write, extra
  side effect, stale observation, or non-passing observation
- **THEN** `review_model_test_alignment(...)` includes the boundary finding and
  returns a blocked decision

#### Scenario: Legacy plans remain compatible
- **WHEN** a Model-Test Alignment plan does not include boundary contracts or
  observations
- **THEN** existing model-test-only and model-test-code behavior remains
  unchanged

### Requirement: Boundary limits are explicit

Code-boundary conformance SHALL remain evidence about a declared boundary's
observed behavior. It SHALL NOT by itself prove that every critical runtime
state write path is mediated by a FlowGuard-backed gateway.

#### Scenario: Trace-level behavior is in scope
- **WHEN** the confidence claim depends on ordered production state, durable
  side effects, external systems, or adapter projection across multiple steps
- **THEN** code-boundary conformance may support the claim but MUST NOT replace
  conformance replay or equivalent production-facing validation

#### Scenario: Boundary report without writer inventory is scoped
- **WHEN** code-boundary conformance is green
- **AND** the project claims FlowGuard protects all critical runtime state
  writes
- **THEN** Model-Test Alignment evidence SHALL be treated as supporting evidence
  only
- **AND** Runtime Gateway Adoption evidence SHALL still be required for the
  runtime protection claim

### Requirement: Model-Test Alignment consumes workflow step contracts
FlowGuard SHALL allow Model-Test Alignment planning to consume workflow step contracts by projecting each required workflow step into a required model obligation with obligation type `workflow_step`.

#### Scenario: Required step has test evidence
- **WHEN** a projected workflow-step obligation has current passing test evidence of an allowed kind
- **THEN** Model-Test Alignment SHALL treat the obligation as covered using the existing evidence freshness and result-status rules

#### Scenario: Required step lacks test evidence
- **WHEN** a projected workflow-step obligation has no current passing test evidence
- **THEN** Model-Test Alignment SHALL report missing test evidence for that workflow-step obligation

