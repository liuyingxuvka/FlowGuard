## MODIFIED Requirements

### Requirement: Frozen Owner Execution Plan
The unified full validator SHALL materialize one canonical
`ValidationInputManifest`, complete owner DAG, and immutable `ParentCurrent`
before starting any producer. For every owner, the frozen plan SHALL bind exact
functional source/content identities, current model-authority head and selected
revision closure, request/purpose, toolchain, environment policy and observed
environment, check inventory, obligation inventory, dependencies, declared
shared resources, installed consumer projection, output subject, and exactly
one execution owner. Evidence outputs SHALL be excluded unless their content
is an explicit functional input. The plan MUST be acyclic, resource conflicts
MUST be ordered, and each owner SHALL have exactly one disposition:
`execute`, `reuse_current`, or `blocked`.

#### Scenario: Plan-only requested
- **WHEN** the caller requests plan-only mode
- **THEN** the complete owner plan and reasons are emitted
- **AND** zero validation producers execute, zero owner or resource leases are
  acquired, zero execution receipts or run manifests are written, and zero
  current-evidence or current-parent pointers are updated

#### Scenario: Input mapping is unknown
- **WHEN** a governed functional input cannot be mapped to exactly one owner or
  declared shared dependency closure
- **THEN** the plan is blocked and the validator does not fall back to run-all

#### Scenario: Only an excluded evidence output changes
- **WHEN** a log, report, progress event, receipt, or pointer output changes and
  no owner declares its content as a functional input
- **THEN** the `ValidationInputManifest` and reusable child identities remain
  unchanged

#### Scenario: Owner dependency cycle is present
- **WHEN** the complete owner plan contains a dependency cycle or unresolved
  shared-resource conflict
- **THEN** the command MUST block before any producer or lease starts

### Requirement: Cross-Run Parent Receipt Composition
The full parent SHALL accept a complete mixture of current-run and prior-run
terminal-success child receipts only after loading and independently verifying
each receipt against the same frozen `ParentCurrent`. Required mapping key,
receipt identity, subject, claim scope, obligation coverage, input and result
fingerprints, and supersession state MUST match exactly. Broad pass SHALL
require complete owner and obligation coverage and publication of one verified
`validation-parent:full` receipt, not execution of every child in the current
run.

#### Scenario: All children are current
- **WHEN** every required child has an independently verified receipt for the
  frozen context
- **THEN** full validation passes by composition with zero heavy child
  executions and MAY publish the verified full parent

#### Scenario: Parent previously failed
- **WHEN** a parent failed because one child failed but other child receipts
  remain exact-current
- **THEN** the next frozen parent may reuse the successful receipts and execute
  only the stale or missing child

#### Scenario: Caller asserts child supersession state
- **WHEN** caller metadata says a child is current but receipt-store
  verification finds a newer eligible child
- **THEN** the parent MUST reject the consumed child and remain unpublished

### Requirement: Unique Final Full Release Gate
Release validation SHALL freeze `ValidationInputManifest`,
`ReleaseTreeManifest`, the complete owner DAG, and `ParentCurrent` only after
the release version, documentation, OpenSpec state, current model authority,
and consumer installation/parity are final. Exactly one final full parent gate
SHALL consume that frozen identity set; it MAY execute stale or missing owners
and reuse independently verified exact-current receipts. The command MUST
publish broad success only as an independently verified receipt whose subject
is `validation-parent:full`. Commit, tag, push, and publication SHALL occur
only after that parent passes.

#### Scenario: Version or documentation changes after the gate
- **WHEN** any post-freeze change alters a frozen manifest or parent input
  before commit or tag
- **THEN** the prior final parent is invalid, publication is blocked, and a new
  manifest set and affected owner plan are required

#### Scenario: Published verification starts
- **WHEN** the release commit and immutable tag already match the receipt-bound
  `ReleaseTreeManifest`
- **THEN** published verification performs read-only identity comparison and
  starts zero validation producers

#### Scenario: Full command ends with only child receipts
- **WHEN** every child passes but the command cannot independently verify and
  atomically publish `validation-parent:full`
- **THEN** the command MUST exit without broad success

