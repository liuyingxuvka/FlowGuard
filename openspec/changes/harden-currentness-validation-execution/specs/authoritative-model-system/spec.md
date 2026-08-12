## MODIFIED Requirements

### Requirement: A project has one observed model-system head
The project SHALL expose exactly one model-authority pointer for the current
`observed_implementation` snapshot. The full head identity SHALL cover the
system id, snapshot fingerprint, subject revision, generation, accepted
revision-set fingerprint, previous-snapshot fingerprint, and activation or
rollback transition receipt fingerprint. No registry label, file discovery
result, model-id suffix, target snapshot, experiment snapshot, same-snapshot
head from another generation, or alternate pointer SHALL act as a fallback
current authority.

#### Scenario: Current-model lookup resolves the sole observed head
- **WHEN** a consumer asks which model system describes the software now
- **THEN** the system resolves and validates the full project model-authority
  head before performing relevance lookup
- **AND** only active members of that exact observed snapshot are eligible as
  current model owners

#### Scenario: Missing or invalid head fails visibly
- **WHEN** the project model-authority pointer is missing, ambiguous, refers to
  a non-observed lane, does not match the referenced snapshot fingerprint, or
  contains an invalid revision or transition identity
- **THEN** current-model lookup reports observed authority as unavailable
- **AND** it does not infer a replacement from discovered files, registry
  entries, lexical matches, historical evidence, or another generation that
  names the same snapshot

#### Scenario: The same snapshot appears in a later generation
- **WHEN** a later accepted transition points to a snapshot fingerprint that
  was also current in an earlier generation
- **THEN** the later head has a distinct full-head fingerprint and transition
  identity
- **AND** a contract bound to the earlier head is stale

### Requirement: Coverage claims use a finite fingerprinted universe
Every broad model-system coverage claim SHALL name a finite, immutable
coverage universe derived from the live model regression manifest and its
currently resolved source inventory. The universe SHALL independently
enumerate required ids for external API, CLI, UI, schema or file, skill or
agent, and documented surfaces; active behavior commitments; model instances
and system properties; behavior-bearing fields, state, and side effects; code
contracts; tests; and evidence obligations. For model instances, the universe
SHALL preserve the exact declared non-excluded id set separately from the
exact materialized id set whose model content and declared runner both exist.
Required model ids SHALL equal the declared non-excluded set, covered model ids
SHALL equal the materialized set, and complete coverage SHALL require the two
sets to be identical. `optional_local`, an absence reason, or another
distribution policy SHALL NOT convert a declared observed-authority model into
an excluded or covered row. A stored snapshot's previously recorded universe
SHALL NOT substitute for rebuilding this live universe at a currentness gate.

#### Scenario: Complete bounded coverage is proven
- **WHEN** a snapshot claims `complete_within_declared_boundary`
- **THEN** the live required ids and snapshot covered ids are equal in every
  declared coverage dimension
- **AND** the declared non-excluded model ids, materialized model-and-runner
  ids, and snapshot model-instance ids are the same exact identity set
- **AND** every referenced evidence obligation is current and passing
- **AND** the claim identifies the live coverage-universe fingerprint and
  boundary

#### Scenario: Coverage has an unresolved or stale row
- **WHEN** any live required id is missing, unknown, excluded without an
  accepted disposition, stale, blocked, skipped, or not run
- **THEN** the system keeps that row visible
- **AND** it reports bounded partial coverage rather than complete coverage

#### Scenario: No finite universe is declared
- **WHEN** a snapshot has no finite fingerprinted coverage universe derived
  from the live manifest and current source inventory
- **THEN** the system rejects claims of full software coverage
- **AND** it may report only the explicitly evidenced local scope

#### Scenario: Stored universe omits a newly available required model
- **WHEN** the live regression manifest and current source inventory resolve a
  required model instance that is absent from the observed snapshot
- **THEN** authority audit reports `observed_source_inventory_stale`
- **AND** the stored snapshot's internally complete coverage rows do not
  satisfy current coverage

#### Scenario: A declared model or runner is absent
- **WHEN** the live manifest declares a non-excluded model id but its model
  content or declared runner is not materialized
- **THEN** authority audit reports `live_model_manifest_incomplete` with the
  exact declared, materialized, and missing identity sets
- **AND** the missing row cannot move into `excluded_ids` or satisfy complete
  observed coverage through `optional_local` or an absence reason

#### Scenario: The frozen current inventory closes sixty-two models
- **WHEN** this change's frozen current manifest declares 62 non-excluded model
  ids
- **THEN** complete observed authority requires 62 materialized model-and-runner
  ids, 62 snapshot model-instance ids, and 62 required and covered model ids
- **AND** zero declared model ids are missing or excluded

### Requirement: Observed authority remains revision truthful
An observed snapshot SHALL be current only while a fresh reconstruction from
the live model regression manifest and current source inventory exactly
matches the complete canonical observed snapshot, including its subject
revision, root identities, model-instance identities, typed relations,
resolved input inventories, required source-surface identities and
fingerprints, referenced owner-artifact identities, coverage universe,
unresolved gaps, evidence identities, and claim boundary. Authority audit
SHALL report the exact live declared, materialized, and missing model-id sets
and the rebuilt live snapshot fingerprint. Pointer-to-snapshot
self-consistency or equality of selected partial projections SHALL be
necessary but SHALL NOT be sufficient for a current authority result.

#### Scenario: Live inventory exactly matches the observed snapshot
- **WHEN** authority audit rebuilds the current source and model inventory
- **AND** every canonical live identity, fingerprint, relation, root, coverage
  row, owner reference, evidence reference, and unresolved gap exactly equals
  the corresponding observed-snapshot value
- **THEN** the observed head may remain current subject to its native evidence
  gates
- **AND** the audit records the rebuilt live-snapshot fingerprint and exact
  declared and materialized model-id sets used for reconciliation

#### Scenario: Software changes without a matching observed snapshot
- **WHEN** source, deployment, configuration, a required source surface, an
  owner artifact, a model or runner, or another fingerprinted implementation
  input changes after the observed snapshot was validated
- **THEN** the system reports the observed authority as stale or blocked
- **AND** it does not relabel an existing target or experiment as observed

#### Scenario: Stored authority is internally consistent but live inventory differs
- **WHEN** the project pointer, stored snapshot fingerprint, stored subject
  revision, and stored coverage status agree with one another
- **AND** a fresh canonical reconstruction has a different subject revision,
  root, model-instance set, relation set, source-surface set, owner-artifact
  fingerprint, resolved input inventory, coverage universe, evidence identity,
  unresolved gap, or claim boundary
- **THEN** authority audit reports `observed_source_inventory_stale`
- **AND** project audit, preflight, activation, release, and broad model
  coverage claims remain blocked until one accepted `ModelRevisionSet` updates
  the observed head

#### Scenario: A target is implemented
- **WHEN** implementation work realizes a validated normative target
- **THEN** the system builds and validates a new
  `observed_implementation` snapshot from the resulting live source inventory
- **AND** it links the new observed snapshot to the target through typed
  realization and supersession relations instead of changing the target's
  subject lane

