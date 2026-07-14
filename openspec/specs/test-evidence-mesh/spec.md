# test-evidence-mesh Specification

## Purpose
This capability defines FlowGuard's Test Evidence Mesh behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: Test partition ownership
FlowGuard SHALL allow projects to declare test partition items for behavior,
state, module, command, side effect, invariant, or release boundary coverage,
and SHALL assign each item to a parent test gate, child suite/script,
read-only suite, or shared kernel owner.

TestMesh SHALL be described as a parent/child test hierarchy mesh: a large test
script, suite, or validation flow is the parent boundary, while child suites or
child test scripts own validation regions. A child suite MAY itself become a
parent gate when its internal test structure grows large enough to split again.

#### Scenario: Complete test partition coverage
- **WHEN** every test partition item has a valid parent, child, read-only, or
  shared-kernel owner
- **THEN** TestMesh reports no coverage-gap finding for that parent suite

#### Scenario: Missing test partition owner
- **WHEN** a partition item has no owner
- **THEN** TestMesh reports a coverage-gap finding and does not return a green
  continue decision

#### Scenario: Child suite remains a contract at the parent layer
- **WHEN** a child suite contains many internal cases, fixtures, or state routes
- **THEN** the parent TestMesh consumes the child ownership and evidence
  contract instead of expanding every child case into the parent graph

### Requirement: Test suite evidence remains explicit
FlowGuard SHALL keep test result status, evidence tier, freshness, selected test
count, skipped tests, timeout status, background completion artifacts, and
not-run reasons visible before a child suite can support parent confidence.

#### Scenario: Stale suite evidence
- **WHEN** a child suite result is stale or foreign to the current source
- **THEN** TestMesh reports stale evidence and avoids counting that suite as
  current parent evidence

#### Scenario: Hidden skipped test
- **WHEN** a suite result claims success while skipped tests are not explicitly
  visible
- **THEN** TestMesh reports hidden skipped evidence instead of accepting the
  suite as green

### Requirement: Test evidence hierarchy exposes child evidence status

FlowGuard SHALL keep child test evidence status visible before a parent test
gate can support routine or release confidence.

#### Scenario: Parent gate requires leaf matrix-cell evidence
- **WHEN** a parent TestMesh declares required leaf matrix-cell ids
- **THEN** each required cell id MUST be owned by a registered child suite or
  script with current passing evidence
- **AND** missing, stale, skipped, running, progress-only, or background
  incomplete leaf-cell evidence MUST block parent confidence

#### Scenario: Leaf matrix-cell suite does not name cells
- **WHEN** a child suite is marked as leaf matrix-cell evidence but does not
  name which cell ids it proves
- **THEN** TestMesh MUST block with a missing leaf-cell ownership finding

### Requirement: Background completion is not progress
FlowGuard SHALL distinguish background progress output from completion evidence.

#### Scenario: Background progress without exit artifact
- **WHEN** a background test run has progress output but no exit/result artifact
- **THEN** TestMesh reports the background run as incomplete rather than passed

### Requirement: Duplicate ownership is blocked
FlowGuard SHALL reject test hierarchies where sibling suites both own the same
state write, side effect, or core validation partition unless the ownership is
read-only or explicitly shared-kernel.

#### Scenario: Duplicate state owner
- **WHEN** two child suites both own the same state or side-effect partition
- **THEN** TestMesh reports an ownership conflict and blocks green continuation

### Requirement: Routine and release gates are distinct
FlowGuard SHALL distinguish routine validation confidence from release
confidence so expensive release-only suites can be visible without blocking fast
routine checks.

#### Scenario: Routine scope with pending release-only suite
- **WHEN** routine validation is requested and a release-only suite is pending
- **THEN** TestMesh may return routine green while reporting the release
  obligation as deferred

#### Scenario: Release scope with missing release suite
- **WHEN** release validation is requested and a release-required suite is not
  current
- **THEN** TestMesh blocks release green confidence

### Requirement: TestMesh rejects invalid reused child suite evidence
TestMesh SHALL reject reused child-suite evidence before that suite supports a
parent test gate unless the suite has a current test-result reuse ticket and a
current proof artifact.

#### Scenario: Reused child suite supports parent
- **WHEN** a child suite is marked as reused
- **AND** its reuse ticket and proof artifact are current
- **AND** the suite otherwise has current passing evidence
- **THEN** TestMesh MAY count that child suite toward parent confidence

#### Scenario: Reused child suite lacks proof
- **WHEN** a child suite is marked as reused but has no reuse ticket or no
  proof artifact
- **THEN** TestMesh SHALL report a reuse-proof finding
- **AND** the child suite SHALL NOT support parent green confidence

#### Scenario: Background progress is not reusable completion
- **WHEN** a reused child suite only has progress output or lacks final
  background exit/result artifacts
- **THEN** TestMesh SHALL report incomplete background evidence rather than
  accepting the old result

### Requirement: Self-maintenance validation mesh
Test Evidence Mesh SHALL represent slow, large, release-only, stale, skipped, or background self-maintenance validations as parent/child evidence with freshness and result artifacts.

#### Scenario: Full regression times out
- **WHEN** full regression does not complete within the practical run window
- **THEN** Test Evidence Mesh SHALL record the timeout as a scoped gap and preserve focused child evidence instead of claiming parent pass

### Requirement: TestMesh leaf evidence preserves three-way targets

TestMesh SHALL preserve model obligation and code contract targets for leaf
test evidence instead of treating child-suite completion as semantic coverage.

#### Scenario: Leaf cell evidence supports a parent gate
- **WHEN** a child test suite owns a transition or matrix cell
- **THEN** the parent confidence still depends on Model-Test Alignment proving
  that the cell binds the model obligation, code contract, and test evidence.

### Requirement: TestMesh consumes transition coverage leaf-cell requirements
TestMesh SHALL accept required leaf-cell ids derived from transition coverage matrices and require child evidence for each required transition cell.

#### Scenario: Child suite owns transition cell
- **WHEN** a TestMesh child suite is marked as leaf matrix-cell evidence and owns a transition coverage cell id
- **THEN** current passing child evidence can satisfy the parent required cell id

#### Scenario: Missing transition cell evidence blocks parent confidence
- **WHEN** a required transition coverage cell has no current passing child owner
- **THEN** TestMesh SHALL block parent confidence with a missing leaf-cell evidence finding

### Requirement: TestMesh does not decide transition semantics
TestMesh SHALL track evidence hierarchy for transition coverage cells but SHALL NOT replace Model-Test Alignment for semantic obligation coverage.

#### Scenario: Parent mesh is green but semantic claim remains scoped
- **WHEN** TestMesh child evidence is current for required cell ids
- **THEN** the mesh can support evidence freshness
- **AND** Model-Test Alignment remains responsible for whether those cells cover the declared model obligations

### Requirement: TestMesh owns ModelMesh-derived leaf-cell evidence
TestMesh SHALL require current child-suite evidence for every required
ModelMesh-derived transition leaf-cell id before a parent validation gate can
support parent confidence.

#### Scenario: ModelMesh-derived cell has no child owner
- **WHEN** a TestMesh parent gate declares required leaf-cell ids generated from
  ModelMesh closure transitions
- **AND** no registered child suite owns one of those ids
- **THEN** TestMesh SHALL report missing leaf-cell evidence
- **AND** parent validation confidence SHALL be blocked

#### Scenario: Child suite owns retry/rejection cell
- **WHEN** a child suite owns a ModelMesh-derived retry/rejection leaf-cell id
- **AND** the suite has current passing evidence and final background artifacts
- **THEN** TestMesh MAY count that child evidence for parent evidence freshness
- **AND** Model-Test Alignment SHALL still own semantic model/code/test binding

### Requirement: TestMesh owns large payload evidence matrices
TestMesh SHALL allow large artifact payload validation matrices to be split
into child suites or scripts with explicit case ownership and current evidence.

#### Scenario: Child suite owns payload cases
- **WHEN** a parent validation gate declares required payload case ids
- **THEN** each required case id MUST be owned by a registered child suite or
  script with current passing evidence before parent confidence is green

#### Scenario: Payload matrix is too large for a flat claim
- **WHEN** payload validation includes many cases, slow cases, release-only
  cases, browser/manual-heavy cases, or background jobs
- **THEN** TestMesh MUST preserve child evidence status instead of allowing a
  flat green parent summary to hide stale, skipped, not-run, or scoped cases

### Requirement: TestMesh does not decide payload semantics
TestMesh SHALL preserve payload case ids and evidence freshness while leaving
payload semantics to Model-Test Alignment.

#### Scenario: Parent mesh is current but semantics are unbound
- **WHEN** child suites have current evidence for required payload case ids
- **THEN** TestMesh can support evidence freshness
- **AND** Model-Test Alignment remains responsible for deciding whether the
  evidence satisfies the artifact payload contract

### Requirement: TestMesh owns required contract-exhaustion child evidence
FlowGuard TestMesh MUST be able to treat canonical contract-exhaustion case ids
as required child-suite or leaf-cell evidence targets.

#### Scenario: Child suite owns generated case
- **WHEN** a parent validation claim depends on a generated contract-exhaustion
  case routed through TestMesh
- **THEN** a registered child suite or script owns the case id with current
  passing evidence

#### Scenario: Progress-only case evidence is insufficient
- **WHEN** a child suite reports only background progress for a required
  contract-exhaustion case
- **THEN** TestMesh does not count the case as completed evidence

### Requirement: TestMesh owns combination case shards
TestMesh SHALL treat generated ContractExhaustionMesh combination case ids and
coverage shard ids as required child-suite or leaf-cell evidence targets when
validation is large, slow, split, or parent-owned.

#### Scenario: Child suite owns combination cases
- **WHEN** a TestMesh parent gate declares required combination case ids
- **THEN** each required case id is owned by a registered child suite or shard
  with current passing evidence

#### Scenario: Missing shard evidence blocks parent validation
- **WHEN** a required coverage shard has no current passing result artifact
- **THEN** TestMesh reports missing shard evidence
- **AND** parent validation confidence remains blocked or scoped

### Requirement: Progress-only shard evidence is not completion
TestMesh SHALL keep background or progress-only shard evidence separate from
completion evidence for generated combination cases.

#### Scenario: Shard has progress but no exit artifact
- **WHEN** a shard run reports progress for generated combination cases
- **AND** no final exit or result artifact exists
- **THEN** TestMesh does not count that shard as passing evidence

### Requirement: TestMesh owns primary path coverage shards
TestMesh SHALL allow parent validation gates to require child suite ownership
for primary-path authority coverage shard ids.

#### Scenario: Child suite owns authority shard
- **WHEN** a child suite records current passing evidence for required
  primary-path authority shard ids
- **THEN** the parent TestMesh gate MAY consume that child evidence

#### Scenario: Unowned shard blocks parent confidence
- **WHEN** a parent gate requires a primary-path authority shard id and no
  child suite owns it with current passing evidence
- **THEN** TestMesh SHALL report the required cell as missing

### Requirement: Broad green test command is insufficient
TestMesh SHALL NOT treat a broad green regression command as primary-path
Cartesian proof unless child shard ownership and current evidence are visible.

#### Scenario: Parent gate lacks child shard evidence
- **WHEN** a parent test command passes but required primary-path shard ids are
  not mapped to child evidence
- **THEN** TestMesh SHALL keep the parent confidence blocked or scoped

### Requirement: TestMesh reconciles commitment coverage shards
FlowGuard SHALL let child suites own behavior commitment coverage shards while
the parent TestMesh reconciles all required commitment case ids.

#### Scenario: Child shard covers required case
- **WHEN** a child suite reports current evidence for a required commitment coverage case id
- **THEN** the parent TestMesh MAY count that case as covered

#### Scenario: Progress-only evidence is insufficient
- **WHEN** a child suite reports progress without the required commitment case ids
- **THEN** the parent TestMesh SHALL NOT treat commitment coverage as complete

### Requirement: Same-intent validation inventories require complete current evidence
FlowGuard TestMesh SHALL treat the complete required inventory for a stable
business intent as the parent evidence boundary. The inventory SHALL include
every required same-intent surface, materialized model/test obligation, family
member, transition cell, contract-exhaustion case, and coverage shard routed to
TestMesh. A caller-selected subset or a broad parent command SHALL NOT support
green confidence for the complete inventory.

#### Scenario: Complete inventory has current child evidence
- **WHEN** every required inventory item is owned by a registered child suite or
  shard with current passing evidence for the same inventory revision
- **THEN** TestMesh MAY treat the inventory evidence boundary as current
- **AND** semantic coverage remains owned by the corresponding Model-Test
  Alignment, ObligationFamily, Primary Path Authority, or ContractExhaustionMesh
  reviewer

#### Scenario: Required inventory item is omitted
- **WHEN** a same-intent validation inventory omits a required surface,
  materialized obligation, family member, transition cell, case, or shard
- **THEN** TestMesh MUST report incomplete required inventory evidence
- **AND** the parent gate MUST NOT return full green confidence

#### Scenario: Locally green subset is not complete coverage
- **WHEN** all declared child suites pass but the declared inventory does not
  prove completeness against its required source inventory
- **THEN** TestMesh MUST keep the parent confidence blocked or scoped instead
  of promoting the locally green subset

#### Scenario: Inventory changes after evidence
- **WHEN** the required inventory revision changes after child or shard evidence
  was produced
- **THEN** TestMesh MUST mark the affected evidence stale and require current
  evidence for the revised inventory

### Requirement: Background regressions provide liveness until a final receipt passes
TestMesh SHALL record background regression progress as liveness only. A
background run MUST NOT satisfy current passing evidence until a final receipt
records the run identity, terminal status or exit code, result artifact,
artifact fingerprint, covered inventory or shard ids, and covered artifact and
verifier versions.

#### Scenario: Background regression is still running
- **WHEN** a background regression emits progress, logs, a process id, or a
  heartbeat but has no final receipt
- **THEN** TestMesh MUST report liveness without counting the run as passed
- **AND** done, release, archive, and publish confidence MUST remain unsupported
  by that run

#### Scenario: Final receipt is incomplete or non-passing
- **WHEN** a background run has a receipt that lacks a terminal result artifact,
  fingerprint, covered required ids, or passing terminal status
- **THEN** TestMesh MUST treat the run as incomplete, failed, or stale according
  to the receipt instead of treating prior progress as completion

#### Scenario: Current final receipt covers the complete inventory
- **WHEN** a final receipt has a passing terminal status and current proof for
  every required inventory item or shard under the current artifact versions
- **THEN** TestMesh MAY count the run as current passing evidence for that
  declared TestMesh boundary

### Requirement: Plane-change validation has explicit owner receipts
The parent validation gate SHALL track focused schema/lookup tests, former-shape rejection tests, model regressions, skill/install parity, OpenSpec receipt consumption, and the one frozen full suite as explicit owner-receipt partitions. It SHALL NOT copy a native test command into a consumer or create an equivalent wrapper test.

#### Scenario: Focused receipts pass before the full gate
- **WHEN** focused plane owner receipts pass before source freeze
- **THEN** routine implementation MAY continue using those exact current receipts
- **AND** the full gate SHALL remain not-run until source/tool identities freeze

### Requirement: Native model regressions have one execution owner
Each native model regression SHALL retain its existing FlowGuard owner. SkillGuard/TestMesh MAY request a missing owner receipt and aggregate it, but SHALL NOT clone, wrap, or independently reschedule the native command.

#### Scenario: Consumer carries the owner command
- **WHEN** a receipt consumer or parent mesh declares the native command already owned by a child
- **THEN** contract validation SHALL fail before execution

#### Scenario: Functional input changes after an owner receipt
- **WHEN** an exact declared functional input changes
- **THEN** only the mapped owner receipt and its downstream aggregation SHALL become stale
- **AND** reports, receipts, logs, timestamps, installation bookkeeping, or task checkmarks SHALL NOT invalidate native test evidence

### Requirement: Installation parity is a distinct validation child
Canonical skill source, compiled contracts, and formal installed component projection SHALL have explicit parity evidence separate from skill source tests.

#### Scenario: Source skill passes but installed hash differs
- **WHEN** source checks pass and installed content differs from canonical content
- **THEN** the installation child SHALL fail or block parent completion

### Requirement: Parent completion consumes every required child
The parent plane-change validation gate SHALL read current passing evidence for every required child partition and SHALL preserve failures, timeouts, skips, not-run states, and stale results without reissuing equivalent child receipts.

#### Scenario: One affected model regression fails
- **WHEN** the full parent test command is green but an affected registered model child has a current failure
- **THEN** the parent SHALL remain blocked until the owning failure is repaired and rerun

### Requirement: TestMesh governs spec-check receipt children
TestMesh SHALL represent each required spec verification check as a child evidence owner with explicit consumers, execution status, reuse boundary, coverage, and freshness.

#### Scenario: Identical check has several consumers
- **WHEN** one current receipt satisfies several mapped tasks or obligations
- **THEN** TestMesh SHALL count one child execution and preserve all consumer references without duplicating evidence

#### Scenario: Unsafe cache hit is proposed
- **WHEN** a receipt lacks exact command/input/tool/environment/coverage identity or explicit cross-change permission
- **THEN** TestMesh SHALL report a reuse-proof blocker

### Requirement: TestMesh keeps spec-check states visible
Spec-check child evidence SHALL preserve `executed`, `reused-current`, `stale`, `not-run`, `blocked`, failed, skipped, timeout, and progress-only states.

#### Scenario: Parent summary is green with a hidden stale child
- **WHEN** any required child is stale, not-run, blocked, failed, skipped, timed out, or progress-only
- **THEN** the parent spec verification gate SHALL NOT claim current pass

