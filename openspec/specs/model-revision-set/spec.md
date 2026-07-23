# model-revision-set Specification

## Purpose
TBD - created by archiving change establish-authoritative-model-system. Update Purpose after archive.
## Requirements
### Requirement: A revision set changes one or more models as one unit
A `ModelRevisionSet` SHALL generalize the existing task-local revision
lifecycle to one or more model-system member changes. It SHALL freeze the task
or change id, subject lane, expected authority-head fingerprint, base and
candidate snapshot fingerprints, exact add, replace, and remove members,
changed relation and owner-artifact ids, affected-closure fingerprint,
required prediction and replay bindings, required evidence references,
implementation-bundle reference, rollback-contract reference, aggregate
status, and decision reason.

#### Scenario: One-model revision uses the same lifecycle
- **WHEN** a change affects exactly one model instance
- **THEN** the system represents it as a one-member revision set
- **AND** it uses the same proposal, validation, acceptance, rejection, and
  rollback rules as a multi-model revision

#### Scenario: Multi-model revision cannot be accepted by member
- **WHEN** a revision set contains multiple model, relation, commitment, field,
  side-effect, property, contract, or test changes
- **THEN** no member can obtain an independently active status
- **AND** the revision set reaches one aggregate accepted or rejected outcome

### Requirement: Candidate systems are isolated from current authority
A revision set SHALL derive its candidate snapshot from one exact immutable
base snapshot without mutating the base snapshot or the project observed-head
pointer. Candidate checks, experiments, failures, and discarded artifacts
SHALL NOT change current observed authority.

#### Scenario: Candidate validation fails
- **WHEN** any candidate validation reports failed, blocked, stale, skipped, or
  not-run evidence
- **THEN** the revision set remains non-active or is rejected
- **AND** the observed-head pointer and base snapshot remain unchanged

#### Scenario: Candidate execution produces partial artifacts
- **WHEN** candidate construction or checking stops after producing only part
  of its planned artifacts
- **THEN** those artifacts remain non-authoritative diagnostic material
- **AND** no partial candidate membership is projected into the observed
  snapshot

### Requirement: Revision-set diffs are complete and fingerprinted
Before validation or activation, the system SHALL compare the exact base and
candidate snapshots and prove that the declared member, relation, commitment,
field, side-effect, system-property, contract, test, and evidence changes equal
the actual fingerprinted differences. Unchanged members and bindings SHALL
retain their exact identities.

#### Scenario: An undeclared sibling changes
- **WHEN** a candidate snapshot changes a sibling model, relation, input, or
  owner-artifact fingerprint that the revision set did not declare
- **THEN** revision validation reports undeclared drift
- **AND** activation is blocked

#### Scenario: A removal has no disposition
- **WHEN** a revision set removes an instance or governed object without an
  exact replacement, retirement, migration, or bounded out-of-scope
  disposition
- **THEN** the affected closure remains unresolved
- **AND** the revision set cannot be accepted

### Requirement: Validation closes the entire affected model system
Revision-set validation SHALL derive a dependency-closed affected slice and
require the existing native owners to validate every affected model,
parent-child reattachment, sibling impact, behavior commitment, field and
side-effect lifecycle, code contract, test obligation, and selected portable
system property. Unaffected evidence MAY be reused only when its exact inputs,
dependencies, tools, environment, obligations, and fingerprints remain
unchanged.

#### Scenario: Members pass locally but joint behavior fails
- **WHEN** every changed model passes its local checks
- **AND** a required parent join, sibling interaction, shared resource, joint
  step, or system property fails
- **THEN** the aggregate revision-set validation fails
- **AND** none of its members is promoted

#### Scenario: Required replay binding does not match
- **WHEN** replay evidence names the wrong prediction id, prediction
  fingerprint, observation boundary, candidate instance, or candidate model
  fingerprint
- **THEN** that evidence does not close the revision-set obligation
- **AND** acceptance remains blocked

### Requirement: Acceptance consumes one exact evidence closure
A revision set SHALL be accepted only when every required native-owner
evidence receipt independently verifies as current, eligible, and passing for
the exact candidate snapshot and affected closure. The accepted evidence set
SHALL contain no missing, duplicate, substituted, or unconsumed required
receipt.

#### Scenario: One required owner has not run
- **WHEN** any required model, hierarchy, commitment, field, contract, test, or
  process owner has no exact current passing receipt
- **THEN** the aggregate acceptance decision is blocked
- **AND** passing receipts from other owners cannot substitute for it

#### Scenario: All required evidence closes
- **WHEN** the declared diff is complete and every required receipt verifies
  against the exact candidate, source revision, affected closure, and
  obligation set
- **THEN** the revision set may record one aggregate accepted decision
- **AND** the decision consumes the exact child-receipt fingerprints on which
  it depends

### Requirement: Observed activation uses compare-and-swap
Activation of a new observed snapshot SHALL compare the current observed-head
fingerprint with the revision set's expected head, persist immutable candidate
and decision records before activation, and update the sole observed-head
pointer exactly once and last. A target or experiment SHALL NOT be activated
as observed merely by changing its lane or lifecycle label.

#### Scenario: Compare-and-swap succeeds
- **WHEN** the current head still equals the expected base fingerprint
- **AND** the accepted revision set and activation evidence match the new
  observed snapshot
- **THEN** the system atomically replaces the project pointer with the new
  observed snapshot fingerprint
- **AND** readers observe either the complete old system or the complete new
  system

#### Scenario: Concurrent candidate wins first
- **WHEN** another accepted revision has already changed the observed head
  after this candidate froze its base
- **THEN** compare-and-swap fails without changing the head
- **AND** the stale candidate must be rebased and revalidated as a new revision
  before activation

#### Scenario: Failure occurs before pointer replacement
- **WHEN** persistence or activation fails before the final pointer
  replacement
- **THEN** the old observed head remains authoritative
- **AND** any fully written immutable candidate records remain non-current
  history rather than a partially active system

### Requirement: Experiment rejection is a pre-implementation return operation
The system SHALL support rejecting or discarding a
`counterfactual_experiment` before implementation without treating the
operation as an observed software rollback.

#### Scenario: Experiment is disproved
- **WHEN** an experimental candidate fails its predictions, replay, or system
  properties before any implementation bundle is applied
- **THEN** the revision set records rejection and its reason
- **AND** the experiment remains historical or is discarded according to
  retention policy
- **AND** the observed-head pointer, software, and data remain unchanged

### Requirement: Target withdrawal is a pre-implementation return operation
The system SHALL support withdrawing or superseding an accepted
`normative_target` before implementation. Target withdrawal SHALL preserve the
target's immutable history and SHALL NOT be reported as restoration of
deployed software.

#### Scenario: Accepted target is no longer desired
- **WHEN** an accepted normative target has not been realized by an
  implementation revision
- **THEN** the system records its withdrawal or a superseding target through
  the existing revision lifecycle
- **AND** the observed-head pointer remains on the same observed snapshot

### Requirement: Operational rollback restores truth before moving authority
After implementation or deployment, rollback of an observed revision SHALL
first restore the exact prior code, configuration, and deployment revision;
restore affected data or execute a validated compensation; restore or
compensate external side effects; and rerun conformance against the prior
observed snapshot. The authority pointer SHALL move back only after those
requirements have current passing evidence.

#### Scenario: Exact operational rollback succeeds
- **WHEN** the current observed head is the snapshot introduced by the
  revision set
- **AND** code, configuration, deployment, data, and external effects have been
  restored or validly compensated
- **AND** current replay and conformance evidence proves the prior observed
  snapshot describes the restored software
- **THEN** the system atomically moves the observed head back to the exact
  prior snapshot
- **AND** the revision set records a rolled-back outcome with the consumed
  restoration evidence

#### Scenario: Model pointer is rolled back without software restoration
- **WHEN** the deployed implementation or affected data still represents the
  newer revision
- **THEN** the system blocks movement of the observed-head pointer to the old
  snapshot
- **AND** it reports that model-authority rollback alone would misdescribe the
  current software

### Requirement: Irreversible effects bound rollback claims
Every implementation-bearing revision set SHALL declare restore, compensate,
or irreversible disposition for each affected persistent-data and external
side-effect domain. Exact rollback SHALL be prohibited when an irreversible
effect lacks an executed and validated compensation contract.

#### Scenario: Irreversible effect has no valid compensation
- **WHEN** a deployed revision produced an irreversible data or external effect
- **AND** no current validated compensation can restore the prior observable
  contract
- **THEN** the system refuses an exact rollback claim and does not point the
  observed head at a snapshot that no longer describes reality
- **AND** recovery proceeds through a new forward repair or explicitly bounded
  compensation revision

#### Scenario: Compensation preserves only a bounded contract
- **WHEN** compensation restores declared user-visible behavior but cannot
  recreate the prior physical data or external state
- **THEN** the rollback result identifies the compensated boundary and
  remaining irreversible effects
- **AND** it does not claim byte-for-byte or state-identical restoration

### Requirement: Advanced authority cannot be rewound by an old revision
Operational rollback SHALL use compare-and-swap against the exact observed
snapshot introduced by the revision set. If the observed head has advanced,
the old revision SHALL NOT overwrite intervening accepted work.

#### Scenario: Head advanced after the revision
- **WHEN** rollback is requested for a revision whose candidate snapshot is no
  longer the current observed head
- **THEN** rollback compare-and-swap is blocked
- **AND** restoration or compensation is represented as a new forward revision
  based on the current observed snapshot

### Requirement: Development orchestration preserves owner boundaries
The development-process owner SHALL order base freezing, candidate
construction, affected-closure validation, evidence aggregation, activation,
and operational rollback. It SHALL expose blocked, skipped, stale, not-run,
and irreversible outcomes, but it SHALL NOT replace the native semantic
decision of model, hierarchy, commitment, field, contract, test, deployment,
data, or side-effect owners.

#### Scenario: Process order completes but a native owner fails
- **WHEN** all scheduled process steps execute in order but a required native
  owner reports failed or blocked evidence
- **THEN** the process reports the revision set as not activatable
- **AND** process completion is not treated as model-system correctness

