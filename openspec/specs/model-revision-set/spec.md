# model-revision-set Specification

## Purpose
Define one atomic change transaction for replacing one or more members of an
authoritative model system. The capability keeps candidates isolated from the
observed head, closes every affected model, relation, commitment, field,
contract, test, and implementation effect together, and permits activation or
operational rollback only with exact fresh evidence.
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
Before validation or activation, the system SHALL independently derive the
actual change set by comparing the exact base and candidate snapshots, their
source-surface inventories, and every referenced native-owner artifact
inventory. The derived set SHALL include added, removed, or fingerprint-changed
model members, relations, behavior commitments, source surfaces, fields,
state, side effects, system properties, code contracts, tests, evidence, and
owner artifacts. Caller-declared changed ids SHALL be treated as assertions
that must exactly reconcile with the derived set and SHALL NOT narrow or
replace it. Unchanged members and bindings SHALL retain their exact identities.

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

### Requirement: Validation closes the entire affected model system
Revision-set validation SHALL seed one dependency-closed affected slice from
the independently derived base-to-candidate diff, including every changed
source surface and owner artifact. It SHALL traverse current typed ownership,
containment, refinement, dependency, delegation, realization, validation, and
evidence relations and require the existing native owners to validate every
reached model, parent-child reattachment, sibling impact, behavior
commitment, source-surface disposition, field and side-effect lifecycle, code
contract, test obligation, and selected portable system property. Unaffected
evidence MAY be reused only when it is outside the derived closure and its
exact inputs, dependencies, tools, environment, obligations, and fingerprints
remain unchanged.

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

### Requirement: Revision building independently re-verifies native-owner evidence
Before a native-owner receipt can make a revision evidence-complete, the revision builder SHALL reload that exact receipt from the canonical receipt store, derive the current owner contract, input, command, toolchain, environment, proof, result, and child-receipt context, and run the native receipt verifier itself. The aggregate receipt and every consumed child SHALL remain present with the same content identity through revision publication. A caller-supplied verification result MAY be carried as an immutable comparison artifact but SHALL match the independently derived result exactly and SHALL NOT be accepted as its own authority.

#### Scenario: Caller repairs a tampered receipt by self-reporting pass
- **WHEN** a caller changes a receipt contract, input, command, toolchain, environment, proof, result, or child identity, recomputes wrapper fingerprints, and supplies `current=true`, `eligible=true`, and `pass`
- **THEN** revision building SHALL reject the evidence against the canonical store and current verification context

#### Scenario: Canonical receipt is exact current
- **WHEN** the receipt loaded from the canonical store passes the independently derived current context and the supplied comparison result is exactly equal
- **THEN** the corresponding native owner MAY contribute evidence for only its exact affected obligations

#### Scenario: Canonical evidence disappears during revision building
- **WHEN** an aggregate receipt or one of its mapped child receipts is removed or replaced after initial verification but before the revision artifacts are published
- **THEN** revision building SHALL re-read the canonical store and block publication

### Requirement: Full model parents consume canonical execution composition
A model-regression parent used for revision building SHALL reference one canonical content-addressed execution receipt whose native contract binds the original tier, claim scope, complete selected-model denominator, current manifest, terminal result, and exact child receipts. The mutable parent wrapper and its recomputable fingerprint SHALL NOT be execution authority.

#### Scenario: A scoped parent wrapper is relabeled as full
- **WHEN** a scoped run happened to select the same model ids as the current full denominator and a caller rewrites its wrapper tier and claim scope to `full`
- **THEN** revision building SHALL reject it because the canonical execution receipt remains bound to the scoped contract

#### Scenario: The exact full parent is current
- **WHEN** the wrapper references the current canonical full-selection execution receipt and every consumed model child remains exact-current
- **THEN** the parent MAY support revision building within that exact manifest boundary

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

### Requirement: ModelRevisionSet accounts for intent contributions atomically
A `ModelRevisionSet` SHALL bind the exact admitted intent-contribution inventory used to derive its candidate. Every contribution inside the revision boundary SHALL have one disposition of `accepted`, `superseded`, `rejected`, `deferred`, `conflicting`, or `unresolved`, and each accepted contribution SHALL map to exact changed obligations, states, transitions, invariants, relations, or explicit gaps.

#### Scenario: Accepted user decision changes one candidate behavior
- **WHEN** a user decision is accepted for a candidate revision
- **THEN** the revision set binds the decision fingerprint and every derived changed model identity
- **AND** acceptance remains atomic with the complete affected closure

#### Scenario: Earlier Spark intent is superseded
- **WHEN** an accepted contribution explicitly supersedes an earlier Spark contribution
- **THEN** the revision set preserves both immutable contribution identities and the supersession edge
- **AND** the earlier contribution is not simultaneously treated as an active candidate obligation

#### Scenario: A contribution has no modeled effect
- **WHEN** an admitted accepted contribution maps to no model obligation, state, transition, invariant, relation, or explicit scoped gap
- **THEN** revision validation reports a disconnected intent contribution
- **AND** the revision set cannot be accepted

### Requirement: Intent conflicts and unresolved targets block acceptance without changing current authority
Revision validation SHALL detect contradictory active contributions, incompatible invariants, unreachable desired terminal states, missing supersession, and target outputs with no declared consumer. No such condition SHALL be resolved by source timestamp, document status, or caller assertion alone.

#### Scenario: Two active goals require incompatible invariants
- **WHEN** the same candidate revision contains two active contributions whose required invariants cannot hold together
- **THEN** the conflict remains explicit and acceptance is blocked
- **AND** the current observed head remains unchanged

#### Scenario: A desired terminal is unreachable
- **WHEN** an accepted contribution names a desired terminal that no candidate transition path can reach from a declared initial state
- **THEN** revision validation reports the target and missing path
- **AND** passing local checks for unrelated members cannot close the revision set

#### Scenario: Candidate behavior is implemented and validated
- **WHEN** the complete candidate is implemented, independently validated, and accepted through the existing activation contract
- **THEN** a new `observed_implementation` snapshot is built from the live implementation inventory
- **AND** typed realization and supersession relations connect the candidate lineage to the new sole observed head

### Requirement: Non-trivial revision sets close current intent lineage
An accepted non-trivial ModelRevisionSet SHALL include the current intent inventory fingerprint and a terminal disposition for every admitted intent contribution, or one explicit evidence-bound rationale that no declared external intent exists for the revision.

#### Scenario: Empty intent inventory passes by vacuity
- **WHEN** a non-trivial revision has no contributions or dispositions and no current no-intent rationale
- **THEN** acceptance SHALL be blocked without changing observed authority

### Requirement: Every affected model has one explicit native owner
A ModelRevisionSet SHALL map every changed or affected model and relation to exactly one declared native owner. Missing or unknown ownership SHALL block candidate acceptance and SHALL NOT be assigned to a generic ModelMesh or self-maintenance owner.

#### Scenario: Changed model id has no owner mapping
- **WHEN** a candidate diff contains a model whose native owner is absent from the frozen owner plan
- **THEN** the revision set SHALL be blocked before activation

### Requirement: Intent dispositions cover every changed model identity
When exact changed-target enforcement is active and a revision contains one or more intent contributions, the union of `changed_model_ids` from accepted dispositions SHALL cover every raw semantic identity that the intent-disposition schema can express. This denominator consists only of `obligation:`, `state:`, `transition:`, `invariant:`, and `relation:` ids found in revision-member changed elements or raw changed-relation ids. Model-instance, root, system, fingerprint, coverage, test, evidence-freshness, and other revision-accounting wrappers remain governed revision evidence but SHALL NOT be treated as unmapped intent. Accepted semantic targets outside the exact semantic diff SHALL remain invalid. A contribution-free revision with an explicit evidence-bound no-declared-intent rationale SHALL remain outside this contribution-coverage comparison.

#### Scenario: One diff member has no accepted intent mapping
- **WHEN** the exact revision diff changes two raw semantic identities but accepted intent dispositions map only one
- **THEN** intent review SHALL report `intent_changed_target_unmapped` with the exact missing identity
- **AND** the revision SHALL NOT be accepted

#### Scenario: Production diff also contains internal wrappers
- **WHEN** a revision contains model-instance, root, system, fingerprint, coverage, test, or freshness wrapper changes plus raw relations
- **AND** accepted dispositions cover every raw semantic relation and other expressible semantic id
- **THEN** the internal wrappers SHALL NOT create unmapped-intent findings
- **AND** the revision MAY pass this coverage gate subject to every other revision requirement

#### Scenario: Several accepted contributions jointly cover the diff
- **WHEN** accepted dispositions independently map disjoint changed model identities whose union covers the exact revision diff
- **THEN** changed-target coverage MAY pass subject to every other intent and revision gate

#### Scenario: Evidence-bound no-intent revision has no contributions
- **WHEN** a contribution-free revision carries the complete current no-declared-intent rationale and evidence required by the revision contract
- **THEN** this contribution-coverage comparison SHALL NOT create an unmapped-target finding

### Requirement: Revision acceptance consumes exact per-owner evidence
Each affected owner SHALL contribute its own exact current receipt covering its declared model members and obligations. An aggregate parent receipt MAY compose those children but SHALL NOT be copied or relabeled as their producer evidence.

#### Scenario: Aggregate receipt is duplicated across owner rows
- **WHEN** one parent receipt is inserted as the native receipt for several owners without exact covered-member producer rows
- **THEN** revision validation SHALL reject every unsupported owner row

### Requirement: Multi-model blueprint revisions activate atomically
A blueprint-affecting revision SHALL freeze the observed base, complete candidate diff, affected closure, provider and inventory identities, per-owner receipts, and candidate snapshot before one atomic accept-and-activate decision.

#### Scenario: One affected model lacks current evidence
- **WHEN** all but one affected model have current passing owner receipts
- **THEN** no member of the candidate revision SHALL become observed authority

### Requirement: Affected native-owner routes consume explicit semantic model evidence
For every native owner route present in the exact affected revision closure, the
revision evidence plan SHALL declare exactly one explicit binding to one or more
existing semantic model children. Missing, duplicate, foreign, or unmaterialized
bindings SHALL block before native-owner evidence is written. The system SHALL
NOT assign an unknown route to a generic, similarly named, or run-all fallback
model.

#### Scenario: Affected inventory route has no semantic model binding
- **WHEN** the exact affected closure contains an authority-inventory route that is absent from the frozen owner-to-model binding plan
- **THEN** revision-owner evidence generation SHALL stop without publishing a bundle
- **AND** the finding SHALL name the unmapped route

#### Scenario: Every affected route has one current binding
- **WHEN** every route in the exact affected closure has one unique explicit binding whose model children exist in the candidate, full manifest, and exact-current full parent
- **THEN** each native owner MAY compose only those exact child receipts needed by its semantic binding and referenced changed-model closure

#### Scenario: A new affected identity category has no native route
- **WHEN** the derived revision closure contains an affected identity outside the explicitly classified model-relation, root, coverage, unresolved-gap, system-property, or typed endpoint categories
- **THEN** closure derivation SHALL fail with the exact unclassified affected identity
- **AND** the identity SHALL NOT be assigned to ModelMesh or another generic owner

### Requirement: Revision construction consumes exact-current intent sources
Before writing a candidate snapshot, revision set, or acceptance artifact, the revision builder SHALL independently re-verify every intent contribution against its declared current source authority. A direct project-file contribution SHALL resolve inside the current project root and match its recomputed canonical source-file identity. A WorkContext contribution SHALL resolve through the current declared read-only context and match its exact context id, context fingerprint, native owner, source reference, and artifact fingerprint. Internal contribution and disposition fingerprints SHALL NOT substitute for current source verification.

#### Scenario: Intent inventory is internally valid but its source changed
- **WHEN** every contribution and disposition fingerprint is internally consistent
- **AND** a declared intent source file has a different current source identity
- **THEN** revision construction fails as stale before writing candidate authority artifacts
- **AND** the existing observed authority remains unchanged

#### Scenario: Intent source remains exact current
- **WHEN** every contribution source reference resolves to a regular project file
- **AND** every recomputed canonical source identity equals its declared source fingerprint
- **THEN** the intent inventory may enter revision review and affected-owner construction
- **AND** each accepted contribution remains bound to that exact current source identity

#### Scenario: Source reference escapes or cannot be resolved
- **WHEN** a contribution source reference is absolute, traverses outside the project root, reaches a link or reparse target outside the root, is missing, or is not a regular file
- **THEN** revision construction fails visibly
- **AND** it does not guess a replacement path or accept an alternate source

#### Scenario: External planning material is supplied through WorkContext
- **WHEN** a contribution carries a complete WorkContext id, context fingerprint, and native owner
- **AND** the project's current declared read-only context contains the exact source reference and artifact fingerprint
- **THEN** the contribution may enter revision review without being treated as a direct project-file fingerprint
- **AND** provider status or execution metadata remains outside model evidence

#### Scenario: WorkContext lineage is stale or undeclared
- **WHEN** the current project declarations cannot reproduce the contribution's exact context, owner, source reference, and artifact fingerprint
- **THEN** revision construction fails visibly
- **AND** it does not fall back to trusting the contribution's internal fingerprint

#### Scenario: Intent source changes during construction
- **WHEN** a verified source identity changes before candidate artifacts are published
- **THEN** publication is blocked and any incomplete outputs remain non-authoritative
- **AND** a new frozen construction attempt is required

### Requirement: Revision construction closes intent-source model ownership
Before candidate snapshot construction, FlowGuard SHALL fold the candidate cumulative intent and compare every active `project_file` source reference with the exact `intent_source_inputs` declared by that contribution's logical model owner. The comparison SHALL be complete and bidirectional per owner. Only after the exact sets match may those files enter the owner model's resolved input inventory and affected-owner derivation. WorkContext contributions SHALL remain on their typed external identity path and SHALL NOT be required to resolve as repository files.

#### Scenario: Candidate adds a new local design source
- **WHEN** a candidate contribution introduces a project-file source for one logical model
- **AND** the model manifest has not declared that exact source path for that owner
- **THEN** revision construction blocks before candidate snapshot or revision publication
- **AND** it does not append the path after acceptance or assign the source to a root owner

#### Scenario: Candidate retires the last use of a local source
- **WHEN** the folded candidate view no longer has any project-file contribution for one owner/path pair
- **AND** the model still declares that path as an intent source
- **THEN** revision construction blocks on the extra historical binding
- **AND** retirement requires one direct removal from the owner-local manifest input set

#### Scenario: WorkContext contribution is current
- **WHEN** a contribution resolves through an exact current WorkContext identity
- **THEN** revision construction validates that external identity through the cumulative intent path
- **AND** the project-file binding comparison neither rejects it nor invents a local path for it

### Requirement: Accepted revisions own one cumulative current-intent view
Every current accepted `ModelRevisionSet` SHALL contain one content-addressed cumulative current-intent view for its candidate snapshot. The view SHALL be derived from the prior accepted revision's complete current view plus the new revision delta. It SHALL keep delta contributions distinct from cumulative authority, bind every active contribution to its verified current source identity, and dispose every prior active contribution through an explicit `retain`, `supersede`, or `retire` transition. The canonical head SHALL reach this view only through its one accepted revision; no second current-intent pointer, latest-delta interpretation, alias, or fallback reader is permitted.

#### Scenario: A small latest delta follows a large accumulated system
- **WHEN** the new revision changes intent for only two current model owners
- **AND** the prior accepted view contains active intent for the rest of the current system
- **THEN** the candidate revision folds both sources into one cumulative current view
- **AND** the latest two contributions SHALL NOT replace the unchanged cumulative intent

#### Scenario: Prior active contribution has no transition
- **WHEN** one contribution active in the prior current view is neither retained, superseded, nor retired in the candidate view
- **THEN** revision construction is blocked before publication
- **AND** the builder SHALL NOT silently drop it or infer last-write-wins behavior

#### Scenario: A contribution identifier is reused with different content
- **WHEN** a candidate presents an existing contribution id with a different contribution fingerprint
- **THEN** revision construction is blocked
- **AND** renewal requires a new contribution id and an explicit supersession transition

#### Scenario: Active intent source changes during construction
- **WHEN** any active cumulative contribution source changes after the candidate view is compiled but before publication
- **THEN** the builder rejects the candidate and writes no current authority
- **AND** rechecking only the newly supplied delta SHALL NOT be sufficient

### Requirement: Current intent migration is explicit and one-way
The first current-schema revision MAY bootstrap a cumulative view only through one explicit, evidence-bound direct migration that audits the exact accepted current ancestry. The migration SHALL classify every admitted ancestral contribution, exclude revisions outside the current ancestry, bind the complete current model-owner denominator, and publish one current-schema accepted revision. After activation, normal authority loading SHALL reject a legacy revision as current intent rather than invoking the migration, reconstructing lineage, or falling back to a latest delta.

#### Scenario: Existing current head has no cumulative view
- **WHEN** the current accepted head uses the immediately retired revision schema
- **AND** the explicit bootstrap audit closes the complete accepted ancestry and current owner denominator
- **THEN** one migration revision may publish the first complete current view
- **AND** the bootstrap receipt identity is carried by that view

#### Scenario: Legacy revision is offered after migration
- **WHEN** normal current-authority loading reaches an accepted revision without a complete current-intent view
- **THEN** current loading fails visibly
- **AND** it SHALL NOT search history, read a legacy delta as cumulative intent, or run migration implicitly

### Requirement: Current authority includes one exact transition receipt
FlowGuard SHALL treat a model authority head as current only when the head, observed snapshot, accepted revision, exactly one typed activation-or-rollback transition receipt, exact predecessor binding, current effective-intent view, and required source identities form one strict cross-validated state. Audit, revision planning and building, activation, and rollback SHALL consume the same current-state validator. Snapshot-plus-revision validation without the current transition receipt SHALL NOT establish current authority.

#### Scenario: Current transition receipt is missing or foreign
- **WHEN** the head's transition fingerprint is missing, duplicated across transition kinds, has stale content identity, names another revision or snapshot, carries another generation, or does not bind the exact previous head
- **THEN** every current-authority consumer blocks with the same invalid-current-state boundary
- **AND** no later green snapshot or revision check hides the transition failure

#### Scenario: Rollback produced the current head
- **WHEN** the current head was produced by a valid operational rollback
- **THEN** the current-state validator resolves the rollback transition, its contract, reverse revision, restoration evidence, predecessor head, and candidate snapshot exactly once
- **AND** it does not reinterpret the rollback as an activation or search an alternate success path

### Requirement: Authority audit proves current intent sources remain current
After strict immutable authority loading, `model-system-audit` SHALL independently reverify every active contribution source and compare the exact source identities with the current effective-intent view. A changed, missing, unsafe, non-regular, or stale WorkContext source SHALL make the current DNA audit non-pass without relabeling the immutable accepted revision as historically corrupt.

#### Scenario: An accepted design source changes after activation
- **WHEN** a direct source file or declared WorkContext artifact no longer matches the current view's verified source identity
- **THEN** audit reports a typed current-intent source stale, missing, or invalid finding
- **AND** the revision remains an immutable record of its former acceptance but cannot support a current claim

### Requirement: Authority pointer replacement preserves peer manifest writes
Activation and rollback SHALL re-read the project manifest immediately before replacing the authority section. If the frozen authority identity changed, the operation SHALL fail as stale. If only unrelated sections changed, the operation SHALL replace the authority section in the newest manifest text and preserve every unrelated byte-level peer update.

#### Scenario: Peer adds an unrelated manifest section during validation
- **WHEN** activation or rollback freezes the current head and a peer adds or changes a non-authority section before pointer replacement
- **THEN** the transition may complete using the still-matching authority base
- **AND** the peer section remains present after the pointer update

#### Scenario: Peer changes authority during validation
- **WHEN** the authority section or exact head identity changes before pointer replacement
- **THEN** the transition fails its final compare-and-swap and leaves the new pointer unpublished
- **AND** any already written immutable candidate artifacts remain non-current orphans

### Requirement: Explicit legacy migration follows the exact accepted transition chain
The one-way migration SHALL traverse typed historical activation and rollback transitions by exact expected-predecessor-head identity. It SHALL strictly parse the complete admitted historical schema and version-specific invariants. Non-matching orphan transitions SHALL be ignored; zero or multiple exact predecessor matches, malformed artifacts, missing chain members, or broken head links SHALL block migration.

#### Scenario: Orphan shares snapshot and generation with the real predecessor
- **WHEN** an unrelated content-addressed transition has the same candidate snapshot and generation as a true predecessor but reconstructs a different head fingerprint
- **THEN** migration follows the sole exact expected-head match
- **AND** the orphan neither becomes ancestry nor creates false ambiguity

#### Scenario: A v4 label hides a damaged legacy authority
- **WHEN** the current artifact declares the legacy v4 schema but its transition, revision, wire types, content identity, or ancestry invariants are invalid
- **THEN** audit reports invalid legacy authority or ancestry
- **AND** it SHALL NOT report the head as a healthy bootstrap-required base based only on the schema label

### Requirement: Bootstrap intent relations are closed and authority wire is strict
Bootstrap SHALL reject supersede or conflict references outside the exact audited legacy/current intent graph unless a dedicated typed external owner and source is explicitly present. Each supersession SHALL agree in both the historical disposition and current replacement declarations. Content-addressed authority loaders SHALL reject unknown keys, duplicate keys, non-finite values, and wrong raw JSON primitive types before normalization. Derived completion/readiness booleans SHALL be recomputed rather than serialized as independent authority truth.

#### Scenario: Bootstrap contribution names a ghost predecessor or conflict
- **WHEN** a current design contribution supersedes or conflicts with an id absent from the exact legacy ancestry, active current set, and typed external-owner inventory
- **THEN** bootstrap fails before candidate publication
- **AND** the view cannot become complete through an unowned relation

#### Scenario: Authority JSON uses a coercible wrong type
- **WHEN** a boolean is encoded as `"false"`, `0`, `1`, or null, or a text/id/SHA field is encoded as a non-string
- **THEN** strict loading rejects the raw wire before fingerprint comparison or object normalization
- **AND** the wrong value cannot canonicalize into the same authority identity as a valid payload

### Requirement: Path-quality identities publish atomically with model revisions
ModelRevisionSet SHALL include the compact path-quality summary, subject identity, and detailed-evidence fingerprint for every added or replaced model in the same candidate and compare-and-swap activation as model content, cumulative intent, topology, bindings, and owner evidence. The independently derived add-or-replace set SHALL be the minimum required path-quality denominator, not an exact ceiling on supplied rows. A candidate MAY additionally carry path-quality rows for unchanged members through its complete current-model denominator, but every extra row SHALL belong to that same candidate's current model set, share the candidate snapshot, and be exact-current, validated, and resolved. A foreign, retired, stale, cross-snapshot, unvalidated, or unresolved extra row SHALL block acceptance. FlowGuard SHALL NOT maintain a second current path-quality pointer or activate an incomplete mixture of old and new rows.

#### Scenario: One affected model lacks path-quality evidence
- **WHEN** a candidate revision set changes several models and one affected model lacks a current required result
- **THEN** the whole candidate remains unaccepted without moving current authority

#### Scenario: Activation wins compare-and-swap
- **WHEN** all affected model and path-quality identities are current and the expected head still matches
- **THEN** they activate atomically under one transition receipt

#### Scenario: Small increment carries complete current DNA
- **WHEN** an independently derived revision adds or replaces 5 models in a candidate whose complete current-model denominator contains 51 models
- **AND** the candidate carries exact-current path-quality rows for all 51 current models from the same candidate snapshot
- **THEN** the 5 changed models satisfy the minimum required denominator
- **AND** the 46 unchanged current rows remain valid candidate DNA rather than causing an exact-equality rejection

#### Scenario: Extra row is foreign or stale
- **WHEN** all added or replaced models have current path-quality rows
- **AND** one additional row names a model outside the candidate current-model denominator, belongs to another snapshot, or is stale, unvalidated, or unresolved
- **THEN** the candidate remains unaccepted
- **AND** changed-member coverage SHALL NOT license the invalid extra row
