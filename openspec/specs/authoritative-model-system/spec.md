# authoritative-model-system Specification

## Purpose
Define the sole project-level authority that identifies which exact model
system describes the software that exists now. The capability separates
observed implementation, normative target, and counterfactual experiment
snapshots; binds them to exact source, model, relation, coverage, and evidence
identities; and prevents a proposed or locally green model from being reported
as the current software model.
## Requirements
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
coverage universe derived from the live model regression manifest and its
currently resolved source inventory. The universe SHALL independently
enumerate required ids for external API, CLI, UI, schema or file, skill or
agent, and documented surfaces; active behavior commitments; model instances
and system properties; behavior-bearing fields, state, and side effects; code
contracts; tests; and evidence obligations. A stored snapshot's previously
recorded universe SHALL NOT substitute for rebuilding this live universe at a
currentness gate.

#### Scenario: Complete bounded coverage is proven
- **WHEN** a snapshot claims `complete_within_declared_boundary`
- **THEN** the live required ids and snapshot covered ids are equal in every
  declared coverage dimension
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

### Requirement: Observed authority remains revision truthful
An observed snapshot SHALL be current only while a fresh reconstruction from
the live model regression manifest and current source inventory exactly
matches the observed head's subject revision, model-instance identities,
resolved input inventories, required source-surface identities and
fingerprints, referenced owner-artifact identities, coverage-universe
fingerprint, and required evidence. Pointer-to-snapshot self-consistency SHALL
be necessary but SHALL NOT be sufficient for a current authority result.

#### Scenario: Live inventory exactly matches the observed snapshot
- **WHEN** authority audit rebuilds the current source and model inventory
- **AND** every required live identity and fingerprint exactly equals the
  corresponding observed-snapshot identity and fingerprint
- **THEN** the observed head may remain current subject to its native evidence
  gates
- **AND** the audit records the rebuilt live-inventory fingerprint used for
  reconciliation

#### Scenario: Software changes without a matching observed snapshot
- **WHEN** source, deployment, configuration, a required source surface, an
  owner artifact, or another fingerprinted implementation input changes after
  the observed snapshot was validated
- **THEN** the system reports the observed authority as stale or blocked
- **AND** it does not relabel an existing target or experiment as observed

#### Scenario: Stored authority is internally consistent but live inventory differs
- **WHEN** the project pointer, stored snapshot fingerprint, stored subject
  revision, and stored coverage status agree with one another
- **AND** a fresh live reconstruction has a different subject revision,
  model-instance set, source-surface set, owner-artifact fingerprint, resolved
  input inventory, or coverage fingerprint
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

### Requirement: Published observed authority is reconstructable from the release tree
The release verifier SHALL require every file in the selected snapshot's
resolved model input inventory to be reachable from the exact committed source
tree when a project publishes an observed model-system head. A local
working-tree file, ignored file, untracked file, alternate checkout, or
historical evidence artifact SHALL NOT satisfy release authority.

#### Scenario: Every authority input is committed
- **WHEN** release validation examines the selected observed snapshot
- **AND** the snapshot and every declared model input path resolve to the exact committed tree with matching content
- **THEN** the release may treat model-authority Git reachability as satisfied
- **AND** ordinary model currentness and evidence gates remain separately required

#### Scenario: Model input exists only in the local working tree
- **WHEN** the observed snapshot references a model file that exists locally but is ignored or untracked
- **THEN** release validation reports the exact missing path and blocks publication
- **AND** it does not drop that model from the live inventory or infer another authority

#### Scenario: Runner input exists only in the local working tree
- **WHEN** the model file is tracked but its snapshot-declared runner or another resolved input is ignored or untracked
- **THEN** the same authority-input reachability gate blocks publication
- **AND** a locally passing runner execution does not substitute for committed reachability

### Requirement: Affected authority is relationship-complete
For an upgraded behavior surface, the authoritative model system SHALL identify its model owner, source owner, test or check owner, runtime entry when applicable, and explicit gaps; an inventory row alone SHALL NOT prove this relationship coverage.

#### Scenario: Model exists without a validating owner edge
- **WHEN** an affected model is inventoried but no current test/check owner or declared gap is attached
- **THEN** the authority audit reports incomplete affected coverage

### Requirement: Whole-system authority is semantic rather than inventory-only
A whole-system understanding claim SHALL be licensed only when every member of the finite current model universe has a semantic disposition and all required inter-model and consumer relations are current. Presence in the inventory alone SHALL NOT license the claim.

#### Scenario: All model files exist without consumer relations
- **WHEN** the finite universe contains every current model file but required consumer relations are absent
- **THEN** whole-system understanding remains unresolved

#### Scenario: Semantic relation changes after verification
- **WHEN** a model disposition or required relation changes after the whole-system receipt
- **THEN** every consuming whole-system claim becomes stale

### Requirement: Blueprint closure uses an independently discovered implementation universe
The authoritative model system SHALL consume a fingerprinted implementation and reconstruction-resource inventory derived independently from declared models, code contracts, and tests before it licenses a whole-software blueprint claim. Every admitted inventory item SHALL have one explicit disposition, and unresolved files, parse failures, hidden state or effect writers, duplicate primary owners, and omitted reconstruction resources SHALL block static blueprint completion.

#### Scenario: Undeclared helper exists in production source
- **WHEN** independent discovery finds a behavior-bearing helper that is absent from the declared model and contract bindings
- **THEN** static blueprint closure is incomplete and identifies the helper

#### Scenario: Every admitted item has a current disposition
- **WHEN** the current inventory, bindings, resources, and owner fingerprints cover every item inside the declared boundary
- **THEN** the system may report static blueprint complete within that boundary

### Requirement: Static blueprint and empirical reconstruction are separate claims
The authoritative model system SHALL report static blueprint closure independently from empirical reconstruction evidence. Static completion with no reconstruction run SHALL NOT be described as independently reconstructed or empirically verified.

#### Scenario: Static closure passes without a reconstruction receipt
- **WHEN** every static obligation is current and empirical reconstruction has not run
- **THEN** the result reports static complete and reconstruction not-run

#### Scenario: Reconstruction receipt targets another blueprint
- **WHEN** an empirical receipt carries a blueprint fingerprint different from the current manifest
- **THEN** empirical reconstruction is stale or blocked without changing the static result

### Requirement: Blueprint projection remains derived from the sole observed authority
Any portable software-blueprint projection SHALL bind the exact current observed model-system snapshot and existing owner fingerprints. It SHALL NOT create another observed head, copy owner semantics into a competing authority, or remain current after a consumed owner changes.

#### Scenario: Observed snapshot changes after export
- **WHEN** the observed model-system snapshot changes after a blueprint projection is produced
- **THEN** the projection becomes stale until deterministically regenerated
