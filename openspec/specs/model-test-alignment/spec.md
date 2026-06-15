# model-test-alignment Specification

## Purpose
This capability defines how FlowGuard aligns model obligations, owner code contracts, and test evidence before granting implementation or release confidence.
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

### Requirement: Model-Test Alignment consumes family parity gates

Model-Test Alignment SHALL be able to consume declared obligation families and family evidence, then block alignment confidence when family parity or required provenance fails.

#### Scenario: Family parity blocks alignment
- **WHEN** a Model-Test Alignment plan includes an obligation family
- **AND** the family parity report has a missing required member/mechanism cell
- **THEN** the alignment report is not OK
- **AND** it includes a family parity finding.

#### Scenario: Complete family parity supports alignment
- **WHEN** every required family member/mechanism cell has current acceptable evidence
- **THEN** Model-Test Alignment does not add family parity blockers.

#### Scenario: Wrong provenance stays visible
- **WHEN** a test proves post-event behavior but does not prove the required event-generation mechanism
- **THEN** the alignment report keeps the provenance gap visible instead of counting that test as mechanism coverage.

### Requirement: Model-Test Alignment consumes runtime path evidence
Model-Test Alignment SHALL be able to consume runtime node contracts,
observations, and path alignment evidence when a model obligation or code
contract requires proof that real code followed the modeled workflow node.

#### Scenario: Runtime path evidence covers obligation
- **WHEN** a required model obligation declares required runtime node ids
- **AND** current passing runtime observations cover those node ids at the
  external contract boundary
- **THEN** Model-Test Alignment SHALL treat the runtime path evidence as
  supporting the declared obligation

#### Scenario: Runtime path evidence is missing
- **WHEN** a required model obligation declares required runtime node ids
- **AND** no current passing runtime observation covers one of those ids
- **THEN** Model-Test Alignment SHALL report missing runtime path evidence and
  SHALL NOT return green alignment

#### Scenario: Runtime path binding mismatch blocks alignment
- **WHEN** a runtime observation names a code contract or model obligation that
  does not match the aligned obligation/code contract pair
- **THEN** Model-Test Alignment SHALL report a runtime path binding mismatch

#### Scenario: Runtime path evidence remains independent from mesh routes
- **WHEN** Model-Test Alignment consumes runtime path rows
- **THEN** it SHALL NOT invoke ModelMesh, TestMesh, or StructureMesh, and SHALL
  leave parent/child proof decisions to their owning routes

### Requirement: Model-Test Alignment rejects invalid reused test evidence
Model-Test Alignment SHALL reject reused test evidence before it counts toward
model obligation or code contract coverage unless the evidence has a current
test-result reuse ticket and a current proof artifact.

#### Scenario: Reused evidence covers obligation
- **WHEN** a `TestEvidence` row is marked as reused
- **AND** its reuse ticket and proof artifact are current
- **AND** the proof artifact covers the same obligation ids as the evidence row
- **THEN** Model-Test Alignment SHALL allow the evidence to participate in
  obligation coverage

#### Scenario: Reused evidence lacks ticket
- **WHEN** a `TestEvidence` row is marked as reused but has no reuse ticket
- **THEN** Model-Test Alignment SHALL report a missing test-reuse ticket finding
- **AND** the row SHALL NOT silently support a green alignment claim

#### Scenario: Reused evidence has stale proof artifact
- **WHEN** reused `TestEvidence` references a stale, non-passing, progress-only,
  or fingerprint-missing proof artifact
- **THEN** Model-Test Alignment SHALL report the proof artifact gap before green
  alignment can be claimed

### Requirement: Self-maintenance obligation binding
Model-Test Alignment SHALL bind self-maintenance obligations to owner code contracts and current tests before broad claims are allowed.

#### Scenario: Field projection changes
- **WHEN** a field lifecycle projection changes
- **THEN** Model-Test Alignment SHALL require corresponding model obligation, owner code contract, and test evidence rows to be current

### Requirement: Model-Test Alignment consumes field projections
Model-Test Alignment SHALL consume field lifecycle projections so
behavior-bearing field obligations bind the same model obligation, owner code
contract, and external-contract test evidence.

#### Scenario: Field projection is fully aligned
- **WHEN** a behavior-bearing field projection names a model obligation and
  owner code contract
- **AND** current passing external-contract test evidence covers the same
  obligation and code contract
- **THEN** Model-Test Alignment MAY count the field projection as covered

#### Scenario: Field code owner is missing
- **WHEN** a required field projection has no owner code contract
- **THEN** Model-Test Alignment MUST report a missing field code contract
  finding and MUST NOT return green alignment for that field obligation

#### Scenario: Field test proves only an internal helper
- **WHEN** test evidence covers a field projection only through an internal
  helper path and not the external contract boundary
- **THEN** Model-Test Alignment MUST keep the field obligation blocked or
  scoped according to the existing assertion-scope rules

### Requirement: Full confidence requires model-code-test binding by default

Model-Test Alignment SHALL require required model obligations, owner code
contracts, and current passing test evidence to bind together by default before
reporting full green confidence.

#### Scenario: Required obligation has code and test bound together
- **WHEN** a required model obligation has an owner code contract
- **AND** current passing test evidence covers both that obligation and that
  owner code contract
- **THEN** Model-Test Alignment can treat that row as locked.

#### Scenario: Required obligation has no code owner
- **WHEN** a required model obligation has no owner code contract
- **THEN** Model-Test Alignment SHALL report a blocker.

#### Scenario: Test covers model but not code
- **WHEN** current passing test evidence covers a required model obligation
- **AND** it does not cover a code contract implementing that obligation
- **THEN** Model-Test Alignment SHALL report a blocker.

#### Scenario: Test binds the wrong code contract
- **WHEN** test evidence covers model obligation A
- **AND** the evidence covers a code contract that does not implement A
- **THEN** Model-Test Alignment SHALL report a blocker.

### Requirement: No compatibility switch for model-test-only green

FlowGuard SHALL NOT provide a compatibility switch that allows required
model-test-only evidence to produce full Model-Test Alignment green confidence.

#### Scenario: Model-test-only evidence is present
- **WHEN** an obligation and test evidence are both present
- **AND** no owner code contract is present
- **THEN** the result is blocked or scoped, not full green.

### Requirement: Binding report rows expose the lock state

Model-Test Alignment SHALL expose model-code-test binding rows that identify the
model obligation id, code contract id, test evidence id, status, and gap reasons.

#### Scenario: Human reads alignment output
- **WHEN** the alignment report is formatted or serialized
- **THEN** each required model obligation has visible binding status.

### Requirement: Model-Test Alignment consumes transition coverage obligations
Model-Test Alignment SHALL support obligations generated from transition coverage cells and apply the same evidence freshness, status, required-kind, and target-id rules as hand-authored obligations.

#### Scenario: Transition obligation has evidence
- **WHEN** a transition-derived obligation has current passing test evidence of an allowed required kind
- **THEN** Model-Test Alignment SHALL treat the transition obligation as covered

#### Scenario: Transition obligation lacks evidence
- **WHEN** a transition-derived obligation has no current passing test evidence
- **THEN** Model-Test Alignment SHALL report missing test evidence for that transition obligation

#### Scenario: Transition cell evidence names target
- **WHEN** a test evidence row is marked as leaf matrix-cell or transition-cell evidence
- **THEN** it MUST identify the target cell id before it can support the transition-derived obligation

### Requirement: Transition coverage stays independent from TestMesh
Model-Test Alignment SHALL evaluate transition-derived obligations directly for ordinary evidence and SHALL route large or slow evidence hierarchy to TestMesh instead of becoming a mesh route.

#### Scenario: Ordinary transition coverage does not require TestMesh
- **WHEN** the matrix is small and ordinary tests provide evidence
- **THEN** Model-Test Alignment can review transition-derived obligations without requiring a TestMesh plan

#### Scenario: Large transition coverage routes outward
- **WHEN** the matrix is large, slow, layered, stale-prone, or release-only
- **THEN** agents use TestMesh for child-suite evidence ownership while Model-Test Alignment keeps semantic obligations visible

### Requirement: Model-test alignment treats unknown cases as boundary obligations

FlowGuard SHALL guide model-test alignment users to include representative
unknown/other cases when a model or code contract has an open external boundary.

#### Scenario: Unknown boundary cases are visible in alignment guidance

- **GIVEN** a model obligation or code boundary contract accepts finite inputs
- **WHEN** an outside-enumeration input may occur
- **THEN** model-test alignment guidance MUST ask for explicit unknown handling,
  boundary observations, tests, or a state closure report
- **AND** it MUST route unresolved unknown cases to model maturation rather than
  treating them as optional human review.

### Requirement: Similarity-driven family evidence
Model-Test Alignment SHALL be able to consume same-family-variant and
evidence-duplicate model-similarity relations when a broad same-class claim
depends on sibling model obligations or shared mechanism evidence.

#### Scenario: Family variant requires sibling evidence
- **WHEN** a model-test alignment plan claims a same-class family and cites a
  same-family-variant similarity relation
- **THEN** the review requires current evidence for each in-scope family member
  or a scoped/exempt rationale for members outside the current claim

#### Scenario: Maintenance group requires shared and variant test obligations
- **WHEN** a model-test alignment plan claims coverage for a similarity
  maintenance group
- **THEN** the plan records shared and variant test obligation ids or equivalent
  obligation-family evidence before claiming the similar workflows are covered

#### Scenario: Evidence duplicate cannot overclaim coverage
- **WHEN** two model obligations cite the same evidence through an
  evidence-duplicate similarity relation
- **THEN** the review accepts the evidence only for obligations whose external
  contract, mechanism, provenance, and freshness match the evidence scope

### Requirement: Model-Test Alignment consumes ModelMesh-derived transition cells
Model-Test Alignment SHALL treat ModelMesh-derived transition coverage cells as
ordinary required transition obligations and apply the existing code-contract,
evidence freshness, required-kind, target-id, and assertion-scope rules.

#### Scenario: ModelMesh-derived transition lacks test evidence
- **WHEN** a ModelMesh-derived transition obligation is required
- **AND** no current passing test evidence covers the matching transition cell
- **THEN** Model-Test Alignment SHALL report missing test evidence

#### Scenario: Rejection retry evidence is incomplete
- **WHEN** a ModelMesh-derived retry/rejection transition requires failure,
  negative, and replay evidence
- **AND** the bound tests only cover the happy path
- **THEN** Model-Test Alignment SHALL report missing required test kinds

#### Scenario: Fake-agent packet evidence remains scoped
- **WHEN** test evidence for a ModelMesh-derived AI packet handoff is synthetic
  or fake-agent-only
- **THEN** Model-Test Alignment SHALL treat it as contract or control-flow
  evidence unless a real external-contract assertion scope is supplied

### Requirement: Artifact payload validation review
Model-Test Alignment SHALL provide artifact payload contract and evidence
helpers that compare declared payload cases with current test, replay, browser,
desktop, or manual evidence.

#### Scenario: Payload contract is satisfied
- **WHEN** an `ArtifactPayloadContract` declares required payload cases and
  expected outputs, errors, state writes, side effects, or round-trip behavior
- **AND** current passing `ArtifactPayloadEvidence` covers every required case
  with external-contract scope
- **THEN** the payload validation report MAY support alignment confidence

#### Scenario: Required payload case is missing
- **WHEN** a required payload case has no current passing evidence
- **THEN** the payload validation report MUST include a missing-payload-evidence
  blocker

#### Scenario: Payload evidence is stale or non-passing
- **WHEN** payload evidence is stale, skipped, failed, timeout, not-run,
  running, progress-only, or error
- **THEN** it MUST NOT count toward payload coverage

#### Scenario: Payload output mismatches contract
- **WHEN** payload evidence observes an output, error path, state write, side
  effect, or round-trip result outside the declared contract
- **THEN** the payload validation report MUST include a mismatch blocker

### Requirement: Payload validation feeds Model-Test Alignment
Model-Test Alignment SHALL let plans include artifact payload contracts and
evidence so payload failures block model/test/code alignment claims.

#### Scenario: Alignment blocks on payload failure
- **WHEN** a Model-Test Alignment plan includes payload contracts or evidence
- **AND** payload validation reports missing, stale, non-passing, scoped, or
  mismatched evidence
- **THEN** `review_model_test_alignment(...)` MUST include equivalent findings
  and return a blocked or scoped decision

#### Scenario: Legacy plans remain compatible
- **WHEN** a Model-Test Alignment plan has no artifact payload contracts or
  evidence
- **THEN** existing model-test, code-contract, boundary, field, and runtime-path
  behavior remains unchanged

