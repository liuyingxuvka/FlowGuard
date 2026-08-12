## MODIFIED Requirements

### Requirement: Revision-set diffs are complete and fingerprinted
Before validation or activation, the system SHALL independently derive the
actual change set by comparing the complete canonical base and candidate
snapshots, their source-surface inventories, and every referenced native-owner
artifact inventory. The derived set SHALL include added, removed, or
fingerprint-changed model members, roots, relations, behavior commitments,
source surfaces, fields, state, side effects, system properties, code
contracts, tests, evidence, owner artifacts, coverage rows, and unresolved
gaps. The validator SHALL derive this set before it evaluates caller
declarations. Caller-declared members, changed ids, affected ids, and
fingerprints SHALL be assertions that must exactly reconcile with the derived
set and SHALL NOT narrow, expand, hash, or replace it. Unchanged members and
bindings SHALL retain their exact identities.

#### Scenario: An undeclared sibling changes
- **WHEN** a candidate snapshot changes a sibling model, relation, input, or
  owner-artifact fingerprint that the revision set did not declare
- **THEN** revision validation reports undeclared drift and the independently
  derived changed id
- **AND** activation is blocked

#### Scenario: A behavior source surface changes without a caller changed id
- **WHEN** a source surface is added, removed, moved, assigned a different
  role or owner, given a different disposition, or has a different content
  fingerprint between the base and candidate inventories
- **AND** the caller omits that surface from its changed-id list
- **THEN** the independently derived diff includes the source surface and its
  affected owner relations
- **AND** the declaration mismatch blocks acceptance rather than silently
  shrinking the affected boundary

#### Scenario: An owner artifact changes under a stable logical id
- **WHEN** a model, runner, purpose closure, resolved input, commitment
  ledger, field inventory, UI inventory, contract, test, or evidence-owner
  artifact keeps its logical id but changes fingerprint
- **THEN** the independently derived diff treats the owner artifact as changed
- **AND** every governed object reached through its typed ownership relations
  enters affected-closure derivation

#### Scenario: Caller declares a change that the inventories do not contain
- **WHEN** a caller-supplied changed id has no corresponding base-to-candidate
  identity or fingerprint difference
- **THEN** revision validation reports an over-declared or unresolved change
  assertion
- **AND** it does not manufacture a difference or evidence obligation to make
  the declaration pass

#### Scenario: A removal has no disposition
- **WHEN** a revision set removes an instance or governed object without an
  exact replacement, retirement, migration, or bounded out-of-scope
  disposition
- **THEN** the affected closure remains unresolved
- **AND** the revision set cannot be accepted

#### Scenario: Caller hashes an incomplete affected set
- **WHEN** caller-supplied affected ids and their caller-computed fingerprint
  omit or add any id relative to the independently derived closure
- **THEN** validation reports the exact identity-set mismatch
- **AND** the caller fingerprint does not authorize the revision

### Requirement: Validation closes the entire affected model system
Revision-set validation SHALL seed one dependency-closed affected slice from
the independently derived complete base-to-candidate diff, including every
changed source surface, root, coverage row, unresolved gap, and owner artifact.
It SHALL derive a deterministic fixed-point closure over explicit current typed
ownership, containment, refinement, dependency, delegation, realization,
validation, consumption, production, and evidence relations in the base and
candidate snapshots. It SHALL require the existing native owners to validate
every reached model, parent-child reattachment, explicitly affected sibling,
behavior commitment, source-surface disposition, field and side-effect
lifecycle, code contract, test obligation, and selected portable system
property. A lexical match, parent membership alone, or caller-selected id SHALL
NOT fan the closure out to unrelated siblings or omit an explicitly related
consumer. Unaffected evidence MAY be reused only when it is outside the
derived closure and its exact inputs, dependencies, tools, environment,
obligations, and fingerprints remain unchanged.

#### Scenario: Changed source surface reaches its native owners
- **WHEN** the derived diff contains a changed behavior source surface
- **THEN** affected closure includes its behavior commitment, primary owner
  model, delegated or primary path, fields, side effects, contracts, tests,
  evidence obligations, and any affected parent or sibling relations
- **AND** the surface cannot be closed by a caller assertion or ledger row
  without current evidence from those native owners

#### Scenario: Changed owner artifact expands the closure
- **WHEN** an owner-artifact fingerprint changes while the governed logical
  ids remain stable
- **THEN** affected closure follows the artifact's exact ownership and
  dependency edges to every consumer whose evidence may be stale
- **AND** revalidation is derived from those edges rather than from a
  caller-selected changed-id subset

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

#### Scenario: A parent has no edge to an otherwise unchanged sibling
- **WHEN** a changed child reaches its parent but no changed relation, shared
  owner, dependency, or reattachment edge reaches another unchanged sibling
- **THEN** the unrelated sibling does not enter affected closure merely because
  it shares the parent
- **AND** the closure report preserves the explicit edge basis for every
  included id

### Requirement: Acceptance consumes one exact evidence closure
A revision set SHALL be accepted only when every required native-owner evidence
receipt independently verifies as current, eligible, and passing for the exact
candidate snapshot and independently derived affected closure. Every receipt
SHALL bind the affected-closure fingerprint and the exact affected ids,
subjects, owner route, and obligations it covers. The union of covered affected
ids SHALL equal the derived closure exactly, and every id SHALL be covered by
its native owner. The accepted evidence set SHALL contain no missing,
duplicate, substituted, over-scoped, or unconsumed required receipt. A
caller-declared required-evidence list and a legacy receipt without closure
coverage SHALL NOT define or satisfy the obligation.

#### Scenario: One required owner has not run
- **WHEN** any required model, hierarchy, commitment, field, contract, test, or
  process owner has no exact current passing receipt
- **THEN** the aggregate acceptance decision is blocked
- **AND** passing receipts from other owners cannot substitute for it

#### Scenario: All required evidence closes
- **WHEN** the independently derived diff and affected closure are complete
- **AND** every required receipt verifies against the exact candidate, source
  revision, affected-closure fingerprint, covered affected ids, native owner,
  and obligation set
- **THEN** the revision set may record one aggregate accepted decision
- **AND** the decision consumes the exact child-receipt fingerprints on which
  it depends

#### Scenario: Two receipts cover only two ids in a thirty-three-id closure
- **WHEN** the independently derived affected closure contains 33 ids
- **AND** two otherwise passing receipts cover only two of those ids
- **THEN** acceptance reports the remaining 31 ids as uncovered
- **AND** equality between a caller-declared required and completed receipt
  list does not make the revision acceptable

#### Scenario: Two receipts collectively cover all thirty-three ids
- **WHEN** the independently derived affected closure contains 33 ids
- **AND** two current receipts explicitly and without overlap or substitution
  cover all 33 ids through their correct native owners and obligations
- **THEN** receipt count alone does not block acceptance
- **AND** the exact coverage union may satisfy the evidence closure

#### Scenario: Legacy evidence omits closure coverage
- **WHEN** an evidence record uses an unsupported schema or omits its
  affected-closure fingerprint or covered affected ids
- **THEN** the record is ineligible for current revision acceptance
- **AND** the system does not inject defaults, use a compatibility reader, or
  infer coverage from its route or receipt id

### Requirement: Observed activation uses compare-and-swap
Activation of a new observed snapshot SHALL use the single shared
project-manifest lock and compare the complete current observed-head
fingerprint with the revision set's expected full head. While holding that
lock, the activation owner SHALL load and validate the complete current head
and base snapshot, independently rebuild the candidate from the live manifest
and current source inventory, require exact canonical equality with the
accepted candidate, validate the independently derived diff, affected closure,
and evidence, persist immutable candidate and decision records, and resample
the live candidate immediately before the pointer write. It SHALL update the
sole observed-head pointer atomically exactly once and last. A target or
experiment SHALL NOT be activated as observed merely by changing its lane or
lifecycle label.

#### Scenario: Compare-and-swap succeeds
- **WHEN** the complete current head still equals the expected full-head
  fingerprint
- **AND** the lock-held live rebuild and final live resample both exactly match
  the accepted candidate snapshot
- **AND** the accepted revision set and activation evidence match that
  candidate
- **THEN** the system atomically replaces the project pointer with the new
  observed snapshot and transition identities
- **AND** readers observe either the complete old system or the complete new
  system

#### Scenario: Concurrent candidate wins first
- **WHEN** two different accepted candidates start from the same expected full
  head
- **AND** one activation changes the observed head while holding the shared
  lock
- **THEN** exactly one candidate becomes current and the generation advances
  exactly once
- **AND** the losing compare-and-swap fails without changing the head or
  automatically retrying, rebasing, or resuming the stale candidate

#### Scenario: Failure occurs before pointer replacement
- **WHEN** candidate, revision, receipt, final live resample, or pointer
  persistence fails before the atomic pointer replacement completes
- **THEN** the old observed head remains byte-for-byte authoritative
- **AND** any fully written immutable candidate records remain non-current
  history rather than a partially active system

#### Scenario: The head is unchanged but live source drifts
- **WHEN** the expected full head still matches
- **AND** the lock-held live rebuild or pre-pointer live resample differs from
  the accepted candidate because a governed live input changed
- **THEN** activation is blocked without moving the pointer
- **AND** the candidate requires a new revision and current evidence

### Requirement: Operational rollback restores truth before moving authority
After implementation or deployment, rollback of an observed revision SHALL
first restore the exact prior code, configuration, and deployment revision;
restore affected data or execute a validated compensation; restore or
compensate external side effects; and rerun conformance against a freshly
rebuilt prior observed snapshot. Exact rollback SHALL then be represented as a
new reverse `ModelRevisionSet` based on the complete current head. The reverse
revision SHALL identify the original revision and activation, derive the
complete reverse diff and affected closure, consume current restoration and
native-owner evidence, and use the same lock, full-head compare-and-swap, live
rebuild, immutable-record, and pointer-last activation transaction. The
original accepted revision SHALL remain immutable, and a rollback receipt
SHALL NOT be stored in a field that claims to identify an accepted revision
set.

#### Scenario: Exact operational rollback succeeds
- **WHEN** the complete current observed head is the head introduced by the
  original revision set
- **AND** code, configuration, deployment, data, and external effects have been
  restored or validly compensated
- **AND** current replay and conformance evidence proves the freshly rebuilt
  prior observed snapshot describes the restored software
- **AND** the reverse revision's diff, affected closure, evidence, and expected
  full head validate
- **THEN** the system atomically activates the reverse `ModelRevisionSet` whose
  candidate is the exact prior observed snapshot
- **AND** the reverse revision and rollback receipt record the rolled-back
  outcome while the original accepted revision remains immutable

#### Scenario: Model pointer is rolled back without software restoration
- **WHEN** the deployed implementation or affected data still represents the
  newer revision
- **THEN** the reverse candidate's live rebuild or restoration evidence fails
  and the system blocks movement of the observed-head pointer
- **AND** it reports that model-authority rollback alone would misdescribe the
  current software

#### Scenario: Rollback transition identities remain typed
- **WHEN** a reverse revision becomes current
- **THEN** the new head's accepted-revision identity references that reverse
  `ModelRevisionSet`
- **AND** its rollback or activation transition receipt remains a separate
  typed identity rather than masquerading as a revision-set fingerprint

### Requirement: Advanced authority cannot be rewound by an old revision
Operational rollback SHALL compare-and-swap against the exact complete
observed head introduced by the original revision, including generation,
snapshot, accepted revision, previous snapshot, and transition receipt
identities. Matching only the snapshot fingerprint SHALL NOT authorize
rollback. If the observed head has advanced or revisited the same snapshot
through a later transition, the old rollback contract SHALL NOT overwrite
intervening accepted work.

#### Scenario: Head advanced after the revision
- **WHEN** rollback is requested for a revision whose complete introduced head
  is no longer the current observed head
- **THEN** rollback compare-and-swap is blocked
- **AND** restoration or compensation is represented as a new forward or
  reverse revision based on the complete current observed head

#### Scenario: A later generation revisits the same snapshot
- **WHEN** the current head names the same snapshot fingerprint as an earlier
  rollback contract but has a different generation, accepted revision, or
  transition receipt
- **THEN** the earlier contract is stale and cannot move the pointer
- **AND** no snapshot-only comparison, compatibility path, or automatic retry
  may authorize it

