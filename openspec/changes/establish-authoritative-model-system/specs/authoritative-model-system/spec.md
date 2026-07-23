## ADDED Requirements

### Requirement: Model-system snapshots declare one subject lane
Every model-system snapshot SHALL declare exactly one subject lane:
`observed_implementation`, `normative_target`, or
`counterfactual_experiment`. The subject lane SHALL remain independent from
the snapshot lifecycle, and neither lifecycle labels nor validation success
SHALL change which subject the snapshot describes.

#### Scenario: Observed snapshot describes a concrete software revision
- **WHEN** a snapshot declares the `observed_implementation` subject lane
- **THEN** it identifies the exact source or deployment revision whose behavior
  it describes
- **AND** its observed status is derived from the project authority pointer and
  current evidence rather than from an editable current flag

#### Scenario: Target and experiment remain non-current
- **WHEN** a `normative_target` or `counterfactual_experiment` snapshot passes
  all of its declared checks
- **THEN** the snapshot remains non-authoritative for the software that exists
  now
- **AND** it is reported as target or experimental context rather than as the
  current observed system

### Requirement: A project has one observed model-system head
The project SHALL expose exactly one model-authority pointer for the current
`observed_implementation` snapshot. The pointer SHALL identify the snapshot by
content fingerprint and subject revision, and no registry label, file
discovery result, model-id suffix, target snapshot, experiment snapshot, or
alternate pointer SHALL act as a fallback current authority.

#### Scenario: Current-model lookup resolves the sole observed head
- **WHEN** a consumer asks which model system describes the software now
- **THEN** the system resolves and validates the project model-authority
  pointer before performing relevance lookup
- **AND** only active members of that observed snapshot are eligible as current
  model owners

#### Scenario: Missing or invalid head fails visibly
- **WHEN** the project model-authority pointer is missing, ambiguous, refers to
  a non-observed lane, or does not match the referenced snapshot fingerprint
- **THEN** current-model lookup reports observed authority as unavailable
- **AND** it does not infer a replacement from discovered files, registry
  entries, lexical matches, or historical evidence

### Requirement: Model-system snapshots are immutable and content-addressed
A model-system snapshot SHALL be an immutable, canonical, content-addressed
record. Its fingerprint SHALL cover its subject lane, subject revision,
coverage universe, model-instance references, typed relations, native-owner
references, evidence references, unresolved rows, and claim boundary.

#### Scenario: Snapshot content changes
- **WHEN** any fingerprinted snapshot member, relation, coverage row, evidence
  reference, unresolved row, or claim boundary changes
- **THEN** the system creates a new snapshot with a new fingerprint
- **AND** the previous snapshot remains unchanged and addressable

#### Scenario: Referenced content does not match
- **WHEN** a snapshot reference resolves to content whose fingerprint differs
  from the recorded fingerprint
- **THEN** the snapshot is invalid for lookup, activation, reuse, and coverage
  claims

### Requirement: Model instances have exact immutable identities
Every model instance in a snapshot SHALL bind a stable logical model id and
model kind to the exact model content, runner content, purpose closure,
subject source revision, and resolved input inventory that it represents.
Mutable names such as a `:current` suffix SHALL NOT establish instance identity
or authority.

#### Scenario: Input selector resolves to concrete files
- **WHEN** a runner uses a pattern or selector to choose model inputs
- **THEN** the model-instance identity and its evidence record the resolved
  paths and content hashes
- **AND** a later change to that resolved inventory produces a different
  instance or makes the prior evidence stale

#### Scenario: Mutable current name conflicts with observed membership
- **WHEN** a discovered model uses a current-looking name but its immutable
  instance fingerprint is not an active member of the observed snapshot
- **THEN** the model is reported as non-authoritative candidate or drift
- **AND** it is not selected as a current owner

### Requirement: Snapshots connect existing owners through typed references
A snapshot SHALL connect model instances and existing governance artifacts
through declared typed relations. Supported relation meanings SHALL include
containment, refinement, dependency, delegation, consumption, production,
realization, supersession, validation, and shared-kernel association. A
relation SHALL NOT transfer the native validation responsibility of the
referenced commitment, field, side effect, contract, test, hierarchy, or
process owner.

#### Scenario: Cross-owner relation is evaluated
- **WHEN** a snapshot relates a model instance to a commitment, field
  inventory, code contract, test obligation, or parent closure
- **THEN** the relation identifies both endpoints, its declared type, and the
  exact referenced fingerprints
- **AND** current evidence from the native owner remains required

#### Scenario: Shared kernel does not prove replacement
- **WHEN** two instances declare a shared-kernel or other similarity relation
- **THEN** the relation alone does not authorize deletion, substitution,
  authority transfer, or evidence reuse

### Requirement: Coverage claims use a finite fingerprinted universe
Every broad model-system coverage claim SHALL name a finite, immutable
coverage universe. The universe SHALL independently enumerate required ids for
external API, CLI, UI, schema or file, skill or agent, and documented
surfaces; active behavior commitments; model instances and system properties;
behavior-bearing fields, state, and side effects; code contracts; tests; and
evidence obligations.

#### Scenario: Complete bounded coverage is proven
- **WHEN** a snapshot claims `complete_within_declared_boundary`
- **THEN** required ids and covered ids are equal in every declared coverage
  dimension
- **AND** every referenced evidence obligation is current and passing
- **AND** the claim identifies the coverage-universe fingerprint and boundary

#### Scenario: Coverage has an unresolved or stale row
- **WHEN** any required id is missing, unknown, excluded without an accepted
  disposition, stale, blocked, skipped, or not run
- **THEN** the system keeps that row visible
- **AND** it reports bounded partial coverage rather than complete coverage

#### Scenario: No finite universe is declared
- **WHEN** a snapshot has no finite fingerprinted coverage universe
- **THEN** the system rejects claims of full software coverage
- **AND** it may report only the explicitly evidenced local scope

### Requirement: Observed authority remains revision truthful
An observed snapshot SHALL be current only while its subject revision,
resolved inputs, model members, referenced owner artifacts, and required
evidence still match the software revision represented by the observed head.

#### Scenario: Software changes without a matching observed snapshot
- **WHEN** source, deployment, configuration, or another fingerprinted
  implementation input changes after the observed snapshot was validated
- **THEN** the system reports the observed authority as stale or blocked
- **AND** it does not relabel an existing target or experiment as observed

#### Scenario: A target is implemented
- **WHEN** implementation work realizes a validated normative target
- **THEN** the system builds and validates a new
  `observed_implementation` snapshot for the resulting software revision
- **AND** it links the new observed snapshot to the target through typed
  realization and supersession relations instead of changing the target's
  subject lane
