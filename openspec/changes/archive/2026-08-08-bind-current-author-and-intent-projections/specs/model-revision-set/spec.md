## ADDED Requirements

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
