## MODIFIED Requirements

### Requirement: WorkContext identities are content addressed and freshness safe
FlowGuard SHALL calculate each context fingerprint from a canonical ordering of
its current artifact inventory, artifact content identities, adapter/native
identities, bounded roots, subject lane, required roles,
behavior-source-surface links, read-only/current flags, and canonical metadata.
At consumption time, FlowGuard MUST re-read every required project-bounded
artifact source and derive whether its content identity is current; a caller
`current` flag or aggregate context hash MUST NOT authorize currentness.
Consumers SHALL declare exact per-artifact and inventory-membership input
edges. A changed context element SHALL stale only consumers whose declared
edges include that element, except that a consumer of the complete inventory
SHALL stale when inventory membership changes.

#### Scenario: An artifact changes after context creation
- **WHEN** covered artifact bytes, identity, role, root, lane, required role,
  source link, or consumed canonical metadata changes
- **THEN** the context fingerprint SHALL change
- **AND** every consumer with an edge to the changed element SHALL become stale
  while unrelated consumers remain current

#### Scenario: Provider acceptance is confused with current content
- **WHEN** a context is content-current but the provider has not validated,
  completed, or archived the native work
- **THEN** WorkContext SHALL remain current only for content identity and SHALL
  make no provider lifecycle claim

#### Scenario: Artifact order varies
- **WHEN** the same artifact set is returned in a different incidental
  filesystem or adapter iteration order
- **THEN** canonical ordering SHALL produce the same context fingerprint

#### Scenario: Source changes after snapshot loading
- **WHEN** a context carries its prior fingerprint and `current=true` but
  re-reading a required bounded source produces a different identity
- **THEN** FlowGuard MUST classify that artifact and its exact dependent
  consumers as stale

#### Scenario: Unrelated context metadata changes
- **WHEN** canonical metadata changes for an artifact that an owner does not
  consume and the owner does not require complete-inventory identity
- **THEN** that owner's input identity and current receipt MUST remain unchanged

#### Scenario: Complete inventory membership changes
- **WHEN** an owner declares the complete WorkContext inventory as an input and
  an artifact is added, removed, or replaced
- **THEN** that owner MUST become stale even if every retained artifact is
  byte-identical

