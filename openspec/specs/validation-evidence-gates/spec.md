# validation-evidence-gates Specification

## Purpose
Define validation evidence gates for UI click-through, artifact payloads,
manual/native boundaries, installed prompt synchronization, and proof artifacts
so broad confidence cannot rest on planned, fake, stale, or incomplete checks.
## Requirements
### Requirement: Cross-route validation evidence gate
The retained `validation_evidence_gates` model SHALL represent the permanent evidence-kernel contract rather than an implementation rollout. It SHALL bind current evidence primitives, field structures, lifecycle, receipts, proof artifacts, validation ownership, and terminal results to their real code, tests, and normative specifications. It SHALL preserve stale, failed, skipped, not-run, progress-only, duplicate-owner, foreign-owner, and proof-fingerprint mismatch states as non-terminal evidence and SHALL require the current-head identity to match the terminal receipt before a broad claim. UI click-through, payload-domain semantics, manual operability, installed-skill synchronization, and release order SHALL remain delegated to their existing specialist owners.

#### Scenario: Rollout milestones are offered as current evidence behavior
- **WHEN** the retained model reaches success only because documentation, prompt, installation, or one-time rollout flags are set
- **THEN** current evidence-kernel purpose closure is blocked

#### Scenario: Real evidence implementation changes
- **WHEN** an owned evidence primitive, lifecycle, receipt, proof, ownership, result, test, or normative spec changes
- **THEN** the model-regression input identity becomes stale and the old evidence-kernel result cannot support current DNA

#### Scenario: Progress or skipped work is presented as terminal success
- **WHEN** a receipt is progress-only or hides failed, skipped, or not-run child work
- **THEN** the evidence model rejects terminal success and preserves the exact non-pass identities

#### Scenario: Ordinary validation would purge evidence automatically
- **WHEN** an ordinary run proposes automatic persistent evidence deletion without the recoverable lifecycle owner and explicit boundary
- **THEN** the model rejects the operation rather than treating cleanup as validation

### Requirement: Representative synthetic payload packs
FlowGuard SHALL require representative synthetic payload packs when artifact
payload behavior is part of a broad confidence claim.

#### Scenario: Payload cases are declared
- **WHEN** a file format, import/export flow, or AI work package is in scope
- **THEN** the evidence plan MUST name representative valid, empty or missing,
  malformed, unknown-field, old-version, round-trip, and boundary cases or
  state why a case is out of scope

#### Scenario: Payload pack is missing
- **WHEN** a payload-bearing claim has no current synthetic payload evidence
- **THEN** the claim MUST remain scoped or blocked until evidence exists

### Requirement: Conditional manual review gate
FlowGuard SHALL require manual evidence only for boundaries that automation
cannot inspect reliably.

#### Scenario: Native or external boundary is not automatable
- **WHEN** a native file picker, download target, clipboard, desktop shell,
  third-party login, system permission, or human visual judgment is required
- **THEN** the validation plan MUST include structured manual evidence or an
  explicit blindspot

#### Scenario: Automated evidence covers the boundary
- **WHEN** browser, desktop, replay, or test evidence fully covers the declared
  boundary
- **THEN** FlowGuard MUST NOT require extra manual review only for ceremony

### Requirement: Final confidence consumes UI and payload gates
FlowGuard final broad confidence SHALL consume UI action and artifact payload
gate evidence when those risks are in scope.

#### Scenario: Final claim lacks gate evidence
- **WHEN** a risk row names implemented UI or artifact payload behavior
- **AND** no current route evidence or scoped blindspot is attached
- **THEN** final confidence MUST be blocked or scoped

### Requirement: Terminal validation output is compact and artifact-backed
Validation aggregators SHALL emit a compact terminal envelope by default while
preserving complete canonical results and complete captured streams in
immutable result artifacts.

#### Scenario: Every child passes
- **WHEN** a validation aggregation completes successfully
- **THEN** terminal output SHALL include status, counts, run and result
  identities, result path and hash, and zero non-pass child ids without
  embedding successful child stdout or duplicate parsed payloads

#### Scenario: A child does not pass
- **WHEN** a child is failed, blocked, stale, skipped, timed out, cancelled, or
  not run
- **THEN** the terminal envelope SHALL identify that child and preserve a
  bounded diagnostic plus the complete result-artifact reference

#### Scenario: Full evidence is needed
- **WHEN** a consumer needs successful child details
- **THEN** it SHALL read the referenced canonical result artifact rather than
  invoke an alternate verbose success authority

### Requirement: Successful diagnostics do not duplicate streams
Persistent evidence receipts SHALL retain complete deterministic stream
sidecars but SHALL NOT copy a success-tail diagnostic into every nested result
row.

#### Scenario: Producer exits successfully
- **WHEN** complete stdout and stderr objects have been stored and fingerprinted
- **THEN** the bounded receipt diagnostic MAY be empty and SHALL preserve the
  object identities needed for audit

### Requirement: Parallel model execution is proof-gated
An isolated-output model regression SHALL be marked shard-safe only when a
current executable proof demonstrates serial/parallel semantic equivalence,
disjoint artifact ownership, stable input identities, and zero shared
repository mutation.

#### Scenario: The UI aggregate is proposed for parallel execution
- **WHEN** its manifest entry changes to `shard_safe=true`
- **THEN** the entry SHALL identify a machine-checkable proof contract and the
  proof SHALL run one serial baseline plus at least two simultaneous isolated
  copies

#### Scenario: A concurrent copy changes shared state
- **WHEN** the proof observes a repository mutation, overlapping output path,
  changed input fingerprint, non-terminal child, or semantic mismatch
- **THEN** the proof SHALL fail and the model SHALL remain ineligible for
  parallel regression execution

#### Scenario: The proof passes
- **WHEN** every copy passes with equivalent projected results, disjoint
  artifacts, current inputs, and no repository mutation
- **THEN** the receipt SHALL bind the model id, proof contract, source
  fingerprint, result projections, and claim boundary for the current release

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
