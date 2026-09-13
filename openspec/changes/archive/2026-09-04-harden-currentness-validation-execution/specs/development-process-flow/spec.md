## ADDED Requirements

### Requirement: Broad process claims consume exactly one verified full parent
DevelopmentProcessFlow SHALL support a broad done, release, archive, or publish
claim only from one independently verified terminal-success receipt whose
subject is exactly `validation-parent:full`. The receipt MUST bind the frozen
owner DAG, `ParentCurrent`, complete required owner and obligation inventory,
and exact verified child receipts. Child, focused, routine, synchronization,
plan, WorkContext, progress, post-change-scan, and provider status evidence
MUST NOT substitute for that parent.

#### Scenario: All focused checks pass without the full parent
- **WHEN** every visible child or synchronization check passes but no verified
  `validation-parent:full` receipt exists
- **THEN** DevelopmentProcessFlow MUST keep broad completion blocked

#### Scenario: Full parent verifies against final inputs
- **WHEN** the loaded `validation-parent:full` receipt independently verifies
  against the final source, model authority, toolchain, environment, owner
  plan, and complete child inventory
- **THEN** DevelopmentProcessFlow MAY use that single receipt to support the
  matching broad claim scope

#### Scenario: A covered input changes after the full parent
- **WHEN** any functional input consumed by the frozen full parent changes
- **THEN** DevelopmentProcessFlow MUST invalidate that parent and derive a new
  affected owner plan before broad confidence can return

### Requirement: Process revalidation is affected-only and owner-exact
DevelopmentProcessFlow SHALL derive revalidation from changed functional
components and the frozen owner DAG. It MUST preserve exact-current unrelated
owner receipts, execute only missing, failed, stale, or invalidated owners, and
retain successful child receipts immediately when another owner fails. An
unmapped or ambiguous changed component, malformed receipt, tampered receipt,
unknown owner, cyclic dependency, or cleanup-unconfirmed lease MUST block the
plan and MUST NOT trigger run-all fallback or automatic retry.

#### Scenario: A repair changes one verifier
- **WHEN** one verifier component changes and its owner mapping is exact
- **THEN** DevelopmentProcessFlow MUST recommend that owner and its dependent
  closure only
- **AND** unrelated exact-current receipts MUST remain reusable

#### Scenario: Receipt verification is malformed
- **WHEN** an affected owner's prior receipt is malformed, tampered, or cannot
  be independently verified
- **THEN** DevelopmentProcessFlow MUST block that owner rather than convert the
  uncertainty into an execution or reuse disposition
- **AND** it MUST NOT invalidate every unrelated owner

#### Scenario: Interrupted owner still has a live descendant
- **WHEN** process-tree cleanup is unconfirmed for an owner
- **THEN** DevelopmentProcessFlow MUST block every later owner in the frozen
  parent and any retry until zero descendants and lease settlement are confirmed

### Requirement: The frozen full gate runs after mutable closure inputs settle
DevelopmentProcessFlow SHALL order version, documentation, OpenSpec state,
model authority, required consumer and installation parity, and other declared
mutable closure inputs before freezing and running the one full validation
parent. Commit, tag, push, archive, or publication MUST occur only after that
parent succeeds. Post-publication verification SHALL compare immutable source,
installation, Git, tag, and remote identities read-only and MUST start zero
validation producers.

#### Scenario: Documentation changes after the full gate
- **WHEN** documentation is a frozen functional input and changes before
  commit, tag, archive, or publication
- **THEN** the full parent MUST become stale and a new affected plan and parent
  identity are required

#### Scenario: Published identities match
- **WHEN** the published commit and immutable tag match the receipt-bound
  release identity
- **THEN** DevelopmentProcessFlow MUST verify parity without launching a
  producer or refreshing validation evidence

### Requirement: WorkContext changes invalidate only declared consumers
DevelopmentProcessFlow SHALL consume WorkContext source identities through
explicit per-artifact or complete-inventory edges. It MUST re-read required
project-bounded sources when deriving currentness and MUST stale only owners
whose declared edges consume the changed element. Aggregate context
currentness or provider status MUST NOT authorize a receipt or force unrelated
owners to rerun.

#### Scenario: One context artifact changes
- **WHEN** one WorkContext artifact changes and only one owner declares an edge
  to it
- **THEN** DevelopmentProcessFlow MUST stale that owner and its dependent
  closure while preserving unrelated current owner receipts

#### Scenario: Caller marks the context current
- **WHEN** a caller supplies `current=true` but a re-read bounded source differs
- **THEN** DevelopmentProcessFlow MUST use the source-derived identity and
  invalidate the exact consumers
