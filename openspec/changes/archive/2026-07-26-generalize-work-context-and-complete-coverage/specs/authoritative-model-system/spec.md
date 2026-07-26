## MODIFIED Requirements

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
