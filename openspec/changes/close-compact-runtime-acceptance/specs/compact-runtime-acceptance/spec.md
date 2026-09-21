## Purpose

Define a finite, evidence-bound acceptance contract for the compact FlowGuard
runtime so model maps, native checks, public reads, consumer installation, and
release claims cannot be promoted from narrow or stale evidence.

## ADDED Requirements

### Requirement: Closeout uses one frozen current identity

The closeout process MUST bind every implementation, model, test, environment,
owner-plan, and evidence result to one declared starting revision and MUST
preserve an explicit blocked or not-run state when that identity cannot be
verified. Historical receipts or a moved remote revision MUST NOT be silently
reused.

#### Scenario: Baseline and workspace are current

- **WHEN** the closeout starts with the declared FlowGuard revision, source
  inventory, prepared interpreter, and isolated workspace
- **THEN** the process records those identities before any owner executes and
  permits only the declared C01-C12 steps to consume them

#### Scenario: Baseline identity is missing or changed

- **WHEN** a source, environment, or remote identity differs from the frozen
  starting record
- **THEN** the closeout blocks with the exact mismatch and does not reinterpret
  a historical result as current

### Requirement: Native case evidence is explicit and path-bound

Every retained native model-case producer MUST expose an explicit typed result
for its cases, bind that result to its current owner and real workflow or
explorer path, and preserve failure, duplicate, missing, and malformed cases.
Process text, mutable global state, synthetic JSON, or a star-shaped aggregate
MUST NOT be used to infer a successful native result.

#### Scenario: Complete native case result is returned

- **WHEN** a current producer returns all declared cases with valid owner,
  path, and evidence identities
- **THEN** the native gate accepts only those explicit results and records the
  exact leaf and boundary coverage

#### Scenario: Native output is inferred or path evidence is synthetic

- **WHEN** a producer emits only an exit code, stdout, mutable global value,
  malformed JSON, or a synthetic path aggregate
- **THEN** the gate rejects the result and leaves current qualification
  unchanged

### Requirement: Public map reads use the accepted writer binding

The public map and row-location reads MUST resolve only the current accepted
writer binding, header, index, and selected shards. They MUST return the
selected result with zero producers and zero writes, reject bad offsets, hashes,
roots, and headers, and report the selected-slice cost separately from index
and metadata cost.

#### Scenario: Selected map read is current

- **WHEN** a caller requests an accepted selected slice whose binding and
  shard identities match
- **THEN** the read returns the selected models and relations without running a
  producer or writing an authority artifact

#### Scenario: Selected map binding is stale or corrupt

- **WHEN** a header, index, offset, hash, root, or selected shard does not match
  the current acceptance binding
- **THEN** the read rejects the request and does not search an ancestor cache or
  fall back to a full-map read

### Requirement: Self-model currentness follows real source dependencies

The FlowGuard self-model MUST represent current source inputs, model
responsibilities, typed relations, recursive leaf identity, and retired
obligations. A source change MUST make only its declared dependent evidence
stale, while an unmapped or ambiguous input MUST block current acceptance.
The self-model MUST remain a candidate until current native and model evidence
is accepted through the normal authority boundary.

#### Scenario: An implementation input changes

- **WHEN** a source or protected test component consumed by one model changes
  while an independent component is unchanged
- **THEN** the dependent model and relations become stale or are revalidated,
  and the independent component remains separately reusable

#### Scenario: Accepted self-model has stale or unresolved inputs

- **WHEN** an accepted snapshot contains a stale input, unresolved owner,
  unknown retired disposition, or candidate-only semantic mesh
- **THEN** broad current or release confidence remains blocked and the exact
  unresolved identity is reported

### Requirement: Compact public routes and consumer distribution are direct

The compact public surface MUST load only an explicitly selected domain,
reject unknown or conflicting selection, and provide no compatibility reader,
fallback route, old scheduler alias, or root-search rescue. An independent
consumer MUST operate from a clean staged projection with transactional
preflight, full recheck, swap, readback, rollback, and unchanged third-party
files.

#### Scenario: Explicit domain consumer runs independently

- **WHEN** a clean consumer process selects one known domain and has no author
  or other-Guard import path
- **THEN** it runs the selected public operation and reports the exact current
  projection

#### Scenario: Domain is absent, ambiguous, or stage validation fails

- **WHEN** no domain, several domains, a renamed staged file, or a drifted
  projection is supplied
- **THEN** the operation or installation rejects explicitly, restores the old
  bytes when needed, and does not invoke a fallback

### Requirement: Protection and test identity remain complete

Every in-scope retained protection and migrated test node MUST have one exact
current owner, one disposition, and one observable replacement or retirement
reason. Collection and final validation MUST reject new ignore, skip, xfail,
hidden, duplicate, or compatibility escapes.

#### Scenario: Required inventory is mapped

- **WHEN** all retained, ported, and retired nodes are reconciled with the
  current source and test distribution
- **THEN** collection exits without errors and each node has an auditable
  current disposition

#### Scenario: A node is unmapped or hidden

- **WHEN** a required node cannot be collected, has duplicate owners, or is
  suppressed by a new escape
- **THEN** the migration gate blocks and names that node rather than shrinking
  the denominator

### Requirement: Public lifecycle and cross-Guard journeys prove map value

The acceptance suite MUST cover the six public operations, real map add,
change, delete, relation, and recursive growth, and independent execution of
FlowGuard and SkillGuard. Receipts from different maintenance units MUST NOT be
shared.

#### Scenario: Local map growth is affected-only

- **WHEN** one model changes and a connected model is affected while an
  unrelated model remains unchanged
- **THEN** the map shows the new relation and affected closure, preserves the
  unrelated entry, and runs only required producers

#### Scenario: Two Guards are tested together

- **WHEN** a cross-Guard journey is executed in a clean target environment
- **THEN** each Guard remains independently importable and executable and no
  receipt, source path, or owner is borrowed from the other Guard

### Requirement: Freeze and final validation preserve evidence order

FlowGuard MUST accept current native and self-model evidence before the final
delivery freeze. The final full pytest owner MUST run once after freeze, and
the verification step MUST consume the accepted evidence without accepting a
new current pointer or mutating tracked authority.

#### Scenario: Freeze follows current acceptance

- **WHEN** source, test, contract, toolchain, environment, owner plan, model,
  and native identities agree and self-model currentness is accepted
- **THEN** the delivery freeze records one immutable identity and unlocks the
  single final full-test owner

#### Scenario: Final validation is requested before freeze

- **WHEN** current model acceptance, owner-plan identity, or a required native
  result is missing
- **THEN** final validation remains blocked and does not create a substitute
  pointer or broaden the source scope

### Requirement: Measurements and publication remain separate claims

The four performance and installation measurements MUST be tied to the final
freeze and include exact details hashes, cost counters, privacy checks, and
platform/not-run boundaries. Packaging and future patch publication MUST NOT be
claimed from source or CI evidence alone.

#### Scenario: Frozen measurements and installation pass

- **WHEN** all four measurement receipts and isolated installation cases match
  the frozen source and evidence identities
- **THEN** a clean candidate package may be produced with explicit claim
  boundaries and no private evidence

#### Scenario: A measurement or release gate is missing

- **WHEN** a cost receipt, isolated installation proof, final full suite, or
  later release authorization is absent
- **THEN** the candidate or publication claim remains blocked or scoped and the
  existing release remains unchanged
