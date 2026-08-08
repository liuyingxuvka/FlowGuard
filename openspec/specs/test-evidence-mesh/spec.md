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

#### Scenario: Release-owner timeout is shorter than observed normal runtime
- **WHEN** a required release suite normally exceeds its configured owner timeout under current supported conditions
- **THEN** Test Evidence Mesh SHALL reject the timeout budget as undersized before using that owner plan for release confidence

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

### Requirement: TestMesh preserves diagnostic campaign topology
TestMesh SHALL record campaign id, `diagnostic_boundary`, planned/executed/failed/not-run counts, visible not-run reason, and stable Finding Ledger ids on child evidence without choosing a process candidate, grouping failures, or executing the child. It SHALL NOT expose the former six-policy execution field, strategy observations, or failure-cluster ids.

#### Scenario: Budgeted child stops visibly
- **WHEN** a child suite reaches a valid `budgeted` stop condition
- **THEN** TestMesh keeps its terminal result, not-run count, reason, and finding ids without reporting declared completeness

#### Scenario: Hard blocker invalidates descendants
- **WHEN** a hard prerequisite failure makes descendant checks invalid
- **THEN** TestMesh records those descendants as not run with the blocker reason and does not require them to execute

### Requirement: Campaign completeness claims are checked
TestMesh SHALL require `planned_count == executed_count + not_run_count` and `failed_count <= executed_count`. It SHALL block a `declared_complete` claim when `not_run_count` is nonzero or failures lack stable finding references. `targeted` and `budgeted` boundaries MAY have not-run items only with visible reasons.

#### Scenario: Unaccounted planned test
- **WHEN** planned count is greater than executed plus not-run count
- **THEN** TestMesh reports a campaign coverage blocker

#### Scenario: Declared-complete campaign has a not-run item
- **WHEN** `diagnostic_boundary=declared_complete` and `not_run_count` is nonzero
- **THEN** TestMesh rejects the completeness claim even when the executed tests passed

### Requirement: TestMesh preserves composite execution identity and completeness
TestMesh SHALL preserve system-definition, request, slice, component, compiled-model, scheduler/bound, truncation, and trace identities through the existing `ProofArtifactRef.artifact_fingerprints` map plus stable case/shard ids, explored-state count, terminal artifacts, and exactly one execution owner for long or background executable-composition checks. New system-specific generic receipt fields SHALL be added only if focused evidence proves the existing fingerprint map cannot represent the identity.

#### Scenario: Background composite run completes
- **WHEN** a background run has a terminal result, exit status, complete stdout/stderr evidence, covered ids, and matching inventory/source identities
- **THEN** TestMesh may expose that current receipt to its parent gate

#### Scenario: Composite run only reports progress
- **WHEN** a PID, log, heartbeat, or explored-state count exists without terminal artifacts
- **THEN** TestMesh reports liveness only and cannot project executable-composition pass

#### Scenario: Exploration is truncated
- **WHEN** the final receipt records an unexplored frontier
- **THEN** TestMesh preserves blocked status and cannot count the selected cases as complete passing evidence

### Requirement: Test receipts bind resolved inputs and snapshot subject
TestMesh SHALL retain the exact resolved input paths and hashes, model-instance
fingerprints, snapshot fingerprint, software subject revision, execution owner,
terminal result, skipped rows, and claim boundary for every evidence shard used
by model-system activation.

#### Scenario: Input glob resolves differently after execution
- **WHEN** the current resolved files or hashes differ from the input inventory recorded by a passing shard
- **THEN** TestMesh marks that shard stale even when the original glob expression is unchanged

### Requirement: Full validation has singular execution owners
One frozen source snapshot SHALL have at most one all-model regression execution
owner and at most one full-test execution owner. Consumers SHALL reuse their
terminal receipts and MUST NOT launch equivalent duplicate owners.

#### Scenario: A background owner is still running
- **WHEN** the process is live but no terminal receipt exists
- **THEN** TestMesh reports running rather than passed and downstream release gates remain blocked

### Requirement: Test evidence binds the complete coverage inventory
Before broad behavior confidence, TestMesh SHALL bind its parent gate to the exact current coverage inventory identity, revision, and fingerprint produced by the shared behavior reconciliation. Every required test or evidence identity derived from a `modeled` or `delegated` expected item SHALL have exactly one native child owner and an explicit current state. A caller-selected green subset SHALL NOT establish complete evidence coverage.

#### Scenario: A green subset omits a required child
- **WHEN** all selected tests pass but the bound coverage inventory requires an additional test or evidence child
- **THEN** TestMesh SHALL keep the parent gate incomplete and SHALL identify the missing child owner

#### Scenario: The coverage inventory changes
- **WHEN** the expected inventory or any modeled, delegated, or scoped disposition changes after a TestMesh result
- **THEN** the affected TestMesh parent and child evidence SHALL become stale according to their declared dependency edges

### Requirement: Coverage dispositions determine evidence ownership
TestMesh SHALL preserve the evidence consequence of every shared coverage disposition. `modeled` items SHALL bind to current model and test evidence, `delegated` items SHALL bind to the exact current evidence owned by the delegated native route, and `scoped` items SHALL remain visible with their boundary and SHALL NOT be projected as passed tests.

#### Scenario: A delegated item lacks native evidence
- **WHEN** an expected item is delegated to a specialist inventory but its required native evidence is missing, stale, skipped, blocked, or not run
- **THEN** TestMesh SHALL preserve that state and SHALL NOT synthesize a passing child from the delegation itself

#### Scenario: An item is intentionally scoped
- **WHEN** an expected item has a valid scoped disposition
- **THEN** TestMesh SHALL retain the scope boundary in the parent accounting without manufacturing an executed test result

### Requirement: Work context and provider status are not test evidence
WorkContext artifacts, provider status, proposals, plans, tasks, checkboxes, and completion markers SHALL be treated as read-only planning context rather than test execution evidence, execution-owner receipts, or reuse authority. An actual provider-native validator MAY appear as ordinary TestMesh evidence only when it ran under a separately declared native execution owner with exact terminal identity, inputs, and freshness.

#### Scenario: A provider task list is complete
- **WHEN** OpenSpec, Spec Kit, Superpowers, a declared-file profile, or another provider reports that all planning tasks are complete
- **THEN** TestMesh SHALL NOT mark any FlowGuard model, test, replay, or native validation child as passed solely from that status

#### Scenario: A provider-native validator executes
- **WHEN** a provider-native validator runs under its own declared execution owner and produces current terminal evidence
- **THEN** TestMesh MAY reference that evidence as an ordinary native child while WorkContext itself remains non-executing and receipt-free

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

### Requirement: Plane-upgrade validation has explicit child partitions
The parent validation gate SHALL track focused schema/lookup tests, migration tests, model regressions, skill/install parity, OpenSpec verification, and the full test suite as explicit child evidence partitions.

#### Scenario: Focused tests pass while full suite runs
- **WHEN** focused plane tests pass and a full suite is still running in the background
- **THEN** routine implementation MAY continue using the focused evidence
- **AND** full completion SHALL remain pending until final full-suite artifacts and exit status exist

### Requirement: Background model regressions expose liveness and final receipts separately
Background model-regression output SHALL be liveness-only until the registered runner writes final result/receipt artifacts with current source fingerprints and exit status.

#### Scenario: Background log is growing
- **WHEN** a regression process emits progress but has no final receipt
- **THEN** TestMesh SHALL report the child as running, not passed

#### Scenario: Peer write occurs during regression
- **WHEN** a watched source/model/test/prompt file changes after a background run starts
- **THEN** the affected result SHALL be stale and rerun or explicitly scoped before parent confidence

### Requirement: Installation parity is a distinct validation child
Canonical skill source, compiled contracts, shadow installation, and formal installed layout SHALL have explicit parity evidence separate from skill source tests.

#### Scenario: Source skill passes but installed hash differs
- **WHEN** source checks pass and installed content differs from canonical content
- **THEN** the installation child SHALL fail or block parent completion

### Requirement: Parent completion consumes every required child
The parent plane-upgrade validation gate SHALL consume current passing evidence for every required child partition and SHALL preserve failures, timeouts, skips, not-run states, and stale results.

#### Scenario: One affected model regression fails
- **WHEN** the full parent test command is green but an affected registered model child has a current failure
- **THEN** the parent SHALL remain blocked until the owning failure is repaired and rerun

### Requirement: TestMesh preserves payload execution proof
TestMesh SHALL preserve payload contract ids, case ids, real surface ids,
result artifact paths, observed payload fingerprints, oracle outcomes, and
independently verifiable execution-proof references when it owns large payload
validation matrices.

#### Scenario: Payload child suite feeds alignment
- **WHEN** a child suite owns a payload case for a file or work-package surface
- **THEN** child evidence identifies the real-surface execution proof that
  Model-Test Alignment can independently consume
- **AND** TestMesh does not treat case ownership, expected payloads, or
  synthetic case generation alone as semantic payload proof

### Requirement: Triggered test obligations contribute to maturation
TestMesh SHALL project its independently required test cells, child owners, current terminal results, stale evidence, skipped work, and not-run work into task-local maturation when layered or slow validation is triggered.

#### Scenario: Planned or running test is not passing evidence
- **WHEN** a required test is planned, not-run, running, progress-only, skipped, stale, failed, or lacks terminal artifacts
- **THEN** maturation MUST preserve the corresponding evidence gap and MUST NOT count it as current passing coverage

### Requirement: Project test inventory preserves exact executable evidence identities
TestMesh SHALL consume a project test inventory that distinguishes test source files, executable test nodes, assertion identities and quality, and static freshness. When execution is requested, TestMesh SHALL additionally preserve collection or selection identity, environment and toolchain fingerprints, execution receipts, and execution freshness. Every required test member SHALL have one explicit owner and terminal static disposition; execution status remains separate and may be `not_run`.

#### Scenario: One test file contains several executable tests
- **WHEN** test discovery finds multiple executable nodes in one source file
- **THEN** the inventory assigns each node a stable identity and preserves its source relationship
- **AND** file presence alone does not prove execution of every node

#### Scenario: A test executes without a meaningful assertion
- **WHEN** an executable test node runs successfully but its assertion audit finds no oracle-bearing assertion for the claimed obligation
- **THEN** TestMesh reports the execution separately from assertion quality
- **AND** the node cannot close that obligation's evidence row

#### Scenario: A receipt targets a stale source or collection
- **WHEN** a passing receipt names a different test source, executable-node set, collection identity, toolchain, or subject fingerprint
- **THEN** the receipt is stale for the current project test inventory
- **AND** it is not reused as current evidence

### Requirement: Broad parent results never manufacture missing child coverage
A broad suite result SHALL provide aggregate parent evidence only. It SHALL NOT create child test-node identities, assertion evidence, obligation bindings, or passing dispositions that are absent from the independently derived project test inventory and required child mesh.

#### Scenario: Parent suite passes with an orphan obligation
- **WHEN** the broad parent suite passes while one required obligation has no owned child test node
- **THEN** static model-code-test closure remains blocked for deep blueprint scope
- **AND** the orphan obligation and missing child owner remain explicit

#### Scenario: Ordinary work changes one bounded neighborhood
- **WHEN** a task changes only a fingerprinted affected blueprint neighborhood
- **THEN** TestMesh selects the exact affected test children and their required ancestors
- **AND** it does not require unrelated test partitions merely because a whole-software blueprint exists

#### Scenario: Background execution is still running
- **WHEN** a background test shard has only progress, logs, or a live process
- **THEN** TestMesh reports liveness without a terminal result
- **AND** no blueprint evidence row becomes current until the exact terminal receipt is verified

### Requirement: Complete project test inventory has terminal dispositions
Every required project test node SHALL have exactly one terminal disposition: behavior coverage, cross-owner integration coverage, supporting evidence, duplicate evidence, scoped exclusion, or blocked. Parameterized and subtest cases SHALL retain stable case identity when their assertions differ materially.

#### Scenario: Required test node is unbound
- **WHEN** a full blueprint inventory contains a required test node with no owner, coverage edge, or typed disposition
- **THEN** TestMesh SHALL report the node and block declared-complete project-test closure

#### Scenario: Test node covers several owners
- **WHEN** one test is intentionally shared across model owners
- **THEN** TestMesh SHALL require exact assertion or native-member coverage edges for each owner
- **AND** file-level matching alone SHALL NOT prove coverage

### Requirement: Parent success recomposes exact leaf evidence
A TestMesh parent SHALL list the complete frozen leaf inventory and SHALL recompose only from exact current child receipt ids and covered-member fingerprints. Parent command success SHALL NOT manufacture a missing leaf or case.

#### Scenario: One required child receipt is absent
- **WHEN** the frozen parent requires child owners A and B but only A has current terminal evidence
- **THEN** the parent SHALL remain incomplete
- **AND** B SHALL remain visibly `execute`, `not_run`, or `blocked`

### Requirement: Affected-only freshness follows explicit ownership edges
Source, model, contract, provider, checker, and environment changes SHALL invalidate only owners that explicitly consume the changed component and their genuine receipt dependants. Unknown or ambiguous ownership SHALL block instead of expanding to run-all.

#### Scenario: One model fingerprint changes
- **WHEN** only model B changes and model A has exact-current independent evidence
- **THEN** A MAY remain reusable
- **AND** B and its declared dependants SHALL require current execution

#### Scenario: Changed component has no owner edge
- **WHEN** an affected component cannot be assigned to one exact validation owner
- **THEN** planning SHALL block before execution
- **AND** it SHALL NOT choose a global fallback owner or all-suite run

### Requirement: Passing leaf receipts come only from the exact supervised producer
A passing validation-owner leaf SHALL be published only from the in-process bounded supervisor result for the exact frozen contract command and working directory. Success SHALL require zero exit, a successful containment query, an exited root process, an explicitly empty descendant-process set, unchanged governed inputs, and one current pre-publication verification. Caller-authored child status, a serialized terminal artifact, or a public generic receipt saver SHALL NOT publish pass.

#### Scenario: Caller self-reports a passing child
- **WHEN** ordinary code constructs a passing child result or a green-looking supervision value without running the frozen owner command
- **THEN** no passing leaf receipt SHALL be published
- **AND** non-pass recording SHALL remain a separate API that rejects `pass`

#### Scenario: Supervised command or working directory differs
- **WHEN** a genuine supervised result was produced for a different command or working directory than the current owner contract
- **THEN** publication SHALL block with the exact command or working-directory mismatch

#### Scenario: Windows Job still reports only the exited root PID
- **WHEN** the root process has exited and a containment query transiently retains only that root PID
- **THEN** the root PID SHALL be excluded from descendant ids
- **AND** an unknown query or any genuine child PID SHALL still block success

#### Scenario: Inputs drift immediately before publication
- **WHEN** governed inputs change after execution or after receipt preparation but before final publication
- **THEN** the prepared evidence SHALL NOT become a current passing receipt
- **AND** the publisher SHALL stage proof data, rederive currentness, and publish only the verified immutable result
