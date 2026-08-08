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
desktop, or manual evidence. Payload cases are synthetic inputs for the real
payload surface; passing evidence MUST identify concrete real-surface execution
proof before it can support alignment confidence.

#### Scenario: Payload contract is satisfied
- **WHEN** an `ArtifactPayloadContract` declares required payload cases and
  expected outputs, errors, state writes, side effects, or round-trip behavior
- **AND** current passing `ArtifactPayloadEvidence` covers every required case
  with external-contract scope
- **AND** each passing row resolves an evidence reference, producer receipt,
  result artifact, or equivalent independently verifiable real-surface proof
- **THEN** the payload validation report MAY support alignment confidence

#### Scenario: Required payload case is missing
- **WHEN** a required payload case has no current passing evidence
- **THEN** the payload validation report MUST include a missing-payload-evidence
  blocker

#### Scenario: Payload evidence lacks real execution proof
- **WHEN** a passing external payload row declares observed fields but has no
  resolvable evidence reference, producer receipt, result artifact, or
  equivalent real-surface execution proof
- **THEN** the payload validation report MUST include an execution-proof
  blocker
- **AND** that row MUST NOT support green payload confidence

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

### Requirement: Alignment consumes contract-exhaustion case ids
FlowGuard Model-Test Alignment MUST be able to bind model obligations, owner
code contracts, and test evidence to canonical contract-exhaustion case ids.

#### Scenario: Same-class test binds canonical case
- **WHEN** a same-class generalized test is required for a model-miss repair
- **THEN** the test evidence records the canonical ContractMutationCase id it
  covers

#### Scenario: Payload evidence binds canonical case
- **WHEN** payload validation evidence covers a generated contract-exhaustion
  payload mutation
- **THEN** Model-Test Alignment can compare the evidence against the payload
  contract and canonical case id

#### Scenario: Missing canonical case blocks coverage
- **WHEN** a required contract-exhaustion case exists but no current aligned
  test evidence covers it
- **THEN** Model-Test Alignment reports the coverage gap

### Requirement: Combination cases bind model, code, and tests
Model-Test Alignment SHALL treat every required ContractExhaustionMesh
combination case as a model obligation that must bind to an owner code contract
and current external-contract test evidence before full semantic alignment.

#### Scenario: Combination case lacks code contract
- **WHEN** a required generated combination case is projected into
  Model-Test Alignment
- **AND** no owner code contract implements that case's model obligation
- **THEN** alignment reports a code-contract gap

#### Scenario: Combination case lacks external test evidence
- **WHEN** a required generated combination case has a model obligation and code
  contract
- **AND** no current external-contract test evidence covers the case id
- **THEN** alignment reports a missing combination-case test evidence gap

### Requirement: Test evidence must cite generated case ids
Model-Test Alignment SHALL not count a test as covering Cartesian coverage
unless the test evidence cites the generated combination case id or a current
TestMesh shard that owns that case id.

#### Scenario: Helper-only test is insufficient
- **WHEN** test evidence passes but covers only an internal helper path and not
  the generated combination case id or owner code contract
- **THEN** Model-Test Alignment blocks full combination-case alignment

### Requirement: Suite Commitments Map To Owners And Tests
The suite-level alignment matrix SHALL map every registered external behavior commitment to one primary owner model, relevant owner code or prompt contract, negative/positive scenarios, TestMesh shard, and current evidence receipt. Source-to-commitment and commitment-to-source mappings MUST both be complete.

#### Scenario: Commitment has no owner code contract
- **WHEN** a model and ordinary test are green but the commitment has no mapped owner code or prompt contract
- **THEN** alignment fails that commitment rather than accepting the two green endpoints

#### Scenario: Source surface is unregistered
- **WHEN** README, CLI, prompt, route registry, contract, model, installer, or project-adoption behavior makes an external promise absent from the ledger
- **THEN** coverage-gap backfill reports the unmapped source surface

### Requirement: Path Sensitive Commitments Require PPA Evidence
Every behavior commitment marked `path_sensitive=true` SHALL consume a current Primary Path Authority receipt proving one runtime authority, visible primary failure, no automatic alternate success, ContractExhaustionMesh coverage, TestMesh shards, and Risk Evidence Ledger disposition.

#### Scenario: Alternate success path remains
- **WHEN** a path-sensitive commitment has a secondary automatic success route
- **THEN** the alignment row remains failing even if primary-path tests pass

### Requirement: Alignment Closure Requires Current TestMesh Receipts
Model-Test Alignment SHALL NOT treat test names, historical reports, or task completion as current evidence. Every required alignment row MUST reference a current TestMesh receipt whose assertion scope covers that row.

#### Scenario: TestMesh shard is stale
- **WHEN** a mapped owner prompt or code file changes after the TestMesh receipt
- **THEN** the alignment row becomes stale and blocks suite-level closure

### Requirement: Model-test alignment maps evidence to commitment ids
FlowGuard SHALL require behavioral test evidence to map to behavior commitment
ids when the claim is about user-visible or externally reliable behavior.

#### Scenario: Test maps to commitment
- **WHEN** a test proves behavior registered in the ledger
- **THEN** Model-Test Alignment SHALL record the commitment id alongside model and obligation ids

#### Scenario: Test lacks commitment mapping
- **WHEN** a broad behavior claim has tests only mapped to local model ids
- **THEN** Model-Test Alignment SHALL report that commitment coverage is incomplete

### Requirement: Repair groups reuse ordinary model-code-test alignment
Model-Test Alignment SHALL use its existing model obligations, primary owner code contracts, test evidence, freshness, and commitment bindings to prove every `affected_obligation_id` referenced by a process repair group. The repair group SHALL cite the corresponding current ordinary `owner_evidence_ids` and its required/current revalidation evidence. Model-Test Alignment SHALL NOT create a strategy-specific binding, cluster owner, or repair-batch owner.

#### Scenario: Repair group obligation has current ordinary alignment
- **WHEN** a repair group references an obligation whose primary code owner and current test evidence are present in the ordinary alignment plan
- **THEN** DPF may consume that alignment evidence for affected revalidation closure

#### Scenario: Repair group obligation lacks a primary owner
- **WHEN** a repair group references an obligation with no current primary owner code contract
- **THEN** ordinary Model-Test Alignment blocks closure without a strategy-specific fallback binding

### Requirement: Executable composition evidence maps from property to real regression
Model-Test Alignment SHALL preserve one chain from system property through affected slice, interaction case, minimal system trace step, component transition, and any declared code contract/runtime node to current external regression evidence. Code/runtime targets are optional non-semantic provenance at the model-checking layer; their presence, currentness, and production-conformance claim are owned here. Local component, token-composition, and executable-composition evidence MUST remain distinct.

#### Scenario: System failure becomes a regression target
- **WHEN** a bounded system check returns a counterexample
- **THEN** alignment creates stable targets for the owning property and each material trace step and binds them to real code/runtime/test evidence or visible gaps

#### Scenario: Unit tests are the only evidence
- **WHEN** local unit tests pass but no current executable-composition or mapped integration evidence covers the system property
- **THEN** alignment keeps the composite obligation open

### Requirement: Alignment evidence binds a model-system snapshot
Model-Test Alignment SHALL compare obligations, code contracts, scenarios,
invariants, hazards, source audits, and evidence against the exact model
instance and model-system snapshot identities they validate.

#### Scenario: Test is green against an older input inventory
- **WHEN** a test result passes but its resolved source inventory differs from the candidate or observed snapshot
- **THEN** alignment reports stale evidence and does not close the obligation

### Requirement: Alignment reports revision-set closure
For a model revision set, Model-Test Alignment SHALL report every required
member, relation, commitment, field, side effect, contract, test, and evidence
row as passed, blocked, failed, stale, skipped, or not run.

#### Scenario: One related contract is not run
- **WHEN** all changed models pass but one required affected code contract is not run
- **THEN** the aggregate revision-set result remains blocked

### Requirement: Alignment preserves one exact behavior authority identity
FlowGuard SHALL preserve and compare the stable `business_intent_id`, `behavior_commitment_id`, and selected `primary_path_id` across behavior-backed model obligations, UI transition obligations, runtime-path evidence, owner code contracts, and final binding rows.

#### Scenario: Exact authority identity aligns
- **WHEN** a required obligation, its behavior commitment, selected primary path, owner code contract, and current test or runtime evidence resolve to the same stable authority identity
- **THEN** Model-Test Alignment MAY report that authority binding as aligned
- **AND** the binding row SHALL expose the stable intent, commitment, and path ids

#### Scenario: Same intent drifts to another primary path
- **WHEN** two obligations or evidence rows name the same `business_intent_id` but resolve to different selected primary-path ids
- **THEN** Model-Test Alignment SHALL report same-intent primary-path drift
- **AND** it SHALL NOT treat both paths as valid owner implementations

#### Scenario: Authority identity is inferred only from text
- **WHEN** a path-sensitive alignment claim supplies a free-text intent, label, route, or function name without stable intent, commitment, and selected-path ids
- **THEN** Model-Test Alignment SHALL report incomplete behavior-authority identity
- **AND** broad alignment confidence SHALL remain unavailable

### Requirement: Family evidence proves the obligations used by alignment
FlowGuard SHALL accept obligation-family evidence for Model-Test Alignment only when each required family member is present and each accepted evidence row's `covered_obligations` resolves to the same concrete obligations used by the alignment plan.

#### Scenario: Family matrix and alignment obligations agree
- **WHEN** every expected family member is materialized
- **AND** each current family evidence row covers the corresponding alignment obligation ids with allowed provenance
- **THEN** Model-Test Alignment SHALL preserve the family-member, mechanism, and obligation binding in its report

#### Scenario: Family evidence names a different obligation
- **WHEN** a family cell is marked covered but its evidence does not list the aligned member obligation in `covered_obligations`
- **THEN** Model-Test Alignment SHALL report a family-to-alignment obligation mismatch
- **AND** the family cell SHALL NOT satisfy the aligned obligation

#### Scenario: Required family member is absent from alignment
- **WHEN** a family declares an expected required member but the alignment plan contains no obligation for that member and no explicit scoped disposition
- **THEN** Model-Test Alignment SHALL report the missing family member obligation
- **AND** full family-level alignment SHALL remain unavailable

### Requirement: Facade alignment proves delegation instead of parallel ownership
FlowGuard SHALL treat a retained facade, alias, adapter, or wrapper code contract for a path-sensitive business intent as a delegating boundary and SHALL require current evidence that it reaches the selected primary-path owner contract without becoming a second owner implementation.

#### Scenario: Facade contract delegates to the owner contract
- **WHEN** a facade code contract is retained for an external surface
- **AND** current model, runtime, and test evidence bind the facade to the selected primary path and its owner code contract
- **THEN** Model-Test Alignment MAY record the facade as a delegating contract
- **AND** the owner code contract SHALL remain the single primary implementation for that intent

#### Scenario: Facade owns independent success behavior
- **WHEN** a retained facade or adapter can return business success, mutate the business terminal, or perform the primary side effect without delegating to the selected owner contract
- **THEN** Model-Test Alignment SHALL report parallel facade ownership or alternate success
- **AND** the path-sensitive alignment SHALL remain blocked

#### Scenario: Facade delegation proof is not current
- **WHEN** the facade, owner code contract, selected primary path, or delegation evidence changes after the binding row was produced
- **THEN** Model-Test Alignment SHALL treat the facade binding as stale
- **AND** it SHALL require current delegation evidence before restoring alignment confidence

### Requirement: Plane-aware obligations bind model, owner code, and tests
Required behavior-plane, typed-relation, lookup, preflight, canonical-relation-derived, migration, and Model Miss obligations SHALL each bind one owner public code contract and current tests covering the same contract.

#### Scenario: Lookup obligation has external contract evidence
- **WHEN** plane-first lookup is required for the change claim
- **THEN** Model-Test Alignment SHALL bind the lookup obligation to the public lookup function/CLI contract and current same-plane/wrong-plane tests

#### Scenario: Internal scorer test is insufficient
- **WHEN** evidence tests only an internal token scorer and does not exercise the public lookup report boundary
- **THEN** alignment SHALL report an external-contract coverage gap

#### Scenario: Canonical relation contributes an alignment obligation
- **WHEN** a current canonical relation identifies an affected endpoint whose behavior is in scope
- **THEN** Model-Test Alignment SHALL derive the concrete obligation from that endpoint and bind it to the endpoint's current model owner, public code contract, and current tests
- **AND** the relation SHALL remain provenance rather than an independent obligation owner

#### Scenario: One plane-aware obligation is unbound
- **WHEN** a required obligation lacks a current model, code, or test binding
- **THEN** alignment remains blocked or scoped and the missing layer remains visible

### Requirement: Migration evidence covers source and disposition
Migration obligations SHALL bind dry-run/apply behavior, canonical output, unknown-custom-Python rejection, semantic parity, and old-authority retirement to the upgrader's public contract and current artifact evidence.

#### Scenario: New ledger loads but old authority remains
- **WHEN** tests prove canonical loading but do not prove retirement of the embedded inventory
- **THEN** alignment SHALL keep the migration closure target open

### Requirement: Model Miss evidence binds same-plane backfeed
Model Miss repair evidence SHALL prove existing same-plane commitment reuse, missing-commitment gap backfill, and multi-plane primary/related separation through the owner public code contract.

#### Scenario: Point miss test passes without same-class case
- **WHEN** only the observed port-bridge example is tested
- **THEN** alignment SHALL report missing same-class/ContractExhaustion evidence for the declared family claim

### Requirement: Stable target ids close wrong-plane counterexamples
Every concrete wrong-plane or unsafe-merge counterexample produced during implementation SHALL receive a stable target id and current known-bad replay or counterexample-regression evidence.

#### Scenario: Cross-plane false friend is repaired
- **WHEN** a prior similarity result merged product and agent models
- **THEN** current evidence SHALL replay the exact target id and prove the public relation now remains false-friend/manual-review

### Requirement: Every changed self-model obligation has explicit evidence disposition
Each changed self-model obligation SHALL identify a current executable evidence owner, an exact reusable receipt, or a visible `not_run` or `gap` disposition; model existence and broad regression membership SHALL NOT substitute for the relationship.

#### Scenario: Changed invariant lacks an evidence owner
- **WHEN** a changed invariant has no direct check, valid reuse identity, or explicit gap
- **THEN** model/test alignment remains incomplete

### Requirement: Pre-code test design and executed evidence are distinct
Model-test alignment SHALL distinguish planned obligations, oracle definitions, and known-bad cases prepared before implementation from test executions produced after implementation. Not-run planned evidence SHALL NOT be reported as executed or passing evidence.

#### Scenario: Oracle exists before implementation
- **WHEN** an obligation and oracle are defined but the implementation test has not run
- **THEN** alignment reports pre-code-ready and executed-evidence not-run

#### Scenario: Executed evidence targets another model identity
- **WHEN** a test passes against a model identity different from the current maturation identity
- **THEN** the evidence is stale for the current alignment claim

### Requirement: Structure recommendations bind to current model authority
Any model-derived code-structure recommendation used for implementation SHALL reference the exact current maturation and implementation-admission identities.

#### Scenario: Recommendation predates maturation revision
- **WHEN** the model or maturation identity changes after the structure recommendation
- **THEN** the recommendation is stale until re-derived or explicitly revalidated

### Requirement: Blueprint alignment is bidirectional over the independent source inventory
For a software-blueprint claim, Model-Test Alignment SHALL verify both that every required model obligation has one current primary implementation binding and that every behavior-bearing implementation surface has a model obligation, owner contract, or explicit non-behavior terminal disposition. Caller-declared CodeContracts SHALL NOT define the complete source denominator.

#### Scenario: Source entrypoint has no declared contract
- **WHEN** independent discovery finds a public or behavior-bearing entrypoint with no model or owner-contract binding
- **THEN** blueprint alignment is blocked as an unowned implementation surface

#### Scenario: Duplicate primary implementations claim one obligation
- **WHEN** two non-delegating implementation bindings claim primary ownership of the same obligation
- **THEN** blueprint alignment fails with duplicate ownership

### Requirement: Path and symbol binding is insufficient for blueprint closure
A blueprint-required implementation binding SHALL cite current source-independent semantic specifications and applicable oracles for its input/output behavior, state and effects, error behavior, and relevant order, retry, timeout, or decision rules. A path and symbol without those references SHALL remain traceability-only evidence.

#### Scenario: Function path exists without semantic specification
- **WHEN** a model obligation binds a current function path and symbol but lacks required semantic or oracle references
- **THEN** ordinary traceability may pass while static blueprint closure remains incomplete

#### Scenario: Hidden writer is discovered
- **WHEN** source discovery finds a state or effect writer not present in the bound semantic write inventory
- **THEN** alignment blocks the blueprint and identifies the writer

### Requirement: Deep blueprint rows bind model semantics code and tests exactly
For static blueprint qualification, Model-Test Alignment SHALL bind every in-scope model obligation through independent semantic evidence and one owner CodeContract to exact implementation surfaces and exact evidence producers. A producer SHALL be an independently re-discovered project test node with assertion-quality evidence or a bounded native model checker whose current project file is independently fingerprinted. Current execution receipts SHALL remain a separate evidence status and SHALL be required only for claims that say the current evidence executed successfully. Every identity and fingerprint consumed by either status SHALL remain explicit.

#### Scenario: One obligation has a complete current chain
- **WHEN** an obligation is linked to independent semantics, one current CodeContract, all implementing surfaces, exact current test nodes, and meaningful assertions
- **THEN** the row MAY report the static model-semantic-code-test binding complete
- **AND** the row exposes the consumed identities and fingerprints
- **AND** execution remains `not_run` until a separate current receipt exists

#### Scenario: A helper is found outside the declared binding
- **WHEN** independent implementation discovery finds a behavior-bearing helper consumed by an obligation but the alignment row omits it
- **THEN** the row remains incomplete and identifies the orphan implementation surface
- **AND** a passing test for another surface cannot substitute for the missing binding

#### Scenario: Test source exists without an executable node
- **WHEN** a test file is inventoried but its executable test node or collection identity is missing
- **THEN** the test remains an unresolved inventory item
- **AND** it does not satisfy the obligation row

### Requirement: Candidate test design and current evidence remain separate
Alignment SHALL distinguish candidate oracle and planned-test design from executed evidence for the current observed implementation. A future obligation MAY carry a planned test or falsifier, but its test status SHALL remain `planned` or `not_run` until the exact candidate implementation is executed and evidenced.

#### Scenario: A future obligation has a planned falsifier
- **WHEN** a candidate target includes a test design and oracle but no candidate execution receipt
- **THEN** the alignment row reports pre-code test design present and executed evidence `not_run`
- **AND** it does not present the future obligation as current-green

#### Scenario: A broad test command passes
- **WHEN** a parent pytest command passes but an in-scope obligation lacks an exact child test node and binding row
- **THEN** the parent result remains aggregate execution evidence only
- **AND** the missing row remains visible and blocks static model-code-test closure

#### Scenario: One accepted future obligation has no test owner
- **WHEN** an accepted candidate obligation has neither a falsifier and planned test owner nor an explicit scoped disposition
- **THEN** Model-Test Alignment reports an unresolved evidence owner
- **AND** candidate readiness remains blocked

### Requirement: Blueprint coverage binds exact test members and dimensions
For each behavior-bearing surface, blueprint alignment SHALL enumerate exact coverage rows containing model obligation, semantic rule, owner code contract, implementation surface, test node, assertion or native-check member, parameter or subtest case identity, covered dimensions, evidence role, oracle, execution owner, and terminal execution disposition.

#### Scenario: Owner test collection is copied to every surface
- **WHEN** a model owner has several behavior surfaces and a test collection does not enumerate which assertions cover which surfaces
- **THEN** alignment SHALL report missing exact coverage rows
- **AND** the collection SHALL NOT automatically cover every surface

#### Scenario: Native checker exists but has no current execution result
- **WHEN** a native checker member and runner fingerprint exist but no current terminal receipt is bound
- **THEN** static checker design SHALL remain visible
- **AND** execution status SHALL be `not_run` rather than `pass`

### Requirement: Test definition and execution evidence remain separate
Model-Test Alignment SHALL distinguish the admitted test source member, the checker or assertion definition, and the current terminal execution receipt. None of these identities SHALL substitute for another.

#### Scenario: Parent suite passed but leaf receipt is absent
- **WHEN** a parent suite reports pass but a required behavior coverage row lacks its exact leaf result or declared bounded delegation
- **THEN** the row SHALL remain incomplete for release confidence

### Requirement: Blueprint coverage has referential integrity
Every blueprint coverage edge SHALL resolve to a current behavior block, implementation surface, owner-declared concrete case, accepted case-and-dimension checker design, its current test-node or native-check owner, oracle identity, semantic rule, and exactly one covered dimension. The alignment review SHALL reject generated, missing, cross-owner, reused, stale, or mismatched references.

#### Scenario: Assertion belongs to another test node
- **WHEN** a coverage edge cites an oracle member whose owning test node differs from the edge's test node
- **THEN** alignment SHALL report the exact cross-test mismatch
- **AND** the edge SHALL NOT satisfy blueprint coverage

#### Scenario: Oracle does not cover a claimed dimension
- **WHEN** a coverage edge claims a behavior dimension absent from the cited oracle contract
- **THEN** alignment SHALL keep that dimension uncovered

### Requirement: Delegated oracle helpers are explicit
A delegated assertion helper SHALL count as an oracle member only when it is explicitly declared, its source identity is current, its call path terminates at current assertion or native-check members, and cycles or unresolved calls are absent.

#### Scenario: Test calls an unregistered assert-like helper
- **WHEN** a test invokes a helper whose name suggests an assertion but no current declaration and terminal oracle path exist
- **THEN** the helper SHALL remain supporting evidence only

### Requirement: Coverage design and execution are separate objects
The model-test alignment result SHALL preserve a formal static-design edge independently from its execution evidence. An owner-declared and accepted checker design assigned to a current test/native owner MAY be `not_run`; a generated, unaccepted, or ownerless checker SHALL remain a design gap rather than a formal edge.

#### Scenario: Planned test has no implementation member
- **WHEN** a case and expected oracle are proposed but no accepted checker design and current test/native owner exist
- **THEN** alignment SHALL report a planned checker gap
- **AND** it SHALL NOT serialize a passing or complete formal coverage edge

### Requirement: Blueprint coverage is exact per behavior and checker member
Each blueprint coverage row SHALL bind one behavior block, semantic rule, external owner contract, primary implementation surface, owner-declared good, boundary, or bad case, oracle, accepted dimension checker design, and an exact current test node or native-check member.

#### Scenario: Checker id exists without a real assertion target
- **WHEN** a checker has an id and fingerprint but no current source assertion, delegated assertion chain, or native-check member
- **THEN** its design status SHALL remain planned or incomplete
- **AND** it SHALL NOT satisfy static model-code-test closure

#### Scenario: Aggregate suite omits one behavior member
- **WHEN** a parent suite exits successfully but its covered-member set excludes one required behavior block
- **THEN** that block SHALL remain `not_run` or incomplete
- **AND** the parent exit SHALL NOT be copied into the missing row

### Requirement: Execution receipts retain exact owner and subject identity
Execution evidence SHALL bind the producer owner, request, model and implementation fingerprints, covered obligations and members, toolchain, environment, result, and terminal artifact. A receipt SHALL NOT be relabeled or copied to another owner or uncovered subject.

#### Scenario: One receipt is relabeled for two owners
- **WHEN** a passing receipt produced for owner A is copied with owner B in a consumer row
- **THEN** owner B SHALL be rejected for producer, subject, or covered-member mismatch

#### Scenario: Required test is skipped or collects zero members
- **WHEN** a required member is skipped, xfailed, not run, or the runner succeeds while collecting zero matching members
- **THEN** execution closure SHALL remain incomplete

### Requirement: Static design and current execution remain independent
Complete static checker design MAY exist without a current run, but a release or executed-evidence claim SHALL require exact current terminal receipts for every required owner and member.

#### Scenario: Complete design has no current execution
- **WHEN** every behavior row has a real test or native-check design but current receipts are absent
- **THEN** static design MAY be complete
- **AND** execution SHALL remain `not_run` without changing the static result

### Requirement: Coverage remains inside one exact behavior block
Every blueprint coverage edge SHALL consume a case, checker design, oracle, implementation surface, behavior contract, and coverage-contract owner belonging to the same exact behavior block. Coverage ownership SHALL come only from the exact owner declared by that coverage contract. Shared model ownership, test-node placement, suite membership, source-case lineage, or a passing owner-level test collection SHALL NOT authorize or reassign a coverage edge for a sibling block.

#### Scenario: Owner-level test is copied to every sibling
- **WHEN** one owner-level test or native checker is associated with several behavior blocks without block-local case and checker identities
- **THEN** Model-Test Alignment SHALL keep the affected sibling coverage incomplete
- **AND** it SHALL NOT copy the aggregate result into each behavior block

#### Scenario: Coverage cites a sibling case
- **WHEN** a coverage edge for behavior block A cites a case or checker declared for behavior block B
- **THEN** Model-Test Alignment SHALL reject the edge as a cross-block mismatch
- **AND** neither block SHALL receive coverage from that edge

#### Scenario: Block-local static design has not executed
- **WHEN** a behavior block has an exact case, checker design, oracle, and execution owner but no current terminal receipt
- **THEN** the block-local static design MAY remain complete
- **AND** its execution disposition SHALL remain `not_run`
- **AND** a parent, suite, or owner-level pass SHALL NOT change that disposition

#### Scenario: Planned cases share one model-level origin
- **WHEN** two sibling blocks derive planned cases from the same owner-level source case
- **THEN** each checker and coverage edge SHALL still bind its own exact block-local case identity
- **AND** the shared source lineage SHALL NOT be interpreted as permission to reuse one parameter-case or checker identity across the siblings

#### Scenario: Coverage owner is inferred from a test container
- **WHEN** a coverage edge names one contract owner but a test module, class, suite, parent model, or aggregate command is used to claim another owner
- **THEN** Model-Test Alignment SHALL reject the ownership mismatch
- **AND** only the coverage contract's exact current owner MAY own the edge and its execution evidence

#### Scenario: Parent execution is copied to sibling blocks
- **WHEN** a parent or aggregate checker has a current passing receipt but one or more child behavior coverage contracts lack their own exact terminal evidence
- **THEN** the parent execution SHALL remain evidence only for its declared coverage owner and subject
- **AND** every uncovered child execution SHALL remain `not_run`, incomplete, or blocked as appropriate

### Requirement: Binding blocker lookup is indexed once
Model-test alignment SHALL read the complete blocker finding sequence once to build exact lookup indexes by model obligation, code contract, and test evidence. Each binding row SHALL derive its blocker codes from those indexes. The indexed result SHALL preserve the same unique sorted blocker codes that a complete finding scan would produce.

#### Scenario: Many binding rows share one finding inventory
- **WHEN** one alignment review contains many model/code/test binding rows and blocker findings
- **THEN** every blocker finding SHALL be admitted to the exact lookup indexes once
- **AND** producing additional binding rows SHALL NOT rescan the complete finding sequence

#### Scenario: One finding identifies several binding dimensions
- **WHEN** a blocker finding identifies an obligation, code contract, or evidence item used by a binding row
- **THEN** that row SHALL contain the finding code exactly once in sorted order
- **AND** indexing SHALL NOT downgrade, discard, or duplicate the blocker

### Requirement: Delegated assertion helpers resolve recursively with lexical identity
A delegated assertion helper SHALL count toward a coverage contract only when its complete current call graph recursively terminates at exact assertion or native-check leaves. Every helper and leaf identity SHALL include its current source owner and lexically qualified identity so nested functions, methods, closures, and same-named helpers in different scopes remain distinct. Cycles, unresolved dynamic calls, ambiguous lexical owners, stale fingerprints, or a branch with no assertion leaf SHALL block the delegated coverage path.

#### Scenario: Nested helper reaches a real assertion leaf
- **WHEN** a coverage contract delegates through several current helpers and every recursive branch terminates at exact current assertion or native-check members
- **THEN** Model-Test Alignment MAY bind those leaves to the original coverage contract
- **AND** every intermediate helper SHALL retain its lexically qualified identity and call edge

#### Scenario: Two nested helpers share a short name
- **WHEN** two helpers have the same local function name but different enclosing functions, methods, modules, or source owners
- **THEN** they SHALL remain distinct delegated-helper identities
- **AND** a short-name match SHALL NOT merge their leaves, fingerprints, coverage, or execution evidence

#### Scenario: Recursive helper branch is unresolved
- **WHEN** any reachable delegated-helper branch cycles, resolves dynamically without current evidence, names a stale helper, or terminates without an assertion/native-check leaf
- **THEN** the exact coverage path SHALL remain incomplete or blocked
- **AND** a passing sibling branch SHALL NOT satisfy the unresolved branch

### Requirement: Helper delegation preserves coverage owner and execution layer
The exact owner declared by the coverage contract SHALL remain the coverage owner across all delegated helper edges. A helper, assertion leaf, test container, full parent, or aggregate suite SHALL NOT take ownership of the coverage contract or lend its result to another behavior. An accepted planned checker and complete helper graph SHALL remain static design; execution SHALL remain `not_run` until a current terminal receipt binds the exact coverage owner, behavior, case, leaf member, subject, and result.

#### Scenario: Helper is relabeled as coverage owner
- **WHEN** a delegated helper or assertion leaf is presented as the coverage owner instead of the owner declared by the coverage contract
- **THEN** Model-Test Alignment SHALL reject the ownership substitution
- **AND** the helper MAY remain only an exact delegated implementation member

#### Scenario: Planned checker has no leaf execution receipt
- **WHEN** the planned checker, helper graph, oracle, coverage owner, and leaf identities are complete but no exact current terminal receipt covers the leaf member
- **THEN** static design MAY remain accepted
- **AND** execution SHALL remain `not_run`

#### Scenario: Parent or suite pass is copied to the helper path
- **WHEN** a parent model or aggregate suite passes but the exact coverage owner and leaf member lack their own terminal execution evidence
- **THEN** the delegated path SHALL remain `not_run`, incomplete, or blocked
- **AND** the aggregate result SHALL remain evidence only for its own declared owner and subject

### Requirement: Canonical-relation-driven family evidence
Model-Test Alignment SHALL consume bounded canonical relation handoffs when a broad finite claim depends on exact sibling, shared-mechanism, same-intent, adapter-only, or evidence-duplicate endpoints. Every required endpoint SHALL bind to a concrete model obligation, owner code contract, and current test evidence, or to an explicit scoped disposition.

#### Scenario: Canonical sibling relation requires member evidence
- **WHEN** an alignment claim cites a current affected-sibling or shared-mechanism relation
- **THEN** the review requires current evidence for each in-scope endpoint obligation or a concrete scoped rationale
- **AND** it preserves the relation id, source authority, endpoint identities, and currentness

#### Scenario: Shared evidence cannot overclaim coverage
- **WHEN** two endpoint obligations cite the same evidence through an evidence-duplicate or shared-mechanism relation
- **THEN** the review accepts that evidence only for obligations whose external contract, mechanism, owner code, provenance, and freshness match its exact scope

#### Scenario: No current relation establishes the family
- **WHEN** a caller claims family-wide alignment from shared wording or shape without a current canonical relation and materialized members
- **THEN** Model-Test Alignment rejects the family-level claim and preserves the missing-relation gap

### Requirement: Canonical relation ids materialize into model-code-test alignment rows
Every in-scope canonical relation consumed by Model-Test Alignment SHALL materialize as concrete model obligations, owner code-contract bindings, test targets, or explicit scoped dispositions. An opaque relation id SHALL NOT satisfy model-code-test coverage.

#### Scenario: Canonical relation is fully materialized
- **WHEN** a canonical relation identifies impacted models or same-intent surfaces requiring code and test coverage
- **THEN** Model-Test Alignment resolves every in-scope endpoint to concrete ModelObligation, owner CodeContract, and current TestEvidence or binding rows
- **AND** the binding report exposes the originating relation and endpoint ids

#### Scenario: Relation id remains opaque
- **WHEN** an alignment plan lists a canonical relation but no concrete alignment row or scoped disposition consumes an in-scope endpoint
- **THEN** Model-Test Alignment reports an unmaterialized relation obligation
- **AND** the opaque id MUST NOT satisfy coverage

#### Scenario: Relation authority changes
- **WHEN** a relation source, endpoint, affected-member set, behavior plane, or currentness changes after alignment evidence was accepted
- **THEN** the dependent alignment rows become stale until rebound to the current relation identity

### Requirement: Path-quality obligations bind model code tests and oracles
Model-Test Alignment SHALL bind every hard semantic obligation and retained-element necessity witness affected by a path-quality decision to the same current model owner, code contract, test member, and executable oracle or explicit scoped disposition. Alignment SHALL verify binding and current evidence but SHALL NOT independently declare a path optimal.

#### Scenario: Equivalent contraction preserves obligations
- **WHEN** a model path removes, merges, delegates, or reorders elements under hard-semantic equivalence
- **THEN** current evidence covers every affected input, output, state, error, effect, order, retry, timeout, progress, permission, interface, intent, authority, oracle, and evidence obligation

#### Scenario: Necessity witness lacks evidence
- **WHEN** a retained element's witness has no current executable counterexample evidence
- **THEN** alignment reports that exact gap and broad activation remains blocked for the affected model
### Requirement: Supporting test provenance does not imply exact behavior coverage
A test node that is current and required but lacks one exact behavior/case/oracle/dimension edge SHALL remain `supporting`. Model-level test-file patterns MAY establish regression provenance, but SHALL NOT assign behavior owners to every test node in the file. Exact behavior coverage and native execution ownership SHALL continue through their dedicated typed edges.

#### Scenario: One test file appears in several model regression inputs
- **WHEN** a required test node belongs to a file referenced by multiple model owners but has no exact behavior coverage edge
- **THEN** the node SHALL remain supporting with no invented behavior owner
- **AND** the independent test inventory SHALL still preserve its exact source identity and required disposition
### Requirement: Supporting oracle implementation does not self-certify behavior
A supporting implementation binding MAY reference an oracle whose physical source is that same supporting surface only when the binding relation is explicitly `supports`, delegates to one exact current behavior owner, and creates no independent behavior contract. The inherited oracle reference SHALL provide owner traceability only. Every direct `implements` binding SHALL continue to require semantic and oracle sources independent from its implementation source.

#### Scenario: A native runner implements the oracle it delegates
- **WHEN** a current native runner is retained in the implementation denominator as a supporting surface and is also the physical source of the exact oracle used by its owner behavior
- **THEN** its typed supporting binding SHALL remain traceable without reporting oracle self-certification
- **AND** the runner SHALL NOT become an independent behavior block or relax source independence for the owner's direct implementation binding
