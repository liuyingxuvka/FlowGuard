## ADDED Requirements

### Requirement: Working deltas cannot impersonate accepted authority
Currentness checks SHALL distinguish an accepted verified snapshot from observed structure and working deltas; loading an old or merely readable snapshot as a fallback SHALL be rejected.

#### Scenario: Accepted snapshot is missing
- **WHEN** the current accepted pointer cannot be verified but a historical snapshot is readable
- **THEN** the route reports `accepted_snapshot_unavailable` and does not claim the historical snapshot is current

### Requirement: Coupling contracts have an acyclic semantic identity

An accepted boundary contract SHALL derive its content fingerprint from its
independent boundary source, finite obligations, materialized relations, and
pointer-free topology only. Snapshot, accepted-revision, head, activation, and
output identities SHALL be verified as external binding context and SHALL NOT
be part of the contract's content-addressed identity.

#### Scenario: The same contract is bound by two authority generations

- **WHEN** the semantic boundary and topology bytes are unchanged but the
  snapshot or accepted revision changes
- **THEN** the contract fingerprint remains unchanged, while the current
  authority loader verifies the new binding through its endpoint and state

#### Scenario: Topology changes

- **WHEN** a model instance, relation, relation evidence, or finite coupling
  obligation changes
- **THEN** the pointer-free contract/topology fingerprint changes and the old
  authority binding cannot be reused as current
